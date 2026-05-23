# ABOUTME: Tests ledger-backed experiment reporting derived from imported TrialRecords.
# ABOUTME: Verifies task grouping, token accounting, and cost reconstruction.

import json
from pathlib import Path

import pytest

from aec_bench.communication.job_report import (
    build_experiment_report,
    experiment_report_to_dict,
    trial_report_from_record,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.trial_record import OutputRecord
from aec_bench.evaluation.behavioral import (
    BehavioralTrace,
    BondType,
    ClassifiedTrace,
    TurnClassification,
)
from aec_bench.harness.harbor_import import import_harbor_job, import_harbor_trial
from tests.support.trial_record_factories import make_trial_record

REPO_ROOT = Path(__file__).resolve().parents[2]
HARBOR_JOB_DIR = REPO_ROOT / "jobs" / "2026-03-04__17-57-43"
HARBOR_TRIAL_DIR = HARBOR_JOB_DIR / "brisbane-8rm__BHVuXg2"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_JOB_DIR.exists(),
    reason="requires archived Harbor job data in jobs/",
)


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


@_skip_no_job_data
def test_trial_report_from_record_preserves_task_and_cost_details() -> None:
    record = import_harbor_trial(trial_dir=HARBOR_TRIAL_DIR, repo_root=REPO_ROOT)

    report = trial_report_from_record(record)

    assert report.trial_name == "brisbane-8rm__BHVuXg2"
    assert report.task_name == "brisbane-8rm"
    assert report.task_type == "audit-office-building"
    assert report.tokens.cache_write_tokens == 14707
    assert report.turns_used == 8
    assert report.cost_usd == pytest.approx(0.25379475)
    assert report.has_error is False


@_skip_no_job_data
def test_build_experiment_report_groups_real_job_by_task_type() -> None:
    records = import_harbor_job(job_dir=HARBOR_JOB_DIR, repo_root=REPO_ROOT)

    report = build_experiment_report(records)

    assert report.experiment_id == "6834bc30-3801-4a45-a114-afb2d3764b7d"
    assert report.agent_name == "tool-loop-sonnet-45"
    assert report.model_name == "claude-sonnet-4-6"
    assert len(report.trials) == 60
    assert set(report.by_task_type) == {"audit-mixed-use", "audit-office-building"}
    assert sum(summary.n_trials for summary in report.by_task_type.values()) == 60
    assert report.total_cost_usd > 0.0
    assert report.overall_mean_reward > 0.0


def test_build_experiment_report_optionally_includes_behavioral_json_fields(
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

    report = build_experiment_report(records, behavioral_classifier=StubClassifier())
    payload = experiment_report_to_dict(report)

    assert payload["behavioral"]["classified_trials"] == 1
    assert payload["behavioral"]["confidence"]["confidence_method"] == "behavioral-turn-classifier"
    assert payload["trials"][0]["classified_turns"] == 2
    assert payload["trials"][0]["dominant_bond"] == "execution"
    assert payload["trials"][0]["mean_turn_confidence"] == pytest.approx(0.85)
