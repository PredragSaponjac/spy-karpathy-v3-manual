"""
Karpathy Autoresearch — Walk-Forward Evaluator
Day-based walk-forward evaluation, utility scoring, stability/overlap/support
penalties. Converts raw forward returns to /MES dollar expectancies.

SKIP rules use a separate skip-utility function (not -abs(return)).
Day concentration uses weighted daily pnl (mean_return * support per day).

NOTE: Mutable knobs (MIN_SUPPORT, NEIGHBOR_BAND_PCT, SKIP_AGGRESSIVENESS,
INTERMARKET_WEIGHT, MOVE_SIZE_PREFERENCE, concentration limits) are read
from the config MODULE at call time so that HypothesisOverride patches
propagate correctly.  Do NOT bind them at import time.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ── Import config MODULE for runtime-mutable knobs ────────────────────
import config as _cfg

# Functions (immutable) — safe to bind once
spy_pct_to_mes_points  = _cfg.spy_pct_to_mes_points
spy_pct_to_mes_dollars = _cfg.spy_pct_to_mes_dollars

# Constants that are NEVER hypothesis-mutable — safe to bind once
MES_POINT_VALUE      = _cfg.MES_POINT_VALUE
ROUND_TRIP_COST_USD  = _cfg.ROUND_TRIP_COST_USD
SLIPPAGE_USD         = _cfg.SLIPPAGE_USD
WF_MIN_TRAIN_DAYS    = _cfg.WF_MIN_TRAIN_DAYS
WF_VAL_DAYS          = _cfg.WF_VAL_DAYS
WF_HOLDOUT_DAYS      = _cfg.WF_HOLDOUT_DAYS
WF_EXPANDING         = _cfg.WF_EXPANDING
W_NET_EXPECTANCY     = _cfg.W_NET_EXPECTANCY
W_MFE                = _cfg.W_MFE
W_DIRECTION          = _cfg.W_DIRECTION
W_SKIP_ACCURACY      = _cfg.W_SKIP_ACCURACY
W_STABILITY          = _cfg.W_STABILITY
P_DRAWDOWN           = _cfg.P_DRAWDOWN
P_COMPLEXITY         = _cfg.P_COMPLEXITY
P_LOW_SUPPORT        = _cfg.P_LOW_SUPPORT
P_OVERLAP            = _cfg.P_OVERLAP
MFE_WINSORIZE_PCTILE = _cfg.MFE_WINSORIZE_PCTILE
TOD_BUCKETS          = _cfg.TOD_BUCKETS

# ── MUTABLE at runtime — always read through _cfg.* ──────────────────
# _cfg.MIN_SUPPORT
# _cfg.MIN_DISTINCT_DAYS
# _cfg.NEIGHBOR_BAND_PCT
# _cfg.MAX_SINGLE_DAY_SCORE_PCT
# _cfg.MAX_SINGLE_REGIME_SCORE_PCT
# _cfg.MIN_TOD_BUCKETS
# _cfg.SKIP_AGGRESSIVENESS       (Karpathy shell knob)
# _cfg.INTERMARKET_WEIGHT        (Karpathy shell knob)
# _cfg.MOVE_SIZE_PREFERENCE      (Karpathy shell knob)


# ─── Data Structures ────────────────────────────────────────────────────

@dataclass
class Predicate:
    """Single condition in a rule."""
    feature: str
    op: str          # 'lt', 'gt', 'between', 'eq', 'in_quantile'
    value: object    # float, int, or str (for state rules like 'strong_pos')
    value_hi: Optional[float] = None  # for 'between'

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        if self.feature not in df.columns:
            return pd.Series(False, index=df.index)
        col = df[self.feature]
        if self.op == 'lt':
            return col < self.value
        elif self.op == 'gt':
            return col > self.value
        elif self.op == 'between':
            return (col >= self.value) & (col <= self.value_hi)
        elif self.op == 'eq':
            return col == self.value
        elif self.op == 'in_quantile':
            return col == self.value
        return pd.Series(False, index=df.index)

    def to_english(self) -> str:
        # FIX: Handle string values (state rules) without .4g formatting
        def _fmt(v):
            return f"{v:.4g}" if isinstance(v, (int, float)) else str(v)
        if self.op == 'lt':
            return f"{self.feature} < {_fmt(self.value)}"
        elif self.op == 'gt':
            return f"{self.feature} > {_fmt(self.value)}"
        elif self.op == 'between':
            return f"{_fmt(self.value)} <= {self.feature} <= {_fmt(self.value_hi)}"
        elif self.op == 'eq':
            return f"{self.feature} = {_fmt(self.value)}"
        elif self.op == 'in_quantile':
            return f"{self.feature} in Q{int(self.value)}"
        return f"{self.feature} {self.op} {self.value}"

    def to_dict(self) -> dict:
        d = {'feature': self.feature, 'op': self.op, 'value': self.value}
        if self.value_hi is not None:
            d['value_hi'] = self.value_hi
        return d


@dataclass
class CandidateRule:
    """A candidate pattern with predicates and direction."""
    name: str
    direction: str               # 'LONG', 'SHORT', 'SKIP'
    predicates: List[Predicate]
    horizon_min: int = 15        # primary horizon in minutes
    source_family: str = ''      # which feature family generated this

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        """Return boolean mask of rows matching all predicates."""
        mask = pd.Series(True, index=df.index)
        for pred in self.predicates:
            mask = mask & pred.evaluate(df)
        return mask

    @property
    def complexity(self) -> int:
        return len(self.predicates)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'direction': self.direction,
            'predicates': [p.to_dict() for p in self.predicates],
            'horizon_min': self.horizon_min,
            'source_family': self.source_family,
            'complexity': self.complexity,
        }


@dataclass
class RuleScore:
    """Evaluation results for a candidate rule."""
    rule: CandidateRule
    support: int = 0
    distinct_days: int = 0

    # Forward return stats (SPY %)
    mean_fwd_return: float = 0.0
    median_fwd_return: float = 0.0
    win_rate: float = 0.0

    # Excursion stats (SPY %)
    median_mfe: float = 0.0       # median favorable excursion
    median_mae: float = 0.0       # median adverse excursion
    max_mae: float = 0.0

    # /MES dollar conversion
    mes_gross_expectancy: float = 0.0
    mes_net_expectancy: float = 0.0
    mes_median_mfe_pts: float = 0.0
    mes_median_mae_pts: float = 0.0

    # Skip-specific metrics
    skip_expectancy_reduction: float = 0.0  # how much worse expectancy is vs baseline
    skip_chop_increase: float = 0.0         # how much choppier vs baseline
    skip_bad_entry_rate: float = 0.0        # fraction of entries that would have been bad

    # Walk-forward results
    wf_folds: int = 0
    wf_profitable_folds: int = 0
    wf_stability: float = 0.0     # fraction of profitable folds
    wf_mean_return: float = 0.0   # mean OOS return across folds
    wf_mean_win_rate: float = 0.0 # mean OOS win rate across folds

    # Composite score
    composite_score: float = 0.0
    penalties: Dict[str, float] = field(default_factory=dict)

    # Neighbor robustness
    neighbor_robust: bool = True

    # Concentration metrics (GPT hardening)
    max_day_contribution_pct: float = 0.0   # worst single-day score share
    max_regime_contribution_pct: float = 0.0 # worst single-regime score share
    tod_bucket_count: int = 0               # how many TOD buckets rule fires in
    day_concentration_ok: bool = True
    regime_concentration_ok: bool = True
    tod_coverage_ok: bool = True

    def to_dict(self) -> dict:
        d = {
            **self.rule.to_dict(),
            'support': self.support,
            'distinct_days': self.distinct_days,
            'mean_fwd_return_pct': round(self.mean_fwd_return, 4),
            'median_fwd_return_pct': round(self.median_fwd_return, 4),
            'win_rate': round(self.win_rate, 4),
            'median_mfe_pct': round(self.median_mfe, 4),
            'median_mae_pct': round(self.median_mae, 4),
            'mes_gross_expectancy_usd': round(self.mes_gross_expectancy, 2),
            'mes_net_expectancy_usd': round(self.mes_net_expectancy, 2),
            'mes_median_mfe_pts': round(self.mes_median_mfe_pts, 2),
            'mes_median_mae_pts': round(self.mes_median_mae_pts, 2),
            'wf_folds': self.wf_folds,
            'wf_profitable_folds': self.wf_profitable_folds,
            'wf_stability': round(self.wf_stability, 4),
            'wf_mean_return': round(self.wf_mean_return, 4),
            'wf_mean_win_rate': round(self.wf_mean_win_rate, 4),
            'composite_score': round(self.composite_score, 4),
            'neighbor_robust': self.neighbor_robust,
            'day_concentration_ok': self.day_concentration_ok,
            'regime_concentration_ok': self.regime_concentration_ok,
            'tod_bucket_count': self.tod_bucket_count,
            'max_day_contribution_pct': round(self.max_day_contribution_pct, 4),
            'max_regime_contribution_pct': round(self.max_regime_contribution_pct, 4),
            'penalties': {k: round(v, 4) for k, v in self.penalties.items()},
        }
        # Skip-specific fields
        if self.rule.direction == 'SKIP':
            d['skip_expectancy_reduction'] = round(self.skip_expectancy_reduction, 4)
            d['skip_chop_increase'] = round(self.skip_chop_increase, 4)
            d['skip_bad_entry_rate'] = round(self.skip_bad_entry_rate, 4)
        return d


# ─── Walk-Forward Splits ────────────────────────────────────────────────

def make_wf_splits(df: pd.DataFrame) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """Create walk-forward train/val splits by trading day."""
    days = sorted(df['day_id'].unique())
    n_days = len(days)

    # FIX: Never return [(df, df)] — that's fake OOS (train == val).
    # If insufficient data, return empty list so wf_folds=0 and composite
    # relies on the maturity gate to block promotion.
    if n_days < WF_MIN_TRAIN_DAYS + WF_VAL_DAYS:
        return []

    holdout_start = n_days - WF_HOLDOUT_DAYS
    available_days = days[:holdout_start]

    splits = []
    for i in range(WF_MIN_TRAIN_DAYS, len(available_days)):
        if WF_EXPANDING:
            train_days = available_days[:i]
        else:
            train_days = available_days[max(0, i - WF_MIN_TRAIN_DAYS):i]

        val_end = min(i + WF_VAL_DAYS, len(available_days))
        val_days = available_days[i:val_end]

        if not val_days:
            continue

        train_mask = df['day_id'].isin(train_days)
        val_mask = df['day_id'].isin(val_days)

        if train_mask.sum() > 0 and val_mask.sum() > 0:
            splits.append((df[train_mask], df[val_mask]))

    return splits  # empty if no valid splits — never fake OOS


def get_holdout(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Return holdout set (last N days)."""
    days = sorted(df['day_id'].unique())
    if len(days) <= WF_HOLDOUT_DAYS:
        return None
    holdout_days = days[-WF_HOLDOUT_DAYS:]
    return df[df['day_id'].isin(holdout_days)]


