"""
Karpathy Autoresearch — Ranking Weights (MUTABLE)

These weights control how the diagnostics packager ranks and presents
rule families to the proposer. They do NOT change the evaluator scoring
(which is frozen in evaluator.py). They only affect which families
get emphasized in the proposer's context window.

The proposer may request changes to these weights through a patch.
"""

# ── Rule Family Priority ──────────────────────────────────────────────
# Higher = more likely to appear in proposer context, more interaction slots
RULE_FAMILY_PRIORITY = {
    "level":       1.0,
    "interaction": 1.0,
    "divergence":  1.2,   # slight boost for intermarket
    "sequence":    1.1,   # slight boost for temporal
    "skip":        1.0,
}

# ── Reporting Emphasis ────────────────────────────────────────────────
# Controls how much weight each metric gets in the summary rankings
# presented to the proposer LLM (not the evaluator)
REPORTING_WEIGHTS = {
    "net_expectancy":    0.35,
    "wf_stability":      0.25,
    "support_breadth":   0.15,   # distinct days relative to total
    "simplicity":        0.10,   # fewer predicates = higher
    "intermarket_value": 0.15,   # bonus for rules using QQQ features
}

# ── Family Performance Tracking ───────────────────────────────────────
# Running averages of how each family has performed across nights
# Updated automatically by karpathy_runner after each experiment
FAMILY_TRACK_RECORD = {
    "level":       {"promoted": 0, "rejected": 0, "avg_composite": 0.0},
    "interaction": {"promoted": 0, "rejected": 0, "avg_composite": 0.0},
    "divergence":  {"promoted": 0, "rejected": 0, "avg_composite": 0.0},
    "sequence":    {"promoted": 0, "rejected": 0, "avg_composite": 0.0},
    "skip":        {"promoted": 0, "rejected": 0, "avg_composite": 0.0},
}


def compute_family_summary(promoted_rules: list) -> dict:
    """Compute per-family performance from a list of promoted RuleScore dicts."""
    families = {}
    for rule in promoted_rules:
        fam = rule.get("source_family", "unknown")
        if fam not in families:
            families[fam] = {
                "count": 0,
                "total_composite": 0.0,
                "total_net_expectancy": 0.0,
                "directions": {"LONG": 0, "SHORT": 0, "SKIP": 0},
            }
        families[fam]["count"] += 1
        families[fam]["total_composite"] += rule.get("composite_score", 0.0)
        families[fam]["total_net_expectancy"] += rule.get("mes_net_expectancy_usd", 0.0)
        d = rule.get("direction", "LONG")
        if d in families[fam]["directions"]:
            families[fam]["directions"][d] += 1

    # Compute averages
    for fam, stats in families.items():
        n = stats["count"]
        stats["avg_composite"] = stats["total_composite"] / n if n else 0.0
        stats["avg_net_expectancy"] = stats["total_net_expectancy"] / n if n else 0.0

    return families
