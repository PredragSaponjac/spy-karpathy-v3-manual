"""
AUTO-GENERATED LIVE RULEBOOK
Do not edit manually — regenerated nightly by Karpathy autoresearch.
"""

RULES = [
    {"name": "D_zdiv_nope_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_nope_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 91.38, "support": 237, "win_rate": 0.6498, "mes_net_expectancy_usd": 51.96, "mes_median_mfe_pts": 51.05, "mes_median_mae_pts": 7.75, "wf_stability": 0.8, "neighbor_robust": true},
    {"name": "L_atm_straddle_pct_high_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "atm_straddle_pct", "op": "gt", "value": 0.8, "value_hi": null}], "composite_score": 74.706, "support": 647, "win_rate": 0.6569, "mes_net_expectancy_usd": 69.82, "mes_median_mfe_pts": 44.29, "mes_median_mae_pts": 18.15, "wf_stability": 0.5, "neighbor_robust": true},
    {"name": "D_zdiv_vex_low_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "zdiv_vex_state", "op": "eq", "value": "strong_neg", "value_hi": null}], "composite_score": 57.0766, "support": 2200, "win_rate": 0.5405, "mes_net_expectancy_usd": 20.84, "mes_median_mfe_pts": 23.26, "mes_median_mae_pts": 14.0, "wf_stability": 0.7273, "neighbor_robust": true},
    {"name": "D_zdiv_net_prem_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_net_prem_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 50.4395, "support": 258, "win_rate": 0.4535, "mes_net_expectancy_usd": 0.5, "mes_median_mfe_pts": 39.81, "mes_median_mae_pts": 16.33, "wf_stability": 0.7, "neighbor_robust": true},
    {"name": "I_atm_avg_iv_q5_Q0_qqq_nope_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "qqq_nope", "op": "gt", "value": -35.50294078657242, "value_hi": null}], "composite_score": 44.9965, "support": 8169, "win_rate": 0.6619, "mes_net_expectancy_usd": 38.95, "mes_median_mfe_pts": 21.63, "mes_median_mae_pts": 8.01, "wf_stability": 0.875, "neighbor_robust": true},
    {"name": "I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "trin", "op": "gt", "value": 0.89, "value_hi": null}], "composite_score": 43.9243, "support": 5936, "win_rate": 0.7394, "mes_net_expectancy_usd": 60.76, "mes_median_mfe_pts": 16.86, "mes_median_mae_pts": 8.84, "wf_stability": 0.75, "neighbor_robust": true},
    {"name": "SKIP_midday_chop_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "pct_of_day", "op": "between", "value": 0.25, "value_hi": 0.55}, {"feature": "efficiency_ratio", "op": "lt", "value": 0.25, "value_hi": null}], "composite_score": 30.2164, "support": 7821, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.8182, "neighbor_robust": true},
    {"name": "SKIP_weak_gate_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "structural_gate", "op": "lt", "value": 0.2, "value_hi": null}], "composite_score": 27.7152, "support": 1029, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6364, "neighbor_robust": true},
    {"name": "SKIP_low_efficiency_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "efficiency_ratio", "op": "lt", "value": 0.15, "value_hi": null}], "composite_score": 21.2253, "support": 16147, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6364, "neighbor_robust": true},
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
