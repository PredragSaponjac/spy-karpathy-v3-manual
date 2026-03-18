"""
Karpathy Autoresearch — Rule Compiler
Generates candidate rules from feature space, evaluates them,
and promotes survivors into a clean rulebook.

Rule hierarchy:
  A. Level rules — single feature quintile/threshold
  B. Interaction rules — 2-3 feature combinations (weighted by hypothesis)
  C. Divergence rules — SPY vs QQQ / intermarket (weighted by hypothesis)
  D. Sequence rules — multi-snapshot state changes (weighted by hypothesis)
  E. Skip rules — conditions where edge is bad

Mutable knobs (MIN_SUPPORT, RULE_FAMILIES_ENABLED, FEATURE_FAMILY_WEIGHTS,
DIVERGENCE_FAMILY_WEIGHTS, SEQUENCE_FAMILY_WEIGHTS) are read from the
config MODULE at call time so HypothesisOverride patches propagate.
"""
import itertools
import math
import numpy as np
import pandas as pd
from typing import List, Dict, Optional

# ── Import config MODULE for runtime-mutable knobs ────────────────────
import config as _cfg

# Constants that are NEVER hypothesis-mutable — safe to bind once
QUANTILE_BINS          = _cfg.QUANTILE_BINS
MAX_PREDICATES_DEFAULT = _cfg.MAX_PREDICATES_DEFAULT
MAX_PREDICATES_ELITE   = _cfg.MAX_PREDICATES_ELITE
PRIMARY_HORIZONS       = _cfg.PRIMARY_HORIZONS
MAX_LIVE_RULES         = _cfg.MAX_LIVE_RULES

# MUTABLE at runtime — always read through _cfg.*
# _cfg.MIN_SUPPORT
# _cfg.RULE_FAMILIES_ENABLED     (Karpathy shell knob)
# _cfg.FEATURE_FAMILY_WEIGHTS    (Karpathy shell knob)
# _cfg.DIVERGENCE_FAMILY_WEIGHTS (Karpathy shell knob)
# _cfg.SEQUENCE_FAMILY_WEIGHTS   (Karpathy shell knob)

from evaluator import (
    Predicate, CandidateRule, RuleScore,
    evaluate_rule, check_neighbor_robustness,
    deduplicate_rules,
)
from feature_factory import get_all_feature_cols, get_feature_families


# ─── Helper: family weight lookup ─────────────────────────────────────

def _get_family_weight(weights_dict: dict, key: str) -> float:
    """Look up a family weight; return 1.0 if not specified."""
    if not weights_dict:
        return 1.0
    return weights_dict.get(key, 1.0)


def _scale_rule_count(base: int, weight: float) -> int:
    """Scale a candidate count by a weight, clipping to ≥1."""
    return max(1, int(math.ceil(base * weight)))


# ─── A. Level Rules ─────────────────────────────────────────────────────

def generate_level_rules(df: pd.DataFrame,
                         horizons: List[int] = None) -> List[CandidateRule]:
    """Single-feature quintile/percentile rules."""
    if horizons is None:
        horizons = PRIMARY_HORIZONS

    rules = []
    qbin_cols = [c for c in df.columns if f'_q{QUANTILE_BINS}' in c]

    for col in qbin_cols:
        base_name = col.replace(f'_q{QUANTILE_BINS}', '')
        for qbin in range(QUANTILE_BINS):
            for direction in ['LONG', 'SHORT']:
                for hz in horizons:
                    pred = Predicate(feature=col, op='eq', value=qbin)
                    name = f"L_{base_name}_Q{qbin}_{direction}_{hz}m"
                    rule = CandidateRule(
                        name=name, direction=direction,
                        predicates=[pred], horizon_min=hz,
                        source_family='level',
                    )
                    rules.append(rule)

    pct_cols = [c for c in df.columns if c.endswith('_pct')]
    for col in pct_cols:
        for direction in ['LONG', 'SHORT']:
            for hz in horizons:
                rules.append(CandidateRule(
                    name=f"L_{col}_low_{direction}_{hz}m",
                    direction=direction,
                    predicates=[Predicate(col, 'lt', 0.20)],
                    horizon_min=hz, source_family='level',
                ))
                rules.append(CandidateRule(
                    name=f"L_{col}_high_{direction}_{hz}m",
                    direction=direction,
                    predicates=[Predicate(col, 'gt', 0.80)],
                    horizon_min=hz, source_family='level',
                ))

    return rules


