# ABOUTME: Imports canonical Harbor trial artifacts into generic TrialRecord contracts.
# ABOUTME: Delegates execution-specific evidence policy through the selected extension boundary.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from aec_bench.adapters.base import AdapterResult
from aec_bench.contracts.agent_output import (
    AgentOutput,
    AgentOutputStatus,
)
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.trial_record import (
    AgentReference,
    Completeness,
    CostRecord,
    EnvironmentSnapshot,
    FileReference,
    InputRecord,
    OutputRecord,
    TaskReference,
    TimingRecord,
    TrialRecord,
)
from aec_bench.contracts.validators import (
    infer_output_format,
    normalize_workspace_path,
)
from aec_bench.harness.execution_payload import read_execution_result
from aec_bench.harness.harbor_contract import (
    HarborArtifactContractError,
    HarborEnvironmentConfig,
    HarborTrialResult,
    read_harbor_trial_result,
)
from aec_bench.harness.harbor_dispatch import (
    MORPH_BACKEND,
    MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
)
from aec_bench.harness.harbor_importing.artifact_io import (
    normalize_artifact_path,
)
from aec_bench.harness.harbor_importing.contracts import (
    HarborImportError,
    ImportedExecutionEvidence,
    ImportEvidenceContext,
    ImportEvidenceIntent,
)
from aec_bench.harness.harbor_importing.output_commit import (
    verify_output_commit,
)
from aec_bench.harness.harbor_importing.registry import (
    load_import_evidence,
)
from aec_bench.harness.verifier_artifacts import (
    read_verifier_artifacts,
)
from aec_bench.tasks.loader import load_task_definition


@dataclass(frozen=True)
class _CollectedTrialArtifacts:
    output_path: Path | None
    conversation_path: Path | None
    trajectory_path: Path | None
    agent_result_path: Path | None
    reward_path: Path | None
    details_path: Path | None


@dataclass(frozen=True)
class _UsageEvidence:
    model_calls: int | None
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    advisor_calls: int | None
    advisor_input_tokens: int | None
    advisor_output_tokens: int | None


@dataclass(frozen=True)
class _PreparedAgentEvidence:
    payload: dict[str, Any]
    execution_result: AdapterResult | None
    output_text: str | None
    status: AgentOutputStatus
    resolved_model: str
    output_error: str | None
    completion_commit: dict[str, Any] | None
    usage: _UsageEvidence
    estimated_cost_usd: float | None


def import_harbor_job(
    *,
    job_dir: Path,
    repo_root: Path,
    experiment_id: str | None = None,
    dataset_id: str | None = None,
) -> list[TrialRecord]:
    """Import every canonical trial directory beneath one Harbor job."""

    trial_dirs = list(iter_harbor_trial_dirs(job_dir=job_dir))
    if not trial_dirs:
        raise HarborImportError(
            f"no Harbor trial directories found in job dir: {job_dir}",
        )
    return [
        import_harbor_trial(
            trial_dir=trial_dir,
            repo_root=repo_root,
            experiment_id=experiment_id,
            dataset_id=dataset_id,
        )
        for trial_dir in trial_dirs
    ]


def iter_harbor_trial_dirs(*, job_dir: Path) -> list[Path]:
    """Return sorted child directories containing a Harbor result artifact."""

    return sorted(child for child in job_dir.iterdir() if child.is_dir() and (child / "result.json").exists())


def build_import_evidence_context(
    *,
    trial_dir: Path,
    repo_root: Path,
) -> ImportEvidenceContext:
    """Read the canonical Harbor result and derive its task evidence path."""

    result_path = Path(trial_dir) / "result.json"
    if not result_path.exists():
        raise HarborImportError(
            f"missing Harbor result artifact: {result_path}",
        )
    harbor_result = _read_harbor_result(result_path)
    return ImportEvidenceContext(
        trial_dir=Path(trial_dir),
        repo_root=Path(repo_root),
        task_instance_dir=(Path(repo_root) / harbor_result.config.task.path),
        harbor_result=harbor_result,
    )


