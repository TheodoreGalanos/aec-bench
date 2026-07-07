# ABOUTME: Verifier for capesize-bulk-carrier Block coefficient calculation task.
# ABOUTME: Computes ground truth from IACS CSR-H Pt 1 Ch 1 Sec 4 §3.1.8 and scores agent output.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

# ---- Input parameters (Capesize bulk carrier) ----
MOULDED_DISPLACEMENT_T = 180000.0
RULE_LENGTH_L_M = 280.0
MOULDED_BREADTH_B_M = 45.0
SCANTLING_DRAUGHT_TSC_M = 18.0

# CSR-H 01 JUL 2025 Pt 1 Ch 1 Sec 4 §3.1.8
SEAWATER_DENSITY_T_M3 = 1.025


def write_reward(reward: float, details: dict[str, float], path: Path) -> None:
    """Write reward JSON for Harbor, plus per-field details to a sibling file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": round(reward, 2)}))
    details_path = path.parent / "details.json"
    details_path.write_text(json.dumps(details))


def compute_ground_truth() -> dict[str, float]:
    """Compute the expected Block coefficient C_B for this instance.

    C_B = Delta / (1.025 x L x B x T_SC) = 180000 / (1.025 x 280 x 45 x 18) = 0.77.
    """
    block_coefficient_cb = MOULDED_DISPLACEMENT_T / (
        SEAWATER_DENSITY_T_M3 * RULE_LENGTH_L_M * MOULDED_BREADTH_B_M * SCANTLING_DRAUGHT_TSC_M
    )

    return {
        "block_coefficient_CB": round(block_coefficient_cb, 2),
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
    expected: float,
    actual_val: object,
    rel_tol: float,
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
    expected: dict[str, float],
    actual: dict | None,
) -> tuple[float, dict[str, float]]:
    """Score each field and return overall reward + per-field details."""
    tolerances: dict[str, float] = {
        "block_coefficient_CB": 0.03,
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
    parser = argparse.ArgumentParser(description="Verify capesize-bulk-carrier output")
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
