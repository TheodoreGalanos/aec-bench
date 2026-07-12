# ABOUTME: Records reproducible experiment manifests and normalized metrics for evidence lifecycles.
# ABOUTME: Binds repository, package, model interaction, verification, and run artifacts by hash.

from __future__ import annotations

import fcntl
import hashlib
import inspect
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from collections import deque
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import unquote, urlparse

from pydantic import Field, NonNegativeFloat, NonNegativeInt, PositiveInt

from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.ledger.durability import (
    fsync_directory as _fsync_directory,
)
from aec_bench.ledger.durability import (
    fsync_tree as _fsync_tree,
)
from aec_bench.ledger.durability import (
    mkdir_durable,
)
from aec_bench.meta_harness.evidence_lifecycle import (
    evidence_request_protocol_identity,
    read_evidence_lifecycle_state,
)
from aec_bench.meta_harness.evidence_lifecycle_metrics import LifecycleSemanticMetrics
from aec_bench.meta_harness.ledger import read_ledger
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_protocol_identity,
    validate_lifecycle_operation_tool_schema,
)
from aec_bench.task_world_templates.lifecycles import (
    lifecycle_package_variant,
    registered_lifecycle_verifier,
)


class LifecycleExperimentMetrics(StrictModel):
    schema_version: Literal["1", "2", "3"] = "3"
    checkpoint_count: NonNegativeInt
    requests: NonNegativeInt
    tool_calls: NonNegativeInt
    reads: NonNegativeInt
    revisits: NonNegativeInt
    evidence_request_calls: NonNegativeInt = 0
    accepted_evidence_requests: NonNegativeInt = 0
    already_released_evidence_requests: NonNegativeInt = 0
    rejected_evidence_requests: NonNegativeInt = 0
    evidence_request_budget_consumed: NonNegativeInt = 0
    evidence_request_artifacts_released: NonNegativeInt = 0
    operation_calls: NonNegativeInt = 0
    completed_operations: NonNegativeInt = 0
    already_current_operations: NonNegativeInt = 0
    rejected_operations: NonNegativeInt = 0
    operation_budget_consumed: NonNegativeInt = 0
    operation_artifacts_produced: NonNegativeInt = 0
    retries: NonNegativeInt
    failures: NonNegativeInt
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    cache_read_tokens: NonNegativeInt
    cache_write_tokens: NonNegativeInt
    estimated_cost_usd: NonNegativeFloat | None = None
    checkpoint_seconds: dict[str, NonNegativeFloat] = Field(default_factory=dict)
    whole_run_seconds: NonNegativeFloat | None = None
    semantic_transition: LifecycleSemanticMetrics | None = None


_V3_OPERATION_METRIC_FIELDS = (
    "operation_calls",
    "completed_operations",
    "already_current_operations",
    "rejected_operations",
    "operation_budget_consumed",
    "operation_artifacts_produced",
)


def lifecycle_experiment_metrics_payload(metrics: LifecycleExperimentMetrics) -> dict[str, Any]:
    """Preserve each metrics version's exact public field projection."""
    payload = metrics.model_dump(mode="json")
    if metrics.schema_version != "3":
        for field_name in _V3_OPERATION_METRIC_FIELDS:
            payload.pop(field_name)
    return payload


class LifecycleExperimentSweepContext(StrictModel):
    schema_version: Literal["1"] = "1"
    sweep_experiment_id: NonEmptyStr
    planned_trial_id: NonEmptyStr
    plan_sha256: NonEmptyStr
    condition_id: NonEmptyStr
    repetition: PositiveInt


class LifecycleExperimentManifest(StrictModel):
    schema_version: NonEmptyStr = "1"
    experiment_id: NonEmptyStr
    created_at: NonEmptyStr
    repository: dict[str, Any]
    environment: dict[str, Any]
    lifecycle: dict[str, Any]
    verifier: dict[str, Any]
    model: dict[str, Any]
    execution: dict[str, Any]
    interaction: dict[str, Any]
    outputs: dict[str, Any]
    sweep: LifecycleExperimentSweepContext | None = None


