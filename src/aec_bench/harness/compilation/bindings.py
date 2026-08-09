# ABOUTME: Validates compiled harness bindings against the executable fixed-kernel data path.
# ABOUTME: Owns binding cardinality, runtime compatibility, topology, and contract enforcement.

from aec_bench.contracts.harness_instance import (
    CompiledHarnessBinding,
    ContextBindingConfig,
    ContextSelectionStrategy,
    HarnessBindingConfiguration,
    HarnessContractSpec,
    HarnessTopologyRole,
    ToolAccessMode,
    ToolBindingConfig,
)
from aec_bench.harness.contract_enforcement import (
    HarnessContractError,
    validate_harness_contracts,
)
from aec_bench.harness.kernel_catalogue import (
    AgentAdapterRuntime,
    KernelRuntimeRegistry,
)

from .diagnostics import CompilationOwner, _fail


def _validate_execution_bearing_harness(
    *,
    bindings: tuple[CompiledHarnessBinding, ...],
    contracts: tuple[HarnessContractSpec, ...],
    registry: KernelRuntimeRegistry,
    task_binding: CompiledHarnessBinding,
    agent_binding: CompiledHarnessBinding,
    compute_binding: CompiledHarnessBinding,
    verification_bindings: tuple[CompiledHarnessBinding, ...],
    import_binding: CompiledHarnessBinding,
) -> None:
    contexts = tuple(binding for binding in bindings if isinstance(binding.configuration, ContextBindingConfig))
    tools = tuple(binding for binding in bindings if isinstance(binding.configuration, ToolBindingConfig))
    _validate_optional_binding_cardinality(contexts=contexts, tools=tools)
    _validate_context_modes(contexts)
    _validate_tool_modes(tools)
    _validate_agent_runtime(
        registry=registry,
        agent_binding=agent_binding,
        contexts=contexts,
        tools=tools,
    )
    expected_dependencies = _expected_binding_dependencies(
        task_binding=task_binding,
        agent_binding=agent_binding,
        compute_binding=compute_binding,
        contexts=contexts,
        tools=tools,
        verification_bindings=verification_bindings,
        import_binding=import_binding,
    )
    _validate_binding_topology(
        bindings=bindings,
        expected_dependencies=expected_dependencies,
    )
    _validate_binding_contracts(
        contracts=contracts,
        bindings=bindings,
    )


def _validate_optional_binding_cardinality(
    *,
    contexts: tuple[CompiledHarnessBinding, ...],
    tools: tuple[CompiledHarnessBinding, ...],
) -> None:
    if len(contexts) > 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="context_binding_cardinality",
            message="fixed kernel supports at most one context binding",
            subject_ids=tuple(binding.binding_id for binding in contexts),
        )
    if len(tools) > 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="tool_binding_cardinality",
            message="fixed kernel supports at most one task-tool binding",
            subject_ids=tuple(binding.binding_id for binding in tools),
        )


def _validate_context_modes(
    contexts: tuple[CompiledHarnessBinding, ...],
) -> None:
    for context in contexts:
        configuration = context.configuration
        assert isinstance(configuration, ContextBindingConfig)
        if configuration.selection_strategy is not ContextSelectionStrategy.FIXED:
            _fail(
                owner=CompilationOwner.HARNESS,
                code="context_selection_strategy_unsupported",
                message="fixed kernel currently implements only fixed context selection",
                subject_ids=(context.binding_id, configuration.selection_strategy.value),
            )


def _validate_tool_modes(
    tools: tuple[CompiledHarnessBinding, ...],
) -> None:
    for tool in tools:
        configuration = tool.configuration
        assert isinstance(configuration, ToolBindingConfig)
        if configuration.access_mode is not ToolAccessMode.EXECUTE:
            _fail(
                owner=CompilationOwner.HARNESS,
                code="tool_access_mode_unsupported",
                message="fixed kernel currently maps only execute task-tool access",
                subject_ids=(tool.binding_id, configuration.access_mode.value),
            )


