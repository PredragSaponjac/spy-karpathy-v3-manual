"""
AUTO-GENERATED LIVE RULEBOOK
Do not edit manually — regenerated nightly by Karpathy autoresearch.
"""

RULES = [
    {"name": "D_zdiv_nope_high_SHORT_30m", "direction": "SHORT", "horizon_min": 30, "conditions": [{"feature": "zdiv_nope_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 77.9824, "support": 130, "win_rate": 0.7846, "mes_net_expectancy_usd": 54.93, "mes_median_mfe_pts": 23.73, "mes_median_mae_pts": 3.95, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "L_otm_put_pct_low_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "otm_put_pct", "op": "lt", "value": 0.2, "value_hi": null}], "composite_score": 63.3111, "support": 75, "win_rate": 0.7867, "mes_net_expectancy_usd": 158.28, "mes_median_mfe_pts": 5.27, "mes_median_mae_pts": 43.25, "wf_stability": 0.6667, "neighbor_robust": true},
    {"name": "D_zdiv_net_prem_high_SHORT_15m", "direction": "SHORT", "horizon_min": 15, "conditions": [{"feature": "zdiv_net_prem_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 56.2344, "support": 149, "win_rate": 0.6309, "mes_net_expectancy_usd": 64.95, "mes_median_mfe_pts": 12.19, "mes_median_mae_pts": 6.68, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "trin", "op": "gt", "value": 0.86, "value_hi": null}], "composite_score": 55.8887, "support": 5011, "win_rate": 0.8835, "mes_net_expectancy_usd": 68.51, "mes_median_mfe_pts": 20.37, "mes_median_mae_pts": 9.89, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "spot_vs_poc", "op": "gt", "value": -0.1195868855423787, "value_hi": null}], "composite_score": 53.0209, "support": 5774, "win_rate": 0.7719, "mes_net_expectancy_usd": 44.44, "mes_median_mfe_pts": 22.83, "mes_median_mae_pts": 13.85, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "D_zdiv_gex_normalized_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_gex_normalized_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 50.7832, "support": 2714, "win_rate": 0.6164, "mes_net_expectancy_usd": 30.57, "mes_median_mfe_pts": 25.3, "mes_median_mae_pts": 13.18, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "SKIP_midday_chop_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "pct_of_day", "op": "between", "value": 0.25, "value_hi": 0.55}, {"feature": "efficiency_ratio", "op": "lt", "value": 0.25, "value_hi": null}], "composite_score": 20.0118, "support": 5253, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "SKIP_weak_gate_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "structural_gate", "op": "lt", "value": 0.2, "value_hi": null}], "composite_score": 16.0083, "support": 746, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.5, "neighbor_robust": true},
    {"name": "SKIP_low_efficiency_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "efficiency_ratio", "op": "lt", "value": 0.15, "value_hi": null}], "composite_score": 14.1317, "support": 11365, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6667, "neighbor_robust": true},
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
