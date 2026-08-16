# ABOUTME: Backend-side adapter execution entrypoint for sandboxed aec-bench runs.
# ABOUTME: Dispatches serialized bundles to direct, tool-loop, RLM, lambda-RLM, and DeepSeek drivers.

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field, replace
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
    AnthropicDirectClient,
    AzureOpenAIChatDirectClient,
    BedrockDirectClient,
    TogetherChatDirectClient,
    anthropic_direct_client_from_payload,
    azure_openai_chat_client_from_payload,
    together_chat_client_from_payload,
)
from aec_bench.adapters.local_registry import detect_direct_provider
from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.adapters.rlm.providers import make_rlm_client
from aec_bench.adapters.runtime_limits import validate_runtime_limit_contract
from aec_bench.adapters.tool_loop import (
    ToolExecutionResult,
    ToolLoopAdapter,
    ToolLoopClient,
    replay_tool_loop_client_from_payload,
)
from aec_bench.adapters.tools.registry import ToolExecutorRegistry
from aec_bench.contracts.provider_broker import ProviderBrokerCallPlane
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext
from aec_bench.harness.execution_payload import (
    ExecutionBundle,
    build_runtime_execution_attestation,
    read_execution_bundle,
    write_execution_result,
)
from aec_bench.harness.provider_broker import BrokeredRlmClient
from aec_bench.trajectory.writer import TrajectoryWriter


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
            "together_chat": together_chat_client_from_payload,
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
        if _payload_has_client(bundle.execution.payload):
            client = self.client_registry.build_direct_client(_client_spec(bundle.execution.payload))
        else:
            client = _default_direct_client_for_model(bundle.execution.resolved_model)
        adapter = DirectAdapter(
            adapter_name=bundle.execution.adapter_name,
            model_name=bundle.execution.resolved_model,
            client=client,
        )
        return adapter.execute(_adapter_request(bundle))


@dataclass(frozen=True)
class ToolLoopExecutionDriver:
    workspace_dir: Path
    client_registry: ExecutionClientRegistry

    def execute(self, bundle: ExecutionBundle) -> AdapterResult:
        tools = [ToolSpec.model_validate(tool_payload) for tool_payload in bundle.request.tools]
        if _payload_has_client(bundle.execution.payload):
            client = self.client_registry.build_tool_loop_client(_client_spec(bundle.execution.payload))
        else:
            client = _default_tool_loop_client_for_model(
                bundle.execution.resolved_model,
                self.workspace_dir,
                tools=tools,
            )
        adapter = ToolLoopAdapter(
            adapter_name=bundle.execution.adapter_name,
            model_name=bundle.execution.resolved_model,
            client=client,
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

        trajectory_writer = _build_trajectory_writer(
            workspace_dir=self.workspace_dir,
            configuration=bundle.request.configuration,
        )
        model_name = bundle.execution.resolved_model
        prompt_cache = _prompt_cache_enabled(bundle.request.configuration)
        broker_client = BrokeredRlmClient.from_environment()
        client: RlmClient
        compaction_client: RlmClient
        if broker_client is None:
            client = make_rlm_client(
                model_name,
                cache=prompt_cache,
            )
            compaction_client = make_rlm_client(model_name, cache=False)
        else:
            client = broker_client
            compaction_client = broker_client.for_call_plane(
                ProviderBrokerCallPlane.AUXILIARY,
            )

        rlm_toml = self.workspace_dir / "rlm.toml"

        # Build advisor client if rlm.toml declares an [advisor] block
        advisor_client: RlmClient | None = None
        if rlm_toml.exists():
            from aec_bench.adapters.rlm.config import parse_rlm_config

            _rlm_cfg = parse_rlm_config(rlm_toml.read_text())
            if _rlm_cfg.advisor and _rlm_cfg.advisor.enabled:
                if broker_client is not None:
                    if _rlm_cfg.advisor.model != model_name:
                        raise ValueError(
                            "provider broker does not authorize a distinct advisor model",
                        )
                    advisor_client = compaction_client
                else:
                    advisor_client = make_rlm_client(
                        _rlm_cfg.advisor.model,
                        cache=prompt_cache,
                    )

        try:
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
                    external_system_prompt=bundle.request.system_prompt,
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
                    external_system_prompt=bundle.request.system_prompt or "",
                    workspace_path=str(self.workspace_dir),
                )

            result = adapter.execute(_adapter_request(bundle))
        except BaseException:
            if broker_client is not None:
                broker_client.finalize()
            raise
        if broker_client is None:
            return result
        receipt = broker_client.finalize()
        return replace(
            result,
            configuration_record={
                **result.configuration_record,
                "provider_broker": {
                    "policy_sha256": receipt.policy_sha256,
                    "receipt": receipt.model_dump(mode="json"),
                },
            },
        )


@dataclass(frozen=True)
class LambdaRlmExecutionDriver:
    workspace_dir: Path

    def execute(self, bundle: ExecutionBundle) -> AdapterResult:
        from aec_bench.adapters.lambda_rlm.initialiser import build_lambda_rlm_adapter

        trajectory_writer = _build_trajectory_writer(
            workspace_dir=self.workspace_dir,
            configuration=bundle.request.configuration,
        )
        model_name = bundle.execution.resolved_model
        client = make_rlm_client(model_name)

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
    validate_runtime_limit_contract(
        adapter_kind=bundle.execution.adapter_kind,
        configuration=bundle.request.configuration,
    )
    driver = registry.resolve(bundle.execution.adapter_kind)
    result = driver.execute(bundle)
    _ensure_kernel_invocation_trajectory(bundle)
    _materialize_raw_output(bundle=bundle, result=result)
    return write_execution_result(
        path=result_path,
        result=result,
        runtime_attestation=build_runtime_execution_attestation(
            bundle=bundle,
            result=result,
        ),
    )