def import_harbor_trial(
    *,
    trial_dir: Path,
    repo_root: Path,
    experiment_id: str | None = None,
    dataset_id: str | None = None,
) -> TrialRecord:
    """Import one Harbor trial and any selected execution-kind evidence."""

    context = build_import_evidence_context(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )
    harbor_result = context.harbor_result
    task = load_task_definition(
        context.task_instance_dir,
        context.repo_root / "tasks",
    )
    import_evidence = load_import_evidence(
        context=context,
        intent=ImportEvidenceIntent.TRIAL_RECORD,
    )
    artifacts = _collect_trial_artifacts(context.trial_dir)
    expected_output_path = normalize_workspace_path(
        task.verifier.expected_output_path,
    )
    agent = _prepare_agent_evidence(
        context=context,
        artifacts=artifacts,
        expected_output_path=expected_output_path,
    )
    system_prompt = _load_system_prompt(
        task_instance_dir=context.task_instance_dir,
        harbor_result=harbor_result,
    )
    evaluation = _evaluation_record(
        reward_path=artifacts.reward_path,
        details_path=artifacts.details_path,
        agent_status=agent.status,
        output_text=agent.output_text,
    )
    evaluation = _with_reviewer_summary(
        evaluation=evaluation,
        trial_dir=context.trial_dir,
    )
    if import_evidence is not None:
        evaluation = import_evidence.augment_evaluation(evaluation)
    task_relative_path = harbor_result.config.task.path
    return TrialRecord(
        trial_id=harbor_result.trial_name,
        experiment_id=(experiment_id or harbor_result.config.job_id),
        dataset_id=dataset_id,
        timestamp=harbor_result.started_at.astimezone(UTC),
        task=TaskReference(
            task_id=task.task_id,
            task_revision=harbor_result.task_checksum,
            visibility=task.visibility,
        ),
        agent=AgentReference(
            adapter=_resolved_record_adapter(
                harbor_result=harbor_result,
                execution_result=agent.execution_result,
                import_evidence=import_evidence,
            ),
            model=agent.resolved_model,
            adapter_revision=harbor_result.agent_info.version,
            configuration=_agent_configuration_record(
                config=harbor_result.config.model_dump(mode="json"),
                resolved_model=agent.resolved_model,
                import_path=harbor_result.config.agent.import_path,
                execution_result=agent.execution_result,
                import_evidence=import_evidence,
            ),
        ),
        environment=EnvironmentSnapshot(
            runtime_image=_runtime_image(
                task_relative_path=task_relative_path,
            ),
            compute_backend=_compute_backend(
                harbor_result.config.environment,
            ),
            tool_versions=None,
        ),
        inputs=InputRecord(
            instruction=task.instruction,
            system_prompt=system_prompt,
            input_files=_input_files(
                repo_root=context.repo_root,
                task_instance_dir=context.task_instance_dir,
                system_prompt=system_prompt,
                manifest_relative_path=task.environment.manifest,
            ),
        ),
        outputs=_output_record(
            context=context,
            artifacts=artifacts,
            agent=agent,
            expected_output_path=expected_output_path,
            import_evidence=import_evidence,
        ),
        evaluation=evaluation,
        timing=_timing_record(harbor_result),
        cost=_cost_record(agent),
        episode_artifact=(None if import_evidence is None else import_evidence.episode_artifact),
        completeness=Completeness.PARTIAL,
    )


