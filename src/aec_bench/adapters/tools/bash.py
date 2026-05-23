# ABOUTME: Bash tool executor for adapter-managed task tools in aec-bench Python.
# ABOUTME: Runs shell commands inside the workspace and reports stdout, stderr, and timeouts.

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.adapters.tool_loop import ToolExecutionResult
from aec_bench.adapters.tools import coerce_timeout, run_subprocess_tool


@dataclass(frozen=True)
class BashToolExecutor:
    workspace_dir: Path
    default_timeout_seconds: float = 30.0

    def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            return ToolExecutionResult(
                output_text="",
                error_message="bash tool requires a non-empty command",
            )

        timeout_seconds = coerce_timeout(
            arguments.get("timeout_seconds"),
            self.default_timeout_seconds,
        )

        return run_subprocess_tool(
            command,
            cwd=self.workspace_dir,
            timeout_seconds=timeout_seconds,
            tool_label="bash command",
            shell=True,
        )
