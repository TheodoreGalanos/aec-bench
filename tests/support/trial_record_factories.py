# ABOUTME: Shared test factories for building bound current TrialRecord instances.
# ABOUTME: Keeps shared run identity out of each trial payload while supporting concise test overrides.

from datetime import UTC, datetime, timedelta
from typing import Any

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    CostRecord,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    ProviderRoute,
    RunManifest,
    TaskReference,
    TimingRecord,
    TrialInput,
    TrialOutput,
    TrialRecord,
    UnresolvedSourceRef,
)


def make_trial_record(**overrides: Any) -> TrialRecord:
    """Build one bound trial record from concise current-contract inputs."""

    experiment_id = overrides.pop("experiment_id", "experiment-001")
    task = TaskReference.model_validate(
        overrides.pop(
            "task",
            {
                "task_id": "electrical/voltage-drop/au-office-fitout",
                "task_revision": "git-sha-task",
            },
        )
    )
    agent = AgentConfiguration.model_validate(
        overrides.pop(
            "agent",
            {
                "adapter": "tool_loop",
                "model": "anthropic:claude-sonnet-4-20250514",
                "adapter_revision": "git-sha-adapter",
                "configuration": {"max_turns": 20},
            },
        )
    )
    environment = ExecutionEnvironmentRef.model_validate(
        overrides.pop(
            "environment",
            {
                "runtime_image": "ghcr.io/example/task-image:latest",
                "compute_backend": "modal",
                "tool_versions": {"codes_search": "abc123"},
            },
        )
    )
    trial_input = TrialInput.model_validate(
        overrides.pop(
            "inputs",
            overrides.pop(
                "input",
                {
                    "instruction": "Review the task and write output.",
                    "task_revision": task.task_revision,
                    "visibility": task.visibility,
                    "system_prompt": "Use tools carefully.",
                },
            ),
        )
    )
    output_payload = overrides.pop(
        "outputs",
        overrides.pop(
            "output",
            {
                "agent_output": AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
                "raw_output_path": "/workspace/output.jsonl",
                "conversation_path": "/workspace/conversation.jsonl",
                "agent_result": {"completion_status": "completed"},
            },
        ),
    )
    output = None if output_payload is None else TrialOutput.model_validate(output_payload)
    started_at = _timestamp(overrides.pop("timestamp", overrides.pop("started_at", None)))
    timing = TimingRecord.model_validate(overrides.pop("timing", {"total_seconds": 12.0, "agent_seconds": 8.0}))
    evidence_status = overrides.pop("evidence_status", EvidenceStatus.NOT_REQUIRED)
    execution_status = overrides.pop("execution_status", ExecutionStatus.COMPLETED)
    evaluation = overrides.pop(
        "evaluation",
        EvaluationResult(
            reward=1.0,
            validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
        ),
    )
    evaluation_status = overrides.pop(
        "evaluation_status",
        EvaluationStatus.COMPLETED if evaluation is not None else EvaluationStatus.NOT_REQUESTED,
    )
    run_id = overrides.pop(
        "run_id",
        ":".join((experiment_id, agent.adapter, agent.model, environment.compute_backend)),
    )
    manifest = RunManifest(
        run_id=run_id,
        experiment_id=experiment_id,
        dataset=overrides.pop("dataset", None),
        source=overrides.pop("source", UnresolvedSourceRef(reason="test fixture has no published source")),
        agent=agent,
        execution_environment=environment,
        provider_route=overrides.pop("provider_route", ProviderRoute(provider="test", route="test")),
        expected_authorities=overrides.pop("expected_authorities", ()),
        evaluation_regime=overrides.pop("evaluation_regime", None),
        qualification=overrides.pop("qualification", None),
    )
    extensions = {
        kind: overrides.pop(kind)
        for kind in (
            "adaptation",
            "lifecycle_execution",
            "lifecycle_provenance",
            "meta_harness_provenance",
        )
        if kind in overrides
    }
    completed_at = overrides.pop(
        "completed_at",
        started_at + timedelta(seconds=timing.total_seconds)
        if execution_status
        in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED, ExecutionStatus.INVALID}
        else None,
    )
    record = TrialRecord(
        trial_id=overrides.pop("trial_id", "trial-001"),
        run_id=run_id,
        task_id=overrides.pop("task_id", task.task_id),
        attempt=overrides.pop("attempt", 1),
        execution_status=execution_status,
        evaluation_status=evaluation_status,
        evidence_status=evidence_status,
        started_at=started_at,
        completed_at=completed_at,
        input=trial_input,
        output=output,
        evaluation=evaluation,
        timing=timing,
        cost=overrides.pop("cost", CostRecord()),
        authority_evidence=overrides.pop("authority_evidence", ()),
        provider_evidence=overrides.pop("provider_evidence", None),
        extension_refs=overrides.pop("extension_refs", ()),
        **overrides,
    )
    for kind, value in extensions.items():
        record.attach_extension(kind, value)
    return record.bind_run_manifest(manifest)


def _timestamp(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime(2026, 3, 13, 10, 0, tzinfo=UTC)
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
