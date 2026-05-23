# ABOUTME: Calibration helpers for reviewer quality control in the feedback domain.
# ABOUTME: Scores reviewer agreement against governed references and updates reviewer state.

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from aec_bench.feedback.models import (
    CalibrationReference,
    CalibrationStatus,
    FeedbackAnnotation,
    ReviewerCalibrationResult,
    ReviewerProfile,
)


def score_reviewer_calibration(
    *,
    reviewer: ReviewerProfile,
    annotations: Sequence[FeedbackAnnotation],
    references: Mapping[str, CalibrationReference],
    calibration_version: str,
    pass_threshold: float = 0.8,
) -> ReviewerCalibrationResult:
    calibration_annotations = [
        annotation
        for annotation in annotations
        if annotation.reviewer_id == reviewer.reviewer_id
        and annotation.is_calibration
        and annotation.calibration_version == calibration_version
        and annotation.trial_id in references
    ]
    matches = sum(
        1
        for annotation in calibration_annotations
        if annotation.judgment == references[annotation.trial_id].reference_judgment
    )
    total_cases = len(calibration_annotations)
    agreement_rate = matches / total_cases if total_cases else 0.0
    return ReviewerCalibrationResult(
        reviewer_id=reviewer.reviewer_id,
        reviewer_discipline=reviewer.discipline,
        calibration_version=calibration_version,
        total_cases=total_cases,
        agreement_rate=agreement_rate,
        passed=total_cases > 0 and agreement_rate >= pass_threshold,
        scored_at=datetime.now(UTC),
    )


def apply_calibration_result(
    *,
    reviewer: ReviewerProfile,
    result: ReviewerCalibrationResult,
) -> ReviewerProfile:
    calibration_status = CalibrationStatus.CALIBRATED if result.passed else CalibrationStatus.PROVISIONAL
    return reviewer.model_copy(
        update={
            "calibration_status": calibration_status,
            "calibration_version": result.calibration_version,
            "updated_at": result.scored_at,
            "weighting": reviewer.weighting.model_copy(update={"calibration_score": result.agreement_rate}),
        }
    )
