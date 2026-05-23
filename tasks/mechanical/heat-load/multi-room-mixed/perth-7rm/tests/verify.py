# ABOUTME: Verifier for multi-room-mixed heat load calculation task.
# ABOUTME: Scores per-room answers and floor totals for a 7-room Perth building.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

# ---- Design conditions (Perth) ----
OUTDOOR_DB = 45.5
INDOOR_DB = 24.0
OUTDOOR_ENTHALPY = 78.4
INDOOR_ENTHALPY = 48.2

# Psychrometric constants
PEOPLE_SENSIBLE_W = 75.0
PEOPLE_LATENT_W = 55.0
AIR_SENSIBLE_FACTOR = 1.21
AIR_LATENT_DIVISOR = 0.833

# Room definitions
ROOMS = [
    {
        "room_no": 1, "name": "Lobby",
        "room_type": "Reception / Lobby", "floor_area": 80,
        "ceiling_height": 3.5, "lighting_density": 15,
        "small_power_density": 5, "conduction_factor": 20,
    },
    {
        "room_no": 2, "name": "Office",
        "room_type": "Office Areas", "floor_area": 200,
        "ceiling_height": 2.7, "lighting_density": 10,
        "small_power_density": 15, "conduction_factor": 18,
    },
    {
        "room_no": 3, "name": "Meeting Room",
        "room_type": "Meeting Rooms", "floor_area": 25,
        "ceiling_height": 2.7, "lighting_density": 10,
        "small_power_density": 8, "conduction_factor": 15,
    },
    {
        "room_no": 4, "name": "Restaurant",
        "room_type": "Restaurants", "floor_area": 150,
        "ceiling_height": 3.0, "lighting_density": 12,
        "small_power_density": 8, "conduction_factor": 15,
    },
    {
        "room_no": 5, "name": "Retail Shop",
        "room_type": "Retail Shops", "floor_area": 100,
        "ceiling_height": 3.5, "lighting_density": 18,
        "small_power_density": 10, "conduction_factor": 20,
    },
    {
        "room_no": 6, "name": "Corridor",
        "room_type": "Corridors", "floor_area": 120,
        "ceiling_height": 2.7, "lighting_density": 6,
        "small_power_density": 0, "conduction_factor": 10,
    },
    {
        "room_no": 7, "name": "Gymnasium",
        "room_type": "Gymnasiums", "floor_area": 200,
        "ceiling_height": 4.0, "lighting_density": 10,
        "small_power_density": 5, "conduction_factor": 15,
    },
]

# AS 1668.2 lookup
AS1668_TABLE: dict[str, dict[str, float]] = {
    "Corridors": {"area_per_person": 0.0, "oa_per_person": 0.0, "min_oa_rate": 0.5},
    "Gymnasiums": {"area_per_person": 5.0, "oa_per_person": 15.0, "min_oa_rate": 0.0},
    "Meeting Rooms": {"area_per_person": 3.0, "oa_per_person": 10.0, "min_oa_rate": 0.0},
    "Office Areas": {"area_per_person": 10.0, "oa_per_person": 10.0, "min_oa_rate": 0.0},
    "Reception / Lobby": {"area_per_person": 5.0, "oa_per_person": 10.0, "min_oa_rate": 0.0},
    "Restaurants": {"area_per_person": 1.5, "oa_per_person": 10.0, "min_oa_rate": 0.0},
    "Retail Shops": {"area_per_person": 5.0, "oa_per_person": 10.0, "min_oa_rate": 0.0},
}


