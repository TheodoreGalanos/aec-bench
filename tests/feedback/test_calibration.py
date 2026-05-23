# ABOUTME: Tests reviewer calibration scoring in the feedback domain.
# ABOUTME: Verifies agreement scoring and reviewer-state updates stay explicit and bounded.

from aec_bench.contracts.evaluation_result import Judgment
from aec_bench.feedback.calibration import apply_calibration_result, score_reviewer_calibration
from aec_bench.feedback.models import CalibrationReference, CalibrationStatus
from tests.support.feedback_factories import make_feedback_annotation, make_reviewer_profile


def test_score_reviewer_calibration_and_update_reviewer_state() -> None:
    reviewer = make_reviewer_profile(reviewer_id="reviewer-cal")
    annotations = [
        make_feedback_annotation(
            annotation_id="annotation-cal-1",
            trial_id="trial-cal-1",
            reviewer_id="reviewer-cal",
            judgment=Judgment.PASS,
            is_calibration=True,
            calibration_version="v1",
        ),
        make_feedback_annotation(
            annotation_id="annotation-cal-2",
            trial_id="trial-cal-2",
            reviewer_id="reviewer-cal",
            judgment=Judgment.FAIL,
            is_calibration=True,
            calibration_version="v1",
        ),
    ]
    references = {
        "trial-cal-1": CalibrationReference(
            trial_id="trial-cal-1",
            reference_judgment=Judgment.PASS,
            reference_categories=["verifier.output"],
            calibration_version="v1",
        ),
        "trial-cal-2": CalibrationReference(
            trial_id="trial-cal-2",
            reference_judgment=Judgment.FAIL,
            reference_categories=["instruction.clarity"],
            calibration_version="v1",
        ),
    }

    result = score_reviewer_calibration(
        reviewer=reviewer,
        annotations=annotations,
        references=references,
        calibration_version="v1",
    )
    updated = apply_calibration_result(reviewer=reviewer, result=result)

    assert result.total_cases == 2
    assert result.agreement_rate == 1.0
    assert result.passed is True
    assert updated.calibration_status == CalibrationStatus.CALIBRATED
    assert updated.calibration_version == "v1"
    assert updated.weighting.calibration_score == 1.0
