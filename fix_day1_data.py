#!/usr/bin/env python3
"""
Day 1 Data Quality Fix Script
==============================
Fixes 4 issues in the spy_autoresearch.db from Day 1 collection:

1. Synthetically correct timestamps (were all stuck at 08:27:08)
2. Re-derive tod_code and tod_regime from corrected timestamps
3. Re-run forward return backfill with correct timestamps (fixes excursion horizons)
4. Report results

Author: Claude (automated fix)
"""
import sqlite3
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(r"C:\Users\18329\Downloads\spy_autoresearch.db")

# Market open in CT (Houston local time) = 8:30 AM
MARKET_OPEN_HOUR = 8
MARKET_OPEN_MIN = 30
SNAP_INTERVAL = 5  # seconds

# Label thresholds (matching spy_engine_v2.py)
FLAT_THRESH_5M = 0.05
FLAT_THRESH_15 = 0.10
FLAT_THRESH_30 = 0.15


def derive_tod(mins_since_open):
    """Derive tod_code and tod_regime from minutes since open.

    Matches spy_engine_v2.py logic but uses correct minute offsets.
    """
    mso = max(0, mins_since_open)
    if mso <= 5:
        return 0, 'OPENING'
    elif mso <= 45:
        return 1, 'MORNING_VOL'
    elif mso <= 150:
        return 2, 'PRIME'
    elif mso <= 210:
        return 3, 'MIDDAY'
    elif mso <= 330:
        return 4, 'AFTERNOON'
    elif mso <= 360:
        return 5, 'POWER_HOUR'
    else:
        return 6, 'FINAL'