def default_execution_driver_registry(*, workspace_dir: Path) -> ExecutionDriverRegistry:
    client_registry = ExecutionClientRegistry()
    direct_driver = DirectExecutionDriver(client_registry=client_registry)
    tool_loop_driver = ToolLoopExecutionDriver(
        workspace_dir=workspace_dir,
        client_registry=client_registry,
    )
    lambda_rlm_driver = LambdaRlmExecutionDriver(workspace_dir=workspace_dir)
    drivers: dict[str, ExecutionDriver] = {
        "direct": direct_driver,
        "tool_loop": tool_loop_driver,
        "pydantic_ai": tool_loop_driver,
        "rlm": RlmExecutionDriver(workspace_dir=workspace_dir),
        "lambda-rlm": lambda_rlm_driver,
        "lambda_rlm": lambda_rlm_driver,
    }
    try:
        from aec_bench.harness.deepseek_harness_driver import DeepSeekHarnessExecutionDriver
    except ModuleNotFoundError as exc:
        if exc.name != "aec_bench.harness.deepseek_harness_driver":
            raise
    else:
        drivers["deepseek_harness"] = DeepSeekHarnessExecutionDriver(workspace_dir=workspace_dir)
    return ExecutionDriverRegistry(drivers=drivers)


def _materialize_raw_output(*, bundle: ExecutionBundle, result: AdapterResult) -> None:
    """Write raw adapter text to the requested output path when the adapter did not."""
    if not result.raw_output_text:
        return

    output_path = Path(bundle.request.output_path)
    if output_path.exists() and output_path.stat().st_size > 0:
        return
    if output_path.is_absolute() and output_path.parts[:2] == ("/", "workspace") and not output_path.parent.exists():
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.raw_output_text, encoding="utf-8")


def _ensure_kernel_invocation_trajectory(bundle: ExecutionBundle) -> None:
    """Guarantee one node-bound invocation event for adapters without native traces."""
    if bundle.execution.adapter_kind in {"rlm", "lambda-rlm", "lambda_rlm"}:
        return
    if "meta_harness_context" not in bundle.request.configuration:
        return
    workspace_dir = Path(bundle.request.output_path).parent
    trajectory_path = workspace_dir / "trajectory.jsonl"
    if trajectory_path.is_file() and trajectory_path.stat().st_size > 0:
        return
    workspace_dir.mkdir(parents=True, exist_ok=True)
    writer = _build_trajectory_writer(
        workspace_dir=workspace_dir,
        configuration=bundle.request.configuration,
    )
    writer.new_step(call_type="main")
    writer.thinking(f"Kernel invocation completed through {bundle.execution.adapter_kind}.")
    writer.close()


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


def _prompt_cache_enabled(configuration: dict[str, Any]) -> bool:
    value = configuration.get("prompt_cache", True)
    if not isinstance(value, bool):
        raise ValueError("prompt_cache must be a boolean")
    return value


def _build_trajectory_writer(
    *,
    workspace_dir: Path,
    configuration: dict[str, Any],
) -> TrajectoryWriter:
    context: MetaHarnessTrajectoryContext | None = None
    if "meta_harness_context" in configuration:
        context = MetaHarnessTrajectoryContext.model_validate(configuration["meta_harness_context"])

    writer = TrajectoryWriter(path=str(workspace_dir / "trajectory.jsonl"))
    if context is not None:
        writer.set_meta_harness_context(context.model_dump(mode="json"))
    return writer


def _client_spec(payload: dict[str, Any]) -> SerializedClientSpec:
    client_payload = cast(dict[str, Any], payload["client"])
    return SerializedClientSpec(
        client_kind=cast(str, client_payload["client_kind"]),
        payload=cast(dict[str, Any], client_payload.get("payload", {})),
    )


def _payload_has_client(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("client"), dict)


def _default_direct_client_for_model(model_name: str) -> DirectClient:
    provider = detect_direct_provider(model_name)
    if provider == "azure":
        return AzureOpenAIChatDirectClient()
    if provider == "bedrock":
        return BedrockDirectClient()
    if provider == "together":
        return TogetherChatDirectClient()
    return AnthropicDirectClient()


def _default_tool_loop_client_for_model(
    model_name: str,
    workspace_dir: Path,
    *,
    tools: list[ToolSpec],
) -> ToolLoopClient:
    from aec_bench.adapters.tool_loop_local import PydanticAiToolLoopClient

    unsupported = sorted(tool.name for tool in tools if tool.name != "bash")
    if unsupported:
        raise ValueError(
            "default tool-loop runtime has no kernel-owned native implementation for: " + ", ".join(unsupported)
        )
    return PydanticAiToolLoopClient(
        model_name,
        workspace=str(workspace_dir),
        enable_bash=any(tool.name == "bash" for tool in tools),
    )


if __name__ == "__main__":
    raise SystemExit(main())
