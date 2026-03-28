"""
Karpathy Autoresearch — Lightweight Checkpoint Manager

On every promoted challenger, saves a timestamped JSON checkpoint
in artifacts/checkpoints/ with full metadata. No auto-rollback yet —
just clean historical promoted-state storage for future use.
"""
import json
from datetime import datetime
from pathlib import Path

from config import ARTIFACTS_DIR

CHECKPOINT_DIR = ARTIFACTS_DIR / "checkpoints"


def save_checkpoint(
    hypothesis_snapshot: dict,
    champion_metrics: dict,
    challenger_metrics: dict,
    data_hash: str,
    hypothesis_hash: str,
    knob_changed: dict,
    judge_verdict: dict,
    accepted_rules: list = None,
):
    """Save a promotion checkpoint.

    Args:
        hypothesis_snapshot: Full hypothesis dict at time of promotion
        champion_metrics: Metrics of the outgoing champion
        challenger_metrics: Metrics of the incoming champion
        data_hash: Hash of the data used
        hypothesis_hash: Hash of the hypothesis used
        knob_changed: {"key": {"old": x, "new": y}} dict
        judge_verdict: Full judge decision dict
        accepted_rules: Optional list of promoted rule dicts
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now()
    ts_str = ts.strftime("%Y-%m-%dT%H-%M-%S")

    checkpoint = {
        "timestamp": ts.isoformat(),
        "data_hash": data_hash,
        "hypothesis_hash": hypothesis_hash,
        "knob_changed": knob_changed,
        "champion_metrics": champion_metrics,
        "challenger_metrics": challenger_metrics,
        "judge_verdict": judge_verdict,
        "hypothesis_snapshot": hypothesis_snapshot,
    }

    if accepted_rules is not None:
        # Store compact version (names + scores only)
        checkpoint["accepted_rules_summary"] = [
            {
                "name": r.get("name", ""),
                "direction": r.get("direction", ""),
                "source_family": r.get("source_family", ""),
                "composite_score": r.get("composite_score", 0),
                "mes_net_expectancy_usd": r.get("mes_net_expectancy_usd", 0),
                "wf_stability": r.get("wf_stability", 0),
            }
            for r in accepted_rules
        ]

    filename = f"checkpoint_{ts_str}.json"
    path = CHECKPOINT_DIR / filename

    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2, default=str)
        print(f"  [CHECKPOINT] Saved: {filename}")
    except IOError as e:
        print(f"  [CHECKPOINT] WARNING: save failed: {e}")


def list_checkpoints() -> list:
    """List all checkpoint files, newest first."""
    if not CHECKPOINT_DIR.exists():
        return []
    files = sorted(CHECKPOINT_DIR.glob("checkpoint_*.json"), reverse=True)
    return files


def load_checkpoint(path: Path) -> dict:
    """Load a checkpoint from disk."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
