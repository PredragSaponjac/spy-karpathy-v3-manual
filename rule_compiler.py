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


# ─── F. Confluence Rules ───────────────────────────────────────────────

def generate_confluence_rules(
    promoted_scores: list,
    horizons: List[int] = None,
) -> List[CandidateRule]:
    """Generate pairwise cross-family combinations from promoted non-confluence rules.

    Guardrails:
    - Pairwise only (exactly 2 parent rules)
    - Cross-family only (different source_family)
    - No C_ from C_ (no nested confluence)
    - Parents must share the same direction (both SHORT or both LONG)
    - Parents must share at least one common horizon
    - Capped at MAX_CONFLUENCE_CANDIDATES total
    """
    import random
    import config as _cfg

    max_candidates = getattr(_cfg, 'MAX_CONFLUENCE_CANDIDATES', 200)

    if horizons is None:
        horizons = PRIMARY_HORIZONS

    # Filter: only non-SKIP, non-confluence promoted rules
    eligible = [
        s for s in promoted_scores
        if s.get("direction") in ("LONG", "SHORT")
        and s.get("source_family", "") != "confluence"
    ]

    if len(eligible) < 2:
        return []

    rules = []

    for i in range(len(eligible)):
        for j in range(i + 1, len(eligible)):
            r1 = eligible[i]
            r2 = eligible[j]

            # Cross-family only
            if r1.get("source_family") == r2.get("source_family"):
                continue

            # Same direction only
            if r1.get("direction") != r2.get("direction"):
                continue

            direction = r1["direction"]

            # Merge predicates from both parents
            preds_1 = [Predicate(**p) for p in r1.get("predicates", [])]
            preds_2 = [Predicate(**p) for p in r2.get("predicates", [])]

            # Deduplicate predicates (same feature+op+value = keep once)
            seen = set()
            merged_preds = []
            for p in preds_1 + preds_2:
                key = (p.feature, p.op, str(p.value), str(p.value_hi))
                if key not in seen:
                    seen.add(key)
                    merged_preds.append(p)

            # Skip if merged has too many predicates (complexity guard)
            if len(merged_preds) > MAX_PREDICATES_ELITE:
                continue

            # Use the longer horizon of the two parents
            hz = max(r1.get("horizon_min", 60), r2.get("horizon_min", 60))
            # Only use horizons that are in PRIMARY_HORIZONS
            if hz not in horizons:
                hz = max(horizons)

            name_1 = r1.get("name", "r1").split("_")[1] if "_" in r1.get("name", "") else "r1"
            name_2 = r2.get("name", "r2").split("_")[1] if "_" in r2.get("name", "") else "r2"
            fam_1 = r1.get("source_family", "x")[:3]
            fam_2 = r2.get("source_family", "x")[:3]

            name = f"C_{fam_1}_{fam_2}_{direction}_{hz}m"
            # Make unique by adding index
            name = f"{name}_{i}x{j}"

            rule = CandidateRule(
                name=name,
                direction=direction,
                predicates=merged_preds,
                horizon_min=hz,
                source_family='confluence',
            )
            rules.append(rule)

    # Cap by random sampling if over limit
    if len(rules) > max_candidates:
        rng = random.Random(42)
        rules = rng.sample(rules, max_candidates)

    return rules


def prune_confluence_by_overlap(
    confluence_scores: list,
    base_scores: list,
    df,
) -> list:
    """Prune confluence rules by Jaccard overlap and marginal utility hurdle.

    Removes confluence rules that:
    - Overlap too much with parent rules (redundant)
    - Overlap too little (too rare to be useful)
    - Don't beat their best parent by the marginal hurdle

    Returns filtered list of RuleScore objects.
    """
    import config as _cfg

    min_jaccard = getattr(_cfg, 'CONFLUENCE_MIN_JACCARD', 0.05)
    max_jaccard = getattr(_cfg, 'CONFLUENCE_MAX_JACCARD', 0.80)
    marginal_hurdle = getattr(_cfg, 'CONFLUENCE_MARGINAL_HURDLE', 0.10)
    max_promoted = getattr(_cfg, 'MAX_CONFLUENCE_PROMOTED', 2)

    # Build mask cache for base rules
    base_masks = {}
    for bs in base_scores:
        mask = bs.rule.evaluate(df)
        base_masks[bs.rule.name] = mask

    surviving = []
    for cs in confluence_scores:
        c_mask = cs.rule.evaluate(df)
        c_support = c_mask.sum()

        if c_support < 1:
            continue

        # Check Jaccard overlap with each same-direction base rule
        too_similar = False
        too_disjoint = True
        has_same_dir = False

        for bs in base_scores:
            if bs.rule.direction != cs.rule.direction:
                continue
            has_same_dir = True
            b_mask = base_masks.get(bs.rule.name)
            if b_mask is None:
                continue

            intersection = (c_mask & b_mask).sum()
            union = (c_mask | b_mask).sum()
            jaccard = intersection / union if union > 0 else 0

            if jaccard > max_jaccard:
                too_similar = True
                break
            if jaccard >= min_jaccard:
                too_disjoint = False

        # If no same-direction base rules exist, skip disjoint check
        if not has_same_dir:
            too_disjoint = False

        if too_similar or too_disjoint:
            continue

        # Marginal utility hurdle: must beat best same-direction base rule
        best_parent_composite = max(
            (bs.composite_score for bs in base_scores
             if bs.rule.direction == cs.rule.direction),
            default=0
        )
        if best_parent_composite > 0:
            improvement = (cs.composite_score - best_parent_composite) / best_parent_composite
            if improvement < marginal_hurdle:
                continue

        surviving.append(cs)

    # Sort by composite and cap
    surviving.sort(key=lambda s: s.composite_score, reverse=True)
    return surviving[:max_promoted]


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

    # NOTE: Confluence rules are NOT generated here.
    # They are generated AFTER base promotion, from promoted rules only.
    # See generate_confluence_rules() — called from karpathy_runner/nightly_train.
    if enabled.get('confluence', False) and verbose:
        print(f"  Confluence rules:  (generated after base promotion)")

    if verbose:
        print(f"  TOTAL candidates:  {len(all_rules):6d}")

    return all_rules


