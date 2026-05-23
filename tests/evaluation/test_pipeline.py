# ABOUTME: Tests the evaluation pipeline coordinator over imported TrialRecords.
# ABOUTME: Verifies stable summary output and explicit automated-judgment readiness policy.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import ConfidenceMetadata
from aec_bench.contracts.trial_record import OutputRecord
from aec_bench.evaluation.behavioral import (
    BehavioralTrace,
    BondType,
    ClassifiedTrace,
    TurnClassification,
)
from aec_bench.evaluation.pipeline import (
    assess_automated_judgment_readiness,
    summarize_evaluation_records,
)
from tests.support.trial_record_factories import make_trial_record


class StubClassifier:
    def classify_trace(self, trace: BehavioralTrace) -> ClassifiedTrace:
        classifications = tuple(
            TurnClassification(
                turn_index=turn.turn_index,
                bond_type=(BondType.VERIFICATION if "verify" in turn.content.lower() else BondType.EXECUTION),
                confidence=0.8 if "verify" in turn.content.lower() else 0.9,
            )
            for turn in trace.turns
            if turn.role == "assistant"
        )
        return ClassifiedTrace(
            trace_id=trace.trace_id,
            model_name=trace.model_name,
            classifications=classifications,
            metadata=dict(trace.metadata),
        )


def test_assess_automated_judgment_readiness_reports_blocking_reasons() -> None:
    readiness = assess_automated_judgment_readiness(
        confidence=ConfidenceMetadata(
            annotator_count=1,
            inter_rater_agreement=0.6,
            confidence_interval=(0.45, 0.85),
            confidence_method="human-review",
        ),
        calibration_sample_size=6,
        calibration_agreement=0.7,
    )

    assert readiness.ready is False
    assert "annotator_count_below_threshold" in readiness.reasons
    assert "inter_rater_agreement_below_threshold" in readiness.reasons
    assert "calibration_sample_size_below_threshold" in readiness.reasons
    assert "calibration_agreement_below_threshold" in readiness.reasons
    assert "confidence_interval_too_wide" in readiness.reasons


def test_summarize_evaluation_records_includes_behavioral_and_judge_readiness(
    tmp_path: Path,
) -> None:
    conversation_path = tmp_path / "conversation.jsonl"
    conversation_path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "Solve the task.", "event": "message"}),
                json.dumps({"role": "assistant", "content": "Run the tool.", "event": "message"}),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": "Verify the result.",
                        "event": "message",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    records = [
        make_trial_record(
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
                raw_output_path="/workspace/output.jsonl",
                conversation_path=conversation_path.as_posix(),
                agent_result={},
            )
        )
    ]

    summary = summarize_evaluation_records(
        records,
        behavioral_classifier=StubClassifier(),
        automated_judgment_confidence=ConfidenceMetadata(
            annotator_count=3,
            inter_rater_agreement=0.92,
            confidence_interval=(0.86, 0.96),
            confidence_method="human-review",
        ),
        calibration_sample_size=24,
        calibration_agreement=0.88,
    )

    assert summary["n_trials"] == 1
    assert summary["trace"]["trials_with_transcript"] == 1
    assert summary["behavioral"]["classified_trials"] == 1
    assert summary["automated_judgment"]["ready"] is True
    assert summary["automated_judgment"]["reasons"] == []
    assert summary["automated_judgment"]["calibration_sample_size"] == 24
    assert summary["automated_judgment"]["calibration_agreement"] == pytest.approx(0.88)
