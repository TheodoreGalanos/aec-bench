# ABOUTME: Verifier for P(f) droop curve multimodal task.
# ABOUTME: Scores agent output against ground truth with 3% relative tolerance per field.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_GROUND_TRUTH_FILE = Path("/tests/ground_truth.json")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

FIELDS = ["slope_mw_per_hz", "active_power_mw", "delta_p_mw"]
REL_TOL = 0.03


def write_reward(reward: float, details: dict[str, float], path: Path) -> None:
    """Write reward JSON for Harbor, plus per-field details to a sibling file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": round(reward, 2)}))
    details_path = path.parent / "details.json"
    details_path.write_text(json.dumps(details))


def load_ground_truth(path: Path) -> dict[str, float]:
    """Load expected values from ground_truth.json."""
    return json.loads(path.read_text(encoding="utf-8"))


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


def score_field(expected: float, actual_val: object) -> float:
    """Score a single field: 1.0 if within relative tolerance, 0.0 otherwise."""
    if actual_val is None:
        return 0.0
    try:
        actual_float = float(actual_val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if math.isclose(actual_float, expected, rel_tol=REL_TOL):
        return 1.0
    return 0.0


def score_answers(
    expected: dict[str, float], actual: dict | None
) -> tuple[float, dict[str, float]]:
    """Score each field and return overall reward plus per-field details."""
    if not actual:
        details = {k: 0.0 for k in FIELDS}
        return 0.0, details

    details: dict[str, float] = {}
    for key in FIELDS:
        exp_val = expected.get(key)
        act_val = actual.get(key)
        if exp_val is None:
            details[key] = 0.0
        else:
            details[key] = score_field(exp_val, act_val)

    total = len(FIELDS)
    reward = sum(details.values()) / total if total > 0 else 0.0
    return round(reward, 2), details


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify P(f) droop output")
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_REWARD_FILE)
    args = parser.parse_args()

    try:
        if not args.input.exists() or args.input.stat().st_size == 0:
            details = {k: 0.0 for k in FIELDS}
            write_reward(0.0, details, args.output)
            return

        expected = load_ground_truth(args.ground_truth)
        text = args.input.read_text(encoding="utf-8")
        actual = extract_json_block(text)
        reward, details = score_answers(expected, actual)
        write_reward(reward, details, args.output)
    except Exception:
        details = {k: 0.0 for k in FIELDS}
        write_reward(0.0, details, args.output)


if __name__ == "__main__":
    main()
