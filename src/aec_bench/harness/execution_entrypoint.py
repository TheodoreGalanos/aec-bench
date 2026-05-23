# ABOUTME: Backend-side adapter execution entrypoint for sandboxed runs in aec-bench Python.
# ABOUTME: Reads serialized execution bundles, dispatches them to direct, tool-loop,
# ABOUTME: RLM, and lambda-RLM drivers, and writes results.

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

from aec_bench.adapters.base import (
    AdapterRequest,
    AdapterResult,
    SerializedClientSpec,
)
from aec_bench.adapters.direct import (
    DirectAdapter,
    DirectClient,
    replay_direct_client_from_payload,
)
from aec_bench.adapters.direct_providers import (
    anthropic_direct_client_from_payload,
    azure_openai_chat_client_from_payload,
)
from aec_bench.adapters.rlm.providers import make_rlm_client
from aec_bench.adapters.tool_loop import (
    ToolExecutionResult,
    ToolLoopAdapter,
    ToolLoopClient,
    replay_tool_loop_client_from_payload,
)
from aec_bench.adapters.tools.registry import ToolExecutorRegistry
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.harness.execution_payload import (
    ExecutionBundle,
    read_execution_bundle,
    write_execution_result,
)


class ExecutionDriver(Protocol):
    def execute(self, bundle: ExecutionBundle) -> AdapterResult: ...


DirectClientFactory = Callable[[dict[str, Any]], DirectClient]
ToolLoopClientFactory = Callable[[dict[str, Any]], ToolLoopClient]


@dataclass(frozen=True)
class ExecutionClientRegistry:
    direct_client_factories: dict[str, DirectClientFactory] = field(
        default_factory=lambda: {
            "replay": replay_direct_client_from_payload,
            "anthropic_api": anthropic_direct_client_from_payload,
            "azure_openai_chat": azure_openai_chat_client_from_payload,
        }
    )
    tool_loop_client_factories: dict[str, ToolLoopClientFactory] = field(
        default_factory=lambda: {"replay": replay_tool_loop_client_from_payload}
    )

    def build_direct_client(self, spec: SerializedClientSpec) -> DirectClient:
        try:
            factory = self.direct_client_factories[spec.client_kind]
        except KeyError as exc:
            msg = f"no direct client factory registered for client kind: {spec.client_kind}"
            raise ValueError(msg) from exc
        return factory(spec.payload)

    def build_tool_loop_client(self, spec: SerializedClientSpec) -> ToolLoopClient:
        try:
            factory = self.tool_loop_client_factories[spec.client_kind]
        except KeyError as exc:
            msg = f"no tool-loop client factory registered for client kind: {spec.client_kind}"
            raise ValueError(msg) from exc
        return factory(spec.payload)


@dataclass(frozen=True)
class ExecutionDriverRegistry:
    drivers: dict[str, ExecutionDriver] = field(default_factory=dict)

    def resolve(self, adapter_kind: str) -> ExecutionDriver:
        try:
            return self.drivers[adapter_kind]
        except KeyError as exc:
            msg = f"no execution driver registered for adapter kind: {adapter_kind}"
            raise ValueError(msg) from exc


@dataclass(frozen=True)
class DirectExecutionDriver:
    client_registry: ExecutionClientRegistry

    def execute(self, bundle: ExecutionBundle) -> AdapterResult:
        adapter = DirectAdapter(
            adapter_name=bundle.execution.adapter_name,
            model_name=bundle.execution.resolved_model,
            client=self.client_registry.build_direct_client(_client_spec(bundle.execution.payload)),
        )
        return adapter.execute(_adapter_request(bundle))


@dataclass(frozen=True)
class ToolLoopExecutionDriver:
    workspace_dir: Path
    client_registry: ExecutionClientRegistry

    def execute(self, bundle: ExecutionBundle) -> AdapterResult:
        tools = [ToolSpec.model_validate(tool_payload) for tool_payload in bundle.request.tools]
        adapter = ToolLoopAdapter(
            adapter_name=bundle.execution.adapter_name,
            model_name=bundle.execution.resolved_model,
            client=self.client_registry.build_tool_loop_client(_client_spec(bundle.execution.payload)),
            tool_executor=TaskToolExecutor(
                registry=ToolExecutorRegistry(workspace_dir=self.workspace_dir),
                tools=tools,
            ),
        )
        return adapter.execute(_adapter_request(bundle, tools=tools))


