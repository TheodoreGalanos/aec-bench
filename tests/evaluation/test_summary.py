# ABOUTME: Tests for ledger-based evaluation summary helpers in the Python evaluation package.
# ABOUTME: Verifies aggregate reward, grouping behavior, and optional behavioral enrichment.

import json
from pathlib import Path

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.trial_record import OutputRecord
from aec_bench.evaluation.behavioral import (
    BehavioralTrace,
    BondType,
    ClassifiedTrace,
    TurnClassification,
)
from aec_bench.evaluation.pipeline import summarize_evaluation_records
from tests.support.trial_record_factories import make_trial_record


class StubClassifier:
    def classify_trace(self, trace: BehavioralTrace) -> ClassifiedTrace:
        classifications: list[TurnClassification] = []

        for turn in trace.turns:
            if turn.role != "assistant":
                continue
            content = turn.content.lower()
            bond_type = BondType.VERIFICATION if "verify" in content else BondType.EXECUTION
            classifications.append(
                TurnClassification(
                    turn_index=turn.turn_index,
                    bond_type=bond_type,
                    confidence=0.9,
                )
            )

        return ClassifiedTrace(
            trace_id=trace.trace_id,
            model_name=trace.model_name,
            classifications=tuple(classifications),
            metadata=dict(trace.metadata),
        )


def test_summarize_evaluation_records_computes_overall_and_grouped_metrics() -> None:
    records = [
        make_trial_record(trial_id="trial-001"),
        make_trial_record(
            trial_id="trial-002",
            task={
                "task_id": "mechanical/heat-load/demo-instance",
                "task_revision": "git-sha-task",
            },
            evaluation={
                "reward": 0.5,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
            },
        ),
    ]

    summary = summarize_evaluation_records(records)

    assert summary["n_trials"] == 2
    assert summary["mean_reward"] == pytest.approx(0.75)
    assert summary["by_adapter"]["tool_loop"]["n_trials"] == 2
    assert summary["by_task_prefix"]["electrical"]["mean_reward"] == pytest.approx(1.0)
    assert summary["by_task_prefix"]["mechanical"]["mean_reward"] == pytest.approx(0.5)


def test_summarize_evaluation_records_includes_behavioral_block_when_classifier_is_supplied(
    tmp_path: Path,
) -> None:
    conversation_path = tmp_path / "conversation.jsonl"
    conversation_path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "Solve the task.", "event": "message"}),
                json.dumps({"role": "assistant", "content": "Run the tool.", "event": "message"}),
                json.dumps({"role": "assistant", "content": "Verify the result.", "event": "message"}),
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

    summary = summarize_evaluation_records(records, behavioral_classifier=StubClassifier())

    assert "behavioral" in summary
    assert summary["behavioral"]["trials_with_behavioral_trace"] == 1
    assert summary["behavioral"]["bond_distribution"]["execution"] == pytest.approx(0.5)
    assert summary["behavioral"]["bond_distribution"]["verification"] == pytest.approx(0.5)
    assert summary["behavioral"]["confidence"]["confidence_method"] == "behavioral-turn-classifier"
    assert summary["behavioral"]["confidence"]["evaluation_completeness"] == pytest.approx(1.0)
