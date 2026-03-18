"""
Karpathy Autoresearch — Nightly Training Runner
Main entry point for nightly pattern discovery.

Usage:
    python nightly_train.py                    # full nightly run
    python nightly_train.py --db path/to.db    # custom DB path
    python nightly_train.py --dry-run          # feature build only, no rule search
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

# Ensure we can import sibling modules
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_PATH, ARTIFACTS_DIR, ALL_OUTCOME_COLS, get_maturity_tier, update_mes_reference_from_data
from prepare_data import build_modeling_frame
from feature_factory import build_features, get_all_feature_cols
from divergence_features import build_divergence_features
from sequence_features import build_sequence_features
from rule_compiler import compile_all_candidates, evaluate_and_promote
from report_writer import write_nightly_report
from live_rulebook import write_live_rulebook


def run_nightly(db_path: Path = DB_PATH, dry_run: bool = False,
                verbose: bool = True) -> dict:
    """Execute full nightly autoresearch pipeline."""
    start = time.time()
    run_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print("=" * 80)
    print(f"  KARPATHY AUTORESEARCH — NIGHTLY RUN")
    print(f"  {run_ts}")
    print("=" * 80)

    # ── Step 1: Load and prepare data ────────────────────────────────────
    print("\n[1/6] Loading data...")
    df = build_modeling_frame(db_path=db_path, backfill=True, verbose=verbose)

    n_rows = len(df)
    n_days = df['date'].nunique() if n_rows > 0 else 0

    # ── Update /MES reference from live spot data ──────────────────────
    import config as _cfg
    update_mes_reference_from_data(df)
    if verbose:
        print(f"  /MES reference: {_cfg.MES_REFERENCE_PRICE:.1f} ({_cfg.MES_REFERENCE_SOURCE})")

    # ── HARD MATURITY GATE ───────────────────────────────────────────────
    tier = get_maturity_tier(n_days)
    tier_mode = tier['mode']
    tier_label = tier['label']
    max_promoted = tier['max_promoted']
    max_entry = tier.get('max_entry_rules', 0)
    max_skip = tier.get('max_skip_rules', 0)

    print(f"\n  MATURITY TIER: {tier_label}")
    print(f"  Days: {n_days} | Mode: {tier_mode}")
    print(f"  Max promotions: {max_promoted} (entry: {max_entry}, skip: {max_skip})")

    if tier_mode == 'features_only':
        print(f"\n{'!'*60}")
        print(f"  FEATURES ONLY — Only {n_days} trading day(s)")
        print(f"  NO rule search will be performed.")
        print(f"  Pipeline builds features and diagnostics only.")
        print(f"  Collect ≥3 days before pattern evaluation begins.")
        print(f"{'!'*60}\n")

    # ── Step 2: Build features ───────────────────────────────────────────
    print("\n[2/6] Building features...")
    df = build_features(df, verbose=verbose)
    df = build_divergence_features(df, verbose=verbose)
    df = build_sequence_features(df, verbose=verbose)

    feature_cols = get_all_feature_cols(df)
    # Include all zdiv_ columns (including _state which is object-type)
    # so diagnostics_packager can count divergence families accurately.
    zdiv_all_cols = [c for c in df.columns if c.startswith('zdiv_')]
    if verbose:
        print(f"  Total usable features: {len(feature_cols)}")

    if dry_run:
        print("\n[DRY RUN] Stopping after feature build.")
        print(f"  DataFrame: {df.shape[0]} rows × {df.shape[1]} cols")
        return {'status': 'dry_run', 'rows': n_rows, 'features': len(feature_cols)}

    # ── HARD GATE: Stop here if insufficient days ────────────────────────
    if tier_mode == 'features_only':
        elapsed = time.time() - start
        diagnostics = {
            'run_timestamp': run_ts,
            'elapsed_seconds': round(elapsed, 1),
            'db_path': str(db_path),
            'total_snapshots': n_rows,
            'distinct_days': n_days,
            'labeled_rows': 0,
            'total_features': len(feature_cols),
            'feature_columns': feature_cols,
            'zdiv_columns': zdiv_all_cols,
            'candidates_generated': 0,
            'rules_promoted': 0,
            'mes_reference_price': _cfg.MES_REFERENCE_PRICE,
            'mes_reference_source': _cfg.MES_REFERENCE_SOURCE,
            'maturity_mode': tier_mode,
            'maturity_label': tier_label,
        }
        with open(ARTIFACTS_DIR / 'diagnostics.json', 'w') as f:
            json.dump(diagnostics, f, indent=2)

        # Write empty artifacts (ensures no stale rulebooks persist)
        pd.DataFrame().to_csv(ARTIFACTS_DIR / 'rule_leaderboard.csv', index=False)
        with open(ARTIFACTS_DIR / 'accepted_rules.json', 'w') as f:
            json.dump([], f)
        write_live_rulebook([], ARTIFACTS_DIR / 'live_rulebook.py')

        # Write report explaining why no rules
        write_nightly_report(
            promoted=[],
            n_rows=n_rows,
            n_days=n_days,
            n_features=len(feature_cols),
            n_candidates=0,
            preliminary=True,
            maturity_tier=tier,
            output_dir=ARTIFACTS_DIR,
        )

        print(f"\n{'='*80}")
        print(f"  NIGHTLY RUN COMPLETE — FEATURES ONLY")
        print(f"  Elapsed: {elapsed:.1f}s")
        print(f"  Snapshots: {n_rows} | Days: {n_days} | Features: {len(feature_cols)}")
        print(f"  No rules evaluated (need ≥3 days)")
        print(f"  Artifacts: {ARTIFACTS_DIR}")
        print(f"{'='*80}")
        return diagnostics

    # ── Step 3: Filter to rows with forward labels ───────────────────────
    print("\n[3/6] Filtering to labeled rows...")
    fwd_mask = df['fwd_15m'].notna() | df['fwd_30m'].notna() | df['fwd_60m'].notna()
    df_labeled = df[fwd_mask].copy()

    if len(df_labeled) < 50:
        print(f"  Only {len(df_labeled)} rows with forward labels. Need ≥50.")
        print("  Run collector longer, then --fill-returns to backfill.")
        return {'status': 'insufficient_labels', 'labeled_rows': len(df_labeled)}

    if verbose:
        print(f"  Labeled rows: {len(df_labeled)} ({len(df_labeled)/len(df)*100:.0f}%)")

    # ── Step 4: Generate candidate rules ─────────────────────────────────
    print("\n[4/6] Generating candidate rules...")
    candidates = compile_all_candidates(df_labeled, verbose=verbose)

    # ── Step 5: Evaluate and promote (with tier-aware limits) ────────────
    print("\n[5/6] Evaluating candidates...")
    promoted = evaluate_and_promote(
        df_labeled, candidates,
        max_entry_rules=max_entry,
        max_skip_rules=max_skip,
        max_total=max_promoted,
        min_wf_folds=tier.get('min_wf_folds', 0),
        verbose=verbose,
    )

    # ── Step 6: Write artifacts ──────────────────────────────────────────
    print("\n[6/6] Writing artifacts...")

    if promoted:
        leaderboard = pd.DataFrame([s.to_dict() for s in promoted])
        leaderboard.to_csv(ARTIFACTS_DIR / 'rule_leaderboard.csv', index=False)
        print(f"  rule_leaderboard.csv: {len(promoted)} rules")

        accepted = [s.to_dict() for s in promoted]
        with open(ARTIFACTS_DIR / 'accepted_rules.json', 'w') as f:
            json.dump(accepted, f, indent=2, default=str)
        print(f"  accepted_rules.json: {len(accepted)} rules")

        # Always write live_rulebook.py for artifact consistency.
        # In non-live modes, promoted may have rules but they're research-only.
        if tier_mode == 'live':
            write_live_rulebook(promoted, ARTIFACTS_DIR / 'live_rulebook.py')
            print("  live_rulebook.py: written (LIVE mode)")
        else:
            # Write empty rulebook so stale rules from prior runs don't persist
            write_live_rulebook([], ARTIFACTS_DIR / 'live_rulebook.py')
            print(f"  live_rulebook.py: written EMPTY ({tier_mode} mode — not live-tradable)")

        write_nightly_report(
            promoted,
            n_rows=n_rows,
            n_days=n_days,
            n_features=len(feature_cols),
            n_candidates=len(candidates),
            preliminary=(tier_mode != 'live'),
            maturity_tier=tier,
            output_dir=ARTIFACTS_DIR,
        )
        print("  nightly_report.md: written")
        print("  nightly_report.json: written")
    else:
        print("  No rules promoted. Writing empty artifacts.")
        pd.DataFrame().to_csv(ARTIFACTS_DIR / 'rule_leaderboard.csv', index=False)
        with open(ARTIFACTS_DIR / 'accepted_rules.json', 'w') as f:
            json.dump([], f)

        write_nightly_report(
            promoted=[],
            n_rows=n_rows,
            n_days=n_days,
            n_features=len(feature_cols),
            n_candidates=len(candidates),
            preliminary=True,
            maturity_tier=tier,
            output_dir=ARTIFACTS_DIR,
        )

    # Diagnostics
    elapsed = time.time() - start
    diagnostics = {
        'run_timestamp': run_ts,
        'elapsed_seconds': round(elapsed, 1),
        'db_path': str(db_path),
        'total_snapshots': n_rows,
        'distinct_days': n_days,
        'labeled_rows': len(df_labeled),
        'total_features': len(feature_cols),
        'feature_columns': feature_cols,
        'zdiv_columns': zdiv_all_cols,
        'candidates_generated': len(candidates),
        'rules_promoted': len(promoted),
        'mes_reference_price': _cfg.MES_REFERENCE_PRICE,
        'mes_reference_source': _cfg.MES_REFERENCE_SOURCE,
        'maturity_mode': tier_mode,
        'maturity_label': tier_label,
    }
    with open(ARTIFACTS_DIR / 'diagnostics.json', 'w') as f:
        json.dump(diagnostics, f, indent=2)
    print(f"  diagnostics.json: written")

    # Summary
    print(f"\n{'='*80}")
    print(f"  NIGHTLY RUN COMPLETE")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Snapshots: {n_rows} | Days: {n_days} | Features: {len(feature_cols)}")
    print(f"  Candidates: {len(candidates)} | Promoted: {len(promoted)}")
    print(f"  Maturity: {tier_label}")
    print(f"  Artifacts: {ARTIFACTS_DIR}")
    print(f"{'='*80}")

    return diagnostics


def main():
    parser = argparse.ArgumentParser(description='Karpathy Autoresearch Nightly Runner')
    parser.add_argument('--db', type=str, default=str(DB_PATH),
                        help='Path to spy_autoresearch.db')
    parser.add_argument('--dry-run', action='store_true',
                        help='Build features only, skip rule search')
    parser.add_argument('--quiet', action='store_true',
                        help='Reduce output')
    args = parser.parse_args()

    run_nightly(
        db_path=Path(args.db),
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )


if __name__ == '__main__':
    main()
