# ABOUTME: Tests append-only feedback persistence and evaluation-facing handoff logic.
# ABOUTME: Verifies annotations remain durable while confidence summaries stay deterministic.

from pathlib import Path

from aec_bench.feedback.adjudication import adjudicate_trial_feedback
from aec_bench.feedback.annotation_consumer import (
    build_evaluation_feedback_handoff,
    read_feedback_annotations,
    read_feedback_items,
    read_latest_adjudication,
    read_reviewer_profile,
    write_adjudication_record,
    write_feedback_annotation,
    write_feedback_item,
    write_reviewer_profile,
)
from aec_bench.feedback.signals import generate_feedback_items
from tests.support.feedback_factories import make_feedback_annotation, make_reviewer_profile


def test_feedback_records_persist_and_build_evaluation_handoff(tmp_path: Path) -> None:
    feedback_root = tmp_path / "feedback"
    reviewer = make_reviewer_profile(reviewer_id="reviewer-001")
    annotations = [
        make_feedback_annotation(annotation_id="annotation-1", judgment="pass"),
        make_feedback_annotation(
            annotation_id="annotation-2",
            reviewer_id="reviewer-002",
            reviewer_discipline="mechanical",
            judgment="fail",
            categories=["instruction.clarity"],
        ),
    ]
    adjudication = adjudicate_trial_feedback(
        annotations=annotations,
        decision_id="decision-1",
        final_judgment="fail",
        decided_by="reviewer-senior",
        rationale="Instruction ambiguity should count against the output.",
    )
    items = generate_feedback_items(annotations=annotations, adjudication=adjudication)

    write_reviewer_profile(feedback_root=feedback_root, reviewer=reviewer)
    for annotation in annotations:
        write_feedback_annotation(feedback_root=feedback_root, annotation=annotation)
    write_adjudication_record(feedback_root=feedback_root, adjudication=adjudication)
    for item in items:
        write_feedback_item(feedback_root=feedback_root, item=item)

    persisted_annotations = read_feedback_annotations(
        feedback_root=feedback_root,
        trial_id="trial-001",
    )
    handoff = build_evaluation_feedback_handoff(
        annotations=persisted_annotations,
        adjudication=read_latest_adjudication(feedback_root=feedback_root, trial_id="trial-001"),
    )

    assert (
        read_reviewer_profile(
            feedback_root=feedback_root,
            reviewer_id="reviewer-001",
        )
        == reviewer
    )
    assert len(persisted_annotations) == 2
    assert len(read_feedback_items(feedback_root=feedback_root, trial_id="trial-001")) == 2
    assert handoff.confidence.annotator_count == 2
    assert handoff.confidence.inter_rater_agreement == 0.5
    assert handoff.adjudication is not None
    assert handoff.adjudication.final_judgment == "fail"
