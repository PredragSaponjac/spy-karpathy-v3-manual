"""
Karpathy Autoresearch — Read-Only Trade Simulator
==================================================
Walks through each tick in spy_autoresearch.db (or a CSV export),
applies the accepted rules, and tracks simulated /MES trades with
no overlapping positions.

Usage:
    # Explicit rulebook path:
    python trade_simulator.py --db spy_autoresearch.db --rules-path artifacts/champion/accepted_rules.json

    # Shorthand: champion or challenger
    python trade_simulator.py --db spy_autoresearch.db --champion
    python trade_simulator.py --db spy_autoresearch.db --challenger

    # CSV data source:
    python trade_simulator.py --csv export.csv --champion
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

# ─── Config ──────────────────────────────────────────────────────────────
DEFAULT_DB_PATH = Path(r"C:\Users\18329\Downloads\spy_autoresearch.db")
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
CHAMPION_RULES  = ARTIFACTS_DIR / "champion"  / "accepted_rules.json"
CHALLENGER_RULES = ARTIFACTS_DIR / "challenger" / "accepted_rules.json"

# ─── Disabled Rules (reversible — clear this list to re-enable) ──────────
# Rules listed here are excluded from simulation at load time.
# This does NOT modify accepted_rules.json or any Karpathy artifacts.
DISABLED_RULES = [
    "L_otm_put_pct_low_SHORT_60m",       # audit: -255.83 PnL, 38.5% WR, main loss driver
    "D_zdiv_pin_score_low_SHORT_60m",     # audit: -126.78 PnL, 27.3% WR, overlap conflict loser
    "I_iv_slope_q5_Q0_div_gex_lt_SHORT_30m",  # audit: -$13.01 expectancy, 25% WF, wins 30 conflicts it shouldn't
]

MES_POINT_VALUE = 5.00       # $5 per point on /MES
ROUND_TRIP_COST = 2.50       # commissions
SLIPPAGE        = 2.50       # estimated slippage
TOTAL_COST      = ROUND_TRIP_COST + SLIPPAGE   # $5.00 per trade

QUANTILE_BINS = 5
QUANTILE_MIN_PERIODS = 10    # need at least this many rows for quantile edges


# ─── Feature Engineering (point-in-time safe, mirrors feature_factory.py) ─

def _quantile_bin(series: pd.Series, n_bins: int = QUANTILE_BINS) -> pd.Series:
    """Point-in-time quantile binning using expanding quantile thresholds."""
    n = len(series)
    if n < n_bins:
        return pd.Series(0, index=series.index, dtype="int64")

    result = pd.Series(0, index=series.index, dtype="int64")
    edges = []
    for q in range(1, n_bins):
        edges.append(
            series.expanding(min_periods=max(n_bins, QUANTILE_MIN_PERIODS))
                  .quantile(q / n_bins)
        )
    for edge_series in edges:
        result = result + (series > edge_series).astype(int)

    return result.clip(0, n_bins - 1)


def _safe_zscore_series(s: pd.Series) -> pd.Series:
    """Expanding z-score (point-in-time)."""
    exp_mean = s.expanding(min_periods=1).mean()
    exp_std  = s.expanding(min_periods=1).std().replace(0, np.nan)
    return ((s - exp_mean) / exp_std).fillna(0.0)


def build_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build the derived features that rules reference but the DB lacks."""

    # ── Quantile bins (_q5) ──────────────────────────────────────────────
    bin_cols = [
        "gex_total", "nope", "atm_avg_iv", "skew_25d", "iv_slope",
        "pin_score", "efficiency_ratio", "structural_gate",
        "vix", "tick", "breadth_composite",
        "spot_chg_pct", "spot_velocity",
    ]
    new = {}
    for col in bin_cols:
        if col in df.columns and df[col].dtype != "object":
            new[f"{col}_q5"] = _quantile_bin(df[col], QUANTILE_BINS)
    if new:
        df = pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)

    # ── Z-score divergences (zdiv_) ──────────────────────────────────────
    METRICS = [
        ("nope",            "qqq_nope",            "zdiv_nope"),
        ("net_prem",        "qqq_net_prem",        "zdiv_net_prem"),
        ("net_delta_flow",  "qqq_net_delta_flow",  "zdiv_net_delta_flow"),
        ("gex_total",       "qqq_gex_total",       "zdiv_gex"),
        ("atm_avg_iv",      "qqq_atm_avg_iv",      "zdiv_atm_iv"),
        ("gex_normalized",  "qqq_gex_normalized",  "zdiv_gex_normalized"),
        ("pin_score",       "qqq_pin_score",       "zdiv_pin_score"),
        ("skew_25d",        "qqq_skew_25d",        "zdiv_skew_25d"),
        ("skew_10d",        "qqq_skew_10d",        "zdiv_skew_10d"),
        ("iv_slope",        "qqq_iv_slope",        "zdiv_iv_slope"),
        ("iv_curvature",    "qqq_iv_curvature",    "zdiv_iv_curvature"),
        ("atm_straddle",    "qqq_atm_straddle",    "zdiv_straddle_pct"),
        ("dex",             "qqq_dex",             "zdiv_dex"),
        ("vex",             "qqq_vex",             "zdiv_vex"),
        ("cex",             "qqq_cex",             "zdiv_cex"),
        ("pcr_vol",         "qqq_pcr_vol",         "zdiv_pcr_vol"),
        ("awks",            "qqq_awks",            "zdiv_awks"),
    ]
    zdiv_new = {}
    for spy_col, qqq_col, out_col in METRICS:
        if spy_col in df.columns and qqq_col in df.columns:
            spy_z = _safe_zscore_series(df[spy_col])
            qqq_z = _safe_zscore_series(df[qqq_col])
            zdiv_new[out_col] = spy_z - qqq_z
    if zdiv_new:
        df = pd.concat([df, pd.DataFrame(zdiv_new, index=df.index)], axis=1)

    # ── Divergence states (zdiv_*_state) ─────────────────────────────────
    zdiv_cols = [c for c in df.columns
                 if c.startswith("zdiv_") and df[c].dtype != "object"]
    state_new = {}
    for col in zdiv_cols:
        z = df[col].fillna(0)
        conditions = [z > 1.5, z > 0.5, z < -1.5, z < -0.5]
        choices    = ["strong_pos", "mild_pos", "strong_neg", "mild_neg"]
        state_new[f"{col}_state"] = np.select(conditions, choices, default="neutral")
    if state_new:
        df = pd.concat([df, pd.DataFrame(state_new, index=df.index)], axis=1)

    return df


