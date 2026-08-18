# ABOUTME: Replays governed proposal authority into prepared evaluation execution batches.
# ABOUTME: Enforces exact verifier, compilation, assignment, and just-in-time gate joins.

from __future__ import annotations

from aec_bench.contracts.evaluation_generation.batch import EvaluationBatchPlan
from aec_bench.contracts.evaluation_plane import (
    EvaluationAssignment,
    EvaluationRegime,
    TaskVerifierSurfaceScope,
    task_verifier_surface_commitment,
)
from aec_bench.evaluation.regime import validate_evaluation_regime_ref
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.proposals.evaluation_execution_preflight import (
    AuthorizedDispatchRef,
    CompilationBatchClosure,
    EvaluationExecutionPreflightError,
    ExecutionGate,
    MonitorReadiness,
    PreparedExecutionBatch,
    ProposalBatchClosure,
    ScheduleClosure,
)
from aec_bench.experimentation.proposals.evaluation_execution_preflight.lifecycle import (
    _normalize_batch,
    _normalize_compilation_closure,
    _normalize_monitor_closure,
    _normalize_proposal_closure,
    _normalize_schedule_closure,
)
from aec_bench.experimentation.proposals.proposal_dispatch import (
    GovernedProposalDispatchAuthorization,
    ProposalDispatchGovernanceError,
    replay_governed_proposal_dispatch,
)
from aec_bench.experimentation.proposals.task_package import (
    assert_proposal_task_verifier_scope,
    project_proposal_task_verifier_surface,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    ProposalTaskPackageError,
)
from aec_bench.harness.evaluation_dispatch_authorization import (
    EvaluationGenerationAuthorizationCode,
    EvaluationGenerationAuthorizationError,
    replay_evaluation_dispatch_gate,
    replay_evaluation_dispatches,
    require_evaluation_dispatch_authorization_count,
    verify_evaluation_dispatch_assignment_order,
)


def prepare_execution_batch(
    *,
    source_batch: EvaluationBatchPlan,
    proposal_closure: ProposalBatchClosure,
    schedule_closure: ScheduleClosure,
    compilation_closure: CompilationBatchClosure,
    monitor_closure: MonitorReadiness,
    evaluation_regime: EvaluationRegime,
    evaluation_assignment: EvaluationAssignment,
    task_verifier_scope: TaskVerifierSurfaceScope,
    ledger: AuthorityLedger,
    authorizations: tuple[GovernedProposalDispatchAuthorization, ...],
) -> PreparedExecutionBatch:
    """Close a complete batch barrier through generic authority replay."""

    batch = _normalize_batch(source_batch)
    proposals = _normalize_proposal_closure(
        batch=batch,
        closure=proposal_closure,
    )
    schedules = _normalize_schedule_closure(
        batch=batch,
        closure=schedule_closure,
    )
    compilations = _normalize_compilation_closure(
        batch=batch,
        schedules=schedules,
        closure=compilation_closure,
    )
    monitors = _normalize_monitor_closure(
        batch=batch,
        closure=monitor_closure,
    )
    if not compilations.dispatch_permitted:
        raise EvaluationExecutionPreflightError(
            "dispatch is forbidden because at least one compile rejection is closed",
        )
    _require_ready_authorization_count(
        batch=batch,
        authorizations=authorizations,
    )
    evaluation, assignment, verifier_scope = _normalize_evaluation_surface(
        evaluation_regime=evaluation_regime,
        evaluation_assignment=evaluation_assignment,
        task_verifier_scope=task_verifier_scope,
    )
    _verify_evaluation_surface(
        batch=batch,
        monitors=monitors,
        evaluation_regime=evaluation,
        evaluation_assignment=assignment,
        verifier_scope=verifier_scope,
    )
    replayed_dispatches = _replay_ready_authorizations(
        ledger=ledger,
        authorizations=authorizations,
    )
    try:
        assert_proposal_task_verifier_scope(
            manifests=tuple(authorization.dispatch.derived_task_manifest for authorization in authorizations),
            expected_scope=verifier_scope,
        )
    except ProposalTaskPackageError as error:
        raise EvaluationExecutionPreflightError(
            f"derived dispatch task verifier scope is invalid: {error}",
        ) from error
    _verify_ready_authorization_order(
        batch=batch,
        dispatches=replayed_dispatches,
    )
    _verify_dispatch_compilations(
        batch=batch,
        compilations=compilations,
        dispatches=replayed_dispatches,
    )
    return PreparedExecutionBatch(
        source_batch=batch,
        proposal_closure=proposals,
        schedule_closure=schedules,
        compilation_closure=compilations,
        monitor_closure=monitors,
        task_verifier_scope=verifier_scope,
        ordered_assignment_sha256s=batch.ordered_assignment_sha256s,
        dispatches=replayed_dispatches,
    )


