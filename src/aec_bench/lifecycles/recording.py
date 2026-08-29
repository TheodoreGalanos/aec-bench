# ABOUTME: Records reproducible experiment manifests and normalized metrics for evidence lifecycles.
# ABOUTME: Binds repository, package, model interaction, verification, and run artifacts by hash.

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import platform
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.lifecycle_evaluation import LifecycleSemanticMetrics
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.ledger.durability import (
    fsync_directory as _fsync_directory,
)
from aec_bench.ledger.durability import (
    fsync_tree as _fsync_tree,
)
from aec_bench.ledger.durability import (
    mkdir_durable,
)
from aec_bench.ledger.process_log import read_ledger
from aec_bench.lifecycles import invocation as lifecycle_invocation
from aec_bench.lifecycles.catalogue import (
    lifecycle_operation_resolver,
    lifecycle_package_variant,
    lifecycle_verifier,
)
from aec_bench.lifecycles.compiled import load_compiled_lifecycle
from aec_bench.lifecycles.evidence_files import is_lifecycle_regular_file
from aec_bench.lifecycles.invocation import LifecycleExperimentMetrics, lifecycle_experiment_metrics_payload
from aec_bench.lifecycles.provenance import callable_provenance, repository_provenance, runtime_dependency_provenance
from aec_bench.lifecycles.runtime.lifecycle import (
    evidence_request_protocol_identity,
    read_lifecycle,
)
from aec_bench.lifecycles.runtime.operation_protocol import (
    lifecycle_operation_protocol_identity,
    validate_lifecycle_operation_tool_schema,
)


