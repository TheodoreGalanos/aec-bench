# ABOUTME: Imports one validated evidence-lifecycle run into the core TrialRecord ledger contract.
# ABOUTME: Reconciles planned dimensions with package, run, verifier, metrics, and adaptation provenance.

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Literal, cast

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    AgentReference,
    ArtifactReference,
    Completeness,
    CostRecord,
    EnvironmentSnapshot,
    FileReference,
    InputRecord,
    LifecycleExecutionRecord,
    LifecycleSessionRecord,
    LifecycleTrialProvenance,
    OutputRecord,
    TaskReference,
    TimingRecord,
    TrialRecord,
)
from aec_bench.ledger.durability import (
    fsync_directory as _fsync_directory,
)
from aec_bench.ledger.durability import (
    fsync_tree as _fsync_tree,
)
from aec_bench.ledger.durability import (
    mkdir_durable,
)
from aec_bench.ledger.writer import DuplicateTrialRecordError, write_trial_record
from aec_bench.meta_harness.evidence_lifecycle import (
    evidence_request_catalog_payload,
    load_evidence_lifecycle_spec,
    read_evidence_lifecycle_state,
    validate_evidence_request_run_state,
    validate_lifecycle_verification,
)
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationManifest,
    LifecycleAblationPlan,
    LifecycleAblationTrial,
    build_lifecycle_ablation_plan,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleEpisodeRequest,
    LifecycleOperationCurrentSource,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import (
    LifecycleExperimentManifest,
    LifecycleExperimentMetrics,
    lifecycle_experiment_metrics_payload,
)
from aec_bench.meta_harness.evidence_lifecycle_state import (
    EvidenceLifecycleRunState,
    EvidenceRequestActionRecord,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    EvidenceLifecycleError,
    expected_evidence_request_run_artifact_paths,
    is_evidence_request_run_artifact_path,
)
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_protocol_identity,
    validate_lifecycle_operation_tool_schema,
)
from aec_bench.meta_harness.lifecycle_operation_snapshot import validate_lifecycle_operation_snapshot
from aec_bench.meta_harness.lifecycle_operation_store import (
    resolve_lifecycle_operation_current_source,
    validate_lifecycle_operation_resolver_replay,
)
from aec_bench.task_world_templates.contracts import EvidenceLifecycleSpec
from aec_bench.task_world_templates.lifecycles import (
    is_sealed_lifecycle_package,
    lifecycle_package_variant,
)


@dataclass(frozen=True)
class _CanonicalInvocation:
    manifest_path: Path
    manifest: dict[str, Any]
    metrics_path: Path
    verification_path: Path
    index_entry: dict[str, Any]


_INDEX_LOCKS_GUARD = Lock()
_INDEX_LOCKS: dict[str, Lock] = {}


def build_lifecycle_trial_record(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    package_dir: Path,
    run_dir: Path,
    artifact_references: list[ArtifactReference] | None = None,
) -> TrialRecord:
    """Build one validated record from the planned working package and canonical invocation."""
    return _build_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=package_dir,
        run_dir=run_dir,
        artifact_references=artifact_references,
        require_planned_paths=True,
        plan=None,
    )