# ─── Core Scoring ────────────────────────────────────────────────────────

def _get_fwd_col(horizon_min: int) -> str:
    return f'fwd_{horizon_min}m'


def _get_mfe_col(horizon_min: int, direction: str) -> str:
    if direction == 'LONG':
        return f'fwd_max_up_{horizon_min}m'
    else:
        return f'fwd_max_dn_{horizon_min}m'


def _get_mae_col(horizon_min: int, direction: str) -> str:
    if direction == 'LONG':
        return f'fwd_max_dn_{horizon_min}m'
    else:
        return f'fwd_max_up_{horizon_min}m'


def _compute_baseline(df: pd.DataFrame, horizon_min: int) -> Dict:
    """Compute baseline stats for the full dataset at a given horizon."""
    fwd_col = _get_fwd_col(horizon_min)
    if fwd_col not in df.columns:
        return {'mean_abs_return': 0.0, 'mean_efficiency': 0.5, 'mean_return': 0.0}

    fwd = df[fwd_col].dropna()
    if len(fwd) == 0:
        return {'mean_abs_return': 0.0, 'mean_efficiency': 0.5, 'mean_return': 0.0}

    eff = df['efficiency_ratio'].dropna() if 'efficiency_ratio' in df.columns else pd.Series(dtype=float)

    return {
        'mean_abs_return': float(fwd.abs().mean()),
        'mean_efficiency': float(eff.mean()) if len(eff) > 0 else 0.5,
        'mean_return': float(fwd.mean()),
    }


