# ABOUTME: Validates host inputs, frozen authority bindings, and the profiled K/H surface.
# ABOUTME: Keeps host-owned integrity failures separate from candidate grammar rejections.

from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessInstance,
    ComputeBindingConfig,
    ContextBindingConfig,
    HarnessBudget,
    ToolBindingConfig,
)
from aec_bench.contracts.harness_kernel import canonical_json_sha256, validate_sha256
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.proposal_execution_context import ScopedSourceMaterialization
from aec_bench.contracts.proposal_execution_profile import ProposalExecutionProfile
from aec_bench.contracts.task_snapshot import TaskSnapshotRef, task_snapshot_commitment
from aec_bench.experimentation.proposals.freezing import GovernedProposalFreezeResult
from aec_bench.harness.kernel_catalogue import (
    AgentAdapterRuntime,
    HarborBackendRuntime,
    KernelRuntimeRegistry,
    KernelRuntimeRegistryError,
)

from .constants import _PROPOSAL_OPERATION_IDS
from .errors import ProposalCompilationHostError


def _validate_host_inputs(
    *,
    governed_freeze: GovernedProposalFreezeResult,
    proposal_freeze: ProposalFreeze,
    candidate_ref: ProgramCandidateRef,
    registry: KernelRuntimeRegistry,
    fixed_harness: CompiledHarnessInstance,
    execution_profile: ProposalExecutionProfile,
    task_snapshot: TaskSnapshotRef,
    source_materializations: tuple[ScopedSourceMaterialization, ...],
    output_contract_sha256: str,
    aggregate_budget: HarnessBudget,
    proposal_grammar_sha256: str,
    lowering_policy_sha256: str,
    allocation_policy_sha256: str,
    session_overhead_seconds: int,
) -> str:
    _validate_host_policy_digests(
        output_contract_sha256=output_contract_sha256,
        proposal_grammar_sha256=proposal_grammar_sha256,
        lowering_policy_sha256=lowering_policy_sha256,
        allocation_policy_sha256=allocation_policy_sha256,
    )
    if session_overhead_seconds < 0:
        raise ProposalCompilationHostError("proposal session overhead must be non-negative")
    _validate_governed_freeze_binding(
        governed_freeze=governed_freeze,
        proposal_freeze=proposal_freeze,
        execution_profile=execution_profile,
    )
    _validate_frozen_candidate_membership(
        proposal_freeze=proposal_freeze,
        candidate_ref=candidate_ref,
    )
    _validate_kernel_harness_and_budget(
        registry=registry,
        fixed_harness=fixed_harness,
        proposal_freeze=proposal_freeze,
        execution_profile=execution_profile,
        aggregate_budget=aggregate_budget,
    )
    task_snapshot_sha256 = _validate_output_contract_and_task(
        proposal_freeze=proposal_freeze,
        task_snapshot=task_snapshot,
        output_contract_sha256=output_contract_sha256,
    )
    _validate_source_materializations(
        source_materializations=source_materializations,
        proposal_freeze=proposal_freeze,
    )
    _validate_execution_profile_surface(
        registry=registry,
        fixed_harness=fixed_harness,
        proposal_freeze=proposal_freeze,
        execution_profile=execution_profile,
    )
    return task_snapshot_sha256


def _validate_host_policy_digests(
    *,
    output_contract_sha256: str,
    proposal_grammar_sha256: str,
    lowering_policy_sha256: str,
    allocation_policy_sha256: str,
) -> None:
    try:
        validate_sha256(output_contract_sha256)
        validate_sha256(proposal_grammar_sha256)
        validate_sha256(lowering_policy_sha256)
        validate_sha256(allocation_policy_sha256)
    except ValueError as error:
        raise ProposalCompilationHostError(
            f"proposal compilation host policy carries an invalid digest: {error}"
        ) from error


def _validate_governed_freeze_binding(
    *,
    governed_freeze: GovernedProposalFreezeResult,
    proposal_freeze: ProposalFreeze,
    execution_profile: ProposalExecutionProfile,
) -> None:
    if governed_freeze.freeze != proposal_freeze:
        raise ProposalCompilationHostError("supplied ProposalFreeze differs from its governed authority context")
    if proposal_freeze.execution_profile_sha256 is None:
        raise ProposalCompilationHostError("proposal freeze does not bind an execution profile and is not executable")
    if proposal_freeze.execution_profile_sha256 != execution_profile.content_sha256:
        raise ProposalCompilationHostError("execution profile differs from the exact governed ProposalFreeze")
    profile_basis = governed_freeze.basis.execution_profile
    if profile_basis is None or profile_basis.artifact_id != (
        f"proposal-freeze.{proposal_freeze.freeze_id}.execution-profile.{proposal_freeze.execution_profile_sha256}"
    ):
        raise ProposalCompilationHostError("governed ProposalFreeze basis omits its exact execution profile")