def _build_lifecycle_trial_record(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    package_dir: Path,
    run_dir: Path,
    artifact_references: list[ArtifactReference] | None,
    require_planned_paths: bool,
    plan: LifecycleAblationPlan | None,
) -> TrialRecord:
    """Build a core record from a validated working tree or immutable snapshot."""
    package = Path(package_dir)
    if is_sealed_lifecycle_package(package):
        raise ValueError("sealed_holdout_public_record_forbidden")
    run = Path(run_dir)
    if require_planned_paths and package.resolve() != Path(trial.package_dir).resolve():
        raise ValueError("supplied package directory does not match planned trial")
    if require_planned_paths and run.resolve() != Path(trial.run_dir).resolve():
        raise ValueError("supplied run directory does not match planned trial")

    if require_planned_paths:
        read_evidence_lifecycle_state(package, run)
    else:
        _validate_snapshotted_lifecycle_state(package, run)
    state = _read_json(run / "state.json")
    variant = lifecycle_package_variant(package)
    if variant is None or variant.get("variant_id") != trial.variant_id:
        raise ValueError("lifecycle package variant does not match planned trial")
    if AdaptationProvenance.model_validate(variant.get("adaptation")) != trial.adaptation:
        raise ValueError("lifecycle package adaptation does not match planned trial")

    invocation = _canonical_invocation(run, manifest, trial)
    experiment = invocation.manifest
    verification = validate_lifecycle_verification(_read_json(invocation.verification_path))
    metrics = lifecycle_experiment_metrics_payload(
        LifecycleExperimentMetrics.model_validate(_read_json(invocation.metrics_path))
    )
    _validate_artifact_hash(
        invocation.verification_path,
        experiment.get("outputs", {}).get("verification.json"),
        "lifecycle verification",
    )
    _validate_artifact_hash(
        invocation.metrics_path,
        experiment.get("outputs", {}).get("metrics.json"),
        "lifecycle metrics",
    )
    _validate_artifact_hash(
        run / "verification.json",
        experiment.get("outputs", {}).get("verification.json"),
        "lifecycle verification",
    )
    _validate_artifact_hash(
        run / "metrics.json",
        experiment.get("outputs", {}).get("metrics.json"),
        "lifecycle metrics",
    )
    _validate_declared_run_artifacts(run, experiment)
    _validate_metrics_against_run(run, state, experiment, metrics, verification)
    lifecycle = experiment.get("lifecycle", {})
    if lifecycle.get("package_sha256") != state.get("package_sha256"):
        raise ValueError("lifecycle experiment package hash does not match run state")
    expected_lifecycle = {
        "lifecycle_id": trial.lifecycle_id,
        "world_id": trial.world_id,
        "spec_sha256": trial.spec_sha256,
        "package_sha256": trial.package_sha256,
    }
    if any(lifecycle.get(key) != value for key, value in expected_lifecycle.items()):
        raise ValueError("lifecycle experiment identity does not match planned package revision")
    expected_state = {
        "lifecycle_id": trial.lifecycle_id,
        "world_id": trial.world_id,
        "lifecycle_spec_sha256": trial.spec_sha256,
        "package_sha256": trial.package_sha256,
    }
    if any(state.get(key) != value for key, value in expected_state.items()):
        raise ValueError("lifecycle run state does not match planned package revision")
    if verification.get("lifecycle_id") != trial.lifecycle_id:
        raise ValueError("lifecycle verification does not match planned lifecycle")
    if lifecycle.get("variant") != variant:
        raise ValueError("lifecycle experiment variant does not match package")
    if not isinstance(variant, dict) or not isinstance(variant.get("visibility"), str):
        raise ValueError("lifecycle package variant visibility is missing")
    try:
        task_visibility = Visibility(variant["visibility"])
    except ValueError as exc:
        raise ValueError("lifecycle package variant visibility is invalid") from exc

    model = experiment.get("model", {})
    execution = experiment.get("execution", {})
    if model.get("requested_model") != trial.agent.model:
        raise ValueError("lifecycle run model does not match planned trial")
    if model.get("requested_adapter", model.get("adapter")) != trial.agent.adapter:
        raise ValueError("lifecycle run adapter does not match planned trial")
    if execution.get("mode") != trial.execution_mode.value:
        raise ValueError("lifecycle run execution mode does not match planned trial")
    if execution.get("memory_visibility_policy") != trial.memory_visibility_policy.value:
        raise ValueError("lifecycle run visibility policy does not match planned trial")
    if execution.get("max_turns_per_session") != trial.max_turns_per_session:
        raise ValueError("lifecycle run turn limit does not match planned trial")

    selected_plan = plan or build_lifecycle_ablation_plan(manifest)
    planned = {item.trial_id: item for item in selected_plan.trials}.get(trial.trial_id)
    if planned != trial:
        raise ValueError("trial does not match the deterministic ablation plan")
    expected_sweep = {
        "schema_version": "1",
        "sweep_experiment_id": manifest.experiment_id,
        "planned_trial_id": trial.trial_id,
        "plan_sha256": selected_plan.plan_sha256,
        "condition_id": f"{trial.execution_mode.value}__{trial.memory_visibility_policy.value}",
        "repetition": trial.repetition,
    }
    if experiment.get("sweep") != expected_sweep:
        raise ValueError("lifecycle sweep context does not match planned trial")

    repository = experiment.get("repository", {})
    runtime_environment = experiment.get("environment", {})
    python_version = runtime_environment.get("python_version")
    if not isinstance(python_version, str) or not python_version:
        raise ValueError("lifecycle invocation Python version is missing")
    code_provenance = selected_plan.code_provenance
    if (
        repository.get("commit") != code_provenance.repository_commit
        or repository.get("source_inventory_sha256") != code_provenance.source_inventory_sha256
    ):
        raise ValueError("lifecycle invocation repository does not match planned code provenance")
    runtime_provenance = runtime_environment.get("runtime_provenance")
    if runtime_provenance != trial.runtime_provenance.model_dump(mode="json"):
        raise ValueError("lifecycle invocation runtime dependencies do not match planned trial")
    planned_verifier = experiment.get("verifier", {})
    verifier_entrypoint = planned_verifier.get("entrypoint") if isinstance(planned_verifier, dict) else None
    if not isinstance(planned_verifier, dict) or (
        planned_verifier.get("qualified_name") != code_provenance.verifier_qualified_name
        or planned_verifier.get("source_sha256") != code_provenance.verifier_source_sha256
    ):
        raise ValueError("lifecycle invocation verifier does not match planned task verifier")
    if not isinstance(verifier_entrypoint, dict) or (
        verifier_entrypoint.get("qualified_name") != code_provenance.verifier_entrypoint_qualified_name
        or verifier_entrypoint.get("source_sha256") != code_provenance.verifier_entrypoint_source_sha256
    ):
        raise ValueError("lifecycle invocation verifier entrypoint does not match planned provenance")
    repository_commit = str(repository.get("commit") or "unknown")
    package_files = lifecycle.get("package_files")
    if not isinstance(package_files, dict) or not package_files:
        raise ValueError("lifecycle experiment must contain package file hashes")
    if package_files != _tree_hashes(package):
        raise ValueError("lifecycle package files do not match canonical manifest")
    input_files = [
        FileReference(path=str(path), hash=str(digest), source="lifecycle_package")
        for path, digest in sorted(package_files.items())
    ]
    instruction = _lifecycle_instruction(package)
    execution_status = str(execution.get("status") or "failed")
    agent_status = AgentOutputStatus.COMPLETED if execution_status == "completed" else AgentOutputStatus.FAILED
    output_structurally_valid = state.get("status") == "complete"
    verifier_completed = verification.get("overall") != "incomplete"
    errors = _verification_failures(verification)
    semantic_transition = metrics.get("semantic_transition")
    operational_metrics = {key: value for key, value in metrics.items() if key != "semantic_transition"}
    trajectories = sorted(str(path) for path in run.glob("**/trajectory.jsonl"))
    conversations = sorted(str(path) for path in run.glob("**/conversation.jsonl"))
    raw_outputs = sorted(str(path) for path in run.glob("**/raw_output.md"))
    totals = {
        "tokens_in": int(metrics.get("input_tokens", 0)),
        "tokens_out": int(metrics.get("output_tokens", 0)),
        "cache_read_tokens": int(metrics.get("cache_read_tokens", 0)),
        "cache_write_tokens": int(metrics.get("cache_write_tokens", 0)),
    }
    total_seconds = float(metrics.get("whole_run_seconds") or 0.0)
    created_at = str(experiment.get("created_at"))
    artifacts = list(artifact_references or [])
    if artifacts:
        input_files = [
            FileReference(
                path=_snapshotted_package_path(artifacts, item.path),
                hash=item.hash,
                source=item.path,
            )
            for item in input_files
        ]
    invocation_manifest = next(
        (artifact for artifact in artifacts if artifact.kind == "lifecycle_manifest"),
        ArtifactReference(
            kind="lifecycle_manifest",
            path=str(invocation.manifest_path),
            sha256=_sha256(invocation.manifest_path),
            media_type="application/json",
        ),
    )
    invocation_index = _artifact_by_kind(artifacts, "lifecycle_invocation_index")
    ablation_manifest = _artifact_by_kind(artifacts, "lifecycle_ablation_manifest")
    ablation_plan = _artifact_by_kind(artifacts, "lifecycle_ablation_plan")
    sessions = _lifecycle_sessions(
        run,
        artifacts,
        state=state,
        experiment=experiment,
        metrics=metrics,
        verification=verification,
    )
    resolved_models = {session.resolved_model for session in sessions if session.resolved_model != "unresolved"}
    resolved_model = next(iter(resolved_models)) if resolved_models else "unresolved"
    resolved_adapters = {session.adapter for session in sessions if session.adapter != "unresolved"}
    resolved_adapter = next(iter(resolved_adapters)) if resolved_adapters else "unresolved"
    verifier = experiment.get("verifier", {})
    verifier_source_sha256 = verifier.get("source_sha256")
    if not isinstance(verifier_source_sha256, str):
        raise ValueError("lifecycle verifier source hash is missing")
    repository_kind = repository.get("repository_kind", "git")
    if repository_kind not in {"git", "source_tree"}:
        raise ValueError("lifecycle repository provenance kind is invalid")
    execution_record = LifecycleExecutionRecord(
        execution_mode=trial.execution_mode.value,
        memory_visibility_policy=trial.memory_visibility_policy.value,
        max_turns_per_session=int(execution.get("max_turns_per_session") or 1),
        status=_execution_status(execution_status),
        sessions=sessions,
    )
    lifecycle_provenance = LifecycleTrialProvenance(
        lifecycle_id=str(lifecycle["lifecycle_id"]),
        world_id=str(lifecycle["world_id"]),
        spec_sha256=str(lifecycle["spec_sha256"]),
        package_sha256=str(lifecycle["package_sha256"]),
        repository_commit=repository_commit,
        repository_kind=cast(Literal["git", "source_tree"], repository_kind),
        repository_dirty=bool(repository.get("dirty")),
        repository_dirty_digest=str(repository["dirty_digest"]),
        runtime_provider=trial.runtime_provenance.provider,
        runtime_distributions=trial.runtime_provenance.distributions,
        runtime_dependency_sha256=trial.runtime_provenance.dependency_inventory_sha256,
        verifier_qualified_name=str(verifier["qualified_name"]),
        verifier_source_sha256=verifier_source_sha256,
        invocation_manifest=invocation_manifest,
        invocation_index=invocation_index,
        ablation_manifest=ablation_manifest,
        ablation_plan=ablation_plan,
    )
    raw_output_refs = [artifact.path for artifact in artifacts if artifact.kind == "raw_output"]
    conversation_refs = [artifact.path for artifact in artifacts if artifact.kind == "conversation"]
    trajectory_refs = [artifact.path for artifact in artifacts if artifact.kind == "trajectory"]
    if artifacts:
        trajectories = trajectory_refs
        conversations = conversation_refs
        raw_outputs = raw_output_refs
    verification_reference = _artifact_by_kind(artifacts, "lifecycle_verification")
    metrics_reference = _artifact_by_kind(artifacts, "lifecycle_metrics")
    raw_output_path = _single_path(raw_output_refs, raw_outputs)
    conversation_path = _single_path(conversation_refs, conversations)
    trajectory_path = _single_path(trajectory_refs, trajectories)

    return TrialRecord(
        trial_id=trial.trial_id,
        experiment_id=manifest.experiment_id,
        timestamp=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
        task=TaskReference(
            task_id=manifest.lifecycle_template_id,
            task_revision=str(state["package_sha256"]),
            visibility=task_visibility,
        ),
        agent=AgentReference(
            adapter=resolved_adapter,
            model=resolved_model,
            adapter_revision=repository_commit,
            configuration={
                "agent_name": trial.agent.name,
                "requested_model": trial.agent.model,
                "requested_adapter": trial.agent.adapter,
                "parameters": trial.agent.parameters,
                "variant_id": trial.variant_id,
                "execution_mode": trial.execution_mode.value,
                "memory_visibility_policy": trial.memory_visibility_policy.value,
                "repetition": trial.repetition,
                "manifest_sha256": selected_plan.manifest_sha256,
                "plan_sha256": selected_plan.plan_sha256,
                "resolved_models": model.get("resolved_models", []),
                "session_configurations": model.get("session_configurations", []),
                "lifecycle_experiment_id": experiment.get("experiment_id"),
                "lifecycle_manifest_sha256": _sha256(invocation.manifest_path),
                "package_sha256": state["package_sha256"],
            },
        ),
        environment=EnvironmentSnapshot(
            runtime_image=f"python:{python_version}",
            compute_backend="local",
            tool_versions={
                "aec_bench_commit": repository_commit,
                "python": python_version,
            },
        ),
        inputs=InputRecord(
            instruction=instruction,
            input_files=input_files,
        ),
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=agent_status,
                output_path=_artifact_output_root(trial, artifacts, run),
                output_format="evidence_lifecycle",
                error_message=None if agent_status is AgentOutputStatus.COMPLETED else "lifecycle execution failed",
            ),
            raw_output_path=raw_output_path,
            conversation_path=conversation_path,
            trajectory_path=trajectory_path,
            agent_result={
                "lifecycle_experiment_id": experiment.get("experiment_id"),
                "execution_status": execution_status,
                "verification_path": (
                    verification_reference.path
                    if verification_reference is not None
                    else str(invocation.verification_path)
                ),
                "metrics_path": metrics_reference.path
                if metrics_reference is not None
                else str(invocation.metrics_path),
                "manifest_path": invocation_manifest.path,
                "trajectories": trajectories,
                "conversations": conversations,
                "raw_outputs": raw_outputs,
            },
            artifacts=artifacts or None,
        ),
        evaluation=EvaluationResult(
            reward=float(verification["reward"]),
            validity=ValidityCheck(
                output_parseable=output_structurally_valid,
                schema_valid=output_structurally_valid and verifier_completed,
                verifier_completed=verifier_completed,
                errors=errors,
            ),
            breakdown={
                "lifecycle_gates": verification.get("gates", {}),
                "semantic_transition": semantic_transition,
                "operational_metrics": operational_metrics,
            },
        ),
        timing=TimingRecord(
            total_seconds=total_seconds,
            agent_seconds=total_seconds,
        ),
        cost=CostRecord(
            **totals,
            estimated_cost_usd=metrics.get("estimated_cost_usd"),
        ),
        adaptation=trial.adaptation,
        lifecycle_execution=execution_record,
        lifecycle_provenance=lifecycle_provenance,
        completeness=(
            Completeness.COMPLETE
            if (
                artifacts
                and sessions
                and all(session.resolved_model != "unresolved" for session in sessions)
                and all(session.adapter != "unresolved" for session in sessions)
                and repository.get("repository_kind") == "git"
                and not bool(repository.get("dirty"))
            )
            else Completeness.PARTIAL
        ),
    )


