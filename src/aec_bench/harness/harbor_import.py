# ABOUTME: Import helpers that map Harbor trial directories into Python TrialRecord contracts.
# ABOUTME: Preserves Python provenance boundaries while using Harbor as the execution substrate.

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
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
from aec_bench.contracts.validators import infer_output_format, normalize_workspace_path
from aec_bench.harness.harbor_contract import (
    HarborArtifactContractError,
    HarborTrialResult,
    read_harbor_trial_result,
)
from aec_bench.harness.verifier_artifacts import read_verifier_artifacts
from aec_bench.tasks.loader import load_task_definition


class HarborImportError(Exception):
    pass


def import_harbor_job(
    *,
    job_dir: Path,
    repo_root: Path,
    experiment_id: str | None = None,
    dataset_id: str | None = None,
) -> list[TrialRecord]:
    trial_dirs = list(iter_harbor_trial_dirs(job_dir=job_dir))
    if not trial_dirs:
        raise HarborImportError(f"no Harbor trial directories found in job dir: {job_dir}")
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
    return sorted(child for child in job_dir.iterdir() if child.is_dir() and (child / "result.json").exists())


def import_harbor_trial(
    *,
    trial_dir: Path,
    repo_root: Path,
    experiment_id: str | None = None,
    dataset_id: str | None = None,
) -> TrialRecord:
    result_path = trial_dir / "result.json"
    if not result_path.exists():
        raise HarborImportError(f"missing Harbor result artifact: {result_path}")

    harbor_result = _read_harbor_result(result_path)
    config = harbor_result.config.model_dump(mode="json")
    task_relative_path = harbor_result.config.task.path

    task_instance_dir = repo_root / task_relative_path
    tasks_root = repo_root / "tasks"
    task = load_task_definition(task_instance_dir, tasks_root)

    # Agent artifacts may be in agent/ (Harbor convention download from /logs/agent/)
    # or artifacts/agent/ (our configured download from /workspace/)
    def _agent_file(name: str) -> Path | None:
        return _existing_path(trial_dir / "agent" / name) or _existing_path(trial_dir / "artifacts" / "agent" / name)

    output_path = _agent_file("output.md")
    if output_path is None:
        output_path = _agent_file("output.jsonl")
    conversation_path = _agent_file("conversation.jsonl")
    trajectory_path = _agent_file("trajectory.jsonl")
    agent_result_path = _agent_file("agent_result.json")
    reward_path = _existing_path(trial_dir / "verifier" / "reward.json")
    details_path = _existing_path(trial_dir / "verifier" / "details.json")

    output_text = _read_text_or_none(output_path)
    agent_status = _agent_status(harbor_result=harbor_result, output_text=output_text)
    system_prompt = _load_system_prompt(
        task_instance_dir=task_instance_dir,
        harbor_result=harbor_result,
    )

    evaluation = _evaluation_record(
        reward_path=reward_path,
        details_path=details_path,
        agent_status=agent_status,
    )

    agent_result_payload = _read_json_object(agent_result_path) if agent_result_path else {}
    # When agent artifacts aren't downloaded (Modal teardown), fall back to
    # Harbor's captured context values from result.json
    if not agent_result_payload and harbor_result.agent_result.metadata:
        agent_result_payload = dict(harbor_result.agent_result.metadata)
    if not agent_result_payload.get("input_tokens") and harbor_result.agent_result.n_input_tokens:
        agent_result_payload["input_tokens"] = harbor_result.agent_result.n_input_tokens
    if not agent_result_payload.get("output_tokens") and harbor_result.agent_result.n_output_tokens:
        agent_result_payload["output_tokens"] = harbor_result.agent_result.n_output_tokens
    import_path = harbor_result.config.agent.import_path
    resolved_model = _resolved_model(harbor_result=harbor_result)
    expected_output_path = normalize_workspace_path(task.verifier.expected_output_path)
    output_format = infer_output_format(expected_output_path)
    output_error = _output_error_message(harbor_result=harbor_result, agent_status=agent_status)
    cache_write_tokens = _int_or_none(agent_result_payload.get("cache_creation_input_tokens"))
    estimated_cost = _float_or_none(harbor_result.agent_result.cost_usd)
    if estimated_cost is None:
        estimated_cost = estimate_cost_usd(
            resolved_model,
            input_tokens=_int_or_none(agent_result_payload.get("input_tokens")) or 0,
            output_tokens=_int_or_none(agent_result_payload.get("output_tokens")) or 0,
            cache_read_tokens=_int_or_none(agent_result_payload.get("cache_read_input_tokens")) or 0,
            cache_write_tokens=cache_write_tokens or 0,
        )

    return TrialRecord(
        trial_id=harbor_result.trial_name,
        experiment_id=experiment_id or harbor_result.config.job_id,
        dataset_id=dataset_id,
        timestamp=harbor_result.started_at.astimezone(UTC),
        task=TaskReference(
            task_id=task.task_id,
            task_revision=harbor_result.task_checksum,
        ),
        agent=AgentReference(
            adapter=harbor_result.agent_info.name,
            model=resolved_model,
            adapter_revision=harbor_result.agent_info.version,
            configuration=_agent_configuration_record(
                config=config,
                resolved_model=resolved_model,
                import_path=import_path,
            ),
        ),
        environment=EnvironmentSnapshot(
            runtime_image=_runtime_image(task_relative_path=task_relative_path),
            compute_backend=harbor_result.config.environment.type,
            tool_versions=None,
        ),
        inputs=InputRecord(
            instruction=task.instruction,
            system_prompt=system_prompt,
            input_files=_input_files(
                repo_root=repo_root,
                task_instance_dir=task_instance_dir,
                system_prompt=system_prompt,
                manifest_relative_path=task.environment.manifest,
            ),
        ),
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=agent_status,
                output_path=expected_output_path,
                output_format=output_format,
                error_message=output_error,
            ),
            raw_output_path=_normalize_artifact_path(output_path, repo_root),
            conversation_path=_normalize_artifact_path(conversation_path, repo_root),
            trajectory_path=_normalize_artifact_path(trajectory_path, repo_root),
            agent_result={
                "failure_kind": None,
                "provider_error": output_error,
                "usage_input_tokens": _int_or_none(agent_result_payload.get("input_tokens")),
                "usage_output_tokens": _int_or_none(agent_result_payload.get("output_tokens")),
                "usage_cache_tokens": _int_or_none(agent_result_payload.get("cache_read_input_tokens")),
                "usage_cache_write_tokens": cache_write_tokens,
                "harbor_status": agent_result_payload.get("status"),
                "system_prompt_source": agent_result_payload.get("system_prompt_source"),
                "turns_used": _int_or_none(agent_result_payload.get("turns_used")),
                "max_turns": _int_or_none(agent_result_payload.get("max_turns")),
            },
        ),
        evaluation=evaluation,
        timing=TimingRecord(
            total_seconds=_duration_between(
                started_at=harbor_result.started_at,
                finished_at=harbor_result.finished_at,
            ),
            agent_seconds=_stage_duration_seconds(harbor_result.agent_execution),
            setup_seconds=_setup_duration_seconds(harbor_result=harbor_result),
            verification_seconds=_stage_duration_seconds(harbor_result.verifier),
        ),
        cost=CostRecord(
            tokens_in=_total_input_tokens(agent_result_payload),
            tokens_out=_int_or_none(agent_result_payload.get("output_tokens")),
            estimated_cost_usd=estimated_cost,
        ),
        completeness=Completeness.PARTIAL,
    )


