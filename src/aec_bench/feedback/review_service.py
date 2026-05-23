# ABOUTME: Shared review workflow service for the feedback domain web and terminal surfaces.
# ABOUTME: Loads reviewer queues, compiles trial bundles, and validates annotation persistence.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from aec_bench.contracts.evaluation_result import Judgment
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.validators import StrictModel
from aec_bench.feedback.adjudication import adjudicate_trial_feedback
from aec_bench.feedback.annotation_consumer import (
    read_feedback_annotations,
    read_feedback_items,
    read_latest_adjudication,
    read_reviewer_profile,
    write_adjudication_record,
    write_calibration_result,
    write_feedback_annotation,
    write_feedback_item,
    write_reviewer_profile,
)
from aec_bench.feedback.assignment import build_reviewer_queue
from aec_bench.feedback.calibration import apply_calibration_result, score_reviewer_calibration
from aec_bench.feedback.models import (
    AdjudicationRecord,
    CalibrationReference,
    EvaluationFeedbackHandoff,
    FeedbackAnnotation,
    FeedbackItem,
    ReviewAssignment,
    ReviewerCalibrationResult,
    ReviewerProfile,
)
from aec_bench.feedback.signals import generate_feedback_items
from aec_bench.ledger.reader import read_trial_records
from aec_bench.tasks.loader import load_task_catalog


class ReviewError(Exception):
    pass


class ReviewNotFoundError(ReviewError):
    pass


class ReviewAccessError(ReviewError):
    pass


class ReviewQueueSnapshot(StrictModel):
    reviewer: ReviewerProfile
    assignments: list[ReviewAssignment]


class ReviewTrialBundle(StrictModel):
    trial: TrialRecord
    reviewer: ReviewerProfile
    annotations: list[FeedbackAnnotation]
    adjudication: AdjudicationRecord | None = None
    feedback_items: list[FeedbackItem]
    handoff: EvaluationFeedbackHandoff


def load_review_queue(
    *,
    ledger_root: Path,
    tasks_root: Path,
    feedback_root: Path,
    reviewer_id: str,
) -> ReviewQueueSnapshot:
    reviewer = _get_reviewer(feedback_root=feedback_root, reviewer_id=reviewer_id)
    task_catalog = load_task_catalog(tasks_root)
    assignments = build_reviewer_queue(
        records=read_trial_records(ledger_root),
        task_visibility_by_id={
            task_id: task_definition.visibility for task_id, task_definition in task_catalog.items()
        },
        reviewer=reviewer,
        existing_annotations=read_feedback_annotations(feedback_root=feedback_root),
    )
    return ReviewQueueSnapshot(reviewer=reviewer, assignments=assignments)


def load_review_bundle(
    *,
    ledger_root: Path,
    tasks_root: Path,
    feedback_root: Path,
    reviewer_id: str,
    trial_id: str,
) -> ReviewTrialBundle:
    reviewer = _get_reviewer(feedback_root=feedback_root, reviewer_id=reviewer_id)
    record = _get_trial_record(ledger_root=ledger_root, trial_id=trial_id)
    task_catalog = load_task_catalog(tasks_root)
    task_definition = task_catalog.get(record.task.task_id)
    if task_definition is None:
        raise ReviewNotFoundError("task not found")
    _enforce_visibility_access(
        reviewer=reviewer,
        is_holdout=task_definition.visibility.value == "holdout",
    )
    annotations = read_feedback_annotations(feedback_root=feedback_root, trial_id=trial_id)
    adjudication = read_latest_adjudication(feedback_root=feedback_root, trial_id=trial_id)
    return ReviewTrialBundle(
        trial=record,
        reviewer=reviewer,
        annotations=annotations,
        adjudication=adjudication,
        feedback_items=read_feedback_items(feedback_root=feedback_root, trial_id=trial_id),
        handoff=_build_handoff(annotations=annotations, adjudication=adjudication),
    )


def persist_feedback_annotation(
    *,
    ledger_root: Path,
    tasks_root: Path,
    feedback_root: Path,
    annotation: FeedbackAnnotation,
) -> FeedbackAnnotation:
    reviewer = _get_reviewer(feedback_root=feedback_root, reviewer_id=annotation.reviewer_id)
    record = _get_trial_record(ledger_root=ledger_root, trial_id=annotation.trial_id)
    task_catalog = load_task_catalog(tasks_root)
    task_definition = task_catalog.get(record.task.task_id)
    if task_definition is None:
        raise ReviewNotFoundError("task not found")
    _enforce_visibility_access(
        reviewer=reviewer,
        is_holdout=task_definition.visibility.value == "holdout",
    )
    if annotation.task_id != record.task.task_id:
        raise ReviewError("annotation task_id does not match trial task")
    if annotation.task_visibility != task_definition.visibility:
        raise ReviewError("annotation task_visibility does not match task definition")
    if annotation.experiment_id != record.experiment_id:
        raise ReviewError("annotation experiment_id does not match trial record")
    if annotation.reviewer_discipline != reviewer.discipline:
        raise ReviewError("annotation reviewer_discipline does not match reviewer profile")
    write_feedback_annotation(feedback_root=feedback_root, annotation=annotation)
    return annotation


