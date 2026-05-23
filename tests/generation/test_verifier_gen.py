# ABOUTME: Tests for the verifier generator — generate_verifier() function.
# ABOUTME: Covers generated script correctness and runtime behaviour via subprocess execution.

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.generation.contracts import GenerationMetadata, SampledInstance
from aec_bench.generation.verifier_gen import generate_verifier
from aec_bench.templates.contracts import (
    OutputSpec,
    ParamSpec,
    ParamType,
    TemplateConfig,
    TemplateMeta,
    ToolMode,
    VisibilityLevel,
)


def _build_test_instance() -> SampledInstance:
    """Build a minimal SampledInstance with two ground truth outputs."""
    return SampledInstance(
        instance_name="test-01",
        all_params={"value_a": 5.0},
        visible_params={"value_a": 5.0},
        hidden_params={},
        ground_truth={"result_x": 10.0, "result_y": 20.0},
        archetype_name="test_arch",
        site_context="test-site",
        difficulty="easy",
        metadata=GenerationMetadata(
            template="test",
            seed=42,
            timestamp=datetime.now(UTC),
            difficulty="easy",
            visibility_level=VisibilityLevel.ALL_GIVEN,
            archetype="test_arch",
            site_context="test-site",
        ),
    )


def _build_test_config() -> TemplateConfig:
    """Build a minimal TemplateConfig with two outputs at different tolerances."""
    meta = TemplateMeta.model_validate(
        {
            "name": "test-template",
            "description": "A template for testing verifier gen",
            "discipline": "Geotechnical",
            "category": "shallow-foundations",
            "tool_mode": ToolMode.WITH_TOOL,
        }
    )

    params = {
        "value_a": ParamSpec.model_validate(
            {
                "type": ParamType.FLOAT,
                "description": "Primary float parameter",
                "unit": "kN",
                "min_value": 0.0,
                "max_value": 100.0,
            }
        ),
    }

    outputs = {
        "result_x": OutputSpec.model_validate(
            {
                "description": "First computed result",
                "tolerance": 0.05,
            }
        ),
        "result_y": OutputSpec.model_validate(
            {
                "description": "Second computed result",
                "tolerance": 0.02,
            }
        ),
    }

    return TemplateConfig.model_validate(
        {
            "meta": meta,
            "params": params,
            "outputs": outputs,
        }
    )


# --- Tests ---


def test_generate_verifier_is_valid_python() -> None:
    """Generated code must compile without errors."""
    instance = _build_test_instance()
    config = _build_test_config()

    code = generate_verifier(instance, config)

    # compile() raises SyntaxError if the code is not valid Python
    compiled = compile(code, "<generated_verify>", "exec")
    assert compiled is not None


def test_generate_verifier_has_ground_truth_values() -> None:
    """Generated code must contain the hardcoded ground truth values."""
    instance = _build_test_instance()
    config = _build_test_config()

    code = generate_verifier(instance, config)

    assert "10.0" in code
    assert "20.0" in code


def test_generate_verifier_has_per_field_tolerances() -> None:
    """Generated code must embed per-field tolerance values from config.outputs."""
    instance = _build_test_instance()
    config = _build_test_config()

    code = generate_verifier(instance, config)

    # result_x has tolerance 0.05, result_y has tolerance 0.02
    assert "0.05" in code
    assert "0.02" in code


def test_generate_verifier_writes_reward_json() -> None:
    """Generated code must reference 'reward.json' as the reward output path."""
    instance = _build_test_instance()
    config = _build_test_config()

    code = generate_verifier(instance, config)

    assert "reward.json" in code


def test_generate_verifier_writes_details_json() -> None:
    """Generated code must reference 'details.json' for per-field breakdown."""
    instance = _build_test_instance()
    config = _build_test_config()

    code = generate_verifier(instance, config)

    assert "details.json" in code


def test_generate_verifier_handles_missing_output() -> None:
    """Generated code must check whether the agent output file exists."""
    instance = _build_test_instance()
    config = _build_test_config()

    code = generate_verifier(instance, config)

    # Must contain an existence check (exists() method call)
    assert ".exists()" in code


def test_generate_verifier_extracts_json_block() -> None:
    """Generated code must contain the regex pattern for fenced JSON blocks."""
    instance = _build_test_instance()
    config = _build_test_config()

    code = generate_verifier(instance, config)

    # The established pattern for extracting json fenced blocks
    assert "```json" in code


def test_generate_verifier_partial_reward(tmp_path: Path) -> None:
    """Running the generated verifier against 1-of-2 correct answers returns reward 0.5."""
    instance = _build_test_instance()
    config = _build_test_config()

    # Write the generated script to a temp file
    verifier_path = tmp_path / "verify.py"
    verifier_path.write_text(generate_verifier(instance, config))

    # Create a fake agent output with result_x correct, result_y wrong
    agent_output = tmp_path / "output.md"
    agent_output.write_text('Some preamble text.\n\n```json\n{"result_x": 10.0, "result_y": 999.0}\n```\n')

    reward_path = tmp_path / "reward.json"

    result = subprocess.run(
        [
            sys.executable,
            str(verifier_path),
            "--input",
            str(agent_output),
            "--output",
            str(reward_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Verifier failed: {result.stderr}"
    assert reward_path.exists(), "reward.json was not written"

    reward_data = json.loads(reward_path.read_text())
    assert "reward" in reward_data
    assert reward_data["reward"] == pytest.approx(0.5, abs=0.01)