def write_reward(reward: float, details: dict, path: Path) -> None:
    """Write reward JSON for Harbor, plus per-field details to a sibling file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": round(reward, 2)}))
    details_path = path.parent / "details.json"
    details_path.write_text(json.dumps(details))


def compute_room(room: dict) -> dict[str, float]:
    """Compute expected values for one room."""
    lookup = AS1668_TABLE[room["room_type"]]
    area_per_person = lookup["area_per_person"]
    oa_per_person = lookup["oa_per_person"]
    min_oa_rate = lookup["min_oa_rate"]

    if area_per_person > 0:
        num_people = room["floor_area"] / area_per_person
    else:
        num_people = 0.0

    if num_people > 0 and oa_per_person > 0:
        total_outside_air = num_people * oa_per_person
    else:
        total_outside_air = room["floor_area"] * min_oa_rate

    people_sensible = num_people * PEOPLE_SENSIBLE_W
    people_latent = num_people * PEOPLE_LATENT_W
    lighting = room["floor_area"] * room["lighting_density"]
    small_power = room["floor_area"] * room["small_power_density"]
    conduction = room["floor_area"] * room["conduction_factor"]

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


ROOM_FIELDS = [
    "num_people", "total_outside_air",
    "people_sensible_w", "people_latent_w",
    "lighting_w", "small_power_w", "conduction_w",
    "ventilation_sensible_w", "ventilation_latent_w",
    "total_sensible_w", "total_latent_w", "total_cooling_w",
]

FLOOR_TOTAL_FIELDS = [
    "total_sensible_w", "total_latent_w", "total_cooling_w",
]


def compute_ground_truth() -> tuple[list[dict[str, float]], dict[str, float]]:
    """Compute expected room-level and floor-level answers."""
    room_results = [compute_room(r) for r in ROOMS]
    floor_totals = {
        "total_sensible_w": sum(r["total_sensible_w"] for r in room_results),
        "total_latent_w": sum(r["total_latent_w"] for r in room_results),
        "total_cooling_w": sum(r["total_cooling_w"] for r in room_results),
    }
    return room_results, floor_totals


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


def score_field(expected: float, actual_val: object, rel_tol: float) -> float:
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


def score_answers(actual: dict | None) -> tuple[float, dict]:
    """Score per-room and floor-total fields, return overall reward + details."""
    expected_rooms, expected_floor = compute_ground_truth()
    details: dict[str, dict[str, float]] = {}

    if not actual:
        for i, room in enumerate(ROOMS):
            details[f"room_{room['room_no']}"] = {f: 0.0 for f in ROOM_FIELDS}
        details["floor_totals"] = {f: 0.0 for f in FLOOR_TOTAL_FIELDS}
        return 0.0, details

    # Score rooms
    actual_rooms = actual.get("rooms", [])
    all_scores: list[float] = []

    for i, room in enumerate(ROOMS):
        room_key = f"room_{room['room_no']}"
        room_details: dict[str, float] = {}

        # Find matching actual room by room_no
        actual_room = None
        for ar in actual_rooms:
            if ar.get("room_no") == room["room_no"]:
                actual_room = ar
                break

        for field in ROOM_FIELDS:
            tol = 0.02 if field == "num_people" else 0.03
            exp_val = expected_rooms[i][field]
            act_val = actual_room.get(field) if actual_room else None
            score = score_field(exp_val, act_val, tol)
            room_details[field] = score
            all_scores.append(score)

        details[room_key] = room_details

    # Score floor totals
    actual_floor = actual.get("floor_totals", {})
    floor_details: dict[str, float] = {}
    for field in FLOOR_TOTAL_FIELDS:
        exp_val = expected_floor[field]
        act_val = actual_floor.get(field)
        score = score_field(exp_val, act_val, 0.03)
        floor_details[field] = score
        all_scores.append(score)

    details["floor_totals"] = floor_details

    total = len(all_scores)
    reward = sum(all_scores) / total if total > 0 else 0.0
    return round(reward, 2), details


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify multi-room-mixed output")
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_REWARD_FILE)
    args = parser.parse_args()

    try:
        if not args.input.exists() or args.input.stat().st_size == 0:
            _, _ = compute_ground_truth()
            reward, details = score_answers(None)
            write_reward(reward, details, args.output)
            return

        text = args.input.read_text()
        actual = extract_json_block(text)
        reward, details = score_answers(actual)
        write_reward(reward, details, args.output)
    except Exception:
        reward, details = score_answers(None)
        write_reward(0.0, details, args.output)


if __name__ == "__main__":
    main()