# ─── B. Interaction Rules ───────────────────────────────────────────────

def generate_interaction_rules(df: pd.DataFrame,
                                horizons: List[int] = None,
                                max_rules: int = 5000) -> List[CandidateRule]:
    """2-feature combination rules from different families.

    FEATURE_FAMILY_WEIGHTS affects how many interaction slots each family
    gets: weight > 1 → more columns selected, weight < 1 → fewer.
    """
    if horizons is None:
        horizons = PRIMARY_HORIZONS

    ffw = getattr(_cfg, 'FEATURE_FAMILY_WEIGHTS', {})   # ← runtime read

    rules = []
    families = get_feature_families(df)

    # Base key columns per family — weights expand or shrink the list
    priority_raw = {
        'spy_dealer':    ['gex_total', 'gex_normalized', 'dealer_gamma_regime'],
        'spy_flow':      ['nope', 'net_prem', 'pcr_vol'],
        'spy_skew':      ['atm_avg_iv', 'skew_25d', 'iv_slope'],
        'spy_structure':  ['pin_score', 'spot_vs_poc'],
        'spy_fluxgate':  ['efficiency_ratio', 'structural_gate'],
        'spy_micro':     ['charm_meltup_score', 'vanna_crush_score'],
        'spy_internals': ['vix', 'tick', 'breadth_composite', 'trin'],
        'spy_context':   ['pct_of_day'],
        'qqq':           ['qqq_nope', 'qqq_gex_total', 'qqq_atm_avg_iv'],
        'divergence':    ['div_gex', 'div_nope', 'div_atm_iv'],
    }

    # Map priority_raw family names → hypothesis family keys
    _family_key_map = {
        'spy_dealer': 'dealer', 'spy_flow': 'flow', 'spy_skew': 'skew',
        'spy_structure': 'structure', 'spy_fluxgate': 'fluxgate',
        'spy_micro': 'micro', 'spy_internals': 'internals',
        'spy_context': 'context', 'qqq': 'internals',
        'divergence': 'dealer',  # divergence interactions get base weight
    }

    key_per_family = {}
    for family_name, raw_cols in priority_raw.items():
        hyp_key = _family_key_map.get(family_name, family_name)
        weight = _get_family_weight(ffw, hyp_key)

        present = [c for c in raw_cols if c in df.columns]
        binned = [f'{c}_q{QUANTILE_BINS}' for c in present
                  if f'{c}_q{QUANTILE_BINS}' in df.columns]
        # FIX: Include raw columns that DON'T have quantile bins
        # (e.g., binary features like charm_meltup_score, structural_gate)
        # so they can participate in mixed bin+raw interactions
        unbinned_raw = [c for c in present
                        if f'{c}_q{QUANTILE_BINS}' not in df.columns]
        base_list = binned + unbinned_raw if (binned or unbinned_raw) else present[:2]

        # Weight controls how many columns we keep
        n_keep = _scale_rule_count(len(base_list), weight)
        key_per_family[family_name] = base_list[:n_keep]

    family_names = list(key_per_family.keys())
    for f1, f2 in itertools.combinations(family_names, 2):
        cols1 = key_per_family[f1]
        cols2 = key_per_family[f2]

        for c1, c2 in itertools.product(cols1, cols2):
            for direction in ['LONG', 'SHORT']:
                for hz in horizons:
                    c1_is_bin = f'_q{QUANTILE_BINS}' in c1
                    c2_is_bin = f'_q{QUANTILE_BINS}' in c2

                    if c1_is_bin and c2_is_bin:
                        # Both columns have quantile bins — use extreme-bin interactions
                        for q1 in [0, QUANTILE_BINS - 1]:
                            for q2 in [0, QUANTILE_BINS - 1]:
                                rules.append(CandidateRule(
                                    name=f"I_{c1}_Q{q1}_{c2}_Q{q2}_{direction}_{hz}m",
                                    direction=direction,
                                    predicates=[
                                        Predicate(c1, 'eq', q1),
                                        Predicate(c2, 'eq', q2),
                                    ],
                                    horizon_min=hz,
                                    source_family='interaction',
                                ))
                    elif c1_is_bin and not c2_is_bin:
                        # FIX: Mixed — c1 is binned, c2 is raw/binary
                        # Use extreme bins for c1, median split for c2
                        c2_median = df[c2].median()
                        for q1 in [0, QUANTILE_BINS - 1]:
                            for op2 in ['gt', 'lt']:
                                rules.append(CandidateRule(
                                    name=f"I_{c1}_Q{q1}_{c2}_{op2}_{direction}_{hz}m",
                                    direction=direction,
                                    predicates=[
                                        Predicate(c1, 'eq', q1),
                                        Predicate(c2, op2, c2_median),
                                    ],
                                    horizon_min=hz,
                                    source_family='interaction',
                                ))
                    elif not c1_is_bin and c2_is_bin:
                        # FIX: Mixed — c1 is raw/binary, c2 is binned
                        c1_median = df[c1].median()
                        for op1 in ['gt', 'lt']:
                            for q2 in [0, QUANTILE_BINS - 1]:
                                rules.append(CandidateRule(
                                    name=f"I_{c1}_{op1}_{c2}_Q{q2}_{direction}_{hz}m",
                                    direction=direction,
                                    predicates=[
                                        Predicate(c1, op1, c1_median),
                                        Predicate(c2, 'eq', q2),
                                    ],
                                    horizon_min=hz,
                                    source_family='interaction',
                                ))
                    # Both raw and no bins — skip (too noisy without binning)

    # Cap rules by random sampling if over max_rules (avoids ordering bias)
    if len(rules) > max_rules:
        import random
        # FIX: Use local RNG to avoid mutating global random state
        rng = random.Random(42)
        rules = rng.sample(rules, max_rules)

    return rules


