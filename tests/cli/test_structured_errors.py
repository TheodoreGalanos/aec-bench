# ABOUTME: Tests for structured CLI errors with remediation steps.
# ABOUTME: Validates error creation, rendering, and JSON serialisation.

from __future__ import annotations

from aec_bench.cli.output import StructuredError


def test_structured_error_fields() -> None:
    err = StructuredError(
        message="Backend connection failed",
        why="ANTHROPIC_API_KEY is not set in the environment",
        fix="Export the API key before running",
        try_steps=["export ANTHROPIC_API_KEY=sk-ant-..."],
    )
    assert err.message == "Backend connection failed"
    assert err.why is not None
    assert len(err.try_steps) == 1


def test_structured_error_to_dict() -> None:
    err = StructuredError(
        message="Task directory not found",
        why="The path does not exist",
        fix="Check the path and try again",
        try_steps=["ls tasks/", "aec-bench task list"],
    )
    d = err.to_dict()
    assert d["message"] == "Task directory not found"
    assert d["why"] == "The path does not exist"
    assert d["fix"] == "Check the path and try again"
    assert len(d["try_steps"]) == 2


def test_structured_error_minimal() -> None:
    err = StructuredError(message="Something broke")
    assert err.why is None
    assert err.fix is None
    assert err.try_steps == []
    d = err.to_dict()
    assert "why" not in d
    assert "fix" not in d
    assert "try_steps" not in d


def test_structured_error_render_contains_key_info() -> None:
    err = StructuredError(
        message="No rlm.toml found",
        why="Task directory does not contain an rlm.toml config",
        fix="Create an rlm.toml or use --adapter direct",
        try_steps=[
            "aec-bench run-local tasks/my-task -m model --adapter direct",
        ],
    )
    rendered = err.render()
    assert "No rlm.toml found" in rendered
    assert "Why:" in rendered
    assert "Fix:" in rendered
    assert "Try:" in rendered
