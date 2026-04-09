# Karpathy Autoresearch — Nightly Report
**Generated:** 2026-04-09 06:42
**Trading instrument:** 1 /MES contract
**Maturity tier:** LIVE — walk-forward validated

## Data Summary
- Snapshots: 60,160
- Trading days: 15
- Features: 780
- Candidates evaluated: 6,297
- Rules promoted: 9

## Assumptions
- /MES reference price: 6758 (live SPY spot 675.78 x10)
- Point value: $5.00
- Tick size: 0.25 pts = $1.25
- Round-trip cost: $2.50
- Slippage: 2 ticks RT = $2.50
- All dollar figures are **estimated** based on these assumptions.

## LONG Patterns (2)

### L_atm_straddle_pct_high_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** LOW

**Conditions:**
- atm_straddle_pct > 0.8

| Metric | Value |
|--------|-------|
| Sample size | 647 snapshots across 12 day(s) |
| Win rate | 65.7% |
| Historically median favorable move | 44.3 pts ($221) |
| Typical adverse excursion | 18.2 pts ($91) |
| Estimated net expectancy (1 /MES) | **$69.82** per trade |
| Walk-forward stability | 50% (5/10 folds) |

**Suggested stop:** 27.2 pts (109 ticks, $136)
**Suggested target range:** 26.6–44.3 pts ($133–$221)

### D_zdiv_vex_low_LONG_60m
**Direction:** LONG | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_vex_state = strong_neg

| Metric | Value |
|--------|-------|
| Sample size | 2200 snapshots across 14 day(s) |
| Win rate | 54.0% |
| Historically median favorable move | 23.3 pts ($116) |
| Typical adverse excursion | 14.0 pts ($70) |
| Estimated net expectancy (1 /MES) | **$20.84** per trade |
| Walk-forward stability | 73% (8/11 folds) |

**Suggested stop:** 21.0 pts (84 ticks, $105)
**Suggested target range:** 14.0–23.3 pts ($70–$116)

## SHORT Patterns (4)

### D_zdiv_nope_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- zdiv_nope_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 237 snapshots across 14 day(s) |
| Win rate | 65.0% |
| Historically median favorable move | 51.0 pts ($255) |
| Typical adverse excursion | 7.7 pts ($39) |
| Estimated net expectancy (1 /MES) | **$51.96** per trade |
| Walk-forward stability | 80% (8/10 folds) |

**Suggested stop:** 11.6 pts (46 ticks, $58)
**Suggested target range:** 30.6–51.0 pts ($153–$255)

### D_zdiv_net_prem_high_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- zdiv_net_prem_state = strong_pos

| Metric | Value |
|--------|-------|
| Sample size | 258 snapshots across 14 day(s) |
| Win rate | 45.3% |
| Historically median favorable move | 39.8 pts ($199) |
| Typical adverse excursion | 16.3 pts ($82) |
| Estimated net expectancy (1 /MES) | **$0.50** per trade |
| Walk-forward stability | 70% (7/10 folds) |

**Suggested stop:** 24.5 pts (98 ticks, $122)
**Suggested target range:** 23.9–39.8 pts ($119–$199)

### I_atm_avg_iv_q5_Q0_qqq_nope_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** HIGH

**Conditions:**
- atm_avg_iv_q5 = 0
- qqq_nope > -35.5

| Metric | Value |
|--------|-------|
| Sample size | 8169 snapshots across 11 day(s) |
| Win rate | 66.2% |
| Historically median favorable move | 21.6 pts ($108) |
| Typical adverse excursion | 8.0 pts ($40) |
| Estimated net expectancy (1 /MES) | **$38.95** per trade |
| Walk-forward stability | 88% (7/8 folds) |

**Suggested stop:** 12.0 pts (48 ticks, $60)
**Suggested target range:** 13.0–21.6 pts ($65–$108)

### I_atm_avg_iv_q5_Q0_trin_gt_SHORT_60m
**Direction:** SHORT | **Horizon:** 60m | **Confidence:** MODERATE

**Conditions:**
- atm_avg_iv_q5 = 0
- trin > 0.89

| Metric | Value |
|--------|-------|
| Sample size | 5936 snapshots across 10 day(s) |
| Win rate | 73.9% |
| Historically median favorable move | 16.9 pts ($84) |
| Typical adverse excursion | 8.8 pts ($44) |
| Estimated net expectancy (1 /MES) | **$60.76** per trade |
| Walk-forward stability | 75% (6/8 folds) |

**Suggested stop:** 13.3 pts (53 ticks, $66)
**Suggested target range:** 10.1–16.9 pts ($51–$84)

## SKIP Conditions (3)
*When these conditions are active, avoid new entries.*

### SKIP_midday_chop_15m
**When active:** Avoid new entries

**Conditions:**
- 0.25 <= pct_of_day <= 0.55
- efficiency_ratio < 0.25

- Historically, forward moves in this state average 9.91% with no clear direction
- Sample: 7821 snapshots

### SKIP_weak_gate_15m
**When active:** Avoid new entries

**Conditions:**
- structural_gate < 0.2

- Historically, forward moves in this state average 11.33% with no clear direction
- Sample: 1029 snapshots

### SKIP_low_efficiency_15m
**When active:** Avoid new entries

**Conditions:**
- efficiency_ratio < 0.15

- Historically, forward moves in this state average 11.62% with no clear direction
- Sample: 16147 snapshots

---
*All figures are historically observed medians, not guarantees.*
*Past patterns may not repeat. Use position sizing and risk management.*