def _validate_frozen_candidate_membership(
    *,
    proposal_freeze: ProposalFreeze,
    candidate_ref: ProgramCandidateRef,
) -> None:
    frozen_candidate = (
        proposal_freeze.incumbent_candidate
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT
        else next(
            (
                candidate
                for candidate in proposal_freeze.realized_candidates
                if candidate.candidate_id == candidate_ref.candidate_id
            ),
            None,
        )
    )
    if frozen_candidate != candidate_ref:
        raise ProposalCompilationHostError("candidate reference is outside the exact governed ProposalFreeze")


def _validate_kernel_harness_and_budget(
    *,
    registry: KernelRuntimeRegistry,
    fixed_harness: CompiledHarnessInstance,
    proposal_freeze: ProposalFreeze,
    execution_profile: ProposalExecutionProfile,
    aggregate_budget: HarnessBudget,
) -> None:
    if (
        registry.manifest.kernel_id != execution_profile.required_kernel_id
        or registry.manifest.version != execution_profile.required_kernel_version
    ):
        raise ProposalCompilationHostError(
            "proposal execution profile requires kernel "
            f"{execution_profile.required_kernel_id}@"
            f"{execution_profile.required_kernel_version}"
        )
    if fixed_harness.kernel_ref != registry.manifest.ref:
        raise ProposalCompilationHostError("fixed harness does not target the exact profiled kernel manifest")
    if fixed_harness.ref != proposal_freeze.fixed_harness_ref:
        raise ProposalCompilationHostError("fixed harness differs from the exact governed ProposalFreeze")
    if proposal_freeze.problem_view.fixed_harness.kernel_ref != registry.manifest.ref:
        raise ProposalCompilationHostError("problem view does not bind the exact profiled kernel manifest")
    if (
        aggregate_budget != fixed_harness.budget
        or aggregate_budget != proposal_freeze.problem_view.fixed_harness.aggregate_budget
    ):
        raise ProposalCompilationHostError("aggregate budget differs from the governed fixed harness")


def _validate_output_contract_and_task(
    *,
    proposal_freeze: ProposalFreeze,
    task_snapshot: TaskSnapshotRef,
    output_contract_sha256: str,
) -> str:
    expected_output_contract_sha256 = canonical_json_sha256(
        proposal_freeze.problem_view.output_contract.model_dump(mode="json")
    )
    if output_contract_sha256 != expected_output_contract_sha256:
        raise ProposalCompilationHostError("host output-contract identity differs from the governed problem view")
    task_snapshot_sha256 = task_snapshot_commitment(task_snapshot)
    problem_view = proposal_freeze.problem_view
    if task_snapshot.task_id != problem_view.task_id or task_snapshot.commitment_sha256 != problem_view.task_revision:
        raise ProposalCompilationHostError("task snapshot differs from the exact governed problem view")
    return task_snapshot_sha256


def _validate_source_materializations(
    *,
    source_materializations: tuple[ScopedSourceMaterialization, ...],
    proposal_freeze: ProposalFreeze,
) -> None:
    expected = {
        source.source_id: (source.source_sha256, source.byte_size)
        for source in proposal_freeze.problem_view.public_sources
    }
    actual = {source.source_id: (source.source_sha256, source.byte_size) for source in source_materializations}
    if actual != expected or len(actual) != len(source_materializations):
        raise ProposalCompilationHostError("public-source materializations differ from the governed allowlist")