_REALIZED_FILE_DIGESTS: dict[Path, tuple[tuple[int, int, int, int, int], str]] = {}
_REQUIREMENT_PATTERN = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[([^]]+)\])?")
_EXTRA_MARKER_PATTERN = re.compile(r"\bextra\s*==\s*(['\"])([^'\"]+)\1")
_OPENAI_COMPATIBLE_PROVIDERS = {
    "alibaba",
    "azure",
    "cerebras",
    "deepseek",
    "fireworks",
    "github",
    "grok",
    "heroku",
    "litellm",
    "moonshotai",
    "nebius",
    "ollama",
    "openai",
    "openai-chat",
    "openai-responses",
    "ovhcloud",
    "sambanova",
    "together",
    "vercel",
}


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
    sweep_context: LifecycleExperimentSweepContext | None = None,
) -> dict[str, Any]:
    """Write one self-contained run record and append its immutable index entry."""
    package = Path(package_dir)
    run = Path(run_dir)
    verification_path = run / "verification.json"
    metrics_path = run / "metrics.json"
    manifest_path = run / "experiment-manifest.json"
    selected_index = index_path or run.parent / "experiment-index.jsonl"
    variant = _package_variant(package)
    lifecycle_state = read_evidence_lifecycle_state(package, run)
    operation_tool_declared = any(tool.get("name") == "execute_operation" for tool in tool_schema)
    if lifecycle_state.get("schema_version") == "5" or operation_tool_declared:
        validate_lifecycle_operation_tool_schema(tool_schema)
    _write_json(verification_path, verification)

    metrics = _build_metrics(run, agent, verification)
    metrics_payload = lifecycle_experiment_metrics_payload(metrics)
    if metrics.semantic_transition is None:
        metrics_payload.pop("semantic_transition")
    _write_json(metrics_path, metrics_payload)
    trajectories = sorted(run.glob("**/trajectory.jsonl"))
    prompts = _interaction_prompts(trajectories)
    repository = repository_provenance(repository_dir or Path(__file__).resolve().parent)
    runtime_provenance = runtime_dependency_provenance(
        adapter_kind=str(agent["adapter"]),
        model_name=str(agent["model"]),
    )
    state = _read_json(run / "state.json")
    experiment_id = f"lifecycle-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}"
    output_hashes = _run_artifact_hashes(run)
    lifecycle_manifest = {
        "lifecycle_id": state["lifecycle_id"],
        "world_id": state["world_id"],
        "spec_sha256": state["lifecycle_spec_sha256"],
        "package_sha256": state["package_sha256"],
        "package_files": _tree_hashes(package),
    }
    if variant is not None:
        lifecycle_manifest["variant"] = variant
    verifier_entrypoint = _callable_provenance(verifier)
    registered_verifier = verifier_entrypoint
    template_path = package / "template.json"
    if template_path.is_file():
        template_id = _read_json(template_path).get("template_id")
        if isinstance(template_id, str):
            try:
                registered_verifier = _callable_provenance(registered_lifecycle_verifier(template_id))
            except KeyError:
                pass
    verifier_chain = [verifier_entrypoint]
    if registered_verifier != verifier_entrypoint:
        verifier_chain.append(registered_verifier)
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
    manifest = LifecycleExperimentManifest(
        experiment_id=experiment_id,
        created_at=datetime.now(UTC).isoformat(),
        repository=repository,
        environment={
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "runtime_provenance": runtime_provenance,
        },
        lifecycle=lifecycle_manifest,
        verifier={
            **registered_verifier,
            "entrypoint": verifier_entrypoint,
            "chain": verifier_chain,
        },
        model={
            "requested_model": agent["model"],
            "resolved_models": sorted(
                {str(session.get("resolved_model") or agent["model"]) for session in agent.get("sessions", [])}
            ),
            "adapter": agent["adapter"],
            "requested_adapter": agent["adapter"],
            "resolved_adapters": agent.get("resolved_adapters", []),
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
        interaction=interaction,
        outputs={
            "verification.json": _sha256(verification_path),
            "metrics.json": _sha256(metrics_path),
            "artifacts": output_hashes,
        },
        sweep=sweep_context,
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
    }


def _build_metrics(
    run_dir: Path,
    agent: dict[str, Any],
    verification: dict[str, Any],
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


def runtime_dependency_provenance(
    *,
    adapter_kind: str,
    model_name: str,
    search_paths: tuple[Path, ...] | None = None,
) -> dict[str, Any]:
    """Hash the realized runtime distributions used by one lifecycle condition."""
    if adapter_kind not in {"in_process", "tool_loop", "pydantic_ai"}:
        raise ValueError(f"unsupported lifecycle runtime adapter: {adapter_kind}")

    provider = _resolve_runtime_provider(adapter_kind, model_name)
    roots = tuple(Path(path).resolve() for path in (search_paths or _runtime_distribution_search_paths()))
    if not roots:
        raise ValueError("lifecycle runtime distribution search path is unavailable")
    distributions: dict[str, importlib_metadata.Distribution] = {}
    for root in roots:
        for candidate_distribution in importlib_metadata.distributions(path=[str(root)]):
            raw_name = candidate_distribution.metadata.get("Name")
            if raw_name:
                distributions.setdefault(_canonicalize_distribution_name(str(raw_name)), candidate_distribution)
    selected = _runtime_distribution_closure(distributions, adapter_kind, provider)
    digest = hashlib.sha256()
    identities: list[str] = []
    for name in sorted(selected):
        distribution = distributions.get(name)
        if distribution is None:
            identity = f"{name}==missing"
            identities.append(identity)
            _update_inventory_digest(digest, f"distribution/{name}", identity.encode("utf-8"))
            continue
        identity = f"{name}=={distribution.version}"
        identities.append(identity)
        _update_inventory_digest(digest, f"distribution/{name}", identity.encode("utf-8"))
        entries = _realized_distribution_entries(name, distribution)
        if not entries:
            raise ValueError(f"runtime distribution has no hashable realized files: {identity}")
        for relative, file_sha256 in entries:
            _update_inventory_digest(
                digest,
                f"distribution/{name}/{relative}",
                bytes.fromhex(file_sha256),
            )
    return {
        "adapter": adapter_kind,
        "provider": provider,
        "distributions": sorted(identities),
        "dependency_inventory_sha256": digest.hexdigest(),
    }


def _runtime_distribution_search_paths() -> tuple[Path, ...]:
    roots: list[Path] = []
    for raw_path in sys.path:
        candidate = Path(raw_path or os.getcwd()).resolve()
        if not candidate.is_dir() or not any(candidate.glob("*.dist-info")):
            continue
        if candidate not in roots:
            roots.append(candidate)
    return tuple(roots)


def _runtime_distribution_closure(
    distributions: dict[str, importlib_metadata.Distribution],
    adapter_kind: str,
    provider: str,
) -> dict[str, set[str]]:
    if adapter_kind == "in_process":
        seeds: dict[str, set[str]] = {"pydantic": set(), "pyyaml": set()}
    else:
        provider_extras, provider_distributions = _runtime_provider_dependencies(provider)
        seeds = {
            "httpx": set(),
            "pydantic": set(),
            "pydantic-ai": set(),
            "pydantic-ai-slim": provider_extras,
            "pyyaml": set(),
        }
        seeds.update({name: set() for name in provider_distributions})
    queue = deque((_canonicalize_distribution_name(name), extras) for name, extras in seeds.items())
    selected: dict[str, set[str]] = {}
    while queue:
        name, requested_extras = queue.popleft()
        if name in selected and requested_extras <= selected[name]:
            continue
        active_extras = selected.setdefault(name, set())
        active_extras.update(requested_extras)
        distribution = distributions.get(name)
        if distribution is None or name == "pydantic-ai":
            continue
        for raw_requirement in distribution.requires or ():
            parsed = _parse_distribution_requirement(raw_requirement, active_extras)
            if parsed is None:
                continue
            requirement_name, requirement_extras = parsed
            queue.append((requirement_name, requirement_extras))
    return selected


def _resolve_runtime_provider(adapter_kind: str, model_name: str) -> str:
    if adapter_kind == "in_process":
        return "in_process"
    from aec_bench.adapters.rlm.providers import resolve_pydantic_provider

    provider = resolve_pydantic_provider(model_name)
    if provider == "auto" and ":" in model_name:
        provider = model_name.split(":", maxsplit=1)[0]
    return "google-vertex" if provider == "vertexai" else provider


def _runtime_provider_dependencies(provider: str) -> tuple[set[str], set[str]]:
    selected = provider.removeprefix("gateway/")
    selected = {
        "chat": "openai",
        "converse": "bedrock",
        "gemini": "google-gla",
        "responses": "openai",
    }.get(selected, selected)
    if selected == "auto":
        return set(), set()
    if selected in _OPENAI_COMPATIBLE_PROVIDERS:
        return {"openai"}, {"openai"}
    mapping: dict[str, tuple[set[str], set[str]]] = {
        "anthropic": ({"anthropic"}, {"anthropic"}),
        "bedrock": ({"bedrock"}, {"boto3", "botocore"}),
        "cohere": ({"cohere"}, {"cohere"}),
        "google-gla": ({"google"}, {"google-genai"}),
        "google-vertex": ({"google", "vertexai"}, {"google-auth", "google-genai"}),
        "groq": ({"groq"}, {"groq"}),
        "huggingface": ({"huggingface"}, {"huggingface-hub"}),
        "mistral": ({"mistral"}, {"mistralai"}),
        "openrouter": ({"openrouter"}, {"openai"}),
        "sentence-transformers": ({"sentence-transformers"}, {"sentence-transformers"}),
        "voyageai": ({"voyageai"}, {"voyageai"}),
        "xai": ({"xai"}, {"xai-sdk"}),
    }
    try:
        return mapping[selected]
    except KeyError as exc:
        raise ValueError(f"unsupported lifecycle runtime provider dependency mapping: {provider}") from exc


def _canonicalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_distribution_requirement(raw_requirement: str, active_extras: set[str]) -> tuple[str, set[str]] | None:
    requirement, separator, marker = raw_requirement.partition(";")
    match = _REQUIREMENT_PATTERN.match(requirement)
    if match is None:
        raise ValueError(f"runtime distribution requirement is malformed: {raw_requirement}")
    if separator and "extra" in marker:
        marker_extras = {match.group(2) for match in _EXTRA_MARKER_PATTERN.finditer(marker)}
        if not marker_extras:
            raise ValueError(f"runtime distribution extra marker is unsupported: {raw_requirement}")
        if not active_extras.intersection(marker_extras):
            return None
    extras = {extra.strip() for extra in (match.group(2) or "").split(",") if extra.strip()}
    return _canonicalize_distribution_name(match.group(1)), extras


def _realized_distribution_entries(
    name: str,
    distribution: importlib_metadata.Distribution,
) -> list[tuple[str, str]]:
    entries: dict[str, str] = {}
    for package_path in distribution.files or ():
        relative = package_path.as_posix()
        if "__pycache__" in package_path.parts or package_path.suffix == ".pyc":
            continue
        path = Path(str(distribution.locate_file(package_path)))
        if path.is_file():
            entries[relative] = _realized_file_sha256(path)
        else:
            entries[relative] = hashlib.sha256(b"missing-realized-file").hexdigest()
    if not entries:
        for metadata_name in ("METADATA", "WHEEL", "entry_points.txt", "direct_url.json", "RECORD"):
            content = distribution.read_text(metadata_name)
            if content is not None:
                entries[f"metadata/{metadata_name}"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        root = Path(str(distribution.locate_file("")))
        candidates = _distribution_top_level_names(name, distribution)
        for candidate in candidates:
            package = root / candidate
            if package.is_file():
                entries[f"package/{candidate}"] = _realized_file_sha256(package)
            elif package.is_dir():
                for path in _runtime_source_files(package):
                    relative = path.relative_to(package).as_posix()
                    entries[f"package/{candidate}/{relative}"] = _realized_file_sha256(path)
    direct_url = distribution.read_text("direct_url.json")
    if direct_url is not None:
        entries.update(_editable_distribution_entries(name, direct_url))
    return sorted(entries.items())


def _distribution_top_level_names(
    name: str,
    distribution: importlib_metadata.Distribution,
) -> tuple[str, ...]:
    declared = distribution.read_text("top_level.txt") or ""
    names = {line.strip() for line in declared.splitlines() if line.strip()}
    names.add(name.replace("-", "_"))
    return tuple(sorted(names))


def _editable_distribution_entries(name: str, direct_url: str) -> dict[str, str]:
    try:
        payload = json.loads(direct_url)
    except json.JSONDecodeError as exc:
        raise ValueError(f"runtime distribution direct_url.json is malformed: {name}") from exc
    if not isinstance(payload, dict) or not bool(payload.get("dir_info", {}).get("editable")):
        return {}
    parsed = urlparse(str(payload.get("url") or ""))
    if parsed.scheme != "file":
        raise ValueError(f"editable runtime distribution has unsupported source URL: {name}")
    source = Path(unquote(parsed.path)).resolve()
    if not source.is_dir():
        raise ValueError(f"editable runtime distribution source is unavailable: {name}")
    return {
        f"editable/{path.relative_to(source).as_posix()}": _realized_file_sha256(path)
        for path in _runtime_source_files(source)
    }


def _runtime_source_files(root: Path) -> list[Path]:
    excluded = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "build", "dist"}
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in excluded for part in path.relative_to(root).parts)
        and path.suffix != ".pyc"
    ]


