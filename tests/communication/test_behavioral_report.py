# ABOUTME: Tests dedicated behavioral export records built from ledger-backed TrialRecords.
# ABOUTME: Verifies per-trial flattening and summary attachment for downstream analysis.

import json
from pathlib import Path

import pytest

from aec_bench.communication.behavioral_report import (
    build_behavioral_export,
    export_behavioral_report_json,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.trial_record import OutputRecord
from aec_bench.evaluation.behavioral import (
    BehavioralTrace,
    BondType,
    ClassifiedTrace,
    TurnClassification,
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


def test_build_behavioral_export_includes_summary_and_flattened_trials(tmp_path: Path) -> None:
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

    export_payload = build_behavioral_export(records, classifier=StubClassifier())
    output_path = export_behavioral_report_json(export_payload, tmp_path / "behavioral.json")
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert written["summary"]["classified_trials"] == 1
    assert written["summary"]["confidence"]["confidence_method"] == "behavioral-turn-classifier"
    assert len(written["trials"]) == 1
    assert written["trials"][0]["trial_id"] == "trial-001"
    assert written["trials"][0]["task_id"] == "electrical/voltage-drop/au-office-fitout"
    assert written["trials"][0]["dominant_bond"] == "execution"
    assert written["trials"][0]["mean_turn_confidence"] == pytest.approx(0.85)
