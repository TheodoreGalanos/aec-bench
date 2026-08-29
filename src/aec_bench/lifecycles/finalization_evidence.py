# ABOUTME: Validates the complete evidence set used to finalize one lifecycle trial.
# ABOUTME: Owns manifest, state, protocol, session, metric, and artifact-inventory checks.

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.contracts.trial_record import ArtifactReference, LifecycleSessionRecord
from aec_bench.lifecycles.catalogue import lifecycle_operation_resolver, lifecycle_package_variant
from aec_bench.lifecycles.compiled import CompiledLifecycle, load_compiled_lifecycle
from aec_bench.lifecycles.evidence_files import require_lifecycle_regular_file, safe_lifecycle_relative_path
from aec_bench.lifecycles.invocation import (
    LifecycleExperimentManifest,
    LifecycleExperimentMetrics,
    LifecycleExperimentRecordingResult,
    LifecycleExperimentTrialContext,
    lifecycle_experiment_metrics_payload,
)
from aec_bench.lifecycles.runtime.episode import LifecycleOperationCurrentSource
from aec_bench.lifecycles.runtime.lifecycle import (
    evidence_request_catalog_payload,
    load_evidence_lifecycle_spec,
    validate_evidence_request_run_state,
    validate_lifecycle_verification,
)
from aec_bench.lifecycles.runtime.operation_protocol import (
    lifecycle_operation_protocol_identity,
    validate_lifecycle_operation_run_state,
    validate_lifecycle_operation_tool_schema,
)
from aec_bench.lifecycles.runtime.operation_snapshot import (
    expected_lifecycle_operation_run_artifact_paths,
    is_lifecycle_operation_run_artifact_path,
    validate_lifecycle_operation_snapshot,
)
from aec_bench.lifecycles.runtime.operation_store import (
    resolve_lifecycle_operation_current_source,
    validate_lifecycle_operation_resolver_replay,
)
from aec_bench.lifecycles.runtime.request_protocol import (
    EvidenceLifecycleError,
    evidence_request_protocol_identity,
    expected_evidence_request_run_artifact_paths,
    is_evidence_request_run_artifact_path,
)
from aec_bench.lifecycles.runtime.state import EvidenceLifecycleRunState, EvidenceRequestActionRecord
from aec_bench.lifecycles.session_records import parse_lifecycle_session_records
from aec_bench.lifecycles.values import LifecycleTrial


@dataclass(frozen=True, slots=True)
class ValidatedLifecycleEvidence:
    """Hold the checked evidence values needed for record assembly."""

    package_dir: Path
    run_dir: Path
    manifest_path: Path
    manifest: LifecycleExperimentManifest
    trial_context: LifecycleExperimentTrialContext
    experiment: dict[str, Any]
    state: dict[str, Any]
    verification: dict[str, Any]
    metrics: dict[str, Any]
    package_files: dict[str, str]
    run_files: dict[str, str]
    execution_status: Literal["completed", "failed", "partial"]
    max_turns_per_session: int


