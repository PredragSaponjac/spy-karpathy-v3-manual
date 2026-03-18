"""
Karpathy Autoresearch — Sequence / Temporal State Features
Multi-snapshot features: acceleration, compression->expansion transitions,
divergence chains, signal improvement/deterioration, QQQ lead-confirm patterns.

All percentile/rank features are POINT-IN-TIME SAFE:
  - Uses expanding rank (only past data) instead of full-sample rank
  - Each row's percentile is computed using only data available up to that row

All new columns are built in batch dicts and concat'd once per block
to avoid pandas fragmentation warnings.
"""
import numpy as np
import pandas as pd
from typing import List


def _expanding_pctile(series: pd.Series) -> pd.Series:
    """Point-in-time percentile rank using expanding window.

    Each row's percentile is its rank among all rows up to and including
    that row — never uses future data. Vectorized via expanding().rank().
    """
    # expanding().rank() is not directly available, so we use a
    # vectorized approach: for each row i, rank(i) / count(i)
    expanding_rank = series.expanding(min_periods=1).apply(
        lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False
    )
    return expanding_rank


def _fast_expanding_pctile(series: pd.Series) -> pd.Series:
    """Point-in-time percentile rank using expanding window.

    FIX: Removed the n>10000 branch that switched from expanding to rolling,
    creating a semantic discontinuity at row 10001. Now always uses
    expanding rank — consistent behavior regardless of dataset size.

    Uses pandas expanding().rank(pct=True) which is O(n) via Cython.
    """
    n = len(series)
    if n == 0:
        return series

    # Always use expanding rank — same semantics at any dataset size.
    # pandas expanding().rank() is implemented in Cython and handles
    # large series efficiently without needing a rolling approximation.
    return series.expanding(min_periods=1).rank(pct=True).fillna(0.5)


# ─── Rolling Acceleration / Momentum ─────────────────────────────────────

def _rolling_acceleration(df: pd.DataFrame, windows: List[int] = None) -> pd.DataFrame:
    """Compute velocity and acceleration over trailing snapshots."""
    if windows is None:
        windows = [6, 12, 24, 60]  # ~30s, 1m, 2m, 5m at 5s intervals

    accel_targets = [
        ('spot', 'price'),
        ('gex_total', 'gex'),
        ('nope', 'nope'),
        ('atm_avg_iv', 'iv'),
        ('skew_25d', 'skew'),
        ('net_prem', 'prem'),
        ('pin_score', 'pin'),
        ('vix', 'vix'),
        ('tick', 'tick_int'),
        ('breadth_composite', 'breadth'),
    ]

    new = {}
    for col, short_name in accel_targets:
        if col not in df.columns:
            continue
        series = df[col].astype(float)

        for w in windows:
            vel = series.diff(w)
            new[f'seq_{short_name}_vel_{w}'] = vel
            new[f'seq_{short_name}_accel_{w}'] = vel.diff(w)

    if new:
        return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
    return df


# ─── Compression → Expansion Detection ──────────────────────────────────

def _compression_expansion(df: pd.DataFrame) -> pd.DataFrame:
    """Detect price/IV compression followed by expansion breakout.

    All percentile ranks use point-in-time expanding rank (no future leakage).
    """
    new = {}

    if 'spot' in df.columns:
        spot = df['spot'].astype(float)
        for w in [30, 60, 120]:
            rolling_range = spot.rolling(w, min_periods=6).max() - spot.rolling(w, min_periods=6).min()
            # Point-in-time percentile rank (expanding, not full-sample)
            range_pctile = _fast_expanding_pctile(rolling_range)
            new[f'seq_price_compression_{w}'] = (range_pctile < 0.20).astype(int)
            new[f'seq_price_expansion_{w}'] = (
                (range_pctile > 0.80) &
                (range_pctile.shift(w) < 0.30)
            ).astype(int)

    if 'atm_avg_iv' in df.columns:
        iv = df['atm_avg_iv'].astype(float)
        iv_range = iv.rolling(60, min_periods=6).max() - iv.rolling(60, min_periods=6).min()
        # Point-in-time percentile rank
        iv_pctile = _fast_expanding_pctile(iv_range)
        new['seq_iv_compression'] = (iv_pctile < 0.20).astype(int)
        new['seq_iv_expansion'] = (
            (iv_pctile > 0.80) & (iv_pctile.shift(60) < 0.30)
        ).astype(int)

    if new:
        return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
    return df


# ─── Divergence Chain States ────────────────────────────────────────────

def _divergence_chains(df: pd.DataFrame) -> pd.DataFrame:
    """Track persistent divergence streaks and reversals."""
    div_cols = ['div_gex', 'div_nope', 'div_atm_iv', 'div_net_prem', 'div_skew_25d']
    present = [c for c in div_cols if c in df.columns]

    new = {}
    for col in present:
        series = df[col].fillna(0)
        sign = np.sign(series)

        # Streak length: vectorized using groupby on sign changes
        sign_changed = (sign != sign.shift(1)).cumsum()
        streak = sign.groupby(sign_changed).cumcount() + 1
        streak = streak.where(sign != 0, 0)

        new[f'{col}_streak'] = streak
        new[f'{col}_streak_long'] = (streak > 24).astype(int)

        # True reversal: +1 → -1 or -1 → +1 across 6 snapshots.
        # Excludes moves to/from neutral (0), which are not real flips.
        sign_prev = sign.shift(6)
        true_reversal = ((sign == 1) & (sign_prev == -1)) | ((sign == -1) & (sign_prev == 1))
        new[f'{col}_reversal'] = true_reversal.astype(int)

    if new:
        df = pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)

    # Composite divergence persistence
    streak_cols = [f'{c}_streak_long' for c in present if f'{c}_streak_long' in df.columns]
    if streak_cols:
        persistence = df[streak_cols].sum(axis=1)
        df = pd.concat([df, pd.DataFrame({'seq_div_persistence': persistence}, index=df.index)], axis=1)

    return df