# ─── Rule Evaluation ─────────────────────────────────────────────────────

def evaluate_predicate(row, predicate: dict) -> bool:
    """Check if a single predicate fires for the given row."""
    feat = predicate["feature"]
    op   = predicate["op"]
    val  = predicate["value"]

    if feat not in row.index:
        return False

    actual = row[feat]
    if pd.isna(actual):
        return False

    if op == "eq":
        return actual == val
    elif op == "gt":
        return actual > val
    elif op == "lt":
        return actual < val
    elif op == "gte" or op == "ge":
        return actual >= val
    elif op == "lte" or op == "le":
        return actual <= val
    elif op == "between":
        val_hi = predicate.get("value_hi", val)
        return val <= actual <= val_hi
    elif op == "ne":
        return actual != val
    else:
        return False


def evaluate_rule(row, rule: dict) -> bool:
    """All predicates must fire for the rule to trigger."""
    return all(evaluate_predicate(row, p) for p in rule["predicates"])


# ─── Deterministic Rule Ranking ──────────────────────────────────────────

def _rule_rank_key(rule: dict):
    """Sort key for deterministic best-match selection among same-bar candidates.

    Rank order (descending priority):
    1. Higher composite_score
    2. Higher mes_net_expectancy_usd
    3. Higher support
    4. Lexical rule name (stable tie-breaker, ascending)
    """
    return (
        -rule.get("composite_score", 0),
        -rule.get("mes_net_expectancy_usd", 0),
        -rule.get("support", 0),
        rule.get("name", ""),
    )


# ─── Simulator ────────────────────────────────────────────────────────────