def _validate_execution_profile_surface(
    *,
    registry: KernelRuntimeRegistry,
    fixed_harness: CompiledHarnessInstance,
    proposal_freeze: ProposalFreeze,
    execution_profile: ProposalExecutionProfile,
) -> None:
    if set(execution_profile.required_operation_ids) != set(_PROPOSAL_OPERATION_IDS):
        raise ProposalCompilationHostError(
            "proposal execution profile does not define the exact compiler operation roles"
        )
    projected = set(proposal_freeze.problem_view.fixed_harness.capability_ids)
    missing_projection = sorted(set(execution_profile.required_operation_ids) - projected)
    if missing_projection:
        raise ProposalCompilationHostError(
            "governed harness projection omits profiled operations: " + ", ".join(missing_projection)
        )
    for constraint in execution_profile.operation_constraints:
        operation = fixed_harness.program_surface.operation(constraint.operation_id)
        definition = registry.operation_definition(constraint.operation_id)
        if definition is None or definition.content_sha256 != constraint.operation_definition_sha256:
            raise ProposalCompilationHostError(
                "proposal execution profile operation definition differs from "
                f"the installed kernel: {constraint.operation_id}"
            )
        try:
            primitive = registry.resolve(constraint.capability_ref)
        except KernelRuntimeRegistryError as error:
            raise ProposalCompilationHostError(
                f"proposal execution profile capability cannot be resolved for {constraint.operation_id}: {error}"
            ) from error
        if (
            operation is None
            or definition.capability.ref != constraint.capability_ref
            or primitive.spec.ref != constraint.capability_ref
            or operation.capability_ref != constraint.capability_ref
            or operation.max_parallelism != constraint.max_parallelism
            or operation.supports_retry is not constraint.supports_retry
            or operation.retry_safe_error_codes != constraint.retry_safe_error_codes
            or operation.supports_recursion is not constraint.supports_recursion
            or operation.required_compilation_scope is not constraint.required_scope
        ):
            raise ProposalCompilationHostError(
                f"fixed harness operation surface differs from its execution profile: {constraint.operation_id}"
            )
    _validate_profiled_harness_bindings(
        registry=registry,
        fixed_harness=fixed_harness,
        execution_profile=execution_profile,
    )


def _validate_profiled_harness_bindings(
    *,
    registry: KernelRuntimeRegistry,
    fixed_harness: CompiledHarnessInstance,
    execution_profile: ProposalExecutionProfile,
) -> None:
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
    topology = execution_profile.harness_topology
    if (
        len(agent_bindings) != topology.required_agent_binding_count
        or len(context_bindings) > topology.max_context_binding_count
        or len(tool_bindings) > topology.max_tool_binding_count
    ):
        raise ProposalCompilationHostError("fixed harness binding cardinality differs from its execution profile")
    try:
        agent_runtimes = tuple(registry.resolve(binding.capability_ref).runtime for binding in agent_bindings)
        backend_runtimes = tuple(registry.resolve(binding.capability_ref).runtime for binding in compute_bindings)
    except KernelRuntimeRegistryError as error:
        raise ProposalCompilationHostError(f"profiled harness binding cannot be resolved: {error}") from error
    surface = execution_profile.execution_surface
    if any(
        not isinstance(runtime, AgentAdapterRuntime)
        or runtime.adapter_kind != surface.adapter_kind
        or runtime.completion_policy != surface.completion_policy
        for runtime in agent_runtimes
    ):
        raise ProposalCompilationHostError("fixed harness agent surface differs from its execution profile")
    backends = {runtime.backend for runtime in backend_runtimes if isinstance(runtime, HarborBackendRuntime)}
    if len(backends) != len(backend_runtimes) or not backends or not backends <= set(surface.allowed_backends):
        raise ProposalCompilationHostError("fixed harness backend surface differs from its execution profile")
    tool_ids = {
        tool_id
        for binding in tool_bindings
        if isinstance(
            configuration := binding.configuration,
            ToolBindingConfig,
        )
        for tool_id in configuration.tool_ids
    }
    if not tool_ids <= set(surface.allowed_tool_ids):
        raise ProposalCompilationHostError("fixed harness tool surface differs from its execution profile")
    if execution_profile.scheduling.max_parallelism > fixed_harness.budget.max_parallelism or any(
        configuration.max_concurrency < execution_profile.scheduling.max_parallelism
        for binding in compute_bindings
        if isinstance(
            configuration := binding.configuration,
            ComputeBindingConfig,
        )
    ):
        raise ProposalCompilationHostError("fixed harness cannot realize the execution profile parallelism")
    if fixed_harness.recursion_policy.enabled and not execution_profile.lowering.allow_recursion:
        raise ProposalCompilationHostError("fixed harness recursion exceeds the execution profile")
