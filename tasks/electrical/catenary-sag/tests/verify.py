# ABOUTME: Verifier for catenary-sag task.
# ABOUTME: Computes ground truth from catenary formulas and scores agent output.

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
    """Compute expected answers from catenary formulas."""
    H = 64500.0  # horizontal tension (N)
    w = 7.58  # conductor unit weight (N/m)
    L = 250.0  # span length (m)

    c = H / w
    sag = c * (math.cosh(L / (2 * c)) - 1)
    length = 2 * c * math.sinh(L / (2 * c))

    return {
        "catenary_constant_m": c,
        "sag_m": sag,
        "conductor_length_m": length,
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


def score_field(expected: float, actual_val, rel_tol: float) -> float:
    """Score a single field: 1.0 if within tolerance, 0.0 otherwise."""
    if actual_val is None:
        return 0.0
    try:
        actual_float = float(actual_val)
    except (TypeError, ValueError):
        return 0.0
    if math.isclose(actual_float, expected, rel_tol=rel_tol):
        return 1.0
    return 0.0


def score_answers(
    expected: dict[str, float], actual: dict | None
) -> tuple[float, dict[str, float]]:
    """Score each field and return overall reward + per-field details."""
    tolerances = {
        "catenary_constant_m": 0.02,
        "sag_m": 0.02,
        "conductor_length_m": 0.02,
    }

    if not actual:
        details = {k: 0.0 for k in expected}
        return 0.0, details

    details = {}
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        tol = tolerances.get(key, 0.02)
        details[key] = score_field(exp_val, act_val, tol)

    total = len(expected)
    reward = sum(details.values()) / total if total > 0 else 0.0
    return round(reward, 2), details


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify catenary-sag output")
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
