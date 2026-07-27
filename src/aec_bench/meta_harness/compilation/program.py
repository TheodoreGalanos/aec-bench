# ABOUTME: Compiles execution programs against the exact content-pinned harness operation surface.
# ABOUTME: Preserves validation order, retry policy, recursion policy, and deterministic topology.

from aec_bench.contracts.execution_program import (
    ActionNode,
    CompiledExecutionProgram,
    ExecutionProgram,
    FanoutNode,
    StopNode,
    VerifyNode,
)
from aec_bench.contracts.harness_instance import (
    CompiledHarnessInstance,
    ProgramOperationRef,
    ProgramOperationScope,
    ProgramOperationSpec,
)
from aec_bench.meta_harness.kernel_catalogue import (
    KernelRuntimeRegistry,
    KernelRuntimeRegistryError,
    ProgramOperationRuntime,
)

from .diagnostics import CompilationOwner, _fail
from .operations import (
    _validate_operation_arguments,
    _validate_operation_retry_taxonomy,
)
from .profile import ProgramCompilationProfile


def compile_execution_program(
    program: ExecutionProgram,
    *,
    harness: CompiledHarnessInstance,
    registry: KernelRuntimeRegistry,
    compilation_scope: ProgramOperationScope = ProgramOperationScope.PUBLIC,
    profile: ProgramCompilationProfile = ProgramCompilationProfile.STANDARD,
) -> CompiledExecutionProgram:
    """Resolve px operation calls against the exact content-pinned Hx surface."""
    if profile is ProgramCompilationProfile.MONOLITHIC_INCUMBENT:
        _validate_monolithic_incumbent_profile(
            program=program,
            compilation_scope=compilation_scope,
        )
    _validate_program_references(
        program=program,
        harness=harness,
        registry=registry,
    )
    _validate_program_limits(program=program, harness=harness)
    _reject_unavailable_verifier_nodes(program)
    operation_refs = _resolve_operation_refs(
        program=program,
        harness=harness,
        registry=registry,
        compilation_scope=compilation_scope,
    )
    _validate_operation_nodes(
        program=program,
        harness=harness,
        registry=registry,
        profile=profile,
    )
    return CompiledExecutionProgram(
        program_id=program.program_id,
        version=program.version,
        harness_ref=harness.ref,
        source_program_sha256=program.content_sha256,
        surface_sha256=harness.program_surface.content_sha256,
        nodes=program.nodes,
        limits=program.limits,
        topological_order=_topological_order(program),
        operation_refs=operation_refs,
    )


def _validate_program_references(
    *,
    program: ExecutionProgram,
    harness: CompiledHarnessInstance,
    registry: KernelRuntimeRegistry,
) -> None:
    if harness.kernel_ref != registry.manifest.ref:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="kernel_reference_mismatch",
            message="compiled harness does not target the installed fixed kernel",
            subject_ids=(harness.instance_id,),
        )
    if program.harness_ref != harness.ref:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="harness_reference_mismatch",
            message="execution program does not target the supplied compiled harness",
            subject_ids=(program.program_id, harness.instance_id),
        )


def _validate_program_limits(
    *,
    program: ExecutionProgram,
    harness: CompiledHarnessInstance,
) -> None:
    if program.limits.max_parallelism > harness.budget.max_parallelism:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="parallelism_exceeds_harness_budget",
            message="execution program parallelism exceeds the compiled harness budget",
            subject_ids=(program.program_id,),
        )
    if program.limits.max_total_attempts > harness.budget.max_total_attempts:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="attempts_exceed_harness_budget",
            message="execution program attempts exceed the compiled harness budget",
            subject_ids=(program.program_id,),
        )


def _reject_unavailable_verifier_nodes(program: ExecutionProgram) -> None:
    verifier_nodes = tuple(node for node in program.nodes if isinstance(node, VerifyNode))
    if verifier_nodes:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="verifier_subject_operation_unavailable",
            message="the installed fixed kernel exposes no operation that verifies an upstream px subject",
            subject_ids=tuple(node.node_id for node in verifier_nodes),
        )


def _resolve_operation_refs(
    *,
    program: ExecutionProgram,
    harness: CompiledHarnessInstance,
    registry: KernelRuntimeRegistry,
    compilation_scope: ProgramOperationScope,
) -> tuple[ProgramOperationRef, ...]:
    operation_ids = sorted(
        {node.operation_id for node in program.nodes if isinstance(node, ActionNode | FanoutNode | VerifyNode)}
    )
    operation_refs: list[ProgramOperationRef] = []
    for operation_id in operation_ids:
        operation = harness.program_surface.operation(operation_id)
        if operation is None:
            _fail(
                owner=CompilationOwner.PROGRAM,
                code="operation_outside_harness_surface",
                message=f"program operation is not exported by Hx: {operation_id}",
                subject_ids=(operation_id, program.program_id),
            )
        _validate_operation_scope(
            operation=operation,
            operation_id=operation_id,
            program_id=program.program_id,
            compilation_scope=compilation_scope,
        )
        runtime = _resolve_operation_runtime(
            operation=operation,
            operation_id=operation_id,
            registry=registry,
        )
        _validate_operation_retry_taxonomy(
            operation=operation,
            runtime=runtime,
        )
        operation_refs.append(operation.ref)
    return tuple(operation_refs)


