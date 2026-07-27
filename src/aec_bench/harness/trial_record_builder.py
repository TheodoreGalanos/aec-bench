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
        task=TaskReference(
            task_id=task.task_id,
            task_revision=task_revision,
            visibility=task.visibility,
        ),
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
                "completion_reason": (result.completion_reason.value if result.completion_reason is not None else None),
                "completion_assistance": (
                    {
                        "contract_satisfied": result.completion_assistance.contract_satisfied,
                        "reminder_sent": result.completion_assistance.reminder_sent,
                        "reminder_turn": result.completion_assistance.reminder_turn,
                        "explicit_final_turn": result.completion_assistance.explicit_final_turn,
                    }
                    if result.completion_assistance is not None
                    else None
                ),
                "completion_commit": (
                    result.completion_commit.model_dump(mode="json") if result.completion_commit is not None else None
                ),
                "failure_kind": (result.failure_kind.value if result.failure_kind is not None else None),
                "provider_error": result.provider_error,
                **({"usage_model_calls": result.usage_model_calls} if result.usage_model_calls is not None else {}),
                "usage_input_tokens": result.usage_input_tokens,
                "usage_output_tokens": result.usage_output_tokens,
            },
        ),
        evaluation=evaluation,
        timing=TimingRecord(total_seconds=total_seconds),
        adaptation=adaptation,
        completeness=completeness,
    )