# ─── Signal Trend Improvement / Deterioration ────────────────────────────

def _signal_trend_changes(df: pd.DataFrame) -> pd.DataFrame:
    """Track whether key signals are improving or deteriorating."""
    signal_cols = [c for c in df.columns if c.startswith('sig_') and df[c].dtype != 'object']

    new = {}
    for col in signal_cols:
        series = df[col].fillna(0)
        new[f'{col}_improving'] = (series.diff(12) > 0).astype(int)
        new[f'{col}_deteriorating'] = (series.diff(12) < 0).astype(int)

    # Regime transition tracking
    if 'regime' in df.columns:
        regime_changed = (df['regime'] != df['regime'].shift(1)).astype(int)
        new['seq_regime_changed'] = regime_changed

        # Vectorized stable count: cumcount within each regime run
        regime_runs = regime_changed.cumsum()
        stable_count = df.groupby(regime_runs).cumcount()
        new['seq_regime_stable_count'] = stable_count

    if new:
        return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
    return df


# ─── QQQ Lead → SPY Confirm Pattern ─────────────────────────────────────

def _qqq_lead_confirm(df: pd.DataFrame) -> pd.DataFrame:
    """Detect QQQ-leads-SPY-confirms pattern at multiple lags.

    All percentile ranks use point-in-time expanding rank (no future leakage).
    """
    if 'spot_chg_pct' not in df.columns:
        return df

    spy = df['spot_chg_pct'].fillna(0)
    qqq = df.get('qqq_spot_chg_pct', pd.Series(0, index=df.index)).fillna(0)

    new = {}
    for threshold in [0.05, 0.10]:
        qqq_moved = qqq.abs() > threshold
        spy_lagging = spy.abs() < threshold * 0.5
        t_str = int(threshold * 100)

        new[f'seq_qqq_leads_spy_{t_str}bp'] = (qqq_moved & spy_lagging).astype(int)
        new[f'seq_qqq_lead_dir_{t_str}bp'] = np.where(
            qqq_moved & spy_lagging, np.sign(qqq), 0
        )

    # QQQ breakout, SPY consolidating
    if 'qqq_spot' in df.columns and 'spot' in df.columns:
        qqq_price = df['qqq_spot'].astype(float)
        spy_price = df['spot'].astype(float)

        qqq_range = qqq_price.rolling(60, min_periods=6).max() - qqq_price.rolling(60, min_periods=6).min()
        spy_range = spy_price.rolling(60, min_periods=6).max() - spy_price.rolling(60, min_periods=6).min()

        # Point-in-time percentile rank (expanding, not full-sample)
        qqq_pctile = _fast_expanding_pctile(qqq_range)
        spy_pctile = _fast_expanding_pctile(spy_range)

        new['seq_qqq_breakout_spy_tight'] = (
            (qqq_pctile > 0.75) & (spy_pctile < 0.35)
        ).astype(int)

    if new:
        return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
    return df


# ─── Momentum Regime Transitions ─────────────────────────────────────────

def _momentum_transitions(df: pd.DataFrame) -> pd.DataFrame:
    """Classify momentum state and detect transitions.

    Percentile rank uses point-in-time expanding rank (no future leakage).
    """
    if 'spot_velocity' not in df.columns:
        return df

    vel = df['spot_velocity'].fillna(0)

    new = {}
    # Point-in-time percentile rank (expanding, not full-sample)
    vel_pctile = _fast_expanding_pctile(vel)
    conditions = [vel_pctile > 0.80, vel_pctile > 0.60, vel_pctile < 0.20, vel_pctile < 0.40]
    choices = ['strong_up', 'mild_up', 'strong_down', 'mild_down']
    new['seq_momentum_state'] = np.select(conditions, choices, default='neutral')

    vel_sign = np.sign(vel)
    vel_sign_prev = vel_sign.shift(12)
    new['seq_momentum_flip'] = (vel_sign != vel_sign_prev).astype(int)
    new['seq_momentum_flip_dir'] = np.where(
        new['seq_momentum_flip'] == 1, vel_sign, 0
    )

    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


# ─── Main Pipeline ───────────────────────────────────────────────────────

def build_sequence_features(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Run full sequence/temporal feature pipeline."""
    if verbose:
        print("Building sequence/temporal features...")

    n_before = len(df.columns)

    df = _rolling_acceleration(df)
    df = _compression_expansion(df)
    df = _divergence_chains(df)
    df = _signal_trend_changes(df)
    df = _qqq_lead_confirm(df)
    df = _momentum_transitions(df)

    n_after = len(df.columns)
    if verbose:
        print(f"  Added {n_after - n_before} sequence features")

    return df


if __name__ == "__main__":
    from prepare_data import build_modeling_frame
    from feature_factory import build_features
    from divergence_features import build_divergence_features

    df = build_modeling_frame(verbose=True)
    df = build_features(df, verbose=True)
    df = build_divergence_features(df, verbose=True)
    df = build_sequence_features(df, verbose=True)

    seq_cols = [c for c in df.columns if c.startswith('seq_')]
    print(f"\nSequence columns ({len(seq_cols)}):")
    for c in sorted(seq_cols)[:30]:
        print(f"  {c}")
    if len(seq_cols) > 30:
        print(f"  ... +{len(seq_cols)-30} more")
