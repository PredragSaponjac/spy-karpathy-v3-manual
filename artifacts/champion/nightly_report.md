# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-04-11 04:45
**Trading instrument:** 1 /MES contract
**Maturity tier:** LIVE — walk-forward validated

## Data Summary
- Snapshots: 68,102
- Trading days: 17
- Features: 785
- Candidates evaluated: 6,297
- Rules promoted: 9

## Assumptions
- /MES reference price: 6793 (live SPY spot 679.27 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## LONG Patterns (5)

### L_atm_straddle_pct_high_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** LOW

**Conditions:**
- atm_straddle_pct > 0.8

| Metric | Value |
|--------|-------|
| Sample size | 651 snapshots across 13 day(s) |
| Win rate | 65.9% |
| Historically median favorable move | 44.8 pts ($224) |
| Typical adverse excursion | 18.1 pts ($91) |
| Estimated net expectancy (1 /MES) | **$74.46** per trade |
| Walk-forward stability | 55% (6/11 folds) |

**Suggested stop:** 27.2 pts (109 ticks, $136)
**Suggested target range:** 26.9–44.8 pts ($134–$224)

### I_breadth_composite_q5_Q0_pct_of_day_lt_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- breadth_composite_q5 = 0
- pct_of_day < 0.3625

| Metric | Value |
|--------|-------|
| Sample size | 4339 snapshots across 11 day(s) |
| Win rate | 54.4% |
| Historically median favorable move | 43.1 pts ($216) |
| Typical adverse excursion | 8.3 pts ($42) |
| Estimated net expectancy (1 /MES) | **$34.91** per trade |
| Walk-forward stability | 75% (6/8 folds) |

**Suggested stop:** 12.5 pts (50 ticks, $63)
**Suggested target range:** 25.9–43.1 pts ($129–$216)

### I_nope_q5_Q0_qqq_gex_total_gt_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- nope_q5 = 0
- qqq_gex_total > -5.161e+08

| Metric | Value |
|--------|-------|
| Sample size | 1068 snapshots across 6 day(s) |
| Win rate | 82.2% |
| Historically median favorable move | 19.9 pts ($99) |
| Typical adverse excursion | 5.1 pts ($25) |
| Estimated net expectancy (1 /MES) | **$53.36** per trade |
| Walk-forward stability | 83% (5/6 folds) |

**Suggested stop:** 7.6 pts (30 ticks, $38)
**Suggested target range:** 11.9–19.9 pts ($60–$99)

### D_zdiv_straddle_pct_high_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_straddle_pct_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 693 snapshots across 16 day(s) |
| Win rate | 51.7% |
| Historically median favorable move | 22.2 pts ($111) |
| Typical adverse excursion | 11.0 pts ($55) |
| Estimated net expectancy (1 /MES) | **$19.86** per trade |
| Walk-forward stability | 62% (8/13 folds) |

**Suggested stop:** 16.4 pts (66 ticks, $82)
**Suggested target range:** 13.3–22.2 pts ($67–$111)

### D_zdiv_vex_low_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_vex_state = strong_neg

| Metric | Value |
|--------|-------|
| Sample size | 2636 snapshots across 16 day(s) |
| Win rate | 52.7% |
| Historically median favorable move | 19.2 pts ($96) |
| Typical adverse excursion | 13.1 pts ($66) |
| Estimated net expectancy (1 /MES) | **$18.89** per trade |
| Walk-forward stability | 77% (10/13 folds) |

**Suggested stop:** 19.7 pts (79 ticks, $99)
**Suggested target range:** 11.5–19.2 pts ($57–$96)

## SHORT Patterns (1)

### D_zdiv_nope_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- zdiv_nope_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 292 snapshots across 16 day(s) |
| Win rate | 68.2% |
| Historically median favorable move | 54.8 pts ($274) |
| Typical adverse excursion | 9.0 pts ($45) |
| Estimated net expectancy (1 /MES) | **$54.14** per trade |
| Walk-forward stability | 83% (10/12 folds) |

**Suggested stop:** 13.5 pts (54 ticks, $67)
**Suggested target range:** 32.9–54.8 pts ($164–$274)

## SKIP Conditions (3)
*When these conditions are active, avoid new entries.*

### SKIP_midday_chop_30m
**When active:** Avoid new entries

**Conditions:**
- 0.25 <= pct_of_day <= 0.55
- efficiency_ratio < 0.25

- Historically, forward moves in this state average 12.38% with no clear direction
- Sample: 8757 snapshots

### SKIP_weak_gate_15m
**When active:** Avoid new entries

**Conditions:**
- structural_gate < 0.2

- Historically, forward moves in this state average 10.80% with no clear direction
- Sample: 1171 snapshots

### SKIP_low_efficiency_15m
**When active:** Avoid new entries

**Conditions:**
- efficiency_ratio < 0.15

- Historically, forward moves in this state average 11.15% with no clear direction
- Sample: 18180 snapshots

---
*All figures are historically observed medians, not guarantees.*
*Past patterns may not repeat. Use position sizing and risk management.*