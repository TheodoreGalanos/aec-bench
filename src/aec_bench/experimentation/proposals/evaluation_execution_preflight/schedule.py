# ABOUTME: Verifies one proposal evaluation schedule against its frozen task plan.
# ABOUTME: Enforces exact kernel, harness, coordinate, budget, and assignment identity.

from __future__ import annotations

from aec_bench.contracts.evaluation_generation.batch import TaskCandidatePlan
from aec_bench.experimentation.proposals.decomposition_optimization import (
    DecompositionExecutionSchedule,
)
from aec_bench.experimentation.proposals.evaluation_execution_preflight import (
    EvaluationExecutionPreflightError,
)


def verify_schedule(
    *,
    task_plan: TaskCandidatePlan,
    schedule: DecompositionExecutionSchedule,
) -> None:
    """Verify one concrete schedule against its exact frozen reference."""

    reference = task_plan.schedule
    if schedule.schedule_id != reference.schedule_id or schedule.content_sha256 != reference.schedule_sha256:
        raise EvaluationExecutionPreflightError(
            f"task plan {task_plan.task_plan_id} schedule identity differs from its reference",
        )
    if (
        schedule.kernel_ref != reference.kernel_ref
        or schedule.kernel_ref != task_plan.kernel_ref
        or schedule.fixed_harness_ref != reference.fixed_harness_ref
        or schedule.fixed_harness_ref != task_plan.fixed_harness_ref
        or schedule.evaluation_plan_ref != reference.evaluation_plan_ref
        or schedule.evaluation_plan_ref != task_plan.evaluation_plan_ref
        or schedule.proposal_freeze.content_sha256 != reference.proposal_freeze_sha256
        or schedule.proposal_freeze.content_sha256 != task_plan.proposal_freeze_sha256
        or schedule.aggregate_budget != reference.aggregate_budget
        or schedule.aggregate_budget != task_plan.aggregate_budget
        or schedule.coordinates != (task_plan.matched_coordinate,)
        or reference.coordinate_sha256 != task_plan.matched_coordinate.content_sha256
    ):
        raise EvaluationExecutionPreflightError(
            f"task plan {task_plan.task_plan_id} schedule differs from "
            "K, H0, evaluation, freeze, budget, or coordinate",
        )
    actual_assignments = tuple(
        (
            assignment.content_sha256,
            assignment.candidate,
            assignment.coordinate.content_sha256,
        )
        for assignment in schedule.assignments
    )
    expected_assignments = tuple(
        (
            assignment.assignment_sha256,
            assignment.candidate,
            assignment.coordinate_sha256,
        )
        for assignment in reference.assignments
    )
    if actual_assignments != expected_assignments:
        raise EvaluationExecutionPreflightError(
            f"task plan {task_plan.task_plan_id} schedule differs from its exact assignments",
        )
