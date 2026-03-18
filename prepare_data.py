"""
Karpathy Autoresearch — Data Preparation
Loads SQLite snapshots, verifies schema, backfills forward returns if needed,
and outputs a clean modeling DataFrame.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    DB_PATH, ALL_OUTCOME_COLS, FWD_RETURN_COLS, FWD_EXCURSION_COLS,
    LABEL_COLS, ALL_SPY_FAMILIES,
)


def connect_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")
    return sqlite3.connect(str(db_path))


def verify_schema(conn: sqlite3.Connection) -> dict:
    """Check what columns exist and categorize them."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(snapshots)").fetchall()}

    report = {
        'total_columns': len(cols),
        'outcome_present': [c for c in ALL_OUTCOME_COLS if c in cols],
        'outcome_missing': [c for c in ALL_OUTCOME_COLS if c not in cols],
        'has_mes_columns': any(c.startswith('mes_') for c in cols),
    }

    # Count feature families
    for family_name, family_cols in ALL_SPY_FAMILIES.items():
        present = [c for c in family_cols if c in cols]
        report[f'family_{family_name}'] = len(present)

    qqq_count = sum(1 for c in cols if c.startswith('qqq_'))
    div_count = sum(1 for c in cols if c.startswith('div_'))
    report['qqq_columns'] = qqq_count
    report['div_columns'] = div_count

    return report


def check_forward_fill_status(conn: sqlite3.Connection) -> dict:
    """Check how many rows have forward returns filled."""
    total = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    if total == 0:
        return {'total': 0, 'filled': 0, 'pct': 0}

    filled = conn.execute(
        "SELECT COUNT(*) FROM snapshots WHERE fwd_5m IS NOT NULL"
    ).fetchone()[0]

    return {'total': total, 'filled': filled, 'pct': filled / total * 100}


def backfill_if_needed(conn: sqlite3.Connection, db_path: Path = None,
                       force: bool = False):
    """Run forward return backfill if columns are mostly NULL.

    Locates spy_engine_v2.py relative to the actual db_path passed to
    build_modeling_frame(), not the config default.
    """
    status = check_forward_fill_status(conn)
    if status['pct'] > 90 and not force:
        print(f"  Forward returns already {status['pct']:.0f}% filled. Skipping backfill.")
        return

    print(f"  Forward returns {status['pct']:.0f}% filled. Running backfill...")

    # Search for spy_engine_v2.py: first next to the DB, then next to config DB_PATH
    search_dirs = []
    if db_path is not None:
        search_dirs.append(db_path.parent)
    search_dirs.append(DB_PATH.parent)

    spy_engine_path = None
    for d in search_dirs:
        candidate = d / "spy_engine_v2.py"
        if candidate.exists():
            spy_engine_path = candidate
            break

    if spy_engine_path is not None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("spy_engine", str(spy_engine_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.fill_returns(conn)
        print("  Backfill complete.")
    else:
        searched = ', '.join(str(d) for d in search_dirs)
        print(f"  WARNING: Cannot find spy_engine_v2.py in: {searched}")
        print("  Forward returns will remain NULL. Run collector with --fill-returns first.")


def load_snapshots(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load all snapshots into a DataFrame."""
    df = pd.read_sql("SELECT * FROM snapshots ORDER BY timestamp", conn)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
    df['date'] = df['timestamp'].dt.date
    return df


def drop_dead_columns(df: pd.DataFrame, threshold: float = 0.95) -> pd.DataFrame:
    """Drop columns that are >threshold% zero/null."""
    drop = []
    for col in df.columns:
        if col in ALL_OUTCOME_COLS or col in ('id', 'timestamp', 'date'):
            continue
        if df[col].dtype == 'object':
            continue
        total = len(df)
        dead = df[col].isna().sum() + (df[col] == 0).sum()
        if dead / total > threshold:
            drop.append(col)
    if drop:
        print(f"  Dropping {len(drop)} dead columns (>{threshold*100:.0f}% zero/null)")
        df = df.drop(columns=drop)
    return df


def add_trading_day_id(df: pd.DataFrame) -> pd.DataFrame:
    """Add integer trading day ID for walk-forward splits."""
    dates = sorted(df['date'].unique())
    date_map = {d: i for i, d in enumerate(dates)}
    df['day_id'] = df['date'].map(date_map)
    return df


def build_modeling_frame(
    db_path: Path = DB_PATH,
    backfill: bool = True,
    drop_dead: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """Main entry point: load, verify, backfill, clean, return modeling DataFrame."""
    if verbose:
        print(f"Loading data from {db_path}")

    conn = connect_db(db_path)

    # Schema check
    report = verify_schema(conn)
    if verbose:
        print(f"  Schema: {report['total_columns']} columns")
        print(f"  Outcome cols present: {len(report['outcome_present'])}/{len(ALL_OUTCOME_COLS)}")
        if report['has_mes_columns']:
            print("  WARNING: mes_* columns detected but will be ignored")
        print(f"  QQQ: {report['qqq_columns']} cols | DIV: {report['div_columns']} cols")
        for fname in ALL_SPY_FAMILIES:
            print(f"    {fname:12s}: {report[f'family_{fname}']:3d} cols")

    # Backfill forward returns
    if backfill:
        backfill_if_needed(conn, db_path=db_path)

    # Load data
    df = load_snapshots(conn)
    conn.close()

    if verbose:
        n_days = df['date'].nunique() if len(df) > 0 else 0
        print(f"  Loaded {len(df)} snapshots across {n_days} trading day(s)")
        if len(df) > 0:
            print(f"  Time range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

    # Drop dead columns
    if drop_dead:
        df = drop_dead_columns(df)

    # Add day IDs
    df = add_trading_day_id(df)

    # Filter to rows that have at least some forward data
    has_fwd = df[FWD_RETURN_COLS].notna().any(axis=1)
    n_with_fwd = has_fwd.sum()
    if verbose:
        if len(df) > 0:
            print(f"  Rows with forward returns: {n_with_fwd}/{len(df)} ({n_with_fwd/len(df)*100:.0f}%)")
        else:
            print(f"  Rows with forward returns: 0/0 (no data yet)")

    # Warn if insufficient days
    n_days = df['date'].nunique()
    if n_days < 3:
        print(f"\n  ⚠ WARNING: Only {n_days} distinct trading day(s) in DB.")
        print(f"    Walk-forward evaluation requires ≥3 days for meaningful results.")
        print(f"    Pipeline will run but confidence estimates will be marked as preliminary.\n")

    return df


if __name__ == "__main__":
    df = build_modeling_frame(verbose=True)
    print(f"\nFinal modeling frame: {df.shape[0]} rows × {df.shape[1]} cols")
    print(f"Columns by dtype:")
    for dtype, count in df.dtypes.value_counts().items():
        print(f"  {dtype}: {count}")
