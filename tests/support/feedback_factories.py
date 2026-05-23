# ABOUTME: Shared test factories for feedback-domain models in aec-bench tests.
# ABOUTME: Builds valid reviewers, annotations, and feedback artifacts with minimal boilerplate.

from typing import Any

from aec_bench.contracts.evaluation_result import Judgment
from aec_bench.contracts.task_definition import Visibility
from aec_bench.feedback.models import (
    AdjudicationRecord,
    AdjudicationStatus,
    CalibrationStatus,
    FeedbackAnnotation,
    FeedbackItem,
    FeedbackItemStatus,
    FeedbackItemType,
    ReviewerProfile,
    ReviewerWeighting,
)


def make_reviewer_profile(**overrides: Any) -> ReviewerProfile:
    payload = {
        "reviewer_id": "reviewer-001",
        "discipline": "mechanical",
        "calibration_status": CalibrationStatus.UNCALIBRATED,
        "calibration_version": None,
        "can_review_holdout": False,
        "weighting": ReviewerWeighting(
            calibration_score=0.5,
            discipline_score=1.0,
            experience_score=0.5,
        ),
        "created_at": "2026-03-16T10:00:00Z",
        "updated_at": "2026-03-16T10:00:00Z",
    }
    payload.update(overrides)
    return ReviewerProfile.model_validate(payload)


def make_feedback_annotation(**overrides: Any) -> FeedbackAnnotation:
    payload = {
        "annotation_id": "annotation-001",
        "trial_id": "trial-001",
        "experiment_id": "experiment-001",
        "task_id": "mechanical/heat-load/public-task",
        "task_visibility": Visibility.PUBLIC,
        "reviewer_id": "reviewer-001",
        "reviewer_discipline": "mechanical",
        "judgment": Judgment.PASS,
        "categories": ["verifier.output"],
        "notes": "Looks consistent with the task.",
        "created_at": "2026-03-16T10:05:00Z",
        "is_calibration": False,
        "calibration_version": None,
    }
    payload.update(overrides)
    return FeedbackAnnotation.model_validate(payload)


def make_adjudication_record(**overrides: Any) -> AdjudicationRecord:
    payload = {
        "decision_id": "decision-001",
        "trial_id": "trial-001",
        "experiment_id": "experiment-001",
        "task_id": "mechanical/heat-load/public-task",
        "task_visibility": Visibility.PUBLIC,
        "status": AdjudicationStatus.AGREED,
        "final_judgment": Judgment.PASS,
        "categories": ["verifier.output"],
        "decided_by": None,
        "rationale": None,
        "source_annotation_ids": ["annotation-001"],
        "created_at": "2026-03-16T10:10:00Z",
    }
    payload.update(overrides)
    return AdjudicationRecord.model_validate(payload)


def make_feedback_item(**overrides: Any) -> FeedbackItem:
    payload = {
        "item_id": "item-001",
        "trial_id": "trial-001",
        "experiment_id": "experiment-001",
        "task_id": "mechanical/heat-load/public-task",
        "task_visibility": Visibility.PUBLIC,
        "item_type": FeedbackItemType.VERIFIER_FIX,
        "status": FeedbackItemStatus.OPEN,
        "title": "Review verifier output handling",
        "summary": "Verifier category suggests output handling should be checked.",
        "categories": ["verifier.output"],
        "source_annotation_ids": ["annotation-001"],
        "adjudication_status": AdjudicationStatus.AGREED,
        "created_at": "2026-03-16T10:15:00Z",
    }
    payload.update(overrides)
    return FeedbackItem.model_validate(payload)
