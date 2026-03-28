# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-03-27 22:03
**Trading instrument:** 1 /MES contract
**Maturity tier:** PRELIMINARY — 2-fold walk-forward validated

## Data Summary
- Snapshots: 34,951
- Trading days: 8
- Features: 778
- Candidates evaluated: 6,297
- Rules promoted: 9

> **PRELIMINARY — 2-FOLD WALK-FORWARD VALIDATED**
> 8 trading day(s) available.
> Walk-forward validation has begun but is not yet conclusive.
> Treat these as preliminary signals. Live trading not recommended until 10+ days.

## Assumptions
- /MES reference price: 6349 (live SPY spot 634.89 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## LONG Patterns (1)

### I_tick_q5_Q0_qqq_atm_avg_iv_gt_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- tick_q5 = 0
- qqq_atm_avg_iv > 0.3199

| Metric | Value |
|--------|-------|
| Sample size | 3802 snapshots across 7 day(s) |
| Win rate | 48.1% |
| Historically median favorable move | 20.0 pts ($100) |
| Typical adverse excursion | 10.0 pts ($50) |
| Estimated net expectancy (1 /MES) | **$-5.85** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 15.1 pts (60 ticks, $75)
**Suggested target range:** 12.0–20.0 pts ($60–$100)

## SHORT Patterns (5)

### I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- atm_avg_iv_q5 = 0
- trin > 0.84

| Metric | Value |
|--------|-------|
| Sample size | 5102 snapshots across 6 day(s) |
| Win rate | 87.6% |
| Historically median favorable move | 17.8 pts ($89) |
| Typical adverse excursion | 7.6 pts ($38) |
| Estimated net expectancy (1 /MES) | **$63.88** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 11.4 pts (46 ticks, $57)
**Suggested target range:** 10.7–17.8 pts ($54–$89)

### I_atm_avg_iv_q5_Q0_spot_vs_poc_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- atm_avg_iv_q5 = 0
- spot_vs_poc > -0.1377

| Metric | Value |
|--------|-------|
| Sample size | 6088 snapshots across 7 day(s) |
| Win rate | 76.2% |
| Historically median favorable move | 22.1 pts ($111) |
| Typical adverse excursion | 14.0 pts ($70) |
| Estimated net expectancy (1 /MES) | **$42.11** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 21.0 pts (84 ticks, $105)
**Suggested target range:** 13.3–22.1 pts ($66–$111)

### D_zdiv_gex_normalized_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- zdiv_gex_normalized_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 2397 snapshots across 7 day(s) |
| Win rate | 58.4% |
| Historically median favorable move | 21.6 pts ($108) |
| Typical adverse excursion | 13.2 pts ($66) |
| Estimated net expectancy (1 /MES) | **$22.17** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 19.9 pts (79 ticks, $99)
**Suggested target range:** 13.0–21.6 pts ($65–$108)

### I_atm_avg_iv_q5_Q0_structural_gate_q5_Q0_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- atm_avg_iv_q5 = 0
- structural_gate_q5 = 0

| Metric | Value |
|--------|-------|
| Sample size | 1890 snapshots across 7 day(s) |
| Win rate | 75.5% |
| Historically median favorable move | 16.0 pts ($80) |
| Typical adverse excursion | 15.9 pts ($80) |
| Estimated net expectancy (1 /MES) | **$38.76** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 23.9 pts (95 ticks, $119)
**Suggested target range:** 9.6–16.0 pts ($48–$80)

### I_atm_avg_iv_q5_Q0_pct_of_day_lt_SHORT_30m
**Direction:** SHORT | **Horizon:** 30m | **Confidence:** PRELIMINARY (insufficient days)

**Conditions:**
- atm_avg_iv_q5 = 0
- pct_of_day < 0.3803

| Metric | Value |
|--------|-------|
| Sample size | 4217 snapshots across 7 day(s) |
| Win rate | 74.6% |
| Historically median favorable move | 14.0 pts ($70) |
| Typical adverse excursion | 7.0 pts ($35) |
| Estimated net expectancy (1 /MES) | **$36.12** per trade |
| Walk-forward stability | 100% (4/4 folds) |

**Suggested stop:** 10.5 pts (42 ticks, $52)
**Suggested target range:** 8.4–14.0 pts ($42–$70)

## SKIP Conditions (3)
*When these conditions are active, avoid new entries.*

### SKIP_midday_chop_30m
**When active:** Avoid new entries

**Conditions:**
- 0.25 <= pct_of_day <= 0.55
- efficiency_ratio < 0.25

- Historically, forward moves in this state average 11.85% with no clear direction
- Sample: 4348 snapshots

### SKIP_weak_gate_30m
**When active:** Avoid new entries

**Conditions:**
- structural_gate < 0.2

- Historically, forward moves in this state average 14.09% with no clear direction
- Sample: 563 snapshots

### SKIP_low_efficiency_15m
**When active:** Avoid new entries

**Conditions:**
- efficiency_ratio < 0.15

- Historically, forward moves in this state average 11.19% with no clear direction
- Sample: 9450 snapshots

---
*All figures are historically observed medians, not guarantees.*
*Past patterns may not repeat. Use position sizing and risk management.*