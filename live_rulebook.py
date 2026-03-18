"""
Karpathy Autoresearch — Live Rulebook
Machine-readable next-day rules for a live trading engine to import.
Also generates the rulebook Python file.
"""
import json
from pathlib import Path
from typing import List

from evaluator import RuleScore


def write_live_rulebook(promoted: List[RuleScore], output_path: Path):
    """Write a Python module that the live engine can import."""
    lines = [
        '"""',
        'AUTO-GENERATED LIVE RULEBOOK',
        'Do not edit manually — regenerated nightly by Karpathy autoresearch.',
        '"""',
        '',
        'RULES = [',
    ]

    for score in promoted:
        rule = score.rule
        conditions = []
        for pred in rule.predicates:
            conditions.append({
                'feature': pred.feature,
                'op': pred.op,
                'value': pred.value,
                'value_hi': pred.value_hi,
            })

        entry = {
            'name': rule.name,
            'direction': rule.direction,
            'horizon_min': rule.horizon_min,
            'conditions': conditions,
            'composite_score': round(score.composite_score, 4),
            'support': score.support,
            'win_rate': round(score.win_rate, 4),
            'mes_net_expectancy_usd': round(score.mes_net_expectancy, 2),
            'mes_median_mfe_pts': round(score.mes_median_mfe_pts, 2),
            'mes_median_mae_pts': round(score.mes_median_mae_pts, 2),
            'wf_stability': round(score.wf_stability, 4),
            'neighbor_robust': score.neighbor_robust,
        }
        lines.append(f'    {json.dumps(entry, default=str)},')

    lines.append(']')
    lines.append('')
    lines.append('')
    lines.append('def evaluate_snapshot(snapshot: dict) -> list:')
    lines.append('    """Evaluate a single snapshot dict against all rules.')
    lines.append('    Returns list of (rule_name, direction, score) for matching rules."""')
    lines.append('    matches = []')
    lines.append('    for rule in RULES:')
    lines.append('        all_match = True')
    lines.append('        for cond in rule["conditions"]:')
    lines.append('            feat = cond["feature"]')
    lines.append('            val = snapshot.get(feat)')
    lines.append('            if val is None:')
    lines.append('                all_match = False')
    lines.append('                break')
    lines.append('            op = cond["op"]')
    lines.append('            if op == "lt" and not (val < cond["value"]):')
    lines.append('                all_match = False; break')
    lines.append('            elif op == "gt" and not (val > cond["value"]):')
    lines.append('                all_match = False; break')
    lines.append('            elif op == "eq" and not (val == cond["value"]):')
    lines.append('                all_match = False; break')
    lines.append('            elif op == "between" and not (cond["value"] <= val <= cond["value_hi"]):')
    lines.append('                all_match = False; break')
    lines.append('        if all_match:')
    lines.append('            matches.append((rule["name"], rule["direction"],')
    lines.append('                           rule["composite_score"]))')
    lines.append('    return sorted(matches, key=lambda x: -x[2])')
    lines.append('')

    output_path.write_text('\n'.join(lines), encoding='utf-8')


def load_live_rules(rulebook_path: Path) -> list:
    """Load rules from the generated rulebook JSON."""
    json_path = rulebook_path.parent / 'accepted_rules.json'
    if json_path.exists():
        with open(json_path) as f:
            return json.load(f)
    return []