# ─── C. Divergence Rules ────────────────────────────────────────────────

def generate_divergence_rules(df: pd.DataFrame,
                               horizons: List[int] = None) -> List[CandidateRule]:
    """Rules based on SPY ↔ QQQ divergence states.

    DIVERGENCE_FAMILY_WEIGHTS controls which sub-families get more rules:
    - relative_strength, z_score_div, non_confirmation,
      recoupling, lead_lag, composite
    """
    if horizons is None:
        horizons = PRIMARY_HORIZONS

    dfw = getattr(_cfg, 'DIVERGENCE_FAMILY_WEIGHTS', {})  # ← runtime read

    rules = []

    # Use zdiv_ (normalized divergence) columns, not raw div_ from the DB.
    # The expanded divergence layer creates zdiv_*_state, zdiv_*_nonconfirm,
    # zdiv_*_recoupling. Also pick up nonconfirm_price and nonconfirm_count.
    state_cols = [c for c in df.columns if c.endswith('_state') and c.startswith('zdiv_')]
    nonconfirm_cols = ([c for c in df.columns if c.startswith('zdiv_') and c.endswith('_nonconfirm')]
                       + [c for c in df.columns if c in ('nonconfirm_price', 'nonconfirm_count')])
    recouple_cols = [c for c in df.columns if c.endswith('_recoupling') and c.startswith('zdiv_')]

    # State-based rules (relative_strength / z_score_div families)
    # Uses the pre-bucketed _state columns (point-in-time z-score derived)
    # instead of full-sample quantiles which would leak future data.
    state_weight = _get_family_weight(dfw, 'z_score_div')
    if state_weight > 0.1:
        for col in state_cols:
            base = col.replace('_state', '')
            for direction in ['LONG', 'SHORT']:
                for hz in horizons:
                    # Strong positive divergence
                    rules.append(CandidateRule(
                        name=f"D_{base}_high_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(col, 'eq', 'strong_pos')],
                        horizon_min=hz, source_family='divergence',
                    ))
                    # Strong negative divergence
                    rules.append(CandidateRule(
                        name=f"D_{base}_low_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(col, 'eq', 'strong_neg')],
                        horizon_min=hz, source_family='divergence',
                    ))

    # Non-confirmation rules
    nc_weight = _get_family_weight(dfw, 'non_confirmation')
    if nc_weight > 0.1:
        for col in nonconfirm_cols:
            for direction in ['LONG', 'SHORT', 'SKIP']:
                for hz in horizons:
                    rules.append(CandidateRule(
                        name=f"D_{col}_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(col, 'eq', 1)],
                        horizon_min=hz, source_family='divergence',
                    ))

    # Recoupling rules
    rc_weight = _get_family_weight(dfw, 'recoupling')
    if rc_weight > 0.1:
        for col in recouple_cols:
            for direction in ['LONG', 'SHORT']:
                for hz in horizons:
                    rules.append(CandidateRule(
                        name=f"D_{col}_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(col, 'eq', 1)],
                        horizon_min=hz, source_family='divergence',
                    ))

    return rules


