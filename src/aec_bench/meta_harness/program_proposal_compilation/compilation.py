# ABOUTME: Orchestrates exact governed proposal compilation without invoking a runtime.
# ABOUTME: Seals successful session bundles or typed zero-dispatch candidate rejections.

from pathlib import Path

from aec_bench.contracts.execution_program import CompiledExecutionProgram, ExecutionProgram
from aec_bench.contracts.harness_instance import (
    CompiledHarnessInstance,
    HarnessBudget,
    ProgramOperationScope,
)
from aec_bench.contracts.program_proposal import (
    OptimizationSplit,
    ProgramCandidateRef,
    ProposalFreeze,
)
from aec_bench.contracts.proposal_execution import (
    ExecutableCandidateGraph,
    MonolithicIncumbentProgram,
    ProposalCompilationRejection,
    ProposalCompilationSuccess,
    ProposalCompileDiagnostic,
    ProposalExecutionSemantics,
    ProposalSessionPlan,
    ScopedSourceMaterialization,
)
from aec_bench.contracts.proposal_execution_budget import CandidateBudgetPlan
from aec_bench.contracts.proposal_execution_context import ProposalSourceScopeManifest
from aec_bench.contracts.proposal_execution_profile import ProposalExecutionProfile
from aec_bench.contracts.proposal_execution_types import (
    ProposalCompilationStatus,
    ProposalCompileRejectionCode,
    ProposalDiagnosticVisibility,
)
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.meta_harness.authority_ledger import AuthorityLedger, AuthorityLedgerError
from aec_bench.meta_harness.compiler import (
    CompilationError,
    CompilationOwner,
    ProgramCompilationProfile,
    compile_execution_program,
)
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.meta_harness.proposal_freeze import (
    GovernedProposalFreezeError,
    GovernedProposalFreezeResult,
    assert_proposal_freeze_authority,
)
from aec_bench.meta_harness.proposal_freezing.validation import (
    ProposalFreezeLifecyclePolicy,
)

from .candidate import (
    _parse_candidate_graph,
    _resolve_exact_candidate_bytes,
    _validate_candidate_program,
)
from .constants import _SESSION_OPERATION_ID
from .contracts import ProposalRunSessionBundle
from .errors import ProposalCompilationHostError, _CandidateCompileError
from .lowering import (
    _build_budget_plan,
    _build_source_scope_manifest,
    _lower_candidate_program,
)
from .profile_validation import _validate_host_inputs


