# ABOUTME: Tests ledger-backed aggregation for behavioral evaluation outputs in aec-bench Python.
# ABOUTME: Verifies classifier-injected aggregation without mixing provider calls into reports.

import json
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.trial_record import OutputRecord, TrialRecord
from aec_bench.evaluation.aggregation import summarize_behavioral_records
from aec_bench.evaluation.behavioral import (
    BehavioralTrace,
    BondType,
    ClassifiedTrace,
    TurnClassification,
)
from tests.support.trial_record_factories import make_trial_record


class StubClassifier:
    def classify_trace(self, trace: BehavioralTrace) -> ClassifiedTrace:
        classifications: list[TurnClassification] = []

        for turn in trace.turns:
            if turn.role != "assistant":
                continue
            content = turn.content.lower()
            if "verify" in content or "check" in content:
                bond_type = BondType.VERIFICATION
                confidence = 0.8
            elif "perhaps" in content or "consider" in content:
                bond_type = BondType.EXPLORATION
                confidence = 0.6
            else:
                bond_type = BondType.EXECUTION
                confidence = 0.9
            classifications.append(
                TurnClassification(
                    turn_index=turn.turn_index,
                    bond_type=bond_type,
                    confidence=confidence,
                    rationale=f"classified as {bond_type.value}",
                )
            )

        return ClassifiedTrace(
            trace_id=trace.trace_id,
            model_name=trace.model_name,
            classifications=tuple(classifications),
            metadata=dict(trace.metadata),
        )


def test_summarize_behavioral_records_aggregates_structural_metrics(tmp_path: Path) -> None:
    records = [
        _record_with_transcript(
            tmp_path,
            trial_id="trial-success",
            reward=1.0,
            assistant_messages=[
                "Run the calculation.",
                "Write the output.",
                "Verify the result.",
            ],
        ),
        _record_with_transcript(
            tmp_path,
            trial_id="trial-branchy",
            reward=0.5,
            assistant_messages=[
                "Perhaps compare another path.",
                "Consider a second option.",
                "Run the command.",
            ],
        ),
        make_trial_record(
            trial_id="trial-missing-trace",
            evaluation={
                "reward": 0.0,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
            },
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
                raw_output_path="/workspace/output.jsonl",
                conversation_path=None,
                agent_result={},
            ),
        ),
    ]

    summary = summarize_behavioral_records(records, classifier=StubClassifier())

    assert summary["n_trials"] == 3
    assert summary["trials_with_behavioral_trace"] == 2
    assert summary["classified_trials"] == 2
    assert summary["reference_trial_count"] == 1
    assert summary["mean_classified_turns"] == pytest.approx(3.0)
    assert summary["bond_distribution"] == {
        "execution": pytest.approx(0.5),
        "verification": pytest.approx(1.0 / 6.0),
        "deliberation": pytest.approx(0.0),
        "exploration": pytest.approx(1.0 / 3.0),
    }
    assert summary["dominant_bond_counts"] == {"execution": 1, "exploration": 1}
    confidence = cast(dict[str, Any], summary["confidence"])
    assert confidence["confidence_method"] == "behavioral-turn-classifier"
    assert confidence["evaluation_completeness"] == pytest.approx(2.0 / 3.0)
    assert confidence["mean_turn_confidence"] == pytest.approx(4.7 / 6.0)
    assert confidence["mean_trial_confidence"] == pytest.approx(4.7 / 6.0)
    assert confidence["low_confidence_turn_fraction"] == pytest.approx(2.0 / 6.0)
    assert confidence["low_confidence_trial_fraction"] == pytest.approx(0.5)
    mean_cosine_similarity = summary["mean_cosine_similarity"]
    mean_normalized_edit_distance = summary["mean_normalized_edit_distance"]
    assert isinstance(mean_cosine_similarity, float)
    assert isinstance(mean_normalized_edit_distance, float)
    assert mean_cosine_similarity < 1.0
    assert mean_cosine_similarity > 0.0
    assert mean_normalized_edit_distance > 0.0
    trials = cast(list[dict[str, Any]], summary["trials"])
    assert trials[0]["mean_turn_confidence"] == pytest.approx((0.9 + 0.9 + 0.8) / 3.0)
    assert trials[1]["mean_turn_confidence"] == pytest.approx((0.6 + 0.6 + 0.9) / 3.0)


def _record_with_transcript(
    tmp_path: Path,
    *,
    trial_id: str,
    reward: float,
    assistant_messages: list[str],
) -> TrialRecord:
    conversation_path = tmp_path / f"{trial_id}.jsonl"
    entries = [
        {"role": "user", "content": "Solve the task.", "event": "message"},
        *[{"role": "assistant", "content": message, "event": "message"} for message in assistant_messages],
    ]
    conversation_path.write_text(
        "\n".join(json.dumps(entry) for entry in entries),
        encoding="utf-8",
    )
    return make_trial_record(
        trial_id=trial_id,
        evaluation={
            "reward": reward,
            "validity": {
                "output_parseable": True,
                "schema_valid": True,
                "verifier_completed": True,
            },
        },
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
            raw_output_path="/workspace/output.jsonl",
            conversation_path=conversation_path.as_posix(),
            agent_result={},
        ),
    )