def _collect_trial_artifacts(
    trial_dir: Path,
) -> _CollectedTrialArtifacts:
    def agent_file(name: str) -> Path | None:
        return _existing_path(
            trial_dir / "agent" / name,
        ) or _existing_path(
            trial_dir / "artifacts" / "agent" / name,
        )

    output_path = agent_file("output.md")
    if output_path is None:
        output_path = agent_file("output.jsonl")
    return _CollectedTrialArtifacts(
        output_path=output_path,
        conversation_path=agent_file("conversation.jsonl"),
        trajectory_path=agent_file("trajectory.jsonl"),
        agent_result_path=agent_file("agent_result.json"),
        reward_path=_existing_path(
            trial_dir / "verifier" / "reward.json",
        ),
        details_path=_existing_path(
            trial_dir / "verifier" / "details.json",
        ),
    )


def _prepare_agent_evidence(
    *,
    context: ImportEvidenceContext,
    artifacts: _CollectedTrialArtifacts,
    expected_output_path: str,
) -> _PreparedAgentEvidence:
    harbor_result = context.harbor_result
    artifact_payload = _read_json_object(artifacts.agent_result_path) if artifacts.agent_result_path else {}
    execution_result = _current_execution_result(
        artifacts.agent_result_path,
        artifact_payload,
    )
    payload = {
        **dict(harbor_result.agent_result.metadata),
        **artifact_payload,
    }
    if not payload.get("input_tokens") and harbor_result.agent_result.n_input_tokens:
        payload["input_tokens"] = harbor_result.agent_result.n_input_tokens
    if not payload.get("output_tokens") and harbor_result.agent_result.n_output_tokens:
        payload["output_tokens"] = harbor_result.agent_result.n_output_tokens
    output_text = _read_text_or_none(artifacts.output_path)
    status = _agent_status(
        harbor_result=harbor_result,
        output_text=output_text,
        execution_result=execution_result,
        lifecycle_status=payload.get("lifecycle_status"),
    )
    resolved_model = _resolved_model(
        harbor_result=harbor_result,
        execution_result=execution_result,
    )
    output_error = _output_error_message(
        harbor_result=harbor_result,
        agent_status=status,
        execution_result=execution_result,
        provider_error=(payload.get("provider_error") or payload.get("error")),
    )
    usage = _usage_evidence(
        execution_result=execution_result,
        payload=payload,
    )
    estimated_cost = _float_or_none(
        harbor_result.agent_result.cost_usd,
    )
    if estimated_cost is None:
        estimated_cost = estimate_cost_usd(
            resolved_model,
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            cache_read_tokens=usage.cache_read_tokens or 0,
            cache_write_tokens=usage.cache_write_tokens or 0,
        )
    return _PreparedAgentEvidence(
        payload=payload,
        execution_result=execution_result,
        output_text=output_text,
        status=status,
        resolved_model=resolved_model,
        output_error=output_error,
        completion_commit=verify_output_commit(
            execution_result=execution_result,
            untrusted_agent_result=payload,
            output_path=artifacts.output_path,
            expected_output_path=expected_output_path,
            task_instance_dir=context.task_instance_dir,
        ),
        usage=usage,
        estimated_cost_usd=estimated_cost,
    )


def _usage_evidence(
    *,
    execution_result: AdapterResult | None,
    payload: dict[str, Any],
) -> _UsageEvidence:
    return _UsageEvidence(
        model_calls=_usage_value(
            execution_result,
            "usage_model_calls",
            payload,
            "usage_model_calls",
        ),
        input_tokens=_usage_value(
            execution_result,
            "usage_input_tokens",
            payload,
            "usage_input_tokens",
            "input_tokens",
        ),
        output_tokens=_usage_value(
            execution_result,
            "usage_output_tokens",
            payload,
            "usage_output_tokens",
            "output_tokens",
        ),
        cache_read_tokens=_usage_value(
            execution_result,
            "usage_cache_read_tokens",
            payload,
            "usage_cache_read_tokens",
            "cache_read_input_tokens",
        ),
        cache_write_tokens=_usage_value(
            execution_result,
            "usage_cache_write_tokens",
            payload,
            "usage_cache_write_tokens",
            "cache_creation_input_tokens",
        ),
        advisor_calls=_usage_value(
            execution_result,
            "usage_advisor_calls",
            payload,
            "usage_advisor_calls",
        ),
        advisor_input_tokens=_usage_value(
            execution_result,
            "usage_advisor_input_tokens",
            payload,
            "usage_advisor_input_tokens",
        ),
        advisor_output_tokens=_usage_value(
            execution_result,
            "usage_advisor_output_tokens",
            payload,
            "usage_advisor_output_tokens",
        ),
    )