def submit_review_annotation(
    *,
    ledger_root: Path,
    tasks_root: Path,
    feedback_root: Path,
    reviewer_id: str,
    trial_id: str,
    judgment: Judgment,
    categories: list[str],
    notes: str | None,
    is_calibration: bool = False,
    calibration_version: str | None = None,
) -> FeedbackAnnotation:
    reviewer = _get_reviewer(feedback_root=feedback_root, reviewer_id=reviewer_id)
    record = _get_trial_record(ledger_root=ledger_root, trial_id=trial_id)
    task_catalog = load_task_catalog(tasks_root)
    task_definition = task_catalog.get(record.task.task_id)
    if task_definition is None:
        raise ReviewNotFoundError("task not found")
    annotation = FeedbackAnnotation(
        annotation_id=f"annotation-{uuid4().hex}",
        trial_id=record.trial_id,
        experiment_id=record.experiment_id,
        task_id=record.task.task_id,
        task_visibility=task_definition.visibility,
        reviewer_id=reviewer.reviewer_id,
        reviewer_discipline=reviewer.discipline,
        judgment=judgment,
        categories=categories,
        notes=notes,
        created_at=datetime.now(UTC),
        is_calibration=is_calibration,
        calibration_version=calibration_version,
    )
    return persist_feedback_annotation(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        annotation=annotation,
    )


def score_review_calibration(
    *,
    feedback_root: Path,
    reviewer_id: str,
    calibration_version: str,
    references: dict[str, CalibrationReference],
) -> tuple[ReviewerCalibrationResult, ReviewerProfile]:
    reviewer = _get_reviewer(feedback_root=feedback_root, reviewer_id=reviewer_id)
    annotations = read_feedback_annotations(
        feedback_root=feedback_root,
        reviewer_id=reviewer_id,
    )
    result = score_reviewer_calibration(
        reviewer=reviewer,
        annotations=annotations,
        references=references,
        calibration_version=calibration_version,
    )
    updated_reviewer = apply_calibration_result(reviewer=reviewer, result=result)
    write_calibration_result(feedback_root=feedback_root, result=result)
    write_reviewer_profile(feedback_root=feedback_root, reviewer=updated_reviewer)
    return result, updated_reviewer


def adjudicate_review_trial(
    *,
    feedback_root: Path,
    reviewer_id: str,
    trial_id: str,
    decision_id: str,
    final_judgment: Judgment | str | None = None,
    rationale: str | None = None,
    contested: bool = False,
) -> tuple[AdjudicationRecord, list[FeedbackItem]]:
    reviewer = _get_reviewer(feedback_root=feedback_root, reviewer_id=reviewer_id)
    annotations = read_feedback_annotations(feedback_root=feedback_root, trial_id=trial_id)
    if not annotations:
        raise ReviewNotFoundError("trial has no annotations")
    _enforce_visibility_access(
        reviewer=reviewer,
        is_holdout=annotations[0].task_visibility.value == "holdout",
    )
    adjudication = adjudicate_trial_feedback(
        annotations=annotations,
        decision_id=decision_id,
        final_judgment=final_judgment,
        decided_by=reviewer_id,
        rationale=rationale,
        contested=contested,
    )
    write_adjudication_record(feedback_root=feedback_root, adjudication=adjudication)
    feedback_items = generate_feedback_items(annotations=annotations, adjudication=adjudication)
    for item in feedback_items:
        write_feedback_item(feedback_root=feedback_root, item=item)
    return adjudication, feedback_items


def _build_handoff(
    *,
    annotations: list[FeedbackAnnotation],
    adjudication: AdjudicationRecord | None,
) -> EvaluationFeedbackHandoff:
    from aec_bench.feedback.annotation_consumer import build_evaluation_feedback_handoff

    return build_evaluation_feedback_handoff(
        annotations=annotations,
        adjudication=adjudication,
    )


def _get_reviewer(*, feedback_root: Path, reviewer_id: str) -> ReviewerProfile:
    reviewer = read_reviewer_profile(feedback_root=feedback_root, reviewer_id=reviewer_id)
    if reviewer is None:
        raise ReviewNotFoundError("reviewer not found")
    return reviewer


def _get_trial_record(*, ledger_root: Path, trial_id: str) -> TrialRecord:
    for record in read_trial_records(ledger_root):
        if record.trial_id == trial_id:
            return record
    raise ReviewNotFoundError("trial not found")


def _enforce_visibility_access(*, reviewer: ReviewerProfile, is_holdout: bool) -> None:
    if is_holdout and not reviewer.can_review_holdout:
        raise ReviewAccessError("reviewer lacks holdout access")