def _validate_agent_runtime(
    *,
    registry: KernelRuntimeRegistry,
    agent_binding: CompiledHarnessBinding,
    contexts: tuple[CompiledHarnessBinding, ...],
    tools: tuple[CompiledHarnessBinding, ...],
) -> None:
    agent_primitive = registry.resolve(agent_binding.capability_ref)
    agent_runtime = agent_primitive.runtime
    if not isinstance(agent_runtime, AgentAdapterRuntime):
        _fail(
            owner=CompilationOwner.RUNTIME,
            code="agent_runtime_invalid",
            message="agent binding does not resolve to a trusted adapter runtime",
            subject_ids=(agent_binding.binding_id,),
        )
    if tools and agent_runtime.adapter_kind != "tool_loop":
        _fail(
            owner=CompilationOwner.HARNESS,
            code="adapter_task_tools_unsupported",
            message=f"adapter {agent_runtime.adapter_kind!r} cannot enforce task-tool controls",
            subject_ids=(agent_binding.binding_id, tools[0].binding_id),
        )
    if contexts and agent_runtime.adapter_kind not in {"direct", "tool_loop", "rlm"}:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="adapter_context_unsupported",
            message=(
                f"adapter {agent_runtime.adapter_kind!r} does not consume only the exact "
                "compiled workspace-system-prompt context"
            ),
            subject_ids=(agent_binding.binding_id, contexts[0].binding_id),
        )
    if agent_binding.topology_role is not HarnessTopologyRole.ORCHESTRATOR:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="single_agent_role_unsupported",
            message="the installed fixed kernel supports one orchestrator agent and no worker routing",
            subject_ids=(agent_binding.binding_id, agent_binding.topology_role.value),
        )


def _expected_binding_dependencies(
    *,
    task_binding: CompiledHarnessBinding,
    agent_binding: CompiledHarnessBinding,
    compute_binding: CompiledHarnessBinding,
    contexts: tuple[CompiledHarnessBinding, ...],
    tools: tuple[CompiledHarnessBinding, ...],
    verification_bindings: tuple[CompiledHarnessBinding, ...],
    import_binding: CompiledHarnessBinding,
) -> dict[str, set[str]]:
    expected_dependencies: dict[str, set[str]] = {
        task_binding.binding_id: set(),
        **{binding.binding_id: {task_binding.binding_id} for binding in (*contexts, *tools)},
        agent_binding.binding_id: {
            task_binding.binding_id,
            *(binding.binding_id for binding in contexts),
            *(binding.binding_id for binding in tools),
        },
        compute_binding.binding_id: {agent_binding.binding_id},
    }
    for verifier in verification_bindings:
        expected_dependencies[verifier.binding_id] = {compute_binding.binding_id}
    expected_dependencies[import_binding.binding_id] = (
        {verification_bindings[0].binding_id} if verification_bindings else {compute_binding.binding_id}
    )
    return expected_dependencies


def _validate_binding_topology(
    *,
    bindings: tuple[CompiledHarnessBinding, ...],
    expected_dependencies: dict[str, set[str]],
) -> None:
    invalid_topology = tuple(
        sorted(
            binding.binding_id
            for binding in bindings
            if set(binding.depends_on) != expected_dependencies[binding.binding_id]
        )
    )
    if invalid_topology:
        _fail(
            owner=CompilationOwner.HARNESS,
            code="unsupported_binding_topology",
            message="harness dependency edges do not match an executable fixed-K data path",
            subject_ids=invalid_topology,
        )


def _validate_binding_contracts(
    *,
    contracts: tuple[HarnessContractSpec, ...],
    bindings: tuple[CompiledHarnessBinding, ...],
) -> None:
    try:
        validate_harness_contracts(contracts=contracts, bindings=bindings)
    except HarnessContractError as error:
        _fail(
            owner=CompilationOwner.HARNESS,
            code=error.code,
            message=str(error),
            subject_ids=error.subject_ids,
        )


def _single_configuration[ConfigurationT: HarnessBindingConfiguration](
    bindings: tuple[CompiledHarnessBinding, ...] | list[CompiledHarnessBinding],
    configuration_type: type[ConfigurationT],
    *,
    role: str,
) -> tuple[CompiledHarnessBinding, ConfigurationT]:
    matches = _configurations(bindings, configuration_type)
    if len(matches) != 1:
        _fail(
            owner=CompilationOwner.HARNESS,
            code=f"{role.replace(' ', '_')}_binding_cardinality",
            message=f"compiled Harbor harness requires exactly one {role} binding; found {len(matches)}",
            subject_ids=tuple(sorted(binding.binding_id for binding, _ in matches)),
        )
    return matches[0]


def _configurations[ConfigurationT: HarnessBindingConfiguration](
    bindings: tuple[CompiledHarnessBinding, ...] | list[CompiledHarnessBinding],
    configuration_type: type[ConfigurationT],
) -> list[tuple[CompiledHarnessBinding, ConfigurationT]]:
    matches: list[tuple[CompiledHarnessBinding, ConfigurationT]] = []
    for binding in bindings:
        configuration = binding.configuration
        if isinstance(configuration, configuration_type):
            matches.append((binding, configuration))
    return matches
