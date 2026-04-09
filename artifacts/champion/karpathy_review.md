# Karpathy Detailed Review
**Run:** 2026-04-07 17:03:27  

## Champion Baseline
- Rules: 9 (entry: 6, skip: 3)
- Net expectancy: $36.15
- WF stability: 0.7046
- Sum composite: 428.0923

---
## Attempt 1

### Proposer Idea
- **Summary:** Increase sequence_family_weights.qqq_lead_confirm from 1.0 to 2.0 to surface sequence-based QQQ lead/confirm rules, addressing zero sequence family promotions despite sequence family being enabled and leveraging strong QQQ intermarket signal already visible in level and interaction rules
- **Patch type:** weight_adjustment
- **Changes:** `{"sequence_family_weights": {"qqq_lead_confirm": 2.0}}`
- **Rationale:** Sequence family is enabled but produced zero promoted rules — it is completely absent from the rulebook despite being a valid search surface; QQQ features (qqq_expected_move_pct, qqq_nope) already appear in top-performing rules with $37+ expectancy, suggesting QQQ lead/confirm sequences could surface durable multi-step patterns; Regime concentration is failing (any_regime_concentration_fail: true), and sequence rules — which are inherently multi-snapshot and regime-adaptive — could diversify the rulebook away from static level/divergence conditions; The current rulebook is dominated by divergence (3) and level (2) rules; boosting qqq_lead_confirm sequences could break the family monotony and improve robustness; intermarket_weight is already 1.4 showing prior success with QQQ emphasis; amplifying QQQ-specific sequences is a natural next step

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.58
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - 4 out of 5 recent experiments were rejected for 0% composite improvement, suggesting the search space may be saturated and weight tweaks are not surfacing new rules - this patch may follow the same pattern
  - Boosting a single sub-family weight from 1.0 to 2.0 (a 2x increase) is aggressive for a sub-family that has produced zero promoted rules so far - the reason it produced zero rules may be that the data doesn't support them, not that the weight is too low
  - Regime concentration is already failing; adding sequence rules that are inherently lower-support and potentially regime-specific could worsen rather than improve this
  - The narrative that 'QQQ features work in level/interaction therefore QQQ sequences will work' is a logical leap - features performing well in static conditions doesn't guarantee temporal sequences will

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 36.15 | 36.15 |
| WF stability | 0.7046 | 0.7046 |
| Sum composite | 428.09 | 428.09 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 2

### Proposer Idea
- **Summary:** Reduce min_support from 100 to 40 to allow discovery of higher-precision, lower-frequency rules that may currently be filtered out before evaluation, addressing the stagnation where weight adjustments produce 0% composite improvement
- **Patch type:** threshold_adjustment
- **Changes:** `{"thresholds": {"min_support": 40}}`
- **Rationale:** Five consecutive weight adjustment experiments produced exactly 0.0% composite improvement, indicating the current candidate pool at min_support=100 is saturated — all promotable rules are already being found; The top rule D_zdiv_nope_high_SHORT has only 223 support snapshots across 13 days, meaning high-quality rules can exist at moderate support levels; lowering to 40 opens the search to sharper, less frequent states that fire ~3 times per day; Regime concentration is already failing — surfacing new rules from conditions that fire less frequently may naturally diversify across regimes rather than concentrating in dominant market states; No sequence rules have been promoted despite the family being enabled; sequence conditions like compression_expansion tend to be rarer events that may need lower support thresholds to pass the filter; This is a fundamentally different knob class (threshold) than the weight adjustments that have been repeatedly rejected, providing clean credit assignment on whether the bottleneck is candidate filtering vs. candidate ranking

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.55
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - Reducing min_support from 100 to 40 is a 60% reduction — quite aggressive. At 14 days, 40 snapshots could mean a rule fires on only 2-3 days, creating severe day concentration risk for any newly promoted rules.
  - The existing regime concentration is already failing. Surfacing lower-support rules may worsen this if those rules cluster in one unusual day/regime rather than diversify as hoped.
  - Walk-forward stability estimates become unreliable at 40 snapshots over 14 days — a rule could achieve high WF stability by hitting well on just 2 folds while being absent from most.

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 36.15 | 36.15 |
| WF stability | 0.7046 | 0.7046 |
| Sum composite | 428.09 | 428.98 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.2%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 3