def _agent_configuration_record(
    *,
    config: dict[str, Any],
    resolved_model: str,
    import_path: str | None,
) -> dict[str, Any]:
    agent_config = cast(dict[str, Any], config.get("agent", {}))
    configuration = dict(cast(dict[str, Any], agent_config.get("kwargs", {})))
    configuration["model"] = resolved_model
    if import_path is not None:
        configuration["import_path"] = import_path
    configuration["harbor_agent_name"] = agent_config.get("name")
    return configuration


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
    ]
    if system_prompt is not None:
        candidate_paths.append((task_instance_dir / "environment" / "system_prompt.md", "system_prompt"))
    if manifest_relative_path is not None:
        candidate_paths.append((task_instance_dir / manifest_relative_path, "manifest"))

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
) -> EvaluationResult:
    completed = agent_status is AgentOutputStatus.COMPLETED
    return read_verifier_artifacts(
        reward_path=reward_path,
        details_path=details_path,
        output_parseable=completed,
        schema_valid=completed,
    )


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
) -> AgentOutputStatus:
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
) -> str | None:
    if agent_status is not AgentOutputStatus.FAILED:
        return None
    exception_info = harbor_result.exception_info
    if isinstance(exception_info, dict):
        message = exception_info.get("message") or exception_info.get("error")
        if isinstance(message, str) and message:
            return message
    return "Harbor trial failed"


def _resolved_model(*, harbor_result: HarborTrialResult) -> str:
    model = harbor_result.agent_result.metadata.get("model")
    if isinstance(model, str) and model:
        return model
    configured_model = harbor_result.config.agent.model_name
    if isinstance(configured_model, str) and configured_model:
        return configured_model
    raise HarborImportError("unable to resolve model name from Harbor result")


def _runtime_image(*, task_relative_path: str) -> str:
    return f"harbor-dockerfile:{task_relative_path}/environment/Dockerfile"


def _setup_duration_seconds(*, harbor_result: HarborTrialResult) -> float | None:
    environment_setup = _stage_duration_seconds(harbor_result.environment_setup)
    agent_setup = _stage_duration_seconds(harbor_result.agent_setup)
    if environment_setup is None and agent_setup is None:
        return None
    return (environment_setup or 0.0) + (agent_setup or 0.0)


def _stage_duration_seconds(stage_payload: Any) -> float | None:
    if stage_payload is None:
        return None
    return _duration_between(
        started_at=cast(datetime, stage_payload.started_at),
        finished_at=cast(datetime, stage_payload.finished_at),
    )


def _duration_between(*, started_at: datetime, finished_at: datetime) -> float:
    return (finished_at.astimezone(UTC) - started_at.astimezone(UTC)).total_seconds()


def _existing_path(path: Path) -> Path | None:
    if path.exists():
        return path
    return None


def _normalize_artifact_path(path: Path | None, repo_root: Path) -> str | None:
    """Normalise an artifact path to jobs/-relative for portable ledger records.

    Stored paths should be relative to the repo root so ledger records
    work across machines and directory moves.
    """
    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        # Path is outside repo root — store as-is
        return path.as_posix()


def _read_text_or_none(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _total_input_tokens(agent_result_payload: dict[str, Any]) -> int | None:
    input_tokens = _int_or_none(agent_result_payload.get("input_tokens")) or 0
    cache_read_tokens = _int_or_none(agent_result_payload.get("cache_read_input_tokens")) or 0
    cache_write_tokens = _int_or_none(agent_result_payload.get("cache_creation_input_tokens")) or 0
    total = input_tokens + cache_read_tokens + cache_write_tokens
    if total == 0:
        return None
    return total


def _read_harbor_result(path: Path) -> HarborTrialResult:
    try:
        return read_harbor_trial_result(path)
    except (HarborArtifactContractError, FileNotFoundError, ValueError) as exc:
        raise HarborImportError(str(exc)) from exc


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarborImportError(f"expected JSON object in {path}")
    return cast(dict[str, Any], payload)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
