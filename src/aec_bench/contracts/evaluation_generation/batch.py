# ABOUTME: Defines candidate assignments, schedules, task plans, and evaluation batches.
# ABOUTME: Checks complete batch topology against supplied generation design data.

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.evaluation_generation.cohort import (
    EvaluationCohortBinding,
    EvaluationCohortManifest,
    EvaluationCohortTask,
    validate_cohort_binding,
)
from aec_bench.contracts.evaluation_generation.spec import (
    EvaluationGenerationSourceRef,
    EvaluationGenerationSpec,
    ProposalGenerationPolicy,
)
from aec_bench.contracts.evaluation_plane import EvaluationRegimeAuthorityScope
from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.harness_instance import HarnessBudget, HarnessInstanceRef
from aec_bench.contracts.harness_kernel import KernelRef, validate_sha256
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.validators import NonEmptyStr


class CandidateAssignmentRef(LegacyContentAddressedModel):
    """Contract-safe identity of one candidate-coordinate assignment."""

    schema_version: Literal["aecbench.candidate-assignment-ref.v2"] = "aecbench.candidate-assignment-ref.v2"
    assignment_sha256: str
    candidate: ProgramCandidateRef
    coordinate_sha256: str

    @field_validator("assignment_sha256", "coordinate_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class CandidateScheduleRef(LegacyContentAddressedModel):
    """Task-scoped candidate schedule whose shape is supplied by its generation spec."""

    schema_version: Literal["aecbench.candidate-schedule-ref.v2"] = "aecbench.candidate-schedule-ref.v2"
    schedule_id: NonEmptyStr
    schedule_sha256: str
    kernel_ref: KernelRef
    fixed_harness_ref: HarnessInstanceRef
    evaluation_regime_ref: EvaluationRegimeRef
    proposal_freeze_sha256: str
    aggregate_budget: HarnessBudget
    coordinate_sha256: str
    assignments: tuple[CandidateAssignmentRef, ...] = Field(min_length=1)

    @field_validator(
        "schedule_sha256",
        "proposal_freeze_sha256",
        "coordinate_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("assignments")
    @classmethod
    def canonicalize_assignments(
        cls,
        value: tuple[CandidateAssignmentRef, ...],
    ) -> tuple[CandidateAssignmentRef, ...]:
        identity_fields = (
            (
                "assignment identities",
                tuple(item.assignment_sha256 for item in value),
            ),
            ("candidate ids", tuple(item.candidate.candidate_id for item in value)),
            (
                "candidate identities",
                tuple(item.candidate.content_sha256 for item in value),
            ),
        )
        for label, identities in identity_fields:
            if len(identities) != len(set(identities)):
                raise ValueError(f"candidate schedule {label} must be unique")
        coordinate_sha256s = {assignment.coordinate_sha256 for assignment in value}
        if len(coordinate_sha256s) != 1:
            raise ValueError(
                "candidate schedule assignments must use one matched coordinate",
            )
        return tuple(sorted(value, key=lambda item: item.candidate.candidate_id))

    @model_validator(mode="after")
    def validate_coordinate(self) -> Self:
        if {assignment.coordinate_sha256 for assignment in self.assignments} != {self.coordinate_sha256}:
            raise ValueError(
                "candidate schedule assignments differ from its coordinate",
            )
        return self


class TaskCandidatePlan(LegacyContentAddressedModel):
    """One task-scoped candidate plan with no evaluation outcomes."""

    schema_version: Literal["aecbench.task-candidate-plan.v2"] = "aecbench.task-candidate-plan.v2"
    task_plan_id: NonEmptyStr
    cohort_binding: EvaluationCohortBinding
    cohort_task: EvaluationCohortTask
    kernel_ref: KernelRef
    fixed_harness_ref: HarnessInstanceRef
    evaluation_regime_ref: EvaluationRegimeRef
    proposal_policy_sha256: str
    runtime_archive_sha256: str
    monitor_policy_sha256: str
    monitor_cycle_plan_sha256: str
    motif_assurance_snapshot_sha256: str
    aggregate_budget: HarnessBudget
    proposal_freeze_sha256: str
    candidate_manifest_sha256: str
    matched_coordinate: MatchedEvaluationCoordinate
    schedule: CandidateScheduleRef

    @field_validator(
        "proposal_policy_sha256",
        "runtime_archive_sha256",
        "monitor_policy_sha256",
        "monitor_cycle_plan_sha256",
        "motif_assurance_snapshot_sha256",
        "proposal_freeze_sha256",
        "candidate_manifest_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_task_bindings(self) -> Self:
        task = self.cohort_task.task
        coordinate = self.matched_coordinate
        expected_task_identity = (
            task.task_id,
            task.public_snapshot.commitment_sha256,
            task.review.profile_id,
        )
        if (
            coordinate.task_id,
            coordinate.task_revision,
            coordinate.review_lineage_id,
        ) != expected_task_identity:
            raise ValueError(
                "candidate task plan coordinate differs from its cohort task",
            )
        schedule = self.schedule
        if (
            schedule.kernel_ref != self.kernel_ref
            or schedule.fixed_harness_ref != self.fixed_harness_ref
            or schedule.evaluation_regime_ref != self.evaluation_regime_ref
            or schedule.aggregate_budget != self.aggregate_budget
            or schedule.proposal_freeze_sha256 != self.proposal_freeze_sha256
            or schedule.coordinate_sha256 != coordinate.content_sha256
        ):
            raise ValueError(
                "candidate task plan schedule differs from its frozen bindings",
            )
        return self


class EvaluationBatchPlan(LegacyContentAddressedModel):
    """Complete outcome-blind candidate batch validated against supplied design data."""

    schema_version: Literal["aecbench.evaluation-batch-plan.v2"] = "aecbench.evaluation-batch-plan.v2"
    batch_id: NonEmptyStr
    prepared_generation_sha256: str
    cohort: EvaluationCohortManifest
    cohort_binding: EvaluationCohortBinding
    kernel_ref: KernelRef
    fixed_harness_ref: HarnessInstanceRef
    evaluation_regime_ref: EvaluationRegimeRef
    evaluation_authority_scope: EvaluationRegimeAuthorityScope
    proposal_policy: ProposalGenerationPolicy
    candidate_manifest_proposal_policy_sha256: str
    compilation_policies_sha256: str
    runtime_archive_sha256: str
    monitor_policy_sha256: str
    monitor_cycle_plan_sha256: str
    motif_assurance_snapshot_sha256: str
    candidate_budget: HarnessBudget
    spec: EvaluationGenerationSpec
    task_plans: tuple[TaskCandidatePlan, ...] = Field(min_length=1)
    ordered_assignment_sha256s: tuple[str, ...] = Field(min_length=1)
    source_contracts: tuple[EvaluationGenerationSourceRef, ...] = ()
    outcomes_observed: Literal[False] = False
    promotion_permitted: Literal[False] = False

    @field_validator(
        "prepared_generation_sha256",
        "candidate_manifest_proposal_policy_sha256",
        "compilation_policies_sha256",
        "runtime_archive_sha256",
        "monitor_policy_sha256",
        "monitor_cycle_plan_sha256",
        "motif_assurance_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("task_plans")
    @classmethod
    def canonicalize_task_plans(
        cls,
        value: tuple[TaskCandidatePlan, ...],
    ) -> tuple[TaskCandidatePlan, ...]:
        identity_fields = (
            (
                "task identities",
                tuple(item.cohort_task.task.task_id for item in value),
            ),
            (
                "world identities",
                tuple(item.cohort_task.task.review.profile_id for item in value),
            ),
            (
                "schedule identities",
                tuple(item.schedule.schedule_sha256 for item in value),
            ),
        )
        for label, identities in identity_fields:
            if len(identities) != len(set(identities)):
                raise ValueError(f"evaluation batch {label} must be unique")
        return tuple(sorted(value, key=lambda item: item.cohort_task.task.task_id))

    @field_validator("ordered_assignment_sha256s")
    @classmethod
    def validate_assignment_sha256s(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError(
                "evaluation batch assignment identities must be unique",
            )
        return value

    @field_validator("source_contracts")
    @classmethod
    def validate_source_contracts(
        cls,
        value: tuple[EvaluationGenerationSourceRef, ...],
    ) -> tuple[EvaluationGenerationSourceRef, ...]:
        roles = tuple(item.role for item in value)
        digests = tuple(item.content_sha256 for item in value)
        if len(roles) != len(set(roles)) or len(digests) != len(set(digests)):
            raise ValueError(
                "evaluation-batch compatibility sources must be unique",
            )
        return value

    @model_validator(mode="after")
    def validate_batch_bindings(self) -> Self:
        _validate_batch_scope(self)
        _validate_batch_task_plans(self)
        _validate_assignment_order(self)
        return self


def _validate_batch_scope(batch: EvaluationBatchPlan) -> None:
    validate_cohort_binding(batch.cohort, batch.cohort_binding)
    if batch.evaluation_authority_scope.regime != batch.evaluation_regime_ref:
        raise ValueError(
            "evaluation batch critic authority differs from its evaluation regime",
        )
    if len(batch.task_plans) != batch.spec.task_count:
        raise ValueError(
            "evaluation batch task count differs from its supplied spec",
        )
    expected_tasks = {item.content_sha256 for item in batch.cohort.tasks}
    actual_tasks = {item.cohort_task.content_sha256 for item in batch.task_plans}
    if actual_tasks != expected_tasks:
        raise ValueError("evaluation batch tasks must match the exact cohort")


def _validate_batch_task_plans(batch: EvaluationBatchPlan) -> None:
    cohort_by_task_id = {item.task.task_id: item for item in batch.cohort.tasks}
    expected_kind_counts = {
        requirement.kind: requirement.count_per_task for requirement in batch.spec.candidate_kind_requirements
    }
    for task_plan in batch.task_plans:
        _validate_shared_task_bindings(batch, task_plan)
        cohort_task = cohort_by_task_id[task_plan.cohort_task.task.task_id]
        if task_plan.matched_coordinate.seed not in cohort_task.evaluation_seeds:
            raise ValueError(
                "evaluation batch coordinate seed is absent from its cohort task",
            )
        assignments = task_plan.schedule.assignments
        if len(assignments) != batch.spec.assignment_count_per_task:
            raise ValueError(
                "evaluation batch task schedule differs from its supplied cardinality",
            )
        actual_kind_counts = {
            kind: sum(assignment.candidate.kind is kind for assignment in assignments) for kind in ProgramCandidateKind
        }
        if any(
            actual_kind_counts[kind] != expected_count for kind, expected_count in expected_kind_counts.items()
        ) or any(count for kind, count in actual_kind_counts.items() if kind not in expected_kind_counts):
            raise ValueError(
                "evaluation batch candidate kinds differ from its supplied spec",
            )


def _validate_shared_task_bindings(
    batch: EvaluationBatchPlan,
    task_plan: TaskCandidatePlan,
) -> None:
    if (
        task_plan.cohort_binding != batch.cohort_binding
        or task_plan.kernel_ref != batch.kernel_ref
        or task_plan.fixed_harness_ref != batch.fixed_harness_ref
        or task_plan.evaluation_regime_ref != batch.evaluation_regime_ref
        or task_plan.proposal_policy_sha256 != batch.candidate_manifest_proposal_policy_sha256
        or task_plan.runtime_archive_sha256 != batch.runtime_archive_sha256
        or task_plan.monitor_policy_sha256 != batch.monitor_policy_sha256
        or task_plan.monitor_cycle_plan_sha256 != batch.monitor_cycle_plan_sha256
        or task_plan.motif_assurance_snapshot_sha256 != batch.motif_assurance_snapshot_sha256
        or task_plan.aggregate_budget != batch.candidate_budget
    ):
        raise ValueError(
            "evaluation batch task plan differs from its shared bindings",
        )


def _validate_assignment_order(batch: EvaluationBatchPlan) -> None:
    expected_assignment_order = tuple(
        assignment.assignment_sha256 for task_plan in batch.task_plans for assignment in task_plan.schedule.assignments
    )
    if len(batch.ordered_assignment_sha256s) != batch.spec.total_assignment_count:
        raise ValueError(
            "evaluation batch assignment count differs from its supplied spec",
        )
    if batch.ordered_assignment_sha256s != expected_assignment_order:
        raise ValueError(
            "evaluation batch assignment order differs from its task schedules",
        )
