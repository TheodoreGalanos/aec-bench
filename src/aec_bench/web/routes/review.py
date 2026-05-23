# ABOUTME: Internal review routes for the feedback domain web layer in aec-bench.
# ABOUTME: Serves reviewer queues, trial detail, annotations, calibration,
# ABOUTME: and adjudication behind explicit gates.

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from aec_bench.contracts.validators import StrictModel
from aec_bench.feedback.adjudication import adjudicate_trial_feedback
from aec_bench.feedback.annotation_consumer import (
    DuplicateFeedbackRecordError,
    read_feedback_annotations,
    read_reviewer_profile,
    write_adjudication_record,
    write_calibration_result,
    write_feedback_item,
    write_reviewer_profile,
)
from aec_bench.feedback.calibration import apply_calibration_result, score_reviewer_calibration
from aec_bench.feedback.models import (
    CalibrationReference,
    FeedbackAnnotation,
    ReviewerProfile,
)
from aec_bench.feedback.review_service import (
    ReviewAccessError,
    ReviewError,
    ReviewNotFoundError,
    load_review_bundle,
    load_review_queue,
    persist_feedback_annotation,
)
from aec_bench.feedback.signals import generate_feedback_items
from aec_bench.web.dependencies import (
    get_web_settings,
    require_internal_access,
)
from aec_bench.web.schemas import ReviewQueueResponse, ReviewTrialResponse

router = APIRouter()


class CalibrationRunRequest(StrictModel):
    reviewer_id: str
    calibration_version: str
    references: list[CalibrationReference]


class AdjudicationSubmission(StrictModel):
    decision_id: str
    trial_id: str
    final_judgment: str | None = None
    decided_by: str | None = None
    rationale: str | None = None
    contested: bool = False


@router.post(
    "/api/internal/review/reviewers",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_access)],
)
def upsert_reviewer(request: Request, reviewer: ReviewerProfile) -> dict[str, object]:
    settings = get_web_settings(request)
    write_reviewer_profile(feedback_root=settings.feedback_root, reviewer=reviewer)
    return reviewer.model_dump(mode="json")


@router.get(
    "/api/internal/review/assignments",
    dependencies=[Depends(require_internal_access)],
)
def review_assignments(request: Request, reviewer_id: str) -> dict[str, object]:
    return _build_assignment_payload(request=request, reviewer_id=reviewer_id)


@router.get(
    "/api/internal/review/trials/{trial_id}",
    dependencies=[Depends(require_internal_access)],
)
def review_trial(request: Request, trial_id: str, reviewer_id: str) -> dict[str, object]:
    return _build_review_bundle(request=request, trial_id=trial_id, reviewer_id=reviewer_id)


@router.post(
    "/api/internal/review/annotations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_access)],
)
def create_annotation(request: Request, annotation: FeedbackAnnotation) -> dict[str, object]:
    settings = get_web_settings(request)
    try:
        persist_feedback_annotation(
            ledger_root=settings.ledger_root,
            tasks_root=settings.tasks_root,
            feedback_root=settings.feedback_root,
            annotation=annotation,
        )
    except DuplicateFeedbackRecordError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ReviewAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return annotation.model_dump(mode="json")


@router.post(
    "/api/internal/review/calibration-results",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_access)],
)
def score_calibration(
    request: Request,
    submission: CalibrationRunRequest,
) -> dict[str, object]:
    settings = get_web_settings(request)
    reviewer = read_reviewer_profile(
        feedback_root=settings.feedback_root,
        reviewer_id=submission.reviewer_id,
    )
    if reviewer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reviewer not found")
    annotations = read_feedback_annotations(
        feedback_root=settings.feedback_root,
        reviewer_id=submission.reviewer_id,
    )
    result = score_reviewer_calibration(
        reviewer=reviewer,
        annotations=annotations,
        references={reference.trial_id: reference for reference in submission.references},
        calibration_version=submission.calibration_version,
    )
    updated_reviewer = apply_calibration_result(reviewer=reviewer, result=result)
    write_calibration_result(feedback_root=settings.feedback_root, result=result)
    write_reviewer_profile(feedback_root=settings.feedback_root, reviewer=updated_reviewer)
    return {
        "result": result.model_dump(mode="json"),
        "reviewer": updated_reviewer.model_dump(mode="json"),
    }


@router.post(
    "/api/internal/review/adjudications",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_access)],
)
def create_adjudication(
    request: Request,
    submission: AdjudicationSubmission,
) -> dict[str, object]:
    settings = get_web_settings(request)
    annotations = read_feedback_annotations(
        feedback_root=settings.feedback_root,
        trial_id=submission.trial_id,
    )
    if not annotations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="trial has no annotations",
        )
    if submission.decided_by is not None:
        reviewer = read_reviewer_profile(
            feedback_root=settings.feedback_root,
            reviewer_id=submission.decided_by,
        )
        if reviewer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reviewer not found")
    adjudication = adjudicate_trial_feedback(
        annotations=annotations,
        decision_id=submission.decision_id,
        final_judgment=submission.final_judgment,
        decided_by=submission.decided_by,
        rationale=submission.rationale,
        contested=submission.contested,
    )
    try:
        write_adjudication_record(feedback_root=settings.feedback_root, adjudication=adjudication)
        for item in generate_feedback_items(annotations=annotations, adjudication=adjudication):
            write_feedback_item(feedback_root=settings.feedback_root, item=item)
    except DuplicateFeedbackRecordError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return adjudication.model_dump(mode="json")


@router.get(
    "/api/review/queue",
    dependencies=[Depends(require_internal_access)],
)
def review_queue_api(request: Request, reviewer_id: str) -> ReviewQueueResponse:
    """Return the reviewer's assignment queue as JSON."""
    assignments = _build_assignment_payload(request=request, reviewer_id=reviewer_id)
    return ReviewQueueResponse(assignments=assignments)


@router.get(
    "/api/review/trial/{trial_id}",
    dependencies=[Depends(require_internal_access)],
)
def review_trial_api(request: Request, trial_id: str, reviewer_id: str) -> ReviewTrialResponse:
    """Return a review bundle for a single trial as JSON."""
    bundle = _build_review_bundle(request=request, trial_id=trial_id, reviewer_id=reviewer_id)
    return ReviewTrialResponse(bundle=bundle)


def _build_assignment_payload(*, request: Request, reviewer_id: str) -> dict[str, object]:
    settings = get_web_settings(request)
    try:
        snapshot = load_review_queue(
            ledger_root=settings.ledger_root,
            tasks_root=settings.tasks_root,
            feedback_root=settings.feedback_root,
            reviewer_id=reviewer_id,
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return snapshot.model_dump(mode="json")


def _build_review_bundle(*, request: Request, trial_id: str, reviewer_id: str) -> dict[str, object]:
    settings = get_web_settings(request)
    try:
        bundle = load_review_bundle(
            ledger_root=settings.ledger_root,
            tasks_root=settings.tasks_root,
            feedback_root=settings.feedback_root,
            reviewer_id=reviewer_id,
            trial_id=trial_id,
        )
    except ReviewAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return bundle.model_dump(mode="json")
