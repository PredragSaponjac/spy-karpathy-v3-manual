"""
Karpathy Autoresearch — LLM Budget Guard

Prevents the proposer/critic loop from exceeding a hard overnight budget.
Controls ONLY LLM spend — the deterministic Python engine is unaffected.

Usage:
    from budget_guard import BudgetTracker, BudgetConfig

    tracker = BudgetTracker()          # uses config.py defaults
    tracker = BudgetTracker(BudgetConfig(hard_budget_usd=50.0))  # override

    if tracker.can_start_new_challenger():
        if tracker.can_run_call(projected_in, projected_out):
            # ... make LLM call ...
            tracker.add_usage(actual_in, actual_out, "proposer")
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import config as _cfg


# ── Data Classes ─────────────────────────────────────────────────────────

@dataclass
class BudgetConfig:
    """All budget-related knobs in one place."""
    hard_budget_usd: float = 0.0
    soft_budget_usd: float = 0.0
    max_challengers: int = 0
    max_output_tokens_per_call: int = 0
    input_price_per_mtok: float = 0.0
    output_price_per_mtok: float = 0.0
    default_model: str = ""
    projected_proposer_input_tokens: int = 0
    projected_proposer_output_tokens: int = 0
    projected_critic_input_tokens: int = 0
    projected_critic_output_tokens: int = 0

    def __post_init__(self):
        """Fill zeros from config.py defaults."""
        _defaults = {
            "hard_budget_usd":                 "LLM_HARD_BUDGET_USD",
            "soft_budget_usd":                 "LLM_SOFT_BUDGET_USD",
            "max_challengers":                 "LLM_MAX_CHALLENGERS",
            "max_output_tokens_per_call":      "LLM_MAX_OUTPUT_TOKENS_PER_CALL",
            "input_price_per_mtok":            "LLM_INPUT_PRICE_PER_MTOK",
            "output_price_per_mtok":           "LLM_OUTPUT_PRICE_PER_MTOK",
            "default_model":                   "LLM_DEFAULT_MODEL",
            "projected_proposer_input_tokens": "LLM_PROJECTED_PROPOSER_INPUT_TOKENS",
            "projected_proposer_output_tokens":"LLM_PROJECTED_PROPOSER_OUTPUT_TOKENS",
            "projected_critic_input_tokens":   "LLM_PROJECTED_CRITIC_INPUT_TOKENS",
            "projected_critic_output_tokens":  "LLM_PROJECTED_CRITIC_OUTPUT_TOKENS",
        }
        for attr, cfg_key in _defaults.items():
            val = getattr(self, attr)
            if val == 0 or val == "" or val == 0.0:
                setattr(self, attr, getattr(_cfg, cfg_key, val))


@dataclass
class UsageRecord:
    """One LLM call's cost record."""
    timestamp: str
    call_type: str               # "proposer" | "critic"
    model: str
    estimated_or_actual: str     # "actual" | "estimated"
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cumulative_cost_usd: float
    challenger_index: int
    decision_context: str = ""


# ── Budget Tracker ───────────────────────────────────────────────────────

