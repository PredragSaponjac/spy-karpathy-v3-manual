# PROGRAM — BOUNDED KARPATHY AUTORESEARCH FOR SPY/QQQ → 1 /MES

You are the autonomous research agent working on top of this existing `spy_karpathy_v2` codebase.

Your job is **not** to redesign the whole system. Your job is to make the nightly research loop more Karpathy-like while keeping the live trading core safe.

This repo already has a strong deterministic foundation:
- `prepare_data.py` loads SQLite snapshots and backfills forward returns
- `feature_factory.py` builds normalized / regime-relative features
- `divergence_features.py` builds SPY↔QQQ intermarket features
- `sequence_features.py` builds temporal / chain features
- `rule_compiler.py` generates candidate rules
- `evaluator.py` performs day-based walk-forward evaluation with guardrails
- `report_writer.py` writes a 1 /MES trader-facing report
- `nightly_train.py` orchestrates the nightly run

Treat that deterministic core as the **truth engine**.

## Mission

Build a **bounded Karpathy shell** around this engine so the system can:
1. read last night's diagnostics and failures,
2. propose one small research mutation,
3. rerun the fixed evaluator,
4. accept or reject the mutation,
5. log the result,
6. repeat in a controlled way.

The system must become more adaptive without becoming reckless.

## What counts as success

Success means the challenger hypothesis improves **robustness-adjusted expected trading value for 1 /MES**, not just raw in-sample fit.

Prefer:
- stable multi-day patterns,
- sparse interpretable rules,
- real SPY↔QQQ intermarket logic,
- divergence and sequence states that survive walk-forward,
- better skip logic,
- clear next-day trade sheets.

Avoid:
- rule explosion,
- one-day hero trades,
- regime-only coincidences,
- exact-threshold fetish,
- evaluator rewrites,
- anything that touches live execution logic.

## Trading object

The trade object is **1 /MES contract**.

All final reporting must be understandable in:
- /MES points,
- /MES dollars,
- estimated adverse move,
- suggested stop,
- target range,
- confidence,
- skip conditions.

The DB contains SPY/QQQ snapshot data and forward-return outcome columns.
Do **not** use any legacy `mes_*` schema. Outcome truth comes from:
- `fwd_*`
- `fwd_max_*`
- `label_*`

## Intermarket requirement

QQQ is a first-class intermarket helper for SPY. This is not optional.

The system must explicitly search and evaluate:
- SPY vs QQQ relative strength,
- QQQ lead / SPY lag,
- SPY lead / QQQ lag,
- non-confirmation,
- divergence widening,
- divergence narrowing,
- recoupling,
- divergence chains over multiple snapshots.

## What you may change automatically

You may only mutate a bounded research surface. If these files do not exist yet, create them.

Allowed mutable files:
- `hypothesis.py`
- `search_space.py`
- `ranking_weights.py`
- `feature_proposals.py` (optional, bounded)

These files may control things like:
- enabled rule families,
- feature-family emphasis,
- divergence family emphasis,
- sequence family emphasis,
- support thresholds,
- overlap thresholds,
- promotion thresholds,
- complexity caps,
- move-value weighting,
- skip aggressiveness,
- one new bounded feature family proposal at a time.

## What must remain frozen

Never auto-edit these files:
- `prepare_data.py`
- `feature_factory.py`
- `divergence_features.py`
- `sequence_features.py`
- `evaluator.py`
- `rule_compiler.py`
- `live_rulebook.py`
- DB schema / SQLite collector / backfill logic
- anything that sends or manages live orders

These files are the fixed evaluation core.

## Mutation policy

Each challenger experiment may contain **exactly one bounded mutation**.

Examples of allowed mutations:
- increase or decrease one feature-family weight,
- enable or disable one rule family,
- add or remove one divergence family,
- add or remove one sequence family,
- tighten or loosen one support threshold,
- tighten or loosen one overlap threshold,
- tighten or loosen one promotion threshold,
- add one simple engineered feature family based on an economically meaningful relationship.

