"""
Karpathy Autoresearch — Runner (Champion vs Challenger Loop)

This is the top-level entry point for the bounded Karpathy shell.
It wraps the existing deterministic nightly_train.py pipeline.

Flow:
  1. Run champion baseline (current hypothesis + fixed engine)
  2. Package diagnostics for proposer
  3. Call proposer LLM → get one bounded patch
  4. Call critic LLM → approve/reject before running
  5. If approved: apply patch, run challenger
  6. Fixed judge compares champion vs challenger
  7. Log result to karpathy_memory.jsonl
  8. If challenger wins: update hypothesis_state.json

Usage:
    python karpathy_runner.py                     # full loop (needs ANTHROPIC_API_KEY)
    python karpathy_runner.py --max-challengers 3 # up to 3 attempts
    python karpathy_runner.py --manual             # no LLM — paste patch JSON manually
    python karpathy_runner.py --champion-only      # just run baseline, no mutation
    python karpathy_runner.py --db path/to.db      # custom DB path
    python karpathy_runner.py --hard-budget-usd 50 # override hard cap
    python karpathy_runner.py --soft-budget-usd 40 # override soft cap
"""
import argparse
import json
import os
import sys
import time
import copy
from datetime import datetime
from pathlib import Path

# Ensure sibling imports work
sys.path.insert(0, str(Path(__file__).parent))

import hashlib

from config import DB_PATH, ARTIFACTS_DIR, MIN_SUPPORT, get_maturity_tier
import config as config_module
from hypothesis import load_hypothesis, save_hypothesis, apply_patch
from search_space import validate_patch
from diagnostics_packager import package_from_artifacts, format_proposer_context, format_critic_context
from karpathy_judge import extract_metrics, judge, judge_first_run
from nightly_train import run_nightly
from evaluator import clear_baseline_cache
from budget_guard import BudgetTracker, BudgetConfig
from checkpoint_manager import save_checkpoint

# ── Paths ─────────────────────────────────────────────────────────────
MEMORY_PATH = Path(__file__).parent / "karpathy_memory.jsonl"
PROMPTS_DIR = Path(__file__).parent / "prompts"
CHAMPION_ARTIFACTS = ARTIFACTS_DIR / "champion"
CHALLENGER_ARTIFACTS = ARTIFACTS_DIR / "challenger"

BUDGET_STATUS_PATH = ARTIFACTS_DIR / "budget_status.json"
BUDGET_HISTORY_PATH = ARTIFACTS_DIR / "budget_history.jsonl"
NIGHTLY_EXEC_REPORT_PATH = ARTIFACTS_DIR / "nightly_exec_report.md"
KARPATHY_REVIEW_PATH = ARTIFACTS_DIR / "karpathy_review.md"


# ── Config Override Context Manager ───────────────────────────────────

class HypothesisOverride:
    """Temporarily override config.py values from a hypothesis dict.

    This is the ONLY way the Karpathy shell affects the frozen engine.
    It monkey-patches config module attributes, runs the pipeline,
    then restores them.  evaluator.py and rule_compiler.py read these
    via ``import config as _cfg`` so changes propagate at call time.
    """

    # Map hypothesis key → config module attribute
    _THRESHOLD_MAP = {
        "min_support":         ("MIN_SUPPORT",         int),
        "neighbor_band_pct":   ("NEIGHBOR_BAND_PCT",   float),
        "max_overlap":         ("MAX_OVERLAP",         float),
        "min_composite_score": ("MIN_COMPOSITE_SCORE", float),
    }

    _SCALAR_MAP = {
        "skip_aggressiveness":  ("SKIP_AGGRESSIVENESS",  float),
        "intermarket_weight":   ("INTERMARKET_WEIGHT",   float),
        "move_size_preference": ("MOVE_SIZE_PREFERENCE", float),
    }

    _DICT_MAP = {
        "rule_families":             "RULE_FAMILIES_ENABLED",
        "feature_family_weights":    "FEATURE_FAMILY_WEIGHTS",
        "divergence_family_weights": "DIVERGENCE_FAMILY_WEIGHTS",
        "sequence_family_weights":   "SEQUENCE_FAMILY_WEIGHTS",
    }

    def __init__(self, hypothesis: dict):
        self.hypothesis = hypothesis
        self._saved = {}

    def __enter__(self):
        # ── Thresholds ────────────────────────────────────────────────
        thresholds = self.hypothesis.get("thresholds", {})
        for hyp_key, (cfg_attr, cast) in self._THRESHOLD_MAP.items():
            if hyp_key in thresholds:
                self._saved[cfg_attr] = getattr(config_module, cfg_attr, None)
                setattr(config_module, cfg_attr, cast(thresholds[hyp_key]))

        # ── Scalar knobs ──────────────────────────────────────────────
        for hyp_key, (cfg_attr, cast) in self._SCALAR_MAP.items():
            if hyp_key in self.hypothesis:
                self._saved[cfg_attr] = getattr(config_module, cfg_attr, None)
                setattr(config_module, cfg_attr, cast(self.hypothesis[hyp_key]))

        # ── Dict knobs (rule families, weights) ───────────────────────
        for hyp_key, cfg_attr in self._DICT_MAP.items():
            if hyp_key in self.hypothesis:
                self._saved[cfg_attr] = getattr(config_module, cfg_attr, None)
                setattr(config_module, cfg_attr, self.hypothesis[hyp_key])

        return self

    def __exit__(self, *args):
        # Restore all overridden values
        for attr, val in self._saved.items():
            if val is not None:
                setattr(config_module, attr, val)
            else:
                try:
                    delattr(config_module, attr)
                except AttributeError:
                    pass