_baseline_cache: Dict = {}


def clear_baseline_cache():
    """Clear baseline cache between champion/challenger runs."""
    _baseline_cache.clear()


def _get_baseline(df: pd.DataFrame, horizon_min: int) -> Dict:
    """Cache baseline by a stable fingerprint using index bounds.

    FIX: Old key (nrows, ncols, horizon) collided across WF folds with
    same dimensions. New key uses first/last index values + row count
    to distinguish different data slices.
    """
    first_idx = int(df.index[0]) if len(df) > 0 else 0
    last_idx = int(df.index[-1]) if len(df) > 0 else 0
    key = (len(df), first_idx, last_idx, horizon_min)
    if key not in _baseline_cache:
        _baseline_cache[key] = _compute_baseline(df, horizon_min)
    return _baseline_cache[key]


def score_rule_on_slice(rule: CandidateRule, df: pd.DataFrame) -> Dict:
    """Score a LONG/SHORT rule on a data slice."""
    mask = rule.evaluate(df)
    matched = df[mask]

    fwd_col = _get_fwd_col(rule.horizon_min)
    if fwd_col not in df.columns:
        return {'support': 0}

    matched_fwd = matched[fwd_col].dropna()
    if len(matched_fwd) == 0:
        return {'support': 0}

    if rule.direction == 'SHORT':
        returns = -matched_fwd
    else:
        returns = matched_fwd

    mfe_col = _get_mfe_col(rule.horizon_min, rule.direction)
    mae_col = _get_mae_col(rule.horizon_min, rule.direction)

    mfe = matched[mfe_col].dropna().abs() if mfe_col in matched.columns else pd.Series(dtype=float)
    mae = matched[mae_col].dropna().abs() if mae_col in matched.columns else pd.Series(dtype=float)

    if len(mfe) > 5:
        clip_val = float(mfe.quantile(MFE_WINSORIZE_PCTILE))
        mfe = mfe.clip(upper=clip_val)

    per_day_weighted = {}
    if 'day_id' in matched.columns:
        for day_id, grp in matched.groupby('day_id'):
            day_fwd = grp[fwd_col].dropna()
            if len(day_fwd) > 0:
                day_mean = float((-day_fwd).mean()) if rule.direction == 'SHORT' else float(day_fwd.mean())
                per_day_weighted[day_id] = day_mean * len(day_fwd)

    per_regime_weighted = {}
    if 'regime' in matched.columns:
        for regime, grp in matched.groupby('regime'):
            reg_fwd = grp[fwd_col].dropna()
            if len(reg_fwd) > 0:
                reg_mean = float((-reg_fwd).mean()) if rule.direction == 'SHORT' else float(reg_fwd.mean())
                per_regime_weighted[regime] = reg_mean * len(reg_fwd)

    tod_buckets_hit = set()
    if 'mins_since_open' in matched.columns:
        mso = matched['mins_since_open']
        for bname, (lo, hi) in TOD_BUCKETS.items():
            if ((mso >= lo) & (mso < hi)).any():
                tod_buckets_hit.add(bname)

    return {
        'support': len(matched_fwd),
        'distinct_days': matched['day_id'].nunique() if 'day_id' in matched.columns else 1,
        'mean_return': float(returns.mean()),
        'median_return': float(returns.median()),
        'win_rate': float((returns > 0).mean()),
        'median_mfe': float(mfe.median()) if len(mfe) > 0 else 0.0,
        'median_mae': float(mae.median()) if len(mae) > 0 else 0.0,
        'max_mae': float(mae.max()) if len(mae) > 0 else 0.0,
        'per_day_weighted': per_day_weighted,
        'per_regime_weighted': per_regime_weighted,
        'tod_buckets_hit': len(tod_buckets_hit),
    }


