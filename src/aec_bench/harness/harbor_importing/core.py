# ABOUTME: Imports canonical Harbor trial artifacts into generic TrialRecord contracts.
# ABOUTME: Accepts bounded-context evidence through one optional loader boundary.

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
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority_evidence import ACTOR_INVOCATION_EVIDENCE_PROTOCOL, AuthorityEvidenceKind
from aec_bench.contracts.dataset import DatasetRef, RepositoryDatasetRef
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    AuthorityExpectation,
    CostRecord,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    GitSourceRef,
    ProviderRoute,
    RunManifest,
    TimingRecord,
    TrialInput,
    TrialOutput,
    TrialRecord,
    TrialTaskKind,
    UnresolvedSourceRef,
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
from aec_bench.harness.harbor_importing.artifact_io import (
    normalize_artifact_path,
)
from aec_bench.harness.harbor_importing.contracts import (
    HarborImportError,
    HarborImportEvidence,
    HarborImportEvidenceLoader,
    ImportEvidenceContext,
    ImportEvidenceIntent,
)
from aec_bench.harness.harbor_importing.output_commit import (
    verify_output_commit,
)
from aec_bench.harness.trial_record_builder import portable_agent_configuration
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
    dataset: DatasetRef | None = None,
    evidence_loader: HarborImportEvidenceLoader | None = None,
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
            dataset=dataset,
            evidence_loader=evidence_loader,
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
    dataset: DatasetRef | None = None,
    evidence_loader: HarborImportEvidenceLoader | None = None,
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
    import_evidence = _load_import_evidence(
        context=context,
        intent=ImportEvidenceIntent.TRIAL_RECORD,
        evidence_loader=evidence_loader,
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
    resolved_adapter = _resolved_record_adapter(
        harbor_result=harbor_result,
        execution_result=agent.execution_result,
        import_evidence=import_evidence,
    )
    configuration = _agent_configuration_record(
        config=harbor_result.config.model_dump(mode="json"),
        resolved_model=agent.resolved_model,
        import_path=harbor_result.config.agent.import_path,
        execution_result=agent.execution_result,
        import_evidence=import_evidence,
    )
    compute_backend = _compute_backend(harbor_result.config.environment)
    run_id = ":".join(
        (experiment_id or harbor_result.config.job_id, resolved_adapter, agent.resolved_model, compute_backend)
    )
    task_kind: TrialTaskKind = (
        "world" if import_evidence is not None and import_evidence.episode_artifact is not None else "artifact"
    )
    expected_authorities = _expected_authorities(
        task_kind=task_kind,
        adapter=resolved_adapter,
        provider_evidence_protocol=_provider_evidence_protocol(
            configuration=configuration,
            adapter=resolved_adapter,
        ),
    )
    manifest = RunManifest(
        run_id=run_id,
        experiment_id=(experiment_id or harbor_result.config.job_id),
        dataset=dataset,
        source=_run_source(dataset),
        agent=AgentConfiguration(
            adapter=resolved_adapter,
            model=agent.resolved_model,
            adapter_revision=harbor_result.agent_info.version,
            configuration=portable_agent_configuration(configuration),
        ),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=_runtime_image(harbor_result.config.environment),
            compute_backend=compute_backend,
            tool_versions=None,
        ),
        provider_route=_provider_route(configuration, resolved_adapter),
        expected_authorities=expected_authorities,
    )
    timing = _timing_record(harbor_result)
    record = TrialRecord(
        trial_id=harbor_result.trial_name,
        run_id=run_id,
        task_id=task.task_id,
        execution_status=(
            ExecutionStatus.COMPLETED if agent.status is AgentOutputStatus.COMPLETED else ExecutionStatus.FAILED
        ),
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=(EvidenceStatus.PENDING if expected_authorities else EvidenceStatus.NOT_REQUIRED),
        started_at=harbor_result.started_at.astimezone(UTC),
        completed_at=harbor_result.finished_at.astimezone(UTC),
        input=TrialInput(
            instruction=task.instruction,
            task_revision=harbor_result.task_checksum,
            task_kind=task_kind,
            visibility=task.visibility,
            system_prompt=system_prompt,
        ),
        output=_output_record(
            context=context,
            artifacts=artifacts,
            agent=agent,
            expected_output_path=expected_output_path,
            import_evidence=import_evidence,
        ),
        evaluation=evaluation,
        timing=timing,
        cost=_cost_record(agent),
    )
    for index, (path, source) in enumerate(
        _input_file_paths(
            task_instance_dir=context.task_instance_dir,
            system_prompt=system_prompt,
            manifest_relative_path=task.environment.manifest,
        )
    ):
        record.attach_artifact(f"input:{source}:{index}", path, media_type=_media_type(path))
    for role, artifact_path, media_type in (
        ("raw_output", artifacts.output_path, _media_type(artifacts.output_path)),
        ("conversation", artifacts.conversation_path, "application/x-ndjson"),
        ("trajectory", artifacts.trajectory_path, "application/x-ndjson"),
    ):
        if artifact_path is not None:
            record.attach_artifact(role, artifact_path, media_type=media_type)
    _attach_import_evidence(record, import_evidence, context.repo_root)
    manifest_path = configuration.get("manifest_path")
    if isinstance(manifest_path, str) and Path(manifest_path).is_file():
        provider_manifest = Path(manifest_path)
        content = provider_manifest.read_bytes()
        actual_manifest_sha256 = hashlib.sha256(content).hexdigest()
        reference_payload = configuration.get("provider_evidence_manifest")
        if reference_payload is not None:
            reference = ArtifactRef.model_validate(reference_payload)
            if reference.sha256 != actual_manifest_sha256 or reference.size_bytes != len(content):
                raise HarborImportError("provider evidence manifest does not match its ArtifactRef")
        declared_manifest_sha256 = configuration.get("evidence_manifest_sha256")
        if isinstance(declared_manifest_sha256, str) and declared_manifest_sha256 != actual_manifest_sha256:
            raise HarborImportError("provider evidence manifest does not match its declared SHA-256")
        record.attach_artifact("provider_evidence", provider_manifest, media_type="application/json")
    return record.bind_run_manifest(manifest)