# ── LLM Integration ──────────────────────────────────────────────────

import re as _re

def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM response text.

    Tries in order:
      1. Direct json.loads (works when assistant prefill gives clean JSON)
      2. Find first { ... last } and parse that substring
      3. Strip markdown fences and retry
    Returns None if all attempts fail.
    """
    # Attempt 1: direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 2: extract outermost { ... }
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    # Attempt 3: strip markdown fences
    cleaned = _re.sub(r'^```(?:json)?\s*', '', text, flags=_re.MULTILINE)
    cleaned = _re.sub(r'\s*```\s*$', '', cleaned, flags=_re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        pass

    return None


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _extract_usage(response) -> tuple:
    """Extract (input_tokens, output_tokens) from an Anthropic API response.

    Returns (None, None) if usage metadata is unavailable.
    """
    try:
        usage = response.usage
        return (usage.input_tokens, usage.output_tokens)
    except (AttributeError, TypeError):
        return (None, None)


def call_proposer(
    diagnostics_context: str,
    model: str = "claude-sonnet-4-6",
    budget: BudgetTracker = None,
    challenger_index: int = 0,
) -> dict:
    """Call the proposer LLM to get a bounded patch suggestion.

    Returns the parsed JSON patch, or None on failure.
    Supports MANUAL_MODE: saves prompt to file, waits for human response.
    """
    prompt_template = _load_prompt("proposer.txt")
    if not prompt_template:
        print("  [WARN] prompts/proposer.txt not found.")
        return None

    # ── Budget pre-check ──────────────────────────────────────────
    if budget:
        proj_in = budget.cfg.projected_proposer_input_tokens
        proj_out = budget.cfg.projected_proposer_output_tokens
        if not budget.can_run_call(proj_in, proj_out):
            print("  [BUDGET] Hard cap would be exceeded. Skipping proposer call.")
            budget._stop_reason = "hard_cap"
            return None

    user_message = (
        f"{prompt_template}\n\n"
        f"--- TONIGHT'S DIAGNOSTICS ---\n"
        f"{diagnostics_context}\n"
        f"--- END DIAGNOSTICS ---\n\n"
        f"Return ONLY valid JSON. No markdown fences. No explanation outside the JSON."
    )

    # ── MANUAL MODE: save prompt, wait for human response ─────────
    manual_mode = os.environ.get("KARPATHY_MANUAL_MODE", "0").lower() in ("1", "true", "yes")
    if manual_mode:
        from manual_bridge import manual_llm_call
        print(f"\n  [MANUAL] Proposer call — paste into Claude and return JSON response")
        text = manual_llm_call(
            role="proposer",
            system_prompt="You are a quantitative research proposer. Return ONLY valid JSON.",
            user_prompt=user_message,
            model_hint=model,
        )
        # Ensure it starts with {
        text = text.strip()
        if not text.startswith("{"):
            text = "{" + text.split("{", 1)[-1] if "{" in text else text

        parsed = _extract_json(text)
        if parsed is None:
            print(f"  [ERROR] Could not extract valid JSON from manual proposer response")
            return None
        return parsed

    # ── API MODE ──────────────────────────────────────────────────
    try:
        import anthropic
    except ImportError:
        print("  [WARN] anthropic package not installed. Use --manual mode.")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [WARN] ANTHROPIC_API_KEY not set. Use --manual mode.")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    try:
        # Request JSON output directly (no assistant prefill — unsupported on newer models)
        response = client.messages.create(
            model=model,
            max_tokens=budget.cfg.max_output_tokens_per_call if budget else 2000,
            messages=[
                {"role": "user", "content": user_message + "\n\nReturn ONLY the raw JSON object. No markdown fences, no explanation."},
            ],
        )
        text = response.content[0].text.strip()

        # Record usage
        if budget:
            actual_in, actual_out = _extract_usage(response)
            if actual_in is not None:
                budget.add_usage(actual_in, actual_out, "proposer",
                                 model=model, actual=True,
                                 challenger_index=challenger_index)
            else:
                budget.add_usage(proj_in, proj_out, "proposer",
                                 model=model, actual=False,
                                 challenger_index=challenger_index,
                                 decision_context="usage unavailable, using projection")

        parsed = _extract_json(text)
        if parsed is None:
            print(f"  [ERROR] Could not extract valid JSON from proposer response")
            print(f"  [DEBUG] First 300 chars: {text[:300]}")
            return None
        return parsed
    except Exception as e:
        print(f"  [ERROR] Proposer call failed: {e}")
        if budget:
            budget.add_usage(proj_in, proj_out // 4, "proposer",
                             model=model, actual=False,
                             challenger_index=challenger_index,
                             decision_context=f"call failed: {e}")
        return None


def call_critic(
    critic_context: str,
    model: str = "claude-sonnet-4-6",
    budget: BudgetTracker = None,
    challenger_index: int = 0,
) -> dict:
    """Call the critic LLM to evaluate a proposed patch.

    Returns parsed JSON verdict, or None on failure.
    Supports MANUAL_MODE: saves prompt to file, waits for human response.
    """
    prompt_template = _load_prompt("critic.txt")
    if not prompt_template:
        return None

    # ── Budget pre-check ──────────────────────────────────────────
    if budget:
        proj_in = budget.cfg.projected_critic_input_tokens
        proj_out = budget.cfg.projected_critic_output_tokens
        if not budget.can_run_call(proj_in, proj_out):
            print("  [BUDGET] Hard cap would be exceeded. Skipping critic call.")
            budget._stop_reason = "hard_cap"
            return None

    user_message = (
        f"{prompt_template}\n\n"
        f"--- CONTEXT ---\n"
        f"{critic_context}\n"
        f"--- END CONTEXT ---\n\n"
        f"Return ONLY valid JSON. No markdown fences."
    )

    # ── MANUAL MODE: save prompt, wait for human response ─────────
    manual_mode = os.environ.get("KARPATHY_MANUAL_MODE", "0").lower() in ("1", "true", "yes")
    if manual_mode:
        from manual_bridge import manual_llm_call
        print(f"\n  [MANUAL] Critic call — paste into Claude and return JSON response")
        text = manual_llm_call(
            role="critic",
            system_prompt="You are a quantitative research critic. Return ONLY valid JSON.",
            user_prompt=user_message,
            model_hint=model,
        )
        text = text.strip()
        if not text.startswith("{"):
            text = "{" + text.split("{", 1)[-1] if "{" in text else text

        parsed = _extract_json(text)
        if parsed is None:
            print(f"  [ERROR] Could not extract valid JSON from manual critic response")
            return None
        return parsed

    # ── API MODE ──────────────────────────────────────────────────
    try:
        import anthropic
    except ImportError:
        print("  [WARN] anthropic package not installed.")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    try:
        # Request JSON output directly (no assistant prefill — unsupported on newer models)
        response = client.messages.create(
            model=model,
            max_tokens=budget.cfg.max_output_tokens_per_call if budget else 1500,
            messages=[
                {"role": "user", "content": user_message + "\n\nReturn ONLY the raw JSON object. No markdown fences, no explanation."},
            ],
        )
        text = response.content[0].text.strip()

        # Record usage
        if budget:
            actual_in, actual_out = _extract_usage(response)
            if actual_in is not None:
                budget.add_usage(actual_in, actual_out, "critic",
                                 model=model, actual=True,
                                 challenger_index=challenger_index)
            else:
                budget.add_usage(proj_in, proj_out, "critic",
                                 model=model, actual=False,
                                 challenger_index=challenger_index,
                                 decision_context="usage unavailable, using projection")

        parsed = _extract_json(text)
        if parsed is None:
            print(f"  [ERROR] Could not extract valid JSON from critic response")
            return None
        return parsed
    except Exception as e:
        print(f"  [ERROR] Critic call failed: {e}")
        if budget:
            budget.add_usage(proj_in, proj_out // 4, "critic",
                             model=model, actual=False,
                             challenger_index=challenger_index,
                             decision_context=f"call failed: {e}")
        return None


# ── Artifact Management ───────────────────────────────────────────────

def _copy_artifacts(src_dir: Path, dest_dir: Path):
    """Copy all artifact files from src to dest.

    Cleans dest first so stale files from prior runs don't persist.
    This ensures champion/challenger snapshots are internally consistent
    (e.g. no stale live_rulebook.py when rules_promoted == 0).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Remove stale files in dest that aren't in src
    src_files = {f.name for f in src_dir.glob("*") if f.is_file()}
    for f in dest_dir.glob("*"):
        if f.is_file() and f.name not in src_files:
            f.unlink()
    # Copy current files
    for f in src_dir.glob("*"):
        if f.is_file():
            (dest_dir / f.name).write_bytes(f.read_bytes())