def evaluate_and_promote(df: pd.DataFrame,
                         candidates: List[CandidateRule],
                         max_entry_rules: int = 6,
                         max_skip_rules: int = 12,
                         max_total: int = 24,
                         min_wf_folds: int = 0,
                         verbose: bool = True,
                         prev_rule_names: set = None) -> List[RuleScore]:
    """Evaluate all candidates and promote the best survivors.

    Rule persistence: previously promoted rules (prev_rule_names) get a 15%
    composite bonus so they are not casually displaced. They are only dropped
    if they explicitly degrade (WF < 0.4, support < 50% min, or negative expectancy).
    """
    if prev_rule_names is None:
        prev_rule_names = set()
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

    # Phase 4b: Rule persistence — previously promoted rules get a composite bonus
    # so they are not casually displaced by marginally better new rules.
    # A prior rule is only truly dropped if it degrades (handled by gates above).
    if prev_rule_names:
        PERSISTENCE_BONUS = 0.15  # 15% composite boost for prior rules
        boosted = 0
        for score in deduped:
            if score.rule.name in prev_rule_names:
                score.composite_score *= (1.0 + PERSISTENCE_BONUS)
                boosted += 1
        if verbose and boosted:
            print(f"  [PERSISTENCE] Boosted {boosted} prior rules by {PERSISTENCE_BONUS:.0%}")

    # Phase 5: Direction-balanced promotion with FLOOR logic
    # BOTH SHORT and LONG rules must be maintained. The market decides which
    # fires more often — the engine must NOT drop validated rules from either side.
    #
    # CORRECT LOGIC:
    # 1. FLOOR: always keep at least min_long_rules LONG and min_short_rules SHORT
    # 2. FILL: use remaining slots for best overall rules (either direction)
    # 3. REPLACE: within each direction, better rules replace weaker ones
    # 4. NEVER reduce a direction below its floor just because the other side scored higher
    long_rules = sorted([s for s in deduped if s.rule.direction == 'LONG'],
                        key=lambda s: s.composite_score, reverse=True)
    short_rules = sorted([s for s in deduped if s.rule.direction == 'SHORT'],
                         key=lambda s: s.composite_score, reverse=True)
    skip_rules = [s for s in deduped if s.rule.direction == 'SKIP']

    # Get floor from config (default 3 each if not set)
    min_long = getattr(_cfg, 'MIN_LONG_RULES', 3)
    min_short = getattr(_cfg, 'MIN_SHORT_RULES', 3)

    # Step 1: Reserve FLOOR slots — take top N from each direction
    guaranteed_long = long_rules[:min_long]
    guaranteed_short = short_rules[:min_short]

    # Step 2: FILL remaining slots from the rest (either direction) by composite
    remaining_slots = max_entry_rules - len(guaranteed_long) - len(guaranteed_short)
    used_ids = set(id(r) for r in guaranteed_long + guaranteed_short)
    remaining_pool = sorted(
        [s for s in long_rules + short_rules if id(s) not in used_ids],
        key=lambda s: s.composite_score, reverse=True
    )
    fill_rules = remaining_pool[:max(0, remaining_slots)]

    entry_rules = guaranteed_long + guaranteed_short + fill_rules
    skip_rules = skip_rules[:max_skip_rules]

    final = entry_rules + skip_rules
    final = sorted(final, key=lambda s: s.composite_score, reverse=True)
    final = final[:max_total]

    if verbose:
        n_long = len([s for s in final if s.rule.direction == 'LONG'])
        n_short = len([s for s in final if s.rule.direction == 'SHORT'])
        n_skip = len([s for s in final if s.rule.direction == 'SKIP'])
        print(f"  After direction-balanced trim: {len(final)} promoted "
              f"(LONG: {n_long}, SHORT: {n_short}, SKIP: {n_skip})")

    return final
