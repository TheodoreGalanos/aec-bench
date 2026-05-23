# ABOUTME: Tests for the bash tool executor in aec-bench Python.
# ABOUTME: Covers successful command execution and timeout/error reporting.

from pathlib import Path

from aec_bench.adapters.tools.bash import BashToolExecutor


def test_bash_tool_executor_runs_command_in_workspace(tmp_path: Path) -> None:
    executor = BashToolExecutor(workspace_dir=tmp_path)

    result = executor.execute({"command": "printf 'hello'"})

    assert result.error_message is None
    assert result.output_text == "hello"


def test_bash_tool_executor_reports_timeout(tmp_path: Path) -> None:
    executor = BashToolExecutor(workspace_dir=tmp_path, default_timeout_seconds=0.01)

    result = executor.execute({"command": "sleep 1"})

    assert result.error_message is not None
    assert "timed out" in result.error_message
