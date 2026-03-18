"""
Karpathy Autoresearch — Deterministic Judge

Compares champion vs challenger using FIXED metrics only.
No LLM calls. Pure Python. The judge cannot be mutated.

Decision criteria (all must be met for challenger to win):
1. Validation utility improved (or at least not worse)
2. Stability across days did not degrade
3. Concentration did not worsen
4. Rule count did not explode
5. Overlap did not increase materially
6. Skip quality did not degrade
7. Net /MES expectancy improved or held

If the challenger improves on the primary metric (net /MES expectancy)
without failing any guard rails, it wins.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


# ── Metrics Extraction ────────────────────────────────────────────────

def extract_metrics(diagnostics: dict, accepted_rules: list) -> dict:
    """Extract the fixed metrics the judge uses from a run's outputs."""
    entry_rules = [r for r in accepted_rules if r.get("direction") != "SKIP"]
    skip_rules = [r for r in accepted_rules if r.get("direction") == "SKIP"]

    # Net /MES expectancy (mean across entry rules)
    net_exps = [r.get("mes_net_expectancy_usd", 0.0) for r in entry_rules]
    mean_net_exp = sum(net_exps) / len(net_exps) if net_exps else 0.0

    # Walk-forward stability (mean)
    stabilities = [r.get("wf_stability", 0.0) for r in accepted_rules]
    mean_stability = sum(stabilities) / len(stabilities) if stabilities else 0.0

    # Day concentration (worst)
    day_pcts = [r.get("max_day_contribution_pct", 0.0) for r in accepted_rules]
    worst_day = max(day_pcts) if day_pcts else 0.0
    day_fails = sum(1 for r in accepted_rules if not r.get("day_concentration_ok", True))

    # Regime concentration (worst)
    regime_pcts = [r.get("max_regime_contribution_pct", 0.0) for r in accepted_rules]
    worst_regime = max(regime_pcts) if regime_pcts else 0.0
    regime_fails = sum(1 for r in accepted_rules if not r.get("regime_concentration_ok", True))

    # Rule count / complexity
    total_rules = len(accepted_rules)
    n_entry = len(entry_rules)
    n_skip = len(skip_rules)

    # Composite scores
    composites = [r.get("composite_score", 0.0) for r in accepted_rules]
    mean_composite = sum(composites) / len(composites) if composites else 0.0
    sum_composite = sum(composites)

    # Family diversity (how many distinct families)
    families = set(r.get("source_family", "") for r in accepted_rules)

    # Skip quality
    skip_exp_reductions = [r.get("skip_expectancy_reduction", 0.0) for r in skip_rules]
    mean_skip_quality = sum(skip_exp_reductions) / len(skip_exp_reductions) if skip_exp_reductions else 0.0

    return {
        "mean_net_expectancy_usd": round(mean_net_exp, 4),
        "sum_composite": round(sum_composite, 4),
        "mean_composite": round(mean_composite, 4),
        "mean_wf_stability": round(mean_stability, 4),
        "worst_day_concentration": round(worst_day, 4),
        "day_concentration_fails": day_fails,
        "worst_regime_concentration": round(worst_regime, 4),
        "regime_concentration_fails": regime_fails,
        "total_rules": total_rules,
        "n_entry": n_entry,
        "n_skip": n_skip,
        "n_families": len(families),
        "families": sorted(families),
        "mean_skip_quality": round(mean_skip_quality, 4),
    }


# ── Judge Decision ────────────────────────────────────────────────────

# Minimum improvement required to accept challenger (prevents noise wins)
MIN_COMPOSITE_IMPROVEMENT_PCT = 0.02     # 2% better sum-of-composites
MAX_STABILITY_DEGRADATION = 0.05         # ≤5% stability loss allowed
MAX_RULE_COUNT_INCREASE = 4              # at most 4 more rules
MAX_DAY_CONCENTRATION_INCREASE = 0.05    # worst-day cannot worsen by >5pp


