# ABOUTME: Builds schema-2 trial records and their shared run manifests from adapter results.
# ABOUTME: Keeps provider evidence and optional forensic files as pending exact artifacts for the ledger writer.

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority_evidence import AuthorityEvidenceRef
from aec_bench.contracts.dataset import DatasetRef
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    AuthorityExpectation,
    CostRecord,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    FileReference,
    ProviderRoute,
    QualificationRequirement,
    RunManifest,
    SourceRef,
    TimingRecord,
    TrialInput,
    TrialOutput,
    TrialRecord,
    TrialTaskKind,
    UnresolvedSourceRef,
)

_NON_CONFIGURATION_FIELDS = frozenset(
    {
        "actor_invocation_authority",
        "child_session_ids",
        "commit_evidence_path",
        "composition_path",
        "cordis_path",
        "evidence_manifest_sha256",
        "provider_evidence_manifest",
        "manifest_path",
        "notifications_path",
        "optional_plugins",
        "root_events_path",
        "root_session_id",
        "root_steps",
        "root_turns",
        "runtime_distribution_version",
        "runtime_execution_attestation",
        "runtime_reported_version",
        "sdk_version",
        "sessions_path",
        "stderr_path",
        "system_prompt_path",
        "tool_calls_completed",
        "tool_calls_started",
        "tool_gateway_close",
        "tool_gateway_evidence_path",
        "unknown_event_types",
    }
)


def portable_agent_configuration(configuration: dict[str, object]) -> dict[str, object]:
    """Keep outcome-affecting adapter settings out of provider evidence and host paths."""

    return {key: value for key, value in configuration.items() if key not in _NON_CONFIGURATION_FIELDS}


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
    run_id: str | None = None,
    dataset: DatasetRef | None = None,
    source: SourceRef | None = None,
    provider_route: ProviderRoute | None = None,
    expected_authorities: tuple[AuthorityExpectation, ...] = (),
    qualification: QualificationRequirement | None = None,
    authority_evidence: tuple[AuthorityEvidenceRef, ...] = (),
    task_kind: TrialTaskKind = "artifact",
    attempt: int = 1,
    extensions: dict[str, BaseModel] | None = None,
) -> TrialRecord:
    stop_reason = result.stop_reason or result.failure_kind
    final_reason = result.completion_reason or stop_reason
    started_at = timestamp or datetime.now(UTC)
    execution_status = (
        ExecutionStatus.COMPLETED
        if result.agent_output.status is AgentOutputStatus.COMPLETED
        else ExecutionStatus.FAILED
    )
    selected_run_id = run_id or ":".join((experiment_id, result.adapter_name, result.resolved_model, compute_backend))
    manifest = RunManifest(
        run_id=selected_run_id,
        experiment_id=experiment_id,
        dataset=dataset,
        source=source or UnresolvedSourceRef(reason="source identity was not supplied to the trial builder"),
        agent=AgentConfiguration(
            adapter=result.adapter_name,
            model=result.resolved_model,
            adapter_revision=adapter_revision,
            configuration=portable_agent_configuration(result.configuration_record),
        ),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=runtime_image,
            compute_backend=compute_backend,
            tool_versions=tool_versions,
        ),
        provider_route=provider_route or _provider_route(result),
        expected_authorities=expected_authorities,
        qualification=qualification,
    )
    record = TrialRecord(
        trial_id=trial_id,
        run_id=selected_run_id,
        task_id=task.task_id,
        attempt=attempt,
        execution_status=execution_status,
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=(EvidenceStatus.PENDING if expected_authorities else EvidenceStatus.NOT_REQUIRED),
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=total_seconds),
        input=TrialInput(
            instruction=request.instruction,
            task_revision=task_revision,
            task_kind=task_kind,
            visibility=task.visibility,
            system_prompt=request.system_prompt,
            input_files=None if input_files is None else tuple(input_files),
        ),
        output=TrialOutput(
            agent_output=result.agent_output,
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
            },
            terminated=result.agent_output.status.value == "completed" and stop_reason is None,
            truncated=stop_reason is not None,
            final_reason=None if final_reason is None else final_reason.value,
        ).bind_runtime_paths(
            raw_output_path=raw_output_path or result.agent_output.output_path,
            conversation_path=conversation_path,
            trajectory_path=trajectory_path,
        ),
        evaluation=evaluation,
        timing=TimingRecord(total_seconds=total_seconds),
        cost=CostRecord(
            model_calls=result.usage_model_calls,
            tokens_in=result.usage_input_tokens,
            tokens_out=result.usage_output_tokens,
            cache_read_tokens=result.usage_cache_read_tokens,
            cache_write_tokens=result.usage_cache_write_tokens,
            advisor_calls=result.usage_advisor_calls,
            advisor_input_tokens=result.usage_advisor_input_tokens,
            advisor_output_tokens=result.usage_advisor_output_tokens,
        ),
        authority_evidence=authority_evidence,
    )
    for kind, extension in sorted((extensions or {}).items()):
        record.attach_extension(kind, extension)
    _attach_existing_file(record, "raw_output", raw_output_path or result.agent_output.output_path, "text/plain")
    _attach_existing_file(record, "conversation", conversation_path, "application/x-ndjson")
    _attach_existing_file(record, "trajectory", trajectory_path, "application/x-ndjson")
    manifest_path = result.configuration_record.get("manifest_path")
    if isinstance(manifest_path, str):
        _validate_provider_evidence_manifest(result.configuration_record, Path(manifest_path))
        _attach_existing_file(record, "provider_evidence", manifest_path, "application/json")
    return record.bind_run_manifest(manifest)


def _provider_route(result: AdapterResult) -> ProviderRoute:
    configuration = result.configuration_record
    provider = configuration.get("provider") or configuration.get("provider_name") or result.adapter_name
    route = configuration.get("provider_route") or configuration.get("route") or result.adapter_name
    return ProviderRoute(provider=str(provider), route=str(route))


def _attach_existing_file(record: TrialRecord, role: str, value: str | None, media_type: str) -> None:
    if value is None:
        return
    path = Path(value)
    if path.is_file():
        record.attach_artifact(role, path, media_type=media_type)


def _validate_provider_evidence_manifest(configuration: dict[str, object], path: Path) -> None:
    reference_payload = configuration.get("provider_evidence_manifest")
    if reference_payload is None or not path.is_file():
        return
    reference = ArtifactRef.model_validate(reference_payload)
    content = path.read_bytes()
    if len(content) != reference.size_bytes or hashlib.sha256(content).hexdigest() != reference.sha256:
        raise ValueError("provider evidence manifest does not match its ArtifactRef")
