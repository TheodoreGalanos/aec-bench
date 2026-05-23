# ABOUTME: Verifier for single-room-office-no-tool heat load calculation task.
# ABOUTME: Computes ground truth from AS 1668.2 and scores agent output field-by-field.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

# ---- Input parameters (Perth, 200 m² restaurants) ----
ROOM_TYPE = "Restaurants"
FLOOR_AREA = 200
CEILING_HEIGHT = 3.0
OUTDOOR_DB = 45.5
INDOOR_DB = 24.0
OUTDOOR_ENTHALPY = 78.4
INDOOR_ENTHALPY = 48.2
LIGHTING_DENSITY = 12
SMALL_POWER_DENSITY = 8
CONDUCTION_FACTOR = 15

# AS 1668.2 lookup for Restaurants
AREA_PER_PERSON = 1.5
OA_PER_PERSON = 10.0

# Psychrometric constants
PEOPLE_SENSIBLE_W = 75.0
PEOPLE_LATENT_W = 55.0
AIR_SENSIBLE_FACTOR = 1.21
AIR_LATENT_DIVISOR = 0.833


def write_reward(reward: float, details: dict[str, float], path: Path) -> None:
    """Write reward JSON for Harbor, plus per-field details to a sibling file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": round(reward, 2)}))
    details_path = path.parent / "details.json"
    details_path.write_text(json.dumps(details))


def compute_ground_truth() -> dict[str, float]:
    """Compute expected answers for the Perth restaurants."""
    num_people = FLOOR_AREA / AREA_PER_PERSON
    total_outside_air = num_people * OA_PER_PERSON

    people_sensible = num_people * PEOPLE_SENSIBLE_W
    people_latent = num_people * PEOPLE_LATENT_W

    lighting = FLOOR_AREA * LIGHTING_DENSITY
    small_power = FLOOR_AREA * SMALL_POWER_DENSITY
    conduction = FLOOR_AREA * CONDUCTION_FACTOR

    delta_t = OUTDOOR_DB - INDOOR_DB
    ventilation_sensible = delta_t * AIR_SENSIBLE_FACTOR * total_outside_air

    delta_h = OUTDOOR_ENTHALPY - INDOOR_ENTHALPY
    ventilation_latent = delta_h * total_outside_air / AIR_LATENT_DIVISOR

    total_sensible = (
        people_sensible + lighting + small_power + conduction + ventilation_sensible
    )
    total_latent = people_latent + ventilation_latent
    total_cooling = total_sensible + total_latent

    return {
        "num_people": num_people,
        "total_outside_air": total_outside_air,
        "people_sensible_w": people_sensible,
        "people_latent_w": people_latent,
        "lighting_w": lighting,
        "small_power_w": small_power,
        "conduction_w": conduction,
        "ventilation_sensible_w": ventilation_sensible,
        "ventilation_latent_w": ventilation_latent,
        "total_sensible_w": total_sensible,
        "total_latent_w": total_latent,
        "total_cooling_w": total_cooling,
    }


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


def score_field(
    expected: float, actual_val: object, rel_tol: float,
) -> float:
    """Score a single field: 1.0 if within tolerance, 0.0 otherwise."""
    if actual_val is None:
        return 0.0
    try:
        actual_float = float(actual_val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if math.isclose(actual_float, expected, rel_tol=rel_tol):
        return 1.0
    return 0.0


def score_answers(
    expected: dict[str, float], actual: dict | None,
) -> tuple[float, dict[str, float]]:
    """Score each field and return overall reward + per-field details."""
    tolerances: dict[str, float] = {
        "num_people": 0.02,
        "total_outside_air": 0.03,
        "people_sensible_w": 0.03,
        "people_latent_w": 0.03,
        "lighting_w": 0.03,
        "small_power_w": 0.03,
        "conduction_w": 0.03,
        "ventilation_sensible_w": 0.03,
        "ventilation_latent_w": 0.03,
        "total_sensible_w": 0.03,
        "total_latent_w": 0.03,
        "total_cooling_w": 0.03,
    }

    if not actual:
        details = {k: 0.0 for k in expected}
        return 0.0, details

    details: dict[str, float] = {}
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        tol = tolerances.get(key, 0.03)
        details[key] = score_field(exp_val, act_val, tol)

    total = len(expected)
    reward = sum(details.values()) / total if total > 0 else 0.0
    return round(reward, 2), details


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify single-room-office-no-tool output")
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_REWARD_FILE)
    args = parser.parse_args()

    try:
        if not args.input.exists() or args.input.stat().st_size == 0:
            details = {k: 0.0 for k in compute_ground_truth()}
            write_reward(0.0, details, args.output)
            return

        text = args.input.read_text()
        expected = compute_ground_truth()
        actual = extract_json_block(text)
        reward, details = score_answers(expected, actual)
        write_reward(reward, details, args.output)
    except Exception:
        details = {k: 0.0 for k in compute_ground_truth()}
        write_reward(0.0, details, args.output)


if __name__ == "__main__":
    main()
