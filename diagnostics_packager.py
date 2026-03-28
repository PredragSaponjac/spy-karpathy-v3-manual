"""
Karpathy Autoresearch — Diagnostics Packager

Builds the JSON context that the LLM proposer and critic need.
This is the bridge between the fixed deterministic engine output
and the bounded Karpathy mutation prompts.

Keeps the context compact enough for Sonnet-class models (~4k tokens).
"""
import json
from pathlib import Path
from typing import List, Optional

from config import ARTIFACTS_DIR, get_maturity_tier
from hypothesis import load_hypothesis
from ranking_weights import compute_family_summary


def package_diagnostics(
    diagnostics: dict,
    accepted_rules: list,
    hypothesis: dict,
    nightly_report: Optional[dict] = None,
) -> dict:
    """Build the full diagnostics context for the proposer/critic.

    Args:
        diagnostics: From artifacts/diagnostics.json
        accepted_rules: From artifacts/accepted_rules.json
        hypothesis: Current champion hypothesis dict
        nightly_report: Optional, from artifacts/nightly_report.json

    Returns:
        Compact JSON-serializable dict for LLM context.
    """
    n_days = diagnostics.get("distinct_days", 0)
    tier = get_maturity_tier(n_days)

    # ── Core summary ──────────────────────────────────────────────────
    package = {
        "maturity": {
            "tier": tier.get("mode", "unknown"),
            "label": tier.get("label", ""),
            "days": n_days,
            "snapshots": diagnostics.get("total_snapshots", 0),
        },
        "pipeline": {
            "features": diagnostics.get("total_features", 0),
            "candidates_generated": diagnostics.get("candidates_generated", 0),
            "rules_promoted": diagnostics.get("rules_promoted", 0),
            "elapsed_seconds": diagnostics.get("elapsed_seconds", 0),
        },
    }

    # ── Rule breakdown ────────────────────────────────────────────────
    if accepted_rules:
        entry_rules = [r for r in accepted_rules if r.get("direction") != "SKIP"]
        skip_rules = [r for r in accepted_rules if r.get("direction") == "SKIP"]

        package["rules"] = {
            "entry_count": len(entry_rules),
            "skip_count": len(skip_rules),
            "total": len(accepted_rules),
        }

        # Top 5 entry rules (compact)
        package["top_entry_rules"] = [
            _compact_rule(r) for r in sorted(
                entry_rules,
                key=lambda x: x.get("composite_score", 0),
                reverse=True
            )[:5]
        ]

        # Top 3 skip rules
        package["top_skip_rules"] = [
            _compact_rule(r) for r in sorted(
                skip_rules,
                key=lambda x: x.get("composite_score", 0),
                reverse=True
            )[:3]
        ]

        # Family performance summary
        package["family_performance"] = compute_family_summary(accepted_rules)

        # Overlap diagnostics: count of rules per family
        family_counts = {}
        for r in accepted_rules:
            fam = r.get("source_family", "unknown")
            family_counts[fam] = family_counts.get(fam, 0) + 1
        package["family_distribution"] = family_counts

        # Direction balance
        dir_counts = {"LONG": 0, "SHORT": 0, "SKIP": 0}
        for r in accepted_rules:
            d = r.get("direction", "LONG")
            dir_counts[d] = dir_counts.get(d, 0) + 1
        package["direction_balance"] = dir_counts

        # Day concentration summary (worst offender)
        worst_day_pct = max(
            (r.get("max_day_contribution_pct", 0) for r in accepted_rules),
            default=0
        )
        package["concentration"] = {
            "worst_day_contribution_pct": round(worst_day_pct, 4),
            "any_day_concentration_fail": any(
                not r.get("day_concentration_ok", True) for r in accepted_rules
            ),
            "any_regime_concentration_fail": any(
                not r.get("regime_concentration_ok", True) for r in accepted_rules
            ),
        }

        # WF stability summary
        stabilities = [r.get("wf_stability", 0) for r in accepted_rules]
        package["wf_summary"] = {
            "mean_stability": round(sum(stabilities) / len(stabilities), 4) if stabilities else 0,
            "min_stability": round(min(stabilities), 4) if stabilities else 0,
            "rules_above_60pct": sum(1 for s in stabilities if s >= 0.60),
        }

        # /MES expectancy summary
        net_exps = [r.get("mes_net_expectancy_usd", 0) for r in entry_rules]
        package["mes_summary"] = {
            "mean_net_expectancy_usd": round(sum(net_exps) / len(net_exps), 2) if net_exps else 0,
            "best_net_expectancy_usd": round(max(net_exps), 2) if net_exps else 0,
            "worst_net_expectancy_usd": round(min(net_exps), 2) if net_exps else 0,
        }

    else:
        package["rules"] = {"entry_count": 0, "skip_count": 0, "total": 0}
        package["top_entry_rules"] = []
        package["top_skip_rules"] = []

    # ── Feature attribution telemetry ────────────────────────────────
    if accepted_rules:
        package["feature_attribution"] = _build_feature_attribution(accepted_rules)

    # ── Current hypothesis ────────────────────────────────────────────
    package["current_hypothesis"] = {
        "rule_families": hypothesis.get("rule_families", {}),
        "feature_family_weights": hypothesis.get("feature_family_weights", {}),
        "divergence_family_weights": hypothesis.get("divergence_family_weights", {}),
        "sequence_family_weights": hypothesis.get("sequence_family_weights", {}),
        "thresholds": hypothesis.get("thresholds", {}),
        "skip_aggressiveness": hypothesis.get("skip_aggressiveness", 1.0),
        "intermarket_weight": hypothesis.get("intermarket_weight", 1.0),
        "move_size_preference": hypothesis.get("move_size_preference", 1.0),
    }

    # ── Divergence family contribution counts ────────────────────────
    package["divergence_families"] = _get_divergence_family_counts(diagnostics)

    # ── Rolling experiment memory (short-term context) ───────────────
    package["recent_experiments"] = _get_rolling_memory()

    return package