def build_authorized_dispatch_ref(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
) -> AuthorizedDispatchRef:
    """Replay one governed authority chain into a dispatch reference."""

    try:
        replayed = replay_governed_proposal_dispatch(
            ledger=ledger,
            authorization=authorization,
        )
    except ProposalDispatchGovernanceError as error:
        raise EvaluationExecutionPreflightError(
            f"dispatch authority chain cannot be replayed: {error}",
        ) from error
    dispatch = replayed.dispatch
    provider_event = replayed.provider_dispatch_event
    verifier_surface = project_proposal_task_verifier_surface(
        dispatch.derived_task_manifest,
    )
    return AuthorizedDispatchRef(
        assignment_sha256=dispatch.execution_assignment_sha256,
        schedule_sha256=dispatch.execution_schedule_sha256,
        candidate=dispatch.candidate_ref,
        coordinate_sha256=dispatch.evaluation_coordinate.content_sha256,
        compilation_sha256=dispatch.compilation_sha256,
        bundle_sha256=dispatch.bundle_sha256,
        task_id=dispatch.task_id,
        task_revision=dispatch.task_revision,
        task_verifier_surface_sha256=task_verifier_surface_commitment(verifier_surface),
        dispatch_id=dispatch.dispatch_id,
        dispatch_sha256=dispatch.content_sha256,
        runtime_archive_sha256=dispatch.runtime_archive_sha256,
        runtime_archive_content_sha256=(dispatch.runtime_archive_content_sha256),
        provider_dispatch_authority_event_id=provider_event.event_id,
        provider_dispatch_authority_event_sha256=(provider_event.content_sha256),
        materialized=True,
        authorized=True,
    )


def open_execution_gate(
    *,
    prepared_batch: PreparedExecutionBatch,
    ledger: AuthorityLedger,
    authorizations: tuple[GovernedProposalDispatchAuthorization, ...],
) -> ExecutionGate:
    """Replay all batch authorities immediately before execution."""

    if not isinstance(prepared_batch, PreparedExecutionBatch):
        raise EvaluationExecutionPreflightError(
            "execution gate accepts only PreparedExecutionBatch",
        )
    try:
        selected = PreparedExecutionBatch.model_validate(
            prepared_batch.model_dump(mode="python"),
        )
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            f"prepared execution batch is invalid: {error}",
        ) from error
    dispatches = _replay_execution_gate_authorizations(
        ready=selected,
        ledger=ledger,
        authorizations=authorizations,
    )
    return ExecutionGate(
        prepared_batch_sha256=selected.content_sha256,
        dispatches=dispatches,
    )


def _normalize_evaluation_surface(
    *,
    evaluation_regime: EvaluationRegime,
    evaluation_assignment: EvaluationAssignment,
    task_verifier_scope: TaskVerifierSurfaceScope,
) -> tuple[EvaluationRegime, EvaluationAssignment, TaskVerifierSurfaceScope]:
    try:
        return (
            EvaluationRegime.model_validate(
                evaluation_regime.model_dump(mode="python"),
            ),
            EvaluationAssignment.model_validate(
                evaluation_assignment.model_dump(mode="python"),
            ),
            TaskVerifierSurfaceScope.model_validate(
                task_verifier_scope.model_dump(mode="python"),
            ),
        )
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            f"evaluation regime, assignment, or verifier surface is invalid: {error}",
        ) from error