@dataclass(frozen=True)
class RlmExecutionDriver:
    workspace_dir: Path

    def execute(self, bundle: ExecutionBundle) -> AdapterResult:
        from aec_bench.adapters.rlm.adapter import RlmAdapter
        from aec_bench.trajectory.writer import TrajectoryWriter

        model_name = bundle.execution.resolved_model
        client = make_rlm_client(model_name)
        compaction_client = make_rlm_client(model_name, cache=False)
        trajectory_writer = TrajectoryWriter(
            path=str(self.workspace_dir / "trajectory.jsonl"),
        )

        rlm_toml = self.workspace_dir / "rlm.toml"

        # Build advisor client if rlm.toml declares an [advisor] block
        advisor_client = None
        if rlm_toml.exists():
            from aec_bench.adapters.rlm.config import parse_rlm_config

            _rlm_cfg = parse_rlm_config(rlm_toml.read_text())
            if _rlm_cfg.advisor and _rlm_cfg.advisor.enabled:
                advisor_client = make_rlm_client(_rlm_cfg.advisor.model, cache=True)

        if rlm_toml.exists():
            from aec_bench.adapters.rlm.initialiser import build_rlm_adapter

            adapter = build_rlm_adapter(
                rlm_config_path=rlm_toml,
                client=client,
                adapter_name=bundle.execution.adapter_name,
                model_name=model_name,
                subcall_client=compaction_client,
                compaction_client=compaction_client,
                trajectory_writer=trajectory_writer,
                workspace_path=str(self.workspace_dir),
                advisor_client=advisor_client,
            )
        else:
            adapter = RlmAdapter(
                adapter_name=bundle.execution.adapter_name,
                model_name=model_name,
                client=client,
                compaction_client=compaction_client,
                trajectory_writer=trajectory_writer,
                scratchpad_path=str(self.workspace_dir / ".scratchpad.json"),
            )

        return adapter.execute(_adapter_request(bundle))


@dataclass(frozen=True)
class LambdaRlmExecutionDriver:
    workspace_dir: Path

    def execute(self, bundle: ExecutionBundle) -> AdapterResult:
        from aec_bench.adapters.lambda_rlm.initialiser import build_lambda_rlm_adapter
        from aec_bench.trajectory.writer import TrajectoryWriter

        model_name = bundle.execution.resolved_model
        client = make_rlm_client(model_name)
        trajectory_writer = TrajectoryWriter(
            path=str(self.workspace_dir / "trajectory.jsonl"),
        )

        # Config path search order: lambda-rlm.toml → rlm.toml → None
        lambda_toml = self.workspace_dir / "lambda-rlm.toml"
        rlm_toml = self.workspace_dir / "rlm.toml"
        if lambda_toml.exists():
            config_path: Path | None = lambda_toml
        elif rlm_toml.exists():
            config_path = rlm_toml
        else:
            config_path = None

        # Build advisor client if config declares an [advisor] block
        advisor_client = None
        if config_path and config_path.exists():
            from aec_bench.adapters.lambda_rlm.config import parse_lambda_rlm_config

            _lrlm_cfg = parse_lambda_rlm_config(config_path.read_text())
            if _lrlm_cfg.advisor and _lrlm_cfg.advisor.enabled:
                advisor_client = make_rlm_client(_lrlm_cfg.advisor.model, cache=True)

        adapter = build_lambda_rlm_adapter(
            config_path=config_path,
            client=client,
            adapter_name=bundle.execution.adapter_name,
            model_name=model_name,
            workspace=str(self.workspace_dir),
            trajectory_writer=trajectory_writer,
            advisor_client=advisor_client,
        )

        return adapter.execute(_adapter_request(bundle))


@dataclass(frozen=True)
class TaskToolExecutor:
    registry: ToolExecutorRegistry
    tools: list[ToolSpec]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        tool = self._tool_by_name(tool_name)
        executor = self.registry.resolve(tool)
        return executor.execute(arguments)

    def _tool_by_name(self, tool_name: str) -> ToolSpec:
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        raise ValueError(f"unsupported tool: {tool_name}")


def run_execution_bundle(
    *,
    bundle_path: Path,
    result_path: Path,
    registry: ExecutionDriverRegistry,
) -> Path:
    bundle = read_execution_bundle(bundle_path)
    driver = registry.resolve(bundle.execution.adapter_kind)
    result = driver.execute(bundle)
    return write_execution_result(path=result_path, result=result)


def default_execution_driver_registry(*, workspace_dir: Path) -> ExecutionDriverRegistry:
    client_registry = ExecutionClientRegistry()
    return ExecutionDriverRegistry(
        drivers={
            "direct": DirectExecutionDriver(client_registry=client_registry),
            "tool_loop": ToolLoopExecutionDriver(
                workspace_dir=workspace_dir,
                client_registry=client_registry,
            ),
            "rlm": RlmExecutionDriver(workspace_dir=workspace_dir),
            "lambda_rlm": LambdaRlmExecutionDriver(workspace_dir=workspace_dir),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    run_execution_bundle(
        bundle_path=Path(args.bundle),
        result_path=Path(args.result),
        registry=default_execution_driver_registry(workspace_dir=Path.cwd()),
    )
    return 0


def _adapter_request(
    bundle: ExecutionBundle,
    *,
    tools: list[ToolSpec] | None = None,
) -> AdapterRequest:
    resolved_tools = tools or [ToolSpec.model_validate(tool_payload) for tool_payload in bundle.request.tools]
    return AdapterRequest(
        instruction=bundle.request.instruction,
        system_prompt=bundle.request.system_prompt,
        tools=resolved_tools,
        configuration=bundle.request.configuration,
        output_path=bundle.request.output_path,
        output_format=bundle.request.output_format,
    )


def _client_spec(payload: dict[str, Any]) -> SerializedClientSpec:
    client_payload = cast(dict[str, Any], payload["client"])
    return SerializedClientSpec(
        client_kind=cast(str, client_payload["client_kind"]),
        payload=cast(dict[str, Any], client_payload.get("payload", {})),
    )


if __name__ == "__main__":
    raise SystemExit(main())
