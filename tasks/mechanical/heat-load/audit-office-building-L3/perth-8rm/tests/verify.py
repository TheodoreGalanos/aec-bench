# ABOUTME: Verifier for audit-office-building-L3 heat load audit task.
# ABOUTME: Scores error detection using recall, fix accuracy, and FP penalty.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

# ---- Planted errors ----
# Each error is keyed by (room_no, field) with the correct value.
PLANTED_ERRORS: list[dict] = [
    {
        "room_no": 5,
        "field": "ventilation_latent_w",
        "given_value": 75294.12,
        "correct_value": 29003.6,
        "description": "Used raw outdoor enthalpy (78.4 kJ/kg) instead of Δh (30.200000000000003 kJ/kg) in latent formula",
    },
    {
        "room_no": 2,
        "field": "conduction_w",
        "given_value": 12150.0,
        "correct_value": 4500,
        "description": "Conduction uses volume (675.0 m³ × 18 W/m² = 12150.0) instead of floor area (250 m² × 18 W/m² = 4500)",
    },
    {
        "room_no": 3,
        "field": "people_sensible_w",
        "given_value": 975.0,
        "correct_value": 1125.0,
        "description": "Used 65 W/person instead of 75 W/person for sensible heat gain",
    },
]

N_PLANTED = len(PLANTED_ERRORS)
REL_TOL = 0.03


# Maps each field to downstream fields that will be wrong if this field is wrong.
CASCADING_FIELDS: dict[str, list[str]] = {
    "conduction_w": ["total_sensible_w", "total_cooling_w"],
    "people_sensible_w": ["total_sensible_w", "total_cooling_w"],
    "ventilation_sensible_w": ["total_sensible_w", "total_cooling_w"],
    "lighting_w": ["total_sensible_w", "total_cooling_w"],
    "small_power_w": ["total_sensible_w", "total_cooling_w"],
    "people_latent_w": ["total_latent_w", "total_cooling_w"],
    "ventilation_latent_w": ["total_latent_w", "total_cooling_w"],
    "num_people": [
        "people_sensible_w", "people_latent_w",
        "ventilation_sensible_w", "ventilation_latent_w",
        "total_sensible_w", "total_latent_w", "total_cooling_w",
    ],
}


def build_cascading_set(planted_errors: list[dict]) -> set[tuple[int, str]]:
    """Derive (room_no, field) pairs that are expected cascading consequences."""
    cascading: set[tuple[int, str]] = set()
    for err in planted_errors:
        for downstream in CASCADING_FIELDS.get(err["field"], []):
            cascading.add((err["room_no"], downstream))
    return cascading


def write_reward(reward: float, details: dict, path: Path) -> None:
    """Write reward JSON for Harbor, plus per-field details to a sibling file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": round(reward, 2)}))
    details_path = path.parent / "details.json"
    details_path.write_text(json.dumps(details))


def extract_json_block(text: str) -> dict | None:
    """Extract the last fenced JSON block from Markdown text."""
    pattern = r"```json\s*\n(.*?)\n\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def match_error(
    planted: dict, found: dict,
) -> tuple[bool, bool]:
    """Check if a found error matches a planted error.

    Returns (detected, fix_correct).
    detected: room_no and field match.
    fix_correct: correct_value is within tolerance.
    """
    if found.get("room_no") != planted["room_no"]:
        return False, False
    if found.get("field") != planted["field"]:
        return False, False

    detected = True
    fix_correct = False

    correct_val = found.get("correct_value")
    if correct_val is not None:
        try:
            correct_float = float(correct_val)
            if math.isclose(correct_float, planted["correct_value"], rel_tol=REL_TOL):
                fix_correct = True
        except (TypeError, ValueError):
            pass

    return detected, fix_correct


def score_audit(actual: dict | None) -> tuple[float, dict]:
    """Score audit output with cascading-aware FP classification.

    Scoring dimensions:
    - Root-cause recall (weight 0.5): Did the model find the planted errors?
    - Fix accuracy (weight 0.5): Did the model provide correct replacement values?
    - FP penalty (up to -0.3): Only penalizes truly spurious errors, not cascading
      consequences of planted errors (e.g. total_sensible_w wrong because
      conduction_w was wrong).
    """
    cascading_set = build_cascading_set(PLANTED_ERRORS)

    details: dict = {
        "n_planted": N_PLANTED,
        "detected": 0,
        "correct_fixes": 0,
        "cascading_matches": 0,
        "true_false_positives": 0,
        "recall": 0.0,
        "fix_accuracy": 0.0,
        "fp_penalty": 0.0,
    }

    if not actual:
        return 0.0, details

    errors_found = actual.get("errors_found", [])
    if not isinstance(errors_found, list):
        return 0.0, details

    # Track which planted errors have been matched
    matched_planted = [False] * N_PLANTED
    correct_fixes = 0
    detected_count = 0

    for found in errors_found:
        found_match = False
        for i, planted in enumerate(PLANTED_ERRORS):
            if matched_planted[i]:
                continue
            detected, fix_ok = match_error(planted, found)
            if detected:
                matched_planted[i] = True
                detected_count += 1
                if fix_ok:
                    correct_fixes += 1
                found_match = True
                break

        if not found_match:
            # Check if this is a cascading consequence of a planted error
            found_key = (found.get("room_no"), found.get("field"))
            if found_key in cascading_set:
                details["cascading_matches"] += 1
            else:
                details["true_false_positives"] += 1

    recall = detected_count / N_PLANTED
    fix_accuracy = correct_fixes / max(detected_count, 1)
    fp_penalty = min(details["true_false_positives"] * 0.1, 0.3)

    reward = max(0.0, min(1.0, 0.5 * recall + 0.5 * fix_accuracy - fp_penalty))

    details.update({
        "detected": detected_count,
        "correct_fixes": correct_fixes,
        "recall": round(recall, 4),
        "fix_accuracy": round(fix_accuracy, 4),
        "fp_penalty": round(fp_penalty, 4),
    })

    return round(reward, 2), details


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify audit-office-building-L3 output")
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_REWARD_FILE)
    args = parser.parse_args()

    try:
        if not args.input.exists() or args.input.stat().st_size == 0:
            write_reward(0.0, {"error": "no output file"}, args.output)
            return

        text = args.input.read_text()
        actual = extract_json_block(text)
        reward, details = score_audit(actual)
        write_reward(reward, details, args.output)
    except Exception:
        write_reward(0.0, {"error": "exception during verification"}, args.output)


if __name__ == "__main__":
    main()
