"""
AUTO-GENERATED LIVE RULEBOOK
Do not edit manually — regenerated nightly by Karpathy autoresearch.
"""

RULES = [
]


def evaluate_snapshot(snapshot: dict) -> list:
    """Evaluate a single snapshot dict against all rules.
    Returns list of (rule_name, direction, score) for matching rules."""
    matches = []
    for rule in RULES:
        all_match = True
        for cond in rule["conditions"]:
            feat = cond["feature"]
            val = snapshot.get(feat)
            if val is None:
                all_match = False
                break
            op = cond["op"]
            if op == "lt" and not (val < cond["value"]):
                all_match = False; break
            elif op == "gt" and not (val > cond["value"]):
                all_match = False; break
            elif op == "eq" and not (val == cond["value"]):
                all_match = False; break
            elif op == "between" and not (cond["value"] <= val <= cond["value_hi"]):
                all_match = False; break
        if all_match:
            matches.append((rule["name"], rule["direction"],
                           rule["composite_score"]))
    return sorted(matches, key=lambda x: -x[2])
