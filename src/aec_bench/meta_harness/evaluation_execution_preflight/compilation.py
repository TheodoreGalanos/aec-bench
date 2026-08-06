# ABOUTME: Closes evaluation compilation results against frozen assignments.
# ABOUTME: Preserves exact schedule, candidate, budget, and rejection identities.

from __future__ import annotations

from aec_bench.contracts.evaluation_generation.batch import EvaluationBatchPlan
from aec_bench.contracts.proposal_execution.compilation import (
    ProposalCompilationRejection,
    ProposalCompilationSuccess,
)
from aec_bench.contracts.proposal_execution_types import ProposalCompilationStatus
from aec_bench.meta_harness.evaluation_execution_preflight import (
    CompilationBatchClosure,
    CompilationResultRef,
    EvaluationExecutionPreflightError,
    ScheduleClosure,
)
from aec_bench.meta_harness.evaluation_execution_preflight.lifecycle import (
    _normalize_batch,
    _normalize_schedule_closure,
)
from aec_bench.meta_harness.program_proposal_compilation import (
    ProposalRunSessionBundle,
)


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

    batch = _normalize_batch(source_batch)
    schedules = _normalize_schedule_closure(
        batch=batch,
        closure=schedule_closure,
    )
    if len(results) != len(batch.ordered_assignment_sha256s):
        raise EvaluationExecutionPreflightError(
            "compilation result count differs from the batch assignments",
        )
    by_assignment = _resolve_compilation_results(
        batch=batch,
        results=results,
    )
    ordered = _order_compilation_results(
        batch=batch,
        schedules=schedules,
        by_assignment=by_assignment,
    )
    rejected = tuple(
        result.assignment_sha256 for result in ordered if result.status is ProposalCompilationStatus.REJECTED
    )
    return CompilationBatchClosure(
        source_batch_sha256=batch.content_sha256,
        schedule_closure_sha256=schedules.content_sha256,
        ordered_assignment_sha256s=batch.ordered_assignment_sha256s,
        results=ordered,
        rejected_assignment_sha256s=rejected,
        dispatch_permitted=not rejected,
    )


def _resolve_compilation_results(
    *,
    batch: EvaluationBatchPlan,
    results: tuple[
        ProposalRunSessionBundle | ProposalCompilationRejection,
        ...,
    ],
) -> dict[str, CompilationResultRef]:
    by_assignment: dict[str, CompilationResultRef] = {}
    for raw_result in results:
        bundle, rejection, compilation = _normalize_compilation_result(
            raw_result,
        )
        matches = tuple(
            (task_plan, assignment)
            for task_plan in batch.task_plans
            if task_plan.proposal_freeze_sha256 == compilation.proposal_freeze.content_sha256
            for assignment in task_plan.schedule.assignments
            if assignment.candidate == compilation.candidate_ref
        )
        if len(matches) != 1:
            raise EvaluationExecutionPreflightError(
                "compiled candidate and freeze do not resolve to exactly one frozen assignment",
            )
        task_plan, assignment = matches[0]
        if bundle is not None:
            result_ref = CompilationResultRef.from_bundle(
                assignment_sha256=assignment.assignment_sha256,
                schedule_sha256=task_plan.schedule.schedule_sha256,
                coordinate_sha256=assignment.coordinate_sha256,
                bundle=bundle,
            )
        else:
            if rejection is None:
                raise AssertionError(
                    "validated compilation result has no bundle or rejection",
                )
            result_ref = CompilationResultRef.from_rejection(
                assignment_sha256=assignment.assignment_sha256,
                schedule_sha256=task_plan.schedule.schedule_sha256,
                coordinate_sha256=assignment.coordinate_sha256,
                rejection=rejection,
            )
        if result_ref.assignment_sha256 in by_assignment:
            raise EvaluationExecutionPreflightError(
                "compilation result assignments must be unique",
            )
        by_assignment[result_ref.assignment_sha256] = result_ref
    return by_assignment


def _normalize_compilation_result(
    raw_result: ProposalRunSessionBundle | ProposalCompilationRejection,
) -> tuple[
    ProposalRunSessionBundle | None,
    ProposalCompilationRejection | None,
    ProposalCompilationSuccess | ProposalCompilationRejection,
]:
    try:
        if isinstance(raw_result, ProposalRunSessionBundle):
            bundle = ProposalRunSessionBundle.model_validate(
                raw_result.model_dump(mode="python"),
            )
            return bundle, None, bundle.compilation
        if isinstance(raw_result, ProposalCompilationRejection):
            rejection = ProposalCompilationRejection.model_validate(
                raw_result.model_dump(mode="python"),
            )
            return None, rejection, rejection
        raise TypeError(
            "compilation input must be a session bundle or typed rejection",
        )
    except ValueError as error:
        raise EvaluationExecutionPreflightError(
            f"compilation result is invalid: {error}",
        ) from error
    except TypeError as error:
        raise EvaluationExecutionPreflightError(str(error)) from error


def _order_compilation_results(
    *,
    batch: EvaluationBatchPlan,
    schedules: ScheduleClosure,
    by_assignment: dict[str, CompilationResultRef],
) -> tuple[CompilationResultRef, ...]:
    ordered: list[CompilationResultRef] = []
    task_plan_by_schedule = {task_plan.schedule.schedule_sha256: task_plan for task_plan in batch.task_plans}
    verified_schedule_by_sha256 = {verified.schedule_sha256: verified for verified in schedules.schedules}
    for assignment_sha256 in batch.ordered_assignment_sha256s:
        closed_result = by_assignment.get(assignment_sha256)
        if closed_result is None:
            raise EvaluationExecutionPreflightError(
                "compilation results do not cover every frozen assignment",
            )
        task_plan = task_plan_by_schedule.get(closed_result.schedule_sha256)
        verified_schedule = verified_schedule_by_sha256.get(
            closed_result.schedule_sha256,
        )
        if task_plan is None or verified_schedule is None:
            raise EvaluationExecutionPreflightError(
                "compilation result references an unknown verified schedule",
            )
        scheduled_assignment = next(
            (item for item in task_plan.schedule.assignments if item.assignment_sha256 == assignment_sha256),
            None,
        )
        if scheduled_assignment is None:
            raise EvaluationExecutionPreflightError(
                "compilation result differs from its schedule assignment",
            )
        if (
            closed_result.candidate != scheduled_assignment.candidate
            or closed_result.coordinate_sha256 != scheduled_assignment.coordinate_sha256
            or closed_result.proposal_freeze_sha256 != task_plan.proposal_freeze_sha256
            or closed_result.kernel_sha256 != task_plan.kernel_sha256
            or closed_result.fixed_harness_sha256 != task_plan.fixed_harness_sha256
            or closed_result.evaluation_plan_ref != task_plan.evaluation_plan_ref
            or closed_result.aggregate_budget != task_plan.aggregate_budget
        ):
            raise EvaluationExecutionPreflightError(
                f"compilation result for {assignment_sha256} differs from its frozen assignment",
            )
        ordered.append(closed_result)
    return tuple(ordered)