def validate_lifecycle_finalization_evidence(
    *,
    trial: LifecycleTrial,
    compiled_source: CompiledLifecycle,
    run_dir: Path,
    recording: LifecycleExperimentRecordingResult,
) -> ValidatedLifecycleEvidence:
    """Validate planned identity and all recorded lifecycle evidence before assembly."""
    package = compiled_source.package_dir
    run = Path(run_dir)
    compiled = load_compiled_lifecycle(package)
    if compiled.envelope != compiled_source.envelope or compiled.envelope != trial.compiled.envelope:
        raise ValueError("lifecycle finalization source does not match the planned compiled identity")

    manifest_path = Path(recording["canonical_manifest"])
    require_lifecycle_regular_file(root=run, path=manifest_path, label="canonical lifecycle manifest")
    expected_manifest = run / "experiments" / recording["experiment_id"] / "experiment-manifest.json"
    if manifest_path.resolve() != expected_manifest.resolve():
        raise ValueError("canonical lifecycle manifest path does not match the finalization source")
    if not manifest_path.is_file() or file_sha256(manifest_path) != recording["manifest_sha256"]:
        raise ValueError("canonical lifecycle manifest hash does not match the recording result")
    _validate_artifact_hash(
        Path(recording["manifest"]),
        recording["manifest_sha256"],
        "run lifecycle manifest",
        root=run,
    )

    manifest = LifecycleExperimentManifest.model_validate(read_json_object(manifest_path))
    if manifest.schema_version != "2" or manifest.trial is None:
        raise ValueError("lifecycle finalization requires a version 2 manifest with exact trial identity")
    if manifest.experiment_id != recording["experiment_id"]:
        raise ValueError("lifecycle recording result does not match the canonical invocation")
    expected_context = LifecycleExperimentTrialContext(
        trial_id=trial.planned.trial_id,
        planned_experiment_id=trial.planned.experiment_id,
        task_id=trial.planned.task_id,
        repetition=trial.planned.repetition,
        run_id=trial.planned.trial_id,
        compiled=trial.compiled.envelope,
    )
    if manifest.trial != expected_context:
        raise ValueError("canonical lifecycle invocation does not match the planned trial")
    if manifest.sweep != trial.sweep_context:
        raise ValueError("canonical lifecycle invocation sweep does not match the planned trial")

    experiment = manifest.model_dump(mode="json")
    state_path = require_lifecycle_regular_file(root=run, path=run / "state.json", label="lifecycle state")
    state = read_json_object(state_path)
    verification_path = manifest_path.with_name("verification.json")
    metrics_path = manifest_path.with_name("metrics.json")
    require_lifecycle_regular_file(root=run, path=verification_path, label="canonical lifecycle verification")
    require_lifecycle_regular_file(root=run, path=metrics_path, label="canonical lifecycle metrics")
    verification = validate_lifecycle_verification(read_json_object(verification_path))
    metrics = lifecycle_experiment_metrics_payload(
        LifecycleExperimentMetrics.model_validate(read_json_object(metrics_path))
    )
    outputs = cast(dict[str, Any], experiment["outputs"])
    _validate_artifact_hash(
        verification_path,
        outputs.get("verification.json"),
        "lifecycle verification",
        root=run,
    )
    _validate_artifact_hash(metrics_path, outputs.get("metrics.json"), "lifecycle metrics", root=run)
    _validate_artifact_hash(
        Path(recording["verification"]),
        outputs.get("verification.json"),
        "run verification",
        root=run,
    )
    _validate_artifact_hash(Path(recording["metrics"]), outputs.get("metrics.json"), "run metrics", root=run)
    _validate_invocation_index(Path(recording["index"]), manifest_path, manifest, verification, run)
    run_files = _validate_declared_run_artifacts(run, experiment)
    package_files = _validate_package_files(package, experiment)
    _validate_lifecycle_identity(trial, package, state, experiment, verification)
    _validate_execution_identity(trial, experiment)
    _validate_lifecycle_state(package, run, state, run_files)
    execution = cast(dict[str, Any], experiment["execution"])
    execution_status = _execution_status(str(execution.get("status") or ""))
    max_turns = _positive_int(execution.get("max_turns_per_session"), "lifecycle max_turns_per_session")
    return ValidatedLifecycleEvidence(
        package_dir=package,
        run_dir=run,
        manifest_path=manifest_path,
        manifest=manifest,
        trial_context=manifest.trial,
        experiment=experiment,
        state=state,
        verification=verification,
        metrics=metrics,
        package_files=package_files,
        run_files=run_files,
        execution_status=execution_status,
        max_turns_per_session=max_turns,
    )