def record_lifecycle_experiment(
    *,
    package_dir: Path,
    run_dir: Path,
    agent: dict[str, Any],
    verifier: Any,
    verification: dict[str, Any],
    tool_schema: list[dict[str, Any]],
    trial_context: lifecycle_invocation.LifecycleExperimentTrialContext,
    repository_dir: Path | None = None,
    index_path: Path | None = None,
    sweep_context: lifecycle_invocation.LifecycleExperimentSweepContext | None = None,
) -> lifecycle_invocation.LifecycleExperimentRecordingResult:
    """Write one self-contained run record and append its immutable index entry."""
    package = Path(package_dir)
    run = Path(run_dir)
    verification_path = run / "verification.json"
    metrics_path = run / "metrics.json"
    manifest_path = run / "experiment-manifest.json"
    selected_index = index_path or run.parent / "experiment-index.jsonl"
    variant = _package_variant(package)
    compiled = load_compiled_lifecycle(package)
    if compiled.envelope != trial_context.compiled:
        raise ValueError("lifecycle package does not match the planned compiled identity")
    session_payloads = _validated_recording_sessions(agent.get("sessions"))
    resolved_models = sorted({session["resolved_model"] for session in session_payloads})
    resolved_adapters = sorted({session["adapter_name"] for session in session_payloads})
    resolved_model = lifecycle_invocation.single_resolved_lifecycle_identity(
        resolved_models,
        kind="model",
    )
    lifecycle_invocation.single_resolved_lifecycle_identity(
        resolved_adapters,
        kind="adapter",
    )
    lifecycle_state = read_lifecycle(
        package,
        run,
        operation_resolver=(
            lifecycle_operation_resolver(package, run) if (package / "template.json").is_file() else None
        ),
    )
    operation_tool_declared = any(tool.get("name") == "execute_operation" for tool in tool_schema)
    if lifecycle_state.get("schema_version") == "7" or operation_tool_declared:
        validate_lifecycle_operation_tool_schema(tool_schema)
    _write_json(verification_path, verification)

    metrics = _build_metrics(run, agent, verification, resolved_model=resolved_model)
    metrics_payload = lifecycle_experiment_metrics_payload(metrics)
    if metrics.semantic_transition is None:
        metrics_payload.pop("semantic_transition")
    _write_json(metrics_path, metrics_payload)
    trajectories = sorted(run.glob("**/trajectory.jsonl"))
    prompts = _interaction_prompts(trajectories)
    repository_capture = lifecycle_invocation.LifecycleRepositoryProvenance.model_validate(
        repository_provenance(repository_dir or Path(__file__).resolve().parent)
    )
    runtime_capture = lifecycle_invocation.LifecycleRuntimeProvenance.model_validate(
        runtime_dependency_provenance(
            adapter_kind=str(agent["adapter"]),
            model_name=str(agent["model"]),
        )
    )
    state = _read_json(run / "state.json")
    experiment_id = f"lifecycle-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(UTC).isoformat()
    python_version = platform.python_version()
    output_hashes = _run_artifact_hashes(run)
    lifecycle_manifest = {
        "lifecycle_id": state["lifecycle_id"],
        "spec_sha256": state["lifecycle_spec_sha256"],
        "package_sha256": state["package_sha256"],
        "package_files": _tree_hashes(package),
    }
    if variant is not None:
        lifecycle_manifest["variant"] = variant
    verifier_capture = lifecycle_invocation.LifecycleVerifierProvenanceCapture(
        entrypoint=lifecycle_invocation.LifecycleCallableProvenance.model_validate(callable_provenance(verifier)),
        registered=lifecycle_invocation.LifecycleCallableProvenance.model_validate(
            callable_provenance(lifecycle_verifier(compiled.envelope.template_id))
        ),
    )
    repository = repository_capture.model_dump(mode="json")
    runtime_provenance = runtime_capture.model_dump(mode="json")
    interaction = {
        **prompts,
        "tool_schema": tool_schema,
        "trajectory_hashes": {str(path.relative_to(run)): _sha256(path) for path in trajectories},
    }
    if any(tool.get("name") == "request_evidence" for tool in tool_schema):
        tool_schema_payload = json.dumps(
            tool_schema,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        interaction["evidence_request_protocol"] = {
            **evidence_request_protocol_identity(),
            "tool_schema_sha256": hashlib.sha256(tool_schema_payload).hexdigest(),
        }
    if operation_tool_declared:
        tool_schema_payload = json.dumps(
            tool_schema,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        interaction["lifecycle_operation_protocol"] = {
            **lifecycle_operation_protocol_identity(),
            "tool_schema_sha256": hashlib.sha256(tool_schema_payload).hexdigest(),
        }
    execution_manifest = {
        "mode": agent["execution_mode"],
        "memory_visibility_policy": agent["memory_visibility_policy"],
        "session_count": len(session_payloads),
        "status": agent["status"],
        "checkpoint_seconds": metrics.checkpoint_seconds,
        "whole_run_seconds": metrics.whole_run_seconds,
    }
    if "max_turns_per_session" in agent:
        execution_manifest["max_turns_per_session"] = agent["max_turns_per_session"]
    if "limits" in agent:
        execution_manifest["limits"] = agent["limits"]
    manifest = lifecycle_invocation.LifecycleExperimentManifest(
        schema_version="2",
        experiment_id=experiment_id,
        created_at=created_at,
        repository=repository,
        environment={
            "python_version": python_version,
            "platform": platform.platform(),
            "runtime_provenance": runtime_provenance,
        },
        lifecycle=lifecycle_manifest,
        verifier=verifier_capture.manifest_payload(),
        model={
            "requested_model": agent["model"],
            "resolved_models": resolved_models,
            "adapter": agent["adapter"],
            "requested_adapter": agent["adapter"],
            "resolved_adapters": resolved_adapters,
            "session_configurations": [session.get("configuration_record", {}) for session in session_payloads],
            "provider_environment": _provider_environment(),
        },
        execution=execution_manifest,
        interaction=interaction,
        outputs={
            "verification.json": _sha256(verification_path),
            "metrics.json": _sha256(metrics_path),
            "artifacts": output_hashes,
        },
        sweep=sweep_context,
        trial=trial_context,
    )
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    _fsync_tree(run)
    experiment_dir = run / "experiments" / experiment_id
    canonical_staging = experiment_dir.with_name(f".{experiment_id}.staging-{uuid.uuid4().hex}")
    canonical_manifest = experiment_dir / "experiment-manifest.json"
    mkdir_durable(experiment_dir.parent)
    try:
        staging_verification = canonical_staging / "verification.json"
        staging_metrics = canonical_staging / "metrics.json"
        staging_manifest = canonical_staging / "experiment-manifest.json"
        _write_json(staging_verification, verification)
        _write_json(staging_metrics, metrics_payload)
        _write_json(staging_manifest, manifest.model_dump(mode="json"))
        manifest_sha256 = _sha256(staging_manifest)
        index_entry = {
            "experiment_id": experiment_id,
            "created_at": manifest.created_at,
            "repository_commit": repository["commit"],
            "model": agent["model"],
            "execution_mode": agent["execution_mode"],
            "memory_visibility_policy": agent["memory_visibility_policy"],
            "reward": verification["reward"],
            "passed": verification["passed"],
            "manifest_path": str(canonical_manifest),
            "manifest_sha256": manifest_sha256,
        }
        if variant is not None:
            index_entry["variant_id"] = variant["variant_id"]
            index_entry["adaptation"] = variant["adaptation"]
        if sweep_context is not None:
            index_entry["sweep"] = sweep_context.model_dump(mode="json")
        _write_json(canonical_staging / "index-entry.json", index_entry)
        _fsync_tree(canonical_staging)
        canonical_staging.replace(experiment_dir)
        _fsync_directory(experiment_dir.parent)
    except Exception:
        if canonical_staging.exists():
            shutil.rmtree(canonical_staging)
        raise
    _append_jsonl(selected_index, index_entry)
    return {
        "experiment_id": experiment_id,
        "manifest": str(manifest_path),
        "canonical_manifest": str(canonical_manifest),
        "manifest_sha256": manifest_sha256,
        "metrics": str(metrics_path),
        "verification": str(verification_path),
        "index": str(selected_index),
        "finalization_authority": lifecycle_invocation.LifecycleInvocationRecorderCapture(
            manifest_sha256=manifest_sha256
        ),
    }


def _validated_recording_sessions(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("lifecycle recording sessions are malformed")
    sessions: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"lifecycle recording session is malformed: {index}")
        session = cast(dict[str, Any], item)
        _required_recording_session_identity(session, "resolved_model", "resolved model", index)
        _required_recording_session_identity(session, "adapter_name", "resolved adapter", index)
        sessions.append(session)
    return sessions


def _required_recording_session_identity(
    session: dict[str, Any],
    field: str,
    label: str,
    index: int,
) -> str:
    value = session.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"lifecycle recording session {label} is invalid: {index}")
    return value


def _build_metrics(
    run_dir: Path,
    agent: dict[str, Any],
    verification: dict[str, Any],
    *,
    resolved_model: str | None = None,
) -> LifecycleExperimentMetrics:
    trajectories = sorted(run_dir.glob("**/trajectory.jsonl"))
    entries = [entry for path in trajectories for entry in read_trajectory(path)]
    requests = sum(len({entry.step for entry in read_trajectory(path) if entry.step > 0}) for path in trajectories)
    tool_calls = [entry for entry in entries if entry.role == "tool_call"]
    state = _read_json(run_dir / "state.json")
    attempts = [attempt for checkpoint in state["checkpoint_runs"] for attempt in checkpoint.get("attempts", [])]
    evidence_request_actions = [
        action for checkpoint in state["checkpoint_runs"] for action in checkpoint.get("evidence_request_actions", [])
    ]
    operation_actions = [
        action for checkpoint in state["checkpoint_runs"] for action in checkpoint.get("operation_actions", [])
    ]
    timing = _lifecycle_timing(run_dir)
    totals = agent["totals"]
    if resolved_model is None:
        resolved_model = lifecycle_invocation.single_resolved_lifecycle_identity(
            (str(session["resolved_model"]) for session in agent.get("sessions", []) if session.get("resolved_model")),
            kind="model",
        )
    if resolved_model == "unresolved":
        resolved_model = str(agent["model"])
    cost = estimate_cost_usd(
        resolved_model,
        input_tokens=int(totals["input_tokens"]),
        output_tokens=int(totals["output_tokens"]),
        cache_read_tokens=int(totals["cache_read_tokens"]),
        cache_write_tokens=int(totals["cache_write_tokens"]),
    )
    semantic_payload = verification.get("semantic_metrics")
    semantic = LifecycleSemanticMetrics.model_validate(semantic_payload) if semantic_payload is not None else None
    return LifecycleExperimentMetrics(
        checkpoint_count=sum(checkpoint["status"] == "submitted" for checkpoint in state["checkpoint_runs"]),
        requests=requests,
        tool_calls=len(tool_calls),
        reads=sum(entry.tool_name == "read_workspace_file" for entry in tool_calls),
        revisits=sum(entry.tool_name == "revisit_checkpoint" for entry in tool_calls),
        evidence_request_calls=len(evidence_request_actions),
        accepted_evidence_requests=sum(action.get("outcome") == "released" for action in evidence_request_actions),
        already_released_evidence_requests=sum(
            action.get("outcome") == "already_released" for action in evidence_request_actions
        ),
        rejected_evidence_requests=sum(action.get("outcome") == "rejected" for action in evidence_request_actions),
        evidence_request_budget_consumed=sum(
            int(action.get("budget_consumed", 0)) for action in evidence_request_actions
        ),
        evidence_request_artifacts_released=sum(
            len(action.get("released_artifacts", []))
            for action in evidence_request_actions
            if action.get("outcome") == "released"
        ),
        operation_calls=len(operation_actions),
        completed_operations=sum(action.get("outcome") == "completed" for action in operation_actions),
        already_current_operations=sum(action.get("outcome") == "already_current" for action in operation_actions),
        rejected_operations=sum(action.get("outcome") == "rejected" for action in operation_actions),
        operation_budget_consumed=sum(int(action.get("budget_consumed", 0)) for action in operation_actions),
        operation_artifacts_produced=sum(
            len(action.get("artifacts", [])) for action in operation_actions if action.get("outcome") == "completed"
        ),
        retries=sum(max(0, len(checkpoint.get("attempts", [])) - 1) for checkpoint in state["checkpoint_runs"]),
        failures=sum(attempt["status"] == "failed" for attempt in attempts),
        input_tokens=int(totals["input_tokens"]),
        output_tokens=int(totals["output_tokens"]),
        cache_read_tokens=int(totals["cache_read_tokens"]),
        cache_write_tokens=int(totals["cache_write_tokens"]),
        estimated_cost_usd=cost,
        checkpoint_seconds=timing["checkpoint_seconds"],
        whole_run_seconds=timing["whole_run_seconds"],
        semantic_transition=semantic,
    )


def _lifecycle_timing(run_dir: Path) -> dict[str, Any]:
    releases: dict[str, datetime] = {}
    submissions: dict[str, datetime] = {}
    timestamps: list[datetime] = []
    for entry in read_ledger(run_dir / "lifecycle_ledger.jsonl"):
        created_at = datetime.fromisoformat(str(entry["created_at"]).replace("Z", "+00:00"))
        timestamps.append(created_at)
        checkpoint_id = entry.get("summary", {}).get("checkpoint_id")
        if not checkpoint_id:
            continue
        if entry["stage"] == "evidence_release":
            releases.setdefault(str(checkpoint_id), created_at)
        elif entry["stage"] == "checkpoint_submission":
            submissions[str(checkpoint_id)] = created_at
    checkpoint_seconds = {
        checkpoint_id: max(0.0, (submitted - releases[checkpoint_id]).total_seconds())
        for checkpoint_id, submitted in submissions.items()
        if checkpoint_id in releases
    }
    return {
        "checkpoint_seconds": checkpoint_seconds,
        "whole_run_seconds": (max(0.0, (max(timestamps) - min(timestamps)).total_seconds()) if timestamps else None),
    }


def _interaction_prompts(trajectory_paths: list[Path]) -> dict[str, Any]:
    system_prompts: list[dict[str, str]] = []
    user_prompts: list[dict[str, str]] = []
    for path in trajectory_paths:
        for entry in read_trajectory(path):
            if entry.role not in {"system", "user"} or entry.content is None:
                continue
            record = {
                "trajectory": str(path),
                "content": entry.content,
                "sha256": _sha256_bytes(entry.content.encode("utf-8")),
            }
            (system_prompts if entry.role == "system" else user_prompts).append(record)
    return {"system_prompts": system_prompts, "user_prompts": user_prompts}


def _provider_environment() -> dict[str, str]:
    allowed = (
        "AWS_REGION",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_DEPLOYMENT_NAME_LM",
    )
    return {name: value for name in allowed if (value := os.getenv(name))}


def _package_variant(package_dir: Path) -> dict[str, Any] | None:
    return lifecycle_package_variant(package_dir)


def _run_artifact_hashes(run_dir: Path) -> dict[str, str]:
    selected: dict[str, str] = {}
    names = {
        "agent_result.json",
        "agent_result.corrupt.json",
        "conversation.jsonl",
        "episode_request.json",
        "episode_result.json",
        "environment_prepared_episode_request.json",
        "environment_prepared_episode_result.json",
        "environment_prepared_rejected_episode_result.json",
        "lifecycle_ledger.jsonl",
        "metrics.json",
        "raw_output.md",
        "rejected_episode_result.json",
        "result.json",
        "state.json",
        "submission.json",
        "trajectory.jsonl",
        "verification.json",
    }
    for path in sorted(run_dir.rglob("*")):
        relative = path.relative_to(run_dir)
        requested_evidence = (
            relative.parts[:1] == ("evidence_requests",)
            or (relative.parts[:2] == ("workspace", "inbox") and "requests" in relative.parts[2:])
            or (relative.parts[:2] == ("workspace", "checkpoints") and path.name == "evidence-requests.json")
        )
        operation_evidence = (
            relative.parts[:1] == ("lifecycle_operations",)
            or (relative.parts[:2] == ("workspace", "inbox") and "operations" in relative.parts[2:])
            or (relative.parts[:2] == ("workspace", "checkpoints") and path.name == "operations.json")
            or relative.parts == ("workspace", "operations", "current-source.json")
        )
        if (
            is_lifecycle_regular_file(root=run_dir, path=path)
            and (path.name in names or requested_evidence or operation_evidence)
            and "experiments" not in relative.parts
        ):
            selected[str(relative)] = _sha256(path)
    return selected


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    mkdir_durable(path.parent)
    lock_path = path.with_name(f".{path.name}.lock")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
