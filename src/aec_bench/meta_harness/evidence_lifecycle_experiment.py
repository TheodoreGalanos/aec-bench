# ABOUTME: Records reproducible experiment manifests and normalized metrics for evidence lifecycles.
# ABOUTME: Binds repository, package, model interaction, verification, and run artifacts by hash.

from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pydantic import Field, NonNegativeFloat, NonNegativeInt

from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.ledger import read_ledger


class LifecycleExperimentMetrics(StrictModel):
    schema_version: NonEmptyStr = "1"
    checkpoint_count: NonNegativeInt
    requests: NonNegativeInt
    tool_calls: NonNegativeInt
    reads: NonNegativeInt
    revisits: NonNegativeInt
    retries: NonNegativeInt
    failures: NonNegativeInt
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    cache_read_tokens: NonNegativeInt
    cache_write_tokens: NonNegativeInt
    estimated_cost_usd: NonNegativeFloat | None = None
    checkpoint_seconds: dict[str, NonNegativeFloat] = Field(default_factory=dict)
    whole_run_seconds: NonNegativeFloat | None = None


class LifecycleExperimentManifest(StrictModel):
    schema_version: NonEmptyStr = "1"
    experiment_id: NonEmptyStr
    created_at: NonEmptyStr
    repository: dict[str, Any]
    lifecycle: dict[str, Any]
    verifier: dict[str, Any]
    model: dict[str, Any]
    execution: dict[str, Any]
    interaction: dict[str, Any]
    outputs: dict[str, Any]


def record_lifecycle_experiment(
    *,
    package_dir: Path,
    run_dir: Path,
    agent: dict[str, Any],
    verifier: Any,
    verification: dict[str, Any],
    tool_schema: list[dict[str, Any]],
    repository_dir: Path | None = None,
    index_path: Path | None = None,
) -> dict[str, Any]:
    """Write one self-contained run record and append its immutable index entry."""
    package = Path(package_dir)
    run = Path(run_dir)
    verification_path = run / "verification.json"
    metrics_path = run / "metrics.json"
    manifest_path = run / "experiment-manifest.json"
    selected_index = index_path or run.parent / "experiment-index.jsonl"
    _write_json(verification_path, verification)

    metrics = _build_metrics(run, agent)
    _write_json(metrics_path, metrics.model_dump(mode="json"))
    trajectories = sorted(run.glob("**/trajectory.jsonl"))
    prompts = _interaction_prompts(trajectories)
    repository = _repository_provenance(repository_dir or Path.cwd())
    state = _read_json(run / "state.json")
    experiment_id = f"lifecycle-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}"
    output_hashes = _run_artifact_hashes(run)
    manifest = LifecycleExperimentManifest(
        experiment_id=experiment_id,
        created_at=datetime.now(UTC).isoformat(),
        repository=repository,
        lifecycle={
            "lifecycle_id": state["lifecycle_id"],
            "world_id": state["world_id"],
            "spec_sha256": state["lifecycle_spec_sha256"],
            "package_sha256": state["package_sha256"],
            "package_files": _tree_hashes(package),
        },
        verifier=_callable_provenance(verifier),
        model={
            "requested_model": agent["model"],
            "resolved_models": sorted(
                {str(session.get("resolved_model") or agent["model"]) for session in agent.get("sessions", [])}
            ),
            "adapter": agent["adapter"],
            "session_configurations": [
                session.get("configuration_record", {}) for session in agent.get("sessions", [])
            ],
            "provider_environment": _provider_environment(),
        },
        execution={
            "mode": agent["execution_mode"],
            "memory_visibility_policy": agent["memory_visibility_policy"],
            "max_turns_per_session": agent["max_turns_per_session"],
            "session_count": len(agent.get("sessions", [])),
            "status": agent["status"],
            "checkpoint_seconds": metrics.checkpoint_seconds,
            "whole_run_seconds": metrics.whole_run_seconds,
        },
        interaction={
            **prompts,
            "tool_schema": tool_schema,
            "trajectory_hashes": {str(path.relative_to(run)): _sha256(path) for path in trajectories},
        },
        outputs={
            "verification.json": _sha256(verification_path),
            "metrics.json": _sha256(metrics_path),
            "artifacts": output_hashes,
        },
    )
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    experiment_dir = run / "experiments" / experiment_id
    canonical_verification = experiment_dir / "verification.json"
    canonical_metrics = experiment_dir / "metrics.json"
    canonical_manifest = experiment_dir / "experiment-manifest.json"
    _write_json(canonical_verification, verification)
    _write_json(canonical_metrics, metrics.model_dump(mode="json"))
    _write_json(canonical_manifest, manifest.model_dump(mode="json"))
    manifest_sha256 = _sha256(canonical_manifest)
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
    _append_jsonl(selected_index, index_entry)
    return {
        "experiment_id": experiment_id,
        "manifest": str(manifest_path),
        "canonical_manifest": str(canonical_manifest),
        "manifest_sha256": manifest_sha256,
        "metrics": str(metrics_path),
        "verification": str(verification_path),
        "index": str(selected_index),
    }