# ─── D. Sequence Rules ──────────────────────────────────────────────────

def generate_sequence_rules(df: pd.DataFrame,
                             horizons: List[int] = None) -> List[CandidateRule]:
    """Rules based on temporal state changes and sequences.

    SEQUENCE_FAMILY_WEIGHTS controls sub-family generation:
    - compression_expansion, divergence_chains, momentum_flips,
      qqq_lead_confirm, acceleration
    """
    if horizons is None:
        horizons = PRIMARY_HORIZONS

    sfw = getattr(_cfg, 'SEQUENCE_FAMILY_WEIGHTS', {})    # ← runtime read

    rules = []

    # Compression → expansion
    ce_weight = _get_family_weight(sfw, 'compression_expansion')
    if ce_weight > 0.1:
        comp_cols = [c for c in df.columns if 'compression' in c and c.startswith('seq_')]
        exp_cols = [c for c in df.columns if 'expansion' in c and c.startswith('seq_')]

        for comp_col in comp_cols:
            for direction in ['LONG', 'SHORT']:
                for hz in horizons:
                    rules.append(CandidateRule(
                        name=f"S_{comp_col}_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(comp_col, 'eq', 1)],
                        horizon_min=hz, source_family='sequence',
                    ))

        for exp_col in exp_cols:
            for direction in ['LONG', 'SHORT']:
                for hz in horizons:
                    rules.append(CandidateRule(
                        name=f"S_{exp_col}_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(exp_col, 'eq', 1)],
                        horizon_min=hz, source_family='sequence',
                    ))

    # Divergence streak rules
    dc_weight = _get_family_weight(sfw, 'divergence_chains')
    if dc_weight > 0.1:
        streak_cols = [c for c in df.columns if c.endswith('_streak_long')]
        for col in streak_cols:
            for direction in ['LONG', 'SHORT']:
                for hz in horizons:
                    rules.append(CandidateRule(
                        name=f"S_{col}_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(col, 'eq', 1)],
                        horizon_min=hz, source_family='sequence',
                    ))

    # Momentum flip rules
    mf_weight = _get_family_weight(sfw, 'momentum_flips')
    if mf_weight > 0.1 and 'seq_momentum_flip' in df.columns:
        for flip_dir in [1, -1]:
            direction = 'LONG' if flip_dir == 1 else 'SHORT'
            for hz in horizons:
                rules.append(CandidateRule(
                    name=f"S_momentum_flip_{direction}_{hz}m",
                    direction=direction,
                    predicates=[
                        Predicate('seq_momentum_flip', 'eq', 1),
                        Predicate('seq_momentum_flip_dir', 'eq', flip_dir),
                    ],
                    horizon_min=hz, source_family='sequence',
                ))

    # QQQ lead-confirm patterns
    ql_weight = _get_family_weight(sfw, 'qqq_lead_confirm')
    if ql_weight > 0.1:
        qqq_lead_cols = [c for c in df.columns if c.startswith('seq_qqq_lead')]
        for col in qqq_lead_cols:
            for direction in ['LONG', 'SHORT']:
                for hz in horizons:
                    pred_val = 1 if direction == 'LONG' else -1
                    rules.append(CandidateRule(
                        name=f"S_{col}_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(col, 'eq', pred_val)],
                        horizon_min=hz, source_family='sequence',
                    ))

    # Acceleration rules
    # Use sign-based thresholds (> 0 = accelerating, < 0 = decelerating)
    # instead of full-sample quantiles which leak future data.
    ac_weight = _get_family_weight(sfw, 'acceleration')
    if ac_weight > 0.1:
        accel_cols = [c for c in df.columns if c.startswith('seq_') and c.endswith('_accel_24')]
        for col in accel_cols:
            if col not in df.columns or df[col].std() == 0:
                continue
            for direction in ['LONG', 'SHORT']:
                for hz in horizons:
                    rules.append(CandidateRule(
                        name=f"S_{col}_high_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(col, 'gt', 0)],
                        horizon_min=hz, source_family='sequence',
                    ))
                    rules.append(CandidateRule(
                        name=f"S_{col}_low_{direction}_{hz}m",
                        direction=direction,
                        predicates=[Predicate(col, 'lt', 0)],
                        horizon_min=hz, source_family='sequence',
                    ))

    return rules


