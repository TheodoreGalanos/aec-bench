# ABOUTME: Builds the current execution profile for governed proposal compilation.
# ABOUTME: Binds sequential proposal policy to the installed kernel and fixed harness.

from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessInstance,
    ComputeBindingConfig,
    ContextBindingConfig,
    ToolBindingConfig,
)
from aec_bench.contracts.proposal_execution_profile import (
    ProposalEnvironmentPolicy,
    ProposalExecutionProfile,
    ProposalExecutionSurfacePolicy,
    ProposalHarnessTopologyPolicy,
    ProposalLoweringPolicy,
    ProposalOperationConstraint,
    ProposalSchedulingPolicy,
    ProposalSchedulingSemantics,
)
from aec_bench.meta_harness.kernel_catalogue import (
    AgentAdapterRuntime,
    HarborBackendRuntime,
    KernelRuntimeRegistry,
    KernelRuntimeRegistryError,
)

from .constants import _PROPOSAL_OPERATION_IDS
from .errors import ProposalCompilationHostError


def proposal_execution_profile(
    *,
    registry: KernelRuntimeRegistry,
    fixed_harness: CompiledHarnessInstance,
    provider_broker_required: bool,
) -> ProposalExecutionProfile:
    """Build the current sequential proposal execution policy."""

    operation_constraints: list[ProposalOperationConstraint] = []
    for operation_id in _PROPOSAL_OPERATION_IDS:
        definition = registry.operation_definition(operation_id)
        operation = fixed_harness.program_surface.operation(operation_id)
        if definition is None or operation is None:
            raise ProposalCompilationHostError("proposal execution profile requires every proposal operation")
        operation_constraints.append(
            ProposalOperationConstraint(
                operation_id=operation_id,
                operation_definition_sha256=definition.content_sha256,
                capability_ref=operation.capability_ref,
                required_scope=operation.required_compilation_scope,
                max_parallelism=operation.max_parallelism,
                supports_retry=operation.supports_retry,
                retry_safe_error_codes=operation.retry_safe_error_codes,
                supports_recursion=operation.supports_recursion,
            )
        )

    agent_bindings = tuple(
        binding for binding in fixed_harness.bindings if isinstance(binding.configuration, AgentBindingConfig)
    )
    context_bindings = tuple(
        binding for binding in fixed_harness.bindings if isinstance(binding.configuration, ContextBindingConfig)
    )
    tool_bindings = tuple(
        binding for binding in fixed_harness.bindings if isinstance(binding.configuration, ToolBindingConfig)
    )
    compute_bindings = tuple(
        binding for binding in fixed_harness.bindings if isinstance(binding.configuration, ComputeBindingConfig)
    )
    if len(agent_bindings) != 1 or not compute_bindings:
        raise ProposalCompilationHostError(
            "proposal execution profile requires one agent and at least one execution backend"
        )
    try:
        agent_runtime = registry.resolve(agent_bindings[0].capability_ref).runtime
        backend_runtimes = tuple(registry.resolve(binding.capability_ref).runtime for binding in compute_bindings)
    except KernelRuntimeRegistryError as error:
        raise ProposalCompilationHostError(
            f"proposal execution profile cannot resolve the fixed harness: {error}"
        ) from error
    if not isinstance(agent_runtime, AgentAdapterRuntime) or any(
        not isinstance(runtime, HarborBackendRuntime) for runtime in backend_runtimes
    ):
        raise ProposalCompilationHostError(
            "proposal execution profile requires typed agent and Harbor backend runtimes"
        )
    backends = tuple(
        sorted({runtime.backend for runtime in backend_runtimes if isinstance(runtime, HarborBackendRuntime)})
    )
    tool_ids = tuple(
        sorted(
            {
                tool_id
                for binding in tool_bindings
                if isinstance(
                    configuration := binding.configuration,
                    ToolBindingConfig,
                )
                for tool_id in configuration.tool_ids
            }
        )
    )
    return ProposalExecutionProfile(
        profile_id="aecbench.proposal-execution",
        version="1.0.0",
        required_kernel_id=registry.manifest.kernel_id,
        required_kernel_version=registry.manifest.version,
        operation_constraints=tuple(operation_constraints),
        harness_topology=ProposalHarnessTopologyPolicy(
            required_agent_binding_count=1,
            max_context_binding_count=len(context_bindings),
            max_tool_binding_count=len(tool_bindings),
        ),
        execution_surface=ProposalExecutionSurfacePolicy(
            adapter_kind=agent_runtime.adapter_kind,
            completion_policy=agent_runtime.completion_policy,
            allowed_tool_ids=tool_ids,
            allowed_backends=backends,
            provider_broker_required=provider_broker_required,
        ),
        lowering=ProposalLoweringPolicy(
            max_semantic_subtasks=4,
            max_fan_in=2,
            max_fan_out=2,
            allow_retry=False,
            allow_recursion=False,
        ),
        scheduling=ProposalSchedulingPolicy(
            semantics=ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW,
            max_parallelism=1,
            environment_policy=(ProposalEnvironmentPolicy.ROTATED_SINGLE_ENVIRONMENT),
            deterministic_commit_order=True,
        ),
    )