def _build_feature_attribution(accepted_rules: list) -> dict:
    """Build feature-level attribution from promoted rules.

    Returns:
        - top_by_support: features appearing in most rules
        - top_by_lift: features in rules with highest net expectancy
        - worst_drag: families that generated rules but with low/negative expectancy
        - family_contribution: per-family summary
    """
    from collections import defaultdict

    feature_stats = defaultdict(lambda: {
        "appearances": 0, "families": set(),
        "total_net_exp": 0.0, "entry_appearances": 0,
    })

    family_stats = defaultdict(lambda: {
        "rule_count": 0, "total_composite": 0.0,
        "total_net_exp": 0.0, "directions": defaultdict(int),
    })

    for rule in accepted_rules:
        fam = rule.get("source_family", "unknown")
        direction = rule.get("direction", "?")
        net_exp = rule.get("mes_net_expectancy_usd", 0)
        composite = rule.get("composite_score", 0)

        family_stats[fam]["rule_count"] += 1
        family_stats[fam]["total_composite"] += composite
        family_stats[fam]["total_net_exp"] += net_exp
        family_stats[fam]["directions"][direction] += 1

        for pred in rule.get("predicates", []):
            feat = pred.get("feature", "")
            if not feat:
                continue
            feature_stats[feat]["appearances"] += 1
            feature_stats[feat]["families"].add(fam)
            # Only count entry rules for lift (SKIP net_exp has different semantics)
            if direction != "SKIP":
                feature_stats[feat]["total_net_exp"] += net_exp
                feature_stats[feat]["entry_appearances"] += 1

    # Top by support (most appearances)
    top_by_support = sorted(
        [{"feature": f, "appearances": s["appearances"],
          "families": sorted(s["families"])}
         for f, s in feature_stats.items()],
        key=lambda x: -x["appearances"]
    )[:8]

    # Top by lift (highest average net expectancy — entry rules only)
    top_by_lift = sorted(
        [{"feature": f,
          "avg_net_exp": round(s["total_net_exp"] / s["entry_appearances"], 2),
          "entry_rules_using": s["entry_appearances"]}
         for f, s in feature_stats.items()
         if s["entry_appearances"] > 0],
        key=lambda x: -x["avg_net_exp"]
    )[:8]

    # Worst drag families (low avg composite or negative expectancy)
    worst_drag = sorted(
        [{"family": fam,
          "rule_count": s["rule_count"],
          "avg_composite": round(s["total_composite"] / s["rule_count"], 2)
          if s["rule_count"] > 0 else 0,
          "avg_net_exp": round(s["total_net_exp"] / s["rule_count"], 2)
          if s["rule_count"] > 0 else 0}
         for fam, s in family_stats.items()],
        key=lambda x: x["avg_net_exp"]
    )[:5]

    # Family contribution summary
    family_contribution = {
        fam: {
            "rule_count": s["rule_count"],
            "avg_composite": round(s["total_composite"] / s["rule_count"], 2)
            if s["rule_count"] > 0 else 0,
            "total_net_exp": round(s["total_net_exp"], 2),
            "directions": dict(s["directions"]),
        }
        for fam, s in family_stats.items()
    }

    return {
        "top_by_support": top_by_support,
        "top_by_lift": top_by_lift,
        "worst_drag": worst_drag,
        "family_contribution": family_contribution,
    }