# ─── E. Skip Rules ──────────────────────────────────────────────────────

def generate_skip_rules(df: pd.DataFrame,
                        horizons: List[int] = None) -> List[CandidateRule]:
    """Rules for when NOT to trade (skip conditions)."""
    if horizons is None:
        horizons = PRIMARY_HORIZONS

    rules = []

    if 'efficiency_ratio' in df.columns:
        for hz in horizons:
            rules.append(CandidateRule(
                name=f"SKIP_low_efficiency_{hz}m", direction='SKIP',
                predicates=[Predicate('efficiency_ratio', 'lt', 0.15)],
                horizon_min=hz, source_family='skip',
            ))

    if 'structural_gate' in df.columns:
        for hz in horizons:
            rules.append(CandidateRule(
                name=f"SKIP_weak_gate_{hz}m", direction='SKIP',
                predicates=[Predicate('structural_gate', 'lt', 0.20)],
                horizon_min=hz, source_family='skip',
            ))

    nonconfirm_cols = [c for c in df.columns if c.startswith('nonconfirm_')]
    if len(nonconfirm_cols) >= 2:
        for hz in horizons:
            rules.append(CandidateRule(
                name=f"SKIP_multi_nonconfirm_{hz}m", direction='SKIP',
                predicates=[Predicate(c, 'eq', 1) for c in nonconfirm_cols[:3]],
                horizon_min=hz, source_family='skip',
            ))

    if 'pct_of_day' in df.columns and 'efficiency_ratio' in df.columns:
        for hz in horizons:
            rules.append(CandidateRule(
                name=f"SKIP_midday_chop_{hz}m", direction='SKIP',
                predicates=[
                    Predicate('pct_of_day', 'between', 0.25, 0.55),
                    Predicate('efficiency_ratio', 'lt', 0.25),
                ],
                horizon_min=hz, source_family='skip',
            ))

    if 'vix_z' in df.columns:
        for hz in horizons:
            rules.append(CandidateRule(
                name=f"SKIP_vix_spike_{hz}m", direction='SKIP',
                predicates=[Predicate('vix_z', 'gt', 2.0)],
                horizon_min=hz, source_family='skip',
            ))

    return rules


# ─── Main Compilation Pipeline ───────────────────────────────────────────

def compile_all_candidates(df: pd.DataFrame, verbose: bool = True) -> List[CandidateRule]:
    """Generate all candidate rules across all types.

    Respects _cfg.RULE_FAMILIES_ENABLED to skip disabled families.
    """
    all_rules = []
    enabled = getattr(_cfg, 'RULE_FAMILIES_ENABLED', {})  # ← runtime read

    if enabled.get('level', True):
        level = generate_level_rules(df)
        all_rules.extend(level)
        if verbose:
            print(f"  Level rules:       {len(level):6d}")
    elif verbose:
        print(f"  Level rules:       DISABLED")

    if enabled.get('interaction', True):
        interaction = generate_interaction_rules(df)
        all_rules.extend(interaction)
        if verbose:
            print(f"  Interaction rules: {len(interaction):6d}")
    elif verbose:
        print(f"  Interaction rules: DISABLED")

    if enabled.get('divergence', True):
        divergence = generate_divergence_rules(df)
        all_rules.extend(divergence)
        if verbose:
            print(f"  Divergence rules:  {len(divergence):6d}")
    elif verbose:
        print(f"  Divergence rules:  DISABLED")

    if enabled.get('sequence', True):
        sequence = generate_sequence_rules(df)
        all_rules.extend(sequence)
        if verbose:
            print(f"  Sequence rules:    {len(sequence):6d}")
    elif verbose:
        print(f"  Sequence rules:    DISABLED")

    if enabled.get('skip', True):
        skip = generate_skip_rules(df)
        all_rules.extend(skip)
        if verbose:
            print(f"  Skip rules:        {len(skip):6d}")
    elif verbose:
        print(f"  Skip rules:        DISABLED")

    if verbose:
        print(f"  TOTAL candidates:  {len(all_rules):6d}")

    return all_rules


