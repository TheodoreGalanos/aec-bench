# ABOUTME: Auto-generated verifier for instance 'sydney-greenfield-new-pvc-00'.
# ABOUTME: Scores agent output against hardcoded ground truth; no external imports needed.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

GROUND_TRUTH: dict[str, float] = {'flow_velocity_m_s': 1.7, 'head_loss_m': 2.83, 'hydraulic_gradient': 0.004}

TOLERANCES: dict[str, float] = {'flow_velocity_m_s': 0.03, 'head_loss_m': 0.03, 'hydraulic_gradient': 0.05}


def write_reward(reward: float, details: dict[str, float], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": round(reward, 2)}))
    details_path = path.parent / "details.json"
    details_path.write_text(json.dumps(details))


def extract_json_block(text: str) -> dict | None:
    pattern = r"```json\s*\n(.*?)\n\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def score_field(expected: float, actual_val: object, rel_tol: float) -> float:
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
    expected: dict[str, float], actual: dict | None,
) -> tuple[float, dict[str, float]]:
    if not actual:
        details = {key: 0.0 for key in expected}
        return 0.0, details

    details: dict[str, float] = {}
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        tol = TOLERANCES.get(key, 0.03)
        details[key] = score_field(exp_val, act_val, tol)

    total = len(expected)
    reward = sum(details.values()) / total if total > 0 else 0.0
    return round(reward, 2), details


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify output for 'sydney-greenfield-new-pvc-00'")
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_REWARD_FILE)
    args = parser.parse_args()

    try:
        if not args.input.exists() or args.input.stat().st_size == 0:
            details = {key: 0.0 for key in GROUND_TRUTH}
            write_reward(0.0, details, args.output)
            return

        text = args.input.read_text()
        actual = extract_json_block(text)
        reward, details = score_answers(GROUND_TRUTH, actual)
        write_reward(reward, details, args.output)
    except Exception:
        details = {key: 0.0 for key in GROUND_TRUTH}
        write_reward(0.0, details, args.output)


if __name__ == "__main__":
    main()
