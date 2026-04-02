# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-04-01 21:41
**Trading instrument:** 1 /MES contract
**Maturity tier:** LIVE — walk-forward validated

## Data Summary
- Snapshots: 44,305
- Trading days: 11
- Features: 782
- Candidates evaluated: 6,297
- Rules promoted: 9

## Assumptions
- /MES reference price: 6552 (live SPY spot 655.24 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## LONG Patterns (1)

### L_otm_put_pct_low_LONG_30m
**Direction:** LONG | **Horizon:** 30m | **Confidence:** LOW

**Conditions:**
- otm_put_pct < 0.2

| Metric | Value |
|--------|-------|
| Sample size | 190 snapshots across 8 day(s) |
| Win rate | 67.4% |
| Historically median favorable move | 43.2 pts ($216) |
| Typical adverse excursion | 5.3 pts ($27) |
| Estimated net expectancy (1 /MES) | **$-8.31** per trade |
| Walk-forward stability | 50% (3/6 folds) |

**Suggested stop:** 8.0 pts (32 ticks, $40)
**Suggested target range:** 25.9–43.2 pts ($130–$216)

## SHORT Patterns (5)

### D_zdiv_nope_high_SHORT_30m
**Direction:** SHORT | **Horizon:** 30m | **Confidence:** HIGH

**Conditions:**
- zdiv_nope_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 130 snapshots across 9 day(s) |
| Win rate | 78.5% |
| Historically median favorable move | 23.9 pts ($120) |
| Typical adverse excursion | 4.0 pts ($20) |
| Estimated net expectancy (1 /MES) | **$55.39** per trade |
| Walk-forward stability | 100% (6/6 folds) |

**Suggested stop:** 6.0 pts (24 ticks, $30)
**Suggested target range:** 14.3–23.9 pts ($72–$120)

### I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- trin > 0.86

| Metric | Value |
|--------|-------|
| Sample size | 5011 snapshots across 7 day(s) |
| Win rate | 88.3% |
| Historically median favorable move | 20.5 pts ($103) |
| Typical adverse excursion | 10.0 pts ($50) |
| Estimated net expectancy (1 /MES) | **$69.08** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 15.0 pts (60 ticks, $75)
**Suggested target range:** 12.3–20.5 pts ($62–$103)

### D_zdiv_net_prem_high_SHORT_15m
**Direction:** SHORT | **Horizon:** 15m | **Confidence:** HIGH

**Conditions:**
- zdiv_net_prem_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 149 snapshots across 9 day(s) |
| Win rate | 63.1% |
| Historically median favorable move | 12.3 pts ($61) |
| Typical adverse excursion | 6.7 pts ($34) |
| Estimated net expectancy (1 /MES) | **$65.49** per trade |
| Walk-forward stability | 100% (6/6 folds) |

**Suggested stop:** 10.1 pts (40 ticks, $51)
**Suggested target range:** 7.4–12.3 pts ($37–$61)

### I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- spot_vs_poc > -0.1196

| Metric | Value |
|--------|-------|
| Sample size | 5774 snapshots across 8 day(s) |
| Win rate | 77.2% |
| Historically median favorable move | 23.0 pts ($115) |
| Typical adverse excursion | 14.0 pts ($70) |
| Estimated net expectancy (1 /MES) | **$44.83** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 20.9 pts (84 ticks, $105)
**Suggested target range:** 13.8–23.0 pts ($69–$115)

### D_zdiv_gex_normalized_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- zdiv_gex_normalized_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 2714 snapshots across 9 day(s) |
| Win rate | 61.6% |
| Historically median favorable move | 25.5 pts ($127) |
| Typical adverse excursion | 13.3 pts ($66) |
| Estimated net expectancy (1 /MES) | **$30.84** per trade |
| Walk-forward stability | 100% (6/6 folds) |

**Suggested stop:** 19.9 pts (80 ticks, $100)
**Suggested target range:** 15.3–25.5 pts ($76–$127)

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