def evaluate_and_promote(df: pd.DataFrame,
                         candidates: List[CandidateRule],
                         max_entry_rules: int = 6,
                         max_skip_rules: int = 12,
                         max_total: int = 24,
                         min_wf_folds: int = 0,
                         verbose: bool = True) -> List[RuleScore]:
    """Evaluate all candidates and promote the best survivors."""
    min_sup = _cfg.MIN_SUPPORT                            # ← runtime read

    if verbose:
        print(f"\nEvaluating {len(candidates)} candidates...")
        print(f"  Tier limits: entry≤{max_entry_rules}, skip≤{max_skip_rules}, total≤{max_total}")
        print(f"  MIN_SUPPORT={min_sup}")

    # Phase 1: Quick filter — check support
    surviving = []
    for i, rule in enumerate(candidates):
        mask = rule.evaluate(df)
        support = mask.sum()
        if support >= min_sup:
            surviving.append(rule)

        if verbose and (i + 1) % 1000 == 0:
            print(f"  Screened {i+1}/{len(candidates)}, {len(surviving)} pass support filter")

    if verbose:
        print(f"  After support filter: {len(surviving)} candidates")

    # Phase 2: Full evaluation
    scored = []
    for i, rule in enumerate(surviving):
        score = evaluate_rule(rule, df)
        min_comp = getattr(_cfg, 'MIN_COMPOSITE_SCORE', 0.0)  # ← runtime read
        if score.support >= min_sup and score.composite_score > min_comp:
            scored.append(score)

        if verbose and (i + 1) % 200 == 0:
            print(f"  Evaluated {i+1}/{len(surviving)}, {len(scored)} positive")

    if verbose:
        print(f"  After evaluation: {len(scored)} positive-scoring rules")

    # Phase 2b: Walk-forward fold gate
    if min_wf_folds > 0:
        before = len(scored)
        scored = [s for s in scored if s.wf_folds >= min_wf_folds]
        if verbose:
            print(f"  After WF fold gate (≥{min_wf_folds}): {len(scored)} (dropped {before - len(scored)})")

    # Phase 2c: Day concentration gate
    before = len(scored)
    scored = [s for s in scored if s.day_concentration_ok]
    if verbose and before != len(scored):
        print(f"  After day-concentration gate: {len(scored)} (dropped {before - len(scored)})")

    # Phase 3: Neighbor robustness check
    robust = []
    for score in scored:
        if check_neighbor_robustness(score.rule, df):
            score.neighbor_robust = True
            robust.append(score)
        else:
            score.neighbor_robust = False

    if verbose:
        print(f"  After robustness check: {len(robust)} robust rules")

    # Phase 4: Deduplicate overlapping rules
    deduped = deduplicate_rules(robust, df)

    # Phase 5: Tier-aware promotion with separate entry/skip caps
    entry_rules = [s for s in deduped if s.rule.direction in ('LONG', 'SHORT')]
    skip_rules = [s for s in deduped if s.rule.direction == 'SKIP']

    entry_rules = entry_rules[:max_entry_rules]
    skip_rules = skip_rules[:max_skip_rules]

    final = entry_rules + skip_rules
    final = sorted(final, key=lambda s: s.composite_score, reverse=True)
    final = final[:max_total]

    if verbose:
        n_entry = len([s for s in final if s.rule.direction != 'SKIP'])
        n_skip = len([s for s in final if s.rule.direction == 'SKIP'])
        print(f"  After tier-aware trim: {len(final)} promoted "
              f"(entry: {n_entry}, skip: {n_skip})")

    return final