def _realized_file_sha256(path: Path) -> str:
    stat = path.stat()
    signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    cached = _REALIZED_FILE_DIGESTS.get(path)
    if cached is not None and cached[0] == signature:
        return cached[1]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _REALIZED_FILE_DIGESTS[path] = (signature, digest)
    return digest


def _update_inventory_digest(digest: Any, label: str, payload: bytes) -> None:
    encoded_label = label.encode("utf-8")
    digest.update(len(encoded_label).to_bytes(8, "big"))
    digest.update(encoded_label)
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)


def repository_provenance(repository_dir: Path) -> dict[str, Any]:
    source_root = _source_inventory_root(repository_dir)
    source_package = _source_package_dir(source_root)
    try:
        root = _git(repository_dir, "rev-parse", "--show-toplevel").decode().strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _source_tree_provenance(source_root, source_package)
    root_path = Path(root)
    if not _source_package_is_tracked(root_path, source_package):
        return _source_tree_provenance(source_root, source_package)
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
        "source_inventory_sha256": _source_inventory_sha256(root_path, source_package),
        "repository_kind": "git",
    }


def _source_inventory_sha256(root: Path, source_package: Path | None = None) -> str:
    selected = [root / "pyproject.toml", root / "uv.lock"]
    source_root = source_package or _source_package_dir(root)
    if source_root.is_dir():
        selected.extend(
            path
            for path in source_root.rglob("*")
            if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
    for pattern in ("*.dist-info/METADATA", "*.dist-info/direct_url.json"):
        selected.extend(path for path in root.glob(pattern) if path.is_file() and not path.is_symlink())
    digest = hashlib.sha256()
    for path in sorted(path for path in selected if path.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _source_tree_provenance(root: Path, source_package: Path) -> dict[str, Any]:
    inventory = _source_inventory_sha256(root, source_package)
    return {
        "root": str(root),
        "commit": f"source-sha256:{inventory}",
        "dirty": False,
        "dirty_digest": hashlib.sha256(b"").hexdigest(),
        "source_inventory_sha256": inventory,
        "repository_kind": "source_tree",
    }


def _source_package_dir(root: Path) -> Path:
    source = root / "src" / "aec_bench"
    return source if source.is_dir() else root / "aec_bench"


def _source_package_is_tracked(repository_root: Path, package_dir: Path) -> bool:
    try:
        relative = (package_dir / "__init__.py").resolve().relative_to(repository_root.resolve())
        _git(repository_root, "ls-files", "--error-unmatch", "--", relative.as_posix())
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        return False
    return True


def _source_inventory_root(repository_dir: Path) -> Path:
    candidate = Path(repository_dir).resolve()
    for parent in (candidate, *candidate.parents):
        if (parent / "src" / "aec_bench").is_dir() or (parent / "aec_bench").is_dir():
            return parent
        if parent.name == "aec_bench" and parent.is_dir():
            return parent.parent
    raise ValueError(f"aec_bench source inventory is unavailable from {repository_dir}")


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
            or relative.parts == ("workspace", "hydraulics", "current-source.json")
        )
        if (
            path.is_file()
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