def score_skip_rule_on_slice(rule: CandidateRule, df: pd.DataFrame) -> Dict:
    """Score a SKIP rule by comparing matched subset to full-dataset baseline."""
    mask = rule.evaluate(df)
    matched = df[mask]

    fwd_col = _get_fwd_col(rule.horizon_min)
    if fwd_col not in df.columns:
        return {'support': 0}

    matched_fwd = matched[fwd_col].dropna()
    if len(matched_fwd) == 0:
        return {'support': 0}

    baseline = _get_baseline(df, rule.horizon_min)

    matched_abs_mean = float(matched_fwd.abs().mean())
    baseline_abs_mean = baseline['mean_abs_return']
    if baseline_abs_mean > 0:
        expectancy_reduction = 1.0 - (matched_abs_mean / baseline_abs_mean)
    else:
        expectancy_reduction = 0.0

    chop_increase = 0.0
    if 'efficiency_ratio' in matched.columns:
        matched_eff = matched['efficiency_ratio'].dropna()
        if len(matched_eff) > 0:
            baseline_eff = baseline['mean_efficiency']
            if baseline_eff > 0:
                chop_increase = 1.0 - (float(matched_eff.mean()) / baseline_eff)

    bad_entry_rate = float((matched_fwd.abs() < 0.05).mean())

    per_day_weighted = {}
    if 'day_id' in matched.columns:
        for day_id, grp in matched.groupby('day_id'):
            day_fwd = grp[fwd_col].dropna()
            if len(day_fwd) > 0:
                per_day_weighted[day_id] = float(day_fwd.abs().mean()) * len(day_fwd)

    per_regime_weighted = {}
    if 'regime' in matched.columns:
        for regime, grp in matched.groupby('regime'):
            reg_fwd = grp[fwd_col].dropna()
            if len(reg_fwd) > 0:
                per_regime_weighted[regime] = float(reg_fwd.abs().mean()) * len(reg_fwd)

    tod_buckets_hit = set()
    if 'mins_since_open' in matched.columns:
        mso = matched['mins_since_open']
        for bname, (lo, hi) in TOD_BUCKETS.items():
            if ((mso >= lo) & (mso < hi)).any():
                tod_buckets_hit.add(bname)

    return {
        'support': len(matched_fwd),
        'distinct_days': matched['day_id'].nunique() if 'day_id' in matched.columns else 1,
        'expectancy_reduction': expectancy_reduction,
        'chop_increase': chop_increase,
        'bad_entry_rate': bad_entry_rate,
        'matched_abs_mean': matched_abs_mean,
        'per_day_weighted': per_day_weighted,
        'per_regime_weighted': per_regime_weighted,
        'tod_buckets_hit': len(tod_buckets_hit),
    }