def _with_reviewer_summary(
    *,
    evaluation: EvaluationResult,
    trial_dir: Path,
) -> EvaluationResult:
    reviewer_summary = _read_reviewer_summary(trial_dir)
    if reviewer_summary is None:
        return evaluation
    breakdown = dict(evaluation.breakdown or {})
    breakdown["llm_reviewer"] = reviewer_summary
    return evaluation.model_copy(update={"breakdown": breakdown})


def _resolved_record_adapter(
    *,
    harbor_result: HarborTrialResult,
    execution_result: AdapterResult | None,
    import_evidence: ImportedExecutionEvidence | None,
) -> str:
    if import_evidence is not None:
        return import_evidence.adapter_name
    if execution_result is not None:
        return execution_result.adapter_name
    return _resolved_adapter(harbor_result)


def _agent_configuration_record(
    *,
    config: dict[str, Any],
    resolved_model: str,
    import_path: str | None,
    execution_result: AdapterResult | None,
    import_evidence: ImportedExecutionEvidence | None,
) -> dict[str, Any]:
    if execution_result is not None:
        return dict(execution_result.configuration_record)
    agent_config = cast(
        dict[str, Any],
        config.get("agent", {}),
    )
    configuration = dict(
        cast(
            dict[str, Any],
            agent_config.get("kwargs", {}),
        )
    )
    if import_evidence is not None:
        configuration = import_evidence.sanitize_agent_configuration(
            configuration,
        )
    configuration["model"] = resolved_model
    if import_path is not None:
        configuration["import_path"] = import_path
    configuration["harbor_agent_name"] = agent_config.get("name")
    return configuration


def _output_record(
    *,
    context: ImportEvidenceContext,
    artifacts: _CollectedTrialArtifacts,
    agent: _PreparedAgentEvidence,
    expected_output_path: str,
    import_evidence: ImportedExecutionEvidence | None,
) -> OutputRecord:
    execution_result = agent.execution_result
    payload = agent.payload
    terminated, truncated, final_reason = _terminal_state(
        execution_result=execution_result,
        payload=payload,
        status=agent.status,
    )
    return OutputRecord(
        agent_output=AgentOutput(
            status=agent.status,
            output_path=expected_output_path,
            output_format=infer_output_format(expected_output_path),
            error_message=agent.output_error,
        ),
        raw_output_path=normalize_artifact_path(
            artifacts.output_path,
            context.repo_root,
        ),
        conversation_path=normalize_artifact_path(
            artifacts.conversation_path,
            context.repo_root,
        ),
        trajectory_path=normalize_artifact_path(
            artifacts.trajectory_path,
            context.repo_root,
        ),
        agent_result={
            "failure_kind": (
                execution_result.failure_kind.value
                if (execution_result is not None and execution_result.failure_kind is not None)
                else payload.get("failure_kind")
            ),
            "stop_reason": (
                execution_result.stop_reason.value
                if (execution_result is not None and execution_result.stop_reason is not None)
                else payload.get("stop_reason")
            ),
            "completion_reason": (
                execution_result.completion_reason.value
                if (execution_result is not None and execution_result.completion_reason is not None)
                else payload.get("completion_reason")
            ),
            "completion_assistance": _completion_assistance(
                execution_result=execution_result,
                payload=payload,
            ),
            "completion_commit": agent.completion_commit,
            "provider_error": (execution_result.provider_error if execution_result is not None else agent.output_error),
            "harbor_status": (
                execution_result.agent_output.status.value if execution_result is not None else payload.get("status")
            ),
            "system_prompt_source": payload.get(
                "system_prompt_source",
            ),
            "turns_used": (
                execution_result.turns_used if execution_result is not None else _int_or_none(payload.get("turns_used"))
            ),
            "max_turns": (
                execution_result.max_turns if execution_result is not None else _int_or_none(payload.get("max_turns"))
            ),
            "runtime_execution_attestation": payload.get(
                "runtime_execution_attestation",
            ),
            "bridge_mode": payload.get("bridge_mode"),
            "lifecycle_status": payload.get("lifecycle_status"),
            "reward_owner": payload.get("reward_owner"),
        },
        artifacts=(None if import_evidence is None else list(import_evidence.artifacts)),
        terminated=terminated,
        truncated=truncated,
        final_reason=final_reason,
    )


