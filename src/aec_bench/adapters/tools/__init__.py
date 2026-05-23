# ABOUTME: Tool integration package for adapter-exposed task tools in aec-bench.
# ABOUTME: Shared helpers for tool executors live here; concrete wrappers in submodules.

import subprocess
from pathlib import Path
from typing import Any

from aec_bench.adapters.tool_loop import ToolExecutionResult


def coerce_timeout(value: Any, default_timeout_seconds: float) -> float:
    """Coerce a timeout value to a positive float, falling back to the default."""
    if value is None:
        return default_timeout_seconds
    if isinstance(value, int | float) and value > 0:
        return float(value)
    return default_timeout_seconds


def join_subprocess_output(stdout: str, stderr: str) -> str:
    """Combine stdout and stderr into a single output string, stripping whitespace."""
    return "\n".join(part for part in [stdout.strip(), stderr.strip()] if part)


def run_subprocess_tool(
    command: str | list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    tool_label: str,
    shell: bool = False,
) -> ToolExecutionResult:
    """Run a subprocess and return a structured tool result."""
    try:
        completed = subprocess.run(
            command,
            shell=shell,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolExecutionResult(
            output_text="",
            error_message=f"{tool_label} timed out after {timeout_seconds} seconds",
        )

    output_text = join_subprocess_output(completed.stdout, completed.stderr)
    if completed.returncode != 0:
        return ToolExecutionResult(
            output_text=output_text,
            error_message=f"{tool_label} failed with exit code {completed.returncode}",
        )
    return ToolExecutionResult(output_text=output_text)
