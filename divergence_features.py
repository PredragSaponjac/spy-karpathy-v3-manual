"""
Karpathy Autoresearch — SPY ↔ QQQ Intermarket Divergence Features

Full prioritized divergence universe with z-score normalization.

NAMING CONVENTION:
  Raw divergence columns from the DB/collector use the prefix ``div_``
  (e.g. div_gex, div_nope).  These are kept intact.

  Normalized (z-score) divergence columns created HERE use the prefix
  ``zdiv_`` (e.g. zdiv_gex, zdiv_nope) to avoid duplicate column names.

  All derived features (state, widening, narrowing, accel, nonconfirm,
  recoupling, leadlag) are keyed off the ``zdiv_`` columns.

Priority tiers:
  Primary  (1.0): zdiv_nope, zdiv_net_prem, zdiv_net_delta_flow, zdiv_gex, zdiv_atm_iv
  Secondary(0.7): zdiv_gex_normalized, zdiv_pin_score, zdiv_skew_25d, zdiv_skew_10d,
                   zdiv_iv_slope, zdiv_iv_curvature, zdiv_straddle_pct
  Tertiary (0.4): zdiv_dex, zdiv_vex, zdiv_cex, zdiv_pcr_vol, zdiv_awks  (≥5 days only)

All new columns are built in batch dicts and concat'd once per block
to avoid pandas fragmentation warnings.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
import config as _cfg

# ── Priority tiers — read from config at runtime ─────────────────────
_DEFAULT_PRIORITY_TIERS = {
    "primary":   1.0,
    "secondary": 0.7,
    "tertiary":  0.4,
}

def _get_priority_tiers() -> dict:
    """Read priority weights from config (runtime-mutable via HypothesisOverride)."""
    return getattr(_cfg, 'DIVERGENCE_PRIORITY_WEIGHTS', _DEFAULT_PRIORITY_TIERS)

# ── Metric definitions: (spy_col, qqq_col, zdiv_output_name, tier) ───
# Phase 1 — always computed
PHASE1_METRICS = [
    # Primary: core flow + dealer + IV
    ("nope",            "qqq_nope",            "zdiv_nope",            "primary"),
    ("net_prem",        "qqq_net_prem",        "zdiv_net_prem",        "primary"),
    ("net_delta_flow",  "qqq_net_delta_flow",  "zdiv_net_delta_flow",  "primary"),
    ("gex_total",       "qqq_gex_total",       "zdiv_gex",             "primary"),
    ("atm_avg_iv",      "qqq_atm_avg_iv",      "zdiv_atm_iv",          "primary"),
    # Secondary: structure + skew + surface
    ("gex_normalized",  "qqq_gex_normalized",  "zdiv_gex_normalized",  "secondary"),
    ("pin_score",       "qqq_pin_score",       "zdiv_pin_score",       "secondary"),
    ("skew_25d",        "qqq_skew_25d",        "zdiv_skew_25d",        "secondary"),
    ("skew_10d",        "qqq_skew_10d",        "zdiv_skew_10d",        "secondary"),
    ("iv_slope",        "qqq_iv_slope",        "zdiv_iv_slope",        "secondary"),
    ("iv_curvature",    "qqq_iv_curvature",    "zdiv_iv_curvature",    "secondary"),
    # atm_straddle_pct: qqq_atm_straddle_pct not in DB — use atm_straddle instead
    ("atm_straddle",    "qqq_atm_straddle",    "zdiv_straddle_pct",    "secondary"),
]

# Phase 2 — tertiary, only when ≥5 days of data
PHASE2_METRICS = [
    ("dex",      "qqq_dex",      "zdiv_dex",      "tertiary"),
    ("vex",      "qqq_vex",      "zdiv_vex",      "tertiary"),
    ("cex",      "qqq_cex",      "zdiv_cex",      "tertiary"),
    ("pcr_vol",  "qqq_pcr_vol",  "zdiv_pcr_vol",  "tertiary"),
    ("awks",     "qqq_awks",     "zdiv_awks",     "tertiary"),
]

# Metrics suitable for lead-lag analysis (flow/price-based, not surface metrics)
LEAD_LAG_METRICS = [
    "zdiv_nope", "zdiv_net_prem", "zdiv_gex", "zdiv_atm_iv",
]

# Lookback parameters
DYNAMICS_LOOKBACK = 12       # snapshots for widening/narrowing
RECOUPLING_LOOKBACK = 24     # snapshots for recoupling detection
LEAD_LAG_WINDOW = 60         # correlation window
LEAD_LAG_LAGS = [6, 12, 24]  # snapshot lags to test


ZSCORE_ROLLING_WINDOW = 390  # ~1 trading day at 5s intervals (6.5h)

def _safe_zscore_series(s: pd.Series) -> pd.Series:
    """Point-in-time z-score: rolling window with expanding fallback.

    Uses a rolling window for established data, expanding window for early
    rows where we don't have enough history. Never uses future data.
    """
    # Expanding mean/std (point-in-time: only uses data up to current row)
    exp_mean = s.expanding(min_periods=1).mean()
    exp_std = s.expanding(min_periods=1).std()

    # Rolling mean/std (preferred once we have enough data)
    roll_mean = s.rolling(ZSCORE_ROLLING_WINDOW, min_periods=30).mean()
    roll_std = s.rolling(ZSCORE_ROLLING_WINDOW, min_periods=30).std()

    # Use rolling where available, expanding as fallback
    mean = roll_mean.fillna(exp_mean)
    std = roll_std.fillna(exp_std)

    # Avoid division by zero
    std = std.replace(0, np.nan)
    result = (s - mean) / std
    return result.fillna(0.0)


# ─── Relative Strength / Return Spreads ──────────────────────────────────

def _relative_strength(df: pd.DataFrame) -> pd.DataFrame:
    """SPY vs QQQ relative strength measures."""
    if 'spot_chg_pct' not in df.columns or 'qqq_spot_chg_pct' not in df.columns:
        return df

    spy_ret = df['spot_chg_pct'].fillna(0)
    qqq_ret = df.get('qqq_spot_chg_pct', pd.Series(0, index=df.index)).fillna(0)

    new = {}
    new['intermarket_return_spread'] = spy_ret - qqq_ret
    new['intermarket_leader'] = np.where(spy_ret > qqq_ret, 1,
                                np.where(spy_ret < qqq_ret, -1, 0))
    qqq_safe = qqq_ret.replace(0, np.nan)
    new['intermarket_rs_ratio'] = (spy_ret / qqq_safe).fillna(1.0).clip(-5, 5)

    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


# ─── Z-Score Divergences (all tiers) ──────────────────────────────────

def _zscore_divergences(df: pd.DataFrame, metrics: list) -> pd.DataFrame:
    """Compute z-score divergence for each metric pair that has both columns.

    Output columns use the zdiv_ prefix to avoid colliding with raw div_
    columns that already exist in the DB.
    """
    new = {}
    for spy_col, qqq_col, out_col, tier in metrics:
        if spy_col not in df.columns or qqq_col not in df.columns:
            continue
        spy_z = _safe_zscore_series(df[spy_col])
        qqq_z = _safe_zscore_series(df[qqq_col])
        new[out_col] = spy_z - qqq_z

    if new:
        return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
    return df


# ─── Divergence States ──────────────────────────────────────────────────

def _divergence_states(df: pd.DataFrame) -> pd.DataFrame:
    """Classify normalized divergences into discrete state buckets.

    FIX: zdiv_ columns are ALREADY z-score normalized (zero mean, unit
    variance). The old code applied a SECOND expanding z-score on top,
    creating nonlinear distortions especially for early rows. Now uses
    raw zdiv_ values directly with fixed thresholds — correct since
    they're already in z-score space.

    Operates on zdiv_ columns only (not raw div_ from the DB).
    """
    zdiv_cols = [c for c in df.columns
                 if c.startswith('zdiv_') and df[c].dtype != 'object']

    new = {}
    for col in zdiv_cols:
        # zdiv_ values are already z-scores — use directly, no re-normalization
        z = df[col].fillna(0)
        conditions = [z > 1.5, z > 0.5, z < -1.5, z < -0.5]
        choices = ['strong_pos', 'mild_pos', 'strong_neg', 'mild_neg']
        new[f'{col}_state'] = np.select(conditions, choices, default='neutral')

    if new:
        return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
    return df


# ─── Divergence Widening / Narrowing / Acceleration ─────────────────────

def _divergence_dynamics(df: pd.DataFrame, lookback: int = DYNAMICS_LOOKBACK) -> pd.DataFrame:
    """Track whether normalized divergences are widening or narrowing.

    Operates on zdiv_ columns only.
    """
    zdiv_cols = [c for c in df.columns
                 if c.startswith('zdiv_') and df[c].dtype != 'object'
                 and not c.endswith('_state')]

    new = {}
    for col in zdiv_cols:
        abs_div = df[col].abs()
        delta = abs_div - abs_div.shift(lookback)
        new[f'{col}_widening'] = (delta > 0).astype(int)
        new[f'{col}_narrowing'] = (delta < 0).astype(int)
        new[f'{col}_accel'] = delta - delta.shift(lookback)

    if new:
        return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
    return df


# ─── Per-Metric Non-Confirmation Detection ──────────────────────────────

def _non_confirmation(df: pd.DataFrame, metrics: list) -> pd.DataFrame:
    """Detect when SPY and QQQ disagree on direction for each metric.

    Non-confirmation = one is rising while the other is falling (over 6-snapshot diff).
    Output columns use the zdiv_ prefix (e.g. zdiv_nope_nonconfirm).
    """
    new = {}

    # Classic price non-confirmation
    if 'spot_chg_pct' in df.columns and 'qqq_spot_chg_pct' in df.columns:
        spy_dir = np.sign(df['spot_chg_pct'].fillna(0))
        qqq_dir = np.sign(df.get('qqq_spot_chg_pct', pd.Series(0, index=df.index)).fillna(0))
        new['nonconfirm_price'] = (spy_dir != qqq_dir).astype(int)

    # Per-metric non-confirmation (directional disagreement over 6-snapshot window)
    for spy_col, qqq_col, out_col, tier in metrics:
        if spy_col not in df.columns or qqq_col not in df.columns:
            continue
        spy_chg = df[spy_col].diff(6)
        qqq_chg = df[qqq_col].diff(6)
        nc = (
            ((spy_chg > 0) & (qqq_chg <= 0)) |
            ((spy_chg <= 0) & (qqq_chg > 0))
        ).astype(int).fillna(0)
        new[f'{out_col}_nonconfirm'] = nc

    # Composite non-confirmation count
    if new:
        tmp = pd.DataFrame(new, index=df.index)
        nc_cols = [c for c in tmp.columns if c.endswith('_nonconfirm')]
        if nc_cols:
            new['nonconfirm_count'] = tmp[nc_cols].sum(axis=1)
        return pd.concat([df, tmp], axis=1)
    return df


# ─── Per-Metric Recoupling Detection ────────────────────────────────────

def _recoupling(df: pd.DataFrame, lookback: int = RECOUPLING_LOOKBACK) -> pd.DataFrame:
    """Detect when a normalized divergence snaps back (recoupling).

    Operates on zdiv_ columns only.
    """
    zdiv_cols = [c for c in df.columns
                 if c.startswith('zdiv_') and df[c].dtype != 'object'
                 and not c.endswith(('_state', '_widening', '_narrowing',
                                     '_accel', '_nonconfirm', '_recoupling'))]

    new = {}
    for col in zdiv_cols:
        abs_div = df[col].abs()
        median_div = abs_div.rolling(lookback, min_periods=1).median()
        was_wide = abs_div.shift(6) > median_div.shift(6) * 1.5
        now_narrow = abs_div < median_div
        new[f'{col}_recoupling'] = (was_wide & now_narrow).astype(int)

    if new:
        df = pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)

    # Composite recoupling signal
    recouple_cols = [c for c in df.columns if c.endswith('_recoupling')
                     and c.startswith('zdiv_')]
    if recouple_cols:
        composite = df[recouple_cols].sum(axis=1)
        df = pd.concat([df, pd.DataFrame({'intermarket_recoupling': composite}, index=df.index)], axis=1)

    return df


# ─── Lead-Lag Detection (price + key flow metrics) ──────────────────────

def _lead_lag(df: pd.DataFrame) -> pd.DataFrame:
    """Detect QQQ leading SPY or vice versa using lagged correlations.

    Price-based lead-lag + flow-metric lead-lag on zdiv_ columns.
    """
    new = {}

    # Price-based lead-lag (NO lookahead — correlate current with PAST)
    # "QQQ leads SPY" = current SPY correlated with past QQQ (QQQ moved first)
    # "SPY leads QQQ" = current QQQ correlated with past SPY (SPY moved first)
    if 'spot_chg_pct' in df.columns and 'qqq_spot_chg_pct' in df.columns:
        spy = df['spot_chg_pct'].fillna(0)
        qqq = df.get('qqq_spot_chg_pct', pd.Series(0, index=df.index)).fillna(0)

        for lag in LEAD_LAG_LAGS:
            # QQQ leads SPY: correlate current SPY with past QQQ
            qqq_past = qqq.shift(lag)
            corr = spy.rolling(LEAD_LAG_WINDOW, min_periods=12).corr(qqq_past)
            new[f'qqq_leads_spy_{lag}'] = corr.fillna(0)

            # SPY leads QQQ: correlate current QQQ with past SPY
            spy_past = spy.shift(lag)
            corr = qqq.rolling(LEAD_LAG_WINDOW, min_periods=12).corr(spy_past)
            new[f'spy_leads_qqq_{lag}'] = corr.fillna(0)

    # Flow-metric lead-lag on zdiv_ columns (NO lookahead)
    # Correlate current divergence magnitude with PAST magnitude
    for zdiv_col in LEAD_LAG_METRICS:
        if zdiv_col not in df.columns:
            continue
        series = df[zdiv_col].fillna(0)
        for lag in [6, 12]:
            past_abs = series.abs().shift(lag)
            current_abs = series.abs()
            corr = current_abs.rolling(LEAD_LAG_WINDOW, min_periods=12).corr(past_abs)
            new[f'{zdiv_col}_leadlag_{lag}'] = corr.fillna(0)

    if new:
        df = pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)

    # Net lead indicator
    lead_cols_qqq = [c for c in df.columns if c.startswith('qqq_leads_spy_')]
    lead_cols_spy = [c for c in df.columns if c.startswith('spy_leads_qqq_')]
    if lead_cols_qqq and lead_cols_spy:
        net_lead = df[lead_cols_qqq].mean(axis=1) - df[lead_cols_spy].mean(axis=1)
        df = pd.concat([df, pd.DataFrame({'net_lead_signal': net_lead}, index=df.index)], axis=1)

    return df


# ─── Priority-Weighted Composite Intermarket Score ───────────────────────

def _composite_intermarket(df: pd.DataFrame, metrics: list) -> pd.DataFrame:
    """Single composite score summarizing intermarket state, priority-weighted.

    Primary metrics contribute at full weight, secondary at 0.7, tertiary at 0.4.
    Uses zdiv_ columns for lookups.
    """
    priority_tiers = _get_priority_tiers()
    tier_map = {}
    for _, _, out_col, tier in metrics:
        tier_map[out_col] = priority_tiers.get(tier, 0.5)

    components = []
    weights = []

    # Non-confirmation signals (negative = disagreement = caution)
    for col in [c for c in df.columns if c.endswith('_nonconfirm')
                and c.startswith('zdiv_')]:
        base = col.replace('_nonconfirm', '')
        w = tier_map.get(base, 0.5)
        components.append(df[col] * -1)
        weights.append(w)

    # Recoupling signals (positive = convergence = opportunity)
    for col in [c for c in df.columns if c.endswith('_recoupling')
                and c.startswith('zdiv_')]:
        base = col.replace('_recoupling', '')
        w = tier_map.get(base, 0.5)
        components.append(df[col] * 0.5)
        weights.append(w)

    # Net lead signal
    if 'net_lead_signal' in df.columns:
        components.append(df['net_lead_signal'])
        weights.append(1.0)

    if components:
        total_weight = sum(weights)
        weighted_sum = sum(c * w for c, w in zip(components, weights))
        composite = weighted_sum / total_weight if total_weight > 0 else pd.Series(0.0, index=df.index)
    else:
        composite = pd.Series(0.0, index=df.index)

    return pd.concat([df, pd.DataFrame({'intermarket_composite': composite}, index=df.index)], axis=1)


# ─── Phase 2 Gate ─────────────────────────────────────────────────────────

MIN_DAYS_FOR_TERTIARY = 5  # align with PRELIMINARY maturity tier (5-9 days)

def _count_distinct_days(df: pd.DataFrame) -> int:
    """Count distinct trading days in the dataframe."""
    if 'date' in df.columns:
        return df['date'].nunique()
    if 'ts' in df.columns:
        try:
            return pd.to_datetime(df['ts']).dt.date.nunique()
        except Exception:
            pass
    # FIX: 4680 = 6.5 hours * 60 min * 12 (5-sec intervals) per trading day.
    # Old value of 1560 overestimated day count by 3x.
    return max(1, len(df) // 4680)

def _has_enough_data_for_tertiary(df: pd.DataFrame) -> bool:
    """Check if we have enough multi-day data for tertiary metrics.

    Gate at >=5 days (aligned with PRELIMINARY maturity tier) because:
    - Tertiary metrics (dex, vex, cex, pcr_vol) are noisy dealer derivatives
    - Z-score normalization on <5 days produces unreliable baselines
    - At 3-4 days (research mode) only 8 rules are promoted -- tertiary
      divergences would crowd the candidate pool with spurious patterns
    """
    return _count_distinct_days(df) >= MIN_DAYS_FOR_TERTIARY


# ─── Diagnostics ──────────────────────────────────────────────────────────

def _count_family_contributions(df: pd.DataFrame, active_metrics: list) -> dict:
    """Count how many derived features each priority tier contributes.

    Returns dict like:
        {"primary":   {"base": 5, "derived": 42, "total": 47},
         "secondary": {"base": 7, "derived": 55, "total": 62},
         "tertiary":  {"base": 0, "derived": 0, "total": 0}}
    """
    col_tier = {}
    for _, _, out_col, tier in active_metrics:
        col_tier[out_col] = tier

    counts = {}
    for tier_name in ["primary", "secondary", "tertiary"]:
        base_cols = [out for out, t in col_tier.items()
                     if t == tier_name and out in df.columns]
        derived = []
        for base in base_cols:
            for suffix in ['_state', '_widening', '_narrowing', '_accel',
                           '_nonconfirm', '_recoupling']:
                candidate = f'{base}{suffix}'
                if candidate in df.columns:
                    derived.append(candidate)
            for c in df.columns:
                if c.startswith(f'{base}_leadlag_'):
                    derived.append(c)

        counts[tier_name] = {
            "base": len(base_cols),
            "derived": len(derived),
            "total": len(base_cols) + len(derived),
        }
    return counts


# ─── Main Pipeline ───────────────────────────────────────────────────────

def build_divergence_features(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Run full SPY <-> QQQ intermarket feature pipeline.

    Phase 1: Always runs -- primary + secondary metrics.
    Phase 2: Tertiary metrics -- only if >=5 days of data (PRELIMINARY maturity).

    Raw div_* columns from the DB are preserved intact.
    Normalized columns use the zdiv_* prefix.
    """
    if verbose:
        print("Building intermarket divergence features...")

    n_before = len(df.columns)
    n_days = _count_distinct_days(df)

    # Determine which metrics to compute
    active_metrics = list(PHASE1_METRICS)

    tertiary_enabled = _has_enough_data_for_tertiary(df)
    if tertiary_enabled:
        active_metrics.extend(PHASE2_METRICS)
        if verbose:
            print(f"  Phase 2 tertiary metrics ENABLED ({n_days} days >= {MIN_DAYS_FOR_TERTIARY})")
    else:
        if verbose:
            print(f"  Phase 2 tertiary metrics SKIPPED ({n_days} days < {MIN_DAYS_FOR_TERTIARY})")

    # Pipeline stages
    df = _relative_strength(df)
    df = _zscore_divergences(df, active_metrics)

    # Count how many zdiv_ cols were created
    n_zdivs = sum(1 for c in df.columns
                  if c.startswith('zdiv_') and not c.startswith('zdiv_')
                  is False and df[c].dtype != 'object'
                  and '_' not in c[5:].replace('_', '', 0))
    # Simpler: just count base zdiv_ columns
    zdiv_bases = [c for c in df.columns
                  if c.startswith('zdiv_') and df[c].dtype != 'object']

    df = _divergence_states(df)
    df = _divergence_dynamics(df)
    df = _non_confirmation(df, active_metrics)
    df = _recoupling(df)
    df = _lead_lag(df)
    df = _composite_intermarket(df, active_metrics)

    n_after = len(df.columns)

    if verbose:
        phase1_present = sum(1 for _, _, out, _ in PHASE1_METRICS
                             if out in df.columns)
        phase2_present = sum(1 for _, _, out, _ in PHASE2_METRICS
                             if out in df.columns)
        print(f"  Normalized divergence metrics (zdiv_*): "
              f"Phase 1: {phase1_present}, Phase 2: {phase2_present}")
        print(f"  Total intermarket features added: {n_after - n_before}")

        # Verify no duplicate column names
        dupes = df.columns[df.columns.duplicated()].tolist()
        if dupes:
            print(f"  WARNING: duplicate columns detected: {dupes[:10]}")
        else:
            print(f"  No duplicate column names (OK)")

        # Family contribution diagnostics
        contrib = _count_family_contributions(df, active_metrics)
        priority_tiers = _get_priority_tiers()
        total_features = sum(c["total"] for c in contrib.values())
        print(f"\n  Divergence family contribution breakdown:")
        print(f"  {'Tier':<12} {'Weight':<8} {'Base':<6} {'Derived':<9} {'Total':<7} {'% of pool'}")
        print(f"  {'─'*52}")
        for tier_name in ["primary", "secondary", "tertiary"]:
            c = contrib[tier_name]
            w = priority_tiers.get(tier_name, 0)
            pct = (c["total"] / total_features * 100) if total_features > 0 else 0
            status = "" if c["total"] > 0 else " (disabled)"
            print(f"  {tier_name:<12} {w:<8.1f} {c['base']:<6} {c['derived']:<9} "
                  f"{c['total']:<7} {pct:5.1f}%{status}")
        print(f"  {'─'*52}")
        print(f"  {'TOTAL':<12} {'':8} {'':6} {'':9} {total_features:<7}")

        if tertiary_enabled and total_features > 0:
            tert_pct = contrib["tertiary"]["total"] / total_features * 100
            if tert_pct > 30:
                print(f"\n  WARNING: Tertiary metrics are {tert_pct:.0f}% of divergence "
                      f"feature pool -- risk of crowding primary/secondary signal")

    return df


if __name__ == "__main__":
    from prepare_data import build_modeling_frame
    from feature_factory import build_features

    df = build_modeling_frame(verbose=True)
    df = build_features(df, verbose=True)
    df = build_divergence_features(df, verbose=True)

    # Show all new zdiv_ and intermarket columns
    new_cols = [c for c in df.columns if c.startswith('zdiv_')
                or c.startswith('intermarket_')
                or c.startswith('nonconfirm_')
                or c.endswith('_recoupling')
                or 'leads' in c or 'leadlag' in c]
    print(f"\nNew normalized intermarket columns ({len(new_cols)}):")
    for c in sorted(new_cols):
        if df[c].dtype != 'object':
            print(f"  {c}: non-null={df[c].notna().sum()}, mean={df[c].mean():.4f}")
        else:
            print(f"  {c}: (categorical)")

    # Confirm no duplicates
    dupes = df.columns[df.columns.duplicated()].tolist()
    if dupes:
        print(f"\nDUPLICATE COLUMNS: {dupes}")
    else:
        print(f"\nNo duplicate columns (OK)")
