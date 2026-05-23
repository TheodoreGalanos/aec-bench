# ABOUTME: Harness helpers for constructing TrialRecord objects in aec-bench Python.
# ABOUTME: Converts task, adapter, and evaluation artifacts into append-only provenance records.

from datetime import UTC, datetime

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
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


def build_trial_record(
    *,
    trial_id: str,
    experiment_id: str,
    task: TaskDefinition,
    task_revision: str,
    request: AdapterRequest,
    result: AdapterResult,
    evaluation: EvaluationResult,
    total_seconds: float,
    runtime_image: str,
    compute_backend: str,
    adapter_revision: str | None = None,
    input_files: list[FileReference] | None = None,
    tool_versions: dict[str, str] | None = None,
    raw_output_path: str | None = None,
    conversation_path: str | None = None,
    trajectory_path: str | None = None,
    timestamp: datetime | None = None,
    adaptation: AdaptationProvenance | None = None,
    completeness: Completeness = Completeness.PARTIAL,
) -> TrialRecord:
    return TrialRecord(
        trial_id=trial_id,
        experiment_id=experiment_id,
        timestamp=timestamp or datetime.now(UTC),
        task=TaskReference(task_id=task.task_id, task_revision=task_revision),
        agent=AgentReference(
            adapter=result.adapter_name,
            model=result.resolved_model,
            adapter_revision=adapter_revision,
            configuration=result.configuration_record,
        ),
        environment=EnvironmentSnapshot(
            runtime_image=runtime_image,
            compute_backend=compute_backend,
            tool_versions=tool_versions,
        ),
        inputs=InputRecord(
            instruction=request.instruction,
            system_prompt=request.system_prompt,
            input_files=input_files,
        ),
        outputs=OutputRecord(
            agent_output=result.agent_output,
            raw_output_path=raw_output_path or result.agent_output.output_path,
            conversation_path=conversation_path,
            trajectory_path=trajectory_path,
            agent_result={
                "failure_kind": (result.failure_kind.value if result.failure_kind is not None else None),
                "provider_error": result.provider_error,
                "usage_input_tokens": result.usage_input_tokens,
                "usage_output_tokens": result.usage_output_tokens,
            },
        ),
        evaluation=evaluation,
        timing=TimingRecord(total_seconds=total_seconds),
        adaptation=adaptation,
        completeness=completeness,
    )
