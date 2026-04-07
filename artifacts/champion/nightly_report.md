# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-04-06 20:17
**Trading instrument:** 1 /MES contract
**Maturity tier:** LIVE — walk-forward validated

## Data Summary
- Snapshots: 51,802
- Trading days: 13
- Features: 780
- Candidates evaluated: 6,297
- Rules promoted: 9

## Assumptions
- /MES reference price: 6586 (live SPY spot 658.58 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## LONG Patterns (2)

### L_atm_straddle_pct_high_LONG_30m
**Direction:** LONG | **Horizon:** 30m | **Confidence:** LOW

**Conditions:**
- atm_straddle_pct > 0.8

| Metric | Value |
|--------|-------|
| Sample size | 638 snapshots across 10 day(s) |
| Win rate | 68.2% |
| Historically median favorable move | 28.4 pts ($142) |
| Typical adverse excursion | 9.2 pts ($46) |
| Estimated net expectancy (1 /MES) | **$70.63** per trade |
| Walk-forward stability | 50% (4/8 folds) |

**Suggested stop:** 13.8 pts (55 ticks, $69)
**Suggested target range:** 17.0–28.4 pts ($85–$142)

### D_zdiv_vex_low_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_vex_state = strong_neg

| Metric | Value |
|--------|-------|
| Sample size | 1759 snapshots across 12 day(s) |
| Win rate | 47.9% |
| Historically median favorable move | 21.8 pts ($109) |
| Typical adverse excursion | 14.0 pts ($70) |
| Estimated net expectancy (1 /MES) | **$18.39** per trade |
| Walk-forward stability | 67% (6/9 folds) |

**Suggested stop:** 21.0 pts (84 ticks, $105)
**Suggested target range:** 13.1–21.8 pts ($65–$109)

## SHORT Patterns (4)

### D_zdiv_nope_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_nope_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 223 snapshots across 12 day(s) |
| Win rate | 65.5% |
| Historically median favorable move | 53.7 pts ($269) |
| Typical adverse excursion | 7.4 pts ($37) |
| Estimated net expectancy (1 /MES) | **$51.85** per trade |
| Walk-forward stability | 78% (7/9 folds) |

**Suggested stop:** 11.1 pts (44 ticks, $55)
**Suggested target range:** 32.2–53.7 pts ($161–$269)

### D_zdiv_net_prem_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_net_prem_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 244 snapshots across 12 day(s) |
| Win rate | 44.7% |
| Historically median favorable move | 52.5 pts ($262) |
| Typical adverse excursion | 16.1 pts ($81) |
| Estimated net expectancy (1 /MES) | **$-1.29** per trade |
| Walk-forward stability | 67% (6/9 folds) |

**Suggested stop:** 24.2 pts (97 ticks, $121)
**Suggested target range:** 31.5–52.5 pts ($157–$262)

### I_pin_score_q5_Q0_qqq_gex_total_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- pin_score_q5 = 0
- qqq_gex_total > -8.162e+08

| Metric | Value |
|--------|-------|
| Sample size | 2194 snapshots across 10 day(s) |
| Win rate | 68.9% |
| Historically median favorable move | 46.4 pts ($232) |
| Typical adverse excursion | 7.8 pts ($39) |
| Estimated net expectancy (1 /MES) | **$24.84** per trade |
| Walk-forward stability | 75% (6/8 folds) |

**Suggested stop:** 11.7 pts (47 ticks, $59)
**Suggested target range:** 27.8–46.4 pts ($139–$232)

### I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- spot_vs_poc > -0.07464

| Metric | Value |
|--------|-------|
| Sample size | 6395 snapshots across 10 day(s) |
| Win rate | 73.8% |
| Historically median favorable move | 19.8 pts ($99) |
| Typical adverse excursion | 9.9 pts ($49) |
| Estimated net expectancy (1 /MES) | **$47.95** per trade |
| Walk-forward stability | 86% (6/7 folds) |

**Suggested stop:** 14.8 pts (59 ticks, $74)
**Suggested target range:** 11.9–19.8 pts ($59–$99)

## SKIP Conditions (3)
*When these conditions are active, avoid new entries.*

### SKIP_midday_chop_15m
**When active:** Avoid new entries

**Conditions:**
- 0.25 <= pct_of_day <= 0.55
- efficiency_ratio < 0.25

- Historically, forward moves in this state average 10.26% with no clear direction
- Sample: 6670 snapshots

### SKIP_weak_gate_15m
**When active:** Avoid new entries

**Conditions:**
- structural_gate < 0.2

- Historically, forward moves in this state average 11.19% with no clear direction
- Sample: 903 snapshots

### SKIP_low_efficiency_15m
**When active:** Avoid new entries

**Conditions:**
- efficiency_ratio < 0.15

- Historically, forward moves in this state average 11.62% with no clear direction
- Sample: 13859 snapshots

---
*All figures are historically observed medians, not guarantees.*
*Past patterns may not repeat. Use position sizing and risk management.*