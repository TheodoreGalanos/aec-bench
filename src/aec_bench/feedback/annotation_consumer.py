# ABOUTME: Persistence and evaluation-handoff helpers for the feedback domain.
# ABOUTME: Stores append-only review records on disk and converts them into
# ABOUTME: evaluation-facing summaries.

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from aec_bench.contracts.evaluation_result import Annotation
from aec_bench.feedback.models import (
    AdjudicationRecord,
    EvaluationFeedbackHandoff,
    FeedbackAnnotation,
    FeedbackItem,
    ReviewerCalibrationResult,
    ReviewerProfile,
)
from aec_bench.feedback.signals import build_feedback_confidence


class DuplicateFeedbackRecordError(Exception):
    pass


def write_reviewer_profile(*, feedback_root: Path, reviewer: ReviewerProfile) -> Path:
    path = feedback_root / "reviewers" / f"{reviewer.reviewer_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reviewer.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_reviewer_profile(*, feedback_root: Path, reviewer_id: str) -> ReviewerProfile | None:
    path = feedback_root / "reviewers" / f"{reviewer_id}.json"
    if not path.exists():
        return None
    return ReviewerProfile.model_validate_json(path.read_text(encoding="utf-8"))


def read_reviewer_profiles(*, feedback_root: Path) -> list[ReviewerProfile]:
    return [
        ReviewerProfile.model_validate_json(path.read_text(encoding="utf-8"))
        for path in _iter_json_files(feedback_root / "reviewers")
    ]


def write_feedback_annotation(*, feedback_root: Path, annotation: FeedbackAnnotation) -> Path:
    path = feedback_root / "annotations" / annotation.trial_id / f"{annotation.annotation_id}.json"
    return _write_append_only(path=path, payload=annotation.model_dump_json(indent=2))


def read_feedback_annotations(
    *,
    feedback_root: Path,
    trial_id: str | None = None,
    reviewer_id: str | None = None,
) -> list[FeedbackAnnotation]:
    if trial_id is not None:
        paths = _iter_json_files(feedback_root / "annotations" / trial_id)
    else:
        paths = _iter_json_files(feedback_root / "annotations")
    annotations = [FeedbackAnnotation.model_validate_json(path.read_text(encoding="utf-8")) for path in paths]
    if reviewer_id is not None:
        annotations = [annotation for annotation in annotations if annotation.reviewer_id == reviewer_id]
    return sorted(
        annotations,
        key=lambda annotation: (annotation.created_at, annotation.annotation_id),
    )


def write_calibration_result(
    *,
    feedback_root: Path,
    result: ReviewerCalibrationResult,
) -> Path:
    path = feedback_root / "calibrations" / result.reviewer_id / f"{result.calibration_version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return path


def write_adjudication_record(*, feedback_root: Path, adjudication: AdjudicationRecord) -> Path:
    path = feedback_root / "adjudications" / adjudication.trial_id / f"{adjudication.decision_id}.json"
    return _write_append_only(path=path, payload=adjudication.model_dump_json(indent=2))


def read_latest_adjudication(*, feedback_root: Path, trial_id: str) -> AdjudicationRecord | None:
    adjudications = [
        AdjudicationRecord.model_validate_json(path.read_text(encoding="utf-8"))
        for path in _iter_json_files(feedback_root / "adjudications" / trial_id)
    ]
    if not adjudications:
        return None
    return sorted(
        adjudications,
        key=lambda adjudication: (adjudication.created_at, adjudication.decision_id),
    )[-1]


def write_feedback_item(*, feedback_root: Path, item: FeedbackItem) -> Path:
    path = feedback_root / "items" / item.trial_id / f"{item.item_id}.json"
    return _write_append_only(path=path, payload=item.model_dump_json(indent=2))


def read_feedback_items(*, feedback_root: Path, trial_id: str | None = None) -> list[FeedbackItem]:
    if trial_id is not None:
        paths = _iter_json_files(feedback_root / "items" / trial_id)
    else:
        paths = _iter_json_files(feedback_root / "items")
    items = [FeedbackItem.model_validate_json(path.read_text(encoding="utf-8")) for path in paths]
    return sorted(items, key=lambda item: (item.created_at, item.item_id))


def build_evaluation_feedback_handoff(
    *,
    annotations: Iterable[FeedbackAnnotation],
    adjudication: AdjudicationRecord | None = None,
) -> EvaluationFeedbackHandoff:
    annotation_list = list(annotations)
    evaluation_annotations = [
        Annotation(
            reviewer_id=annotation.reviewer_id,
            reviewer_discipline=annotation.reviewer_discipline,
            timestamp=annotation.created_at,
            judgment=annotation.judgment,
            categories=annotation.categories,
            notes=annotation.notes,
        )
        for annotation in annotation_list
    ]
    return EvaluationFeedbackHandoff(
        annotations=evaluation_annotations,
        confidence=build_feedback_confidence(
            annotations=annotation_list,
            adjudication=adjudication,
        ),
        adjudication=adjudication,
    )


def _write_append_only(*, path: Path, payload: str) -> Path:
    if path.exists():
        raise DuplicateFeedbackRecordError(f"feedback record already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def _iter_json_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.json") if path.is_file())
