# ABOUTME: Tests for the CLI wrapper generator — generate_cli_wrapper() function.
# ABOUTME: Covers generated code correctness, argparse args, tracing, and subprocess execution.

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from aec_bench.generation.cli_wrapper_gen import generate_cli_wrapper
from aec_bench.templates.contracts import (
    OutputSpec,
    ParamSpec,
    ParamType,
    TemplateConfig,
    TemplateMeta,
    ToolMode,
)


def _build_minimal_config() -> TemplateConfig:
    """Build a minimal TemplateConfig with one float param for testing."""
    meta = TemplateMeta.model_validate(
        {
            "name": "test",
            "description": "test",
            "discipline": "test",
            "category": "test",
            "tool_mode": ToolMode.WITH_TOOL,
        }
    )
    params = {
        "value_a": ParamSpec.model_validate(
            {
                "type": ParamType.FLOAT,
                "description": "Input A",
                "unit": "m",
                "min_value": 0.0,
                "max_value": 100.0,
            }
        )
    }
    outputs = {"result": OutputSpec.model_validate({"description": "The result"})}
    return TemplateConfig.model_validate({"meta": meta, "params": params, "outputs": outputs})


def _build_full_config() -> TemplateConfig:
    """Build a TemplateConfig with float, int, and enum params for testing."""
    meta = TemplateMeta.model_validate(
        {
            "name": "geotechnical-bearing",
            "description": "Bearing capacity calculation",
            "discipline": "Geotechnical",
            "category": "shallow-foundations",
            "tool_mode": ToolMode.WITH_TOOL,
        }
    )
    params = {
        "cohesion_kpa": ParamSpec.model_validate(
            {
                "type": ParamType.FLOAT,
                "description": "Effective cohesion c'",
                "unit": "kPa",
                "min_value": 0.0,
                "max_value": 150.0,
            }
        ),
        "depth_m": ParamSpec.model_validate(
            {
                "type": ParamType.INT,
                "description": "Foundation depth",
                "unit": "m",
                "min_value": 0,
                "max_value": 10,
            }
        ),
        "soil_type": ParamSpec.model_validate(
            {
                "type": ParamType.ENUM,
                "description": "Soil classification",
                "values": ["clay", "sand", "gravel"],
            }
        ),
    }
    outputs = {"bearing_capacity": OutputSpec.model_validate({"description": "Ultimate bearing capacity"})}
    return TemplateConfig.model_validate({"meta": meta, "params": params, "outputs": outputs})


_TRIVIAL_ENGINE = textwrap.dedent("""\
    def compute(value_a: float = 0.0) -> dict[str, float]:
        return {"result": value_a * 2}
""")

_FULL_ENGINE = textwrap.dedent("""\
    def compute(
        cohesion_kpa: float = 0.0, depth_m: int = 1, soil_type: str = "clay"
    ) -> dict[str, float]:
        return {"bearing_capacity": cohesion_kpa * depth_m}
""")


# --- Test 1: generated code must be valid Python ---


def test_generate_cli_wrapper_is_valid_python() -> None:
    """compile() must succeed on the generated source without syntax errors."""
    config = _build_minimal_config()
    code = generate_cli_wrapper(config, _TRIVIAL_ENGINE)
    assert isinstance(code, str)
    assert len(code) > 0
    # Will raise SyntaxError if code is invalid
    compile(code, "<test>", "exec")


# --- Test 2: generated code has argparse args derived from param names ---


def test_generate_cli_wrapper_has_argparse_args() -> None:
    """Generated code must contain CLI args in kebab-case derived from param names."""
    config = _build_full_config()
    code = generate_cli_wrapper(config, _FULL_ENGINE)
    # cohesion_kpa -> --cohesion-kpa
    assert "--cohesion-kpa" in code
    # depth_m -> --depth-m
    assert "--depth-m" in code
    # soil_type -> --soil-type
    assert "--soil-type" in code


# --- Test 3: generated code has tracing to invocations.jsonl ---


def test_generate_cli_wrapper_has_tracing() -> None:
    """Generated code must reference invocations.jsonl for trace logging."""
    config = _build_minimal_config()
    code = generate_cli_wrapper(config, _TRIVIAL_ENGINE)
    assert "invocations.jsonl" in code


# --- Test 4: generated code has --help-params flag ---


def test_generate_cli_wrapper_has_help_params() -> None:
    """Generated code must include a --help-params flag."""
    config = _build_minimal_config()
    code = generate_cli_wrapper(config, _TRIVIAL_ENGINE)
    # Accept either the flag name or the dest attribute name
    assert "help_params" in code or "help-params" in code


# --- Test 5: generated code has --format flag ---


def test_generate_cli_wrapper_has_format_flag() -> None:
    """Generated code must include a --format flag supporting json and table."""
    config = _build_minimal_config()
    code = generate_cli_wrapper(config, _TRIVIAL_ENGINE)
    assert "--format" in code


# --- Test 6: engine source is embedded verbatim ---


def test_generate_cli_wrapper_includes_engine() -> None:
    """The engine source text must appear verbatim in the generated code."""
    config = _build_minimal_config()
    code = generate_cli_wrapper(config, _TRIVIAL_ENGINE)
    assert _TRIVIAL_ENGINE in code


# --- Test 7: generated script actually executes and returns correct JSON ---


def test_generated_cli_wrapper_executes_and_returns_json(tmp_path: Path) -> None:
    """Write generated code to a file, run it, verify JSON output is correct."""
    config = _build_minimal_config()
    code = generate_cli_wrapper(config, _TRIVIAL_ENGINE)

    script_path = tmp_path / "generated_tool.py"
    script_path.write_text(code)

    result = subprocess.run(
        [sys.executable, str(script_path), "--value-a", "5.0"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    output = json.loads(result.stdout)
    assert output["result"] == pytest.approx(10.0)


# --- Test 8: enum params use choices in argparse ---


def test_generate_cli_wrapper_enum_uses_choices() -> None:
    """Enum params must appear as choices in the generated argparse setup."""
    config = _build_full_config()
    code = generate_cli_wrapper(config, _FULL_ENGINE)
    # The enum values should appear as choices
    assert "clay" in code
    assert "sand" in code
    assert "gravel" in code


# --- Test 9: help text includes description and unit ---


def test_generate_cli_wrapper_help_includes_unit() -> None:
    """Help text for float/int params must include both description and unit."""
    config = _build_full_config()
    code = generate_cli_wrapper(config, _FULL_ENGINE)
    # The description and unit should appear together
    assert "Effective cohesion c'" in code
    assert "kPa" in code


# --- Test 10: --format table produces key:value output ---


def test_generated_cli_wrapper_format_table(tmp_path: Path) -> None:
    """--format table must produce key: value lines instead of JSON."""
    config = _build_minimal_config()
    code = generate_cli_wrapper(config, _TRIVIAL_ENGINE)

    script_path = tmp_path / "generated_tool_table.py"
    script_path.write_text(code)

    result = subprocess.run(
        [sys.executable, str(script_path), "--value-a", "3.0", "--format", "table"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    # Table format: "result: 6.0" style output
    assert "result" in result.stdout
    assert "6.0" in result.stdout
