# Karpathy Nightly Execution Report
**Generated:** 2026-03-27 15:20:21  
**Elapsed:** 9214.8s  
**Maturity:** PRELIMINARY — 2-fold walk-forward validated (8 days)  

## Challenger Summary
- Attempts: **3**
- Accepted: **1**
- Rejected: **2**

## Top LONG Rules
- **I_tick_q5_Q0_qqq_atm_avg_iv_gt_LONG_60m** — $-5.85/MES, WF 1.00, composite 36.0533

## Top SHORT Rules
- **I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m** — $63.88/MES, WF 1.00, composite 48.1223
- **I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m** — $42.11/MES, WF 1.00, composite 45.3076
- **D_zdiv_gex_normalized_high_SHORT_60m** — $22.17/MES, WF 1.00, composite 37.2065

## Top SKIP Rules
- **SKIP_midday_chop_30m** — composite 20.4220, support 4348
- **SKIP_weak_gate_30m** — composite 15.2418, support 563
- **SKIP_low_efficiency_15m** — composite 11.1889, support 9450

## /MES Expectancy (1 contract)
- Mean net expectancy: **$32.87**
- Best: $63.88 / Worst: $-5.85

## Divergence Family Contributions
- **PRIMARY**: 5 base, 43 total columns (33.9%)
- **SECONDARY**: 7 base, 49 total columns (38.6%)
- **TERTIARY**: 5 base, 35 total columns (27.6%)
- Total divergence columns: **127**

## LLM Spend
- Total: **$0.7835**
- Proposer calls: 3
- Critic calls: 3
- Remaining: $29.22 of $30.00 hard cap