### Proposer Idea
- **Summary:** Increase move_size_preference from 2.0 to 1.2 to reduce bias toward large moves and allow more moderate-but-durable trade signals to surface, addressing regime concentration failure
- **Patch type:** scalar_adjustment
- **Changes:** `{"move_size_preference": 1.2}`
- **Rationale:** move_size_preference is already maxed at 2.0, which heavily biases toward large moves — yet regime concentration is still failing, suggesting the system is over-indexing on a narrow set of large-move conditions that cluster in specific regimes; The worst entry rule (D_zdiv_net_prem_high_SHORT_60m) has negative expectancy (-$1.29) despite passing promotion — this may be surviving because it captures large adverse moves that satisfy the move_size_preference but lack robustness; Reducing move_size_preference to 1.2 (still above neutral) should broaden the candidate pool to include moderate-sized but more regime-diverse moves, potentially addressing the regime concentration flag; Recent experiments have tried weight adjustments (0% improvement), overlap tightening (-3.4%), and support reduction (0.2%) — all failed to clear the 2% hurdle. This scalar has not been tested and directly affects which candidates score highest in the ranking pipeline

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.62
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - This is an untested scalar that directly changes the ranking pipeline's candidate selection — at 14 days, the effect could be hard to distinguish from noise
  - Reducing move_size_preference from 2.0 to 1.2 is a large jump (40% reduction) — a more incremental step to 1.5 would be safer and more testable
  - The causal link between move_size_preference and regime concentration failure is plausible but speculative — regime concentration could be driven by the dominance of divergence family (3/6 entry rules) rather than move size bias

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 36.15 | 36.15 |
| WF stability | 0.7046 | 0.7046 |
| Sum composite | 428.09 | 340.36 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (-20.5%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 4

### Proposer Idea
- **Summary:** Increase divergence_family_weights.z_score_div from 1.0 to 1.8 to amplify the strongest performing rule family sub-type, where z_score_div rules hold the top composite (73.0) and best net expectancy ($51.89) among all promoted rules
- **Patch type:** weight_adjustment
- **Changes:** `{"divergence_family_weights": {"z_score_div": 1.8}}`
- **Rationale:** The top promoted rule D_zdiv_nope_high_SHORT_60m (composite 73.0, $51.89 net exp, 0.78 wf_stability) is a z_score_div divergence rule — the single strongest rule in the entire rulebook; Two of the three divergence rules use z_score_div features (zdiv_nope_state, zdiv_vex_state, zdiv_net_prem_state), and divergence family has highest avg_composite (52.34) among entry families; The regime concentration failure suggests we need more diverse rule discovery; boosting z_score_div weight should help the candidate generator explore more z-score divergence thresholds and conditions, potentially surfacing new high-quality variants across different regimes; Previous rejected attempts targeted sequence weights (0% improvement), min_support (0.2%), max_overlap (-3.4%), structure weights (0%), and move_size_preference (-20.5%) — divergence_family_weights have not been tried this session

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.52
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - Boosting z_score_div weight risks deepening the already-failing regime concentration by doubling down on the dominant divergence family (3 of 6 entry rules are already divergence)
  - The diagnostics explicitly flag regime concentration failure, and amplifying the already-strongest sub-family is the opposite of diversification — it's concentration chasing
  - All three z_score_div rules already made it through promotion at weight 1.0; raising to 1.8 may just generate near-duplicate variants of existing zdiv rules that get pruned by overlap anyway
  - Five consecutive rejected patches this session suggest the rulebook may be near a local optimum for 14 days of data — another weight tweak is unlikely to clear the 2% composite improvement bar

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 36.15 | 36.15 |
| WF stability | 0.7046 | 0.7046 |
| Sum composite | 428.09 | 428.09 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## Attempt 5

### Proposer Idea
- **Summary:** Raise min_composite_score from 0.0 to 3.0 to prune weak candidates earlier, freeing promotion slots for stronger rules and addressing regime concentration failure by eliminating marginal rules like D_zdiv_net_prem (net_exp -$1.29)
- **Patch type:** threshold_adjustment
- **Changes:** `{"thresholds": {"min_composite_score": 3.0}}`
- **Rationale:** One promoted entry rule (D_zdiv_net_prem_high_SHORT_60m) has negative net expectancy (-$1.29) and composite of only 59.07, dragging down overall divergence family performance and occupying a promotion slot; Regime concentration is already failing (any_regime_concentration_fail=true), suggesting marginal rules are fitting narrow regimes rather than durable states — raising the floor should filter these out; The interaction family has only 1 rule (composite 43.29) and sequence family has 0 promotions, suggesting weak candidates are crowding out potentially better rules from underrepresented families; This knob has NOT been tried in any recent experiment — all 5 recent attempts were weight_adjustments, threshold.min_support, move_size_preference, and threshold.max_overlap, so this is a fresh direction

### Critic Response
- **Verdict:** cautious_approve
- **Confidence:** 0.62
- **Recommendation:** run_with_extra_caution
- **Concerns:**
  - min_composite_score of 3.0 is extremely low — the weakest promoted rule has composite 43.29, so a floor of 3.0 will not prune ANY currently promoted rule, making the claimed benefit of removing D_zdiv_net_prem (composite 59.07) incorrect
  - The patch narrative claims it will remove the negative-expectancy rule, but composite 59.07 >> 3.0, so this rule will survive the filter unchanged — the proposer appears to misunderstand what this knob controls
  - This is likely a no-op or near-no-op: if min_composite_score filters candidates before promotion, a threshold of 3.0 out of 6297 candidates will prune only the absolute worst noise, which may already be filtered by other gates

### Deterministic Evaluation
| Metric | Champion | Challenger |
|--------|----------|------------|
| Rules | 9.00 | 9.00 |
| Net exp $/MES | 36.15 | 36.15 |
| WF stability | 0.7046 | 0.7046 |
| Sum composite | 428.09 | 428.09 |
| Day concentration | 0.00 | 0.00 |

### Judge Decision
- **✗ REJECTED**
- **Reason:** All guardrails pass but composite improvement (0.0%) below minimum threshold (2%). No structural simplification qualifies for LATERAL_PROMOTE. Champion retained.

---
## LLM Budget
- Spend: $1.6239 / $30.00
- Calls: 5 proposer + 5 critic