def finalize_lifecycle_trial_record(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    package_dir: Path,
    run_dir: Path,
) -> Path:
    """Snapshot immutable lifecycle artifacts and append exactly one core record."""
    if is_sealed_lifecycle_package(package_dir):
        raise ValueError("sealed_holdout_public_record_forbidden")
    record_path = Path(trial.ledger_path)
    if record_path.exists():
        raise DuplicateTrialRecordError(f"trial record already exists: {record_path}")
    ledger_root = Path(manifest.ledger_root)
    artifact_dir = ledger_root / manifest.experiment_id / "_artifacts" / trial.trial_id
    if artifact_dir.exists():
        record = _record_from_snapshot(
            manifest=manifest,
            trial=trial,
            artifact_dir=artifact_dir,
            ledger_root=ledger_root,
            plan=None,
        )
        return write_trial_record(ledger_root=ledger_root, record=record)
    _repair_shared_invocation_index(Path(run_dir), manifest, trial)
    mkdir_durable(artifact_dir.parent)
    staging = artifact_dir.with_name(f".{trial.trial_id}.staging-{uuid.uuid4().hex}")
    try:
        build_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=Path(package_dir),
            run_dir=Path(run_dir),
        )
        _stage_authoritative_snapshot(
            manifest=manifest,
            trial=trial,
            package_dir=Path(package_dir),
            run_dir=Path(run_dir),
            staging=staging,
        )
        _validate_snapshot_layout(staging, manifest, trial, plan=None)
        artifact_references = _snapshot_references(
            staging=staging,
            final=artifact_dir,
            ledger_root=ledger_root,
        )
        record = _build_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=staging / "package",
            run_dir=staging / "run",
            artifact_references=artifact_references,
            require_planned_paths=False,
            plan=None,
        )
        _fsync_tree(staging)
        staging.replace(artifact_dir)
        _fsync_directory(artifact_dir.parent)
        return write_trial_record(ledger_root=ledger_root, record=record)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def validate_lifecycle_ablation_record(
    record: TrialRecord,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> None:
    """Rebuild and compare one ledger record against its immutable planned snapshot."""
    plan = build_lifecycle_ablation_plan(manifest)
    planned = {item.trial_id: item for item in plan.trials}.get(trial.trial_id)
    if planned != trial:
        raise ValueError("existing TrialRecord does not match the deterministic ablation plan")
    if record.experiment_id != manifest.experiment_id or record.trial_id != trial.trial_id:
        raise ValueError("existing TrialRecord does not match the planned trial identity")
    ledger_root = Path(manifest.ledger_root)
    artifact_dir = ledger_root / manifest.experiment_id / "_artifacts" / trial.trial_id
    if not artifact_dir.is_dir():
        raise ValueError("existing TrialRecord does not have an immutable artifact snapshot")
    expected = _record_from_snapshot(
        manifest=manifest,
        trial=trial,
        artifact_dir=artifact_dir,
        ledger_root=ledger_root,
        plan=None,
    )
    if not _matches_historical_record(record, expected):
        raise ValueError("existing TrialRecord does not match its immutable lifecycle ablation snapshot")


def validate_lifecycle_ablation_snapshot(
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> TrialRecord:
    """Validate and reconstruct an unpublished immutable trial snapshot."""
    plan = build_lifecycle_ablation_plan(manifest)
    planned = {item.trial_id: item for item in plan.trials}.get(trial.trial_id)
    if planned != trial:
        raise ValueError("lifecycle snapshot does not match the deterministic ablation plan")
    ledger_root = Path(manifest.ledger_root)
    artifact_dir = ledger_root / manifest.experiment_id / "_artifacts" / trial.trial_id
    if not artifact_dir.is_dir():
        raise ValueError("lifecycle artifact snapshot does not exist")
    return _record_from_snapshot(
        manifest=manifest,
        trial=trial,
        artifact_dir=artifact_dir,
        ledger_root=ledger_root,
        plan=plan,
    )


def validate_historical_lifecycle_ablation_record(
    record: TrialRecord,
    manifest: LifecycleAblationManifest,
    plan: LifecycleAblationPlan,
    trial: LifecycleAblationTrial,
) -> None:
    """Validate one record against the plan captured at execution time."""
    planned = {item.trial_id: item for item in plan.trials}.get(trial.trial_id)
    if planned != trial:
        raise ValueError("historical TrialRecord does not match its snapshotted ablation plan")
    if record.experiment_id != manifest.experiment_id or record.trial_id != trial.trial_id:
        raise ValueError("historical TrialRecord does not match its snapshotted trial identity")
    ledger_root = Path(manifest.ledger_root)
    artifact_dir = ledger_root / manifest.experiment_id / "_artifacts" / trial.trial_id
    expected = _record_from_snapshot(
        manifest=manifest,
        trial=trial,
        artifact_dir=artifact_dir,
        ledger_root=ledger_root,
        plan=plan,
    )
    if not _matches_historical_record(record, expected):
        raise ValueError("historical TrialRecord does not match its immutable lifecycle ablation snapshot")


def _matches_historical_record(record: TrialRecord, expected: TrialRecord) -> bool:
    """Allow only the omitted visibility field used by records written before that field existed."""
    if record == expected:
        return True
    if record.task.visibility is not None or "visibility" in record.task.model_fields_set:
        return False
    legacy_expected = expected.model_copy(
        update={
            "task": expected.task.model_copy(update={"visibility": None}),
        }
    )
    return record == legacy_expected


def _record_from_snapshot(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    artifact_dir: Path,
    ledger_root: Path,
    plan: LifecycleAblationPlan | None,
) -> TrialRecord:
    _validate_snapshot_layout(artifact_dir, manifest, trial, plan=plan)
    artifacts = _snapshot_references(
        staging=artifact_dir,
        final=artifact_dir,
        ledger_root=ledger_root,
    )
    return _build_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=artifact_dir / "package",
        run_dir=artifact_dir / "run",
        artifact_references=artifacts,
        require_planned_paths=False,
        plan=plan,
    )


def _stage_authoritative_snapshot(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    package_dir: Path,
    run_dir: Path,
    staging: Path,
) -> None:
    invocation = _canonical_invocation(run_dir, manifest, trial)
    lifecycle = cast(dict[str, Any], invocation.manifest["lifecycle"])
    package_files = cast(dict[str, str], lifecycle["package_files"])
    outputs = cast(dict[str, Any], invocation.manifest["outputs"])
    run_files = cast(dict[str, str], outputs["artifacts"])
    for relative in sorted(package_files):
        _copy_declared_file(package_dir, staging / "package", relative)
    for relative in sorted(run_files):
        _copy_declared_file(run_dir, staging / "run", relative)

    experiment_id = str(invocation.manifest["experiment_id"])
    canonical_dir = staging / "run" / "experiments" / experiment_id
    canonical_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(invocation.manifest_path, canonical_dir / "experiment-manifest.json")
    shutil.copy2(invocation.metrics_path, canonical_dir / "metrics.json")
    shutil.copy2(invocation.verification_path, canonical_dir / "verification.json")

    normalized_seal = dict(invocation.index_entry)
    normalized_seal["manifest_path"] = "experiment-manifest.json"
    _write_json(canonical_dir / "index-entry.json", normalized_seal)
    normalized_index = dict(invocation.index_entry)
    normalized_index["manifest_path"] = f"run/experiments/{experiment_id}/experiment-manifest.json"
    _write_jsonl(staging / "experiment-index.jsonl", [normalized_index])

    plan = build_lifecycle_ablation_plan(manifest)
    persisted_manifest = Path(manifest.output_root) / "manifest.json"
    if persisted_manifest.is_file() and _read_json(persisted_manifest) != manifest.model_dump(mode="json"):
        raise ValueError("persisted ablation manifest does not match planned sweep")
    persisted_plan = Path(manifest.output_root) / "plan.json"
    if persisted_plan.is_file() and _read_json(persisted_plan) != plan.model_dump(mode="json"):
        raise ValueError("persisted ablation plan does not match planned sweep")
    _write_json(staging / "sweep" / "manifest.json", manifest.model_dump(mode="json"))
    _write_json(staging / "sweep" / "plan.json", plan.model_dump(mode="json"))


def _copy_declared_file(source_root: Path, destination_root: Path, raw_relative: str) -> None:
    relative = Path(raw_relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"declared artifact path is unsafe: {raw_relative}")
    source = source_root / relative
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"declared artifact source is not a regular file: {source}")
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _validate_snapshot_layout(
    artifact_dir: Path,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    *,
    plan: LifecycleAblationPlan | None,
) -> None:
    snapshot_manifest = LifecycleAblationManifest.model_validate(_read_json(artifact_dir / "sweep" / "manifest.json"))
    if snapshot_manifest != manifest:
        raise ValueError("artifact snapshot ablation manifest does not match requested sweep")
    expected_plan = plan or build_lifecycle_ablation_plan(manifest)
    snapshot_plan = LifecycleAblationPlan.model_validate(_read_json(artifact_dir / "sweep" / "plan.json"))
    if snapshot_plan != expected_plan:
        raise ValueError("artifact snapshot ablation plan does not match requested sweep")
    invocation = _canonical_invocation(artifact_dir / "run", manifest, trial)
    lifecycle = cast(dict[str, Any], invocation.manifest["lifecycle"])
    outputs = cast(dict[str, Any], invocation.manifest["outputs"])
    expected = {
        *(f"package/{relative}" for relative in cast(dict[str, str], lifecycle["package_files"])),
        *(f"run/{relative}" for relative in cast(dict[str, str], outputs["artifacts"])),
        f"run/experiments/{invocation.manifest['experiment_id']}/experiment-manifest.json",
        f"run/experiments/{invocation.manifest['experiment_id']}/metrics.json",
        f"run/experiments/{invocation.manifest['experiment_id']}/verification.json",
        f"run/experiments/{invocation.manifest['experiment_id']}/index-entry.json",
        "experiment-index.jsonl",
        "sweep/manifest.json",
        "sweep/plan.json",
    }
    actual = {path.relative_to(artifact_dir).as_posix() for path in artifact_dir.rglob("*") if path.is_file()}
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(f"artifact snapshot file set mismatch; missing={missing}, unexpected={unexpected}")


