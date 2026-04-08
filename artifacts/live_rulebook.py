"""
AUTO-GENERATED LIVE RULEBOOK
Do not edit manually — regenerated nightly by Karpathy autoresearch.
"""

RULES = [
    {"name": "D_zdiv_nope_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_nope_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 94.4135, "support": 223, "win_rate": 0.6547, "mes_net_expectancy_usd": 51.89, "mes_median_mfe_pts": 53.49, "mes_median_mae_pts": 6.97, "wf_stability": 0.7778, "neighbor_robust": true},
    {"name": "L_atm_straddle_pct_high_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "atm_straddle_pct", "op": "gt", "value": 0.8, "value_hi": null}], "composite_score": 76.6464, "support": 640, "win_rate": 0.6641, "mes_net_expectancy_usd": 71.08, "mes_median_mfe_pts": 43.47, "mes_median_mae_pts": 17.48, "wf_stability": 0.5556, "neighbor_robust": true},
    {"name": "D_zdiv_net_prem_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_net_prem_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 59.0708, "support": 244, "win_rate": 0.4467, "mes_net_expectancy_usd": -1.29, "mes_median_mfe_pts": 49.78, "mes_median_mae_pts": 15.87, "wf_stability": 0.6667, "neighbor_robust": true},
    {"name": "D_zdiv_vex_low_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "zdiv_vex_state", "op": "eq", "value": "strong_neg", "value_hi": null}], "composite_score": 55.3543, "support": 2020, "win_rate": 0.5248, "mes_net_expectancy_usd": 20.8, "mes_median_mfe_pts": 21.25, "mes_median_mae_pts": 14.13, "wf_stability": 0.7, "neighbor_robust": true},
    {"name": "L_qqq_expected_move_pct_high_LONG_30m", "direction": "LONG", "horizon_min": 30, "conditions": [{"feature": "qqq_expected_move_pct", "op": "gt", "value": 0.8, "value_hi": null}], "composite_score": 45.693, "support": 3005, "win_rate": 0.617, "mes_net_expectancy_usd": 37.23, "mes_median_mfe_pts": 25.3, "mes_median_mae_pts": 11.25, "wf_stability": 0.6667, "neighbor_robust": true},
    {"name": "I_atm_avg_iv_q5_Q0_qqq_nope_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "qqq_nope", "op": "gt", "value": -36.52092468399469, "value_hi": null}], "composite_score": 43.2885, "support": 8294, "win_rate": 0.6595, "mes_net_expectancy_usd": 37.16, "mes_median_mfe_pts": 21.02, "mes_median_mae_pts": 7.82, "wf_stability": 0.875, "neighbor_robust": true},
    {"name": "SKIP_midday_chop_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "pct_of_day", "op": "between", "value": 0.25, "value_hi": 0.55}, {"feature": "efficiency_ratio", "op": "lt", "value": 0.25, "value_hi": null}], "composite_score": 20.1351, "support": 7203, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.8, "neighbor_robust": true},
    {"name": "SKIP_weak_gate_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "structural_gate", "op": "lt", "value": 0.2, "value_hi": null}], "composite_score": 19.3391, "support": 972, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.7, "neighbor_robust": true},
    {"name": "SKIP_low_efficiency_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "efficiency_ratio", "op": "lt", "value": 0.15, "value_hi": null}], "composite_score": 14.1516, "support": 14975, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6, "neighbor_robust": true},
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