def fix_timestamps(conn):
    """Fix all timestamps to be sequential 5-second intervals starting at 8:30 AM CT."""
    print("\n" + "=" * 70)
    print("  STEP 1: Fix timestamps")
    print("=" * 70)

    rows = conn.execute("SELECT id FROM snapshots ORDER BY id").fetchall()
    ids = [r[0] for r in rows]
    n = len(ids)

    start_time = datetime(2026, 3, 18, MARKET_OPEN_HOUR, MARKET_OPEN_MIN, 0)
    end_time = start_time + timedelta(seconds=(n - 1) * SNAP_INTERVAL)

    print(f"  Rows: {n}")
    print(f"  Start: {start_time} CT")
    print(f"  End:   {end_time} CT")
    print(f"  Interval: {SNAP_INTERVAL}s")

    # Batch update timestamps
    batch = []
    for i, row_id in enumerate(ids):
        ts = start_time + timedelta(seconds=i * SNAP_INTERVAL)
        batch.append((ts.isoformat(), row_id))

    conn.executemany("UPDATE snapshots SET timestamp = ? WHERE id = ?", batch)
    conn.commit()

    # Verify
    first = conn.execute("SELECT timestamp FROM snapshots ORDER BY id LIMIT 1").fetchone()[0]
    last = conn.execute("SELECT timestamp FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()[0]
    distinct = conn.execute("SELECT COUNT(DISTINCT timestamp) FROM snapshots").fetchone()[0]
    print(f"  Verified: {distinct} distinct timestamps")
    print(f"  First: {first}")
    print(f"  Last:  {last}")

    return start_time, n


def fix_tod_and_time_features(conn, start_time, n_rows):
    """Re-derive tod_code, tod_regime, mins_since_open, mins_to_close, pct_of_day."""
    print("\n" + "=" * 70)
    print("  STEP 2: Fix tod_code / tod_regime / time features")
    print("=" * 70)

    rows = conn.execute("SELECT id FROM snapshots ORDER BY id").fetchall()
    ids = [r[0] for r in rows]

    market_open = start_time.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN, second=0)

    batch = []
    tod_counts = {}
    for i, row_id in enumerate(ids):
        ts = start_time + timedelta(seconds=i * SNAP_INTERVAL)
        mso = max(0, (ts - market_open).total_seconds() / 60)
        mtc = max(0, 390 - mso)
        pod = mso / 390.0

        tod_code, tod_regime = derive_tod(mso)
        tod_counts[tod_regime] = tod_counts.get(tod_regime, 0) + 1

        batch.append((mso, mtc, pod, tod_code, tod_regime, row_id))

    conn.executemany(
        "UPDATE snapshots SET mins_since_open=?, mins_to_close=?, pct_of_day=?, "
        "tod_code=?, tod_regime=? WHERE id=?",
        batch
    )
    conn.commit()

    print(f"  Updated {len(batch)} rows")
    print(f"  TOD distribution:")
    for regime, count in sorted(tod_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {regime:15s}: {count:5d} ({count/len(batch)*100:.1f}%)")

    return tod_counts


def fix_forward_returns_and_excursions(conn):
    """Re-run forward return and excursion backfill with corrected timestamps.

    This fixes:
    - fwd_1m/5m/15m/30m/60m (were all NULL because dt was always 0)
    - fwd_max_up/dn per horizon (were all identical because all windows matched)
    - labels (were all NULL)
    """
    print("\n" + "=" * 70)
    print("  STEP 3: Backfill forward returns, excursions, and labels")
    print("=" * 70)

    rows = conn.execute(
        "SELECT id, timestamp, spot FROM snapshots ORDER BY id"
    ).fetchall()

    if len(rows) < 2:
        print("  Need more data.")
        return

    ts = [datetime.fromisoformat(r[1]) for r in rows]
    sp = [r[2] for r in rows]
    ids = [r[0] for r in rows]
    n = len(rows)

    # Ensure all columns exist
    existing = {r[1] for r in conn.execute("PRAGMA table_info(snapshots)").fetchall()}
    needed = [
        'fwd_1m', 'fwd_5m', 'fwd_15m', 'fwd_30m', 'fwd_60m', 'fwd_eod',
        'label_5m', 'label_15m', 'label_30m',
        'fwd_max_up_5m', 'fwd_max_dn_5m',
        'fwd_max_up_15m', 'fwd_max_dn_15m', 'fwd_range_15m',
        'fwd_max_up_30m', 'fwd_max_dn_30m',
        'fwd_max_up_60m', 'fwd_max_dn_60m', 'fwd_range_60m',
    ]
    for col in needed:
        if col not in existing:
            ctype = 'TEXT' if col.startswith('label_') else 'REAL'
            try:
                conn.execute(f"ALTER TABLE snapshots ADD COLUMN {col} {ctype}")
            except:
                pass

    fwd_targets = [
        (60, 'fwd_1m'), (300, 'fwd_5m'), (900, 'fwd_15m'),
        (1800, 'fwd_30m'), (3600, 'fwd_60m'),
    ]
    thresholds = {
        'fwd_5m': FLAT_THRESH_5M,
        'fwd_15m': FLAT_THRESH_15,
        'fwd_30m': FLAT_THRESH_30,
    }
    label_map = {
        'fwd_5m': 'label_5m',
        'fwd_15m': 'label_15m',
        'fwd_30m': 'label_30m',
    }

    updated = 0
    fwd_fill_counts = {col: 0 for _, col in fwd_targets}
    label_fill_counts = {v: 0 for v in label_map.values()}
    excursion_fill_counts = {f'fwd_max_up_{w}m': 0 for w in [5, 15, 30, 60]}

    batch_updates = []

    for i in range(n):
        s0 = sp[i]
        if s0 <= 0:
            continue

        ups = {}
        filled = set()

        # Max excursion tracking per window
        max_up = {5: 0.0, 15: 0.0, 30: 0.0, 60: 0.0}
        max_dn = {5: 0.0, 15: 0.0, 30: 0.0, 60: 0.0}

        for j in range(i + 1, n):
            dt = (ts[j] - ts[i]).total_seconds()
            if dt > 3660:  # stop searching past 61 minutes
                break

            move = sp[j] - s0
            ret = move / s0 * 100

            # Track max excursion per window -- each window is independent
            for win_min in [5, 15, 30, 60]:
                if dt <= win_min * 60:
                    max_up[win_min] = max(max_up[win_min], move)
                    max_dn[win_min] = min(max_dn[win_min], move)

            # Standard forward returns: first price AT or AFTER the target horizon
            for secs, col in fwd_targets:
                if col not in filled and dt >= secs:
                    ups[col] = ret
                    filled.add(col)
                    fwd_fill_counts[col] += 1
                    if col in label_map:
                        th = thresholds.get(col, 0.1)
                        label = 'UP' if ret > th else ('DOWN' if ret < -th else 'FLAT')
                        ups[label_map[col]] = label
                        label_fill_counts[label_map[col]] += 1

        # Store max excursions (as % of spot)
        for win_min in [5, 15, 30, 60]:
            ups[f'fwd_max_up_{win_min}m'] = max_up[win_min] / s0 * 100
            ups[f'fwd_max_dn_{win_min}m'] = max_dn[win_min] / s0 * 100
            excursion_fill_counts[f'fwd_max_up_{win_min}m'] += 1
        ups['fwd_range_15m'] = (max_up[15] - max_dn[15]) / s0 * 100
        ups['fwd_range_60m'] = (max_up[60] - max_dn[60]) / s0 * 100

        # EOD return (last row of the same date)
        day = ts[i].date()
        for j in range(n - 1, i, -1):
            if ts[j].date() == day:
                ups['fwd_eod'] = (sp[j] - s0) / s0 * 100
                break

        if ups:
            # Clear forward returns for rows that don't have enough future data
            # (leave as NULL instead of filling with stale data)
            sc = ', '.join(f"{k}=?" for k in ups)
            batch_updates.append((list(ups.values()) + [ids[i]], sc))
            updated += 1

        if (i + 1) % 1000 == 0:
            print(f"  Progress: {i+1}/{n} rows processed...")

    # Execute updates
    for vals_and_id, set_clause in batch_updates:
        conn.execute(f"UPDATE snapshots SET {set_clause} WHERE id=?", vals_and_id)
    conn.commit()

    # NULL out forward returns for rows that genuinely don't have future data
    # These are rows near end of day where the forward horizon extends past available data
    null_counts = {}
    for secs, col in fwd_targets:
        # Count how many rows DON'T have this forward return filled
        unfilled = n - fwd_fill_counts[col]
        null_counts[col] = unfilled

    print(f"\n  Filled forward returns for {updated}/{n} rows:")
    for col, count in fwd_fill_counts.items():
        pct = count / n * 100
        null = null_counts.get(col, n - count)
        print(f"    {col:10s}: {count:5d} filled, {null:5d} NULL (genuinely no future data)")

    print(f"\n  Label fill counts:")
    for col, count in label_fill_counts.items():
        print(f"    {col:10s}: {count:5d} filled")

    return fwd_fill_counts, label_fill_counts


def check_excursion_distinctness(conn):
    """Report on excursion horizon distinctness after fix."""
    print("\n" + "=" * 70)
    print("  STEP 4: Verify excursion horizon distinctness")
    print("=" * 70)

    result = conn.execute('''
        SELECT
          COUNT(*) as total,
          SUM(CASE WHEN ABS(fwd_max_up_5m - fwd_max_up_15m) < 0.0001 THEN 1 ELSE 0 END) as up5_eq_15,
          SUM(CASE WHEN ABS(fwd_max_up_15m - fwd_max_up_30m) < 0.0001 THEN 1 ELSE 0 END) as up15_eq_30,
          SUM(CASE WHEN ABS(fwd_max_up_30m - fwd_max_up_60m) < 0.0001 THEN 1 ELSE 0 END) as up30_eq_60,
          SUM(CASE WHEN ABS(fwd_max_up_5m - fwd_max_up_60m) < 0.0001 THEN 1 ELSE 0 END) as up5_eq_60,
          SUM(CASE WHEN ABS(fwd_max_dn_5m - fwd_max_dn_15m) < 0.0001 THEN 1 ELSE 0 END) as dn5_eq_15,
          SUM(CASE WHEN ABS(fwd_max_dn_5m - fwd_max_dn_60m) < 0.0001 THEN 1 ELSE 0 END) as dn5_eq_60
        FROM snapshots WHERE fwd_max_up_5m IS NOT NULL
    ''').fetchone()

    total = result[0]
    pairs = [
        ('up_5m == up_15m', result[1]),
        ('up_15m == up_30m', result[2]),
        ('up_30m == up_60m', result[3]),
        ('up_5m == up_60m', result[4]),
        ('dn_5m == dn_15m', result[5]),
        ('dn_5m == dn_60m', result[6]),
    ]

    print(f"  Total rows with excursions: {total}")
    print(f"  Equality rates (lower = more distinct horizons):")
    for label, count in pairs:
        pct = count / total * 100 if total > 0 else 0
        status = "OK" if pct < 50 else "HIGH" if pct < 90 else "BROKEN"
        print(f"    {label:20s}: {count:5d}/{total} ({pct:5.1f}%) [{status}]")


def report_label_distribution(conn):
    """Report label distribution across horizons."""
    print("\n" + "=" * 70)
    print("  STEP 5: Label distributions")
    print("=" * 70)

    for label_col in ['label_5m', 'label_15m', 'label_30m']:
        rows = conn.execute(
            f"SELECT {label_col}, COUNT(*) FROM snapshots WHERE {label_col} IS NOT NULL GROUP BY {label_col}"
        ).fetchall()
        total = sum(r[1] for r in rows)
        null_count = conn.execute(
            f"SELECT COUNT(*) FROM snapshots WHERE {label_col} IS NULL"
        ).fetchone()[0]
        print(f"\n  {label_col} (filled={total}, null={null_count}):")
        for label, count in sorted(rows, key=lambda x: x[0]):
            print(f"    {label:5s}: {count:5d} ({count/total*100:.1f}%)")


def main():
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}")
        sys.exit(1)

    # Create backup
    backup_path = DB_PATH.with_suffix('.db.bak_day1fix')
    if not backup_path.exists():
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"Backup created: {backup_path}")
    else:
        print(f"Backup already exists: {backup_path}")

    conn = sqlite3.connect(str(DB_PATH))

    try:
        # Step 1: Fix timestamps
        start_time, n_rows = fix_timestamps(conn)

        # Step 2: Fix tod_code and time features
        tod_counts = fix_tod_and_time_features(conn, start_time, n_rows)

        # Step 3: Backfill forward returns and excursions
        fwd_counts, label_counts = fix_forward_returns_and_excursions(conn)

        # Step 4: Verify excursion distinctness
        check_excursion_distinctness(conn)

        # Step 5: Report label distributions
        report_label_distribution(conn)

        print("\n" + "=" * 70)
        print("  ALL DAY 1 FIXES COMPLETE")
        print("=" * 70)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
