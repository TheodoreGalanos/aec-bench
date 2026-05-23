# ABOUTME: Adjudication helpers for resolving reviewer disagreement in the feedback domain.
# ABOUTME: Keeps consensus, escalation, and final decisions explicit instead of silently averaging.

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from aec_bench.contracts.evaluation_result import Judgment
from aec_bench.feedback.models import AdjudicationRecord, AdjudicationStatus, FeedbackAnnotation


def adjudicate_trial_feedback(
    *,
    annotations: Sequence[FeedbackAnnotation],
    decision_id: str | None = None,
    final_judgment: Judgment | str | None = None,
    decided_by: str | None = None,
    rationale: str | None = None,
    contested: bool = False,
) -> AdjudicationRecord:
    if not annotations:
        msg = "at least one annotation is required for adjudication"
        raise ValueError(msg)

    first = annotations[0]
    judgments = {annotation.judgment for annotation in annotations}
    categories = sorted({category for annotation in annotations for category in annotation.categories})
    annotation_ids = [annotation.annotation_id for annotation in annotations]
    resolved_judgment = _coerce_judgment(final_judgment)
    resolved_decision_id = decision_id or f"{first.trial_id}:adjudication"

    if len(judgments) == 1:
        return AdjudicationRecord(
            decision_id=resolved_decision_id,
            trial_id=first.trial_id,
            experiment_id=first.experiment_id,
            task_id=first.task_id,
            task_visibility=first.task_visibility,
            status=AdjudicationStatus.AGREED,
            final_judgment=next(iter(judgments)),
            categories=categories,
            source_annotation_ids=annotation_ids,
            created_at=datetime.now(UTC),
        )

    if contested:
        return AdjudicationRecord(
            decision_id=resolved_decision_id,
            trial_id=first.trial_id,
            experiment_id=first.experiment_id,
            task_id=first.task_id,
            task_visibility=first.task_visibility,
            status=AdjudicationStatus.CONTESTED,
            categories=categories,
            rationale=rationale,
            source_annotation_ids=annotation_ids,
            created_at=datetime.now(UTC),
        )

    if resolved_judgment is None or decided_by is None:
        return AdjudicationRecord(
            decision_id=resolved_decision_id,
            trial_id=first.trial_id,
            experiment_id=first.experiment_id,
            task_id=first.task_id,
            task_visibility=first.task_visibility,
            status=AdjudicationStatus.NEEDS_ADJUDICATION,
            categories=categories,
            rationale=rationale,
            source_annotation_ids=annotation_ids,
            created_at=datetime.now(UTC),
        )

    return AdjudicationRecord(
        decision_id=resolved_decision_id,
        trial_id=first.trial_id,
        experiment_id=first.experiment_id,
        task_id=first.task_id,
        task_visibility=first.task_visibility,
        status=AdjudicationStatus.ADJUDICATED,
        final_judgment=resolved_judgment,
        categories=categories,
        decided_by=decided_by,
        rationale=rationale,
        source_annotation_ids=annotation_ids,
        created_at=datetime.now(UTC),
    )


def _coerce_judgment(value: Judgment | str | None) -> Judgment | None:
    if value is None or isinstance(value, Judgment):
        return value
    return Judgment(value)
