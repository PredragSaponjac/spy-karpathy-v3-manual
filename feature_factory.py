"""
Karpathy Autoresearch — Feature Factory
Standard normalization, regime-relative transforms, time-of-day buckets,
quantile binning, and family organization.

All new columns are built in batch dicts and concat'd once per block
to avoid pandas fragmentation warnings.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

from config import (
    ALL_SPY_FAMILIES, QUANTILE_BINS, TOD_BUCKETS,
    ALL_OUTCOME_COLS,
)


# ─── Helpers (all point-in-time safe — no future data leakage) ────────

_EXPANDING_WINDOW = 390  # ~1 trading day at 5s intervals

def _safe_zscore(series: pd.Series) -> pd.Series:
    """Point-in-time z-score: expanding mean/std (only past data per row).

    Each row is normalized using only data available up to that row.
    Uses expanding window — never touches future rows.
    """
    exp_mean = series.expanding(min_periods=1).mean()
    exp_std = series.expanding(min_periods=1).std().replace(0, np.nan)
    return ((series - exp_mean) / exp_std).fillna(0.0)


def _safe_percentile_rank(series: pd.Series) -> pd.Series:
    """Point-in-time percentile rank [0, 1] using expanding window.

    Each row's rank is computed among all rows up to and including it.
    Never uses future data.
    """
    if len(series.dropna()) < 2:
        return pd.Series(0.5, index=series.index)
    return series.expanding(min_periods=1).rank(pct=True).fillna(0.5)


def _quantile_bin(series: pd.Series, n_bins: int = QUANTILE_BINS) -> pd.Series:
    """Point-in-time quantile binning using expanding quantile thresholds.

    Computes bin edges from data available up to each row (expanding),
    then assigns the current value to a bin. Never uses future data.
    """
    n = len(series)
    if n < n_bins:
        return pd.Series(0, index=series.index, dtype='int64')

    result = pd.Series(0, index=series.index, dtype='int64')
    # Compute expanding quantile thresholds for each bin edge
    edges = []
    for q in range(1, n_bins):
        edges.append(series.expanding(min_periods=max(n_bins, 10)).quantile(q / n_bins))

    # Assign bins row-by-row using the expanding thresholds
    for i, edge_series in enumerate(edges):
        result = result + (series > edge_series).astype(int)

    return result.clip(0, n_bins - 1)


# ─── Normalizers (batch-concat) ──────────────────────────────────────────

def normalize_zscore(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Add z-score columns for given features. Built in one concat."""
    present = [c for c in cols if c in df.columns and df[c].dtype != 'object']
    if not present:
        return df
    new = {f'{col}_z': _safe_zscore(df[col]) for col in present}
    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