def _build_metrics(run_dir: Path, agent: dict[str, Any]) -> LifecycleExperimentMetrics:
    trajectories = sorted(run_dir.glob("**/trajectory.jsonl"))
    entries = [entry for path in trajectories for entry in read_trajectory(path)]
    requests = sum(len({entry.step for entry in read_trajectory(path) if entry.step > 0}) for path in trajectories)
    tool_calls = [entry for entry in entries if entry.role == "tool_call"]
    state = _read_json(run_dir / "state.json")
    attempts = [attempt for checkpoint in state["checkpoint_runs"] for attempt in checkpoint.get("attempts", [])]
    timing = _lifecycle_timing(run_dir)
    totals = agent["totals"]
    resolved_model = next(
        (str(session["resolved_model"]) for session in agent.get("sessions", []) if session.get("resolved_model")),
        agent["model"],
    )
    cost = estimate_cost_usd(
        resolved_model,
        input_tokens=int(totals["input_tokens"]),
        output_tokens=int(totals["output_tokens"]),
        cache_read_tokens=int(totals["cache_read_tokens"]),
        cache_write_tokens=int(totals["cache_write_tokens"]),
    )
    return LifecycleExperimentMetrics(
        checkpoint_count=sum(checkpoint["status"] == "submitted" for checkpoint in state["checkpoint_runs"]),
        requests=requests,
        tool_calls=len(tool_calls),
        reads=sum(entry.tool_name == "read_workspace_file" for entry in tool_calls),
        revisits=sum(entry.tool_name == "revisit_checkpoint" for entry in tool_calls),
        retries=sum(max(0, len(checkpoint.get("attempts", [])) - 1) for checkpoint in state["checkpoint_runs"]),
        failures=sum(attempt["status"] == "failed" for attempt in attempts),
        input_tokens=int(totals["input_tokens"]),
        output_tokens=int(totals["output_tokens"]),
        cache_read_tokens=int(totals["cache_read_tokens"]),
        cache_write_tokens=int(totals["cache_write_tokens"]),
        estimated_cost_usd=cost,
        checkpoint_seconds=timing["checkpoint_seconds"],
        whole_run_seconds=timing["whole_run_seconds"],
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


def _repository_provenance(repository_dir: Path) -> dict[str, Any]:
    root = _git(repository_dir, "rev-parse", "--show-toplevel").decode().strip()
    root_path = Path(root)
    commit = _git(root_path, "rev-parse", "HEAD").decode().strip()
    status = _git(root_path, "status", "--porcelain=v1", "--untracked-files=all")
    diff = _git(root_path, "diff", "--binary", "HEAD")
    untracked = _git(root_path, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    digest = hashlib.sha256()
    digest.update(status)
    digest.update(diff)
    for raw_path in sorted(path for path in untracked if path):
        path = root_path / raw_path.decode()
        digest.update(raw_path)
        if path.is_file():
            digest.update(path.read_bytes())
    return {
        "root": str(root_path),
        "commit": commit,
        "dirty": bool(status.strip()),
        "dirty_digest": digest.hexdigest(),
    }


def _callable_provenance(verifier: Any) -> dict[str, Any]:
    source_path = inspect.getsourcefile(verifier)
    return {
        "qualified_name": f"{getattr(verifier, '__module__', '')}.{getattr(verifier, '__qualname__', repr(verifier))}",
        "source_path": source_path,
        "source_sha256": _sha256(Path(source_path)) if source_path and Path(source_path).is_file() else None,
    }


def _provider_environment() -> dict[str, str]:
    allowed = (
        "AWS_REGION",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_DEPLOYMENT_NAME_LM",
    )
    return {name: value for name in allowed if (value := os.getenv(name))}


def _run_artifact_hashes(run_dir: Path) -> dict[str, str]:
    selected: dict[str, str] = {}
    names = {"submission.json", "trajectory.jsonl", "conversation.jsonl", "agent_result.json"}
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and (path.name in names or path.name in {"verification.json", "metrics.json"}):
            selected[str(path.relative_to(run_dir))] = _sha256(path)
    return selected


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _git(cwd: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )
    return completed.stdout


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
