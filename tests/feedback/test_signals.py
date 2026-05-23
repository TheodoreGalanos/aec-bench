# ABOUTME: Tests structured feedback signal generation from human annotations.
# ABOUTME: Verifies confidence summaries and generated improvement items remain deterministic.

from aec_bench.contracts.evaluation_result import Judgment
from aec_bench.feedback.signals import build_feedback_confidence, generate_feedback_items
from tests.support.feedback_factories import make_adjudication_record, make_feedback_annotation


def test_generate_feedback_items_and_confidence_summary() -> None:
    annotations = [
        make_feedback_annotation(
            annotation_id="annotation-1",
            judgment=Judgment.PASS,
            categories=["verifier.output", "instruction.clarity"],
        ),
        make_feedback_annotation(
            annotation_id="annotation-2",
            reviewer_id="reviewer-002",
            judgment=Judgment.FAIL,
            categories=["rubric.edge-case"],
        ),
    ]
    adjudication = make_adjudication_record(
        status="adjudicated",
        final_judgment=Judgment.FAIL,
        decided_by="reviewer-senior",
        source_annotation_ids=["annotation-1", "annotation-2"],
    )

    items = generate_feedback_items(annotations=annotations, adjudication=adjudication)
    confidence = build_feedback_confidence(annotations=annotations, adjudication=adjudication)

    assert [item.item_type for item in items] == [
        "instruction_revision",
        "rubric_update",
        "verifier_fix",
    ]
    assert confidence.annotator_count == 2
    assert confidence.inter_rater_agreement == 0.5
    assert confidence.confidence_method == "adjudicated_human_review"
