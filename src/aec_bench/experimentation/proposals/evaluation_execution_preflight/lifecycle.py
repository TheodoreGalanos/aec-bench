# ABOUTME: Defines proposal evaluation execution preflight contracts and lifecycle closure.
# ABOUTME: Closes proposal, schedule, compilation, monitor, and authority evidence before execution.

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.evaluation_generation.batch import EvaluationBatchPlan
from aec_bench.contracts.evaluation_plane import (
    EvaluationAssignment,
    EvaluationRegime,
    TaskVerifierSurfaceScope,
    task_verifier_surface_commitment,
)
from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.harness_instance import HarnessBudget, HarnessInstanceRef
from aec_bench.contracts.harness_kernel import (
    KernelRef,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.proposal_execution.compilation import ProposalCompilationRejection
from aec_bench.contracts.proposal_execution_types import ProposalCompilationStatus
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.evaluation.regime import validate_evaluation_regime_ref
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.governance.motif_assurance import MotifAssuranceSnapshot
from aec_bench.experimentation.governance.standing_monitors import (
    CycleMonitorPlan,
    StandingMonitorPolicy,
)
from aec_bench.experimentation.proposals.decomposition_optimization import (
    DecompositionExecutionSchedule,
)
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.experimentation.proposals.program_proposer import (
    ProgramProposalInvocation,
    ProgramProposalInvocationStatus,
)
from aec_bench.experimentation.proposals.proposal_dispatch import (
    GovernedProposalDispatchAuthorization,
)


class EvaluationExecutionPreflightError(ValueError):
    """Reject incomplete or identity-drifted execution preflight evidence."""


class ProposalInvocationRef(LegacyContentAddressedModel):
    """Content-pinned successful proposer invocation for one task plan."""

    schema_version: Literal["aecbench.proposal-invocation-ref.v1"] = "aecbench.proposal-invocation-ref.v1"
    task_plan_id: NonEmptyStr
    invocation_sha256: str
    policy_sha256: str
    problem_view_sha256: str
    candidate_manifest_sha256: str
    model_id: NonEmptyStr
    policy_checkpoint_sha256: str
    grammar_sha256: str
    candidates: tuple[ProgramCandidateRef, ...] = Field(min_length=1)
    completed: Literal[True] = True

    @field_validator(
        "invocation_sha256",
        "policy_sha256",
        "problem_view_sha256",
        "candidate_manifest_sha256",
        "policy_checkpoint_sha256",
        "grammar_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("candidates")
    @classmethod
    def validate_candidates(
        cls,
        value: tuple[ProgramCandidateRef, ...],
    ) -> tuple[ProgramCandidateRef, ...]:
        if any(candidate.kind is not ProgramCandidateKind.PROPOSAL for candidate in value):
            raise ValueError("proposer invocation reference may contain only proposal candidates")
        identities = tuple(candidate.content_sha256 for candidate in value)
        if len(identities) != len(set(identities)):
            raise ValueError("proposer invocation candidates must be unique")
        return tuple(sorted(value, key=lambda candidate: candidate.candidate_id))


class ProposalBatchClosure(LegacyContentAddressedModel):
    """Task-scoped proposer invocations closed before compilation."""

    schema_version: Literal["aecbench.proposal-batch-closure.v1"] = "aecbench.proposal-batch-closure.v1"
    source_batch_sha256: str
    invocations: tuple[ProposalInvocationRef, ...] = Field(min_length=1)
    proposals_closed: Literal[True] = True

    @field_validator("source_batch_sha256")
    @classmethod
    def validate_batch_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("invocations")
    @classmethod
    def validate_invocations(
        cls,
        value: tuple[ProposalInvocationRef, ...],
    ) -> tuple[ProposalInvocationRef, ...]:
        invocation_ids = tuple(invocation.invocation_sha256 for invocation in value)
        if len(invocation_ids) != len(set(invocation_ids)):
            raise ValueError("proposer invocation identities must be unique")
        return tuple(
            sorted(
                value,
                key=lambda invocation: (
                    invocation.task_plan_id,
                    invocation.invocation_sha256,
                ),
            )
        )


class VerifiedSchedule(LegacyContentAddressedModel):
    """Exact join between a plan schedule reference and its concrete schedule."""

    schema_version: Literal["aecbench.verified-evaluation-schedule.v1"] = "aecbench.verified-evaluation-schedule.v1"
    task_plan_id: NonEmptyStr
    schedule_ref_sha256: str
    schedule_sha256: str
    schedule: DecompositionExecutionSchedule
    ordered_assignment_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "schedule_ref_sha256",
        "schedule_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("ordered_assignment_sha256s")
    @classmethod
    def validate_assignment_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("verified schedule assignments must be unique")
        return value

    @model_validator(mode="after")
    def validate_schedule_identity(self) -> Self:
        if self.schedule_sha256 != self.schedule.content_sha256:
            raise ValueError("verified schedule identity differs from the concrete schedule")
        actual = tuple(assignment.content_sha256 for assignment in self.schedule.assignments)
        if self.ordered_assignment_sha256s != actual:
            raise ValueError("verified assignment order differs from the concrete schedule")
        return self


class ScheduleClosure(LegacyContentAddressedModel):
    """Concrete schedules verified against the frozen evaluation batch."""

    schema_version: Literal["aecbench.evaluation-schedule-closure.v1"] = "aecbench.evaluation-schedule-closure.v1"
    source_batch_sha256: str
    schedules: tuple[VerifiedSchedule, ...] = Field(min_length=1)
    schedules_closed: Literal[True] = True

    @field_validator("source_batch_sha256")
    @classmethod
    def validate_batch_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("schedules")
    @classmethod
    def validate_schedules(
        cls,
        value: tuple[VerifiedSchedule, ...],
    ) -> tuple[VerifiedSchedule, ...]:
        task_ids = tuple(schedule.task_plan_id for schedule in value)
        schedule_ids = tuple(schedule.schedule_sha256 for schedule in value)
        evaluation_task_ids = tuple(schedule.schedule.proposal_freeze.problem_view.task_id for schedule in value)
        if (
            len(task_ids) != len(set(task_ids))
            or len(schedule_ids) != len(set(schedule_ids))
            or len(evaluation_task_ids) != len(set(evaluation_task_ids))
        ):
            raise ValueError("verified schedules must be unique")
        return tuple(
            sorted(
                value,
                key=lambda schedule: (schedule.schedule.proposal_freeze.problem_view.task_id),
            )
        )


class CompilationResultRef(LegacyContentAddressedModel):
    """One assignment-scoped compile result retaining a typed rejection."""

    schema_version: Literal["aecbench.compilation-result-ref.v1"] = "aecbench.compilation-result-ref.v1"
    assignment_sha256: str
    schedule_sha256: str
    candidate: ProgramCandidateRef
    coordinate_sha256: str
    proposal_freeze_sha256: str
    kernel_ref: KernelRef
    fixed_harness_ref: HarnessInstanceRef
    evaluation_regime_ref: EvaluationRegimeRef
    aggregate_budget: HarnessBudget
    status: ProposalCompilationStatus
    compilation_sha256: str
    bundle_sha256: str | None = None
    typed_rejection: ProposalCompilationRejection | None = None

    @field_validator(
        "assignment_sha256",
        "schedule_sha256",
        "coordinate_sha256",
        "proposal_freeze_sha256",
        "compilation_sha256",
        "bundle_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @model_validator(mode="after")
    def validate_result_shape(self) -> Self:
        if self.status is ProposalCompilationStatus.COMPILED:
            if self.bundle_sha256 is None or self.typed_rejection is not None:
                raise ValueError(
                    "compiled result requires a bundle and no typed rejection",
                )
            return self
        if self.bundle_sha256 is not None or self.typed_rejection is None:
            raise ValueError(
                "rejected result requires a typed rejection and no bundle",
            )
        rejection = self.typed_rejection
        if (
            self.compilation_sha256 != rejection.content_sha256
            or self.candidate != rejection.candidate_ref
            or self.proposal_freeze_sha256 != rejection.proposal_freeze.content_sha256
            or self.kernel_ref != rejection.kernel_ref
            or self.fixed_harness_ref != rejection.fixed_harness_ref
            or self.evaluation_regime_ref != rejection.proposal_freeze.evaluation_regime_ref
            or self.aggregate_budget != rejection.proposal_freeze.problem_view.fixed_harness.aggregate_budget
        ):
            raise ValueError(
                "typed compile rejection differs from its assignment-scoped reference",
            )
        return self

    @classmethod
    def from_rejection(
        cls,
        *,
        assignment_sha256: str,
        schedule_sha256: str,
        coordinate_sha256: str,
        rejection: ProposalCompilationRejection,
    ) -> CompilationResultRef:
        """Retain one exact deterministic rejection without permitting a bundle."""

        selected = ProposalCompilationRejection.model_validate(
            rejection.model_dump(mode="python"),
        )
        freeze = selected.proposal_freeze
        return cls(
            assignment_sha256=assignment_sha256,
            schedule_sha256=schedule_sha256,
            candidate=selected.candidate_ref,
            coordinate_sha256=coordinate_sha256,
            proposal_freeze_sha256=freeze.content_sha256,
            kernel_ref=selected.kernel_ref,
            fixed_harness_ref=selected.fixed_harness_ref,
            evaluation_regime_ref=freeze.evaluation_regime_ref,
            aggregate_budget=freeze.problem_view.fixed_harness.aggregate_budget,
            status=ProposalCompilationStatus.REJECTED,
            compilation_sha256=selected.content_sha256,
            typed_rejection=selected,
        )

    @classmethod
    def from_bundle(
        cls,
        *,
        assignment_sha256: str,
        schedule_sha256: str,
        coordinate_sha256: str,
        bundle: ProposalRunSessionBundle,
    ) -> CompilationResultRef:
        """Derive one successful compile reference from its exact session bundle."""

        selected = ProposalRunSessionBundle.model_validate(
            bundle.model_dump(mode="python"),
        )
        compilation = selected.compilation
        freeze = compilation.proposal_freeze
        return cls(
            assignment_sha256=assignment_sha256,
            schedule_sha256=schedule_sha256,
            candidate=compilation.candidate_ref,
            coordinate_sha256=coordinate_sha256,
            proposal_freeze_sha256=freeze.content_sha256,
            kernel_ref=compilation.kernel_ref,
            fixed_harness_ref=compilation.fixed_harness_ref,
            evaluation_regime_ref=freeze.evaluation_regime_ref,
            aggregate_budget=compilation.budget_plan.aggregate_budget,
            status=ProposalCompilationStatus.COMPILED,
            compilation_sha256=compilation.content_sha256,
            bundle_sha256=selected.content_sha256,
        )


class CompilationBatchClosure(LegacyContentAddressedModel):
    """Compilation results with an explicit fail-closed dispatch flag."""

    schema_version: Literal["aecbench.compilation-batch-closure.v1"] = "aecbench.compilation-batch-closure.v1"
    source_batch_sha256: str
    schedule_closure_sha256: str
    ordered_assignment_sha256s: tuple[str, ...]
    results: tuple[CompilationResultRef, ...]
    rejected_assignment_sha256s: tuple[str, ...]
    dispatch_permitted: bool
    compilations_closed: Literal[True] = True

    @field_validator(
        "source_batch_sha256",
        "schedule_closure_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "ordered_assignment_sha256s",
        "rejected_assignment_sha256s",
    )
    @classmethod
    def validate_assignment_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("compilation closure assignment identities must be unique")
        return value

    @model_validator(mode="after")
    def validate_complete_results(self) -> Self:
        if not self.ordered_assignment_sha256s or len(self.results) != len(self.ordered_assignment_sha256s):
            raise ValueError(
                "compilation closure must cover every ordered assignment",
            )
        actual_order = tuple(result.assignment_sha256 for result in self.results)
        if actual_order != self.ordered_assignment_sha256s:
            raise ValueError("compilation results differ from the frozen assignment order")
        expected_rejections = tuple(
            result.assignment_sha256 for result in self.results if result.status is ProposalCompilationStatus.REJECTED
        )
        if self.rejected_assignment_sha256s != expected_rejections:
            raise ValueError("compile rejection identities differ from the typed results")
        if self.dispatch_permitted is not (not expected_rejections):
            raise ValueError("dispatch permission must fail closed on any compile rejection")
        return self


class MonitorReadiness(LegacyContentAddressedModel):
    """Exact standing monitor, cycle, evaluation, and assurance preflight."""

    schema_version: Literal["aecbench.monitor-readiness.v1"] = "aecbench.monitor-readiness.v1"
    source_batch_sha256: str
    evaluation_regime: EvaluationRegimeRef
    policy: StandingMonitorPolicy
    policy_sha256: str
    cycle_plan: CycleMonitorPlan
    cycle_plan_sha256: str
    assurance_snapshot: MotifAssuranceSnapshot
    assurance_snapshot_sha256: str
    monitors_closed: Literal[True] = True

    @field_validator(
        "source_batch_sha256",
        "policy_sha256",
        "cycle_plan_sha256",
        "assurance_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_monitor_identity(self) -> Self:
        if (
            self.policy_sha256 != self.policy.content_sha256
            or self.cycle_plan_sha256 != self.cycle_plan.content_sha256
            or self.assurance_snapshot_sha256 != self.assurance_snapshot.content_sha256
            or self.cycle_plan.evaluation_regime != self.evaluation_regime
            or self.cycle_plan.standing_policy_sha256 != self.policy_sha256
            or self.cycle_plan.assurance_snapshot_sha256 != self.assurance_snapshot_sha256
        ):
            raise ValueError("monitor closure identities do not form one exact surface")
        return self


class AuthorizedDispatchRef(LegacyContentAddressedModel):
    """Materialized and provider-authorized dispatch identity for one assignment."""

    schema_version: Literal["aecbench.authorized-dispatch-ref.v1"] = "aecbench.authorized-dispatch-ref.v1"
    assignment_sha256: str
    schedule_sha256: str
    candidate: ProgramCandidateRef
    coordinate_sha256: str
    compilation_sha256: str
    bundle_sha256: str
    task_id: NonEmptyStr
    task_revision: str
    task_verifier_surface_sha256: str
    dispatch_id: NonEmptyStr
    dispatch_sha256: str
    runtime_archive_sha256: str
    runtime_archive_content_sha256: str
    provider_dispatch_authority_event_id: NonEmptyStr
    provider_dispatch_authority_event_sha256: str
    materialized: Literal[True]
    authorized: Literal[True]

    @field_validator(
        "assignment_sha256",
        "schedule_sha256",
        "coordinate_sha256",
        "compilation_sha256",
        "bundle_sha256",
        "task_revision",
        "task_verifier_surface_sha256",
        "dispatch_sha256",
        "runtime_archive_sha256",
        "runtime_archive_content_sha256",
        "provider_dispatch_authority_event_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class PreparedExecutionBatch(LegacyContentAddressedModel):
    """Only complete preflight object from which batch execution may open."""

    schema_version: Literal["aecbench.prepared-execution-batch.v1"] = "aecbench.prepared-execution-batch.v1"
    source_batch: EvaluationBatchPlan
    proposal_closure: ProposalBatchClosure
    schedule_closure: ScheduleClosure
    compilation_closure: CompilationBatchClosure
    monitor_closure: MonitorReadiness
    task_verifier_scope: TaskVerifierSurfaceScope
    ordered_assignment_sha256s: tuple[str, ...]
    dispatches: tuple[AuthorizedDispatchRef, ...]
    execution_permitted: Literal[True] = True

    @model_validator(mode="after")
    def validate_complete_preflight(self) -> Self:
        batch_sha256 = self.source_batch.content_sha256
        if {
            self.proposal_closure.source_batch_sha256,
            self.schedule_closure.source_batch_sha256,
            self.compilation_closure.source_batch_sha256,
            self.monitor_closure.source_batch_sha256,
        } != {batch_sha256}:
            raise ValueError("prepared batch closures do not bind one source batch")
        if (
            self.ordered_assignment_sha256s != self.source_batch.ordered_assignment_sha256s
            or self.compilation_closure.ordered_assignment_sha256s != self.ordered_assignment_sha256s
            or tuple(dispatch.assignment_sha256 for dispatch in self.dispatches) != self.ordered_assignment_sha256s
        ):
            raise ValueError("prepared batch does not preserve the frozen assignment order")
        if not self.compilation_closure.dispatch_permitted:
            raise ValueError("prepared batch cannot contain a typed compile rejection")
        expected_task_identities = {
            (
                task_plan.cohort_task.task.task_id,
                task_plan.cohort_task.task.public_snapshot.commitment_sha256,
            )
            for task_plan in self.source_batch.task_plans
        }
        verifier_by_task = {
            (surface.task_id, surface.task_revision): task_verifier_surface_commitment(surface)
            for surface in self.task_verifier_scope.task_surfaces
        }
        if set(verifier_by_task) != expected_task_identities:
            raise ValueError(
                "prepared batch verifier scope differs from the frozen batch tasks",
            )
        compilation_by_assignment = {result.assignment_sha256: result for result in self.compilation_closure.results}
        for dispatch in self.dispatches:
            result = compilation_by_assignment[dispatch.assignment_sha256]
            if dispatch.runtime_archive_sha256 != self.source_batch.runtime_archive_sha256:
                raise ValueError("prepared batch dispatch differs from the frozen runtime archive")
            if (
                dispatch.schedule_sha256 != result.schedule_sha256
                or dispatch.candidate != result.candidate
                or dispatch.coordinate_sha256 != result.coordinate_sha256
                or dispatch.compilation_sha256 != result.compilation_sha256
                or dispatch.bundle_sha256 != result.bundle_sha256
            ):
                raise ValueError(
                    "prepared batch dispatch differs from its schedule, compilation, or bundle",
                )
            if (
                verifier_by_task.get((dispatch.task_id, dispatch.task_revision))
                != dispatch.task_verifier_surface_sha256
            ):
                raise ValueError(
                    "prepared batch dispatch differs from its task verifier scope",
                )
        return self


class ExecutionGate(LegacyContentAddressedModel):
    """Minimal public execution surface derivable only from a prepared batch."""

    schema_version: Literal["aecbench.execution-gate.v1"] = "aecbench.execution-gate.v1"
    prepared_batch_sha256: str
    dispatches: tuple[AuthorizedDispatchRef, ...] = Field(min_length=1)
    authority_replayed: Literal[True] = True
    execution_permitted: Literal[True] = True

    @field_validator("prepared_batch_sha256")
    @classmethod
    def validate_ready_hash(cls, value: str) -> str:
        return validate_sha256(value)


def close_proposal_batch(
    *,
    source_batch: EvaluationBatchPlan,
    invocations: tuple[ProgramProposalInvocation, ...],
) -> ProposalBatchClosure:
    """Close the required successful proposer invocations against one batch."""

    batch = _normalize_batch(source_batch)
    expected_count = batch.spec.task_count * batch.spec.proposer_invocations_per_task
    if len(invocations) != expected_count:
        raise EvaluationExecutionPreflightError(
            "proposer invocation count differs from the batch specification",
        )
    references: list[ProposalInvocationRef] = []
    seen_invocation_sha256s: set[str] = set()
    for task_plan in batch.task_plans:
        matches = tuple(
            invocation
            for invocation in invocations
            if invocation.candidate_manifest_sha256 == task_plan.candidate_manifest_sha256
        )
        if len(matches) != batch.spec.proposer_invocations_per_task:
            raise EvaluationExecutionPreflightError(
                f"task plan {task_plan.task_plan_id} proposer invocation count differs from the batch specification",
            )
        expected_candidates = tuple(
            sorted(
                (
                    assignment.candidate
                    for assignment in task_plan.schedule.assignments
                    if assignment.candidate.kind is ProgramCandidateKind.PROPOSAL
                ),
                key=lambda candidate: candidate.candidate_id,
            )
        )
        for invocation in matches:
            if invocation.status is not ProgramProposalInvocationStatus.COMPLETED:
                raise EvaluationExecutionPreflightError(
                    f"task plan {task_plan.task_plan_id} proposer invocation is not completed",
                )
            try:
                selected = ProgramProposalInvocation.model_validate(
                    invocation.model_dump(mode="python"),
                )
            except ValueError as error:
                raise EvaluationExecutionPreflightError(
                    f"task plan {task_plan.task_plan_id} proposer invocation is invalid: {error}",
                ) from error
            if selected.content_sha256 in seen_invocation_sha256s:
                raise EvaluationExecutionPreflightError("proposer invocation identities must be unique")
            seen_invocation_sha256s.add(selected.content_sha256)
            actual_candidates = tuple(artifact.reference for artifact in selected.artifacts)
            policy = batch.proposal_policy
            if (
                selected.policy_sha256 != batch.candidate_manifest_proposal_policy_sha256
                or selected.model_id != policy.model_id
                or selected.policy_checkpoint_sha256 != policy.policy_checkpoint_sha256
                or selected.grammar_sha256 != policy.grammar_sha256
                or selected.candidate_manifest_sha256 != task_plan.candidate_manifest_sha256
                or actual_candidates != expected_candidates
            ):
                raise EvaluationExecutionPreflightError(
                    f"task plan {task_plan.task_plan_id} proposer invocation differs from its frozen proposal set",
                )
            references.append(
                ProposalInvocationRef(
                    task_plan_id=task_plan.task_plan_id,
                    invocation_sha256=selected.content_sha256,
                    policy_sha256=selected.policy_sha256,
                    problem_view_sha256=selected.problem_view_sha256,
                    candidate_manifest_sha256=(selected.candidate_manifest_sha256),
                    model_id=selected.model_id,
                    policy_checkpoint_sha256=(selected.policy_checkpoint_sha256),
                    grammar_sha256=selected.grammar_sha256,
                    candidates=actual_candidates,
                )
            )
    return ProposalBatchClosure(
        source_batch_sha256=batch.content_sha256,
        invocations=tuple(references),
    )


def verify_schedules(
    *,
    source_batch: EvaluationBatchPlan,
    schedules: tuple[DecompositionExecutionSchedule, ...],
) -> ScheduleClosure:
    """Verify batch schedule references against their concrete schedules."""

    from aec_bench.experimentation.proposals.evaluation_execution_preflight.schedule import (
        verify_schedule,
    )

    batch = _normalize_batch(source_batch)
    if len(schedules) != len(batch.task_plans):
        raise EvaluationExecutionPreflightError(
            "concrete schedule count differs from the batch task plans",
        )
    verified: list[VerifiedSchedule] = []
    seen_schedule_sha256s: set[str] = set()
    for task_plan in batch.task_plans:
        matches = tuple(schedule for schedule in schedules if schedule.schedule_id == task_plan.schedule.schedule_id)
        if len(matches) != 1:
            raise EvaluationExecutionPreflightError(
                f"task plan {task_plan.task_plan_id} requires one concrete schedule identity",
            )
        raw_schedule = matches[0]
        if len(raw_schedule.assignments) != len(task_plan.schedule.assignments):
            raise EvaluationExecutionPreflightError(
                f"task plan {task_plan.task_plan_id} schedule assignment count differs from its reference",
            )
        try:
            schedule = DecompositionExecutionSchedule.model_validate(
                raw_schedule.model_dump(mode="python"),
            )
        except ValueError as error:
            raise EvaluationExecutionPreflightError(
                f"task plan {task_plan.task_plan_id} schedule identity is invalid: {error}",
            ) from error
        if schedule.content_sha256 in seen_schedule_sha256s:
            raise EvaluationExecutionPreflightError("concrete schedule identities must be unique")
        seen_schedule_sha256s.add(schedule.content_sha256)
        verify_schedule(task_plan=task_plan, schedule=schedule)
        verified.append(
            VerifiedSchedule(
                task_plan_id=task_plan.task_plan_id,
                schedule_ref_sha256=task_plan.schedule.content_sha256,
                schedule_sha256=schedule.content_sha256,
                schedule=schedule,
                ordered_assignment_sha256s=tuple(assignment.content_sha256 for assignment in schedule.assignments),
            )
        )
    closure = ScheduleClosure(
        source_batch_sha256=batch.content_sha256,
        schedules=tuple(verified),
    )
    expected_order = tuple(
        assignment for schedule in closure.schedules for assignment in schedule.ordered_assignment_sha256s
    )
    if expected_order != batch.ordered_assignment_sha256s:
        raise EvaluationExecutionPreflightError(
            "verified schedules differ from the global ordered assignments",
        )
    return closure


def close_compilation_batch(
    *,
    source_batch: EvaluationBatchPlan,
    schedule_closure: ScheduleClosure,
    results: tuple[
        ProposalRunSessionBundle | ProposalCompilationRejection,
        ...,
    ],
) -> CompilationBatchClosure:
    """Close compile results in frozen order and fail dispatch on rejection."""

    from aec_bench.experimentation.proposals.evaluation_execution_preflight.compilation import (
        close_compilation_batch as close_compilations,
    )

    return close_compilations(
        source_batch=source_batch,
        schedule_closure=schedule_closure,
        results=results,
    )


def verify_monitor_readiness(
    *,
    source_batch: EvaluationBatchPlan,
    evaluation_regime: EvaluationRegime,
    evaluation_assignment: EvaluationAssignment,
    policy: StandingMonitorPolicy,
    cycle_plan: CycleMonitorPlan,
    assurance_snapshot: MotifAssuranceSnapshot,
) -> MonitorReadiness:
    """Bind the standing alarms to the exact evaluation and assurance surfaces."""

    batch = _normalize_batch(source_batch)
    try:
        selected_policy = StandingMonitorPolicy.model_validate(
            policy.model_dump(mode="python"),
        )
        selected_evaluation_regime = EvaluationRegime.model_validate(
            evaluation_regime.model_dump(mode="python"),
        )
        selected_assignment = EvaluationAssignment.model_validate(
            evaluation_assignment.model_dump(mode="python"),
        )
        selected_cycle = CycleMonitorPlan.model_validate(
            cycle_plan.model_dump(mode="python"),
        )
        selected_assurance = MotifAssuranceSnapshot.model_validate(
            assurance_snapshot.model_dump(mode="python"),
        )
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            f"evaluation monitor surface is invalid: {error}",
        ) from error
    if selected_policy.content_sha256 != batch.monitor_policy_sha256:
        raise EvaluationExecutionPreflightError(
            "standing monitor policy identity differs from the source batch",
        )
    if selected_assignment.regime != batch.evaluation_regime_ref:
        raise EvaluationExecutionPreflightError(
            "evaluation assignment regime differs from the source batch",
        )
    try:
        validate_evaluation_regime_ref(selected_evaluation_regime, selected_assignment.regime)
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            str(error),
        ) from error
    monitoring = selected_evaluation_regime.monitoring_policy
    if monitoring is None or monitoring.configuration.get("standing_policy") != selected_policy.model_dump(mode="json"):
        raise EvaluationExecutionPreflightError(
            "evaluation regime monitoring policy differs from the standing monitor policy",
        )
    if selected_assurance.content_sha256 != batch.motif_assurance_snapshot_sha256:
        raise EvaluationExecutionPreflightError(
            "motif assurance snapshot identity differs from the source batch",
        )
    if selected_cycle.evaluation_regime != batch.evaluation_regime_ref:
        raise EvaluationExecutionPreflightError(
            "cycle monitor plan differs from the batch evaluation regime",
        )
    if selected_cycle.standing_policy_sha256 != selected_policy.content_sha256:
        raise EvaluationExecutionPreflightError(
            "cycle monitor plan differs from the standing monitor policy",
        )
    if selected_cycle.assurance_snapshot_sha256 != selected_assurance.content_sha256:
        raise EvaluationExecutionPreflightError(
            "cycle monitor plan differs from the motif assurance snapshot",
        )
    if selected_cycle.content_sha256 != batch.monitor_cycle_plan_sha256:
        raise EvaluationExecutionPreflightError(
            "cycle monitor plan identity differs from the source batch",
        )
    return MonitorReadiness(
        source_batch_sha256=batch.content_sha256,
        evaluation_regime=batch.evaluation_regime_ref,
        policy=selected_policy,
        policy_sha256=selected_policy.content_sha256,
        cycle_plan=selected_cycle,
        cycle_plan_sha256=selected_cycle.content_sha256,
        assurance_snapshot=selected_assurance,
        assurance_snapshot_sha256=selected_assurance.content_sha256,
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
    """Close the batch barrier only after every prerequisite is exact."""

    from aec_bench.experimentation.proposals.evaluation_execution_preflight.authorization import (
        prepare_execution_batch as build_prepared_batch,
    )

    return build_prepared_batch(
        source_batch=source_batch,
        proposal_closure=proposal_closure,
        schedule_closure=schedule_closure,
        compilation_closure=compilation_closure,
        monitor_closure=monitor_closure,
        evaluation_regime=evaluation_regime,
        evaluation_assignment=evaluation_assignment,
        task_verifier_scope=task_verifier_scope,
        ledger=ledger,
        authorizations=authorizations,
    )


def build_authorized_dispatch_ref(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
) -> AuthorizedDispatchRef:
    """Replay one governed authority chain before exposing its dispatch reference."""

    from aec_bench.experimentation.proposals.evaluation_execution_preflight.authorization import (
        build_authorized_dispatch_ref as build_dispatch_ref,
    )

    return build_dispatch_ref(
        ledger=ledger,
        authorization=authorization,
    )


def open_execution_gate(
    *,
    prepared_batch: PreparedExecutionBatch,
    ledger: AuthorityLedger,
    authorizations: tuple[GovernedProposalDispatchAuthorization, ...],
) -> ExecutionGate:
    """Replay all authorities just before exposing prepared dispatches."""

    from aec_bench.experimentation.proposals.evaluation_execution_preflight.authorization import (
        open_execution_gate as open_execution_gate,
    )

    return open_execution_gate(
        prepared_batch=prepared_batch,
        ledger=ledger,
        authorizations=authorizations,
    )


def _normalize_batch(source_batch: EvaluationBatchPlan) -> EvaluationBatchPlan:
    try:
        return EvaluationBatchPlan.model_validate(
            source_batch.model_dump(mode="python"),
        )
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            f"evaluation batch is invalid: {error}",
        ) from error


def _normalize_proposal_closure(
    *,
    batch: EvaluationBatchPlan,
    closure: ProposalBatchClosure,
) -> ProposalBatchClosure:
    try:
        selected = ProposalBatchClosure.model_validate(
            closure.model_dump(mode="python"),
        )
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            f"proposal closure is invalid: {error}",
        ) from error
    if selected.source_batch_sha256 != batch.content_sha256:
        raise EvaluationExecutionPreflightError(
            "proposal closure differs from the source batch",
        )
    expected_task_ids = tuple(
        task_plan.task_plan_id
        for task_plan in batch.task_plans
        for _ in range(batch.spec.proposer_invocations_per_task)
    )
    if tuple(item.task_plan_id for item in selected.invocations) != tuple(sorted(expected_task_ids)):
        raise EvaluationExecutionPreflightError(
            "proposal closure does not cover the batch task plans",
        )
    return selected


def _normalize_schedule_closure(
    *,
    batch: EvaluationBatchPlan,
    closure: ScheduleClosure,
) -> ScheduleClosure:
    try:
        selected = ScheduleClosure.model_validate(
            closure.model_dump(mode="python"),
        )
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            f"schedule closure is invalid: {error}",
        ) from error
    if selected.source_batch_sha256 != batch.content_sha256:
        raise EvaluationExecutionPreflightError(
            "schedule closure differs from the source batch",
        )
    expected = tuple(task_plan.task_plan_id for task_plan in batch.task_plans)
    if tuple(item.task_plan_id for item in selected.schedules) != expected:
        raise EvaluationExecutionPreflightError(
            "schedule closure does not cover the batch task plans",
        )
    return selected


def _normalize_compilation_closure(
    *,
    batch: EvaluationBatchPlan,
    schedules: ScheduleClosure,
    closure: CompilationBatchClosure,
) -> CompilationBatchClosure:
    try:
        selected = CompilationBatchClosure.model_validate(
            closure.model_dump(mode="python"),
        )
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            f"compilation closure is invalid: {error}",
        ) from error
    if (
        selected.source_batch_sha256 != batch.content_sha256
        or selected.schedule_closure_sha256 != schedules.content_sha256
        or selected.ordered_assignment_sha256s != batch.ordered_assignment_sha256s
    ):
        raise EvaluationExecutionPreflightError(
            "compilation closure differs from the source batch or schedule closure",
        )
    return selected


def _normalize_monitor_closure(
    *,
    batch: EvaluationBatchPlan,
    closure: MonitorReadiness,
) -> MonitorReadiness:
    try:
        selected = MonitorReadiness.model_validate(
            closure.model_dump(mode="python"),
        )
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            f"monitor closure is invalid: {error}",
        ) from error
    if (
        selected.source_batch_sha256 != batch.content_sha256
        or selected.policy_sha256 != batch.monitor_policy_sha256
        or selected.cycle_plan_sha256 != batch.monitor_cycle_plan_sha256
        or selected.assurance_snapshot_sha256 != batch.motif_assurance_snapshot_sha256
        or selected.evaluation_regime != batch.evaluation_regime_ref
    ):
        raise EvaluationExecutionPreflightError(
            "monitor closure differs from the source batch",
        )
    return selected
