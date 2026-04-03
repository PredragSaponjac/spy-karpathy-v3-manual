"""
AUTO-GENERATED LIVE RULEBOOK
Do not edit manually — regenerated nightly by Karpathy autoresearch.
"""

RULES = [
    {"name": "D_zdiv_nope_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_nope_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 93.386, "support": 208, "win_rate": 0.6635, "mes_net_expectancy_usd": 56.3, "mes_median_mfe_pts": 53.87, "mes_median_mae_pts": 6.88, "wf_stability": 0.875, "neighbor_robust": true},
    {"name": "L_atm_straddle_pct_high_LONG_30m", "direction": "LONG", "horizon_min": 30, "conditions": [{"feature": "atm_straddle_pct", "op": "gt", "value": 0.8, "value_hi": null}], "composite_score": 76.8976, "support": 535, "win_rate": 0.757, "mes_net_expectancy_usd": 90.79, "mes_median_mfe_pts": 29.91, "mes_median_mae_pts": 7.59, "wf_stability": 0.5714, "neighbor_robust": true},
    {"name": "I_iv_slope_q5_Q0_div_gex_lt_SHORT_30m", "direction": "SHORT", "horizon_min": 30, "conditions": [{"feature": "iv_slope_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "div_gex", "op": "lt", "value": -792050958.7438127, "value_hi": null}], "composite_score": 72.2013, "support": 2287, "win_rate": 0.3808, "mes_net_expectancy_usd": -13.01, "mes_median_mfe_pts": 104.47, "mes_median_mae_pts": 11.37, "wf_stability": 0.25, "neighbor_robust": true},
    {"name": "D_zdiv_net_prem_high_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "zdiv_net_prem_state", "op": "eq", "value": "strong_pos", "value_hi": null}], "composite_score": 61.5183, "support": 218, "win_rate": 0.4633, "mes_net_expectancy_usd": 5.18, "mes_median_mfe_pts": 54.86, "mes_median_mae_pts": 15.9, "wf_stability": 0.75, "neighbor_robust": true},
    {"name": "I_gex_normalized_gt_atm_avg_iv_q5_Q0_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "gex_normalized", "op": "gt", "value": -0.00413235, "value_hi": null}, {"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}], "composite_score": 53.9793, "support": 5333, "win_rate": 0.7242, "mes_net_expectancy_usd": 61.97, "mes_median_mfe_pts": 26.65, "mes_median_mae_pts": 5.94, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m", "direction": "SHORT", "horizon_min": 60, "conditions": [{"feature": "atm_avg_iv_q5", "op": "eq", "value": 0, "value_hi": null}, {"feature": "trin", "op": "gt", "value": 0.87, "value_hi": null}], "composite_score": 52.2148, "support": 6074, "win_rate": 0.8242, "mes_net_expectancy_usd": 67.27, "mes_median_mfe_pts": 19.0, "mes_median_mae_pts": 7.78, "wf_stability": 1.0, "neighbor_robust": true},
    {"name": "SKIP_midday_chop_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "pct_of_day", "op": "between", "value": 0.25, "value_hi": 0.55}, {"feature": "efficiency_ratio", "op": "lt", "value": 0.25, "value_hi": null}], "composite_score": 19.0649, "support": 6160, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.875, "neighbor_robust": true},
    {"name": "SKIP_weak_gate_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "structural_gate", "op": "lt", "value": 0.2, "value_hi": null}], "composite_score": 17.5472, "support": 831, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.625, "neighbor_robust": true},
    {"name": "SKIP_low_efficiency_15m", "direction": "SKIP", "horizon_min": 15, "conditions": [{"feature": "efficiency_ratio", "op": "lt", "value": 0.15, "value_hi": null}], "composite_score": 13.3188, "support": 12795, "win_rate": 0.0, "mes_net_expectancy_usd": 0.0, "mes_median_mfe_pts": 0.0, "mes_median_mae_pts": 0.0, "wf_stability": 0.625, "neighbor_robust": true},
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