def _terminal_state(
    *,
    execution_result: AdapterResult | None,
    payload: dict[str, Any],
    status: AgentOutputStatus,
) -> tuple[bool, bool, str | None]:
    for field, terminated in (("completion_reason", True), ("stop_reason", False), ("failure_kind", False)):
        current = None if execution_result is None else getattr(execution_result, field)
        reason = current.value if current is not None else payload.get(field)
        if isinstance(reason, str) and reason:
            return terminated, not terminated, reason
    return status is AgentOutputStatus.COMPLETED, False, None


def _completion_assistance(
    *,
    execution_result: AdapterResult | None,
    payload: dict[str, Any],
) -> object:
    if execution_result is None or execution_result.completion_assistance is None:
        return payload.get("completion_assistance")
    assistance = execution_result.completion_assistance
    return {
        "contract_satisfied": assistance.contract_satisfied,
        "reminder_sent": assistance.reminder_sent,
        "reminder_turn": assistance.reminder_turn,
        "explicit_final_turn": assistance.explicit_final_turn,
    }


def _timing_record(
    harbor_result: HarborTrialResult,
) -> TimingRecord:
    return TimingRecord(
        total_seconds=_duration_between(
            started_at=harbor_result.started_at,
            finished_at=harbor_result.finished_at,
        ),
        agent_seconds=_stage_duration_seconds(
            harbor_result.agent_execution,
        ),
        setup_seconds=_setup_duration_seconds(
            harbor_result=harbor_result,
        ),
        verification_seconds=_stage_duration_seconds(
            harbor_result.verifier,
        ),
    )


def _cost_record(agent: _PreparedAgentEvidence) -> CostRecord:
    usage = agent.usage
    total_input_tokens = (
        usage.input_tokens if agent.execution_result is not None else _total_input_tokens(agent.payload)
    )
    return CostRecord(
        model_calls=usage.model_calls,
        tokens_in=total_input_tokens,
        tokens_out=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        estimated_cost_usd=agent.estimated_cost_usd,
        advisor_calls=usage.advisor_calls,
        advisor_input_tokens=usage.advisor_input_tokens,
        advisor_output_tokens=usage.advisor_output_tokens,
    )


def _input_files(
    *,
    repo_root: Path,
    task_instance_dir: Path,
    system_prompt: str | None,
    manifest_relative_path: str | None,
) -> list[FileReference] | None:
    candidate_paths = [
        (task_instance_dir / "instruction.md", "task"),
        (task_instance_dir / "task.toml", "task"),
        (task_instance_dir / "tests" / "test.sh", "verifier"),
        (
            task_instance_dir / "environment" / "output_contract.json",
            "output_completion_contract",
        ),
    ]
    if system_prompt is not None:
        candidate_paths.append(
            (
                task_instance_dir / "environment" / "system_prompt.md",
                "system_prompt",
            )
        )
    if manifest_relative_path is not None:
        candidate_paths.append(
            (
                task_instance_dir / manifest_relative_path,
                "manifest",
            )
        )
    file_references = [
        FileReference(
            path=path.relative_to(repo_root).as_posix(),
            hash=_sha256(path),
            source=source,
        )
        for path, source in candidate_paths
        if path.exists()
    ]
    return file_references or None


