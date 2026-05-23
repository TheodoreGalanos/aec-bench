# ABOUTME: codes_search tool executor for adapter-managed task tools in aec-bench Python.
# ABOUTME: Invokes the staged CLI wrapper inside the workspace and translates arguments to flags.

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.adapters.tool_loop import ToolExecutionResult
from aec_bench.adapters.tools import coerce_timeout, run_subprocess_tool


@dataclass(frozen=True)
class CodesSearchToolExecutor:
    workspace_dir: Path
    script_path: Path
    python_executable: str = "python3"
    default_timeout_seconds: float = 30.0

    def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        timeout_seconds = coerce_timeout(
            arguments.get("timeout_seconds"),
            self.default_timeout_seconds,
        )
        command = [
            self.python_executable,
            str(self._resolved_script_path()),
            *_build_cli_args(arguments),
        ]

        return run_subprocess_tool(
            command,
            cwd=self.workspace_dir,
            timeout_seconds=timeout_seconds,
            tool_label="codes_search",
        )

    def _resolved_script_path(self) -> Path:
        if self.script_path.is_absolute():
            return self.script_path
        return self.workspace_dir / self.script_path


def _build_cli_args(arguments: dict[str, Any]) -> list[str]:
    ordered_keys = ["query", "jurisdiction", "code_type", "limit", "year", "keywords"]
    skip = set(ordered_keys) | {"timeout_seconds"}
    remaining = sorted(k for k in arguments if k not in skip)
    cli_args: list[str] = []
    for key in ordered_keys + remaining:
        value = arguments.get(key)
        if value is None:
            continue
        cli_args.extend(_argument_pair(key, value))
    return cli_args


def _argument_pair(key: str, value: Any) -> list[str]:
    flag = f"--{key.replace('_', '-')}"
    if isinstance(value, bool):
        return [flag] if value else []
    if isinstance(value, list):
        return [flag, ",".join(str(item) for item in value)]
    return [flag, str(value)]
