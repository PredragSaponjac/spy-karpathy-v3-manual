"""
Karpathy Autoresearch — Hypothesis Configuration (MUTABLE)

This file is the ONLY place the Karpathy shell may write mutations.
It holds the current champion hypothesis. When a challenger patch wins,
karpathy_runner.py updates this file.

DO NOT EDIT MANUALLY during an active experiment.
"""
import json
from pathlib import Path

_HYPOTHESIS_PATH = Path(__file__).parent / "hypothesis_state.json"

# ── Default Champion Hypothesis ──────────────────────────────────────────
DEFAULT_HYPOTHESIS = {
    # Which rule families to generate
    "rule_families": {
        "level":       True,
        "interaction": True,
        "divergence":  True,
        "sequence":    True,
        "skip":        True,
        "confluence":  False,  # disabled by default — Karpathy can toggle
    },

    # Feature-family emphasis for interaction rule generation
    # 1.0 = baseline weight; >1 = more interaction slots; <1 = fewer
    "feature_family_weights": {
        "tape":       1.0,
        "dealer":     1.0,
        "flow":       1.0,
        "skew":       1.0,
        "structure":  1.0,
        "expanded":   1.0,
        "0dte":       1.0,
        "fluxgate":   1.0,
        "micro":      1.0,
        "internals":  1.0,
        "signals":    1.0,
        "context":    1.0,
    },

    # Divergence family emphasis (SPY↔QQQ intermarket)
    "divergence_family_weights": {
        "relative_strength": 1.0,
        "z_score_div":       1.0,
        "non_confirmation":  1.0,
        "recoupling":        1.0,
        "lead_lag":          1.0,
        "composite":         1.0,
    },

    # Sequence family emphasis (temporal patterns)
    "sequence_family_weights": {
        "compression_expansion": 1.0,
        "divergence_chains":     1.0,
        "momentum_flips":        1.0,
        "qqq_lead_confirm":      1.0,
        "acceleration":          1.0,
    },

    # Thresholds (override config.py defaults)
    "thresholds": {
        "min_support":       20,
        "max_overlap":       0.60,
        "neighbor_band_pct": 0.10,
        "min_composite_score": 0.0,
    },

    # Skip aggressiveness: >1 = more aggressive skip (higher skip thresholds)
    # <1 = more permissive skip
    "skip_aggressiveness": 1.0,

    # Intermarket weight: >1 = emphasize QQQ signals more; <1 = less
    "intermarket_weight": 1.0,

    # Move size preference: >1 = prefer larger tradable moves; <1 = prefer any signal
    "move_size_preference": 1.0,
}


def load_hypothesis() -> dict:
    """Load the current champion hypothesis from disk, or return defaults.

    Uses safe_load with schema validation and corruption fallback.
    """
    try:
        from state_io import safe_load
        saved = safe_load(_HYPOTHESIS_PATH)
    except ImportError:
        # Fallback if state_io not available
        if _HYPOTHESIS_PATH.exists():
            try:
                with open(_HYPOTHESIS_PATH, 'r') as f:
                    saved = json.load(f)
            except (json.JSONDecodeError, KeyError):
                return DEFAULT_HYPOTHESIS.copy()
        else:
            return DEFAULT_HYPOTHESIS.copy()

    # Merge with defaults to ensure all keys exist (handles new keys like confluence)
    merged = _deep_merge(DEFAULT_HYPOTHESIS, saved)
    return merged


def save_hypothesis(hypothesis: dict):
    """Save hypothesis to disk (called when a challenger wins).

    Uses safe_save with atomic write, backup, and validation.
    """
    try:
        from state_io import safe_save
        safe_save(hypothesis, _HYPOTHESIS_PATH)
    except ImportError:
        # Fallback if state_io not available
        with open(_HYPOTHESIS_PATH, 'w') as f:
            json.dump(hypothesis, f, indent=2)


def apply_patch(hypothesis: dict, patch: dict) -> dict:
    """Apply a proposer patch to a hypothesis, returning a new challenger hypothesis.

    Patch format (from proposer LLM):
    {
        "changes": {
            // Exactly one of these per patch:
            "feature_family_weights": {"dealer": 1.15},
            "divergence_family_weights": {"z_score_div": 1.3},
            "sequence_family_weights": {"compression_expansion": 1.2},
            "rule_family_enable": {"sequence": false},
            "thresholds": {"min_support": 35},
            "skip_aggressiveness": 1.1,
            "intermarket_weight": 1.2,
            "move_size_preference": 1.3
        }
    }
    """
    challenger = json.loads(json.dumps(hypothesis))  # deep copy

    changes = patch.get("changes", {})

    # Feature family weights
    if "feature_family_weights" in changes:
        for k, v in changes["feature_family_weights"].items():
            if k in challenger["feature_family_weights"]:
                challenger["feature_family_weights"][k] = float(v)

    # Rule family enable/disable
    if "rule_family_enable" in changes:
        for k, v in changes["rule_family_enable"].items():
            if k in challenger["rule_families"]:
                challenger["rule_families"][k] = _parse_bool(v)

    # Divergence family weights
    if "divergence_family_weights" in changes:
        for k, v in changes["divergence_family_weights"].items():
            if k in challenger["divergence_family_weights"]:
                challenger["divergence_family_weights"][k] = float(v)

    # Sequence family weights
    if "sequence_family_weights" in changes:
        for k, v in changes["sequence_family_weights"].items():
            if k in challenger["sequence_family_weights"]:
                challenger["sequence_family_weights"][k] = float(v)

    # Thresholds
    if "thresholds" in changes:
        for k, v in changes["thresholds"].items():
            if k in challenger["thresholds"]:
                challenger["thresholds"][k] = float(v)

    # Scalar knobs
    for scalar in ("skip_aggressiveness", "intermarket_weight", "move_size_preference"):
        if scalar in changes:
            challenger[scalar] = float(changes[scalar])

    return challenger


def _parse_bool(value) -> bool:
    """Strict boolean parsing that handles LLM string outputs correctly.

    Python's bool("False") == True, so we must parse explicitly.
    Accepts: True/False, "true"/"false", "yes"/"no", "1"/"0", 1/0.
    Raises ValueError for ambiguous values.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ('true', 'yes', '1'):
            return True
        if lower in ('false', 'no', '0'):
            return False
        raise ValueError(f"Cannot parse '{value}' as boolean. "
                         f"Use true/false, yes/no, or 1/0.")
    raise ValueError(f"Cannot parse {type(value).__name__} '{value}' as boolean.")


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    """Merge overrides into defaults (1 level deep for nested dicts)."""
    result = defaults.copy()
    for k, v in overrides.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = {**result[k], **v}
        else:
            result[k] = v
    return result