def _load_import_evidence(
    *,
    context: ImportEvidenceContext,
    intent: ImportEvidenceIntent,
    evidence_loader: HarborImportEvidenceLoader | None,
) -> HarborImportEvidence | None:
    configuration = context.harbor_result.config.agent.kwargs
    has_execution_kind = "execution_kind" in configuration
    execution_kind = configuration.get("execution_kind")
    if has_execution_kind and (not isinstance(execution_kind, str) or not execution_kind):
        raise HarborImportError("Harbor execution_kind must be a non-empty string")
    if evidence_loader is None:
        if has_execution_kind:
            raise HarborImportError(f"Harbor execution kind {execution_kind!r} requires an evidence loader")
        return None
    evidence = evidence_loader(context=context, intent=intent)
    if has_execution_kind and evidence is None:
        raise HarborImportError(f"evidence loader does not support Harbor execution kind {execution_kind!r}")
    return evidence


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
    import_evidence: HarborImportEvidence | None,
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
    import_evidence: HarborImportEvidence | None,
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
    import_evidence: HarborImportEvidence | None,
) -> TrialOutput:
    execution_result = agent.execution_result
    payload = agent.payload
    terminated, truncated, final_reason = _terminal_state(
        execution_result=execution_result,
        payload=payload,
        status=agent.status,
    )
    return TrialOutput(
        agent_output=AgentOutput(
            status=agent.status,
            output_path=expected_output_path,
            output_format=infer_output_format(expected_output_path),
            error_message=agent.output_error,
        ),
        agent_result={
            # These are Harbor backend identifiers only. Canonical import binds
            # TrialRecord.trial_id to the planned UUID in the reconciliation boundary.
            "harbor_job_id": context.harbor_result.config.job_id,
            "harbor_trial_name": context.harbor_result.trial_name,
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
        terminated=terminated,
        truncated=truncated,
        final_reason=final_reason,
    ).bind_runtime_paths(
        raw_output_path=normalize_artifact_path(artifacts.output_path, context.repo_root),
        conversation_path=normalize_artifact_path(artifacts.conversation_path, context.repo_root),
        trajectory_path=normalize_artifact_path(artifacts.trajectory_path, context.repo_root),
    )


def _terminal_state(
    *,
    execution_result: AdapterResult | None,
    payload: dict[str, Any],
    status: AgentOutputStatus,
) -> tuple[bool, bool, str | None]:
    for field, flags in (
        ("completion_reason", (True, False)),
        ("stop_reason", (False, True)),
        ("failure_kind", (False, False)),
    ):
        current = None if execution_result is None else getattr(execution_result, field)
        reason = current.value if current is not None else payload.get(field)
        if isinstance(reason, str) and reason:
            return flags[0], flags[1], reason
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


def _input_file_paths(
    *,
    task_instance_dir: Path,
    system_prompt: str | None,
    manifest_relative_path: str | None,
) -> tuple[tuple[Path, str], ...]:
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
    return tuple((path, source) for path, source in candidate_paths if path.is_file())


def _run_source(dataset: DatasetRef | None) -> GitSourceRef | UnresolvedSourceRef:
    if isinstance(dataset, RepositoryDatasetRef):
        return GitSourceRef(revision=dataset.source_revision)
    return UnresolvedSourceRef(reason="Harbor import has no retained Harness source snapshot or clean Git revision")


def _provider_route(configuration: dict[str, Any], adapter: str) -> ProviderRoute:
    provider = configuration.get("provider") or configuration.get("provider_name") or adapter
    route = configuration.get("provider_route") or configuration.get("route") or adapter
    return ProviderRoute(provider=str(provider), route=str(route))


def _provider_evidence_protocol(*, configuration: dict[str, Any], adapter: str) -> str | None:
    if "deepseek" not in adapter.casefold():
        return None
    manifest_path = configuration.get("manifest_path")
    if isinstance(manifest_path, str) and Path(manifest_path).is_file():
        try:
            payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict) and payload.get("schema") == "aec-bench/deepseek-evidence/2":
            return "aec-bench/deepseek-evidence/2"
    return "aec-bench/deepseek-evidence/3"


