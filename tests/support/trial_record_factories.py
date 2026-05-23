# ABOUTME: Shared test factories for building valid TrialRecord instances in aec-bench tests.
# ABOUTME: Keeps ledger and importer tests focused on behavior over repeated provenance setup.

from typing import Any

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import (
    AgentReference,
    Completeness,
    EnvironmentSnapshot,
    FileReference,
    InputRecord,
    OutputRecord,
    TaskReference,
    TimingRecord,
    TrialRecord,
)


def make_trial_record(**overrides: Any) -> TrialRecord:
    payload = {
        "trial_id": "trial-001",
        "experiment_id": "experiment-001",
        "timestamp": "2026-03-13T10:00:00Z",
        "task": TaskReference(
            task_id="electrical/voltage-drop/au-office-fitout",
            task_revision="git-sha-task",
        ),
        "agent": AgentReference(
            adapter="tool_loop",
            model="anthropic:claude-sonnet-4-20250514",
            adapter_revision="git-sha-adapter",
            configuration={"max_turns": 20},
        ),
        "environment": EnvironmentSnapshot(
            runtime_image="ghcr.io/example/task-image:latest",
            compute_backend="modal",
            tool_versions={"codes_search": "abc123"},
        ),
        "inputs": InputRecord(
            instruction="Review the task and write output.",
            system_prompt="Use tools carefully.",
            input_files=[
                FileReference(
                    path="/workspace/input/drawing.json",
                    hash="hash-123",
                    source="r2://bucket/drawing.json",
                )
            ],
        ),
        "outputs": OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
            raw_output_path="/workspace/output.jsonl",
            conversation_path="/workspace/conversation.jsonl",
            agent_result={"completion_status": "completed"},
        ),
        "evaluation": EvaluationResult(
            reward=1.0,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
        "timing": TimingRecord(total_seconds=12.0, agent_seconds=8.0),
        "completeness": Completeness.COMPLETE,
    }
    payload.update(overrides)
    return TrialRecord.model_validate(payload)
