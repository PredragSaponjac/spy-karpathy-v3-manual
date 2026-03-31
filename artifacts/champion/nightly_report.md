# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-03-31 07:33
**Trading instrument:** 1 /MES contract
**Maturity tier:** PRELIMINARY — 2-fold walk-forward validated

## Data Summary
- Snapshots: 38,948
- Trading days: 9
- Features: 780
- Candidates evaluated: 6,297
- Rules promoted: 9

> **PRELIMINARY — 2-FOLD WALK-FORWARD VALIDATED**
> 9 trading day(s) available.
> Walk-forward validation has begun but is not yet conclusive.
> Treat these as preliminary signals. Live trading not recommended until 10+ days.

## Assumptions
- /MES reference price: 6318 (live SPY spot 631.77 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## SHORT Patterns (6)

### L_otm_put_pct_low_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- otm_put_pct < 0.2

| Metric | Value |
|--------|-------|
| Sample size | 66 snapshots across 7 day(s) |
| Win rate | 77.3% |
| Historically median favorable move | 27.3 pts ($136) |
| Typical adverse excursion | 3.2 pts ($16) |
| Estimated net expectancy (1 /MES) | **$160.26** per trade |
| Walk-forward stability | 60% (3/5 folds) |

**Suggested stop:** 4.8 pts (19 ticks, $24)
**Suggested target range:** 16.4–27.3 pts ($82–$136)

### D_zdiv_nope_high_SHORT_30m
**Direction:** SHORT | **Horizon:** 30m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- zdiv_nope_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 122 snapshots across 8 day(s) |
| Win rate | 77.0% |
| Historically median favorable move | 36.1 pts ($181) |
| Typical adverse excursion | 3.0 pts ($15) |
| Estimated net expectancy (1 /MES) | **$46.66** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 4.5 pts (18 ticks, $22)
**Suggested target range:** 21.7–36.1 pts ($108–$181)

### D_zdiv_net_prem_high_SHORT_15m
**Direction:** SHORT | **Horizon:** 15m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- zdiv_net_prem_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 144 snapshots across 8 day(s) |
| Win rate | 61.8% |
| Historically median favorable move | 11.3 pts ($57) |
| Typical adverse excursion | 6.8 pts ($34) |
| Estimated net expectancy (1 /MES) | **$61.83** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 10.3 pts (41 ticks, $51)
**Suggested target range:** 6.8–11.3 pts ($34–$57)

### I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- atm_avg_iv_q5 = 0
- trin > 0.85

| Metric | Value |
|--------|-------|
| Sample size | 4915 snapshots across 6 day(s) |
| Win rate | 87.8% |
| Historically median favorable move | 17.7 pts ($89) |
| Typical adverse excursion | 7.8 pts ($39) |
| Estimated net expectancy (1 /MES) | **$64.06** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 11.7 pts (47 ticks, $59)
**Suggested target range:** 10.6–17.7 pts ($53–$89)

### I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- atm_avg_iv_q5 = 0
- spot_vs_poc > -0.1366

| Metric | Value |
|--------|-------|
| Sample size | 6071 snapshots across 7 day(s) |
| Win rate | 76.3% |
| Historically median favorable move | 22.0 pts ($110) |
| Typical adverse excursion | 13.9 pts ($70) |
| Estimated net expectancy (1 /MES) | **$42.01** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 20.9 pts (84 ticks, $105)
**Suggested target range:** 13.2–22.0 pts ($66–$110)

### D_zdiv_gex_normalized_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- zdiv_gex_normalized_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 2489 snapshots across 8 day(s) |
| Win rate | 59.9% |
| Historically median favorable move | 21.5 pts ($107) |
| Typical adverse excursion | 13.7 pts ($68) |
| Estimated net expectancy (1 /MES) | **$25.62** per trade |
| Walk-forward stability | 100% (5/5 folds) |

**Suggested stop:** 20.5 pts (82 ticks, $102)
**Suggested target range:** 12.9–21.5 pts ($64–$107)

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