# ABOUTME: Resolves proposal-session operations and bindings against the installed fixed kernel.
# ABOUTME: Fails closed when compiled H0 surfaces or implementation identities drift.

from __future__ import annotations

from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ToolBindingConfig,
)
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.harness.kernel_catalogue import (
    AgentAdapterRuntime,
    KernelOperationDefinition,
    KernelOperationHandlerKey,
    KernelRuntimeRegistry,
    KernelRuntimeRegistryError,
    ToolProviderRuntime,
    verify_kernel_implementation_identity,
)

from .contracts import ProposalSessionRuntimeError

_COMMIT_AGENT_CAPABILITY_ID = "aecbench.adapter.rlm-output-commit"


def _operation_definition_for_proposal_runtime(
    *,
    bundle: ProposalRunSessionBundle,
    registry: KernelRuntimeRegistry,
    operation_id: str,
) -> KernelOperationDefinition | None:
    """Resolve proposal-runtime dispatch from the exact compiled H0 operation."""

    operation = bundle.fixed_harness.program_surface.operation(operation_id)
    if operation is None:
        raise ProposalSessionRuntimeError(
            "operation_surface_mismatch",
            f"proposal operation is absent from the fixed H0 surface: {operation_id}",
        )
    definition = registry.operation_definition(operation_id)
    if definition is None:
        if registry.is_legacy_definition_free:
            return None
        raise ProposalSessionRuntimeError(
            "operation_definition_missing",
            "fixed-K proposal operation has no phase-neutral definition: " + operation_id,
        )
    try:
        primitive = registry.resolve(operation.capability_ref)
    except KernelRuntimeRegistryError as error:
        raise ProposalSessionRuntimeError(
            "kernel_capability_mismatch",
            f"proposal operation does not resolve against fixed K: {error}",
        ) from error
    if definition.capability.ref != operation.capability_ref or definition.primitive != primitive:
        raise ProposalSessionRuntimeError(
            "operation_definition_mismatch",
            "compiled proposal operation differs from its installed kernel definition: " + operation_id,
        )
    return definition


def _require_proposal_operation_handler(
    *,
    bundle: ProposalRunSessionBundle,
    registry: KernelRuntimeRegistry,
    operation_id: str,
    expected: KernelOperationHandlerKey,
) -> None:
    """Require one proposal operation to resolve to its exact graph-runtime handler."""

    definition = _operation_definition_for_proposal_runtime(
        bundle=bundle,
        registry=registry,
        operation_id=operation_id,
    )
    if definition is None:
        return
    if definition.handler_key is not expected:
        raise ProposalSessionRuntimeError(
            "operation_handler_mismatch",
            f"proposal operation {operation_id!r} has the wrong fixed-K handler",
        )


def _validate_kernel(
    *,
    bundle: ProposalRunSessionBundle,
    registry: KernelRuntimeRegistry,
) -> None:
    if (
        bundle.fixed_harness.kernel_ref != registry.manifest.ref
        or bundle.compilation.kernel_ref != registry.manifest.ref
    ):
        raise ProposalSessionRuntimeError(
            "kernel_identity_mismatch",
            "proposal session fixed H0 does not target the installed fixed K",
        )
    try:
        verify_kernel_implementation_identity(registry)
    except ValueError as error:
        raise ProposalSessionRuntimeError(
            "kernel_implementation_drift",
            f"proposal session fixed K implementation drifted: {error}",
        ) from error


def _resolve_agent_runtime(
    *,
    bundle: ProposalRunSessionBundle,
    registry: KernelRuntimeRegistry,
) -> tuple[AgentBindingConfig, AgentAdapterRuntime, tuple[str, ...]]:
    bindings = tuple(
        binding for binding in bundle.fixed_harness.bindings if isinstance(binding.configuration, AgentBindingConfig)
    )
    if len(bindings) != 1:
        raise ProposalSessionRuntimeError(
            "harness_binding_invalid",
            "proposal session requires exactly one fixed-H0 agent binding",
        )
    binding = bindings[0]
    configuration = binding.configuration
    if not isinstance(configuration, AgentBindingConfig):
        raise ProposalSessionRuntimeError(
            "harness_binding_invalid",
            "proposal agent binding has the wrong configuration type",
        )
    try:
        primitive = registry.resolve(binding.capability_ref)
    except ValueError as error:
        raise ProposalSessionRuntimeError(
            "kernel_capability_mismatch",
            f"proposal agent capability does not resolve against fixed K: {error}",
        ) from error
    if (
        binding.capability_ref.capability_id != _COMMIT_AGENT_CAPABILITY_ID
        or not isinstance(primitive.runtime, AgentAdapterRuntime)
        or primitive.runtime.adapter_kind != "rlm"
        or primitive.runtime.completion_policy != "task_output_commit"
    ):
        raise ProposalSessionRuntimeError(
            "harness_completion_boundary_unsupported",
            "proposal execution requires the fixed rlm-output-commit harness",
        )
    session_operation = bundle.fixed_harness.program_surface.resolve_operation(
        bundle.session_operation_ref,
    )
    if session_operation is None:
        raise ProposalSessionRuntimeError(
            "harness_operation_mismatch",
            "proposal session operation no longer resolves on fixed H0",
        )
    return (
        configuration,
        primitive.runtime,
        tuple(sorted(session_operation.binding_ids)),
    )


def _validate_tool_surface(
    *,
    bundle: ProposalRunSessionBundle,
    registry: KernelRuntimeRegistry,
) -> None:
    tool_bindings = tuple(
        binding for binding in bundle.fixed_harness.bindings if isinstance(binding.configuration, ToolBindingConfig)
    )
    if len(tool_bindings) > 1:
        raise ProposalSessionRuntimeError(
            "harness_binding_invalid",
            "proposal session supports at most one fixed-H0 tool binding",
        )
    if not tool_bindings:
        return
    try:
        primitive = registry.resolve(tool_bindings[0].capability_ref)
    except ValueError as error:
        raise ProposalSessionRuntimeError(
            "kernel_capability_mismatch",
            f"proposal tool capability does not resolve against fixed K: {error}",
        ) from error
    if not isinstance(primitive.runtime, ToolProviderRuntime):
        raise ProposalSessionRuntimeError(
            "kernel_capability_mismatch",
            "proposal tool binding resolves to the wrong fixed-K primitive",
        )
    raise ProposalSessionRuntimeError(
        "harness_tool_boundary_unsupported",
        "the initial rlm-output-commit proposal runtime does not expose task tool bindings",
    )