def _validate_champion_consistency(champion_dir: Path, diagnostics: dict):
    """Validate that champion artifacts are internally consistent.

    If rules_promoted == 0, live_rulebook.py must not contain active rules.
    Prints a warning if inconsistency is detected (does not crash).
    """
    rules_promoted = diagnostics.get('rules_promoted', 0)
    rulebook_path = champion_dir / 'live_rulebook.py'

    if rules_promoted == 0 and rulebook_path.exists():
        content = rulebook_path.read_text(encoding='utf-8')
        # Check if RULES list has any entries (non-empty list)
        if 'RULES = [' in content:
            # Find what's between RULES = [ and ]
            start = content.index('RULES = [') + len('RULES = [')
            end = content.index(']', start)
            rules_content = content[start:end].strip()
            if rules_content:
                print(f"  [WARN] Champion artifact inconsistency: "
                      f"rules_promoted=0 but live_rulebook.py has active rules. "
                      f"Overwriting with empty rulebook.")
                from live_rulebook import write_live_rulebook
                write_live_rulebook([], rulebook_path)


def _load_rules(artifacts_dir: Path) -> list:
    """Load accepted_rules.json from an artifacts directory."""
    path = artifacts_dir / "accepted_rules.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def _load_diagnostics(artifacts_dir: Path) -> dict:
    """Load diagnostics.json from an artifacts directory."""
    path = artifacts_dir / "diagnostics.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


# ── Memory Log ────────────────────────────────────────────────────────