class BudgetTracker:
    """Tracks LLM spend across one overnight Karpathy run.

    Thread-safe: NO — single-threaded nightly runner only.
    """

    def __init__(self, config: Optional[BudgetConfig] = None):
        self.cfg = config or BudgetConfig()
        self.spend_so_far_usd: float = 0.0
        self.estimated_reserved_usd: float = 0.0
        self.proposer_calls: int = 0
        self.critic_calls: int = 0
        self.challenger_attempts: int = 0
        self.usage_log: List[UsageRecord] = []
        self._stop_reason: Optional[str] = None  # "soft_cap" | "hard_cap" | None

    # ── Cost estimation ──────────────────────────────────────────────

    def estimate_call_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate USD cost for a single call."""
        return (
            (input_tokens / 1_000_000) * self.cfg.input_price_per_mtok
            + (output_tokens / 1_000_000) * self.cfg.output_price_per_mtok
        )

    # ── Usage recording ──────────────────────────────────────────────

    def add_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        call_type: str,
        model: Optional[str] = None,
        actual: bool = True,
        challenger_index: int = 0,
        decision_context: str = "",
    ):
        """Record one LLM call's token usage.

        Args:
            input_tokens:  Actual (or projected) input tokens.
            output_tokens: Actual (or projected) output tokens.
            call_type:     "proposer" or "critic".
            model:         Model name (defaults to config default).
            actual:        True if tokens come from the API response.
            challenger_index: Which challenger attempt this belongs to.
            decision_context: Optional short note (e.g. "critic rejected").
        """
        cost = self.estimate_call_cost(input_tokens, output_tokens)
        self.spend_so_far_usd += cost

        if call_type == "proposer":
            self.proposer_calls += 1
        elif call_type == "critic":
            self.critic_calls += 1

        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            call_type=call_type,
            model=model or self.cfg.default_model,
            estimated_or_actual="actual" if actual else "estimated",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            cumulative_cost_usd=round(self.spend_so_far_usd, 6),
            challenger_index=challenger_index,
            decision_context=decision_context,
        )
        self.usage_log.append(record)

    # ── Budget checks ────────────────────────────────────────────────

    def can_run_call(
        self,
        projected_input_tokens: int,
        projected_output_tokens: int,
    ) -> bool:
        """Check if there's budget for this call (against hard cap)."""
        projected_cost = self.estimate_call_cost(
            projected_input_tokens, projected_output_tokens
        )
        return (self.spend_so_far_usd + projected_cost) <= self.cfg.hard_budget_usd

    def can_start_new_challenger(self) -> bool:
        """Check if we can start another challenger attempt.

        False if:
          - spend >= soft budget (stop launching new challengers)
          - challenger_attempts >= max_challengers
          - hard budget already breached
        """
        if self.spend_so_far_usd >= self.cfg.hard_budget_usd:
            self._stop_reason = "hard_cap"
            return False
        if self.spend_so_far_usd >= self.cfg.soft_budget_usd:
            self._stop_reason = "soft_cap"
            return False
        if self.challenger_attempts >= self.cfg.max_challengers:
            return False
        return True

    def record_challenger_start(self):
        """Mark that a new challenger attempt has begun."""
        self.challenger_attempts += 1

    def remaining_budget(self) -> float:
        """Dollars remaining before hard cap."""
        return max(0.0, self.cfg.hard_budget_usd - self.spend_so_far_usd)

    @property
    def soft_cap_hit(self) -> bool:
        return self.spend_so_far_usd >= self.cfg.soft_budget_usd

    @property
    def hard_cap_hit(self) -> bool:
        return self.spend_so_far_usd >= self.cfg.hard_budget_usd

    @property
    def stop_reason(self) -> Optional[str]:
        return self._stop_reason

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Full status snapshot for artifacts/budget_status.json."""
        return {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": {
                "hard_budget_usd": self.cfg.hard_budget_usd,
                "soft_budget_usd": self.cfg.soft_budget_usd,
                "max_challengers": self.cfg.max_challengers,
                "input_price_per_mtok": self.cfg.input_price_per_mtok,
                "output_price_per_mtok": self.cfg.output_price_per_mtok,
                "default_model": self.cfg.default_model,
            },
            "spend": {
                "total_usd": round(self.spend_so_far_usd, 6),
                "remaining_usd": round(self.remaining_budget(), 6),
                "pct_of_hard_cap": round(
                    self.spend_so_far_usd / self.cfg.hard_budget_usd * 100, 2
                ) if self.cfg.hard_budget_usd > 0 else 0,
            },
            "calls": {
                "proposer": self.proposer_calls,
                "critic": self.critic_calls,
                "total": self.proposer_calls + self.critic_calls,
            },
            "challengers": {
                "attempted": self.challenger_attempts,
                "max": self.cfg.max_challengers,
            },
            "stop_reason": self._stop_reason,
        }

    def save_json(self, path: Path):
        """Write current status to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def append_history(self, path: Path):
        """Append all new usage records to budget_history.jsonl."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            for rec in self.usage_log:
                f.write(json.dumps({
                    "timestamp": rec.timestamp,
                    "call_type": rec.call_type,
                    "model": rec.model,
                    "estimated_or_actual": rec.estimated_or_actual,
                    "input_tokens": rec.input_tokens,
                    "output_tokens": rec.output_tokens,
                    "cost_usd": rec.cost_usd,
                    "cumulative_cost_usd": rec.cumulative_cost_usd,
                    "challenger_index": rec.challenger_index,
                    "decision_context": rec.decision_context,
                }, default=str) + "\n")

    def print_summary(self):
        """Print end-of-run budget summary to stdout."""
        print(f"\n{'─' * 60}")
        print(f"  LLM BUDGET SUMMARY")
        print(f"{'─' * 60}")
        print(f"  Model:             {self.cfg.default_model}")
        print(f"  Total spend:       ${self.spend_so_far_usd:.4f}")
        print(f"  Hard cap:          ${self.cfg.hard_budget_usd:.2f}")
        print(f"  Soft cap:          ${self.cfg.soft_budget_usd:.2f}")
        print(f"  Remaining:         ${self.remaining_budget():.4f}")
        print(f"  Proposer calls:    {self.proposer_calls}")
        print(f"  Critic calls:      {self.critic_calls}")
        print(f"  Challenger attempts: {self.challenger_attempts}")
        if self._stop_reason:
            label = "SOFT CAP" if self._stop_reason == "soft_cap" else "HARD CAP"
            print(f"  Stopped by:        {label}")
        else:
            print(f"  Stopped by:        normal completion")
        print(f"{'─' * 60}")