# ─── Rule Evaluation ────────────────────────────────────────────────────

def evaluate_rule(rule: CandidateRule, df: pd.DataFrame) -> RuleScore:
    """Full evaluation with walk-forward, concentration checks, and winsorization.
    Routes SKIP rules to the separate skip evaluator."""
    if rule.direction == 'SKIP':
        return _evaluate_skip_rule(rule, df)
    return _evaluate_entry_rule(rule, df)


def _get_train_only(df: pd.DataFrame) -> pd.DataFrame:
    """Return training-only data (exclude holdout days) for in-sample metrics.

    FIX: In-sample metrics were computed on the full dataset including
    holdout/OOS data, leaking future information into the 40% in-sample
    component of the composite score.
    """
    days = sorted(df['day_id'].unique())
    n_days = len(days)
    if n_days <= WF_HOLDOUT_DAYS:
        return df  # not enough data to reserve holdout
    train_days = days[:n_days - WF_HOLDOUT_DAYS]
    return df[df['day_id'].isin(train_days)]


def _evaluate_entry_rule(rule: CandidateRule, df: pd.DataFrame) -> RuleScore:
    """Evaluate a LONG/SHORT entry rule."""
    score = RuleScore(rule=rule)

    # FIX: Use train-only data for in-sample metrics (exclude holdout)
    df_train = _get_train_only(df)
    overall = score_rule_on_slice(rule, df_train)
    if overall['support'] < _cfg.MIN_SUPPORT:          # ← runtime read
        score.support = overall.get('support', 0)
        return score

    score.support = overall['support']
    score.distinct_days = overall['distinct_days']
    score.mean_fwd_return = overall['mean_return']
    score.median_fwd_return = overall['median_return']
    score.win_rate = overall['win_rate']
    score.median_mfe = overall['median_mfe']
    score.median_mae = overall['median_mae']
    score.max_mae = overall['max_mae']

    score.mes_gross_expectancy = spy_pct_to_mes_dollars(score.mean_fwd_return, gross=True)
    score.mes_net_expectancy = spy_pct_to_mes_dollars(score.mean_fwd_return)
    score.mes_median_mfe_pts = spy_pct_to_mes_points(score.median_mfe)
    score.mes_median_mae_pts = spy_pct_to_mes_points(score.median_mae)

    _apply_concentration_checks(score, overall)
    _run_walk_forward(score, rule, df, skip=False)
    score.composite_score = _compute_entry_composite(score)
    return score


def _evaluate_skip_rule(rule: CandidateRule, df: pd.DataFrame) -> RuleScore:
    """Evaluate a SKIP rule using skip-specific utility."""
    score = RuleScore(rule=rule)

    overall = score_skip_rule_on_slice(rule, df)
    if overall['support'] < _cfg.MIN_SUPPORT:          # ← runtime read
        score.support = overall.get('support', 0)
        return score

    score.support = overall['support']
    score.distinct_days = overall['distinct_days']
    score.skip_expectancy_reduction = overall['expectancy_reduction']
    score.skip_chop_increase = overall['chop_increase']
    score.skip_bad_entry_rate = overall['bad_entry_rate']
    score.mean_fwd_return = overall['matched_abs_mean']
    score.median_fwd_return = 0.0
    score.win_rate = 0.0

    _apply_concentration_checks(score, overall)
    _run_walk_forward(score, rule, df, skip=True)
    score.composite_score = _compute_skip_composite(score)
    return score


# ─── Concentration Checks (shared) ──────────────────────────────────────

def _apply_concentration_checks(score: RuleScore, stats: Dict):
    """Apply day/regime/TOD concentration checks from stats dict."""
    per_day = stats.get('per_day_weighted', {})
    if per_day:
        total_abs = sum(abs(v) for v in per_day.values())
        if total_abs > 0:
            max_day_pct = max(abs(v) / total_abs for v in per_day.values())
            score.max_day_contribution_pct = max_day_pct
            score.day_concentration_ok = max_day_pct <= _cfg.MAX_SINGLE_DAY_SCORE_PCT
        else:
            score.day_concentration_ok = True
    elif score.distinct_days == 1:
        score.max_day_contribution_pct = 1.0
        score.day_concentration_ok = False

    per_regime = stats.get('per_regime_weighted', {})
    if per_regime:
        total_abs = sum(abs(v) for v in per_regime.values())
        if total_abs > 0:
            max_regime_pct = max(abs(v) / total_abs for v in per_regime.values())
            score.max_regime_contribution_pct = max_regime_pct
            score.regime_concentration_ok = max_regime_pct <= _cfg.MAX_SINGLE_REGIME_SCORE_PCT
        else:
            score.regime_concentration_ok = True

    score.tod_bucket_count = stats.get('tod_buckets_hit', 0)
    is_tod_rule = any('tod_' in p.feature or 'pct_of_day' in p.feature
                      for p in score.rule.predicates)
    if not is_tod_rule:
        score.tod_coverage_ok = score.tod_bucket_count >= _cfg.MIN_TOD_BUCKETS
    else:
        score.tod_coverage_ok = True