def _evaluation_record(
    *,
    reward_path: Path | None,
    details_path: Path | None,
    agent_status: AgentOutputStatus,
    output_text: str | None,
) -> EvaluationResult:
    completed = agent_status is AgentOutputStatus.COMPLETED
    verifier_attested_output = bool(output_text and output_text.strip()) and _positive_verifier_reward(reward_path)
    valid_output = completed or verifier_attested_output
    return read_verifier_artifacts(
        reward_path=reward_path,
        details_path=details_path,
        output_parseable=valid_output,
        schema_valid=valid_output,
    )


def _positive_verifier_reward(
    reward_path: Path | None,
) -> bool:
    if reward_path is None:
        return False
    payload = _read_json_object(reward_path)
    reward = _float_or_none(payload.get("reward"))
    return reward is not None and reward > 0.0


def _load_system_prompt(
    *,
    task_instance_dir: Path,
    harbor_result: HarborTrialResult,
) -> str | None:
    metadata = harbor_result.agent_result.metadata
    if metadata.get("system_prompt_source") != "workspace_file":
        return None
    system_prompt_path = task_instance_dir / "environment" / "system_prompt.md"
    if not system_prompt_path.exists():
        return None
    return system_prompt_path.read_text(encoding="utf-8")


def _agent_status(
    *,
    harbor_result: HarborTrialResult,
    output_text: str | None,
    execution_result: AdapterResult | None,
    lifecycle_status: object,
) -> AgentOutputStatus:
    if execution_result is not None:
        return execution_result.agent_output.status
    if lifecycle_status == "complete":
        return AgentOutputStatus.COMPLETED
    if lifecycle_status == "failed":
        return AgentOutputStatus.FAILED
    if lifecycle_status == "partial":
        return AgentOutputStatus.PARTIAL
    if harbor_result.exception_info is not None:
        return AgentOutputStatus.FAILED
    if output_text is None:
        return AgentOutputStatus.EMPTY
    if output_text.strip():
        return AgentOutputStatus.COMPLETED
    return AgentOutputStatus.EMPTY


def _output_error_message(
    *,
    harbor_result: HarborTrialResult,
    agent_status: AgentOutputStatus,
    execution_result: AdapterResult | None,
    provider_error: object,
) -> str | None:
    if execution_result is not None:
        return execution_result.agent_output.error_message or execution_result.provider_error
    if agent_status is not AgentOutputStatus.FAILED:
        return None
    if isinstance(provider_error, str) and provider_error:
        return provider_error
    exception_info = harbor_result.exception_info
    if isinstance(exception_info, dict):
        message = exception_info.get("message") or exception_info.get("error")
        if isinstance(message, str) and message:
            return message
    return "Harbor trial failed"


def _resolved_model(
    *,
    harbor_result: HarborTrialResult,
    execution_result: AdapterResult | None,
) -> str:
    if execution_result is not None:
        return execution_result.resolved_model
    model = harbor_result.agent_result.metadata.get("model")
    if isinstance(model, str) and model:
        return model
    configured_model = harbor_result.config.agent.model_name
    if isinstance(configured_model, str) and configured_model:
        return configured_model
    raise HarborImportError(
        "unable to resolve model name from Harbor result",
    )


def _resolved_adapter(
    harbor_result: HarborTrialResult,
) -> str:
    adapter = harbor_result.agent_result.metadata.get(
        "adapter_name",
    )
    if isinstance(adapter, str) and adapter:
        return adapter
    return harbor_result.agent_info.name


def _runtime_image(*, task_relative_path: str) -> str:
    return f"harbor-dockerfile:{task_relative_path}/environment/Dockerfile"


