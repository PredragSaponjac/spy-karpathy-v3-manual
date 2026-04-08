# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-04-08 06:15
**Trading instrument:** 1 /MES contract
**Maturity tier:** LIVE — walk-forward validated

## Data Summary
- Snapshots: 55,955
- Trading days: 14
- Features: 780
- Candidates evaluated: 6,297
- Rules promoted: 9

## Assumptions
- /MES reference price: 6590 (live SPY spot 659.00 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## LONG Patterns (3)

### L_atm_straddle_pct_high_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** LOW

**Conditions:**
- atm_straddle_pct > 0.8

| Metric | Value |
|--------|-------|
| Sample size | 640 snapshots across 11 day(s) |
| Win rate | 66.4% |
| Historically median favorable move | 43.5 pts ($217) |
| Typical adverse excursion | 17.5 pts ($87) |
| Estimated net expectancy (1 /MES) | **$71.08** per trade |
| Walk-forward stability | 56% (5/9 folds) |

**Suggested stop:** 26.2 pts (105 ticks, $131)
**Suggested target range:** 26.1–43.5 pts ($130–$217)

### D_zdiv_vex_low_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_vex_state = strong_neg

| Metric | Value |
|--------|-------|
| Sample size | 2020 snapshots across 13 day(s) |
| Win rate | 52.5% |
| Historically median favorable move | 21.2 pts ($106) |
| Typical adverse excursion | 14.1 pts ($71) |
| Estimated net expectancy (1 /MES) | **$20.80** per trade |
| Walk-forward stability | 70% (7/10 folds) |

**Suggested stop:** 21.2 pts (85 ticks, $106)
**Suggested target range:** 12.7–21.2 pts ($64–$106)

### L_qqq_expected_move_pct_high_LONG_30m
**Direction:** LONG | **Horizon:** 30m | **Confidence:** MODERATE

**Conditions:**
- qqq_expected_move_pct > 0.8

| Metric | Value |
|--------|-------|
| Sample size | 3005 snapshots across 11 day(s) |
| Win rate | 61.7% |
| Historically median favorable move | 25.3 pts ($127) |
| Typical adverse excursion | 11.2 pts ($56) |
| Estimated net expectancy (1 /MES) | **$37.23** per trade |
| Walk-forward stability | 67% (6/9 folds) |

**Suggested stop:** 16.9 pts (67 ticks, $84)
**Suggested target range:** 15.2–25.3 pts ($76–$127)

## SHORT Patterns (3)

### D_zdiv_nope_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_nope_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 223 snapshots across 13 day(s) |
| Win rate | 65.5% |
| Historically median favorable move | 53.5 pts ($267) |
| Typical adverse excursion | 7.0 pts ($35) |
| Estimated net expectancy (1 /MES) | **$51.89** per trade |
| Walk-forward stability | 78% (7/9 folds) |

**Suggested stop:** 10.4 pts (42 ticks, $52)
**Suggested target range:** 32.1–53.5 pts ($160–$267)

### D_zdiv_net_prem_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_net_prem_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 244 snapshots across 13 day(s) |
| Win rate | 44.7% |
| Historically median favorable move | 49.8 pts ($249) |
| Typical adverse excursion | 15.9 pts ($79) |
| Estimated net expectancy (1 /MES) | **$-1.29** per trade |
| Walk-forward stability | 67% (6/9 folds) |

**Suggested stop:** 23.8 pts (95 ticks, $119)
**Suggested target range:** 29.9–49.8 pts ($149–$249)

### I_atm_avg_iv_q5_Q0_qqq_nope_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- qqq_nope > -36.52

| Metric | Value |
|--------|-------|
| Sample size | 8294 snapshots across 11 day(s) |
| Win rate | 66.0% |
| Historically median favorable move | 21.0 pts ($105) |
| Typical adverse excursion | 7.8 pts ($39) |
| Estimated net expectancy (1 /MES) | **$37.16** per trade |
| Walk-forward stability | 88% (7/8 folds) |

**Suggested stop:** 11.7 pts (47 ticks, $59)
**Suggested target range:** 12.6–21.0 pts ($63–$105)

## SKIP Conditions (3)
*When these conditions are active, avoid new entries.*

### SKIP_midday_chop_15m
**When active:** Avoid new entries

**Conditions:**
- 0.25 <= pct_of_day <= 0.55
- efficiency_ratio < 0.25

- Historically, forward moves in this state average 10.13% with no clear direction
- Sample: 7203 snapshots

### SKIP_weak_gate_15m
**When active:** Avoid new entries

**Conditions:**
- structural_gate < 0.2

- Historically, forward moves in this state average 11.46% with no clear direction
- Sample: 972 snapshots

### SKIP_low_efficiency_15m
**When active:** Avoid new entries

**Conditions:**
- efficiency_ratio < 0.15

- Historically, forward moves in this state average 11.79% with no clear direction
- Sample: 14975 snapshots

---
*All figures are historically observed medians, not guarantees.*
*Past patterns may not repeat. Use position sizing and risk management.*