def compile_governed_proposal(
    *,
    compilation_id: str,
    bundle_id: str,
    session_plan_id: str,
    ledger: AuthorityLedger,
    governed_freeze: GovernedProposalFreezeResult,
    proposal_freeze: ProposalFreeze,
    candidate_ref: ProgramCandidateRef,
    candidate_artifact_root: Path,
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
    session_overhead_seconds: int = 0,
    lifecycle_policy: ProposalFreezeLifecyclePolicy | None = None,
) -> ProposalRunSessionBundle | ProposalCompilationRejection:
    """Compile one exact frozen proposal without importing or invoking any runtime."""
    task_snapshot_sha256 = _validate_host_inputs(
        governed_freeze=governed_freeze,
        proposal_freeze=proposal_freeze,
        candidate_ref=candidate_ref,
        registry=registry,
        fixed_harness=fixed_harness,
        execution_profile=execution_profile,
        task_snapshot=task_snapshot,
        source_materializations=source_materializations,
        output_contract_sha256=output_contract_sha256,
        aggregate_budget=aggregate_budget,
        proposal_grammar_sha256=proposal_grammar_sha256,
        lowering_policy_sha256=lowering_policy_sha256,
        allocation_policy_sha256=allocation_policy_sha256,
        session_overhead_seconds=session_overhead_seconds,
    )
    authority_event_sha256 = _replay_governed_freeze(
        ledger=ledger,
        governed_freeze=governed_freeze,
        proposal_freeze=proposal_freeze,
        execution_profile=execution_profile,
        lifecycle_policy=lifecycle_policy,
    )
    candidate_bytes = _resolve_exact_candidate_bytes(
        ledger=ledger,
        governed_freeze=governed_freeze,
        candidate_ref=candidate_ref,
        candidate_artifact_root=candidate_artifact_root,
    )

    try:
        graph = _parse_candidate_graph(
            candidate_ref=candidate_ref,
            candidate_bytes=candidate_bytes,
        )
        _validate_candidate_program(
            graph=graph,
            candidate_ref=candidate_ref,
            proposal_freeze=proposal_freeze,
            proposal_grammar_sha256=proposal_grammar_sha256,
            output_contract_sha256=output_contract_sha256,
            execution_profile=execution_profile,
        )
        source_scope_manifest = _build_source_scope_manifest(
            graph=graph,
            proposal_freeze=proposal_freeze,
            task_snapshot=task_snapshot,
            source_materializations=source_materializations,
        )
        budget_plan = _build_budget_plan(
            graph=graph,
            proposal_freeze=proposal_freeze,
            fixed_harness=fixed_harness,
            aggregate_budget=aggregate_budget,
            execution_profile=execution_profile,
            allocation_policy_sha256=allocation_policy_sha256,
            session_overhead_seconds=session_overhead_seconds,
        )
        lowered_program = _lower_candidate_program(
            graph=graph,
            fixed_harness=fixed_harness,
            aggregate_budget=aggregate_budget,
            execution_profile=execution_profile,
        )
        compiled_program = _compile_lowered_candidate(
            graph=graph,
            lowered_program=lowered_program,
            fixed_harness=fixed_harness,
            registry=registry,
        )
    except _CandidateCompileError as error:
        return _rejection(
            compilation_id=compilation_id,
            candidate_ref=candidate_ref,
            proposal_freeze=proposal_freeze,
            authority_event_sha256=authority_event_sha256,
            registry=registry,
            fixed_harness=fixed_harness,
            execution_profile=execution_profile,
            lowering_policy_sha256=lowering_policy_sha256,
            task_snapshot_sha256=task_snapshot_sha256,
            error=error,
        )
    return _seal_proposal_session_bundle(
        compilation_id=compilation_id,
        bundle_id=bundle_id,
        session_plan_id=session_plan_id,
        graph=graph,
        candidate_ref=candidate_ref,
        proposal_freeze=proposal_freeze,
        authority_event_sha256=authority_event_sha256,
        registry=registry,
        fixed_harness=fixed_harness,
        execution_profile=execution_profile,
        task_snapshot=task_snapshot,
        lowering_policy_sha256=lowering_policy_sha256,
        task_snapshot_sha256=task_snapshot_sha256,
        source_scope_manifest=source_scope_manifest,
        budget_plan=budget_plan,
        lowered_program=lowered_program,
        compiled_program=compiled_program,
    )


def _replay_governed_freeze(
    *,
    ledger: AuthorityLedger,
    governed_freeze: GovernedProposalFreezeResult,
    proposal_freeze: ProposalFreeze,
    execution_profile: ProposalExecutionProfile,
    lifecycle_policy: ProposalFreezeLifecyclePolicy | None,
) -> str:
    try:
        stored_event = assert_proposal_freeze_authority(
            ledger=ledger,
            result=governed_freeze,
            freeze=proposal_freeze,
            lifecycle_policy=lifecycle_policy,
        )
    except (AuthorityLedgerError, GovernedProposalFreezeError, ValueError) as error:
        raise ProposalCompilationHostError(
            f"proposal freeze authority failed immediately before candidate resolution: {error}"
        ) from error
    profile_basis = governed_freeze.basis.execution_profile
    assert profile_basis is not None
    try:
        stored_profile = ledger.resolve_basis(profile_basis)
        frozen_execution_profile = ProposalExecutionProfile.model_validate_json(
            stored_profile.content_path.read_bytes()
        )
    except (AuthorityLedgerError, OSError, ValueError) as error:
        raise ProposalCompilationHostError(f"exact frozen execution profile cannot be resolved: {error}") from error
    if frozen_execution_profile != execution_profile:
        raise ProposalCompilationHostError("execution profile differs from the exact replayed freeze basis")
    return stored_event.event.content_sha256


def _compile_lowered_candidate(
    *,
    graph: ExecutableCandidateGraph,
    lowered_program: ExecutionProgram,
    fixed_harness: CompiledHarnessInstance,
    registry: KernelRuntimeRegistry,
) -> CompiledExecutionProgram:
    try:
        return compile_execution_program(
            lowered_program,
            harness=fixed_harness,
            registry=registry,
            compilation_scope=ProgramOperationScope.PROPOSAL_SESSION_INTERNAL,
            profile=(
                ProgramCompilationProfile.MONOLITHIC_INCUMBENT
                if isinstance(graph, MonolithicIncumbentProgram)
                else ProgramCompilationProfile.STANDARD
            ),
        )
    except CompilationError as error:
        if error.diagnostic.owner is CompilationOwner.PROGRAM:
            raise _CandidateCompileError(
                ProposalCompileRejectionCode.GRAMMAR_INVALID,
                error.diagnostic.message,
                subject_ids=error.diagnostic.subject_ids,
            ) from error
        raise ProposalCompilationHostError(
            f"profile-bound K/H failed while compiling a validated proposal: {error}"
        ) from error


