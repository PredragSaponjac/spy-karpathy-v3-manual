# Karpathy Detailed Review
**Run:** 2026-04-02 15:06:00  

## Champion Baseline
- Rules: 9 (entry: 6, skip: 3)
- Net expectancy: $44.75
- WF stability: 0.7302
- Sum composite: 460.1282

---
## Attempt 1

### Proposer Idea
- **Summary:** Raise min_composite_score from 0.0 to 3.0 to prune weak candidates earlier and concentrate evaluation budget on higher-quality rules, addressing regime concentration and the negative-expectancy interaction rule that slipped through
- **Patch type:** threshold_adjustment
- **Changes:** `{"thresholds": {"min_composite_score": 3.0}}`
- **Rationale:** One promoted interaction rule (I_iv_slope_q5_Q0_div_gex_lt_SHORT_30m) has negative net expectancy (-$13.01) and wf_stability of only 0.25 — it should never have been promoted. A higher min_composite_score floor would filter weak candidates earlier in the pipeline.; Regime concentration is already failing (any_regime_concentration_fail: true), meaning the rulebook is over-fitted to certain market conditions. Raising the quality floor forces the engine to only promote rules with stronger composite evidence, which should improve regime diversity.; The pipeline generated 6297 candidates but only promoted 9 — a 0.14% promotion rate. Pruning the bottom of the candidate pool earlier frees walk-forward evaluation budget for deeper analysis of genuinely strong candidates.; All 5 recent experiments tried weight adjustments (skew, z_score_div) and all failed with 0% or negative composite improvement. This is a different knob class (threshold_adjustment) targeting a different failure mode (weak rule leakage rather than feature emphasis).

### Critic Response
- **Verdict:** approve
- **Confidence:** 0.82
- **Recommendation:** run_as_is
- **Concerns:**
  - min_composite_score of 3.0 is a very mild floor — unlikely to cause harm but also may have minimal effect since the weakest promoted rule (I_iv_slope_q5_Q0_div_gex_lt_SHORT_30m) has composite 72.2, far above 3.0. The negative-expectancy rule already passed composite gating, so this floor likely won't prevent its promotion — the problem is the promotion gate itself, not the candidate floor.
  - The stated rationale that this will 'eliminate negative-expectancy rules from promotion' is likely incorrect — composite score of 72.2 >> 3.0, so the problematic rule would still pass this filter. The patch may be solving the wrong problem.

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 44.75 | 44.75 |
| WF stability | 0.7302 | 0.7302 |
| Sum composite | 460.13 | 460.13 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 2

### Proposer Idea
- **Summary:** Tighten max_overlap from 0.6 to 0.45 to force pruning of redundant SHORT interaction rules and open promotion slots for underrepresented families like sequence and level
- **Patch type:** threshold_adjustment
- **Changes:** `{"thresholds": {"max_overlap": 0.45}}`
- **Rationale:** Interaction family has 3 promoted rules (all SHORT) but only avg composite 59.47 vs divergence at 77.45 — suggests overlapping mediocre rules are occupying promotion slots; Direction balance is heavily skewed (5 SHORT, 1 LONG, 3 SKIP) and regime concentration is already failing — pruning overlapping rules should open slots for diverse discoveries; The I_iv_slope_q5_Q0_div_gex_lt rule has negative net expectancy (-13.01 USD) and 0.25 wf_stability yet still got promoted, suggesting overlap tolerance is too permissive and allowing weaker variants through; Sequence family has zero promoted rules despite being enabled — tighter overlap may free candidate budget for sequence rules that currently lose tiebreakers to near-duplicate interaction rules; Previous attempts boosted weights (skew, z_score_div) and raised min_composite with 0% improvement; this is a different knob targeting structural pruning rather than feature emphasis

