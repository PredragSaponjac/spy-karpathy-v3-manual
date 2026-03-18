"""
Karpathy Autoresearch — Search Space Bounds (MUTABLE)

Defines the valid ranges for every knob the proposer may touch.
The critic and judge use these bounds to reject out-of-range patches.
"""

# ── Feature family weight bounds ──────────────────────────────────────
# No single family weight can go below 0.3 or above 2.5
FEATURE_WEIGHT_MIN = 0.3
FEATURE_WEIGHT_MAX = 2.5

# ── Threshold bounds ──────────────────────────────────────────────────
THRESHOLD_BOUNDS = {
    "min_support":         (15, 100),     # snapshots
    "max_overlap":         (0.30, 0.80),  # Jaccard
    "neighbor_band_pct":   (0.05, 0.25),  # ±%
    "min_composite_score": (-5.0, 10.0),  # composite
}

# ── Scalar knob bounds ────────────────────────────────────────────────
SCALAR_BOUNDS = {
    "skip_aggressiveness":  (0.5, 2.0),
    "intermarket_weight":   (0.3, 2.5),
    "move_size_preference": (0.5, 2.0),
}

# ── Mutation limits per patch ─────────────────────────────────────────
# One mutation per challenger = clean credit assignment.
# If a challenger wins, we know exactly which knob caused the improvement.
MAX_KNOB_CHANGES_PER_PATCH = 1

# The critic should reject if more than this many knobs change
CRITIC_MAX_CHANGES = 1


def validate_patch(patch: dict) -> tuple:
    """Validate a proposed patch against bounds.

    Returns (is_valid: bool, errors: list[str])
    """
    errors = []
    changes = patch.get("changes", {})

    # Count total changes
    n_changes = 0

    # FIX: Helper to safely coerce LLM values to float (prevents TypeError
    # crashes when LLM returns strings like "40" instead of 40)
    def _safe_float(v, label=""):
        try:
            return float(v)
        except (TypeError, ValueError):
            errors.append(f"{label}: cannot convert {v!r} to float")
            return None

    # Feature family weights
    ffw = changes.get("feature_family_weights", {})
    if not isinstance(ffw, dict):
        errors.append(f"feature_family_weights must be dict, got {type(ffw).__name__}")
        ffw = {}
    for k, v in ffw.items():
        n_changes += 1
        v = _safe_float(v, f"feature_family_weights.{k}")
        if v is not None and (v < FEATURE_WEIGHT_MIN or v > FEATURE_WEIGHT_MAX):
            errors.append(f"feature_family_weights.{k}={v} out of [{FEATURE_WEIGHT_MIN}, {FEATURE_WEIGHT_MAX}]")

    # Divergence family weights
    dfw = changes.get("divergence_family_weights", {})
    if not isinstance(dfw, dict):
        errors.append(f"divergence_family_weights must be dict, got {type(dfw).__name__}")
        dfw = {}
    for k, v in dfw.items():
        n_changes += 1
        v = _safe_float(v, f"divergence_family_weights.{k}")
        if v is not None and (v < FEATURE_WEIGHT_MIN or v > FEATURE_WEIGHT_MAX):
            errors.append(f"divergence_family_weights.{k}={v} out of [{FEATURE_WEIGHT_MIN}, {FEATURE_WEIGHT_MAX}]")

    # Sequence family weights
    sfw = changes.get("sequence_family_weights", {})
    if not isinstance(sfw, dict):
        errors.append(f"sequence_family_weights must be dict, got {type(sfw).__name__}")
        sfw = {}
    for k, v in sfw.items():
        n_changes += 1
        v = _safe_float(v, f"sequence_family_weights.{k}")
        if v is not None and (v < FEATURE_WEIGHT_MIN or v > FEATURE_WEIGHT_MAX):
            errors.append(f"sequence_family_weights.{k}={v} out of [{FEATURE_WEIGHT_MIN}, {FEATURE_WEIGHT_MAX}]")

    # Rule family enable/disable
    rfe = changes.get("rule_family_enable", {})
    if not isinstance(rfe, dict):
        errors.append(f"rule_family_enable must be dict, got {type(rfe).__name__}")
        rfe = {}
    for k, v in rfe.items():
        n_changes += 1

    # Thresholds
    thresholds = changes.get("thresholds", {})
    if not isinstance(thresholds, dict):
        errors.append(f"thresholds must be dict, got {type(thresholds).__name__}")
        thresholds = {}
    for k, v in thresholds.items():
        n_changes += 1
        v = _safe_float(v, f"thresholds.{k}")
        if v is not None and k in THRESHOLD_BOUNDS:
            lo, hi = THRESHOLD_BOUNDS[k]
            if v < lo or v > hi:
                errors.append(f"thresholds.{k}={v} out of [{lo}, {hi}]")

    # Scalars
    for scalar in ("skip_aggressiveness", "intermarket_weight", "move_size_preference"):
        if scalar in changes:
            n_changes += 1
            v = _safe_float(changes[scalar], scalar)
            if v is not None:
                lo, hi = SCALAR_BOUNDS[scalar]
                if v < lo or v > hi:
                    errors.append(f"{scalar}={v} out of [{lo}, {hi}]")

    # Total change count
    if n_changes > MAX_KNOB_CHANGES_PER_PATCH:
        errors.append(f"Too many changes: {n_changes} > {MAX_KNOB_CHANGES_PER_PATCH}")

    if n_changes == 0:
        errors.append("No changes in patch")

    return (len(errors) == 0, errors)
