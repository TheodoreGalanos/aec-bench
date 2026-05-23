# ABOUTME: Generates a self-contained verify.py script for a sampled task instance.
# ABOUTME: The generated script has hardcoded ground truth and tolerances; no aec_bench imports.

import textwrap

from aec_bench.generation.contracts import SampledInstance
from aec_bench.templates.contracts import TemplateConfig


def generate_verifier(instance: SampledInstance, config: TemplateConfig) -> str:
    """Return a self-contained verify.py script string for the given instance.

    The generated script:
    - Has hardcoded ground truth values from instance.ground_truth
    - Has per-field tolerances from config.outputs (defaulting to 0.03)
    - Extracts the last fenced ```json block from the agent output file
    - Scores field-by-field with math.isclose
    - Writes reward.json and details.json
    - Handles all error cases with reward 0.0
    - Accepts --input and --output CLI flags
    """
    ground_truth_repr = _format_dict_of_floats(instance.ground_truth)
    tolerances_repr = _build_tolerances_repr(instance.ground_truth, config)
    instance_name = instance.instance_name

    return textwrap.dedent(f"""\
        # ABOUTME: Auto-generated verifier for instance {instance_name!r}.
        # ABOUTME: Scores agent output against hardcoded ground truth; no external imports needed.

        import argparse
        import json
        import math
        import re
        from pathlib import Path

        DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
        DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

        GROUND_TRUTH: dict[str, float] = {ground_truth_repr}

        TOLERANCES: dict[str, float] = {tolerances_repr}


        def write_reward(reward: float, details: dict[str, float], path: Path) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({{"reward": round(reward, 2)}}))
            details_path = path.parent / "details.json"
            details_path.write_text(json.dumps(details))


        def extract_json_block(text: str) -> dict | None:
            pattern = r"```json\\s*\\n(.*?)\\n\\s*```"
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
                details = {{key: 0.0 for key in expected}}
                return 0.0, details

            details: dict[str, float] = {{}}
            for key, exp_val in expected.items():
                act_val = actual.get(key)
                tol = TOLERANCES.get(key, 0.03)
                details[key] = score_field(exp_val, act_val, tol)

            total = len(expected)
            reward = sum(details.values()) / total if total > 0 else 0.0
            return round(reward, 2), details


        def main() -> None:
            parser = argparse.ArgumentParser(description="Verify output for {instance_name!r}")
            parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_FILE)
            parser.add_argument("--output", type=Path, default=DEFAULT_REWARD_FILE)
            args = parser.parse_args()

            try:
                if not args.input.exists() or args.input.stat().st_size == 0:
                    details = {{key: 0.0 for key in GROUND_TRUTH}}
                    write_reward(0.0, details, args.output)
                    return

                text = args.input.read_text()
                actual = extract_json_block(text)
                reward, details = score_answers(GROUND_TRUTH, actual)
                write_reward(reward, details, args.output)
            except Exception:
                details = {{key: 0.0 for key in GROUND_TRUTH}}
                write_reward(0.0, details, args.output)


        if __name__ == "__main__":
            main()
    """)


def _format_dict_of_floats(data: dict[str, float]) -> str:
    """Render a dict[str, float] as a Python literal string."""
    if not data:
        return "{}"
    inner = ", ".join(f"{k!r}: {v!r}" for k, v in sorted(data.items()))
    return "{" + inner + "}"


def _build_tolerances_repr(
    ground_truth: dict[str, float],
    config: TemplateConfig,
) -> str:
    """Build a tolerances dict using config.outputs tolerances, falling back to 0.03."""
    tolerances: dict[str, float] = {}
    for field in ground_truth:
        output_spec = config.outputs.get(field)
        tolerances[field] = output_spec.tolerance if output_spec is not None else 0.03
    return _format_dict_of_floats(tolerances)