def _expected_authorities(
    *,
    task_kind: str,
    adapter: str,
    provider_evidence_protocol: str | None,
) -> tuple[AuthorityExpectation, ...]:
    expected: list[AuthorityExpectation] = []
    if task_kind == "world":
        expected.extend(
            (
                AuthorityExpectation(
                    authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
                    protocol=ACTOR_INVOCATION_EVIDENCE_PROTOCOL,
                ),
                AuthorityExpectation(
                    authority_kind=AuthorityEvidenceKind.WORLD,
                    protocol="aec-bench/world-evidence/1",
                ),
            )
        )
    if "deepseek" in adapter.casefold():
        if provider_evidence_protocol is None:
            raise ValueError("DeepSeek imports require a provider evidence protocol")
        expected.append(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.PROVIDER,
                protocol=provider_evidence_protocol,
            )
        )
    return tuple(expected)


def _attach_import_evidence(
    record: TrialRecord,
    evidence: HarborImportEvidence | None,
    repo_root: Path,
) -> None:
    if evidence is None:
        return
    authority_sha256 = {item.reference.artifact.sha256 for item in evidence.authority_evidence}
    if evidence.episode_artifact is not None:
        authority_sha256.add(evidence.episode_artifact.sha256)
    for index, artifact in enumerate(evidence.artifacts):
        path = Path(artifact.path)
        if not path.is_absolute():
            path = repo_root / path
        if artifact.sha256 in authority_sha256:
            continue
        role = f"output:{artifact.kind}:{index}"
        record.attach_artifact(role, path, media_type=artifact.media_type)
    for authority in evidence.authority_evidence:
        record.attach_artifact(
            f"authority:{authority.reference.authority_kind.value}:{authority.reference.protocol}",
            authority.path,
            media_type=authority.reference.artifact.media_type,
        )
    if evidence.episode_artifact is not None:
        episode_path = Path(evidence.episode_artifact.path)
        if not episode_path.is_absolute():
            episode_path = repo_root / episode_path
        record.attach_artifact(
            f"authority:{AuthorityEvidenceKind.WORLD.value}:aec-bench/world-evidence/1",
            episode_path,
            media_type=evidence.episode_artifact.media_type,
        )


def _media_type(path: Path | None) -> str:
    if path is None:
        return "application/octet-stream"
    if path.suffix == ".json":
        return "application/json"
    if path.suffix == ".jsonl":
        return "application/x-ndjson"
    if path.suffix == ".md":
        return "text/markdown"
    return "application/octet-stream"


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


def _runtime_image(environment: HarborEnvironmentConfig) -> str:
    configured_image = environment.kwargs.get("image")
    if isinstance(configured_image, str) and configured_image:
        return configured_image
    return f"harbor:{_compute_backend(environment)}"


def _compute_backend(
    environment: HarborEnvironmentConfig,
) -> str:
    if environment.type is not None:
        return environment.type
    raw_backend = environment.kwargs.get("compute_backend")
    if isinstance(raw_backend, str) and raw_backend:
        return raw_backend
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
