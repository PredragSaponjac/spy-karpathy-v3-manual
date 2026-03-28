"""
Karpathy Autoresearch — Safe State I/O

Atomic save/load for hypothesis_state.json with:
- Schema validation on load
- Temp-file write + atomic rename
- .bak of previous state before overwrite
- Corruption protection with fallback to defaults
"""
import json
import os
import shutil
from pathlib import Path
from typing import Tuple

from hypothesis import DEFAULT_HYPOTHESIS

# ── Schema: required keys and their expected types ─────────────────────

_SCHEMA = {
    "rule_families": dict,
    "feature_family_weights": dict,
    "divergence_family_weights": dict,
    "sequence_family_weights": dict,
    "thresholds": dict,
    "skip_aggressiveness": (int, float),
    "intermarket_weight": (int, float),
    "move_size_preference": (int, float),
}

_REQUIRED_RULE_FAMILIES = [
    "level", "interaction", "divergence", "sequence", "skip",
]

_THRESHOLD_KEYS = [
    "min_support", "max_overlap", "neighbor_band_pct", "min_composite_score",
]


def validate_hypothesis(data: dict) -> Tuple[bool, list]:
    """Validate hypothesis dict against schema.

    Returns (is_valid, list_of_errors).
    """
    errors = []

    if not isinstance(data, dict):
        return False, ["hypothesis is not a dict"]

    # Check top-level keys and types
    for key, expected_type in _SCHEMA.items():
        if key not in data:
            errors.append(f"missing key: {key}")
            continue
        if not isinstance(data[key], expected_type):
            errors.append(f"{key}: expected {expected_type}, got {type(data[key]).__name__}")

    # Check rule_families has required keys
    rf = data.get("rule_families", {})
    if isinstance(rf, dict):
        for fam in _REQUIRED_RULE_FAMILIES:
            if fam not in rf:
                errors.append(f"rule_families missing: {fam}")
            elif not isinstance(rf[fam], bool):
                errors.append(f"rule_families.{fam}: expected bool, got {type(rf[fam]).__name__}")

    # Check thresholds has required keys with numeric values
    th = data.get("thresholds", {})
    if isinstance(th, dict):
        for tk in _THRESHOLD_KEYS:
            if tk not in th:
                errors.append(f"thresholds missing: {tk}")
            elif not isinstance(th[tk], (int, float)):
                errors.append(f"thresholds.{tk}: expected number, got {type(th[tk]).__name__}")

    # Check weight dicts have numeric values
    for weight_key in ("feature_family_weights", "divergence_family_weights",
                        "sequence_family_weights"):
        wd = data.get(weight_key, {})
        if isinstance(wd, dict):
            for k, v in wd.items():
                if not isinstance(v, (int, float)):
                    errors.append(f"{weight_key}.{k}: expected number, got {type(v).__name__}")

    return len(errors) == 0, errors


def safe_load(path: Path) -> dict:
    """Load hypothesis state with validation and corruption fallback.

    Priority:
    1. Load main file, validate → return if valid
    2. Load .bak file, validate → return if valid + warn
    3. Return DEFAULT_HYPOTHESIS
    """
    # Try main file
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            is_valid, errors = validate_hypothesis(data)
            if is_valid:
                return data
            else:
                print(f"  [STATE_IO] WARNING: {path.name} failed validation: {errors[:3]}")
                print(f"  [STATE_IO] Trying backup...")
        except (json.JSONDecodeError, IOError) as e:
            print(f"  [STATE_IO] WARNING: {path.name} corrupted: {e}")
            print(f"  [STATE_IO] Trying backup...")

    # Try backup
    bak_path = path.with_suffix(path.suffix + '.bak')
    if bak_path.exists():
        try:
            with open(bak_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            is_valid, errors = validate_hypothesis(data)
            if is_valid:
                print(f"  [STATE_IO] Recovered from backup: {bak_path.name}")
                # Restore main from backup
                shutil.copy2(str(bak_path), str(path))
                return data
            else:
                print(f"  [STATE_IO] Backup also invalid: {errors[:3]}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"  [STATE_IO] Backup also corrupted: {e}")

    # Fallback to defaults
    print(f"  [STATE_IO] Using DEFAULT_HYPOTHESIS (no valid state found)")
    return DEFAULT_HYPOTHESIS.copy()


def safe_save(data: dict, path: Path):
    """Save hypothesis state with atomic write and backup.

    1. Validate data before writing
    2. Back up current file to .bak
    3. Write to temp file
    4. Atomic rename temp → target
    """
    is_valid, errors = validate_hypothesis(data)
    if not is_valid:
        print(f"  [STATE_IO] REFUSING to save invalid hypothesis: {errors[:3]}")
        return

    # Back up current file
    if path.exists():
        bak_path = path.with_suffix(path.suffix + '.bak')
        try:
            shutil.copy2(str(path), str(bak_path))
        except IOError as e:
            print(f"  [STATE_IO] WARNING: backup failed: {e}")

    # Write to temp file
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
    except IOError as e:
        print(f"  [STATE_IO] ERROR: temp write failed: {e}")
        if tmp_path.exists():
            tmp_path.unlink()
        return

    # Atomic rename (os.replace handles target-exists on Windows)
    try:
        os.replace(str(tmp_path), str(path))
    except OSError as e:
        print(f"  [STATE_IO] ERROR: atomic replace failed: {e}")
        # Try to clean up temp file
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