def _get_rolling_memory(last_n: int = 10) -> dict:
    """Extract rolling 3-day and 5-day experiment summaries from memory.

    Returns compact digest so the proposer sees recent trends without
    drowning in stale history.
    """
    from pathlib import Path
    memory_path = Path(__file__).parent / "karpathy_memory.jsonl"
    if not memory_path.exists():
        return {"total_experiments": 0, "rolling_3d": [], "rolling_5d": []}

    entries = []
    with open(memory_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not entries:
        return {"total_experiments": 0, "rolling_3d": [], "rolling_5d": []}

    # Only keep judged experiments (have champion + challenger metrics)
    judged = [e for e in entries if e.get("phase") == "judge"]

    # Build compact summaries
    def _summarize(entry: dict) -> dict:
        patch = entry.get("patch", {})
        decision = entry.get("decision", {})
        return {
            "ts": entry.get("timestamp", ""),
            "summary": patch.get("summary", "no summary"),
            "patch_type": patch.get("patch_type", "unknown"),
            "accepted": decision.get("accepted", False),
            "reason_short": (decision.get("reason", "")[:120]
                             if decision.get("reason") else ""),
        }

    recent = judged[-last_n:]
    rolling_3d = recent[-3:] if len(recent) >= 3 else recent
    rolling_5d = recent[-5:] if len(recent) >= 5 else recent

    return {
        "total_experiments": len(judged),
        "total_accepted": sum(1 for e in judged
                              if e.get("decision", {}).get("accepted")),
        "rolling_3d": [_summarize(e) for e in rolling_3d],
        "rolling_5d": [_summarize(e) for e in rolling_5d],
    }


def _get_divergence_family_counts(diagnostics: dict) -> dict:
    """Extract primary/secondary/tertiary divergence contribution counts.

    Reads from the feature column list in diagnostics (built by nightly_train)
    and classifies each divergence-related column by its priority tier.
    """
    from divergence_features import PHASE1_METRICS, PHASE2_METRICS

    # Build base → tier map
    base_tier = {}
    for _, _, out_col, tier in PHASE1_METRICS:
        base_tier[out_col] = tier
    for _, _, out_col, tier in PHASE2_METRICS:
        base_tier[out_col] = tier

    # Get column lists from diagnostics.
    # zdiv_columns includes ALL zdiv_* cols (including object-type _state);
    # feature_columns only has numeric cols. Merge both for accurate counts.
    all_cols = list(set(
        diagnostics.get("feature_columns", [])
        + diagnostics.get("zdiv_columns", [])
    ))

    counts = {"primary": 0, "secondary": 0, "tertiary": 0}
    base_counts = {"primary": 0, "secondary": 0, "tertiary": 0}

    for col in all_cols:
        # Check if it's a base divergence metric
        if col in base_tier:
            tier = base_tier[col]
            base_counts[tier] += 1
            counts[tier] += 1
            continue
        # Check if it's a derived column (e.g. zdiv_nope_state, zdiv_gex_widening)
        # Match the LONGEST prefix to avoid zdiv_gex matching before zdiv_gex_normalized
        best_base = None
        best_tier = None
        for base, tier in base_tier.items():
            if col.startswith(base + '_'):
                if best_base is None or len(base) > len(best_base):
                    best_base = base
                    best_tier = tier
        if best_tier:
            counts[best_tier] += 1

    total = sum(counts.values())
    result = {}
    for tier_name in ["primary", "secondary", "tertiary"]:
        pct = (counts[tier_name] / total * 100) if total > 0 else 0
        result[tier_name] = {
            "base_metrics": base_counts[tier_name],
            "total_columns": counts[tier_name],
            "pct_of_pool": round(pct, 1),
        }
    result["total_divergence_columns"] = total

    return result


def _compact_rule(rule: dict) -> dict:
    """Compact a rule dict for LLM context (keep it small)."""
    return {
        "name": rule.get("name", ""),
        "direction": rule.get("direction", ""),
        "family": rule.get("source_family", ""),
        "horizon": rule.get("horizon_min", 0),
        "support": rule.get("support", 0),
        "days": rule.get("distinct_days", 0),
        "win_rate": rule.get("win_rate", 0),
        "net_exp_usd": rule.get("mes_net_expectancy_usd", 0),
        "wf_stability": rule.get("wf_stability", 0),
        "composite": rule.get("composite_score", 0),
        "conditions": rule.get("conditions_english",
                               [p.get("feature", "") for p in rule.get("predicates", [])]),
    }


def package_from_artifacts(artifacts_dir: Path = ARTIFACTS_DIR) -> dict:
    """Convenience: load artifacts from disk and package them."""
    # Load diagnostics
    diag_path = artifacts_dir / "diagnostics.json"
    diagnostics = {}
    if diag_path.exists():
        with open(diag_path) as f:
            diagnostics = json.load(f)

    # Load accepted rules
    rules_path = artifacts_dir / "accepted_rules.json"
    accepted = []
    if rules_path.exists():
        with open(rules_path) as f:
            accepted = json.load(f)

    # Load nightly report
    report_path = artifacts_dir / "nightly_report.json"
    report = None
    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)

    hypothesis = load_hypothesis()

    return package_diagnostics(diagnostics, accepted, hypothesis, report)


def format_proposer_context(package: dict) -> str:
    """Format the diagnostics package as a compact text block for the proposer prompt."""
    return json.dumps(package, indent=2, default=str)


def format_critic_context(package: dict, patch: dict) -> str:
    """Format diagnostics + proposed patch for the critic prompt."""
    context = {
        "diagnostics": package,
        "proposed_patch": patch,
    }
    return json.dumps(context, indent=2, default=str)
