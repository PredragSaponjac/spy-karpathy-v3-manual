"""
AUTO-GENERATED LIVE RULEBOOK
Do not edit manually — regenerated nightly by Karpathy autoresearch.
"""

RULES = [
    {"name": "L_otm_put_pct_low_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "otm_put_pct", "op": "lt", "value": 0.2, "value_hi": null}], "composite_score": 105.6988, "support": 66, "win_rate": 0.7727, "mes_net_expectancy_usd": 162.71, "mes_median_mfe_pts": 27.68, "mes_median_mae_pts": 3.23, "wf_stability": 0.6, "neighbor_robust": true},
    {"name": "D_zdiv_nope_high_SHORT_30m", "direction": "SHORT", "horizon_min": 30, "conditions": [{"feature": "zdiv_nope_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 81.3937, "support": 122, "win_rate": 0.7705, "mes_net_expectancy_usd": 47.43, "mes_median_mfe_pts": 36.68, "mes_median_mae_pts": 3.02, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "D_zdiv_net_prem_high_SHORT_15m", "direction": "SHORT", "horizon_min": 15, "conditions": [{"feature": "zdiv_net_prem_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 53.8967, "support": 144, "win_rate": 0.6181, "mes_net_expectancy_usd": 62.82, "mes_median_mfe_pts": 11.5, "mes_median_mae_pts": 6.94, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "trin", "op": "gt", "value": 0.85, "value_hi": null}], "composite_score": 52.6355, "support": 4915, "win_rate": 0.8783, "mes_net_expectancy_usd": 65.08, "mes_median_mfe_pts": 17.99, "mes_median_mae_pts": 7.92, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "spot_vs_poc", "op": "gt", "value": -0.136618174721129, "value_hi": null}], "composite_score": 50.4051, "support": 6071, "win_rate": 0.763, "mes_net_expectancy_usd": 42.7, "mes_median_mfe_pts": 22.35, "mes_median_mae_pts": 14.14, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "D_zdiv_gex_normalized_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_gex_normalized_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 43.5892, "support": 2489, "win_rate": 0.5986, "mes_net_expectancy_usd": 26.07, "mes_median_mfe_pts": 21.78, "mes_median_mae_pts": 13.87, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "SKIP_midday_chop_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "pct_of_day", "op": "between", "value": 0.25, "value_hi": 0.55}, {"feature": "efficiency_ratio", "op": "lt", "value": 0.25, "value_hi": null}], "composite_score": 19.6241, "support": 4911, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "SKIP_weak_gate_30m", "direction": "SKIP", "horizon_min": 30, "conditions": [{"feature": "structural_gate", "op": "lt", "value": 0.2, "value_hi": null}], "composite_score": 14.2544, "support": 603, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6, "neighbor_robust": true},
    {"name": "SKIP_low_efficiency_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "efficiency_ratio", "op": "lt", "value": 0.15, "value_hi": null}], "composite_score": 12.4572, "support": 10492, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.6, "neighbor_robust": true},
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
