#!/usr/bin/env python3
# ABOUTME: Verifier for the RLM test task — voltage drop calculation.
# ABOUTME: Extracts JSON from output.md and scores against ground truth.

import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT = Path("/workspace/output.md")
DEFAULT_REWARD = Path("/logs/verifier/reward.json")


def compute_ground_truth() -> dict[str, float]:
    I, L, R, X, pf, V = 45.0, 80.0, 0.524, 0.08, 0.85, 400.0
    sin_phi = math.sin(math.acos(pf))
    Vd = math.sqrt(3) * I * L * (R * pf + X * sin_phi) / 1000
    Vd_pct = Vd / V * 100
    return {
        "voltage_drop_v": Vd,
        "voltage_drop_pct": Vd_pct,
        "compliance": 1.0 if Vd_pct <= 5.0 else 0.0,
    }


def extract_json(text: str) -> dict | None:
    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def score(expected: dict, actual: dict | None) -> tuple[float, dict]:
    if actual is None:
        return 0.0, {k: 0.0 for k in expected}
    details = {}
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        if act_val is None:
            details[key] = 0.0
            continue
        try:
            act_float = float(act_val)
        except (TypeError, ValueError):
            details[key] = 0.0
            continue
        if key == "compliance":
            details[key] = 1.0 if act_float == exp_val else 0.0
        else:
            details[key] = 1.0 if math.isclose(act_float, exp_val, rel_tol=0.03) else 0.0
    reward = sum(details.values()) / len(details) if details else 0.0
    return reward, details


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REWARD)
    args = parser.parse_args()

    try:
        text = args.input.read_text() if args.input.exists() else ""
        expected = compute_ground_truth()
        actual = extract_json(text)
        reward, details = score(expected, actual)
    except Exception:
        expected = compute_ground_truth()
        reward, details = 0.0, {k: 0.0 for k in expected}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"reward": round(reward, 2)}))
    (args.output.parent / "details.json").write_text(json.dumps(details))


if __name__ == "__main__":
    main()
