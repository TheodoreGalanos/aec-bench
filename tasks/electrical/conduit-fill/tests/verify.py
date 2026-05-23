# ABOUTME: Verifier for conduit-fill task.
# ABOUTME: Computes ground truth from cable geometry and scores agent output.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")


def write_reward(reward: float, details: dict[str, float], path: Path) -> None:
    """Write reward JSON for Harbor, plus per-field details to a sibling file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": round(reward, 2)}))
    details_path = path.parent / "details.json"
    details_path.write_text(json.dumps(details))


def compute_ground_truth() -> dict[str, float]:
    """Compute expected answers from cable geometry formulas."""
    conduit_id = 50.0  # conduit internal diameter (mm)
    cat6_od = 6.2  # Cat6 cable outer diameter (mm)
    fiber_od = 3.0  # fiber cable outer diameter (mm)

    cat6_area = math.pi * (cat6_od / 2) ** 2
    fiber_area = math.pi * (fiber_od / 2) ** 2
    total_cable_area = 6 * cat6_area + 2 * fiber_area
    conduit_area = math.pi * (conduit_id / 2) ** 2
    fill_pct = (total_cable_area / conduit_area) * 100
    compliance = 1.0 if fill_pct <= 40.0 else 0.0

    return {
        "total_cable_area_mm2": total_cable_area,
        "conduit_area_mm2": conduit_area,
        "fill_pct": fill_pct,
        "compliance": compliance,
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
    expected: float, actual_val, rel_tol: float, exact: bool = False
) -> float:
    """Score a single field: 1.0 if within tolerance, 0.0 otherwise."""
    if actual_val is None:
        return 0.0
    try:
        actual_float = float(actual_val)
    except (TypeError, ValueError):
        return 0.0
    if exact:
        return 1.0 if actual_float == expected else 0.0
    if math.isclose(actual_float, expected, rel_tol=rel_tol):
        return 1.0
    return 0.0


def score_answers(
    expected: dict[str, float], actual: dict | None
) -> tuple[float, dict[str, float]]:
    """Score each field and return overall reward + per-field details."""
    tolerances = {
        "total_cable_area_mm2": {"rel_tol": 0.01, "exact": False},
        "conduit_area_mm2": {"rel_tol": 0.01, "exact": False},
        "fill_pct": {"rel_tol": 0.01, "exact": False},
        "compliance": {"rel_tol": 0.0, "exact": True},
    }

    if not actual:
        details = {k: 0.0 for k in expected}
        return 0.0, details

    details = {}
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        cfg = tolerances.get(key, {"rel_tol": 0.01, "exact": False})
        details[key] = score_field(exp_val, act_val, cfg["rel_tol"], cfg["exact"])

    total = len(expected)
    reward = sum(details.values()) / total if total > 0 else 0.0
    return round(reward, 2), details


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify conduit-fill output")
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