# ─── Walk-Forward (shared) ──────────────────────────────────────────────

def _run_walk_forward(score: RuleScore, rule: CandidateRule,
                      df: pd.DataFrame, skip: bool):
    """Run walk-forward evaluation across day-based splits.

    Collects per-fold OOS metrics so composite scoring can be driven
    primarily by out-of-sample performance, not in-sample fit.
    """
    splits = make_wf_splits(df)

    # FIX: Require minimum support per fold to prevent single-outlier
    # domination. Weight fold metrics by support for fair averaging.
    MIN_FOLD_SUPPORT = 3  # at least 3 firings per fold to count
    fold_returns = []
    fold_win_rates = []
    fold_weights = []   # support-based weights

    for train_df, val_df in splits:
        if skip:
            val_stats = score_skip_rule_on_slice(rule, val_df)
            sup = val_stats['support']
            if sup >= MIN_FOLD_SUPPORT:
                score.wf_folds += 1
                exp_red = val_stats['expectancy_reduction']
                fold_returns.append(exp_red)
                fold_weights.append(sup)
                if exp_red > 0:
                    score.wf_profitable_folds += 1
        else:
            val_stats = score_rule_on_slice(rule, val_df)
            sup = val_stats['support']
            if sup >= MIN_FOLD_SUPPORT:
                score.wf_folds += 1
                fold_returns.append(val_stats['mean_return'])
                fold_win_rates.append(val_stats['win_rate'])
                fold_weights.append(sup)
                if val_stats['mean_return'] > 0:
                    score.wf_profitable_folds += 1

    if score.wf_folds > 0:
        score.wf_stability = score.wf_profitable_folds / score.wf_folds
        # FIX: Support-weighted average so high-support folds matter more
        total_w = sum(fold_weights)
        if total_w > 0:
            score.wf_mean_return = sum(r * w for r, w in zip(fold_returns, fold_weights)) / total_w
            if fold_win_rates:
                wr_weights = fold_weights[:len(fold_win_rates)]
                wr_total = sum(wr_weights)
                score.wf_mean_win_rate = sum(r * w for r, w in zip(fold_win_rates, wr_weights)) / wr_total if wr_total > 0 else 0.0
        else:
            score.wf_mean_return = 0.0
            score.wf_mean_win_rate = 0.0
    else:
        score.wf_stability = 0.0
        score.wf_mean_return = 0.0
        score.wf_mean_win_rate = 0.0


# ─── Composite Scoring ──────────────────────────────────────────────────

