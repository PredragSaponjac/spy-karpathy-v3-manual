# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-03-31 19:03
**Trading instrument:** 1 /MES contract
**Maturity tier:** LIVE — walk-forward validated

## Data Summary
- Snapshots: 41,809
- Trading days: 10
- Features: 782
- Candidates evaluated: 6,297
- Rules promoted: 9

## Assumptions
- /MES reference price: 6502 (live SPY spot 650.21 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## SHORT Patterns (6)

### D_zdiv_nope_high_SHORT_30m
**Direction:** SHORT | **Horizon:** 30m | **Confidence:** HIGH

**Conditions:**
- zdiv_nope_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 130 snapshots across 9 day(s) |
| Win rate | 78.5% |
| Historically median favorable move | 23.7 pts ($119) |
| Typical adverse excursion | 3.9 pts ($20) |
| Estimated net expectancy (1 /MES) | **$54.93** per trade |
| Walk-forward stability | 100% (6/6 folds) |

**Suggested stop:** 5.9 pts (24 ticks, $30)
**Suggested target range:** 14.2–23.7 pts ($71–$119)

### L_otm_put_pct_low_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- otm_put_pct < 0.2

| Metric | Value |
|--------|-------|
| Sample size | 75 snapshots across 8 day(s) |
| Win rate | 78.7% |
| Historically median favorable move | 5.3 pts ($26) |
| Typical adverse excursion | 43.3 pts ($216) |
| Estimated net expectancy (1 /MES) | **$158.28** per trade |
| Walk-forward stability | 67% (4/6 folds) |

**Suggested stop:** 64.9 pts (260 ticks, $324)
**Suggested target range:** 3.2–5.3 pts ($16–$26)

### D_zdiv_net_prem_high_SHORT_15m
**Direction:** SHORT | **Horizon:** 15m | **Confidence:** HIGH

**Conditions:**
- zdiv_net_prem_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 149 snapshots across 9 day(s) |
| Win rate | 63.1% |
| Historically median favorable move | 12.2 pts ($61) |
| Typical adverse excursion | 6.7 pts ($33) |
| Estimated net expectancy (1 /MES) | **$64.95** per trade |
| Walk-forward stability | 100% (6/6 folds) |

**Suggested stop:** 10.0 pts (40 ticks, $50)
**Suggested target range:** 7.3–12.2 pts ($37–$61)

### I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- trin > 0.86

| Metric | Value |
|--------|-------|
| Sample size | 5011 snapshots across 7 day(s) |
| Win rate | 88.3% |
| Historically median favorable move | 20.4 pts ($102) |
| Typical adverse excursion | 9.9 pts ($49) |
| Estimated net expectancy (1 /MES) | **$68.51** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 14.8 pts (59 ticks, $74)
**Suggested target range:** 12.2–20.4 pts ($61–$102)

### I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- spot_vs_poc > -0.1196

| Metric | Value |
|--------|-------|
| Sample size | 5774 snapshots across 8 day(s) |
| Win rate | 77.2% |
| Historically median favorable move | 22.8 pts ($114) |
| Typical adverse excursion | 13.8 pts ($69) |
| Estimated net expectancy (1 /MES) | **$44.44** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 20.8 pts (83 ticks, $104)
**Suggested target range:** 13.7–22.8 pts ($68–$114)

### D_zdiv_gex_normalized_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- zdiv_gex_normalized_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 2714 snapshots across 9 day(s) |
| Win rate | 61.6% |
| Historically median favorable move | 25.3 pts ($127) |
| Typical adverse excursion | 13.2 pts ($66) |
| Estimated net expectancy (1 /MES) | **$30.57** per trade |
| Walk-forward stability | 100% (6/6 folds) |

**Suggested stop:** 19.8 pts (79 ticks, $99)
**Suggested target range:** 15.2–25.3 pts ($76–$127)

## SKIP Conditions (3)
*When these conditions are active, avoid new entries.*

### SKIP_midday_chop_15m
**When active:** Avoid new entries

**Conditions:**
- 0.25 <= pct_of_day <= 0.55
- efficiency_ratio < 0.25

- Historically, forward moves in this state average 10.49% with no clear direction
- Sample: 5253 snapshots

### SKIP_weak_gate_15m
**When active:** Avoid new entries

**Conditions:**
- structural_gate < 0.2

- Historically, forward moves in this state average 11.82% with no clear direction
- Sample: 746 snapshots

### SKIP_low_efficiency_15m
**When active:** Avoid new entries

**Conditions:**
- efficiency_ratio < 0.15

- Historically, forward moves in this state average 11.88% with no clear direction
- Sample: 11365 snapshots

---
*All figures are historically observed medians, not guarantees.*
*Past patterns may not repeat. Use position sizing and risk management.*