def _verify_evaluation_surface(
    *,
    batch: EvaluationBatchPlan,
    monitors: MonitorReadiness,
    evaluation_regime: EvaluationRegime,
    evaluation_assignment: EvaluationAssignment,
    verifier_scope: TaskVerifierSurfaceScope,
) -> None:
    if evaluation_assignment.regime != batch.evaluation_regime_ref:
        raise EvaluationExecutionPreflightError(
            "evaluation regime identity differs from the source batch",
        )
    try:
        validate_evaluation_regime_ref(evaluation_regime, evaluation_assignment.regime)
    except ValueError as error:
        raise EvaluationExecutionPreflightError(str(error)) from error
    if evaluation_assignment.task_verifier_commitment != task_verifier_surface_commitment(verifier_scope):
        raise EvaluationExecutionPreflightError(
            "evaluation assignment task verifier differs from the expected scope",
        )
    monitoring = evaluation_regime.monitoring_policy
    if monitoring is None or monitoring.configuration.get("standing_policy") != monitors.policy.model_dump(mode="json"):
        raise EvaluationExecutionPreflightError(
            "evaluation regime monitoring policy differs from the closed monitor policy",
        )


def _verify_dispatch_compilations(
    *,
    batch: EvaluationBatchPlan,
    compilations: CompilationBatchClosure,
    dispatches: tuple[AuthorizedDispatchRef, ...],
) -> None:
    compilation_by_assignment = {result.assignment_sha256: result for result in compilations.results}
    for assignment_sha256, dispatch in zip(
        batch.ordered_assignment_sha256s,
        dispatches,
        strict=True,
    ):
        compilation = compilation_by_assignment[assignment_sha256]
        if dispatch.runtime_archive_sha256 != batch.runtime_archive_sha256:
            raise EvaluationExecutionPreflightError(
                f"dispatch {assignment_sha256} differs from the frozen runtime archive",
            )
        if (
            dispatch.schedule_sha256 != compilation.schedule_sha256
            or dispatch.candidate != compilation.candidate
            or dispatch.coordinate_sha256 != compilation.coordinate_sha256
            or dispatch.compilation_sha256 != compilation.compilation_sha256
            or dispatch.bundle_sha256 != compilation.bundle_sha256
        ):
            raise EvaluationExecutionPreflightError(
                f"dispatch {assignment_sha256} differs from its schedule, compilation, or bundle",
            )


def _replay_ready_authorizations(
    *,
    ledger: AuthorityLedger,
    authorizations: tuple[GovernedProposalDispatchAuthorization, ...],
) -> tuple[AuthorizedDispatchRef, ...]:
    return replay_evaluation_dispatches(
        authorizations=authorizations,
        replay=lambda authorization: build_authorized_dispatch_ref(
            ledger=ledger,
            authorization=authorization,
        ),
    )


def _require_ready_authorization_count(
    *,
    batch: EvaluationBatchPlan,
    authorizations: tuple[GovernedProposalDispatchAuthorization, ...],
) -> None:
    try:
        require_evaluation_dispatch_authorization_count(
            expected_assignment_sha256s=batch.ordered_assignment_sha256s,
            authorizations=authorizations,
        )
    except EvaluationGenerationAuthorizationError as error:
        raise EvaluationExecutionPreflightError(
            "dispatch authorization count differs from the batch assignments",
        ) from error


def _verify_ready_authorization_order(
    *,
    batch: EvaluationBatchPlan,
    dispatches: tuple[AuthorizedDispatchRef, ...],
) -> None:
    try:
        verify_evaluation_dispatch_assignment_order(
            expected_assignment_sha256s=batch.ordered_assignment_sha256s,
            dispatches=dispatches,
        )
    except EvaluationGenerationAuthorizationError as error:
        raise EvaluationExecutionPreflightError(
            "governed dispatch authorizations differ from the frozen assignment order",
        ) from error


def _replay_execution_gate_authorizations(
    *,
    ready: PreparedExecutionBatch,
    ledger: AuthorityLedger,
    authorizations: tuple[GovernedProposalDispatchAuthorization, ...],
) -> tuple[AuthorizedDispatchRef, ...]:
    try:
        return replay_evaluation_dispatch_gate(
            expected_dispatches=ready.dispatches,
            authorizations=authorizations,
            replay=lambda authorization: (
                build_authorized_dispatch_ref(
                    ledger=ledger,
                    authorization=authorization,
                )
            ),
        )
    except EvaluationGenerationAuthorizationError as error:
        if error.code is EvaluationGenerationAuthorizationCode.CARDINALITY:
            raise EvaluationExecutionPreflightError(
                "execution-gate authorization count differs from the prepared batch",
            ) from error
        raise EvaluationExecutionPreflightError(
            "just-in-time dispatch authority replay differs from the prepared batch",
        ) from error
