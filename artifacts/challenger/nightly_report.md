# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-03-31 15:12
**Trading instrument:** 1 /MES contract
**Maturity tier:** LIVE — walk-forward validated

## Data Summary
- Snapshots: 39,952
- Trading days: 10
- Features: 780
- Candidates evaluated: 6,297
- Rules promoted: 9

## Assumptions
- /MES reference price: 6411 (live SPY spot 641.12 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## SHORT Patterns (6)

### L_otm_put_pct_low_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- otm_put_pct < 0.2

| Metric | Value |
|--------|-------|
| Sample size | 66 snapshots across 7 day(s) |
| Win rate | 77.3% |
| Historically median favorable move | 27.7 pts ($138) |
| Typical adverse excursion | 3.2 pts ($16) |
| Estimated net expectancy (1 /MES) | **$162.71** per trade |
| Walk-forward stability | 60% (3/5 folds) |

**Suggested stop:** 4.8 pts (19 ticks, $24)
**Suggested target range:** 16.6–27.7 pts ($83–$138)

### D_zdiv_nope_high_SHORT_30m
**Direction:** SHORT | **Horizon:** 30m | **Confidence:** HIGH

**Conditions:**
- zdiv_nope_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 122 snapshots across 8 day(s) |
| Win rate | 77.0% |
| Historically median favorable move | 36.7 pts ($183) |
| Typical adverse excursion | 3.0 pts ($15) |
| Estimated net expectancy (1 /MES) | **$47.43** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 4.5 pts (18 ticks, $23)
**Suggested target range:** 22.0–36.7 pts ($110–$183)

### D_zdiv_net_prem_high_SHORT_15m
**Direction:** SHORT | **Horizon:** 15m | **Confidence:** HIGH

**Conditions:**
- zdiv_net_prem_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 144 snapshots across 8 day(s) |
| Win rate | 61.8% |
| Historically median favorable move | 11.5 pts ($58) |
| Typical adverse excursion | 6.9 pts ($35) |
| Estimated net expectancy (1 /MES) | **$62.82** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 10.4 pts (42 ticks, $52)
**Suggested target range:** 6.9–11.5 pts ($35–$58)

### I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- trin > 0.85

| Metric | Value |
|--------|-------|
| Sample size | 4915 snapshots across 6 day(s) |
| Win rate | 87.8% |
| Historically median favorable move | 18.0 pts ($90) |
| Typical adverse excursion | 7.9 pts ($40) |
| Estimated net expectancy (1 /MES) | **$65.08** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 11.9 pts (48 ticks, $59)
**Suggested target range:** 10.8–18.0 pts ($54–$90)

### I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- spot_vs_poc > -0.1366

| Metric | Value |
|--------|-------|
| Sample size | 6071 snapshots across 7 day(s) |
| Win rate | 76.3% |
| Historically median favorable move | 22.3 pts ($112) |
| Typical adverse excursion | 14.1 pts ($71) |
| Estimated net expectancy (1 /MES) | **$42.70** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 21.2 pts (85 ticks, $106)
**Suggested target range:** 13.4–22.3 pts ($67–$112)

### D_zdiv_gex_normalized_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- zdiv_gex_normalized_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 2489 snapshots across 8 day(s) |
| Win rate | 59.9% |
| Historically median favorable move | 21.8 pts ($109) |
| Typical adverse excursion | 13.9 pts ($69) |
| Estimated net expectancy (1 /MES) | **$26.07** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 20.8 pts (83 ticks, $104)
**Suggested target range:** 13.1–21.8 pts ($65–$109)

## SKIP Conditions (3)
*When these conditions are active, avoid new entries.*

### SKIP_midday_chop_15m
**When active:** Avoid new entries

**Conditions:**
- 0.25 <= pct_of_day <= 0.55
- efficiency_ratio < 0.25

- Historically, forward moves in this state average 9.54% with no clear direction
- Sample: 4911 snapshots

### SKIP_weak_gate_30m
**When active:** Avoid new entries

**Conditions:**
- structural_gate < 0.2

- Historically, forward moves in this state average 14.28% with no clear direction
- Sample: 603 snapshots

### SKIP_low_efficiency_15m
**When active:** Avoid new entries

**Conditions:**
- efficiency_ratio < 0.15

- Historically, forward moves in this state average 11.27% with no clear direction
- Sample: 10492 snapshots

---
*All figures are historically observed medians, not guarantees.*
*Past patterns may not repeat. Use position sizing and risk management.*