def _seal_proposal_session_bundle(
    *,
    compilation_id: str,
    bundle_id: str,
    session_plan_id: str,
    graph: ExecutableCandidateGraph,
    candidate_ref: ProgramCandidateRef,
    proposal_freeze: ProposalFreeze,
    authority_event_sha256: str,
    registry: KernelRuntimeRegistry,
    fixed_harness: CompiledHarnessInstance,
    execution_profile: ProposalExecutionProfile,
    task_snapshot: TaskSnapshotRef,
    lowering_policy_sha256: str,
    task_snapshot_sha256: str,
    source_scope_manifest: ProposalSourceScopeManifest,
    budget_plan: CandidateBudgetPlan,
    lowered_program: ExecutionProgram,
    compiled_program: CompiledExecutionProgram,
) -> ProposalRunSessionBundle:
    try:
        compilation = ProposalCompilationSuccess(
            compilation_id=compilation_id,
            status=ProposalCompilationStatus.COMPILED,
            candidate_ref=candidate_ref,
            raw_proposal_artifact_sha256=candidate_ref.candidate_artifact_sha256,
            proposal_graph=graph,
            proposal_freeze=proposal_freeze,
            freeze_authority_event_sha256=authority_event_sha256,
            kernel_sha256=registry.manifest.content_sha256,
            fixed_harness_ref=fixed_harness.ref,
            surface_sha256=fixed_harness.program_surface.content_sha256,
            lowering_policy_sha256=lowering_policy_sha256,
            task_snapshot_sha256=task_snapshot_sha256,
            execution_profile=execution_profile,
            source_scope_manifest=source_scope_manifest,
            budget_plan=budget_plan,
            lowered_program=lowered_program,
            compiled_program=compiled_program,
        )
        session_plan = ProposalSessionPlan(
            session_plan_id=session_plan_id,
            compilation=compilation,
            planned_node_ids=graph.node_ids,
            topological_order=graph.topological_order,
        )
        session_operation = fixed_harness.program_surface.operation(_SESSION_OPERATION_ID)
        assert session_operation is not None
        return ProposalRunSessionBundle(
            bundle_id=bundle_id,
            compilation=compilation,
            session_plan=session_plan,
            fixed_harness=fixed_harness,
            task_snapshot=task_snapshot,
            session_operation_ref=session_operation.ref,
            execution_semantics=ProposalExecutionSemantics(execution_profile.scheduling.semantics.value),
        )
    except ValueError as error:
        raise ProposalCompilationHostError(f"validated proposal compilation could not be sealed: {error}") from error


def _rejection(
    *,
    compilation_id: str,
    candidate_ref: ProgramCandidateRef,
    proposal_freeze: ProposalFreeze,
    authority_event_sha256: str,
    registry: KernelRuntimeRegistry,
    fixed_harness: CompiledHarnessInstance,
    execution_profile: ProposalExecutionProfile,
    lowering_policy_sha256: str,
    task_snapshot_sha256: str,
    error: _CandidateCompileError,
) -> ProposalCompilationRejection:
    visibility = (
        ProposalDiagnosticVisibility.TRAINING_VISIBLE
        if proposal_freeze.split is OptimizationSplit.TRAINING
        else ProposalDiagnosticVisibility.HOST_ONLY
    )
    try:
        return ProposalCompilationRejection(
            compilation_id=compilation_id,
            status=ProposalCompilationStatus.REJECTED,
            candidate_ref=candidate_ref,
            raw_proposal_artifact_sha256=candidate_ref.candidate_artifact_sha256,
            proposal_freeze=proposal_freeze,
            freeze_authority_event_sha256=authority_event_sha256,
            kernel_sha256=registry.manifest.content_sha256,
            fixed_harness_ref=fixed_harness.ref,
            surface_sha256=fixed_harness.program_surface.content_sha256,
            lowering_policy_sha256=lowering_policy_sha256,
            task_snapshot_sha256=task_snapshot_sha256,
            execution_profile=execution_profile,
            diagnostic=ProposalCompileDiagnostic(
                owner="candidate",
                code=error.code,
                subject_ids=error.subject_ids,
                message=str(error),
                feedback_visibility=visibility,
            ),
            trial_record_permitted=False,
            run_bundle_permitted=False,
        )
    except ValueError as sealing_error:
        raise ProposalCompilationHostError(
            f"typed candidate rejection could not be sealed: {sealing_error}"
        ) from sealing_error
