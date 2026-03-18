# Karpathy Autoresearch V3 — Bounded Mutation Shell for SPY 0DTE

Automated nightly research layer with a **bounded Karpathy mutation shell** on top of the fixed deterministic SPY/QQQ 0DTE pattern engine.

## How It Works

1. **During market hours**: `spy_engine_v2.py` writes 437-column snapshots to SQLite every 5 seconds
2. **After market close**: This Karpathy layer runs on the accumulated data
3. **It backfills** forward returns (1m, 5m, 15m, 30m, 60m, EOD) and max excursions
4. **It builds** normalized features, intermarket divergences, and temporal sequences
5. **It searches** for patterns across 5 rule types (level, interaction, divergence, sequence, skip)
6. **It evaluates** walk-forward on day-based expanding splits
7. **It promotes** only stable, robust, interpretable patterns
8. **It writes** a human-readable report and machine-readable rulebook for next-day trading

## Quick Start

```bash
cd spy_karpathy_v3

# ── Option A: Deterministic baseline only (no Karpathy mutation) ──
python nightly_train.py

# ── Option B: Full Karpathy loop (champion + up to 3 challengers) ──
python karpathy_runner.py

# ── Option C: Champion baseline only (no mutation attempts) ──
python karpathy_runner.py --champion-only

# ── Option D: Manual mode (paste your own patch JSON) ──
python karpathy_runner.py --manual

# ── Other options ──
python karpathy_runner.py --max-challengers 5    # more attempts
python karpathy_runner.py --db /path/to/spy.db   # custom DB
python karpathy_runner.py --quiet                 # less output
```

### Environment Setup

```bash
# Required for Karpathy LLM proposer/critic
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows (Git Bash)
export PYTHONIOENCODING=utf-8
```

## Output Artifacts

All outputs go to `artifacts/`:

| File | Description |
|------|-------------|
| `nightly_report.md` | Human-readable report for trading 1 /MES |
| `nightly_report.json` | Machine-readable version |
| `rule_leaderboard.csv` | All promoted rules ranked by score |
| `accepted_rules.json` | Full rule definitions with stats |
| `live_rulebook.py` | Importable Python module for live engine |
| `diagnostics.json` | Run metadata and timing |
| `nightly_exec_report.md` | Human-readable nightly execution summary |
| `karpathy_review.md` | Detailed per-attempt challenger review |
| `budget_status.json` | Current LLM spend status |
| `budget_history.jsonl` | Append-only per-call cost log |

## Architecture

```
spy_karpathy_v3/
  ── FROZEN DETERMINISTIC CORE (do not edit) ──
  config.py               # All tunables: /MES conversion, weights, thresholds
  prepare_data.py          # Load SQLite, verify schema, backfill forward returns
  feature_factory.py       # Z-scores, percentiles, quantile bins, regime-relative
  divergence_features.py   # SPY↔QQQ: relative strength, lead-lag, non-confirmation
  sequence_features.py     # Temporal: acceleration, compression, divergence chains
  evaluator.py             # Walk-forward evaluation, utility scoring, overlap detection
  rule_compiler.py         # Generate candidates across 5 rule types
  nightly_train.py         # Deterministic nightly runner
  live_rulebook.py         # Generates importable rules for live engine
  report_writer.py         # Human-readable nightly report

  ── BOUNDED KARPATHY SHELL (mutation layer) ──
  karpathy_runner.py       # Champion vs challenger orchestrator
  karpathy_judge.py        # Fixed-metric deterministic judge
  hypothesis.py            # Mutable research knobs (the ONLY auto-editable config)
  hypothesis_state.json    # Current champion hypothesis (auto-managed)
  search_space.py          # Bounds for every mutable knob
  ranking_weights.py       # Reporting emphasis weights
  diagnostics_packager.py  # JSON context builder for LLM proposer/critic
  budget_guard.py          # LLM spend tracker + hard/soft cap enforcement
  karpathy_memory.jsonl    # Experiment log (append-only)

  ── PROMPTS ──
  prompts/proposer.txt     # LLM prompt: propose one bounded mutation
  prompts/critic.txt       # LLM prompt: try to kill the mutation
  prompts/usage_notes.md   # How to use the prompts

  ── OUTPUT ──
  artifacts/               # Current best artifacts
  artifacts/champion/      # Champion run artifacts
  artifacts/challenger/    # Last challenger run artifacts
```

## Karpathy Shell — How It Works

The Karpathy shell wraps the frozen deterministic engine in a champion-vs-challenger loop:

1. **Champion baseline**: Run `nightly_train.py` with current hypothesis settings
2. **Proposer**: LLM (Sonnet-class) reads diagnostics, proposes ONE bounded mutation
3. **Critic**: LLM tries to kill the patch before it runs (saves compute)
4. **Challenger**: If critic approves, re-run engine with the mutated hypothesis
5. **Judge**: Pure Python comparison — challenger must beat champion on fixed metrics
6. **Memory**: Log the experiment result (accept/reject and why)
7. **Repeat**: Up to N challenger attempts per night

### What the Karpathy shell CAN mutate

- Feature family weights (emphasis in interaction rule generation)
- Enable/disable a rule family (level/interaction/divergence/sequence/skip)
- Divergence family weights (SPY↔QQQ signal emphasis)
- Sequence family weights (temporal pattern emphasis)
- Support/overlap/promotion thresholds
- Skip aggressiveness
- Intermarket weight (QQQ signal importance)
- Move size preference (larger vs smaller signals)

### What the Karpathy shell CANNOT touch

