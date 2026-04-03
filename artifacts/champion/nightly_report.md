# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-04-02 16:53
**Trading instrument:** 1 /MES contract
**Maturity tier:** LIVE — walk-forward validated

## Data Summary
- Snapshots: 47,680
- Trading days: 12
- Features: 782
- Candidates evaluated: 6,297
- Rules promoted: 9

## Assumptions
- /MES reference price: 6558 (live SPY spot 655.84 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## LONG Patterns (1)

### L_atm_straddle_pct_high_LONG_30m
**Direction:** LONG | **Horizon:** 30m | **Confidence:** LOW

**Conditions:**
- atm_straddle_pct > 0.8

| Metric | Value |
|--------|-------|
| Sample size | 535 snapshots across 9 day(s) |
| Win rate | 75.7% |
| Historically median favorable move | 29.9 pts ($150) |
| Typical adverse excursion | 7.6 pts ($38) |
| Estimated net expectancy (1 /MES) | **$90.79** per trade |
| Walk-forward stability | 57% (4/7 folds) |

**Suggested stop:** 11.4 pts (46 ticks, $57)
**Suggested target range:** 17.9–29.9 pts ($90–$150)

## SHORT Patterns (5)

### D_zdiv_nope_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- zdiv_nope_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 208 snapshots across 11 day(s) |
| Win rate | 66.3% |
| Historically median favorable move | 53.9 pts ($269) |
| Typical adverse excursion | 6.9 pts ($34) |
| Estimated net expectancy (1 /MES) | **$56.30** per trade |
| Walk-forward stability | 88% (7/8 folds) |

**Suggested stop:** 10.3 pts (41 ticks, $52)
**Suggested target range:** 32.3–53.9 pts ($162–$269)

### I_iv_slope_q5_Q0_div_gex_lt_SHORT_30m
**Direction:** SHORT | **Horizon:** 30m | **Confidence:** SPECULATIVE

**Conditions:**
- iv_slope_q5 = 0
- div_gex < -7.921e+08

| Metric | Value |
|--------|-------|
| Sample size | 2287 snapshots across 8 day(s) |
| Win rate | 38.1% |
| Historically median favorable move | 104.5 pts ($522) |
| Typical adverse excursion | 11.4 pts ($57) |
| Estimated net expectancy (1 /MES) | **$-13.01** per trade |
| Walk-forward stability | 25% (1/4 folds) |

**Suggested stop:** 17.1 pts (68 ticks, $85)
**Suggested target range:** 62.7–104.5 pts ($313–$522)

### D_zdiv_net_prem_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_net_prem_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 218 snapshots across 11 day(s) |
| Win rate | 46.3% |
| Historically median favorable move | 54.9 pts ($274) |
| Typical adverse excursion | 15.9 pts ($79) |
| Estimated net expectancy (1 /MES) | **$5.18** per trade |
| Walk-forward stability | 75% (6/8 folds) |

**Suggested stop:** 23.8 pts (95 ticks, $119)
**Suggested target range:** 32.9–54.9 pts ($165–$274)

### I_gex_normalized_gt_atm_avg_iv_q5_Q0_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- gex_normalized > -0.004132
- atm_avg_iv_q5 = 0

| Metric | Value |
|--------|-------|
| Sample size | 5333 snapshots across 8 day(s) |
| Win rate | 72.4% |
| Historically median favorable move | 26.6 pts ($133) |
| Typical adverse excursion | 5.9 pts ($30) |
| Estimated net expectancy (1 /MES) | **$61.97** per trade |
| Walk-forward stability | 100% (6/6 folds) |

**Suggested stop:** 8.9 pts (36 ticks, $45)
**Suggested target range:** 16.0–26.6 pts ($80–$133)

### I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- trin > 0.87

| Metric | Value |
|--------|-------|
| Sample size | 6074 snapshots across 8 day(s) |
| Win rate | 82.4% |
| Historically median favorable move | 19.0 pts ($95) |
| Typical adverse excursion | 7.8 pts ($39) |
| Estimated net expectancy (1 /MES) | **$67.27** per trade |
| Walk-forward stability | 100% (6/6 folds) |

**Suggested stop:** 11.7 pts (47 ticks, $58)
**Suggested target range:** 11.4–19.0 pts ($57–$95)

## SKIP Conditions (3)
*When these conditions are active, avoid new entries.*

### SKIP_midday_chop_15m
**When active:** Avoid new entries

**Conditions:**
- 0.25 <= pct_of_day <= 0.55
- efficiency_ratio < 0.25

- Historically, forward moves in this state average 10.30% with no clear direction
- Sample: 6160 snapshots

### SKIP_weak_gate_15m
**When active:** Avoid new entries

**Conditions:**
- structural_gate < 0.2

- Historically, forward moves in this state average 11.52% with no clear direction
- Sample: 831 snapshots

### SKIP_low_efficiency_15m
**When active:** Avoid new entries

**Conditions:**
- efficiency_ratio < 0.15

- Historically, forward moves in this state average 11.90% with no clear direction
- Sample: 12795 snapshots

---
*All figures are historically observed medians, not guarantees.*
*Past patterns may not repeat. Use position sizing and risk management.*