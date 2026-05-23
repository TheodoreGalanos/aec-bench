# ABOUTME: Derived signal helpers for turning human review into structured benchmark feedback.
# ABOUTME: Produces confidence summaries and deterministic improvement items from annotations.

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime

from aec_bench.contracts.evaluation_result import ConfidenceMetadata
from aec_bench.feedback.models import (
    AdjudicationRecord,
    AdjudicationStatus,
    FeedbackAnnotation,
    FeedbackItem,
    FeedbackItemStatus,
    FeedbackItemType,
)


def build_feedback_confidence(
    *,
    annotations: Sequence[FeedbackAnnotation],
    adjudication: AdjudicationRecord | None = None,
) -> ConfidenceMetadata:
    annotator_count = len({annotation.reviewer_id for annotation in annotations})
    if not annotations:
        agreement = None
    else:
        judgment_counts = Counter(annotation.judgment for annotation in annotations)
        agreement = max(judgment_counts.values()) / len(annotations)
    method = "adjudicated_human_review" if adjudication is not None else "human_review_consensus"
    return ConfidenceMetadata(
        annotator_count=annotator_count,
        inter_rater_agreement=agreement,
        confidence_method=method,
    )


def generate_feedback_items(
    *,
    annotations: Sequence[FeedbackAnnotation],
    adjudication: AdjudicationRecord | None = None,
) -> list[FeedbackItem]:
    if not annotations:
        return []
    first = annotations[0]
    created_at = adjudication.created_at if adjudication is not None else datetime.now(UTC)
    categories = sorted({category for annotation in annotations for category in annotation.categories})
    source_annotation_ids = [annotation.annotation_id for annotation in annotations]
    adjudication_status = adjudication.status if adjudication is not None else AdjudicationStatus.NEEDS_ADJUDICATION
    items: list[FeedbackItem] = []

    for item_type in sorted(
        {_item_type_for_category(category) for category in categories},
        key=str,
    ):
        matching_categories = sorted(
            category for category in categories if _item_type_for_category(category) == item_type
        )
        items.append(
            FeedbackItem(
                item_id=f"{first.trial_id}:{item_type.value}",
                trial_id=first.trial_id,
                experiment_id=first.experiment_id,
                task_id=first.task_id,
                task_visibility=first.task_visibility,
                item_type=item_type,
                status=FeedbackItemStatus.OPEN,
                title=_title_for_item_type(item_type),
                summary=_summary_for_categories(matching_categories),
                categories=matching_categories,
                source_annotation_ids=source_annotation_ids,
                adjudication_status=adjudication_status,
                created_at=created_at,
            )
        )

    return items


def _item_type_for_category(category: str) -> FeedbackItemType:
    if category.startswith("verifier"):
        return FeedbackItemType.VERIFIER_FIX
    if category.startswith("instruction"):
        return FeedbackItemType.INSTRUCTION_REVISION
    if category.startswith("instance"):
        return FeedbackItemType.INSTANCE_PROPOSAL
    if category.startswith("rubric"):
        return FeedbackItemType.RUBRIC_UPDATE
    return FeedbackItemType.LIFECYCLE_CHANGE


def _title_for_item_type(item_type: FeedbackItemType) -> str:
    titles = {
        FeedbackItemType.VERIFIER_FIX: "Review verifier behavior",
        FeedbackItemType.INSTRUCTION_REVISION: "Clarify task instructions",
        FeedbackItemType.INSTANCE_PROPOSAL: "Consider a new task instance",
        FeedbackItemType.RUBRIC_UPDATE: "Review rubric coverage",
        FeedbackItemType.LIFECYCLE_CHANGE: "Review task lifecycle",
    }
    return titles[item_type]


def _summary_for_categories(categories: Sequence[str]) -> str:
    category_text = ", ".join(categories)
    return f"Human review surfaced these structured categories: {category_text}."