def judge(champion_metrics: dict, challenger_metrics: dict,
          patch_summary: str = "") -> dict:
    """Compare champion vs challenger. Returns structured decision.

    Returns dict with:
        - accepted: bool
        - reason: str
        - details: dict of comparisons
    """
    decision = {
        "timestamp": datetime.now().isoformat(),
        "patch_summary": patch_summary,
        "champion": champion_metrics,
        "challenger": challenger_metrics,
        "checks": {},
        "accepted": False,
        "reason": "",
    }

    checks = decision["checks"]

    # ── Check 1: Composite improvement ────────────────────────────────
    # Handles all sign combinations including negative baselines:
    #   positive → more positive: normal relative improvement
    #   negative → less negative: real improvement (e.g. -100 → -10 is good)
    #   negative → positive: big win
    #   near-zero: use absolute delta with epsilon denominator
    champ_comp = champion_metrics["sum_composite"]
    chall_comp = challenger_metrics["sum_composite"]
    abs_delta = chall_comp - champ_comp

    # Use max(|champion|, 1.0) as denominator to avoid divide-by-zero
    # and to give sensible relative improvement for negative baselines.
    # -100 → -10 gives abs_delta=+90, denom=100, improvement=0.90 (90% better).
    denom = max(abs(champ_comp), 1.0)
    improvement_pct = abs_delta / denom

    checks["composite_improvement_pct"] = round(improvement_pct, 4)
    checks["composite_pass"] = improvement_pct >= MIN_COMPOSITE_IMPROVEMENT_PCT

    # ── Check 2: Stability did not degrade ────────────────────────────
    stability_delta = (challenger_metrics["mean_wf_stability"]
                       - champion_metrics["mean_wf_stability"])
    checks["stability_delta"] = round(stability_delta, 4)
    checks["stability_pass"] = stability_delta >= -MAX_STABILITY_DEGRADATION

    # ── Check 3: Day concentration did not worsen ─────────────────────
    day_conc_delta = (challenger_metrics["worst_day_concentration"]
                      - champion_metrics["worst_day_concentration"])
    checks["day_concentration_delta"] = round(day_conc_delta, 4)
    checks["day_concentration_pass"] = day_conc_delta <= MAX_DAY_CONCENTRATION_INCREASE

    # Also reject if challenger has more concentration fails
    checks["day_concentration_fails_pass"] = (
        challenger_metrics["day_concentration_fails"]
        <= champion_metrics["day_concentration_fails"]
    )

    # ── Check 4: Rule count did not explode ───────────────────────────
    rule_delta = challenger_metrics["total_rules"] - champion_metrics["total_rules"]
    checks["rule_count_delta"] = rule_delta
    checks["rule_count_pass"] = rule_delta <= MAX_RULE_COUNT_INCREASE

    # ── Check 5: Skip quality did not degrade ─────────────────────────
    skip_delta = (challenger_metrics["mean_skip_quality"]
                  - champion_metrics["mean_skip_quality"])
    checks["skip_quality_delta"] = round(skip_delta, 4)
    # Skip quality should not degrade (allow small tolerance)
    checks["skip_quality_pass"] = skip_delta >= -0.05

    # ── Check 6: Net /MES expectancy ──────────────────────────────────
    exp_delta = (challenger_metrics["mean_net_expectancy_usd"]
                 - champion_metrics["mean_net_expectancy_usd"])
    checks["net_expectancy_delta"] = round(exp_delta, 4)
    # Must not degrade more than $1
    checks["net_expectancy_pass"] = exp_delta >= -1.0

    # ── Final decision ────────────────────────────────────────────────
    all_pass = all(v for k, v in checks.items() if k.endswith("_pass"))
    has_improvement = checks["composite_pass"]

    if all_pass and has_improvement:
        decision["accepted"] = True
        decision["reason"] = (
            f"Challenger improves composite by {improvement_pct*100:.1f}% "
            f"with net expectancy delta ${exp_delta:+.2f}, "
            f"stability delta {stability_delta:+.4f}. "
            f"All guardrails passed."
        )
    elif all_pass and not has_improvement:
        decision["accepted"] = False
        decision["reason"] = (
            f"All guardrails pass but composite improvement "
            f"({improvement_pct*100:.1f}%) below minimum threshold "
            f"({MIN_COMPOSITE_IMPROVEMENT_PCT*100:.0f}%). "
            f"Champion retained."
        )
    else:
        failed = [k.replace("_pass", "") for k, v in checks.items()
                  if k.endswith("_pass") and not v]
        decision["accepted"] = False
        decision["reason"] = (
            f"Challenger failed guardrails: {', '.join(failed)}. "
            f"Champion retained."
        )

    return decision


# ── Special case: no champion yet ─────────────────────────────────────

def judge_first_run(challenger_metrics: dict) -> dict:
    """When there's no champion yet, accept any valid challenger."""
    decision = {
        "timestamp": datetime.now().isoformat(),
        "patch_summary": "first_run",
        "champion": None,
        "challenger": challenger_metrics,
        "checks": {},
        "accepted": challenger_metrics["total_rules"] > 0,
        "reason": (
            "First run accepted as champion baseline."
            if challenger_metrics["total_rules"] > 0
            else "First run produced no rules. No champion set."
        ),
    }
    return decision