def _validate_operation_scope(
    *,
    operation: ProgramOperationSpec,
    operation_id: str,
    program_id: str,
    compilation_scope: ProgramOperationScope,
) -> None:
    if (
        operation.required_compilation_scope is not ProgramOperationScope.PUBLIC
        and operation.required_compilation_scope is not compilation_scope
    ):
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="proposal_session_scope_required",
            message=f"program operation is internal to governed proposal sessions: {operation_id}",
            subject_ids=(operation_id, program_id),
        )


def _resolve_operation_runtime(
    *,
    operation: ProgramOperationSpec,
    operation_id: str,
    registry: KernelRuntimeRegistry,
) -> ProgramOperationRuntime:
    try:
        primitive = registry.resolve(operation.capability_ref)
    except KernelRuntimeRegistryError as exc:
        _fail(
            owner=CompilationOwner.KERNEL,
            code="operation_capability_not_installed",
            message=str(exc),
            subject_ids=(operation_id,),
        )
    if not isinstance(primitive.runtime, ProgramOperationRuntime):
        _fail(
            owner=CompilationOwner.KERNEL,
            code="operation_runtime_invalid",
            message=f"operation has no trusted program runtime: {operation_id}",
            subject_ids=(operation_id,),
        )
    return primitive.runtime


def _validate_operation_nodes(
    *,
    program: ExecutionProgram,
    harness: CompiledHarnessInstance,
    registry: KernelRuntimeRegistry,
    profile: ProgramCompilationProfile,
) -> None:
    for candidate_node in program.nodes:
        if not isinstance(candidate_node, ActionNode | FanoutNode | VerifyNode):
            continue
        operation = harness.program_surface.operation(candidate_node.operation_id)
        assert operation is not None
        _validate_node_retry(candidate_node, operation=operation)
        _validate_node_recursion(
            candidate_node,
            operation=operation,
            harness=harness,
        )
        _validate_operation_arguments(
            candidate_node,
            operation=operation,
            profile=profile,
            registry=registry,
        )


def _validate_node_retry(
    node: ActionNode | FanoutNode | VerifyNode,
    *,
    operation: ProgramOperationSpec,
) -> None:
    if node.retry is not None and not operation.supports_retry:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="retry_not_supported",
            message=f"operation does not support retry: {node.operation_id}",
            subject_ids=(node.node_id,),
        )
    if node.retry is None:
        return
    unsafe_retry_codes = tuple(
        error_code for error_code in node.retry.retry_on if error_code not in operation.retry_safe_error_codes
    )
    if unsafe_retry_codes:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="retry_error_code_not_safe",
            message=(
                "program retry policy includes error codes outside the operation safe set: "
                + ", ".join(unsafe_retry_codes)
            ),
            subject_ids=(node.node_id, node.operation_id),
        )


def _validate_node_recursion(
    node: ActionNode | FanoutNode | VerifyNode,
    *,
    operation: ProgramOperationSpec,
    harness: CompiledHarnessInstance,
) -> None:
    if isinstance(node, ActionNode | FanoutNode) and node.recursion is not None:
        if not harness.recursion_policy.enabled or not operation.supports_recursion:
            _fail(
                owner=CompilationOwner.PROGRAM,
                code="recursion_not_supported",
                message=f"operation does not support recursion: {node.operation_id}",
                subject_ids=(node.node_id,),
            )


def _validate_monolithic_incumbent_profile(
    *,
    program: ExecutionProgram,
    compilation_scope: ProgramOperationScope,
) -> None:
    if compilation_scope is not ProgramOperationScope.PROPOSAL_SESSION_INTERNAL:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="monolithic_incumbent_scope_required",
            message="monolithic incumbent compilation is confined to governed task-resident sessions",
            subject_ids=(program.program_id,),
        )
    actions = tuple(node for node in program.nodes if isinstance(node, ActionNode | FanoutNode | VerifyNode))
    stops = tuple(node for node in program.nodes if isinstance(node, StopNode))
    valid = (
        len(program.nodes) == 2
        and len(actions) == 1
        and isinstance(actions[0], ActionNode)
        and actions[0].operation_id == "finalize_proposed_plan.v1"
        and not actions[0].depends_on
        and not actions[0].arguments
        and len(stops) == 1
        and stops[0].depends_on == (actions[0].node_id,)
        and stops[0].result is not None
        and stops[0].result.node_id == actions[0].node_id
        and stops[0].result.output_port == "result"
    )
    if not valid:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="monolithic_incumbent_shape_invalid",
            message="monolithic incumbent profile requires one argument-free final task action followed by one stop",
            subject_ids=(program.program_id,),
        )


def _topological_order(program: ExecutionProgram) -> tuple[str, ...]:
    remaining = {node.node_id: set(node.depends_on) for node in program.nodes}
    order: list[str] = []
    while remaining:
        ready = sorted(node_id for node_id, dependencies in remaining.items() if not dependencies)
        assert ready
        order.extend(ready)
        for node_id in ready:
            del remaining[node_id]
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return tuple(order)