- `evaluator.py` — scoring math is frozen
- `prepare_data.py` — data loading is frozen
- `feature_factory.py` — feature generation is frozen
- `divergence_features.py` — intermarket features are frozen
- `sequence_features.py` — temporal features are frozen
- `rule_compiler.py` — rule generation logic is frozen
- `live_rulebook.py` — live execution is frozen
- DB schema, collector, backfill logic

### Judge Criteria

The challenger only wins if ALL of these pass:
- Sum-of-composites improves by ≥2%
- WF stability does not degrade by >5%
- Day concentration does not worsen by >5pp
- Rule count does not increase by >4
- Skip quality does not degrade
- Net /MES expectancy does not drop by >$1

## Rule Types

| Type | Description | Example |
|------|-------------|---------|
| **A. Level** | Single feature in extreme quintile | GEX in bottom 20% → LONG |
| **B. Interaction** | 2-3 features from different families | Low GEX + High VIX → SHORT |
| **C. Divergence** | SPY vs QQQ disagreement | SPY/QQQ flow non-confirmation → SKIP |
| **D. Sequence** | Multi-snapshot state change | Price compression → expansion → LONG |
| **E. Skip** | When NOT to trade | Low efficiency + midday → avoid |

## /MES Conversion

The DB stores SPY % returns. Conversion to /MES dollars:

```
/MES points = SPY_return_% / 100 × MES_REFERENCE_PRICE
/MES dollars = points × $5/point
Net dollars  = gross - round_trip_cost - slippage
```

Configure in `config.py`:
- `MES_REFERENCE_PRICE = 6030.0` (adjust to current /ES level)
- `ROUND_TRIP_COST_USD = 2.50`
- `SLIPPAGE_TICKS_RT = 2`

## Guardrails

- Max 3 predicates per rule (4 only for elite survivors)
- Max 25 live rules promoted
- Min 30 snapshots support
- Neighbor robustness check (±10% threshold shift)
- Overlap deduplication (Jaccard > 60%)
- Day coverage check (rejects single-day rules)
- Walk-forward required (not just in-sample)

## Maturity Tiers

| Days | Mode | Max Rules | Behavior |
|------|------|-----------|----------|
| <3 | `features_only` | 0 | Builds features and diagnostics only. No rule search. |
| 3–4 | `research` | 8 (4 entry + 4 skip) | Watchlist candidates, 1+ walk-forward fold required |
| 5–9 | `preliminary` | 14 (6 entry + 8 skip) | Not yet live-tradable, 2+ walk-forward folds |
| 10+ | `live` | 24 (6 entry + 12 skip) | Walk-forward validated, writes `live_rulebook.py` |

## Data Requirements

- **Minimum**: 1 day (~5,000 snapshots) — features_only mode (no rule search)
- **Usable**: 3+ days — rule search begins (research mode)
- **Recommended**: 5+ days — reliable pattern discovery (preliminary mode)
- **Ideal**: 10+ days — stable multi-day validation (live mode)

## Overnight Budget Policy

The LLM proposer/critic loop has an automatic budget guard to prevent runaway API spend:

| Parameter | Default | CLI Override |
|-----------|---------|--------------|
| Hard cap | $30.00 | `--hard-budget-usd` |
| Soft cap | $24.00 | `--soft-budget-usd` |
| Max challengers | 5 | `--max-challengers` |

**Behavior:**
- **Below soft cap**: normal operation, launch new challengers freely
- **Soft cap reached**: stop launching new challengers, allow final bookkeeping
- **Hard cap reached**: abort LLM loop immediately, write final artifacts, exit cleanly
- **Champion-only mode**: zero LLM spend (budget tracker still runs, reports $0)

Pricing assumes claude-sonnet-4-6 at $3/Mtok input, $15/Mtok output. Configure in `config.py` under `LLM_*` constants.

**Artifacts produced:**
- `artifacts/budget_status.json` — current spend snapshot (updated after each attempt)
- `artifacts/budget_history.jsonl` — append-only per-call cost log with timestamps

## Nightly Review Reports

After each run, two review files are generated:

**`artifacts/nightly_exec_report.md`** — Short human-readable summary:
- Maturity mode, challenger attempts, accepted/rejected counts
- Top LONG / SHORT / SKIP rules with /MES expectancy
- LLM spend summary

**`artifacts/karpathy_review.md`** — Detailed per-attempt review:
- Proposer idea (summary, patch type, changes, rationale)
- Critic response (verdict, confidence, concerns)
- Deterministic evaluation (champion vs challenger metrics table)
- Judge decision and reason

## Important Notes

- Forward return columns (`fwd_*`, `label_*`) are backfilled after collection
- No `mes_*` columns are used — intentionally removed
- QQQ is a first-class intermarket helper, not optional
- All dollar figures are estimates based on configured assumptions
- This is a research tool, not trading advice

## Experiment Memory

Every challenger attempt is logged to `karpathy_memory.jsonl`:

```json
{
  "timestamp": "2026-03-18T21:30:00",
  "attempt": 1,
  "phase": "judge",
  "patch": {"summary": "increase divergence family weight", ...},
  "champion_metrics": {...},
  "challenger_metrics": {...},
  "decision": {"accepted": false, "reason": "..."}
}
```

Review the memory log to understand what mutations have been tried and why they succeeded or failed. This helps the proposer avoid repeating failed experiments.

**Resetting memory**: When starting a fresh data collection campaign (e.g. after wiping the DB), clear this file so the proposer starts with no stale experiment history:
```bash
echo -n > karpathy_memory.jsonl
```
The file is auto-created on first write if missing. Empty or missing memory is handled cleanly — no errors or warnings.
