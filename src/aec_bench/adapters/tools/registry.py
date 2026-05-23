# ABOUTME: Tool executor resolution for adapter-declared task tools in aec-bench Python.
# ABOUTME: Maps declared ToolSpec records to concrete executors without leaking backend policy.

from dataclasses import dataclass
from pathlib import Path

from aec_bench.adapters.tools.bash import BashToolExecutor
from aec_bench.adapters.tools.codes_search import CodesSearchToolExecutor
from aec_bench.contracts.task_definition import ToolSpec


@dataclass(frozen=True)
class ToolExecutorRegistry:
    workspace_dir: Path

    def resolve(self, tool: ToolSpec) -> BashToolExecutor | CodesSearchToolExecutor:
        if tool.name == "bash":
            return BashToolExecutor(workspace_dir=self.workspace_dir)
        if tool.name == "codes_search":
            return CodesSearchToolExecutor(
                workspace_dir=self.workspace_dir,
                script_path=Path(tool.source),
            )
        raise ValueError(f"unsupported tool: {tool.name}")