def log_experiment(entry: dict):
    """Append one experiment to karpathy_memory.jsonl."""
    with open(MEMORY_PATH, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def load_memory(last_n: int = 20) -> list:
    """Load the last N experiments from memory."""
    if not MEMORY_PATH.exists():
        return []
    entries = []
    with open(MEMORY_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries[-last_n:]


# ── Nightly Review Report Writers ─────────────────────────────────────

def _write_nightly_exec_report(
    run_ts: str,
    elapsed: float,
    champion_metrics: dict,
    attempt_log: list,
    budget: BudgetTracker,
    maturity_tier: dict,
    n_days: int,
    champion_rules: list,
):
    """Write artifacts/nightly_exec_report.md — short human-readable summary."""
    lines = []
    lines.append(f"# Karpathy Nightly Execution Report")
    lines.append(f"**Generated:** {run_ts}  ")
    lines.append(f"**Elapsed:** {elapsed:.1f}s  ")
    lines.append(f"**Maturity:** {maturity_tier.get('label', 'unknown')} ({n_days} days)  ")
    lines.append("")

    # ── Challenger summary
    total = len(attempt_log)
    accepted = sum(1 for a in attempt_log if a.get("accepted"))
    rejected = total - accepted
    lines.append(f"## Challenger Summary")
    lines.append(f"- Attempts: **{total}**")
    lines.append(f"- Accepted: **{accepted}**")
    lines.append(f"- Rejected: **{rejected}**")
    if budget.stop_reason:
        label = "Soft cap ($%.2f)" % budget.cfg.soft_budget_usd if budget.stop_reason == "soft_cap" else "Hard cap ($%.2f)" % budget.cfg.hard_budget_usd
        lines.append(f"- Stopped by: **{label}**")
    lines.append("")

    # ── Top rules by direction
    entry_long = [r for r in champion_rules if r.get("direction") == "LONG"]
    entry_short = [r for r in champion_rules if r.get("direction") == "SHORT"]
    skip_rules = [r for r in champion_rules if r.get("direction") == "SKIP"]

    def _top3(rules):
        return sorted(rules, key=lambda x: x.get("composite_score", 0), reverse=True)[:3]

    if entry_long:
        lines.append("## Top LONG Rules")
        for r in _top3(entry_long):
            exp = r.get("mes_net_expectancy_usd", 0)
            lines.append(f"- **{r.get('name', '?')}** — ${exp:.2f}/MES, WF {r.get('wf_stability', 0):.2f}, composite {r.get('composite_score', 0):.4f}")
        lines.append("")

    if entry_short:
        lines.append("## Top SHORT Rules")
        for r in _top3(entry_short):
            exp = r.get("mes_net_expectancy_usd", 0)
            lines.append(f"- **{r.get('name', '?')}** — ${exp:.2f}/MES, WF {r.get('wf_stability', 0):.2f}, composite {r.get('composite_score', 0):.4f}")
        lines.append("")

    if skip_rules:
        lines.append("## Top SKIP Rules")
        for r in _top3(skip_rules):
            lines.append(f"- **{r.get('name', '?')}** — composite {r.get('composite_score', 0):.4f}, support {r.get('support', 0)}")
        lines.append("")

    # ── /MES expectancy summary
    entry_rules = [r for r in champion_rules if r.get("direction") != "SKIP"]
    if entry_rules:
        net_exps = [r.get("mes_net_expectancy_usd", 0) for r in entry_rules]
        mfes = [r.get("mes_median_mfe_usd", 0) for r in entry_rules]
        maes = [r.get("mes_median_mae_usd", 0) for r in entry_rules]
        lines.append("## /MES Expectancy (1 contract)")
        lines.append(f"- Mean net expectancy: **${sum(net_exps)/len(net_exps):.2f}**")
        lines.append(f"- Best: ${max(net_exps):.2f} / Worst: ${min(net_exps):.2f}")
        if mfes and any(m != 0 for m in mfes):
            lines.append(f"- Median MFE (favorable): ${sum(mfes)/len(mfes):.2f}")
        if maes and any(m != 0 for m in maes):
            lines.append(f"- Median MAE (adverse):   ${sum(maes)/len(maes):.2f}")
        lines.append("")

    # ── Divergence family contributions
    diag_path = ARTIFACTS_DIR / "diagnostics.json"
    if diag_path.exists():
        try:
            import json as _json
            with open(diag_path) as _f:
                _diag = _json.load(_f)
            from diagnostics_packager import _get_divergence_family_counts
            div_fam = _get_divergence_family_counts(_diag)
            lines.append("## Divergence Family Contributions")
            for tier_name in ["primary", "secondary", "tertiary"]:
                tc = div_fam.get(tier_name, {})
                base = tc.get("base_metrics", 0)
                total_c = tc.get("total_columns", 0)
                pct = tc.get("pct_of_pool", 0)
                lines.append(f"- **{tier_name.upper()}**: {base} base, "
                             f"{total_c} total columns ({pct:.1f}%)")
            lines.append(f"- Total divergence columns: "
                         f"**{div_fam.get('total_divergence_columns', 0)}**")
            lines.append("")
        except Exception:
            pass  # non-critical, skip if anything fails

    # ── LLM spend
    lines.append("## LLM Spend")
    lines.append(f"- Total: **${budget.spend_so_far_usd:.4f}**")
    lines.append(f"- Proposer calls: {budget.proposer_calls}")
    lines.append(f"- Critic calls: {budget.critic_calls}")
    lines.append(f"- Remaining: ${budget.remaining_budget():.2f} of ${budget.cfg.hard_budget_usd:.2f} hard cap")
    lines.append("")

    NIGHTLY_EXEC_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_karpathy_review(
    run_ts: str,
    champion_metrics: dict,
    attempt_log: list,
    budget: BudgetTracker,
):
    """Write artifacts/karpathy_review.md — detailed per-attempt review."""
    lines = []
    lines.append(f"# Karpathy Detailed Review")
    lines.append(f"**Run:** {run_ts}  ")
    lines.append("")

    lines.append(f"## Champion Baseline")
    lines.append(f"- Rules: {champion_metrics.get('total_rules', 0)} "
                 f"(entry: {champion_metrics.get('n_entry', 0)}, skip: {champion_metrics.get('n_skip', 0)})")
    lines.append(f"- Net expectancy: ${champion_metrics.get('mean_net_expectancy_usd', 0):.2f}")
    lines.append(f"- WF stability: {champion_metrics.get('mean_wf_stability', 0):.4f}")
    lines.append(f"- Sum composite: {champion_metrics.get('sum_composite', 0):.4f}")
    lines.append("")

    if not attempt_log:
        lines.append("*No challenger attempts were made.*\n")
    else:
        for i, att in enumerate(attempt_log, 1):
            lines.append(f"---")
            lines.append(f"## Attempt {i}")
            lines.append("")

            # Proposer idea
            patch = att.get("patch", {})
            lines.append(f"### Proposer Idea")
            lines.append(f"- **Summary:** {patch.get('summary', 'n/a')}")
            lines.append(f"- **Patch type:** {patch.get('patch_type', 'n/a')}")
            changes = patch.get("changes", {})
            if changes:
                lines.append(f"- **Changes:** `{json.dumps(changes, default=str)}`")
            # Proposer uses "why" (array); support both for backwards compat
            why = patch.get('why', patch.get('rationale', []))
            if isinstance(why, list):
                why = '; '.join(why) if why else 'n/a'
            lines.append(f"- **Rationale:** {why}")
            lines.append("")

            # Outcome phase
            phase = att.get("phase", "unknown")

            if phase == "bounds_check":
                lines.append(f"### Outcome: REJECTED at bounds check")
                for err in att.get("errors", []):
                    lines.append(f"- {err}")
                lines.append("")
                continue

            # Critic response
            critic = att.get("critic_verdict")
            if critic:
                lines.append(f"### Critic Response")
                lines.append(f"- **Verdict:** {critic.get('verdict', 'n/a')}")
                lines.append(f"- **Confidence:** {critic.get('confidence', 'n/a')}")
                lines.append(f"- **Recommendation:** {critic.get('recommendation', 'n/a')}")
                concerns = critic.get("main_concerns", [])
                if concerns:
                    lines.append(f"- **Concerns:**")
                    for c in concerns:
                        lines.append(f"  - {c}")
                lines.append("")

                if phase == "critic":
                    lines.append(f"### Outcome: KILLED by critic (no engine run)")
                    lines.append("")
                    continue

            # Challenger vs champion
            challenger_m = att.get("challenger_metrics")
            if challenger_m:
                lines.append(f"### Deterministic Evaluation")
                lines.append(f"| Metric | Champion | Challenger |")
                lines.append(f"|--------|----------|------------|")
                champ_m = att.get("champion_at_time", champion_metrics)
                for key, label in [
                    ("total_rules", "Rules"),
                    ("mean_net_expectancy_usd", "Net exp $/MES"),
                    ("mean_wf_stability", "WF stability"),
                    ("sum_composite", "Sum composite"),
                    ("max_day_concentration", "Day concentration"),
                ]:
                    cv = champ_m.get(key, 0)
                    av = challenger_m.get(key, 0)
                    fmt = ".4f" if isinstance(cv, float) and cv < 10 else ".2f"
                    lines.append(f"| {label} | {cv:{fmt}} | {av:{fmt}} |")
                lines.append("")

            # Judge decision
            decision = att.get("decision")
            if decision:
                lines.append(f"### Judge Decision")
                status = "✓ ACCEPTED" if decision.get("accepted") else "✗ REJECTED"
                lines.append(f"- **{status}**")
                lines.append(f"- **Reason:** {decision.get('reason', 'n/a')}")
                lines.append("")

    # Budget summary at bottom
    lines.append("---")
    lines.append(f"## LLM Budget")
    lines.append(f"- Spend: ${budget.spend_so_far_usd:.4f} / ${budget.cfg.hard_budget_usd:.2f}")
    lines.append(f"- Calls: {budget.proposer_calls} proposer + {budget.critic_calls} critic")
    if budget.stop_reason:
        lines.append(f"- **Run stopped by {budget.stop_reason}**")
    lines.append("")

    KARPATHY_REVIEW_PATH.write_text("\n".join(lines), encoding="utf-8")


# ── Champion Caching ──────────────────────────────────────────────────

_champion_cache = {}  # module-level cache, cleared between karpathy_runner invocations


def _compute_data_hash(db_path: Path) -> str:
    """Hash the DB file's modification time + size.

    Not a content hash (too slow for large DBs). Sufficient because
    the DB only changes when the collector appends new data.
    """
    try:
        stat = db_path.stat()
        key = f"{stat.st_mtime_ns}:{stat.st_size}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    except OSError:
        return "no_db"


def _compute_hypothesis_hash(hypothesis: dict) -> str:
    """Hash the hypothesis dict for cache keying."""
    serialized = json.dumps(hypothesis, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _get_cached_champion(data_hash: str, hyp_hash: str):
    """Return cached (diagnostics, rules, metrics) or None if cache miss."""
    key = f"{data_hash}:{hyp_hash}"
    cached = _champion_cache.get(key)
    if cached:
        print(f"  [CACHE] Champion cache HIT (data={data_hash[:8]}, hyp={hyp_hash[:8]})")
        return cached
    return None


def _set_champion_cache(data_hash: str, hyp_hash: str,
                        diagnostics: dict, rules: list, metrics: dict):
    """Store champion results in cache."""
    key = f"{data_hash}:{hyp_hash}"
    _champion_cache[key] = (diagnostics, rules, metrics)
    print(f"  [CACHE] Champion cached (data={data_hash[:8]}, hyp={hyp_hash[:8]})")


# ── Main Runner ───────────────────────────────────────────────────────

def run_karpathy(
    db_path: Path = DB_PATH,
    max_challengers: int = None,
    manual: bool = False,
    champion_only: bool = False,
    model: str = None,
    verbose: bool = True,
    hard_budget_usd: float = None,
    soft_budget_usd: float = None,
):
    """Run the full bounded Karpathy loop.

    1. Run champion baseline
    2. For up to max_challengers attempts:
       a. Proposer suggests a patch
       b. Critic evaluates the patch
       c. If approved: run challenger
       d. Judge compares
       e. If challenger wins: update champion
    """
    start_time = time.time()
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Initialize budget tracker ─────────────────────────────────────
    budget_cfg = BudgetConfig()
    if hard_budget_usd is not None:
        budget_cfg.hard_budget_usd = hard_budget_usd
    if soft_budget_usd is not None:
        budget_cfg.soft_budget_usd = soft_budget_usd
    if max_challengers is not None:
        budget_cfg.max_challengers = max_challengers
    if model:
        budget_cfg.default_model = model

    # Resolve effective values
    eff_max = budget_cfg.max_challengers
    eff_model = budget_cfg.default_model

    budget = BudgetTracker(budget_cfg)

    print("=" * 80)
    print("  KARPATHY AUTORESEARCH — BOUNDED MUTATION LOOP")
    print(f"  {run_ts}")
    print(f"  Max challengers: {eff_max}")
    print(f"  Mode: {'manual' if manual else 'auto'}")
    print(f"  Budget: soft ${budget_cfg.soft_budget_usd:.2f} / hard ${budget_cfg.hard_budget_usd:.2f}")
    print(f"  Model: {eff_model}")
    print("=" * 80)

    # ── Step 1: Run champion baseline (with caching) ─────────────────
    print("\n" + "─" * 60)
    print("  PHASE 1: CHAMPION BASELINE")
    print("─" * 60)

    hypothesis = load_hypothesis()

    # Compute cache keys
    data_hash = _compute_data_hash(db_path)
    hyp_hash = _compute_hypothesis_hash(hypothesis)

    # Check cache
    cached = _get_cached_champion(data_hash, hyp_hash)
    if cached is not None:
        champion_diag, champion_rules, champion_metrics = cached
    else:
        with HypothesisOverride(hypothesis):
            clear_baseline_cache()  # FIX: fresh cache for each run
            champion_diag = run_nightly(db_path=db_path, verbose=verbose)

        # Save champion artifacts
        _copy_artifacts(ARTIFACTS_DIR, CHAMPION_ARTIFACTS)
        _validate_champion_consistency(CHAMPION_ARTIFACTS, champion_diag)
        champion_rules = _load_rules(ARTIFACTS_DIR)
        champion_metrics = extract_metrics(champion_diag, champion_rules)

        # Cache for reuse on subsequent challengers
        _set_champion_cache(data_hash, hyp_hash,
                            champion_diag, champion_rules, champion_metrics)

    print(f"\n  Champion metrics:")
    print(f"    Rules: {champion_metrics['total_rules']} "
          f"(entry: {champion_metrics['n_entry']}, skip: {champion_metrics['n_skip']})")
    print(f"    Mean net expectancy: ${champion_metrics['mean_net_expectancy_usd']:.2f}")
    print(f"    Mean WF stability: {champion_metrics['mean_wf_stability']:.4f}")
    print(f"    Sum composite: {champion_metrics['sum_composite']:.4f}")

    # Save initial budget status
    budget.save_json(BUDGET_STATUS_PATH)

    if champion_only:
        print("\n  [--champion-only] Stopping after baseline.")
        log_experiment({
            "timestamp": run_ts,
            "mode": "champion_only",
            "champion_metrics": champion_metrics,
        })
        # Write review reports (empty attempt log)
        elapsed = time.time() - start_time
        n_days = champion_diag.get("distinct_days", 0)
        tier = get_maturity_tier(n_days)
        _write_nightly_exec_report(run_ts, elapsed, champion_metrics, [],
                                   budget, tier, n_days, champion_rules)
        _write_karpathy_review(run_ts, champion_metrics, [], budget)
        budget.print_summary()
        budget.save_json(BUDGET_STATUS_PATH)
        budget.append_history(BUDGET_HISTORY_PATH)
        return

    # Check maturity — don't run mutations if features_only
    n_days = champion_diag.get("distinct_days", 0)
    tier = get_maturity_tier(n_days)
    if tier["mode"] == "features_only":
        print(f"\n  Maturity: {tier['label']}")
        print("  Skipping challenger mutations — need ≥3 days.")
        log_experiment({
            "timestamp": run_ts,
            "mode": "features_only_skip",
            "champion_metrics": champion_metrics,
            "days": n_days,
        })
        elapsed = time.time() - start_time
        _write_nightly_exec_report(run_ts, elapsed, champion_metrics, [],
                                   budget, tier, n_days, champion_rules)
        _write_karpathy_review(run_ts, champion_metrics, [], budget)
        budget.print_summary()
        budget.save_json(BUDGET_STATUS_PATH)
        budget.append_history(BUDGET_HISTORY_PATH)
        return

    # ── Step 2: Challenger loop ───────────────────────────────────────
    best_champion_metrics = champion_metrics
    mutations_accepted = 0
    attempt_log = []   # for review reports

    for attempt in range(1, eff_max + 1):
        # ── Budget gate: can we start a new challenger? ───────────
        if not budget.can_start_new_challenger():
            reason = budget.stop_reason or "max_challengers"
            print(f"\n  [BUDGET] Cannot start challenger {attempt}: {reason}")
            break

        budget.record_challenger_start()

        print(f"\n{'─' * 60}")
        print(f"  PHASE 2: CHALLENGER ATTEMPT {attempt}/{eff_max}")
        print(f"  Budget: ${budget.spend_so_far_usd:.4f} spent / ${budget.remaining_budget():.2f} remaining")
        print(f"{'─' * 60}")

        # Track this attempt for the review
        att_record = {"attempt": attempt, "phase": None, "patch": {},
                      "critic_verdict": None, "champion_at_time": copy.deepcopy(best_champion_metrics),
                      "challenger_metrics": None, "decision": None,
                      "accepted": False}

        # Package diagnostics
        diag_package = package_from_artifacts()
        context_str = format_proposer_context(diag_package)

        # ── Get patch ─────────────────────────────────────────────────
        if manual:
            print("\n  [MANUAL MODE] Paste your patch JSON (Ctrl+D or empty line to finish):")
            lines = []
            try:
                while True:
                    line = input()
                    if not line.strip():
                        break
                    lines.append(line)
            except EOFError:
                pass
            try:
                patch = json.loads("\n".join(lines))
            except json.JSONDecodeError as e:
                print(f"  [ERROR] Invalid JSON: {e}")
                continue
        else:
            # ── Budget gate: proposer call ────────────────────────
            if budget.hard_cap_hit:
                print("  [BUDGET] Hard cap hit. Aborting loop.")
                break

            print("\n  Calling proposer LLM...")
            patch = call_proposer(context_str, model=eff_model,
                                  budget=budget, challenger_index=attempt)
            if patch is None:
                if budget.hard_cap_hit:
                    print("  [BUDGET] Hard cap hit during proposer. Aborting.")
                    break
                print("  [FAIL] Proposer returned nothing. Skipping attempt.")
                continue

        att_record["patch"] = patch
        summary = patch.get("summary", "no summary")
        print(f"  Proposed: {summary}")

        # ── Validate patch bounds ─────────────────────────────────────
        is_valid, errors = validate_patch(patch)
        if not is_valid:
            print(f"  [REJECTED] Patch failed bounds check:")
            for err in errors:
                print(f"    - {err}")
            att_record["phase"] = "bounds_check"
            att_record["errors"] = errors
            attempt_log.append(att_record)
            log_experiment({
                "timestamp": datetime.now().isoformat(),
                "attempt": attempt,
                "phase": "bounds_check",
                "patch": patch,
                "rejected": True,
                "errors": errors,
            })
            budget.save_json(BUDGET_STATUS_PATH)
            continue

        # ── Call critic ───────────────────────────────────────────────
        if not manual:
            if budget.hard_cap_hit:
                print("  [BUDGET] Hard cap hit before critic. Aborting.")
                break

            print("  Calling critic LLM...")
            critic_ctx = format_critic_context(diag_package, patch)
            critic_verdict = call_critic(critic_ctx, model=eff_model,
                                         budget=budget, challenger_index=attempt)

            att_record["critic_verdict"] = critic_verdict

            if budget.hard_cap_hit:
                print("  [BUDGET] Hard cap hit during critic. Aborting.")
                break

            if critic_verdict:
                verdict = critic_verdict.get("verdict", "reject")
                confidence = critic_verdict.get("confidence", 0)
                recommendation = critic_verdict.get("recommendation", "reject_before_run")

                print(f"  Critic verdict: {verdict} (confidence: {confidence})")
                print(f"  Recommendation: {recommendation}")

                if verdict == "reject" or recommendation == "reject_before_run":
                    concerns = critic_verdict.get("main_concerns", [])
                    print(f"  Critic KILLED the patch:")
                    for c in concerns:
                        print(f"    - {c}")
                    att_record["phase"] = "critic"
                    attempt_log.append(att_record)
                    log_experiment({
                        "timestamp": datetime.now().isoformat(),
                        "attempt": attempt,
                        "phase": "critic",
                        "patch": patch,
                        "critic_verdict": critic_verdict,
                        "rejected": True,
                    })
                    budget.save_json(BUDGET_STATUS_PATH)
                    continue
            else:
                print("  [WARN] Critic failed. Running challenger anyway with caution.")

        # ── Apply patch and run challenger ─────────────────────────────
        print("\n  Applying patch and running challenger...")
        challenger_hypothesis = apply_patch(hypothesis, patch)

        with HypothesisOverride(challenger_hypothesis):
            clear_baseline_cache()  # FIX: fresh cache for challenger run
            challenger_diag = run_nightly(db_path=db_path, verbose=verbose)

        # Save challenger artifacts
        _copy_artifacts(ARTIFACTS_DIR, CHALLENGER_ARTIFACTS)
        challenger_rules = _load_rules(ARTIFACTS_DIR)
        challenger_metrics = extract_metrics(challenger_diag, challenger_rules)

        att_record["challenger_metrics"] = challenger_metrics

        print(f"\n  Challenger metrics:")
        print(f"    Rules: {challenger_metrics['total_rules']} "
              f"(entry: {challenger_metrics['n_entry']}, skip: {challenger_metrics['n_skip']})")
        print(f"    Mean net expectancy: ${challenger_metrics['mean_net_expectancy_usd']:.2f}")
        print(f"    Mean WF stability: {challenger_metrics['mean_wf_stability']:.4f}")
        print(f"    Sum composite: {challenger_metrics['sum_composite']:.4f}")

        # ── Judge ─────────────────────────────────────────────────────
        print("\n  JUDGE comparing champion vs challenger...")

        if best_champion_metrics["total_rules"] == 0:
            decision = judge_first_run(challenger_metrics)
        else:
            decision = judge(best_champion_metrics, challenger_metrics,
                             patch_summary=summary)

        att_record["decision"] = decision
        att_record["phase"] = "judge"

        if decision["accepted"]:
            print(f"  ✓ CHALLENGER WINS: {decision['reason']}")
            mutations_accepted += 1
            att_record["accepted"] = True

            # Build knob_changed for checkpoint
            changes = patch.get("changes", {})
            knob_changed = {}
            for change_key, change_val in changes.items():
                if isinstance(change_val, dict):
                    for k, v in change_val.items():
                        old_val = hypothesis.get(change_key, {}).get(k, "?")
                        knob_changed[f"{change_key}.{k}"] = {"old": old_val, "new": v}
                else:
                    old_val = hypothesis.get(change_key, "?")
                    knob_changed[change_key] = {"old": old_val, "new": change_val}

            # Save pre-mutation champion metrics for checkpoint
            pre_mutation_champion_metrics = copy.deepcopy(best_champion_metrics)

            # Update champion
            best_champion_metrics = challenger_metrics
            hypothesis = challenger_hypothesis
            save_hypothesis(hypothesis)
            champion_rules = challenger_rules  # update for final report

            # Copy challenger artifacts to main
            _copy_artifacts(CHALLENGER_ARTIFACTS, ARTIFACTS_DIR)
            _copy_artifacts(CHALLENGER_ARTIFACTS, CHAMPION_ARTIFACTS)

            # Save checkpoint (pre-mutation champion vs winning challenger)
            save_checkpoint(
                hypothesis_snapshot=challenger_hypothesis,
                champion_metrics=pre_mutation_champion_metrics,
                challenger_metrics=challenger_metrics,
                data_hash=data_hash,
                hypothesis_hash=_compute_hypothesis_hash(challenger_hypothesis),
                knob_changed=knob_changed,
                judge_verdict=decision,
                accepted_rules=challenger_rules,
            )

            # Invalidate champion cache (hypothesis changed)
            _champion_cache.clear()
        else:
            print(f"  ✗ CHAMPION RETAINED: {decision['reason']}")

        attempt_log.append(att_record)

        # Log
        log_experiment({
            "timestamp": datetime.now().isoformat(),
            "attempt": attempt,
            "phase": "judge",
            "patch": patch,
            "champion_metrics": best_champion_metrics,
            "challenger_metrics": challenger_metrics,
            "decision": decision,
        })

        # Update budget status after each attempt
        budget.save_json(BUDGET_STATUS_PATH)

    # ── Final Summary ─────────────────────────────────────────────────
    elapsed = time.time() - start_time

    print(f"\n{'=' * 80}")
    print(f"  KARPATHY LOOP COMPLETE")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Challengers attempted: {budget.challenger_attempts}")
    print(f"  Mutations accepted: {mutations_accepted}")
    print(f"  Final champion metrics:")
    print(f"    Rules: {best_champion_metrics['total_rules']}")
    print(f"    Net expectancy: ${best_champion_metrics['mean_net_expectancy_usd']:.2f}")
    print(f"    WF stability: {best_champion_metrics['mean_wf_stability']:.4f}")
    print(f"{'=' * 80}")

    # ── Budget summary ────────────────────────────────────────────
    budget.print_summary()

    # ── Write artifacts ───────────────────────────────────────────
    budget.save_json(BUDGET_STATUS_PATH)
    budget.append_history(BUDGET_HISTORY_PATH)

    _write_nightly_exec_report(run_ts, elapsed, best_champion_metrics,
                               attempt_log, budget, tier, n_days, champion_rules)
    _write_karpathy_review(run_ts, champion_metrics, attempt_log, budget)

    print(f"\n  Review reports:")
    print(f"    {NIGHTLY_EXEC_REPORT_PATH}")
    print(f"    {KARPATHY_REVIEW_PATH}")
    print(f"    {BUDGET_STATUS_PATH}")


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Karpathy Autoresearch — Bounded Mutation Runner"
    )
    parser.add_argument("--db", type=str, default=str(DB_PATH),
                        help="Path to spy_autoresearch.db")
    parser.add_argument("--max-challengers", type=int, default=None,
                        help=f"Max challenger attempts per night (default: from config)")
    parser.add_argument("--manual", action="store_true",
                        help="Manual mode: paste patch JSON instead of LLM")
    parser.add_argument("--champion-only", action="store_true",
                        help="Run baseline only, no mutations")
    parser.add_argument("--model", type=str, default=None,
                        help="LLM model for proposer/critic (default: from config)")
    parser.add_argument("--quiet", action="store_true",
                        help="Reduce output")

    # Budget CLI overrides
    parser.add_argument("--hard-budget-usd", type=float, default=None,
                        help="Override hard budget cap in USD (default: from config)")
    parser.add_argument("--soft-budget-usd", type=float, default=None,
                        help="Override soft budget cap in USD (default: from config)")

    args = parser.parse_args()

    run_karpathy(
        db_path=Path(args.db),
        max_challengers=args.max_challengers,
        manual=args.manual,
        champion_only=args.champion_only,
        model=args.model,
        verbose=not args.quiet,
        hard_budget_usd=args.hard_budget_usd,
        soft_budget_usd=args.soft_budget_usd,
    )


if __name__ == "__main__":
    main()