def _canonical_invocation(
    run_dir: Path,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> _CanonicalInvocation:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((run_dir / "experiments").glob("*/experiment-manifest.json")):
        if path.parent.name.startswith("."):
            continue
        payload = LifecycleExperimentManifest.model_validate(_read_json(path)).model_dump(mode="json")
        sweep = payload.get("sweep")
        if not isinstance(sweep, dict):
            continue
        if (
            sweep.get("sweep_experiment_id") == manifest.experiment_id
            and sweep.get("planned_trial_id") == trial.trial_id
        ):
            candidates.append((path, payload))
    if len(candidates) != 1:
        raise ValueError("expected exactly one canonical lifecycle invocation for planned trial")
    manifest_path, payload = candidates[0]
    experiment_id = str(payload["experiment_id"])
    seal_path = manifest_path.parent / "index-entry.json"
    index_path = run_dir.parent / "experiment-index.jsonl"
    seal_entry = _read_json(seal_path) if seal_path.is_file() else None
    if seal_entry is not None:
        _validate_invocation_index_entry(
            seal_entry,
            entry_path=seal_path,
            manifest_path=manifest_path,
            manifest=payload,
        )

    shared_entries: list[dict[str, Any]] | None = None
    if index_path.is_file():
        try:
            shared_entries = [entry for entry in _read_jsonl(index_path) if entry.get("experiment_id") == experiment_id]
        except (json.JSONDecodeError, ValueError):
            if seal_entry is None:
                raise
    if shared_entries is not None and len(shared_entries) > 1:
        raise ValueError("canonical lifecycle invocation must have at most one shared index entry")
    shared_entry = shared_entries[0] if shared_entries else None
    if shared_entry is not None:
        _validate_invocation_index_entry(
            shared_entry,
            entry_path=index_path,
            manifest_path=manifest_path,
            manifest=payload,
        )
    if (
        seal_entry is not None
        and shared_entry is not None
        and not _equivalent_index_entries(
            seal_entry,
            shared_entry,
        )
    ):
        raise ValueError("canonical lifecycle invocation seal conflicts with shared index entry")
    index_entry = seal_entry or shared_entry
    if index_entry is None:
        raise ValueError("canonical lifecycle invocation has no sealed or shared index entry")
    return _CanonicalInvocation(
        manifest_path=manifest_path,
        manifest=payload,
        metrics_path=manifest_path.parent / "metrics.json",
        verification_path=manifest_path.parent / "verification.json",
        index_entry=index_entry,
    )


def _validate_invocation_index_entry(
    entry: dict[str, Any],
    *,
    entry_path: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> None:
    if entry.get("experiment_id") != manifest.get("experiment_id"):
        raise ValueError("canonical lifecycle invocation id does not match index entry")
    indexed_path = Path(str(entry.get("manifest_path", "")))
    if not indexed_path.is_absolute():
        indexed_path = entry_path.parent / indexed_path
    if indexed_path.resolve() != manifest_path.resolve():
        raise ValueError("canonical lifecycle invocation path does not match index entry")
    if entry.get("manifest_sha256") != _sha256(manifest_path):
        raise ValueError("canonical lifecycle invocation hash does not match index entry")
    if entry.get("sweep") != manifest.get("sweep"):
        raise ValueError("canonical lifecycle invocation sweep does not match index entry")


def _equivalent_index_entries(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return {key: value for key, value in first.items() if key != "manifest_path"} == {
        key: value for key, value in second.items() if key != "manifest_path"
    }


def _repair_shared_invocation_index(
    run_dir: Path,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
) -> None:
    invocation = _canonical_invocation(run_dir, manifest, trial)
    index_path = run_dir.parent / "experiment-index.jsonl"
    normalized = dict(invocation.index_entry)
    normalized["manifest_path"] = str(invocation.manifest_path)
    with _exclusive_index_lock(index_path):
        needs_rewrite = not index_path.is_file()
        try:
            entries = (
                _read_jsonl(index_path)
                if index_path.is_file()
                else _recover_index_entries_from_seals(index_path.parent)
            )
        except (json.JSONDecodeError, ValueError):
            entries = _recover_index_entries_from_seals(index_path.parent)
            needs_rewrite = True
        matching = [entry for entry in entries if entry.get("experiment_id") == normalized["experiment_id"]]
        if len(matching) > 1:
            raise ValueError("canonical lifecycle invocation has duplicate shared index entries")
        if matching:
            if not _equivalent_index_entries(matching[0], normalized):
                raise ValueError("canonical lifecycle invocation seal conflicts with shared index entry")
            if needs_rewrite:
                _write_jsonl_atomic(
                    index_path,
                    sorted(entries, key=lambda entry: str(entry.get("experiment_id", ""))),
                )
            return
        entries.append(normalized)
        _write_jsonl_atomic(index_path, sorted(entries, key=lambda entry: str(entry.get("experiment_id", ""))))


@contextmanager
def _exclusive_index_lock(index_path: Path) -> Iterator[None]:
    mkdir_durable(index_path.parent)
    lock_path = index_path.with_name(f".{index_path.name}.lock")
    key = str(lock_path.resolve())
    with _INDEX_LOCKS_GUARD:
        thread_lock = _INDEX_LOCKS.setdefault(key, Lock())
    with thread_lock:
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _recover_index_entries_from_seals(index_root: Path) -> list[dict[str, Any]]:
    recovered: dict[str, dict[str, Any]] = {}
    for seal_path in sorted(index_root.glob("*/experiments/*/index-entry.json")):
        if seal_path.parent.name.startswith("."):
            continue
        entry = _read_json(seal_path)
        manifest_path = seal_path.parent / "experiment-manifest.json"
        manifest = LifecycleExperimentManifest.model_validate(_read_json(manifest_path)).model_dump(mode="json")
        _validate_invocation_index_entry(
            entry,
            entry_path=seal_path,
            manifest_path=manifest_path,
            manifest=manifest,
        )
        normalized = dict(entry)
        normalized["manifest_path"] = str(manifest_path)
        experiment_id = str(normalized["experiment_id"])
        if experiment_id in recovered and not _equivalent_index_entries(recovered[experiment_id], normalized):
            raise ValueError(f"conflicting canonical invocation seals: {experiment_id}")
        recovered[experiment_id] = normalized
    return list(recovered.values())


def _validate_declared_run_artifacts(run_dir: Path, experiment: dict[str, Any]) -> None:
    outputs = experiment.get("outputs")
    declared = outputs.get("artifacts") if isinstance(outputs, dict) else None
    if not isinstance(declared, dict) or not declared:
        raise ValueError("canonical lifecycle manifest must declare run artifact hashes")
    required = {"lifecycle_ledger.jsonl", "metrics.json", "state.json", "verification.json"}
    missing = sorted(required - set(declared))
    if missing:
        raise ValueError(f"canonical lifecycle manifest is missing required run artifacts: {', '.join(missing)}")
    root = run_dir.resolve()
    for raw_relative, expected in sorted(declared.items()):
        relative = Path(str(raw_relative))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"canonical lifecycle manifest contains unsafe artifact path: {raw_relative}")
        path = (run_dir / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"canonical lifecycle manifest artifact escapes run root: {raw_relative}") from exc
        if not path.is_file() or not isinstance(expected, str) or _sha256(path) != expected:
            raise ValueError(f"run artifact hash does not match canonical manifest: {raw_relative}")
    interaction = experiment.get("interaction")
    trajectories = interaction.get("trajectory_hashes") if isinstance(interaction, dict) else None
    if not isinstance(trajectories, dict):
        raise ValueError("canonical lifecycle manifest must declare trajectory hashes")
    for relative, digest in trajectories.items():
        if declared.get(relative) != digest:
            raise ValueError(f"trajectory hash does not match declared run artifact: {relative}")


def _validate_snapshotted_lifecycle_state(package_dir: Path, run_dir: Path) -> None:
    state = EvidenceLifecycleRunState.model_validate(_read_json(run_dir / "state.json"))
    spec = load_evidence_lifecycle_spec(package_dir)
    validate_evidence_request_run_state(state, spec)
    if state.schema_version == "5":
        expected_source = resolve_lifecycle_operation_current_source(package_dir, run_dir, state)
        validate_lifecycle_operation_resolver_replay(package_dir, run_dir, state, spec)
        validate_lifecycle_operation_snapshot(
            run_dir,
            state,
            spec,
            expected_current_source=LifecycleOperationCurrentSource(
                revision_id=expected_source.revision_id,
                physical_source_state_sha256=expected_source.physical_source_state_sha256,
                visible_source_state_sha256=expected_source.visible_source_state_sha256,
                source_state=expected_source.source_state,
            ),
        )
    if state.branch is not None:
        raise ValueError("branched lifecycle snapshots are not supported by ablation finalization")
    for checkpoint in state.checkpoint_runs:
        checkpoint_spec = next(item for item in spec.checkpoints if item.checkpoint_id == checkpoint.checkpoint_id)
        expected_catalog = evidence_request_catalog_payload(checkpoint_spec, checkpoint)
        catalog_path = run_dir / "workspace" / "checkpoints" / checkpoint.checkpoint_id / "evidence-requests.json"
        catalog_was_released = expected_catalog is not None and checkpoint.status.value != "pending"
        if not catalog_was_released:
            if catalog_path.exists():
                raise ValueError("snapshot contains an unreleased or undeclared evidence request catalogue")
        elif not catalog_path.is_file() or _read_json(catalog_path) != expected_catalog:
            raise ValueError("snapshotted evidence request catalogue does not match lifecycle state")
        for action in checkpoint.evidence_request_actions:
            transaction = run_dir / "evidence_requests" / action.action_id
            action_path = transaction / "action.json"
            committed_path = transaction / "committed.json"
            if not action_path.is_file() or not committed_path.is_file():
                raise ValueError(f"snapshotted evidence request transaction is incomplete: {action.action_id}")
            persisted_action = EvidenceRequestActionRecord.model_validate(_read_json(action_path))
            if persisted_action != action:
                raise ValueError("snapshotted evidence request action does not match lifecycle state")
            committed = _read_json(committed_path)
            if committed != {"action_id": action.action_id, "status": "committed"}:
                raise ValueError("snapshotted evidence request transaction is not committed")
            for artifact in action.released_artifacts:
                canonical = run_dir / artifact.path
                workspace = run_dir / "workspace" / artifact.workspace_path
                if (
                    not canonical.is_file()
                    or _sha256(canonical) != artifact.sha256
                    or not workspace.is_file()
                    or _sha256(workspace) != artifact.sha256
                ):
                    raise ValueError("snapshotted requested evidence artifact hash mismatch")
        if checkpoint.status.value != "submitted":
            continue
        if checkpoint.submission_sha256 is None:
            raise ValueError(f"snapshotted checkpoint lacks submission hash: {checkpoint.checkpoint_id}")
        path = run_dir / "episodes" / checkpoint.checkpoint_id / "submission.json"
        if not path.is_file() or _sha256(path) != checkpoint.submission_sha256:
            raise ValueError(f"snapshotted checkpoint submission hash mismatch: {checkpoint.checkpoint_id}")
    if any(checkpoint.conditional_evidence is not None for checkpoint in spec.checkpoints):
        _validate_evidence_request_artifact_inventory(run_dir, state, spec)


def _validate_evidence_request_artifact_inventory(
    run_dir: Path,
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
) -> None:
    expected = expected_evidence_request_run_artifact_paths(state, spec)
    actual: set[str] = set()
    for path in sorted(run_dir.rglob("*")):
        relative = path.relative_to(run_dir).as_posix()
        if not is_evidence_request_run_artifact_path(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"snapshotted evidence request artifact is a symlink: {relative}")
        if path.is_file():
            actual.add(relative)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        unexpected = ", ".join(sorted(actual - expected)) or "none"
        raise ValueError(
            "snapshotted evidence request artifact inventory does not match lifecycle state: "
            f"missing={missing}; unexpected={unexpected}"
        )


def _validate_metrics_against_run(
    run_dir: Path,
    state: dict[str, Any],
    experiment: dict[str, Any],
    metrics: dict[str, Any],
    verification: dict[str, Any],
) -> None:
    checkpoint_runs = state.get("checkpoint_runs")
    if not isinstance(checkpoint_runs, list):
        raise ValueError("lifecycle state checkpoint_runs are malformed")
    attempts = [
        attempt
        for checkpoint in checkpoint_runs
        if isinstance(checkpoint, dict)
        for attempt in checkpoint.get("attempts", [])
        if isinstance(attempt, dict)
    ]
    evidence_request_actions = [
        action
        for checkpoint in checkpoint_runs
        if isinstance(checkpoint, dict)
        for action in checkpoint.get("evidence_request_actions", [])
        if isinstance(action, dict)
    ]
    operation_actions = [
        action
        for checkpoint in checkpoint_runs
        if isinstance(checkpoint, dict)
        for action in checkpoint.get("operation_actions", [])
        if isinstance(action, dict)
    ]
    expected = {
        "checkpoint_count": sum(
            isinstance(checkpoint, dict) and checkpoint.get("status") == "submitted" for checkpoint in checkpoint_runs
        ),
        "retries": sum(
            max(0, len(checkpoint.get("attempts", [])) - 1)
            for checkpoint in checkpoint_runs
            if isinstance(checkpoint, dict)
        ),
        "failures": sum(attempt.get("status") == "failed" for attempt in attempts),
    }
    if state.get("schema_version") == "4":
        expected.update(
            {
                "evidence_request_calls": len(evidence_request_actions),
                "accepted_evidence_requests": sum(
                    action.get("outcome") == "released" for action in evidence_request_actions
                ),
                "already_released_evidence_requests": sum(
                    action.get("outcome") == "already_released" for action in evidence_request_actions
                ),
                "rejected_evidence_requests": sum(
                    action.get("outcome") == "rejected" for action in evidence_request_actions
                ),
                "evidence_request_budget_consumed": sum(
                    int(action.get("budget_consumed", 0)) for action in evidence_request_actions
                ),
                "evidence_request_artifacts_released": sum(
                    len(action.get("released_artifacts", []))
                    for action in evidence_request_actions
                    if action.get("outcome") == "released"
                ),
            }
        )
    if state.get("schema_version") == "5":
        if metrics.get("schema_version") != "3":
            raise ValueError("lifecycle v5 metrics require schema version 3")
        expected.update(
            {
                "operation_calls": len(operation_actions),
                "completed_operations": sum(action.get("outcome") == "completed" for action in operation_actions),
                "already_current_operations": sum(
                    action.get("outcome") == "already_current" for action in operation_actions
                ),
                "rejected_operations": sum(action.get("outcome") == "rejected" for action in operation_actions),
                "operation_budget_consumed": sum(int(action.get("budget_consumed", 0)) for action in operation_actions),
                "operation_artifacts_produced": sum(
                    len(action.get("artifacts", []))
                    for action in operation_actions
                    if action.get("outcome") == "completed"
                ),
            }
        )
    for field, value in expected.items():
        if metrics.get(field) != value:
            raise ValueError(f"lifecycle {field} does not match run state")

    interaction = experiment.get("interaction")
    if not isinstance(interaction, dict):
        raise ValueError("lifecycle invocation interaction is malformed")
    trajectory_hashes = interaction.get("trajectory_hashes")
    if not isinstance(trajectory_hashes, dict):
        raise ValueError("lifecycle invocation trajectory hashes are malformed")
    if state.get("schema_version") == "5":
        protocol = interaction.get("lifecycle_operation_protocol")
        tool_schema = interaction.get("tool_schema")
        if not isinstance(protocol, dict) or not isinstance(tool_schema, list):
            raise ValueError("lifecycle invocation operation protocol is missing")
        encoded_tool_schema = json.dumps(tool_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected_protocol = lifecycle_operation_protocol_identity()
        try:
            validate_lifecycle_operation_tool_schema(tool_schema)
        except EvidenceLifecycleError as exc:
            raise ValueError("lifecycle invocation operation protocol does not match the public tool contract") from exc
        if (
            protocol.get("schema_version") != expected_protocol["schema_version"]
            or protocol.get("sha256") != expected_protocol["sha256"]
            or protocol.get("tool") != expected_protocol["tool"]
            or protocol.get("tool_schema_sha256") != hashlib.sha256(encoded_tool_schema).hexdigest()
        ):
            raise ValueError("lifecycle invocation operation protocol does not match the public tool contract")
    entries_by_trajectory = [read_trajectory(run_dir / relative) for relative in sorted(trajectory_hashes)]
    entries = [entry for trajectory in entries_by_trajectory for entry in trajectory]
    tool_calls = [entry for entry in entries if entry.role == "tool_call"]
    trajectory_metrics = {
        "requests": sum(
            len({entry.step for entry in trajectory if entry.step > 0}) for trajectory in entries_by_trajectory
        ),
        "tool_calls": len(tool_calls),
        "reads": sum(entry.tool_name == "read_workspace_file" for entry in tool_calls),
        "revisits": sum(entry.tool_name == "revisit_checkpoint" for entry in tool_calls),
    }
    for field, value in trajectory_metrics.items():
        if metrics.get(field) != value:
            raise ValueError(f"lifecycle {field} does not match trajectories")
    if metrics.get("semantic_transition") != verification.get("semantic_metrics"):
        raise ValueError("lifecycle semantic metrics do not match verification")
    execution = experiment.get("execution")
    if not isinstance(execution, dict) or (
        execution.get("checkpoint_seconds") != metrics.get("checkpoint_seconds")
        or execution.get("whole_run_seconds") != metrics.get("whole_run_seconds")
    ):
        raise ValueError("lifecycle execution timing does not match metrics")


def _validate_artifact_hash(path: Path, expected: object, label: str) -> None:
    if not isinstance(expected, str) or _sha256(path) != expected:
        raise ValueError(f"{label} hash does not match manifest")


def _copy_artifact_tree(
    source: Path,
    destination: Path,
    *,
    excluded_roots: set[str],
    excluded_names: set[str] | None = None,
) -> None:
    excluded_names = excluded_names or set()
    if not source.is_dir():
        raise ValueError(f"artifact source directory does not exist: {source}")
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if not relative.parts or relative.parts[0] in excluded_roots or path.name in excluded_names:
            continue
        if path.is_symlink():
            raise ValueError(f"artifact snapshots do not accept symlinks: {path}")
        if not path.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _snapshot_references(
    *,
    staging: Path,
    final: Path,
    ledger_root: Path,
) -> list[ArtifactReference]:
    references: list[ArtifactReference] = []
    for path in sorted(item for item in staging.rglob("*") if item.is_file()):
        relative = path.relative_to(staging)
        final_path = final / relative
        references.append(
            ArtifactReference(
                kind=_artifact_kind(relative),
                path=final_path.relative_to(ledger_root).as_posix(),
                sha256=_sha256(path),
                media_type=_media_type(path),
            )
        )
    if not references:
        raise ValueError("lifecycle artifact snapshot is empty")
    return references


def _artifact_kind(relative: Path) -> str:
    path = relative.as_posix()
    if path.startswith("run/experiments/") and path.endswith("/experiment-manifest.json"):
        return "lifecycle_manifest"
    if path.startswith("run/experiments/") and path.endswith("/index-entry.json"):
        return "lifecycle_invocation_seal"
    if path == "experiment-index.jsonl":
        return "lifecycle_invocation_index"
    if path == "sweep/manifest.json":
        return "lifecycle_ablation_manifest"
    if path == "sweep/plan.json":
        return "lifecycle_ablation_plan"
    if path == "run/verification.json":
        return "lifecycle_verification"
    if path == "run/metrics.json":
        return "lifecycle_metrics"
    if path.endswith("/trajectory.jsonl"):
        return "trajectory"
    if path.endswith("/conversation.jsonl"):
        return "conversation"
    if path.endswith("/episode_request.json"):
        return "lifecycle_episode_request"
    if path.endswith("/episode_result.json"):
        return "lifecycle_episode_result"
    if path.endswith("/environment_prepared_episode_request.json"):
        return "environment_prepared_lifecycle_episode_request"
    if path.endswith("/environment_prepared_episode_result.json") or path.endswith(
        "/environment_prepared_rejected_episode_result.json"
    ):
        return "environment_prepared_lifecycle_episode_result"
    if path.endswith("/rejected_episode_result.json"):
        return "rejected_lifecycle_episode_result"
    if path.endswith("/raw_output.md"):
        return "raw_output"
    if path.endswith("/agent_result.json"):
        return "agent_result"
    if path.endswith("/agent_result.corrupt.json"):
        return "corrupt_agent_result"
    if path.startswith("run/evidence_requests/") and path.endswith("/action.json"):
        return "evidence_request_action"
    if path.startswith("run/evidence_requests/") and path.endswith("/committed.json"):
        return "evidence_request_commit"
    if path.startswith("run/evidence_requests/") and "/artifacts/" in path:
        return "requested_evidence"
    if path.endswith("/evidence-requests.json"):
        return "evidence_request_catalog"
    if path.startswith("run/workspace/inbox/") and "/requests/" in path:
        return "requested_evidence_projection"
    if path.startswith("run/lifecycle_operations/") and path.endswith("/request.json"):
        return "lifecycle_operation_request"
    if path.startswith("run/lifecycle_operations/") and path.endswith("/action.json"):
        return "lifecycle_operation_action"
    if path.startswith("run/lifecycle_operations/") and path.endswith("/result-manifest.json"):
        return "lifecycle_operation_result_manifest"
    if path.startswith("run/lifecycle_operations/") and path.endswith("/committed.json"):
        return "lifecycle_operation_commit"
    if path.startswith("run/lifecycle_operations/") and "/artifacts/" in path:
        return "lifecycle_operation_artifact"
    if path.endswith("/operations.json"):
        return "lifecycle_operation_catalog"
    if path == "run/workspace/hydraulics/current-source.json":
        return "lifecycle_operation_current_source"
    if path.startswith("run/workspace/inbox/") and "/operations/" in path:
        return "lifecycle_operation_projection"
    if path.endswith("/submission.json") or "/submissions/" in path:
        return "checkpoint_submission"
    if path == "run/state.json":
        return "lifecycle_state"
    if path == "run/lifecycle_ledger.jsonl":
        return "lifecycle_ledger"
    if path.startswith("package/"):
        return "lifecycle_package"
    return "lifecycle_run_artifact"


def _media_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }.get(path.suffix.lower(), "application/octet-stream")


def _lifecycle_sessions(
    run_dir: Path,
    artifacts: list[ArtifactReference],
    *,
    state: dict[str, Any],
    experiment: dict[str, Any],
    metrics: dict[str, Any],
    verification: dict[str, Any],
) -> list[LifecycleSessionRecord]:
    outputs = cast(dict[str, Any], experiment["outputs"])
    execution = cast(dict[str, Any], experiment["execution"])
    model = cast(dict[str, Any], experiment["model"])
    expected_execution_mode = str(execution.get("mode") or "")
    expected_session_mode = "persistent" if expected_execution_mode == "persistent_context" else "fresh"
    expected_visibility = str(execution.get("memory_visibility_policy") or "")
    declared = cast(dict[str, str], outputs["artifacts"])
    result_paths = sorted(Path(relative) for relative in declared if Path(relative).name == "agent_result.json")
    payloads: dict[str, tuple[Path, dict[str, Any]]] = {}
    configuration_records: list[dict[str, Any]] = []
    for relative in result_paths:
        payload = _read_json(run_dir / relative)
        session_id = str(payload.get("session_id") or "")
        if not session_id:
            raise ValueError(f"lifecycle session is missing session_id: {relative}")
        if session_id in payloads:
            raise ValueError(f"lifecycle run contains duplicate session_id: {session_id}")
        payloads[session_id] = (relative, payload)
        configuration = payload.get("configuration_record")
        if not isinstance(configuration, dict):
            raise ValueError(f"lifecycle session configuration is malformed: {session_id}")
        configuration_records.append(cast(dict[str, Any], configuration))

    ordered_session_ids: list[str] = []
    expected_checkpoints: dict[str, list[str]] = {}
    expected_attempt_statuses: dict[str, list[str]] = {}
    checkpoint_runs = state.get("checkpoint_runs")
    if not isinstance(checkpoint_runs, list):
        raise ValueError("lifecycle state checkpoint_runs are malformed")
    for checkpoint in checkpoint_runs:
        if not isinstance(checkpoint, dict):
            raise ValueError("lifecycle state checkpoint record is malformed")
        checkpoint_id = str(checkpoint.get("checkpoint_id") or "")
        attempts = checkpoint.get("attempts")
        if not isinstance(attempts, list):
            raise ValueError(f"lifecycle checkpoint attempts are malformed: {checkpoint_id}")
        if any(not isinstance(attempt, dict) for attempt in attempts):
            raise ValueError(f"lifecycle checkpoint attempt is malformed: {checkpoint_id}")
        checkpoint_status = str(checkpoint.get("status") or "")
        if checkpoint_status == "submitted":
            if not attempts:
                raise ValueError(f"submitted checkpoint has no adapter attempt owner: {checkpoint_id}")
            submitted_attempts = [attempt for attempt in attempts if attempt.get("status") == "submitted"]
            if len(submitted_attempts) != 1 or attempts[-1] != submitted_attempts[0]:
                raise ValueError(f"submitted checkpoint has ambiguous adapter attempt ownership: {checkpoint_id}")
        elif any(attempt.get("status") == "submitted" for attempt in attempts):
            raise ValueError(f"unsubmitted checkpoint contains submitted adapter attempt: {checkpoint_id}")
        for attempt in attempts:
            session_id = str(attempt.get("session_id") or "")
            if not session_id:
                raise ValueError(f"lifecycle checkpoint attempt has no session owner: {checkpoint_id}")
            if attempt.get("execution_mode") != expected_execution_mode:
                raise ValueError(f"lifecycle checkpoint attempt execution mode mismatch: {checkpoint_id}")
            request_relative = Path("episodes") / checkpoint_id / session_id / "episode_request.json"
            request_hash = attempt.get("episode_request_sha256")
            declared_request_hash = declared.get(request_relative.as_posix())
            if request_hash is not None:
                if expected_execution_mode != "fresh_context":
                    raise ValueError(f"persistent lifecycle attempt cannot own a fresh request: {session_id}")
                if request_hash != declared_request_hash:
                    raise ValueError(f"lifecycle episode request hash does not match attempt state: {session_id}")
                request = LifecycleEpisodeRequest.model_validate(_read_json(run_dir / request_relative))
                expected_request_identity = {
                    "episode_id": f"{state.get('lifecycle_id')}.{attempt.get('attempt_id')}",
                    "lifecycle_id": state.get("lifecycle_id"),
                    "world_id": state.get("world_id"),
                    "lifecycle_spec_sha256": state.get("lifecycle_spec_sha256"),
                    "package_sha256": state.get("package_sha256"),
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_ids": (checkpoint_id,),
                    "attempt_id": attempt.get("attempt_id"),
                    "session_id": session_id,
                    "execution_mode": expected_execution_mode,
                    "memory_visibility_policy": expected_visibility,
                    "requested_adapter": model.get("requested_adapter", model.get("adapter")),
                    "requested_model": model.get("requested_model"),
                    "max_turns_per_session": execution.get("max_turns_per_session"),
                }
                actual_request_identity = {key: getattr(request, key) for key in expected_request_identity}
                if actual_request_identity != expected_request_identity:
                    raise ValueError(f"lifecycle episode request identity mismatch: {session_id}")
            elif declared_request_hash is not None:
                raise ValueError(f"lifecycle episode request lacks attempt-state hash: {session_id}")
            if session_id not in ordered_session_ids:
                ordered_session_ids.append(session_id)
            expected_checkpoints.setdefault(session_id, []).append(checkpoint_id)
            expected_attempt_statuses.setdefault(session_id, []).append(str(attempt.get("status") or ""))
    if set(payloads) != set(ordered_session_ids):
        raise ValueError("lifecycle session artifacts do not match checkpoint attempt lineage")
    if expected_execution_mode == "fresh_context" and any(
        len(checkpoint_ids) != 1 for checkpoint_ids in expected_checkpoints.values()
    ):
        raise ValueError("fresh lifecycle session must own exactly one checkpoint attempt")

    if execution.get("session_count") != len(payloads):
        raise ValueError("lifecycle execution session_count does not match session artifacts")
    if model.get("session_configurations") != configuration_records:
        raise ValueError("lifecycle model session configurations do not match session artifacts")

    sessions: list[LifecycleSessionRecord] = []
    for session_id in ordered_session_ids:
        relative, payload = payloads[session_id]
        checkpoint_ids = payload.get("checkpoint_ids", [])
        if not isinstance(checkpoint_ids, list):
            raise ValueError(f"lifecycle session checkpoint_ids are malformed: {session_id}")
        expected_ids = list(dict.fromkeys(expected_checkpoints[session_id]))
        if checkpoint_ids != expected_ids:
            raise ValueError(f"lifecycle session checkpoint coverage does not match state: {session_id}")
        requested_adapter = str(payload.get("adapter") or "")
        resolved_adapter = str(payload.get("adapter_name") or "")
        if payload.get("session_mode") != expected_session_mode:
            raise ValueError(f"lifecycle session execution mode does not match invocation: {session_id}")
        if payload.get("memory_visibility_policy") != expected_visibility:
            raise ValueError(f"lifecycle session visibility policy does not match invocation: {session_id}")
        parts = relative.parts
        if expected_session_mode == "persistent" and parts[:2] != ("sessions", session_id):
            raise ValueError(f"persistent lifecycle session artifact path is invalid: {session_id}")
        if expected_session_mode == "fresh" and (
            len(parts) < 4 or parts[0] != "episodes" or parts[1] != expected_ids[0] or parts[2] != session_id
        ):
            raise ValueError(f"fresh lifecycle session artifact path is invalid: {session_id}")
        if requested_adapter != model.get("requested_adapter", model.get("adapter")):
            raise ValueError(f"lifecycle session requested adapter does not match invocation: {session_id}")
        if not resolved_adapter:
            raise ValueError(f"lifecycle session resolved adapter is missing: {session_id}")
        if payload.get("max_turns") != execution.get("max_turns_per_session"):
            raise ValueError(f"lifecycle session max_turns does not match invocation: {session_id}")
        resolved_model = str(payload.get("resolved_model") or payload.get("model") or "")
        if not resolved_model:
            raise ValueError(f"lifecycle session resolved model is missing: {session_id}")
        session_status = _session_status(str(payload.get("status") or "failed"))
        attempts_submitted = all(status == "submitted" for status in expected_attempt_statuses[session_id])
        identity_mismatch = (
            resolved_adapter != requested_adapter
            and session_status == "failed"
            and payload.get("failure_kind") == "adapter_identity_mismatch"
        )
        unresolved_interruption = (
            resolved_adapter == "unresolved"
            and session_status == "failed"
            and payload.get("failure_kind") in {"interrupted", "interrupted_after_completion"}
        )
        failure_kind = payload.get("failure_kind")
        terminal_failure = (
            attempts_submitted and session_status == "failed" and isinstance(failure_kind, str) and bool(failure_kind)
        )
        if resolved_adapter != requested_adapter and not (identity_mismatch or unresolved_interruption):
            raise ValueError(f"lifecycle session resolved adapter does not match invocation: {session_id}")
        if attempts_submitted != (session_status == "completed") and not (
            attempts_submitted and (identity_mismatch or unresolved_interruption or terminal_failure)
        ):
            raise ValueError(f"lifecycle session status does not match checkpoint attempts: {session_id}")
        session_artifacts = [
            artifact for artifact in artifacts if f"/run/{relative.parent.as_posix()}/" in f"/{artifact.path}"
        ]
        sessions.append(
            LifecycleSessionRecord(
                session_id=session_id,
                checkpoint_ids=expected_ids,
                requested_adapter=requested_adapter,
                adapter=resolved_adapter,
                resolved_model=resolved_model,
                execution_mode=cast(Literal["persistent_context", "fresh_context"], expected_execution_mode),
                memory_visibility_policy=cast(
                    Literal[
                        "persistent_context",
                        "artifact_memory",
                        "raw_evidence_only",
                        "current_release_only",
                    ],
                    expected_visibility,
                ),
                configuration=cast(dict[str, Any], payload.get("configuration_record") or {}),
                status=session_status,
                input_tokens=int(payload.get("input_tokens", 0)),
                output_tokens=int(payload.get("output_tokens", 0)),
                cache_read_tokens=int(payload.get("cache_read_tokens", 0)),
                cache_write_tokens=int(payload.get("cache_write_tokens", 0)),
                failure_kind=(str(payload["failure_kind"]) if payload.get("failure_kind") is not None else None),
                provider_error=(str(payload["provider_error"]) if payload.get("provider_error") is not None else None),
                artifacts=session_artifacts,
            )
        )
    resolved_models = sorted({session.resolved_model for session in sessions})
    if model.get("resolved_models") != resolved_models:
        raise ValueError("lifecycle resolved models do not match session artifacts")
    resolved_adapters = sorted({session.adapter for session in sessions})
    if model.get("resolved_adapters") != resolved_adapters:
        raise ValueError("lifecycle resolved adapters do not match session artifacts")
    if any(session.status != "completed" for session in sessions) and (
        execution.get("status") != "failed"
        or verification.get("overall") != "incomplete"
        or float(verification.get("reward", 0.0)) != 0.0
    ):
        raise ValueError("failed lifecycle sessions must remain an unscored failed execution")
    token_fields = {
        "input_tokens": "input_tokens",
        "output_tokens": "output_tokens",
        "cache_read_tokens": "cache_read_tokens",
        "cache_write_tokens": "cache_write_tokens",
    }
    for metric_field, session_field in token_fields.items():
        if metrics.get(metric_field) != sum(getattr(session, session_field) for session in sessions):
            raise ValueError(f"lifecycle {metric_field} does not match session artifacts")
    if execution.get("status") == "completed" and (
        state.get("status") != "complete" or any(session.status != "completed" for session in sessions)
    ):
        raise ValueError("completed lifecycle execution contradicts state or session status")
    return sessions


def _session_status(status: str) -> Literal["completed", "failed", "partial"]:
    if status in {"completed", "ok"}:
        return "completed"
    if status == "partial":
        return "partial"
    return "failed"


def _execution_status(status: str) -> Literal["completed", "failed", "partial"]:
    if status == "completed":
        return "completed"
    if status == "partial":
        return "partial"
    return "failed"


def _artifact_output_root(
    trial: LifecycleAblationTrial,
    artifacts: list[ArtifactReference],
    run_dir: Path,
) -> str:
    if not artifacts:
        return str(run_dir)
    experiment_id = Path(trial.ledger_path).parent.name
    return (Path(experiment_id) / "_artifacts" / trial.trial_id / "run").as_posix()


def _snapshotted_package_path(artifacts: list[ArtifactReference], package_path: str) -> str:
    suffix = f"/package/{package_path}"
    matches = [artifact.path for artifact in artifacts if artifact.path.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"snapshotted package artifact missing or ambiguous: {package_path}")
    return matches[0]


def _single_path(preferred: list[str], fallback: list[str]) -> str | None:
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def _artifact_by_kind(artifacts: list[ArtifactReference], kind: str) -> ArtifactReference | None:
    matches = [artifact for artifact in artifacts if artifact.kind == kind]
    if len(matches) > 1:
        raise ValueError(f"artifact snapshot contains duplicate {kind} records")
    return matches[0] if matches else None


def _lifecycle_instruction(package_dir: Path) -> str:
    parts = [path.read_text(encoding="utf-8").strip() for path in sorted((package_dir / "instructions").glob("*.md"))]
    instruction = "\n\n".join(part for part in parts if part)
    if not instruction:
        raise ValueError("lifecycle package instructions are empty")
    return instruction


def _verification_failures(verification: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    gates = verification.get("gates", {})
    if not isinstance(gates, dict):
        return ["verification gates are malformed"]
    for gate_id, gate in gates.items():
        if not isinstance(gate, dict):
            failures.append(f"{gate_id}:malformed")
            continue
        for failure in gate.get("failures", []):
            failures.append(f"{gate_id}:{failure}")
    return failures


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, payloads: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(payload, sort_keys=True) + "\n" for payload in payloads),
        encoding="utf-8",
    )


def _write_jsonl_atomic(path: Path, payloads: list[dict[str, Any]]) -> None:
    mkdir_durable(path.parent)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write("".join(json.dumps(payload, sort_keys=True) + "\n" for payload in payloads))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"expected JSONL file: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        records.append(cast(dict[str, Any], payload))
    return records


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
