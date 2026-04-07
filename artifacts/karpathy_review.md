# Karpathy Detailed Review
**Run:** 2026-04-06 15:20:42  

## Champion Baseline
- Rules: 9 (entry: 6, skip: 3)
- Net expectancy: $35.40
- WF stability: 0.7033
- Sum composite: 402.6612

---
## Attempt 1

### Proposer Idea
- **Summary:** Raise move_size_preference from 1.8 to 2.0 to push candidate scoring harder toward larger net moves, potentially lifting composite of existing high-expectancy rules and pruning marginal ones like D_zdiv_net_prem (−$1.29)
- **Patch type:** scalar_adjustment
- **Changes:** `{"move_size_preference": 2.0}`
- **Rationale:** The rulebook contains D_zdiv_net_prem_high_SHORT_60m with net_exp_usd of -$1.29 yet composite of 56.4 — this marginal rule is surviving because move-size scoring is not penalizing near-zero expectancy enough; The best rules (atm_straddle_pct LONG $70.63, zdiv_nope SHORT $51.85, interaction SHORT $47.95) all have meaningful move sizes; increasing move_size_preference further rewards these durable signals; Five consecutive weight_adjustment and threshold_adjustment patches all returned 0.0% composite improvement — a scalar_adjustment on a different knob (move_size_preference) is a fresh mutation class that hasn't been tried in the rolling window; Regime concentration is already failing; by favoring larger moves the system may naturally diversify away from small choppy-regime rules that cluster in one regime; Current move_size_preference is 1.8, already elevated — nudging to the ceiling of 2.0 is a small bounded change that increases scoring pressure without restructuring the pipeline

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.55
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - Five consecutive patches have all returned 0.0% composite improvement — this suggests the pipeline may be insensitive to small knob changes at this maturity, and this patch may suffer the same fate rather than being harmful
  - Moving move_size_preference to the ceiling (2.0) eliminates future upward tuning room on this knob; if it works partially, there's no further incremental step available
  - The reasoning that larger move preference will fix regime concentration is speculative — no diagnostic evidence directly links move size to regime diversity
  - At 13 days, the negative-expectancy rule (D_zdiv_net_prem at -$1.29) could easily flip positive with one more day of data; pruning it via scoring pressure may be premature

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 35.40 | 35.40 |
| WF stability | 0.7033 | 0.7033 |
| Sum composite | 402.66 | 424.92 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✓ ACCEPTED**
- **Reason:** Challenger improves composite by 5.5% with net expectancy delta $+0.00, stability delta +0.0000. All guardrails passed.

---
## Attempt 2

### Proposer Idea
- **Summary:** Raise min_composite_score from 0.0 to 3.0 to prune marginal rules like D_zdiv_net_prem (-$1.29 expectancy, composite 61.6) and force promotion slots toward higher-quality candidates, addressing regime concentration failure
- **Patch type:** threshold_adjustment
- **Changes:** `{"thresholds": {"min_composite_score": 3.0}}`
- **Rationale:** D_zdiv_net_prem_high_SHORT_60m has negative net expectancy (-$1.29) yet sits at composite 61.6 occupying a promotion slot; raising the composite floor won't directly remove it but will raise the bar for all candidates competing for slots; Regime concentration is failing (any_regime_concentration_fail: true) suggesting the current rulebook includes rules that cluster in specific regimes; a higher composite floor forces candidates to demonstrate broader robustness to earn promotion; The worst_drag list shows divergence family avg_net_exp of only $22.98 dragged down by the negative-expectancy rule; raising the quality floor should improve the average expectancy of promoted divergence rules; No previous experiment has tried adjusting min_composite_score, so this is a fresh knob with clean credit assignment

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.62
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - The min_composite_score change from 0.0 to 3.0 is unlikely to have any practical effect: the lowest promoted composite is 14.1 (skip) and 49.3 (entry). A floor of 3.0 is far below any currently promoted rule, so this may be a no-op that wastes an experiment cycle.
  - The stated goal of pruning D_zdiv_net_prem (-$1.29 expectancy, composite 61.6) will NOT be achieved by a floor of 3.0 since 61.6 >> 3.0. The narrative about this rule being pruned is misleading.
  - The patch's own risk section acknowledges it may be too conservative to hit the 2% improvement threshold, which means this is likely headed for rejection at the acceptance gate — burning a cycle for nothing.

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 35.40 | 35.40 |
| WF stability | 0.7033 | 0.7033 |
| Sum composite | 424.92 | 424.92 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 3