def _compute_entry_composite(s: RuleScore) -> float:
    """Composite score for LONG/SHORT entry rules.

    Walk-forward OOS results are the PRIMARY driver of composite quality.
    In-sample metrics are used only as secondary signals and penalties.

    Hypothesis knobs wired:
      MOVE_SIZE_PREFERENCE  → scales the MFE reward component
      INTERMARKET_WEIGHT    → bonus for divergence-family rules
    """
    if s.support < _cfg.MIN_SUPPORT:                    # ← runtime read
        return -999.0

    raw = 0.0

    # PRIMARY: Walk-forward OOS performance (60% of positive signal)
    # wf_mean_return is the average OOS return across folds
    wf_expectancy_usd = spy_pct_to_mes_dollars(s.wf_mean_return) if s.wf_folds > 0 else 0.0
    raw += 0.35 * wf_expectancy_usd

    # Walk-forward stability (fraction of profitable folds)
    raw += W_STABILITY * s.wf_stability * 50

    # Walk-forward OOS win rate
    raw += 0.10 * (s.wf_mean_win_rate - 0.5) * 100 if s.wf_folds > 0 else 0.0

    # SECONDARY: In-sample signals (scaled down, 40% of positive signal)
    # Net expectancy
    raw += (W_NET_EXPECTANCY * 0.5) * s.mes_net_expectancy

    # MFE reward (winsorized), scaled by move_size_preference
    move_pref = getattr(_cfg, 'MOVE_SIZE_PREFERENCE', 1.0)
    raw += (W_MFE * 0.5) * s.mes_median_mfe_pts * MES_POINT_VALUE * move_pref

    # Directional accuracy (in-sample, discounted)
    raw += (W_DIRECTION * 0.5) * (s.win_rate - 0.5) * 100

    # Intermarket bonus: divergence-family rules get a boost
    intermarket_w = getattr(_cfg, 'INTERMARKET_WEIGHT', 1.0)
    if s.rule.source_family == 'divergence' and intermarket_w != 1.0:
        # Additive bonus proportional to how much intermarket_weight exceeds 1.0
        # e.g. intermarket_weight=1.3 → +30% of current raw (capped at ±15 pts)
        bonus = raw * (intermarket_w - 1.0)
        bonus = max(-15.0, min(15.0, bonus))
        raw += bonus

    # Penalties
    penalties = {}

    if s.mes_median_mae_pts > 0:
        penalties['drawdown'] = P_DRAWDOWN * s.mes_median_mae_pts * MES_POINT_VALUE
        raw -= penalties['drawdown']

    if s.rule.complexity > 2:
        penalties['complexity'] = P_COMPLEXITY * (s.rule.complexity - 2) * 10
        raw -= penalties['complexity']

    min_sup = _cfg.MIN_SUPPORT                          # ← runtime read
    if s.support < min_sup * 3:
        penalties['low_support'] = P_LOW_SUPPORT * (1 - s.support / (min_sup * 3)) * 20
        raw -= penalties['low_support']

    if s.distinct_days < _cfg.MIN_DISTINCT_DAYS:        # ← runtime read
        penalties['low_days'] = 20.0
        raw -= penalties['low_days']

    if not s.day_concentration_ok:
        excess = s.max_day_contribution_pct - _cfg.MAX_SINGLE_DAY_SCORE_PCT
        penalties['day_concentration'] = 30.0 * excess / (1.0 - _cfg.MAX_SINGLE_DAY_SCORE_PCT)
        raw -= penalties['day_concentration']

    if not s.regime_concentration_ok:
        excess = s.max_regime_contribution_pct - _cfg.MAX_SINGLE_REGIME_SCORE_PCT
        penalties['regime_concentration'] = 15.0 * excess / (1.0 - _cfg.MAX_SINGLE_REGIME_SCORE_PCT)
        raw -= penalties['regime_concentration']

    if not s.tod_coverage_ok:
        penalties['tod_narrow'] = 10.0
        raw -= penalties['tod_narrow']

    s.penalties = penalties
    return raw


def _compute_skip_composite(s: RuleScore) -> float:
    """Composite score for SKIP rules.

    Hypothesis knob wired:
      SKIP_AGGRESSIVENESS  → multiplier on final skip score
    """
    if s.support < _cfg.MIN_SUPPORT:                    # ← runtime read
        return -999.0

    raw = 0.0
    raw += 40.0 * max(0.0, s.skip_expectancy_reduction)
    raw += 20.0 * max(0.0, s.skip_chop_increase)
    raw += 15.0 * s.skip_bad_entry_rate
    raw += W_STABILITY * s.wf_stability * 50

    penalties = {}

    if s.rule.complexity > 2:
        penalties['complexity'] = P_COMPLEXITY * (s.rule.complexity - 2) * 10
        raw -= penalties['complexity']

    min_sup = _cfg.MIN_SUPPORT                          # ← runtime read
    if s.support < min_sup * 3:
        penalties['low_support'] = P_LOW_SUPPORT * (1 - s.support / (min_sup * 3)) * 20
        raw -= penalties['low_support']

    if s.distinct_days < _cfg.MIN_DISTINCT_DAYS:        # ← runtime read
        penalties['low_days'] = 20.0
        raw -= penalties['low_days']

    if not s.day_concentration_ok:
        excess = s.max_day_contribution_pct - _cfg.MAX_SINGLE_DAY_SCORE_PCT
        penalties['day_concentration'] = 30.0 * excess / (1.0 - _cfg.MAX_SINGLE_DAY_SCORE_PCT)
        raw -= penalties['day_concentration']

    if not s.regime_concentration_ok:
        excess = s.max_regime_contribution_pct - _cfg.MAX_SINGLE_REGIME_SCORE_PCT
        penalties['regime_concentration'] = 15.0 * excess / (1.0 - _cfg.MAX_SINGLE_REGIME_SCORE_PCT)
        raw -= penalties['regime_concentration']

    if not s.tod_coverage_ok:
        penalties['tod_narrow'] = 10.0
        raw -= penalties['tod_narrow']

    s.penalties = penalties

    # Apply skip aggressiveness multiplier (Karpathy knob)
    skip_agg = getattr(_cfg, 'SKIP_AGGRESSIVENESS', 1.0)
    return raw * skip_agg


