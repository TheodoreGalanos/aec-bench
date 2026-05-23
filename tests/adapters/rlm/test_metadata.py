# ABOUTME: Tests for RLM iteration metadata extraction and formatting.
# ABOUTME: Validates format_iteration_metadata produces correct compact output.

"""Tests for RLM iteration metadata extraction and formatting."""

from aec_bench.adapters.rlm.engine import ExecutionResult
from aec_bench.adapters.rlm.metadata import format_iteration_metadata


def test_metadata_includes_variable_names() -> None:
    result = ExecutionResult(stdout="42\n", variables_changed=["answer"])
    variables = {"answer": "int", "data": "list"}
    metadata = format_iteration_metadata(
        result=result,
        variables=variables,
        iteration=1,
        token_budget_pct=10.0,
    )
    assert "answer" in metadata
    assert "int" in metadata


def test_metadata_includes_iteration_number() -> None:
    result = ExecutionResult(stdout="ok\n")
    metadata = format_iteration_metadata(
        result=result,
        variables={},
        iteration=5,
        token_budget_pct=45.0,
    )
    assert "5" in metadata


def test_metadata_includes_budget_warning_when_high() -> None:
    result = ExecutionResult(stdout="")
    metadata = format_iteration_metadata(
        result=result,
        variables={},
        iteration=10,
        token_budget_pct=85.0,
    )
    assert "budget" in metadata.lower() or "85" in metadata


def test_metadata_includes_error_when_present() -> None:
    result = ExecutionResult(stdout="", error="ZeroDivisionError: division by zero")
    metadata = format_iteration_metadata(
        result=result,
        variables={},
        iteration=1,
        token_budget_pct=5.0,
    )
    assert "ZeroDivisionError" in metadata


def test_metadata_does_not_include_full_stdout() -> None:
    long_output = "x" * 5000
    result = ExecutionResult(stdout=long_output)
    metadata = format_iteration_metadata(
        result=result,
        variables={},
        iteration=1,
        token_budget_pct=5.0,
    )
    assert len(metadata) < 1000


def test_metadata_with_no_execution_result() -> None:
    metadata = format_iteration_metadata(
        result=None,
        variables={"x": "int"},
        iteration=3,
        token_budget_pct=20.0,
    )
    assert "3" in metadata
    assert "no code executed" in metadata.lower()
    assert "x" in metadata


def test_metadata_includes_template_status() -> None:
    from aec_bench.adapters.rlm.template import TemplateStatus

    status = TemplateStatus(
        total_sections=5,
        completed_sections=2,
        unlocked=["methodology"],
        pending=["aie", "risks"],
        completed=["background", "design"],
    )
    metadata = format_iteration_metadata(
        result=None,
        variables={},
        iteration=3,
        token_budget_pct=30.0,
        template_status=status,
    )
    assert "2/5" in metadata
    assert "methodology" in metadata
