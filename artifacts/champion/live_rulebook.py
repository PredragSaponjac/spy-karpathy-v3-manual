"""
AUTO-GENERATED LIVE RULEBOOK
Do not edit manually — regenerated nightly by Karpathy autoresearch.
"""

RULES = [
    {"name": "D_zdiv_nope_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_nope_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 94.3916, "support": 223, "win_rate": 0.6547, "mes_net_expectancy_usd": 51.85, "mes_median_mfe_pts": 53.7, "mes_median_mae_pts": 7.39, "wf_stability": 0.7778, "neighbor_robust": true},
    {"name": "D_zdiv_net_prem_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_net_prem_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 61.6332, "support": 244, "win_rate": 0.4467, "mes_net_expectancy_usd": -1.29, "mes_median_mfe_pts": 52.46, "mes_median_mae_pts": 16.11, "wf_stability": 0.6667, "neighbor_robust": true},
    {"name": "L_atm_straddle_pct_high_LONG_30m", "direction": "LONG", "horizon_min": 30, "conditions": [{"feature": "atm_straddle_pct", "op": "gt", "value": 0.8, "value_hi": null}], "composite_score": 61.4013, "support": 638, "win_rate": 0.6818, "mes_net_expectancy_usd": 70.63, "mes_median_mfe_pts": 28.4, "mes_median_mae_pts": 9.2, "wf_stability": 0.5, "neighbor_robust": true},
    {"name": "D_zdiv_vex_low_LONG_60m", "direction": "LONG", "horizon_min": 60, "conditions": [{"feature": "zdiv_vex_state", "op": "eq", "value": "strong_neg", "value_hi": null}], "composite_score": 52.5547, "support": 1759, "win_rate": 0.4787, "mes_net_expectancy_usd": 18.39, "mes_median_mfe_pts": 21.83, "mes_median_mae_pts": 14.03, "wf_stability": 0.6667, "neighbor_robust": true},
    {"name": "I_pin_score_q5_Q0_qqq_gex_total_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "pin_score_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "qqq_gex_total", "op": "gt", "value": -816244963.1145918, "value_hi": null}], "composite_score": 51.5198, "support": 2194, "win_rate": 0.6892, "mes_net_expectancy_usd": 24.84, "mes_median_mfe_pts": 46.35, "mes_median_mae_pts": 7.81, "wf_stability": 0.75, "neighbor_robust": true},
    {"name": "I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "spot_vs_poc", "op": "gt", "value": -0.07463709615999896, "value_hi": null}], "composite_score": 49.3465, "support": 6395, "win_rate": 0.7378, "mes_net_expectancy_usd": 47.95, "mes_median_mfe_pts": 19.79, "mes_median_mae_pts": 9.9, "wf_stability": 0.8571, "neighbor_robust": true},
    {"name": "SKIP_midday_chop_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "pct_of_day", "op": "between", "value": 0.25, "value_hi": 0.55}, {"feature": "efficiency_ratio", "op": "lt", "value": 0.25, "value_hi": null}], "composite_score": 20.0951, "support": 6670, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.8889, "neighbor_robust": true},
    {"name": "SKIP_weak_gate_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "structural_gate", "op": "lt", "value": 0.2, "value_hi": null}], "composite_score": 19.8234, "support": 903, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6667, "neighbor_robust": true},
    {"name": "SKIP_low_efficiency_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "efficiency_ratio", "op": "lt", "value": 0.15, "value_hi": null}], "composite_score": 14.1494, "support": 13859, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.5556, "neighbor_robust": true},
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