def _compute_backend(
    environment: HarborEnvironmentConfig,
) -> str:
    if environment.type is not None:
        return environment.type
    raw_backend = environment.kwargs.get("compute_backend")
    if isinstance(raw_backend, str) and raw_backend:
        return raw_backend
    if environment.import_path == MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH:
        return MORPH_BACKEND
    raise HarborImportError(
        "unable to resolve compute backend from Harbor result",
    )


def _setup_duration_seconds(
    *,
    harbor_result: HarborTrialResult,
) -> float | None:
    environment_setup = _stage_duration_seconds(
        harbor_result.environment_setup,
    )
    agent_setup = _stage_duration_seconds(
        harbor_result.agent_setup,
    )
    if environment_setup is None and agent_setup is None:
        return None
    return (environment_setup or 0.0) + (agent_setup or 0.0)


def _stage_duration_seconds(
    stage_payload: Any,
) -> float | None:
    if stage_payload is None:
        return None
    return _duration_between(
        started_at=cast(datetime, stage_payload.started_at),
        finished_at=cast(datetime, stage_payload.finished_at),
    )


def _duration_between(
    *,
    started_at: datetime,
    finished_at: datetime,
) -> float:
    return (finished_at.astimezone(UTC) - started_at.astimezone(UTC)).total_seconds()


def _existing_path(path: Path) -> Path | None:
    if path.exists():
        return path
    return None


def _read_text_or_none(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _total_input_tokens(
    agent_result_payload: dict[str, Any],
) -> int | None:
    input_tokens = _int_or_none(agent_result_payload.get("input_tokens")) or 0
    cache_read_tokens = (
        _int_or_none(
            agent_result_payload.get("cache_read_input_tokens"),
        )
        or 0
    )
    cache_write_tokens = (
        _int_or_none(
            agent_result_payload.get(
                "cache_creation_input_tokens",
            ),
        )
        or 0
    )
    total = input_tokens + cache_read_tokens + cache_write_tokens
    if total == 0:
        return None
    return total


def _read_harbor_result(path: Path) -> HarborTrialResult:
    try:
        return read_harbor_trial_result(path)
    except (
        HarborArtifactContractError,
        FileNotFoundError,
        ValueError,
    ) as error:
        raise HarborImportError(str(error)) from error


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarborImportError(
            f"expected JSON object in {path}",
        )
    return cast(dict[str, Any], payload)


def _current_execution_result(
    path: Path | None,
    payload: dict[str, Any],
) -> AdapterResult | None:
    if path is None or not isinstance(
        payload.get("agent_output"),
        dict,
    ):
        return None
    required = {
        "adapter_name",
        "resolved_model",
        "configuration_record",
        "transcript",
    }
    if not required.issubset(payload):
        return None
    try:
        return read_execution_result(path)
    except (KeyError, TypeError, ValueError) as error:
        raise HarborImportError(
            f"invalid current execution result artifact: {error}",
        ) from error


def _usage_value(
    execution_result: AdapterResult | None,
    attribute: str,
    payload: dict[str, Any],
    *keys: str,
) -> int | None:
    if execution_result is not None:
        value = _int_or_none(
            getattr(execution_result, attribute),
        )
        if value is not None:
            return value
    for key in keys:
        value = _int_or_none(payload.get(key))
        if value is not None:
            return value
    return None


def _read_reviewer_summary(
    trial_dir: Path,
) -> dict[str, Any] | None:
    for path in [
        trial_dir / "reviewer" / "summary.json",
        (trial_dir / "artifacts" / "logs" / "reviewer" / "summary.json"),
        trial_dir / "logs" / "reviewer" / "summary.json",
    ]:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return cast(dict[str, Any], payload)
    return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


__all__ = (
    "build_import_evidence_context",
    "import_harbor_job",
    "import_harbor_trial",
    "iter_harbor_trial_dirs",
)