Examples of forbidden mutations:
- rewrite evaluator math,
- rewrite live execution,
- invent giant nested composites,
- add unlimited feature search,
- free-form code rewrites across the repo,
- multiple simultaneous hypothesis changes in one experiment.

## Exact-threshold warning

Do not anchor on brittle exact thresholds like `tick < -734` unless the effect is robust across neighboring bands.

Prefer:
- quantiles,
- percentiles,
- z-scores,
- regime-relative states,
- time-of-day-relative states,
- economically meaningful bands.

## Sequence logic requirement

Static states alone are not enough. The agent should value sequence logic highly.

Examples of sequence states worth testing:
- compression → expansion,
- QQQ leads → SPY lags → SPY internals improve → recoupling,
- divergence widens → stalls → narrows,
- acceleration flip after dead tape,
- pin pressure rising then breaking,
- IV crush / spike regime transition.

## Skip logic requirement

Skip logic is a first-class research target.

Good skip rules identify environments where:
- edge is low,
- chop is high,
- path is hostile,
- signals conflict,
- a superficially attractive setup should be ignored.

Do not score skip rules as inverted directional trades. Use the fixed skip scoring path already in `evaluator.py`.

## Karpathy shell design

Build a shell around the existing engine with these components:

### 1. `karpathy_runner.py`
Responsibilities:
- run a baseline nightly pass,
- collect metrics and artifacts,
- ask the proposer for one bounded mutation,
- write challenger config files,
- rerun the nightly engine,
- pass both runs to the judge,
- log the decision.

### 2. `karpathy_judge.py`
Responsibilities:
- compare champion vs challenger using fixed metrics only,
- accept the challenger only if it improves robustness-adjusted utility without increasing fragility,
- write structured decision logs.

### 3. `karpathy_memory.jsonl`
Store for every experiment:
- timestamp,
- baseline metrics,
- proposed mutation,
- challenger metrics,
- accepted/rejected,
- rejection reason or win reason.

### 4. `prompts/proposer.txt`
A concise prompt that asks for one bounded mutation based on the latest diagnostics.

### 5. `prompts/critic.txt`
A red-team prompt that tries to kill the proposed mutation before it runs.

## Judge criteria

The challenger should only win if it improves the system on the fixed evaluator.

Judge on:
- validation utility,
- stability across days,
- concentration by day,
- concentration by regime,
- rule count and simplicity,
- overlap / redundancy,
- skip quality,
- expected net value for 1 /MES.

Reject if the challenger:
- wins only because of one day,
- wins only in one regime,
- increases complexity too much,
- increases overlap too much,
- surfaces too many live-eligible rules,
- worsens skip behavior,
- tells a prettier story but does not improve fixed metrics.

## Maturity gates

Respect these repo maturity tiers. Do not weaken them.

- `<3 days` → `features_only`
- `3–4 days` → `research`
- `5–9 days` → `preliminary`
- `10+ days` → `live`

Before `10+` days, do not emit a real live rulebook.

## Required outputs each night

### Champion report
- top long states,
- top short states,
- top skip states,
- expected move in points and dollars,
- adverse move,
- suggested stop,
- target range,
- confidence.

### Challenger report
- one mutation attempted,
- why it was proposed,
- what changed,
- what improved or worsened.

### Judge decision
- accepted / rejected,
- why,
- whether champion stays.

## Style guidance

Be conservative, empirical, and sparse.

A small number of robust states is better than a large rule zoo.
Do not chase flashiness.
Do not use narrative certainty where the data is weak.
When in doubt, prefer a simpler explanation and a tighter search surface.

## First task

Given this existing repo, add the bounded Karpathy shell cleanly and minimally.
Reuse the current architecture. Do not re-architect the deterministic core.
If a file needed for the bounded shell does not yet exist, create it.
If a README section is needed to explain how to run champion vs challenger nightly experiments, add it.
