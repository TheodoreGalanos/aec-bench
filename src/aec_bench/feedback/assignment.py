# ABOUTME: Reviewer assignment logic for the feedback domain in aec-bench.
# ABOUTME: Builds deterministic review queues with holdout safety and discipline-aware ordering.

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime

from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.feedback.models import FeedbackAnnotation, ReviewAssignment, ReviewerProfile


def build_reviewer_queue(
    *,
    records: Sequence[TrialRecord],
    task_visibility_by_id: dict[str, Visibility],
    reviewer: ReviewerProfile,
    existing_annotations: Sequence[FeedbackAnnotation],
    limit: int | None = None,
) -> list[ReviewAssignment]:
    annotation_counts = Counter(annotation.trial_id for annotation in existing_annotations)
    reviewer_trial_ids = {
        annotation.trial_id for annotation in existing_annotations if annotation.reviewer_id == reviewer.reviewer_id
    }
    candidates: list[tuple[tuple[int, int, str, str], ReviewAssignment]] = []
    assigned_at = datetime.now(UTC)

    for record in records:
        visibility = task_visibility_by_id.get(record.task.task_id)
        if visibility is None:
            continue
        if visibility is Visibility.HOLDOUT and not reviewer.can_review_holdout:
            continue
        if record.trial_id in reviewer_trial_ids:
            continue

        discipline = _task_discipline(record.task.task_id)
        discipline_match = discipline == reviewer.discipline.casefold()
        reason = "discipline_match" if discipline_match else "cross_discipline_backup"
        assignment = ReviewAssignment(
            assignment_id=f"{reviewer.reviewer_id}:{record.trial_id}",
            trial_id=record.trial_id,
            experiment_id=record.experiment_id,
            task_id=record.task.task_id,
            task_visibility=visibility,
            reviewer_id=reviewer.reviewer_id,
            reviewer_discipline=reviewer.discipline,
            assigned_at=assigned_at,
            assignment_reason=reason,
        )
        sort_key = (
            annotation_counts[record.trial_id],
            0 if discipline_match else 1,
            record.experiment_id,
            record.trial_id,
        )
        candidates.append((sort_key, assignment))

    assignments = [assignment for _, assignment in sorted(candidates, key=lambda item: item[0])]
    if limit is not None:
        return assignments[:limit]
    return assignments


def _task_discipline(task_id: str) -> str:
    return task_id.split("/", maxsplit=1)[0].casefold()