def validate_lifecycle_sessions(
    *,
    trial: LifecycleTrial,
    evidence: ValidatedLifecycleEvidence,
    artifact_references: Sequence[ArtifactReference],
) -> list[LifecycleSessionRecord]:
    """Parse session evidence and reconcile metrics with state and trajectories."""
    sessions = parse_lifecycle_session_records(
        run_dir=evidence.run_dir,
        artifact_references=artifact_references,
        state=evidence.state,
        declared_run_artifacts=evidence.run_files,
        requested_model=trial.planned.agent.model,
        requested_adapter=trial.planned.agent.adapter,
        execution_mode=trial.execution_mode.value,
        memory_visibility_policy=trial.visibility_policy.value,
        max_turns_per_session=evidence.max_turns_per_session,
        execution_status=evidence.execution_status,
        verification=evidence.verification,
    )
    _validate_metrics_and_sessions(
        evidence.run_dir,
        evidence.state,
        evidence.experiment,
        evidence.metrics,
        evidence.verification,
        sessions,
    )
    return sessions


def validate_lifecycle_run_snapshot(package_dir: Path, run_dir: Path) -> EvidenceLifecycleRunState:
    """Validate one filesystem-backed lifecycle run against its current package contract."""
    package = Path(package_dir)
    run = Path(run_dir)
    declared_files = {
        path.relative_to(run).as_posix(): ""
        for path in sorted(run.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }
    return _validate_lifecycle_state(
        package,
        run,
        read_json_object(run / "state.json"),
        declared_files,
    )


def validate_lifecycle_run_metrics(
    *,
    run_dir: Path,
    state: Mapping[str, Any],
    experiment: Mapping[str, Any],
    metrics: Mapping[str, Any],
    verification: Mapping[str, Any],
) -> None:
    """Reconcile recorded metrics and protocols with state and trajectories."""
    run = Path(run_dir)
    state_contract = EvidenceLifecycleRunState.model_validate(state)
    _validate_interaction_protocols(state_contract, experiment)
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
        "evidence_request_calls": len(evidence_request_actions),
        "accepted_evidence_requests": sum(action.get("outcome") == "released" for action in evidence_request_actions),
        "already_released_evidence_requests": sum(
            action.get("outcome") == "already_released" for action in evidence_request_actions
        ),
        "rejected_evidence_requests": sum(action.get("outcome") == "rejected" for action in evidence_request_actions),
        "evidence_request_budget_consumed": sum(
            _non_negative_int(action.get("budget_consumed", 0), "lifecycle evidence request budget_consumed")
            for action in evidence_request_actions
        ),
        "evidence_request_artifacts_released": sum(
            len(action.get("released_artifacts", []))
            for action in evidence_request_actions
            if action.get("outcome") == "released"
        ),
        "operation_calls": len(operation_actions),
        "completed_operations": sum(action.get("outcome") == "completed" for action in operation_actions),
        "already_current_operations": sum(action.get("outcome") == "already_current" for action in operation_actions),
        "rejected_operations": sum(action.get("outcome") == "rejected" for action in operation_actions),
        "operation_budget_consumed": sum(
            _non_negative_int(action.get("budget_consumed", 0), "lifecycle operation budget_consumed")
            for action in operation_actions
        ),
        "operation_artifacts_produced": sum(
            len(action.get("artifacts", [])) for action in operation_actions if action.get("outcome") == "completed"
        ),
    }
    if state.get("schema_version") == "7" and metrics.get("schema_version") != "3":
        raise ValueError("operation lifecycle metrics require schema version 3")
    for field, value in expected.items():
        if metrics.get(field) != value:
            raise ValueError(f"lifecycle {field} does not match run state")
    interaction = experiment.get("interaction")
    trajectory_hashes = interaction.get("trajectory_hashes") if isinstance(interaction, dict) else None
    if not isinstance(trajectory_hashes, dict):
        raise ValueError("lifecycle invocation trajectory hashes are malformed")
    trajectories = [
        read_trajectory(run / safe_lifecycle_relative_path(relative)) for relative in sorted(trajectory_hashes)
    ]
    entries = [entry for trajectory in trajectories for entry in trajectory]
    tool_calls = [entry for entry in entries if entry.role == "tool_call"]
    trajectory_metrics = {
        "requests": sum(len({entry.step for entry in trajectory if entry.step > 0}) for trajectory in trajectories),
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
    if not isinstance(execution, dict):
        raise ValueError("lifecycle execution timing does not match metrics")
    raw_checkpoint_seconds = execution.get("checkpoint_seconds")
    if not isinstance(raw_checkpoint_seconds, dict):
        raise ValueError("lifecycle execution timing does not match metrics")
    checkpoint_seconds = {
        str(checkpoint_id): _non_negative_number(seconds, "lifecycle checkpoint timing")
        for checkpoint_id, seconds in raw_checkpoint_seconds.items()
    }
    whole_run_seconds = execution.get("whole_run_seconds")
    normalized_whole_run_seconds = (
        None if whole_run_seconds is None else _non_negative_number(whole_run_seconds, "lifecycle whole-run timing")
    )
    if checkpoint_seconds != metrics.get("checkpoint_seconds") or normalized_whole_run_seconds != metrics.get(
        "whole_run_seconds"
    ):
        raise ValueError("lifecycle execution timing does not match metrics")


def _validate_invocation_index(
    index_path: Path,
    manifest_path: Path,
    manifest: LifecycleExperimentManifest,
    verification: Mapping[str, Any],
    run: Path,
) -> None:
    seal_path = manifest_path.with_name("index-entry.json")
    require_lifecycle_regular_file(root=run, path=seal_path, label="canonical lifecycle invocation seal")
    require_lifecycle_regular_file(
        root=index_path.parent,
        path=index_path,
        label="shared lifecycle invocation index",
    )
    seal = read_json_object(seal_path)
    _validate_index_entry(seal, seal_path, manifest_path, manifest, verification)
    entries = _read_jsonl(index_path)
    matching = [entry for entry in entries if entry.get("experiment_id") == manifest.experiment_id]
    if len(matching) != 1:
        raise ValueError("canonical lifecycle invocation must have one shared index entry")
    _validate_index_entry(matching[0], index_path, manifest_path, manifest, verification)
    shared_identity = {key: item for key, item in matching[0].items() if key != "manifest_path"}
    seal_identity = {key: item for key, item in seal.items() if key != "manifest_path"}
    if shared_identity != seal_identity:
        raise ValueError("canonical lifecycle invocation seal conflicts with the shared index")


def _validate_index_entry(
    entry: Mapping[str, Any],
    entry_path: Path,
    manifest_path: Path,
    manifest: LifecycleExperimentManifest,
    verification: Mapping[str, Any],
) -> None:
    if entry.get("experiment_id") != manifest.experiment_id:
        raise ValueError("canonical lifecycle invocation id does not match its index entry")
    indexed = Path(str(entry.get("manifest_path") or ""))
    if not indexed.is_absolute():
        indexed = entry_path.parent / indexed
    if indexed.resolve() != manifest_path.resolve():
        raise ValueError("canonical lifecycle invocation path does not match its index entry")
    if entry.get("manifest_sha256") != file_sha256(manifest_path):
        raise ValueError("canonical lifecycle invocation hash does not match its index entry")
    repository = manifest.repository
    model = manifest.model
    execution = manifest.execution
    lifecycle = manifest.lifecycle
    expected: dict[str, Any] = {
        "experiment_id": manifest.experiment_id,
        "created_at": manifest.created_at,
        "repository_commit": repository.get("commit"),
        "model": model.get("requested_model"),
        "execution_mode": execution.get("mode"),
        "memory_visibility_policy": execution.get("memory_visibility_policy"),
        "reward": verification.get("reward"),
        "passed": verification.get("passed"),
        "manifest_sha256": file_sha256(manifest_path),
    }
    variant = lifecycle.get("variant")
    if variant is not None:
        if not isinstance(variant, dict):
            raise ValueError("canonical lifecycle invocation variant is malformed")
        expected["variant_id"] = variant.get("variant_id")
        expected["adaptation"] = variant.get("adaptation")
    if manifest.sweep is not None:
        expected["sweep"] = manifest.sweep.model_dump(mode="json")
    expected_fields = {*expected, "manifest_path"}
    if set(entry) != expected_fields:
        raise ValueError("canonical lifecycle invocation index fields do not match the recorded invocation")
    for field, value in expected.items():
        if entry.get(field) != value:
            raise ValueError(f"canonical lifecycle invocation {field} does not match its index entry")


def _validate_lifecycle_identity(
    trial: LifecycleTrial,
    package: Path,
    state: Mapping[str, Any],
    experiment: Mapping[str, Any],
    verification: Mapping[str, Any],
) -> None:
    lifecycle = cast(dict[str, Any], experiment["lifecycle"])
    envelope = trial.compiled.envelope
    expected_lifecycle = {
        "lifecycle_id": envelope.lifecycle_id,
        "spec_sha256": envelope.lifecycle_spec_sha256,
        "package_sha256": envelope.package_sha256,
    }
    if any(lifecycle.get(key) != value for key, value in expected_lifecycle.items()):
        raise ValueError("lifecycle invocation does not match the compiled package identity")
    expected_state = {
        "lifecycle_id": envelope.lifecycle_id,
        "lifecycle_spec_sha256": envelope.lifecycle_spec_sha256,
        "package_sha256": envelope.package_sha256,
    }
    if any(state.get(key) != value for key, value in expected_state.items()):
        raise ValueError("lifecycle run state does not match the compiled package identity")
    if verification.get("lifecycle_id") != envelope.lifecycle_id:
        raise ValueError("lifecycle verification does not match the compiled package identity")
    variant = lifecycle_package_variant(package)
    if lifecycle.get("variant") != variant:
        raise ValueError("lifecycle invocation variant does not match the compiled package")
    actual_variant_id = None if variant is None else variant.get("variant_id")
    if actual_variant_id != envelope.variant_id:
        raise ValueError("lifecycle package variant does not match the compiled package identity")


def _validate_execution_identity(trial: LifecycleTrial, experiment: Mapping[str, Any]) -> None:
    model = cast(dict[str, Any], experiment["model"])
    execution = cast(dict[str, Any], experiment["execution"])
    if model.get("requested_model") != trial.planned.agent.model:
        raise ValueError("lifecycle run model does not match the planned trial")
    if (
        model.get("requested_adapter") != trial.planned.agent.adapter
        or model.get("adapter") != trial.planned.agent.adapter
    ):
        raise ValueError("lifecycle run adapter does not match the planned trial")
    if execution.get("mode") != trial.execution_mode.value:
        raise ValueError("lifecycle run execution mode does not match the planned trial")
    if execution.get("memory_visibility_policy") != trial.visibility_policy.value:
        raise ValueError("lifecycle run visibility policy does not match the planned trial")
    if execution.get("max_turns_per_session") != trial.max_turns_per_session:
        raise ValueError("lifecycle run turn limit does not match the planned trial")


def _validate_declared_run_artifacts(run: Path, experiment: Mapping[str, Any]) -> dict[str, str]:
    outputs = experiment.get("outputs")
    declared = outputs.get("artifacts") if isinstance(outputs, dict) else None
    if not isinstance(declared, dict) or not declared:
        raise ValueError("canonical lifecycle manifest must declare run artifact hashes")
    required = {"lifecycle_ledger.jsonl", "metrics.json", "state.json", "verification.json"}
    missing = sorted(required - set(declared))
    if missing:
        raise ValueError(f"canonical lifecycle manifest is missing required run artifacts: {', '.join(missing)}")
    validated: dict[str, str] = {}
    for raw_relative, expected in sorted(declared.items()):
        relative = safe_lifecycle_relative_path(str(raw_relative))
        try:
            path = require_lifecycle_regular_file(
                root=run,
                path=run / relative,
                label=f"run artifact {raw_relative}",
            )
        except ValueError as exc:
            raise ValueError(f"run artifact is not a contained regular file: {raw_relative}") from exc
        if not isinstance(expected, str) or file_sha256(path) != expected:
            raise ValueError(f"run artifact hash does not match canonical manifest: {raw_relative}")
        validated[relative.as_posix()] = expected
    interaction = experiment.get("interaction")
    trajectory_hashes = interaction.get("trajectory_hashes") if isinstance(interaction, dict) else None
    if not isinstance(trajectory_hashes, dict):
        raise ValueError("canonical lifecycle manifest must declare trajectory hashes")
    for relative, digest in trajectory_hashes.items():
        if validated.get(str(relative)) != digest:
            raise ValueError(f"trajectory hash does not match declared run artifact: {relative}")
    return validated


def _validate_package_files(package: Path, experiment: Mapping[str, Any]) -> dict[str, str]:
    lifecycle = experiment.get("lifecycle")
    declared = lifecycle.get("package_files") if isinstance(lifecycle, dict) else None
    if not isinstance(declared, dict) or not declared:
        raise ValueError("canonical lifecycle manifest must declare package file hashes")
    actual = _tree_hashes(package)
    if declared != actual:
        raise ValueError("lifecycle package files do not match the canonical manifest")
    return cast(dict[str, str], declared)


def _validate_lifecycle_state(
    package: Path,
    run: Path,
    raw_state: Mapping[str, Any],
    declared_run_artifacts: Mapping[str, str],
) -> EvidenceLifecycleRunState:
    state = EvidenceLifecycleRunState.model_validate(raw_state)
    spec = load_evidence_lifecycle_spec(package)
    try:
        validate_evidence_request_run_state(state, spec)
        validate_lifecycle_operation_run_state(state, spec)
    except EvidenceLifecycleError as exc:
        raise ValueError(f"lifecycle run state does not match its package contract: {exc}") from exc
    _validate_evidence_request_snapshot(run, state, spec, declared_run_artifacts)
    _validate_operation_snapshot(package, run, state, spec, declared_run_artifacts)
    return state


def _validate_evidence_request_snapshot(
    run: Path,
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
    declared_run_artifacts: Mapping[str, str],
) -> None:
    _validate_reserved_artifact_inventory(
        run=run,
        declared_run_artifacts=declared_run_artifacts,
        expected=expected_evidence_request_run_artifact_paths(state, spec),
        selects=is_evidence_request_run_artifact_path,
        label="evidence request",
    )
    checkpoint_specs = {checkpoint.checkpoint_id: checkpoint for checkpoint in spec.checkpoints}
    for checkpoint in state.checkpoint_runs:
        checkpoint_spec = checkpoint_specs[checkpoint.checkpoint_id]
        expected_catalog = evidence_request_catalog_payload(checkpoint_spec, checkpoint)
        catalog_path = run / "workspace" / "checkpoints" / checkpoint.checkpoint_id / "evidence-requests.json"
        catalog_released = expected_catalog is not None and checkpoint.status.value != "pending"
        if catalog_released:
            if not catalog_path.is_file() or read_json_object(catalog_path) != expected_catalog:
                raise ValueError("evidence request catalogue does not match lifecycle state")
        elif catalog_path.exists():
            raise ValueError("run contains an unreleased or undeclared evidence request catalogue")
        for action in checkpoint.evidence_request_actions:
            transaction = run / "evidence_requests" / action.action_id
            action_path = transaction / "action.json"
            committed_path = transaction / "committed.json"
            if not action_path.is_file() or not committed_path.is_file():
                raise ValueError(f"evidence request transaction is incomplete: {action.action_id}")
            if EvidenceRequestActionRecord.model_validate(read_json_object(action_path)) != action:
                raise ValueError("evidence request transaction does not match lifecycle state")
            if read_json_object(committed_path) != {"action_id": action.action_id, "status": "committed"}:
                raise ValueError("evidence request transaction is not committed")
            for artifact in action.released_artifacts:
                canonical = run / artifact.path
                workspace = run / "workspace" / artifact.workspace_path
                if (
                    not canonical.is_file()
                    or file_sha256(canonical) != artifact.sha256
                    or not workspace.is_file()
                    or file_sha256(workspace) != artifact.sha256
                ):
                    raise ValueError("requested evidence artifact hash does not match lifecycle state")
        if checkpoint.status.value == "submitted":
            submission = run / "episodes" / checkpoint.checkpoint_id / "submission.json"
            if checkpoint.submission_sha256 is None or not submission.is_file():
                raise ValueError(f"submitted checkpoint lacks its submission artifact: {checkpoint.checkpoint_id}")
            if file_sha256(submission) != checkpoint.submission_sha256:
                raise ValueError(
                    f"checkpoint submission hash does not match lifecycle state: {checkpoint.checkpoint_id}"
                )


def _validate_operation_snapshot(
    package: Path,
    run: Path,
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
    declared_run_artifacts: Mapping[str, str],
) -> None:
    expected = expected_lifecycle_operation_run_artifact_paths(state, spec)
    _validate_reserved_artifact_inventory(
        run=run,
        declared_run_artifacts=declared_run_artifacts,
        expected=expected,
        selects=is_lifecycle_operation_run_artifact_path,
        label="lifecycle operation",
    )
    if not any(checkpoint.conditional_operations is not None for checkpoint in spec.checkpoints):
        return
    resolver = lifecycle_operation_resolver(package, run)
    if resolver is None:
        raise ValueError("operation lifecycle package has no operation resolver")
    validate_lifecycle_operation_resolver_replay(run, state, spec, resolver)
    current = resolve_lifecycle_operation_current_source(state, resolver)
    validate_lifecycle_operation_snapshot(
        run,
        state,
        spec,
        expected_current_source=LifecycleOperationCurrentSource(
            revision_id=current.revision_id,
            physical_source_state_sha256=current.physical_source_state_sha256,
            visible_source_state_sha256=current.visible_source_state_sha256,
            source_state=current.source_state,
        ),
    )


def _validate_reserved_artifact_inventory(
    *,
    run: Path,
    declared_run_artifacts: Mapping[str, str],
    expected: frozenset[str],
    selects: Callable[[str], bool],
    label: str,
) -> None:
    actual: set[str] = set()
    for path in sorted(run.rglob("*")):
        relative = path.relative_to(run).as_posix()
        if not selects(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"{label} artifact is a symlink: {relative}")
        if path.is_file():
            actual.add(relative)
    declared = {relative for relative in declared_run_artifacts if selects(relative)}
    if actual != expected or declared != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        undeclared = sorted(expected - declared)
        raise ValueError(
            f"{label} artifact inventory does not match lifecycle state; "
            f"missing={missing}; unexpected={unexpected}; undeclared={undeclared}"
        )


def _validate_interaction_protocols(
    state: EvidenceLifecycleRunState,
    experiment: Mapping[str, Any],
) -> None:
    interaction = experiment.get("interaction")
    if not isinstance(interaction, dict):
        raise ValueError("lifecycle invocation interaction is malformed")
    tool_schema = interaction.get("tool_schema")
    if not isinstance(tool_schema, list) or any(not isinstance(tool, dict) for tool in tool_schema):
        raise ValueError("lifecycle invocation tool schema is malformed")
    encoded = json.dumps(tool_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tool_schema_sha256 = hashlib.sha256(encoded).hexdigest()
    evidence_tools = [tool for tool in tool_schema if tool.get("name") == "request_evidence"]
    supports_evidence = any(checkpoint.evidence_request_budget > 0 for checkpoint in state.checkpoint_runs)
    evidence_protocol = interaction.get("evidence_request_protocol")
    if supports_evidence:
        expected_evidence_protocol = {
            **evidence_request_protocol_identity(),
            "tool_schema_sha256": tool_schema_sha256,
        }
        if len(evidence_tools) != 1 or evidence_protocol != expected_evidence_protocol:
            raise ValueError("lifecycle evidence request protocol does not match the current tool contract")
    elif evidence_tools or evidence_protocol is not None:
        raise ValueError("lifecycle invocation declares an unsupported evidence request protocol")

    operation_tools = [tool for tool in tool_schema if tool.get("name") == "execute_operation"]
    supports_operations = state.schema_version == "7"
    operation_protocol = interaction.get("lifecycle_operation_protocol")
    if supports_operations:
        try:
            validate_lifecycle_operation_tool_schema(tool_schema)
        except EvidenceLifecycleError as exc:
            raise ValueError("lifecycle operation tool schema does not match the public contract") from exc
        expected_operation_protocol = {
            **lifecycle_operation_protocol_identity(),
            "tool_schema_sha256": tool_schema_sha256,
        }
        if operation_protocol != expected_operation_protocol:
            raise ValueError("lifecycle operation protocol does not match the public tool contract")
    elif operation_tools or operation_protocol is not None:
        raise ValueError("lifecycle invocation declares an unsupported operation protocol")


def _validate_metrics_and_sessions(
    run: Path,
    state: Mapping[str, Any],
    experiment: Mapping[str, Any],
    metrics: Mapping[str, Any],
    verification: Mapping[str, Any],
    sessions: Sequence[LifecycleSessionRecord],
) -> None:
    execution = cast(dict[str, Any], experiment["execution"])
    model = cast(dict[str, Any], experiment["model"])
    outputs = cast(dict[str, Any], experiment["outputs"])
    declared = cast(dict[str, str], outputs["artifacts"])
    session_count = _non_negative_int(execution.get("session_count"), "lifecycle execution session_count")
    if session_count != len(sessions):
        raise ValueError("lifecycle execution session_count does not match session artifacts")
    configuration_records = [
        read_json_object(run / relative).get("configuration_record")
        for relative in sorted(Path(relative) for relative in declared if Path(relative).name == "agent_result.json")
    ]
    if model.get("session_configurations") != configuration_records:
        raise ValueError("lifecycle model session configurations do not match session artifacts")
    if model.get("resolved_models") != sorted({session.resolved_model for session in sessions}):
        raise ValueError("lifecycle resolved models do not match session artifacts")
    if model.get("resolved_adapters") != sorted({session.adapter for session in sessions}):
        raise ValueError("lifecycle resolved adapters do not match session artifacts")
    token_fields = {
        "input_tokens": "input_tokens",
        "output_tokens": "output_tokens",
        "cache_read_tokens": "cache_read_tokens",
        "cache_write_tokens": "cache_write_tokens",
    }
    for metric_field, session_field in token_fields.items():
        if metrics.get(metric_field) != sum(getattr(session, session_field) for session in sessions):
            raise ValueError(f"lifecycle {metric_field} does not match session artifacts")
    validate_lifecycle_run_metrics(
        run_dir=run,
        state=state,
        experiment=experiment,
        metrics=metrics,
        verification=verification,
    )


def _validate_artifact_hash(path: Path, expected: object, label: str, *, root: Path) -> None:
    try:
        selected = require_lifecycle_regular_file(root=root, path=path, label=label)
    except ValueError as exc:
        raise ValueError(f"{label} is not a contained regular file") from exc
    if not isinstance(expected, str) or file_sha256(selected) != expected:
        raise ValueError(f"{label} hash does not match the canonical manifest")


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _positive_int(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _non_negative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _non_negative_number(value: object, label: str) -> int | float:
    if type(value) not in {int, float}:
        raise ValueError(f"{label} must be a finite non-negative number")
    number = cast(int | float, value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return number


def _execution_status(value: str) -> Literal["completed", "failed", "partial"]:
    if value not in {"completed", "failed", "partial"}:
        raise ValueError(f"lifecycle execution status is invalid: {value}")
    return cast(Literal["completed", "failed", "partial"], value)


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"lifecycle invocation index does not exist: {path}")
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object in lifecycle invocation index: {path}")
        entries.append(cast(dict[str, Any], payload))
    return entries


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = (
    "ValidatedLifecycleEvidence",
    "file_sha256",
    "validate_lifecycle_finalization_evidence",
    "validate_lifecycle_run_metrics",
    "validate_lifecycle_run_snapshot",
    "validate_lifecycle_sessions",
)