def _parse_args():
    """Parse CLI arguments for data source and rulebook selection."""
    parser = argparse.ArgumentParser(
        description="Karpathy Autoresearch Trade Simulator"
    )
    # Data source (required — pick one)
    data_group = parser.add_mutually_exclusive_group(required=True)
    data_group.add_argument("--db", type=str, default=None,
                            help="Path to SQLite database (spy_autoresearch.db)")
    data_group.add_argument("--csv", type=str, default=None,
                            help="Path to CSV export")

    # Rulebook source (required — pick one)
    rules_group = parser.add_mutually_exclusive_group(required=True)
    rules_group.add_argument("--champion", action="store_true",
                             help="Use champion rulebook (artifacts/champion/accepted_rules.json)")
    rules_group.add_argument("--challenger", action="store_true",
                             help="Use challenger rulebook (artifacts/challenger/accepted_rules.json)")
    rules_group.add_argument("--rules-path", type=str, default=None,
                             help="Explicit path to accepted_rules.json")

    return parser.parse_args()


def _load_from_db(db_path: str) -> pd.DataFrame:
    """Load snapshot data from SQLite database."""
    path = Path(db_path)
    if not path.exists():
        print(f"  ERROR: DB file not found: {path}")
        sys.exit(1)
    print(f"\nLoading data from {path} ...")
    conn = sqlite3.connect(str(path))
    df = pd.read_sql("SELECT * FROM snapshots ORDER BY timestamp", conn)
    conn.close()
    return df


def _load_from_csv(csv_path: str) -> pd.DataFrame:
    """Load snapshot data from CSV export."""
    path = Path(csv_path)
    if not path.exists():
        print(f"  ERROR: CSV file not found: {path}")
        sys.exit(1)
    print(f"\nLoading data from {path} ...")
    df = pd.read_csv(str(path))
    # Sort by timestamp to match DB ordering
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def _preflight_check(df: pd.DataFrame, rules: list) -> None:
    """Validate that all columns required by rules (or their base columns)
    exist in the DataFrame. Fails closed on missing base columns."""

    # Columns that build_derived_features() will create
    DERIVED_PREFIXES = ("_q5", "zdiv_")

    # Collect all features referenced by rules
    rule_feats = set()
    for r in rules:
        for p in r["predicates"]:
            rule_feats.add(p["feature"])

    # Split into base (must exist now) vs derived (will be created)
    base_needed = set()
    derived_needed = set()
    for f in rule_feats:
        if any(f.endswith(sfx) or f.startswith(pfx)
               for sfx, pfx in [("_q5", "zdiv_"), ("_state", "zdiv_")]):
            derived_needed.add(f)
        else:
            base_needed.add(f)

    # Check base columns
    existing = set(df.columns)
    missing_base = base_needed - existing
    if missing_base:
        print(f"\n  FATAL: {len(missing_base)} base column(s) missing from data:")
        for m in sorted(missing_base):
            print(f"    - {m}")
        print("\n  Cannot proceed. These columns are required by rules and are NOT")
        print("  derivable by build_derived_features().")
        sys.exit(1)

    # Check that base columns needed for derived features exist
    # _q5 columns need their base column (e.g. atm_avg_iv_q5 needs atm_avg_iv)
    for feat in derived_needed:
        if feat.endswith("_q5"):
            base_col = feat.replace("_q5", "")
            if base_col not in existing:
                print(f"\n  FATAL: Base column '{base_col}' missing (needed to derive '{feat}')")
                sys.exit(1)
        elif feat.endswith("_state") and feat.startswith("zdiv_"):
            # zdiv_nope_state → needs zdiv_nope → needs (nope, qqq_nope)
            # Map from zdiv state column back to the exact raw base pair
            ZDIV_BASE_MAP = {
                "zdiv_nope":            ("nope",           "qqq_nope"),
                "zdiv_net_prem":        ("net_prem",       "qqq_net_prem"),
                "zdiv_net_delta_flow":  ("net_delta_flow", "qqq_net_delta_flow"),
                "zdiv_gex":             ("gex_total",      "qqq_gex_total"),
                "zdiv_atm_iv":          ("atm_avg_iv",     "qqq_atm_avg_iv"),
                "zdiv_gex_normalized":  ("gex_normalized", "qqq_gex_normalized"),
                "zdiv_pin_score":       ("pin_score",      "qqq_pin_score"),
                "zdiv_skew_25d":        ("skew_25d",       "qqq_skew_25d"),
                "zdiv_skew_10d":        ("skew_10d",       "qqq_skew_10d"),
                "zdiv_iv_slope":        ("iv_slope",       "qqq_iv_slope"),
                "zdiv_iv_curvature":    ("iv_curvature",   "qqq_iv_curvature"),
                "zdiv_straddle_pct":    ("atm_straddle",   "qqq_atm_straddle"),
                "zdiv_dex":             ("dex",            "qqq_dex"),
                "zdiv_vex":             ("vex",            "qqq_vex"),
                "zdiv_cex":             ("cex",            "qqq_cex"),
                "zdiv_pcr_vol":         ("pcr_vol",        "qqq_pcr_vol"),
                "zdiv_awks":            ("awks",           "qqq_awks"),
            }
            # Strip _state to get the zdiv column name
            zdiv_col = feat.replace("_state", "")
            pair = ZDIV_BASE_MAP.get(zdiv_col)
            if pair is None:
                print(f"\n  FATAL: Unknown zdiv mapping for '{feat}' (zdiv_col='{zdiv_col}')")
                sys.exit(1)
            spy_col, qqq_col = pair
            missing_pair = []
            if spy_col not in existing:
                missing_pair.append(spy_col)
            if qqq_col not in existing:
                missing_pair.append(qqq_col)
            if missing_pair:
                print(f"\n  FATAL: Raw column(s) missing for rule feature '{feat}':")
                for m in missing_pair:
                    print(f"    - {m}")
                print(f"  Derivation chain: {feat} → {zdiv_col} → ({spy_col}, {qqq_col})")
                sys.exit(1)

    print("  Preflight check passed — all required base columns present.")