### Proposer Idea
- **Summary:** Increase divergence_family_weights.z_score_div from 1.0 to 1.8 to amplify the strongest rule family, where the top rule D_zdiv_nope has 94.4 composite and $51.85 expectancy, potentially surfacing additional z-score divergence rules and lifting overall composite
- **Patch type:** weight_adjustment
- **Changes:** `{"divergence_family_weights": {"z_score_div": 1.8}}`
- **Rationale:** The divergence family leads all families with avg_composite 69.53 and the single best rule (D_zdiv_nope_high_SHORT_60m, composite 94.39, $51.85 net exp, 0.78 WF stability) is a z_score_div rule; Three of 6 entry rules are divergence-family, and two of the three use zdiv_ features — z_score_div is the most productive divergence sub-family but is weighted at default 1.0; Regime concentration is currently failing; boosting z_score_div may surface additional z-score divergence rules in different regimes or directions (currently only 1 LONG divergence rule exists), improving regime diversity; Recent rejected experiments tried internals (1.8), dealer (1.6), sequence qqq_lead_confirm (2.0), and min_composite_score (3.0) — none passed the 2% composite bar. This targets the empirically strongest sub-family that hasn't been tried yet

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.55
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - Regime concentration is already failing — boosting the dominant family's dominant sub-family is more likely to deepen that concentration than fix it
  - 3 of 6 entry rules are already divergence family; amplifying z_score_div risks turning this into a 4-5 rule divergence-dominated book with even less family diversity
  - The proposer's own risk section acknowledges this could worsen regime concentration, yet the patch proceeds anyway — the hope that WF gating catches fragile rules is reasonable but not guaranteed with only 13 days

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 35.40 | 35.40 |
| WF stability | 0.7033 | 0.7033 |
| Sum composite | 424.92 | 424.92 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 4

### Proposer Idea
- **Summary:** Increase feature_family_weights.structure from 1.0 to 1.8 to boost structure features like spot_vs_poc which appears in the second-best interaction rule with $47.95 expectancy, potentially surfacing new structure-based rules and addressing regime concentration failure by diversifying rule conditions
- **Patch type:** weight_adjustment
- **Changes:** `{"feature_family_weights": {"structure": 1.8}}`
- **Rationale:** spot_vs_poc is the 4th highest feature by lift ($47.95 avg net expectancy) but only appears in 1 rule — structure features are underrepresented despite strong signal; The system has regime concentration failure and only 3 active entry families (divergence, level, interaction) — boosting structure features could surface new candidates from underexplored feature space; No sequence rules were promoted despite sequence families being enabled, and no structure-heavy rules exist — this is a fresh search direction not yet attempted in recent experiments; Recent rejected patches targeted divergence weights and thresholds which produced 0% composite improvement — structure is a different family axis entirely, avoiding the retry discipline concern

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.52
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - Recent history shows 4 out of 5 weight/threshold adjustment patches were rejected by the judge for producing 0% composite improvement — this pattern suggests feature weight adjustments may not meaningfully alter the promotion pipeline at current data maturity
  - spot_vs_poc appears in only 1 rule with $47.95 expectancy — extrapolating from a single rule that the entire structure family is underexplored is thin evidence for a 1.0→1.8 weight boost
  - Regime concentration is already failing; if structure features are correlated with the same regime conditions driving existing rules, this could worsen rather than help the problem

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 35.40 | 35.40 |
| WF stability | 0.7033 | 0.7033 |
| Sum composite | 424.92 | 424.92 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 5

### Proposer Idea
- **Summary:** Tighten max_overlap from 0.6 to 0.42 to force pruning of near-duplicate divergence rules, free promotion slots for diverse families, and address regime concentration failure
- **Patch type:** threshold_adjustment
- **Changes:** `{"thresholds": {"max_overlap": 0.42}}`
- **Rationale:** 3 of 6 entry rules are divergence family (D_zdiv_nope, D_zdiv_net_prem, D_zdiv_vex) — all z-score divergence rules likely firing on overlapping snapshots, crowding out other families; D_zdiv_net_prem has negative expectancy (-$1.29) yet occupies a promotion slot with composite 61.6 — tighter overlap pruning should eliminate it as redundant with the stronger D_zdiv_nope (composite 94.4, $51.85); Regime concentration is failing (any_regime_concentration_fail: true) — overlapping divergence rules that fire in the same regime are the most likely cause; Previous weight_adjustment attempts (z_score_div, structure, feature weights) all produced 0.0% composite improvement — the issue isn't weighting, it's that redundant rules consume promotion slots; Reducing max_overlap from 0.6 to 0.42 is a meaningful structural change that forces the pipeline to prefer non-overlapping rules, opening slots for sequence or other underrepresented families

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.68
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - Dropping max_overlap from 0.6 to 0.42 is a 30% relative tightening — this is a meaningful jump that could prune more rules than intended, not just the targeted D_zdiv_net_prem
  - Three consecutive weight-adjustment patches all produced 0.0% composite improvement, suggesting the pipeline may be relatively stable/saturated — this structural change may also produce 0.0% and waste an attempt
  - The assumption that divergence rules overlap heavily is plausible but not directly evidenced in diagnostics — no pairwise overlap statistics are provided

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 35.40 | 46.35 |
| WF stability | 0.7033 | 0.7244 |
| Sum composite | 424.92 | 410.42 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (-3.4%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## LLM Budget
- Spend: $1.6204 / $30.00
- Calls: 5 proposer + 5 critic
