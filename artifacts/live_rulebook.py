"""
AUTO-GENERATED LIVE RULEBOOK
Do not edit manually — regenerated nightly by Karpathy autoresearch.
"""

RULES = [
    {"name": "D_zdiv_nope_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_nope_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 95.2885, "support": 292, "win_rate": 0.6815, "mes_net_expectancy_usd": 54.14, "mes_median_mfe_pts": 54.78, "mes_median_mae_pts": 8.97, "wf_stability": 0.8333, "neighbor_robust": true},
    {"name": "L_atm_straddle_pct_high_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "atm_straddle_pct", "op": "gt", "value": 0.8, "value_hi": null}], "composite_score": 78.0811, "support": 651, "win_rate": 0.659, "mes_net_expectancy_usd": 74.46, "mes_median_mfe_pts": 44.81, "mes_median_mae_pts": 18.14, "wf_stability": 0.5455, "neighbor_robust": true},
    {"name": "I_breadth_composite_q5_Q0_pct_of_day_lt_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "breadth_composite_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "pct_of_day", "op": "lt", "value": 0.3625213675213675, "value_hi": null}], "composite_score": 63.1413, "support": 4339, "win_rate": 0.5444, "mes_net_expectancy_usd": 34.91, "mes_median_mfe_pts": 43.14, "mes_median_mae_pts": 8.35, "wf_stability": 0.75, "neighbor_robust": true},
    {"name": "I_nope_q5_Q0_qqq_gex_total_gt_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "nope_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "qqq_gex_total", "op": "gt", "value": -516067048.6234969, "value_hi": null}], "composite_score": 52.0735, "support": 1068, "win_rate": 0.8221, "mes_net_expectancy_usd": 53.36, "mes_median_mfe_pts": 19.86, "mes_median_mae_pts": 5.07, "wf_stability": 0.8333, "neighbor_robust": true},
    {"name": "D_zdiv_straddle_pct_high_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "zdiv_straddle_pct_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 51.313, "support": 693, "win_rate": 0.5166, "mes_net_expectancy_usd": 19.86, "mes_median_mfe_pts": 22.25, "mes_median_mae_pts": 10.96, "wf_stability": 0.6154, "neighbor_robust": true},
    {"name": "D_zdiv_vex_low_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "zdiv_vex_state", "op": "eq", "value": "strong_neg", "value_hi": null}], "composite_score": 50.4401, "support": 2636, "win_rate": 0.5273, "mes_net_expectancy_usd": 18.89, "mes_median_mfe_pts": 19.15, "mes_median_mae_pts": 13.14, "wf_stability": 0.7692, "neighbor_robust": true},
    {"name": "SKIP_midday_chop_30m", "direction": "SKIP", "horizon_min": 30, "conditions": [{"feature": "pct_of_day", "op": "between", "value": 0.25, "value_hi": 0.55}, {"feature": "efficiency_ratio", "op": "lt", "value": 0.25, "value_hi": null}], "composite_score": 29.0576, "support": 8757, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6923, "neighbor_robust": true},
    {"name": "SKIP_weak_gate_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "structural_gate", "op": "lt", "value": 0.2, "value_hi": null}], "composite_score": 28.5562, "support": 1171, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6923, "neighbor_robust": true},
    {"name": "SKIP_low_efficiency_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "efficiency_ratio", "op": "lt", "value": 0.15, "value_hi": null}], "composite_score": 21.5251, "support": 18180, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6154, "neighbor_robust": true},
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