def run_simulation():
    args = _parse_args()

    print("=" * 72)
    print("  KARPATHY AUTORESEARCH — TRADE SIMULATOR")
    print("=" * 72)

    # Resolve rulebook path
    if args.champion:
        rules_path = CHAMPION_RULES
        rulebook_label = "CHAMPION"
    elif args.challenger:
        rules_path = CHALLENGER_RULES
        rulebook_label = "CHALLENGER"
    else:
        rules_path = Path(args.rules_path)
        rulebook_label = str(rules_path)

    if not rules_path.exists():
        print(f"  FATAL: Rulebook not found: {rules_path}")
        sys.exit(1)

    print(f"\n  Rulebook: {rulebook_label}")
    print(f"  Path:     {rules_path}")

    # Load rules
    with open(rules_path) as f:
        rules = json.load(f)

    # Apply denylist (reversible — edit DISABLED_RULES to re-enable)
    if DISABLED_RULES:
        before = len(rules)
        disabled = [r for r in rules if r["name"] in DISABLED_RULES]
        rules = [r for r in rules if r["name"] not in DISABLED_RULES]
        for d in disabled:
            print(f"  DISABLED: {d['name']} (removed from simulation)")
        print(f"  {before} loaded, {len(disabled)} disabled, {len(rules)} active")

    trade_rules = [r for r in rules if r["direction"] != "SKIP"]
    skip_rules  = [r for r in rules if r["direction"] == "SKIP"]

    print(f"\nActive rules: {len(rules)} ({len(trade_rules)} trade, {len(skip_rules)} skip)")
    for r in rules:
        print(f"  {r['direction']:5s} {r['horizon_min']:3d}m  {r['name']}")

    # Load data
    if args.db:
        df = _load_from_db(args.db)
    else:
        df = _load_from_csv(args.csv)
    print(f"  {len(df):,} rows, {df.shape[1]} columns")

    # Parse timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
    df["date"] = df["timestamp"].dt.date

    # Preflight validation
    print("\nRunning preflight column check ...")
    _preflight_check(df, rules)

    dates = sorted(df["date"].unique())
    print(f"  {len(dates)} trading days: {dates[0]} to {dates[-1]}")

    # Build derived features
    print("\nBuilding derived features (quantile bins, zdiv states) ...")
    df = build_derived_features(df)
    print(f"  Done. Frame now has {df.shape[1]} columns.")

    # Verify rule features exist
    all_feats = set()
    for r in rules:
        for p in r["predicates"]:
            all_feats.add(p["feature"])
    missing = all_feats - set(df.columns)
    if missing:
        print(f"\n  WARNING: {len(missing)} rule features missing from data:")
        for m in sorted(missing):
            print(f"    - {m}")
        print("  Rules using missing features will never fire.\n")

    # Sort trade rules by composite score (best-first for deterministic selection)
    trade_rules.sort(key=_rule_rank_key)

    # ── Simulation loop ──────────────────────────────────────────────────
    print("\nRunning simulation ...\n")

    all_trades = []
    daily_stats = {}
    rule_stats  = defaultdict(lambda: {"trades": 0, "wins": 0, "losses": 0,
                                        "pnl": 0.0, "gross_pnl": 0.0})

    # Suppression tracking
    suppression_log = []
    suppressed_same_bar = 0
    suppressed_trade_open = 0
    raw_signal_count = 0
    rule_suppressed_counts = defaultdict(int)
    rule_win_counts = defaultdict(int)       # times a rule won same-bar conflict

    for day in dates:
        day_df = df[df["date"] == day].reset_index(drop=True)
        if len(day_df) < 10:
            continue

        open_trade = None          # only one position at a time
        day_trades = []

        for idx in range(len(day_df)):
            row = day_df.iloc[idx]
            ts  = row["timestamp"]

            # ── Check if open trade expires ──────────────────────────────
            if open_trade is not None:
                if ts >= open_trade["exit_time"]:
                    open_trade = None   # position closed, slot free

            # ── Collect all matching trade rules for this bar ────────────
            # (needed for suppression logging even when trade is open)
            matching_rules = []
            for rule in trade_rules:
                if evaluate_rule(row, rule):
                    matching_rules.append(rule)

            if matching_rules:
                raw_signal_count += len(matching_rules)

            # ── If in a position, log and skip all signals ───────────────
            if open_trade is not None:
                for rule in matching_rules:
                    suppression_log.append({
                        "timestamp": str(ts),
                        "rule": rule["name"],
                        "reason": "trade_open",
                        "active_rule": open_trade["rule"],
                        "active_exit": str(open_trade["exit_time"]),
                    })
                    suppressed_trade_open += 1
                    rule_suppressed_counts[rule["name"]] += 1
                continue

            # ── Check skip rules first ───────────────────────────────────
            skipped = False
            for sr in skip_rules:
                if evaluate_rule(row, sr):
                    skipped = True
                    break

            if skipped:
                continue

            # ── No matching trade rules ──────────────────────────────────
            if not matching_rules:
                continue

            # ── Pick best matching rule (already sorted by composite) ────
            # Try each in rank order until one has valid forward data
            winner = None
            winner_trade = None

            for rule in matching_rules:
                horizon = rule["horizon_min"]
                direction = rule["direction"]

                fwd_col = f"fwd_{horizon}m"
                if fwd_col not in row.index or pd.isna(row[fwd_col]):
                    continue

                fwd_return_pct = row[fwd_col]
                spot = row["spot"]
                if pd.isna(spot) or spot == 0:
                    continue

                fwd_points = spot * 10 * (fwd_return_pct / 100.0)  # spot is SPY, multiply by 10 for /MES points

                if direction == "LONG":
                    gross_pnl = fwd_points * MES_POINT_VALUE
                elif direction == "SHORT":
                    gross_pnl = -fwd_points * MES_POINT_VALUE
                else:
                    continue

                net_pnl = gross_pnl - TOTAL_COST
                exit_time = ts + pd.Timedelta(minutes=horizon)

                winner = rule
                winner_trade = {
                    "date":       day,
                    "entry_time": ts,
                    "exit_time":  exit_time,
                    "rule":       rule["name"],
                    "direction":  direction,
                    "horizon":    horizon,
                    "spot":       spot,
                    "fwd_pct":    fwd_return_pct,
                    "fwd_pts":    fwd_points,
                    "gross_pnl":  gross_pnl,
                    "net_pnl":    net_pnl,
                    "win":        net_pnl > 0,
                }
                break  # first valid rule in ranked order wins

            if winner is None:
                continue

            # ── Log same-bar losers ──────────────────────────────────────
            for rule in matching_rules:
                if rule["name"] == winner["name"]:
                    continue
                suppression_log.append({
                    "timestamp": str(ts),
                    "rule": rule["name"],
                    "reason": "same_bar_conflict",
                    "winning_rule": winner["name"],
                })
                suppressed_same_bar += 1
                rule_suppressed_counts[rule["name"]] += 1

            rule_win_counts[winner["name"]] += 1

            # ── Execute winning trade ────────────────────────────────────
            day_trades.append(winner_trade)
            all_trades.append(winner_trade)

            rs = rule_stats[winner["name"]]
            rs["trades"] += 1
            rs["pnl"]    += winner_trade["net_pnl"]
            rs["gross_pnl"] += winner_trade["gross_pnl"]
            if winner_trade["net_pnl"] > 0:
                rs["wins"] += 1
            else:
                rs["losses"] += 1

            open_trade = winner_trade

        # Day summary
        n_trades = len(day_trades)
        wins     = sum(1 for t in day_trades if t["win"])
        losses   = n_trades - wins
        day_pnl  = sum(t["net_pnl"] for t in day_trades)

        daily_stats[day] = {
            "trades": n_trades,
            "wins":   wins,
            "losses": losses,
            "pnl":    day_pnl,
        }

    # ── Output Results ───────────────────────────────────────────────────
    print("=" * 72)
    print("  PER-DAY BREAKDOWN")
    print("=" * 72)
    print(f"{'Date':>12s}  {'Trades':>6s}  {'Wins':>5s}  {'Losses':>6s}  {'Daily P&L':>10s}")
    print("-" * 50)

    total_pnl   = 0.0
    total_trades = 0
    total_wins   = 0
    total_losses = 0
    daily_pnls   = []

    for day in sorted(daily_stats.keys()):
        s = daily_stats[day]
        total_pnl    += s["pnl"]
        total_trades += s["trades"]
        total_wins   += s["wins"]
        total_losses += s["losses"]
        daily_pnls.append(s["pnl"])
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        print(f"{str(day):>12s}  {s['trades']:6d}  {s['wins']:5d}  {s['losses']:6d}  ${s['pnl']:>9.2f}")

    print("-" * 50)
    print(f"{'TOTAL':>12s}  {total_trades:6d}  {total_wins:5d}  {total_losses:6d}  ${total_pnl:>9.2f}")

    # ── Per-Rule Breakdown ───────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  PER-RULE BREAKDOWN")
    print("=" * 72)
    print(f"{'Rule':<55s}  {'N':>5s}  {'Win%':>5s}  {'Net P&L':>10s}  {'Avg':>8s}")
    print("-" * 90)

    for name in sorted(rule_stats.keys(), key=lambda k: rule_stats[k]["pnl"], reverse=True):
        rs = rule_stats[name]
        wr = (rs["wins"] / rs["trades"] * 100) if rs["trades"] > 0 else 0
        avg = rs["pnl"] / rs["trades"] if rs["trades"] > 0 else 0
        print(f"{name:<55s}  {rs['trades']:5d}  {wr:5.1f}  ${rs['pnl']:>9.2f}  ${avg:>7.2f}")

    # ── Summary Stats ────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  SUMMARY")
    print("=" * 72)

    n_days = len([d for d in daily_stats.values() if d["trades"] > 0])
    avg_trades_day = total_trades / n_days if n_days > 0 else 0
    avg_daily_pnl  = total_pnl / n_days if n_days > 0 else 0
    overall_wr     = (total_wins / total_trades * 100) if total_trades > 0 else 0

    print(f"  Trading days:       {n_days}")
    print(f"  Total trades:       {total_trades}")
    print(f"  Avg trades/day:     {avg_trades_day:.1f}")
    print(f"  Overall win rate:   {overall_wr:.1f}%")
    print(f"  Total P&L:          ${total_pnl:,.2f}")
    print(f"  Avg daily P&L:      ${avg_daily_pnl:,.2f}")

    if total_trades > 0:
        avg_win  = np.mean([t["net_pnl"] for t in all_trades if t["win"]]) if total_wins > 0 else 0
        avg_loss = np.mean([t["net_pnl"] for t in all_trades if not t["win"]]) if total_losses > 0 else 0
        print(f"  Avg winning trade:  ${avg_win:,.2f}")
        print(f"  Avg losing trade:   ${avg_loss:,.2f}")
        if avg_loss != 0:
            print(f"  Profit factor:      {abs(sum(t['net_pnl'] for t in all_trades if t['win']) / sum(t['net_pnl'] for t in all_trades if not t['win'])):.2f}")

    # ── Max Drawdown ─────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  DRAWDOWN ANALYSIS")
    print("=" * 72)

    if all_trades:
        # Trade-by-trade equity curve
        equity = [0.0]
        for t in all_trades:
            equity.append(equity[-1] + t["net_pnl"])

        equity = np.array(equity)
        running_max = np.maximum.accumulate(equity)
        drawdowns   = equity - running_max
        max_dd      = drawdowns.min()
        max_dd_idx  = drawdowns.argmin()

        # Find peak before max drawdown
        peak_idx = np.argmax(equity[:max_dd_idx + 1])

        print(f"  Max drawdown:       ${max_dd:,.2f}")
        print(f"  Peak equity:        ${running_max[max_dd_idx]:,.2f}")
        print(f"  Trough equity:      ${equity[max_dd_idx]:,.2f}")
        print(f"  Trades to peak:     {peak_idx}")
        print(f"  Trades to trough:   {max_dd_idx}")
        print(f"  Final equity:       ${equity[-1]:,.2f}")

        # Consecutive losses
        streak = 0
        max_loss_streak = 0
        streak_loss = 0.0
        max_streak_loss = 0.0
        for t in all_trades:
            if not t["win"]:
                streak += 1
                streak_loss += t["net_pnl"]
                max_loss_streak = max(max_loss_streak, streak)
                max_streak_loss = min(max_streak_loss, streak_loss)
            else:
                streak = 0
                streak_loss = 0.0

        print(f"  Max losing streak:  {max_loss_streak} trades")
        print(f"  Worst streak P&L:   ${max_streak_loss:,.2f}")

        # Daily drawdown
        cum_daily = np.cumsum(daily_pnls)
        daily_running_max = np.maximum.accumulate(cum_daily)
        daily_dd = cum_daily - daily_running_max
        max_daily_dd = daily_dd.min()
        print(f"  Max daily drawdown: ${max_daily_dd:,.2f}")
    else:
        print("  No trades to analyze.")

    # ── Trade Distribution ───────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  TRADE DISTRIBUTION")
    print("=" * 72)

    if all_trades:
        pnls = [t["net_pnl"] for t in all_trades]
        print(f"  Min trade P&L:      ${min(pnls):,.2f}")
        print(f"  Max trade P&L:      ${max(pnls):,.2f}")
        print(f"  Median trade P&L:   ${np.median(pnls):,.2f}")
        print(f"  Std dev:            ${np.std(pnls):,.2f}")

        # By direction
        for d in ["LONG", "SHORT"]:
            dt = [t for t in all_trades if t["direction"] == d]
            if dt:
                dpnl = sum(t["net_pnl"] for t in dt)
                dwr  = sum(1 for t in dt if t["win"]) / len(dt) * 100
                print(f"  {d:5s}: {len(dt)} trades, {dwr:.1f}% win rate, ${dpnl:,.2f} P&L")

        # By horizon
        for h in sorted(set(t["horizon"] for t in all_trades)):
            ht = [t for t in all_trades if t["horizon"] == h]
            hpnl = sum(t["net_pnl"] for t in ht)
            hwr  = sum(1 for t in ht if t["win"]) / len(ht) * 100
            print(f"  {h}m horizon: {len(ht)} trades, {hwr:.1f}% win rate, ${hpnl:,.2f} P&L")

    # ── Overlap / Suppression Summary ─────────────────────────────────────
    print("\n" + "=" * 72)
    print("  OVERLAP & SUPPRESSION SUMMARY")
    print("=" * 72)

    total_suppressed = suppressed_same_bar + suppressed_trade_open
    print(f"  Raw candidate signals:   {raw_signal_count}")
    print(f"  Executed trades:         {total_trades}")
    print(f"  Total suppressed:        {total_suppressed}")
    print(f"    Same-bar conflict:     {suppressed_same_bar}")
    print(f"    Trade already open:    {suppressed_trade_open}")

    if rule_suppressed_counts:
        print(f"\n  Top suppressed rules:")
        top_suppressed = sorted(rule_suppressed_counts.items(),
                                key=lambda x: -x[1])[:5]
        for name, count in top_suppressed:
            print(f"    {name}: {count} times")

    if rule_win_counts:
        print(f"\n  Top same-bar conflict winners:")
        top_winners = sorted(rule_win_counts.items(),
                             key=lambda x: -x[1])[:5]
        for name, count in top_winners:
            print(f"    {name}: won {count} conflicts")

    if raw_signal_count > 0:
        exec_rate = total_trades / raw_signal_count * 100
        print(f"\n  Execution rate:          {exec_rate:.1f}% of raw signals")

    print("\n" + "=" * 72)
    print("  Simulation complete.")
    print("=" * 72)


if __name__ == "__main__":
    run_simulation()