def normalize_percentile(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Add percentile rank columns. Built in one concat."""
    present = [c for c in cols if c in df.columns and df[c].dtype != 'object']
    if not present:
        return df
    new = {f'{col}_pct': _safe_percentile_rank(df[col]) for col in present}
    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


def normalize_quantile_bins(df: pd.DataFrame, cols: List[str],
                            n_bins: int = QUANTILE_BINS) -> pd.DataFrame:
    """Add quantile bin columns. Built in one concat."""
    present = [c for c in cols if c in df.columns and df[c].dtype != 'object']
    if not present:
        return df
    new = {f'{col}_q{n_bins}': _quantile_bin(df[col], n_bins) for col in present}
    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


# ─── Regime-Relative Transforms ─────────────────────────────────────────

def regime_relative_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute features relative to the current regime (point-in-time safe).

    Uses expanding mean/std within each regime group so that each row
    is only compared to prior rows in the same regime — no future leakage.
    """
    if 'regime' not in df.columns:
        return df

    regime_cols = [
        'gex_total', 'nope', 'atm_avg_iv', 'skew_25d', 'net_prem',
        'pin_score', 'efficiency_ratio', 'structural_gate',
    ]
    present = [c for c in regime_cols if c in df.columns]
    if not present:
        return df

    new = {}
    for col in present:
        # Point-in-time: expanding mean/std within each regime group
        # Each row only sees prior rows in the same regime
        grouped = df.groupby('regime')[col]
        regime_mean = grouped.transform(lambda x: x.expanding(min_periods=1).mean())
        regime_std = grouped.transform(lambda x: x.expanding(min_periods=1).std()).replace(0, np.nan)
        new[f'{col}_regime_z'] = ((df[col] - regime_mean) / regime_std).fillna(0)

    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


# ─── Time-of-Day Features ───────────────────────────────────────────────

def add_tod_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add time-of-day bucket indicators and normalized time."""
    if 'mins_since_open' not in df.columns:
        return df

    mso = df['mins_since_open']
    new = {}

    for bucket_name, (lo, hi) in TOD_BUCKETS.items():
        new[f'tod_{bucket_name}'] = ((mso >= lo) & (mso < hi)).astype(int)

    new['tod_normalized'] = (mso / 390.0).clip(0, 1)
    mid = 195.0
    new['tod_ushaped'] = ((mso - mid) / mid) ** 2

    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


# ─── QQQ Feature Extraction ─────────────────────────────────────────────

def extract_qqq_features(df: pd.DataFrame) -> List[str]:
    """Return list of QQQ feature columns present in df.

    FIX: Also exclude any qqq_fwd_* or qqq_label_* columns to prevent
    forward label leakage if QQQ outcome columns ever exist in the DB.
    ALL_OUTCOME_COLS only contains SPY outcomes, so qqq_fwd_15m would
    bypass the old filter and become a feature with perfect lookahead.
    """
    excluded = set(ALL_OUTCOME_COLS)
    return [c for c in df.columns
            if c.startswith('qqq_')
            and c not in excluded
            and not c.startswith('qqq_fwd_')
            and not c.startswith('qqq_label_')]


def extract_div_features(df: pd.DataFrame) -> List[str]:
    """Return list of divergence feature columns present in df."""
    return [c for c in df.columns if c.startswith('div_') and c not in ALL_OUTCOME_COLS]


# ─── Feature Organization ───────────────────────────────────────────────

def get_feature_families(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Return dict of family_name -> list of actual columns present."""
    families = {}

    for name, configured_cols in ALL_SPY_FAMILIES.items():
        present = [c for c in configured_cols if c in df.columns]
        if present:
            families[f'spy_{name}'] = present

    qqq = extract_qqq_features(df)
    if qqq:
        families['qqq'] = qqq

    div = extract_div_features(df)
    if div:
        families['divergence'] = div

    derived = [c for c in df.columns
               if c.endswith('_z') or c.endswith('_pct') or '_q5' in c
               or c.endswith('_regime_z') or c.startswith('tod_')]
    if derived:
        families['derived'] = derived

    return families


def get_all_feature_cols(df: pd.DataFrame) -> List[str]:
    """Return flat list of all usable feature columns (excludes outcomes, meta)."""
    meta = {'id', 'timestamp', 'date', 'day_id', 'dte', 'is_dupe', 'dupe_streak',
            '_snapshot_count'}
    exclude = set(ALL_OUTCOME_COLS) | meta
    exclude |= {c for c in df.columns if c.startswith('mes_')}

    return [c for c in df.columns
            if c not in exclude and df[c].dtype != 'object']


# ─── Main Pipeline ───────────────────────────────────────────────────────

def build_features(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Run full feature engineering pipeline."""
    if verbose:
        print("Building features...")

    # Key columns for z-score normalization
    key_zscore = [
        'gex_total', 'gex_to_volume', 'dex', 'vex', 'cex', 'nope', 'net_prem', 'net_delta_flow',
        'atm_avg_iv', 'skew_25d', 'iv_slope', 'iv_curvature',
        'pin_score', 'theta_per_min', 'atm_straddle',
        'efficiency_ratio', 'structural_gate', 'persistence',
        'charm_meltup_score', 'vanna_crush_score',
        'tick', 'nyse_add', 'vix', 'trin', 'breadth_composite',
        'spot_velocity', 'spot_accel',
        'real_theta_atm', 'total_real_theta', 'extrinsic_atm',
    ]
    key_zscore += [c for c in df.columns if c.startswith('qqq_') and df[c].dtype != 'object']
    key_zscore += [c for c in df.columns if c.startswith('div_') and df[c].dtype != 'object']

    df = normalize_zscore(df, key_zscore)

    pct_cols = [
        'gex_total', 'nope', 'net_prem', 'pcr_vol', 'pcr_oi',
        'atm_avg_iv', 'skew_25d', 'pin_score',
        'vix', 'breadth_composite', 'sector_rotation',
    ]
    df = normalize_percentile(df, pct_cols)

    bin_cols = [
        'gex_total', 'nope', 'atm_avg_iv', 'skew_25d', 'iv_slope',
        'pin_score', 'efficiency_ratio', 'structural_gate',
        'vix', 'tick', 'breadth_composite',
        'spot_chg_pct', 'spot_velocity',
    ]
    df = normalize_quantile_bins(df, bin_cols)

    df = regime_relative_features(df)
    df = add_tod_features(df)

    if verbose:
        families = get_feature_families(df)
        total_features = sum(len(v) for v in families.values())
        print(f"  Feature families: {len(families)}")
        for name, cols in families.items():
            print(f"    {name:20s}: {len(cols):4d} features")
        print(f"  Total features: {total_features}")

    return df


if __name__ == "__main__":
    from prepare_data import build_modeling_frame
    df = build_modeling_frame(verbose=True)
    df = build_features(df, verbose=True)
    print(f"\nFinal frame: {df.shape[0]} rows x {df.shape[1]} cols")
