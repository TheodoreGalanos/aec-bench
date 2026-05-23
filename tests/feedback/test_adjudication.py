# ABOUTME: Tests disagreement handling for feedback annotations in aec-bench.
# ABOUTME: Verifies agreement, escalation, and final adjudication stay structurally explicit.

from aec_bench.contracts.evaluation_result import Judgment
from aec_bench.feedback.adjudication import adjudicate_trial_feedback
from aec_bench.feedback.models import AdjudicationStatus
from tests.support.feedback_factories import make_feedback_annotation


def test_adjudicate_trial_feedback_marks_consensus_without_senior_reviewer() -> None:
    annotations = [
        make_feedback_annotation(annotation_id="annotation-1", judgment=Judgment.FAIL),
        make_feedback_annotation(
            annotation_id="annotation-2",
            reviewer_id="reviewer-002",
            judgment=Judgment.FAIL,
        ),
    ]

    decision = adjudicate_trial_feedback(annotations=annotations)

    assert decision.status == AdjudicationStatus.AGREED
    assert decision.final_judgment == Judgment.FAIL
    assert decision.decided_by is None


def test_adjudicate_trial_feedback_requires_explicit_resolution_for_disagreement() -> None:
    annotations = [
        make_feedback_annotation(annotation_id="annotation-1", judgment=Judgment.PASS),
        make_feedback_annotation(
            annotation_id="annotation-2",
            reviewer_id="reviewer-002",
            judgment=Judgment.FAIL,
        ),
    ]

    pending = adjudicate_trial_feedback(annotations=annotations)
    resolved = adjudicate_trial_feedback(
        annotations=annotations,
        decision_id="decision-resolved",
        final_judgment=Judgment.FAIL,
        decided_by="reviewer-senior",
        rationale="Failure judgment is better supported by the transcript.",
    )

    assert pending.status == AdjudicationStatus.NEEDS_ADJUDICATION
    assert pending.final_judgment is None
    assert resolved.status == AdjudicationStatus.ADJUDICATED
    assert resolved.final_judgment == Judgment.FAIL
    assert resolved.decided_by == "reviewer-senior"