### Critic Response
- **Verdict:** approve
- **Confidence:** 0.78
- **Recommendation:** run_as_is
- **Concerns:**
  - If the 3 interaction rules actually have Jaccard overlap below 0.45 already, this is a no-op wasted cycle — but that's a low-risk failure mode
  - Reducing from 0.6 to 0.45 is a meaningful 25% tightening — could lose a legitimately useful rule that shares partial overlap but adds independent signal

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 44.75 | 49.65 |
| WF stability | 0.7302 | 0.7440 |
| Sum composite | 460.13 | 445.11 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (-3.3%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 3

### Proposer Idea
- **Summary:** Increase feature_family_weights.internals from 1.0 to 1.8 to amplify internals-derived features like TRIN which shows 67.27 avg net expectancy but appears in only 1 rule, potentially surfacing more breadth-based entry rules to address regime concentration and SHORT-only interaction dominance
- **Patch type:** weight_adjustment
- **Changes:** `{"feature_family_weights": {"internals": 1.8}}`
- **Rationale:** TRIN (an internals feature) appears in the 5th-ranked entry rule with $67.27 net expectancy and perfect 1.0 walk-forward stability, yet only appears in 1 rule — internals family is underrepresented relative to its demonstrated lift; The system has regime concentration failure and 5 SHORT vs 1 LONG directional imbalance; boosting internals may surface breadth-based conditions that fire across different regimes and directions; No internals weight adjustment has been attempted in recent experiments — prior rejected attempts targeted skew, divergence z_score_div, and thresholds, so this is a fresh knob family; Interaction rules dominate (3 of 6 entry rules) with lower avg expectancy ($38.74) than the TRIN-using rule ($67.27); upweighting internals could promote higher-quality internals-based candidates that compete with or complement interaction rules

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.55
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - TRIN appearing in only 1 rule with 1.0 WF stability on 8 days is a thin evidence base for upweighting an entire feature family — the perfect stability score on such few days is suspicious and could reflect low sample variance rather than true robustness
  - Prior weight adjustment attempts (skew 1.0→1.7, z_score_div 1.0→1.8) all failed to clear the 2% composite improvement threshold, suggesting the engine is relatively insensitive to 0.8-unit weight bumps and this may waste a cycle
  - Regime concentration is already failing — the patch narrative claims internals will help, but there's no direct evidence that breadth features fire differentially across regimes in this dataset

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 44.75 | 44.75 |
| WF stability | 0.7302 | 0.7302 |
| Sum composite | 460.13 | 460.13 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 4

### Proposer Idea
- **Summary:** Increase feature_family_weights.dealer from 1.0 to 1.6 to boost dealer-positioning features (GEX, DEX) that already appear in 2 of the top 5 entry rules with strong expectancy, potentially surfacing new dealer-driven rules to diversify away from SHORT-only interaction dominance
- **Patch type:** weight_adjustment
- **Changes:** `{"feature_family_weights": {"dealer": 1.6}}`
- **Rationale:** gex_normalized appears in the 5th-ranked entry rule with $61.97 net expectancy and perfect 1.0 walk-forward stability — dealer features are demonstrably durable; div_gex appears in an interaction rule but that rule has negative expectancy (-$13.01) and 0.25 WF stability, suggesting the system needs to better weight raw dealer signals over weak interaction combinations; The current rulebook is 5 SHORT / 1 LONG with regime concentration failing — amplifying dealer features (which capture positioning asymmetries) may surface LONG-side dealer-driven rules to rebalance; Prior rejected attempts targeted internals (1.8), skew (1.7), z_score_div (1.8), thresholds — dealer family weight has NOT been tried in recent experiments

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.45
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - Three consecutive weight_adjustment patches (internals 1.8, skew 1.7, z_score_div 1.8) were all rejected as TIE_REJECT with 0.0% or negative composite improvement — this is the same category of change and the pattern suggests weight nudges at this maturity level simply don't move the needle enough to clear the 2% composite threshold
  - The narrative that boosting dealer weight will surface LONG-side rules is speculative — gex_normalized already appears in a SHORT rule, and there's no diagnostic evidence that underweighted dealer features are suppressing LONG-side candidates
  - Regime concentration is already failing; this patch does nothing structurally to address that and may add more SHORT dealer rules that worsen the concentration problem

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 44.75 | 44.75 |
| WF stability | 0.7302 | 0.7302 |
| Sum composite | 460.13 | 460.13 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 5

### Proposer Idea
- **Summary:** Increase sequence_family_weights.qqq_lead_confirm from 1.0 to 2.0 to surface QQQ-lead sequence rules that may break regime concentration and add LONG diversity to the SHORT-heavy rulebook
- **Patch type:** weight_adjustment
- **Changes:** `{"sequence_family_weights": {"qqq_lead_confirm": 2.0}}`
- **Rationale:** The rulebook is 5 SHORT / 1 LONG with regime concentration already failing — sequence rules (especially QQQ lead/confirm) could surface directionally diverse patterns that fire in different regimes; Zero sequence rules were promoted despite the sequence family being enabled, suggesting the scoring pipeline is underweighting sequence candidates relative to level/interaction/divergence; intermarket_weight is already at 1.4 showing commitment to QQQ signals, but the sequence sub-family that specifically captures QQQ leading SPY confirmations (qqq_lead_confirm) has not produced any promoted rules at default weight — a strong boost may push viable candidates over the promotion threshold; All 4 prior rejected attempts targeted feature_family_weights or thresholds and produced 0.0% composite improvement — this is a completely different knob family (sequence_family_weights) that has not been tried

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.55
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - Four consecutive weight/threshold adjustments have all produced 0.0% composite improvement and been rejected — this is the same class of intervention (weight adjustment) just targeting a different sub-knob, so the base rate for success is very low
  - With only 12 days of data and zero sequence rules ever promoted, boosting qqq_lead_confirm to 2.0 is speculative — there may simply not be enough QQQ-lead-SPY-confirm episodes to form robust sequences yet
  - The narrative about regime concentration and directional diversity is compelling but entirely forward-looking — there is no diagnostic evidence that sequence candidates are close to promotion threshold and just need a boost

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 44.75 | 44.75 |
| WF stability | 0.7302 | 0.7302 |
| Sum composite | 460.13 | 460.13 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## LLM Budget
- Spend: $1.6316 / $30.00
- Calls: 5 proposer + 5 critic
