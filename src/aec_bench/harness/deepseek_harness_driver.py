# ABOUTME: Builds the DeepSeek Harness adapter from a serialized execution bundle.
# ABOUTME: Keeps SDK configuration at the backend execution composition boundary.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.adapters.deepseek_harness import DeepSeekHarnessAdapter
from aec_bench.adapters.deepseek_harness.config import DeepSeekHarnessSettings
from aec_bench.adapters.deepseek_harness.runtime import DeepSeekHarnessProcessRuntime, DeepSeekRuntime
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.harness.execution_payload import ExecutionBundle

DeepSeekRuntimeFactory = Callable[[DeepSeekHarnessSettings, Path], DeepSeekRuntime]


def _default_runtime_factory(settings: DeepSeekHarnessSettings, workspace: Path) -> DeepSeekRuntime:
    return DeepSeekHarnessProcessRuntime(settings=settings, workspace=workspace)


@dataclass(frozen=True)
class DeepSeekHarnessExecutionDriver:
    workspace_dir: Path
    runtime_factory: DeepSeekRuntimeFactory = _default_runtime_factory

    def execute(self, bundle: ExecutionBundle) -> AdapterResult:
        settings = DeepSeekHarnessSettings.from_execution_payload(
            model_name=bundle.execution.resolved_model,
            payload=bundle.execution.payload,
        )
        runtime = self.runtime_factory(settings, self.workspace_dir)
        adapter = DeepSeekHarnessAdapter(
            settings=settings,
            workspace=self.workspace_dir,
            runtime=runtime,
            adapter_name=bundle.execution.adapter_name,
        )
        return adapter.execute(_adapter_request(bundle))


def _adapter_request(bundle: ExecutionBundle) -> AdapterRequest:
    return AdapterRequest(
        instruction=bundle.request.instruction,
        system_prompt=bundle.request.system_prompt,
        tools=[ToolSpec.model_validate(tool) for tool in bundle.request.tools],
        configuration=bundle.request.configuration,
        output_path=bundle.request.output_path,
        output_format=bundle.request.output_format,
    )