# ─── Neighbor Robustness ─────────────────────────────────────────────────

def check_neighbor_robustness(rule: CandidateRule, df: pd.DataFrame,
                               band_pct: float = None) -> bool:
    """Check if rule survives when thresholds are shifted +/- band_pct."""
    if band_pct is None:
        band_pct = _cfg.NEIGHBOR_BAND_PCT               # ← runtime read

    min_sup = _cfg.MIN_SUPPORT                           # ← runtime read

    if rule.direction == 'SKIP':
        base_stats = score_skip_rule_on_slice(rule, df)
        if base_stats['support'] < min_sup:
            return False
        base_positive = base_stats['expectancy_reduction'] > 0
    else:
        base_stats = score_rule_on_slice(rule, df)
        if base_stats['support'] < min_sup:
            return False
        base_positive = base_stats['mean_return'] > 0

    for pred in rule.predicates:
        if pred.op in ('lt', 'gt'):
            for shift in [-band_pct, +band_pct]:
                # For near-zero thresholds, multiplicative shift does nothing.
                # Use additive epsilon perturbation instead.
                if isinstance(pred.value, (int, float)) and abs(pred.value) < 1e-6:
                    shifted_val = pred.value + shift  # additive (band_pct is ~0.10)
                elif isinstance(pred.value, (int, float)):
                    shifted_val = pred.value * (1 + shift)  # multiplicative
                else:
                    continue  # string value, can't shift
                shifted = Predicate(
                    feature=pred.feature,
                    op=pred.op,
                    value=shifted_val,
                )
                shifted_rule = CandidateRule(
                    name=rule.name + '_shifted',
                    direction=rule.direction,
                    predicates=[shifted if p is pred else p for p in rule.predicates],
                    horizon_min=rule.horizon_min,
                )
                if rule.direction == 'SKIP':
                    shifted_stats = score_skip_rule_on_slice(shifted_rule, df)
                    if shifted_stats['support'] < min_sup * 0.5:
                        return False
                    if (shifted_stats['expectancy_reduction'] > 0) != base_positive:
                        return False
                else:
                    shifted_stats = score_rule_on_slice(shifted_rule, df)
                    if shifted_stats['support'] < min_sup * 0.5:
                        return False
                    if (shifted_stats['mean_return'] > 0) != base_positive:
                        return False

        # FIX: Handle 'eq' on quantile bins — check adjacent bins
        elif pred.op in ('eq', 'in_quantile') and isinstance(pred.value, (int, float)):
            bin_val = int(pred.value)
            for neighbor_bin in [bin_val - 1, bin_val + 1]:
                if neighbor_bin < 0:
                    continue
                shifted = Predicate(
                    feature=pred.feature,
                    op=pred.op,
                    value=float(neighbor_bin),
                )
                shifted_rule = CandidateRule(
                    name=rule.name + '_neighbor',
                    direction=rule.direction,
                    predicates=[shifted if p is pred else p for p in rule.predicates],
                    horizon_min=rule.horizon_min,
                )
                if rule.direction == 'SKIP':
                    shifted_stats = score_skip_rule_on_slice(shifted_rule, df)
                    # Adjacent bin must still have some support
                    if shifted_stats['support'] < min_sup * 0.3:
                        return False
                else:
                    shifted_stats = score_rule_on_slice(shifted_rule, df)
                    if shifted_stats['support'] < min_sup * 0.3:
                        return False

    return True


# ─── Overlap Detection ──────────────────────────────────────────────────

def compute_overlap(rule_a: CandidateRule, rule_b: CandidateRule,
                    df: pd.DataFrame) -> float:
    """Compute Jaccard overlap between two rules' match sets."""
    mask_a = rule_a.evaluate(df)
    mask_b = rule_b.evaluate(df)
    intersection = (mask_a & mask_b).sum()
    union = (mask_a | mask_b).sum()
    if union == 0:
        return 0.0
    return intersection / union


def deduplicate_rules(scored_rules: List[RuleScore], df: pd.DataFrame,
                      max_overlap: float = None) -> List[RuleScore]:
    """Remove overlapping rules, keeping the higher-scoring one."""
    if max_overlap is None:
        max_overlap = getattr(_cfg, 'MAX_OVERLAP', 0.60)  # ← runtime read from hypothesis
    scored_rules = sorted(scored_rules, key=lambda s: s.composite_score, reverse=True)
    kept = []
    for candidate in scored_rules:
        is_dup = False
        for existing in kept:
            overlap = compute_overlap(candidate.rule, existing.rule, df)
            if overlap > max_overlap:
                is_dup = True
                break
        if not is_dup:
            kept.append(candidate)
    return kept
