# ABOUTME: Finalizes one sealed lifecycle run into an owner-only immutable TrialRecord snapshot.
# ABOUTME: Binds frozen authority, exact task/run bytes, runtime identity, and replayed verification.

from __future__ import annotations

import json
import shutil
import stat
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import (
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
from aec_bench.ledger.durability import fsync_directory, fsync_tree, mkdir_durable
from aec_bench.meta_harness.evidence_lifecycle import (
    evidence_lifecycle_package_identity,
    read_evidence_lifecycle_state,
    validate_lifecycle_verification,
)
from aec_bench.meta_harness.evidence_lifecycle_calibration import (
    FrozenLifecycleCondition,
    LifecycleCalibrationFreeze,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import repository_provenance
from aec_bench.meta_harness.evidence_lifecycle_holdout_audit import (
    LifecycleHoldoutAuditClaim,
    LifecycleHoldoutTargetFreeze,
    lifecycle_holdout_private_layout,
    validate_lifecycle_holdout_target_mount,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_execution_contract import (
    LifecycleHoldoutRunStart,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_models import (
    LifecycleHoldoutAgentEvidence,
    LifecycleHoldoutAuditManifest,
    LifecycleHoldoutSessionEvidence,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_models import (
    holdout_record_status as _record_status,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_models import (
    holdout_verification_failures as _verification_failures,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    canonical_sha256 as _canonical_sha256,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    copy_regular_file as _copy_regular_file,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    copy_tree_exact as _copy_tree_exact,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    exclusive_finalization_lock as _exclusive_finalization_lock,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    first_ledger_timestamp as _first_ledger_timestamp,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    ledger_duration_seconds as _ledger_duration_seconds,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    media_type as _media_type,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    prepare_private_root as _prepare_private_root,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    read_json as _read_json,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    read_model as _read_model,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    require_regular_file as _require_regular_file,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    set_owner_only_directory as _set_owner_only_directory,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    set_owner_only_tree as _set_owner_only_tree,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    sha256 as _sha256,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    tree_hashes as _tree_hashes,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    tree_structure_sha256 as _tree_structure_sha256,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    validate_nonoverlap as _validate_nonoverlap,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    validate_owner_only_tree as _validate_owner_only_tree,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    validate_private_root as _validate_private_root,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    validate_private_root_destination as _validate_private_root_destination,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    validate_relative_path as _validate_relative_path,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    validate_tree_source as _validate_tree_source,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    write_private_json as _write_private_json,
)
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import (
    write_private_record as _write_private_record,
)
from aec_bench.meta_harness.evidence_lifecycle_session_records import (
    parse_lifecycle_session_records,
)
from aec_bench.meta_harness.evidence_lifecycle_source_provenance import (
    validate_repository_matches_loaded_source as _validate_repository_matches_loaded_source,
)
from aec_bench.meta_harness.evidence_lifecycle_trial_record import (
    validate_lifecycle_snapshot_state,
)
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_protocol_identity,
    validate_lifecycle_operation_tool_schema,
)
from aec_bench.task_world_templates.lifecycles import (
    SealedLifecycleMount,
    bind_sealed_lifecycle,
    verify_lifecycle_template,
)

__all__ = [
    "LifecycleHoldoutAuditManifest",
    "finalize_lifecycle_holdout_trial_record",
    "validate_lifecycle_holdout_trial_record",
]


def finalize_lifecycle_holdout_trial_record(
    *,
    run_dir: Path,
    run_start_path: Path,
    calibration_freeze_path: Path,
    target_freeze_path: Path,
    claim_path: Path,
    mount: SealedLifecycleMount,
    selected_condition: FrozenLifecycleCondition,
    private_ledger_root: Path,
    repository_dir: Path,
    agent_evidence: dict[str, Any],
    verified_result: dict[str, Any],
) -> Path:
    """Snapshot one sealed execution and idempotently publish its private record."""
    root = Path(private_ledger_root)
    _validate_private_root_destination(root)
    sources = (
        mount.package_dir,
        Path(run_dir),
        Path(run_start_path),
        Path(calibration_freeze_path),
        Path(target_freeze_path),
        Path(claim_path),
        Path(repository_dir),
    )
    _validate_nonoverlap(root, sources)
    manifest = _prepare_audit_manifest(
        run_dir=Path(run_dir),
        run_start_path=Path(run_start_path),
        calibration_freeze_path=Path(calibration_freeze_path),
        target_freeze_path=Path(target_freeze_path),
        claim_path=Path(claim_path),
        mount=mount,
        selected_condition=selected_condition,
        private_ledger_root=root,
        repository_dir=Path(repository_dir),
        agent_evidence=agent_evidence,
        verified_result=verified_result,
    )

    _prepare_private_root(root)
    artifact_dir = root / manifest.experiment_id / "_artifacts" / manifest.trial_id
    record_path = root / manifest.experiment_id / f"{manifest.trial_id}.json"
    with _exclusive_finalization_lock(root, manifest.experiment_id, manifest.trial_id):
        if record_path.exists() or record_path.is_symlink():
            record = validate_lifecycle_holdout_trial_record(
                record_path=record_path,
                private_ledger_root=root,
                mount=mount,
            )
            stored = _audit_manifest_from_record(record, root)
            if stored != manifest:
                raise ValueError("sealed holdout trial is already finalized with different content")
            return record_path

        if artifact_dir.exists() or artifact_dir.is_symlink():
            if artifact_dir.is_symlink() or not artifact_dir.is_dir():
                raise ValueError("sealed holdout snapshot conflicts with an existing path")
            stored = _read_model(artifact_dir / "authority" / "audit-manifest.json", LifecycleHoldoutAuditManifest)
            if stored != manifest:
                raise ValueError("sealed holdout snapshot already exists with different content")
            _validate_snapshot(artifact_dir, manifest=manifest, mount=mount)
            references = _snapshot_references(artifact_dir, artifact_dir, root)
            record = _build_trial_record(artifact_dir, root, manifest, references)
            _write_private_record(record_path, record, root)
            _validate_owner_only_tree(root)
            return record_path

        mkdir_durable(artifact_dir.parent)
        _set_owner_only_directory(artifact_dir.parent, root)
        staging = artifact_dir.with_name(f".{manifest.trial_id}.staging-{uuid.uuid4().hex}")
        try:
            _copy_tree_exact(mount.package_dir, staging / "package")
            _copy_tree_exact(Path(run_dir), staging / "run")
            _copy_regular_file(Path(calibration_freeze_path), staging / "authority" / "calibration-freeze.json")
            _copy_regular_file(Path(target_freeze_path), staging / "authority" / "target-freeze.json")
            _copy_regular_file(Path(claim_path), staging / "authority" / "claim.json")
            _write_private_json(staging / "authority" / "audit-manifest.json", manifest.model_dump(mode="json"))
            _set_owner_only_tree(staging)
            _validate_snapshot(staging, manifest=manifest, mount=mount)
            references = _snapshot_references(staging, artifact_dir, root)
            record = _build_trial_record(staging, root, manifest, references)
            fsync_tree(staging)
            staging.replace(artifact_dir)
            fsync_directory(artifact_dir.parent)
            _write_private_record(record_path, record, root)
        except Exception:
            if staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)
            raise
    _validate_owner_only_tree(root)
    return record_path


def validate_lifecycle_holdout_trial_record(
    *,
    record_path: Path,
    private_ledger_root: Path,
    mount: SealedLifecycleMount,
) -> TrialRecord:
    """Rebuild a private record from its immutable snapshot and replay sealed authority."""
    root = Path(private_ledger_root)
    _validate_private_root(root)
    path = Path(record_path)
    _require_regular_file(path, label="holdout TrialRecord")
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError("holdout TrialRecord escapes the private ledger root") from exc
    record = TrialRecord.model_validate_json(path.read_bytes())
    canonical_record_path = root / record.experiment_id / f"{record.trial_id}.json"
    if path.resolve() != canonical_record_path:
        raise ValueError("private holdout TrialRecord path is not canonical")
    if record.task.visibility is not Visibility.HOLDOUT:
        raise ValueError("private holdout TrialRecord must declare holdout visibility")
    if record.lifecycle_provenance is None or record.lifecycle_execution is None:
        raise ValueError("private holdout TrialRecord is missing lifecycle provenance")
    artifact_dir = root / record.experiment_id / "_artifacts" / record.trial_id
    if artifact_dir.is_symlink() or not artifact_dir.is_dir() or artifact_dir.resolve() != artifact_dir:
        raise ValueError("private holdout TrialRecord has no canonical snapshot")
    references = _validate_artifact_references(record, root, artifact_dir)
    manifest = _audit_manifest_from_record(record, root)
    _validate_snapshot(artifact_dir, manifest=manifest, mount=mount)
    expected = _build_trial_record(artifact_dir, root, manifest, references)
    if expected != record:
        raise ValueError("private holdout TrialRecord does not match its immutable snapshot")
    _validate_owner_only_tree(root)
    return record


def _prepare_audit_manifest(
    *,
    run_dir: Path,
    run_start_path: Path,
    calibration_freeze_path: Path,
    target_freeze_path: Path,
    claim_path: Path,
    mount: SealedLifecycleMount,
    selected_condition: FrozenLifecycleCondition,
    private_ledger_root: Path,
    repository_dir: Path,
    agent_evidence: dict[str, Any],
    verified_result: dict[str, Any],
) -> LifecycleHoldoutAuditManifest:
    calibration = _read_model(calibration_freeze_path, LifecycleCalibrationFreeze)
    target = validate_lifecycle_holdout_target_mount(
        target_freeze_path=target_freeze_path,
        mount=mount,
    )
    layout = lifecycle_holdout_private_layout(target)
    if (
        calibration_freeze_path != layout.calibration_freeze_path
        or claim_path != layout.claim_path
        or private_ledger_root != layout.ledger_root
    ):
        raise ValueError("sealed holdout paths do not match the target-bound private audit layout")
    claim = _read_model(claim_path, LifecycleHoldoutAuditClaim)
    run_start = _read_model(run_start_path, LifecycleHoldoutRunStart)
    selected = FrozenLifecycleCondition.model_validate(selected_condition.model_dump(mode="json"))
    if selected != calibration.selected_condition:
        raise ValueError("selected condition does not match the frozen public condition")
    _validate_authority(calibration, target, claim)
    _validate_run_start(
        run_start,
        run_start_path=run_start_path,
        run_dir=run_dir,
        private_ledger_root=private_ledger_root,
        calibration=calibration,
        target=target,
        claim=claim,
    )
    evidence = LifecycleHoldoutAgentEvidence.model_validate(agent_evidence)
    if evidence.runtime.python_version != run_start.python_version:
        raise ValueError("holdout runtime Python does not match the run-start marker")
    _validate_agent_condition(evidence, selected)
    verification = validate_lifecycle_verification(verified_result)

    package = mount.package_dir
    _validate_tree_source(package, label="sealed package")
    _validate_tree_source(run_dir, label="sealed run")
    _validate_tree_source(repository_dir, label="repository source")
    for authority_path in (calibration_freeze_path, target_freeze_path, claim_path):
        _require_regular_file(authority_path, label="holdout authority")
    with mount.activate():
        validate_lifecycle_snapshot_state(package, run_dir)
        state = read_evidence_lifecycle_state(package, run_dir)
    _validate_run_authorization(state, run_start, run_dir)
    _validate_target_state(target, state, verification)
    _validate_agent_state(evidence, state, verification, run_dir)

    _validate_repository_matches_loaded_source(repository_dir)
    repository = repository_provenance(repository_dir)
    if repository.get("repository_kind") != "git" or bool(repository.get("dirty")):
        raise ValueError("sealed holdout finalization requires a clean Git repository")
    package_files = _tree_hashes(package)
    run_files = _tree_hashes(run_dir)
    identity = evidence_lifecycle_package_identity(package)
    if (
        identity["lifecycle_id"] != target.lifecycle_id
        or identity["world_id"] != target.world_id
        or identity["spec_sha256"] != target.lifecycle_spec_sha256
        or identity["package_sha256"] != target.package_sha256
    ):
        raise ValueError("sealed holdout package does not match the target freeze")
    created_at = _first_ledger_timestamp(run_dir / "lifecycle_ledger.jsonl")
    payload = {
        "schema_version": "1",
        "experiment_id": f"sealed-holdout-{calibration.freeze_sha256}",
        "trial_id": f"holdout-{claim.claim_sha256}",
        "created_at": created_at,
        "calibration_freeze_sha256": calibration.freeze_sha256,
        "target_freeze_sha256": target.target_freeze_sha256,
        "target_commitment_sha256": target.public_target_commitment_sha256,
        "claim_sha256": claim.claim_sha256,
        "run_start_sha256": run_start.run_start_sha256,
        "lifecycle_id": target.lifecycle_id,
        "world_id": target.world_id,
        "lifecycle_spec_sha256": target.lifecycle_spec_sha256,
        "package_sha256": target.package_sha256,
        "package_tree_sha256": target.package_tree_sha256,
        "run_tree_sha256": _tree_structure_sha256(run_dir),
        "python_version": run_start.python_version,
        "repository": repository,
        "selected_condition": selected.model_dump(mode="json"),
        "agent_evidence": evidence.model_dump(mode="json"),
        "verification": verification,
        "package_files": package_files,
        "run_files": run_files,
    }
    return LifecycleHoldoutAuditManifest.model_validate(
        {**payload, "audit_manifest_sha256": _canonical_sha256(payload)}
    )


def _validate_authority(
    calibration: LifecycleCalibrationFreeze,
    target: LifecycleHoldoutTargetFreeze,
    claim: LifecycleHoldoutAuditClaim,
) -> None:
    if (
        target.public_experiment_id != calibration.experiment_id
        or target.public_manifest_sha256 != calibration.manifest_sha256
        or target.public_plan_sha256 != calibration.plan_sha256
        or target.holdout_repetitions != calibration.selection_policy.holdout_repetitions
    ):
        raise ValueError("sealed target does not match the frozen public campaign")
    if (
        claim.calibration_freeze_sha256 != calibration.freeze_sha256
        or claim.target_freeze_sha256 != target.target_freeze_sha256
        or claim.holdout_repetition != 1
        or claim.status != "claimed"
    ):
        raise ValueError("sealed audit claim does not bind the frozen campaign and target")


def _validate_run_start(
    run_start: LifecycleHoldoutRunStart,
    *,
    run_start_path: Path,
    run_dir: Path,
    private_ledger_root: Path,
    calibration: LifecycleCalibrationFreeze,
    target: LifecycleHoldoutTargetFreeze,
    claim: LifecycleHoldoutAuditClaim,
) -> None:
    layout = lifecycle_holdout_private_layout(target)
    expected_path = layout.run_start_path
    mirrored_path = run_dir / "run-start.json"
    for directory in (run_start_path.parent, run_dir):
        if directory.is_symlink() or not directory.is_dir() or stat.S_IMODE(directory.stat().st_mode) & 0o077:
            raise ValueError("sealed private execution boundary must be owner-only")
    for marker_path in (run_start_path, mirrored_path):
        if marker_path.is_symlink() or not marker_path.is_file() or stat.S_IMODE(marker_path.stat().st_mode) & 0o077:
            raise ValueError("sealed private execution authority must be owner-only")
    if run_start_path != expected_path or run_dir != layout.run_dir:
        raise ValueError("sealed execution lacks its canonical bound run-start marker")
    _require_regular_file(mirrored_path, label="bound run-start marker")
    if mirrored_path.read_bytes() != run_start_path.read_bytes():
        raise ValueError("sealed run-start marker does not match its run binding")
    if (
        Path(run_start.private_execution_root) != run_dir.parent.resolve()
        or Path(run_start.run_dir) != run_dir.resolve()
        or Path(run_start.private_ledger_root) != private_ledger_root.resolve(strict=False)
    ):
        raise ValueError("sealed run-start marker does not bind the canonical private roots")
    if (
        run_start.claim_sha256 != claim.claim_sha256
        or run_start.calibration_freeze_sha256 != calibration.freeze_sha256
        or run_start.target_freeze_sha256 != target.target_freeze_sha256
        or run_start.selected_condition != calibration.selected_condition
    ):
        raise ValueError("sealed run-start marker does not bind the claimed frozen authority")


def _validate_agent_condition(
    evidence: LifecycleHoldoutAgentEvidence,
    selected: FrozenLifecycleCondition,
) -> None:
    interrupted_unresolved = (
        evidence.status == "failed"
        and evidence.resolved_adapters == ("unresolved",)
        and all(
            session.status == "failed"
            and session.adapter_name == "unresolved"
            and session.failure_kind in {"interrupted", "interrupted_after_completion"}
            for session in evidence.sessions
        )
    )
    expected = {
        "model": selected.requested_model,
        "adapter": selected.requested_adapter,
        "execution_mode": selected.execution_mode.value,
        "memory_visibility_policy": selected.memory_visibility_policy.value,
        "max_turns_per_session": selected.max_turns_per_session,
    }
    actual = {field: getattr(evidence, field) for field in expected}
    if actual != expected or (
        evidence.resolved_adapters != (selected.resolved_adapter,) and not interrupted_unresolved
    ):
        raise ValueError("holdout agent evidence does not match the selected condition")
    runtime = evidence.runtime
    if (
        runtime.provider != selected.runtime_provider
        or runtime.distributions != selected.runtime_distributions
        or runtime.dependency_sha256 != selected.runtime_dependency_sha256
    ):
        raise ValueError("holdout runtime does not match the frozen public condition")
    interaction = evidence.interaction
    tool_schema = list(interaction.tool_schema)
    validate_lifecycle_operation_tool_schema(tool_schema)
    protocol = lifecycle_operation_protocol_identity()
    if (
        interaction.protocol != selected.interaction_protocol
        or interaction.protocol_sha256 != selected.interaction_protocol_sha256
        or interaction.tool_schema_sha256 != selected.tool_schema_sha256
        or interaction.protocol_sha256 != protocol["sha256"]
        or interaction.tool_schema_sha256 != _canonical_sha256(tool_schema)
    ):
        raise ValueError("holdout interaction does not match the frozen public condition")
    expected_session_mode = "persistent" if evidence.execution_mode == "persistent_context" else "fresh"
    for session in evidence.sessions:
        unresolved_failure = evidence.status == "failed" and session.resolved_model == "unresolved"
        unresolved_adapter = (
            interrupted_unresolved
            and session.adapter_name == "unresolved"
            and session.failure_kind in {"interrupted", "interrupted_after_completion"}
        )
        if (
            session.model != selected.requested_model
            or session.adapter != selected.requested_adapter
            or (session.adapter_name != selected.resolved_adapter and not unresolved_adapter)
            or (session.resolved_model != selected.resolved_model and not unresolved_failure)
            or session.session_mode != expected_session_mode
            or session.memory_visibility_policy != selected.memory_visibility_policy.value
            or session.max_turns != selected.max_turns_per_session
        ):
            raise ValueError("holdout session does not match the selected condition")
    token_fields = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
    for field in token_fields:
        if getattr(evidence.totals, field) != sum(getattr(session, field) for session in evidence.sessions):
            raise ValueError(f"holdout {field} total does not match session evidence")
    failures = sum(session.status not in {"completed", "ok"} for session in evidence.sessions)
    if evidence.totals.failures != failures:
        raise ValueError("holdout failure total does not match session evidence")
    if (evidence.status == "completed") != (failures == 0):
        raise ValueError("holdout execution status does not match session evidence")


def _validate_target_state(
    target: LifecycleHoldoutTargetFreeze,
    state: dict[str, Any],
    verification: dict[str, Any],
) -> None:
    expected = {
        "lifecycle_id": target.lifecycle_id,
        "world_id": target.world_id,
        "lifecycle_spec_sha256": target.lifecycle_spec_sha256,
        "package_sha256": target.package_sha256,
    }
    if any(state.get(field) != value for field, value in expected.items()):
        raise ValueError("sealed run state does not match the target freeze")
    if verification.get("lifecycle_id") != target.lifecycle_id:
        raise ValueError("sealed verification does not match the target freeze")


def _validate_run_authorization(
    state: dict[str, Any],
    run_start: LifecycleHoldoutRunStart,
    run_dir: Path,
) -> None:
    if state.get("run_authorization_sha256") != run_start.run_start_sha256:
        raise ValueError("sealed run authorization is not bound into lifecycle state")
    ledger_path = Path(run_dir) / "lifecycle_ledger.jsonl"
    try:
        first_line = next(line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip())
        first_entry = json.loads(first_line)
    except (FileNotFoundError, StopIteration, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("sealed run authorization has no first durable ledger event") from exc
    summary = first_entry.get("summary") if isinstance(first_entry, dict) else None
    if (
        not isinstance(summary, dict)
        or first_entry.get("stage") != "run_authorization"
        or first_entry.get("status") != "authorized"
        or summary.get("run_authorization_sha256") != run_start.run_start_sha256
    ):
        raise ValueError("sealed run authorization is not bound into the first durable ledger event")


def _validate_agent_state(
    evidence: LifecycleHoldoutAgentEvidence,
    state: dict[str, Any],
    verification: dict[str, Any],
    run_dir: Path,
) -> None:
    canonical = _parse_holdout_sessions(
        run_dir=run_dir,
        artifacts=[],
        state=state,
        evidence=evidence,
        verification=verification,
    )
    expected = [_session_record_from_evidence(session) for session in evidence.sessions]
    if canonical != expected:
        raise ValueError("holdout agent evidence does not match canonical on-disk session results")
    if tuple(sorted({session.adapter for session in canonical})) != evidence.resolved_adapters:
        raise ValueError("holdout resolved adapters do not match canonical session results")
    token_fields = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
    for field in token_fields:
        if getattr(evidence.totals, field) != sum(getattr(session, field) for session in canonical):
            raise ValueError(f"holdout {field} total does not match canonical session results")
    failures = sum(session.status != "completed" for session in canonical)
    if evidence.totals.failures != failures:
        raise ValueError("holdout failure total does not match canonical session results")


def _parse_holdout_sessions(
    *,
    run_dir: Path,
    artifacts: list[ArtifactReference],
    state: dict[str, Any],
    evidence: LifecycleHoldoutAgentEvidence,
    verification: dict[str, Any],
) -> list[LifecycleSessionRecord]:
    return parse_lifecycle_session_records(
        run_dir=run_dir,
        artifact_references=artifacts,
        state=state,
        declared_run_artifacts=_tree_hashes(run_dir),
        requested_model=evidence.model,
        requested_adapter=evidence.adapter,
        execution_mode=evidence.execution_mode,
        memory_visibility_policy=evidence.memory_visibility_policy,
        max_turns_per_session=evidence.max_turns_per_session,
        execution_status=_record_status(evidence.status),
        verification=verification,
    )


def _session_record_from_evidence(session: LifecycleHoldoutSessionEvidence) -> LifecycleSessionRecord:
    return LifecycleSessionRecord(
        session_id=session.session_id,
        checkpoint_ids=list(session.checkpoint_ids),
        requested_adapter=session.adapter,
        adapter=session.adapter_name,
        resolved_model=session.resolved_model,
        execution_mode=("persistent_context" if session.session_mode == "persistent" else "fresh_context"),
        memory_visibility_policy=session.memory_visibility_policy,
        configuration=session.configuration_record,
        status=_record_status(session.status),
        input_tokens=session.input_tokens,
        output_tokens=session.output_tokens,
        cache_read_tokens=session.cache_read_tokens,
        cache_write_tokens=session.cache_write_tokens,
        failure_kind=session.failure_kind,
        provider_error=session.provider_error,
        artifacts=[],
    )


def _validate_snapshot(
    artifact_dir: Path,
    *,
    manifest: LifecycleHoldoutAuditManifest,
    mount: SealedLifecycleMount,
) -> None:
    root_entries = {path.name: "directory" if path.is_dir() else "other" for path in artifact_dir.iterdir()}
    if root_entries != {"authority": "directory", "package": "directory", "run": "directory"}:
        raise ValueError("sealed holdout snapshot root inventory is invalid")
    if _tree_hashes(artifact_dir / "package") != manifest.package_files:
        raise ValueError("sealed holdout package snapshot does not match its audit manifest")
    if _tree_hashes(artifact_dir / "run") != manifest.run_files:
        raise ValueError("sealed holdout run snapshot does not match its audit manifest")
    if _tree_structure_sha256(artifact_dir / "run") != manifest.run_tree_sha256:
        raise ValueError("sealed holdout run tree does not match its audit manifest")
    authority = artifact_dir / "authority"
    actual_authority = {path.name: "file" if path.is_file() else "other" for path in authority.iterdir()}
    expected_authority = {
        "audit-manifest.json": "file",
        "calibration-freeze.json": "file",
        "claim.json": "file",
        "target-freeze.json": "file",
    }
    if actual_authority != expected_authority or any(path.is_symlink() for path in authority.iterdir()):
        raise ValueError("sealed holdout authority snapshot inventory is invalid")
    stored = _read_model(authority / "audit-manifest.json", LifecycleHoldoutAuditManifest)
    if stored != manifest:
        raise ValueError("sealed holdout audit manifest does not match the snapshot")
    calibration = _read_model(authority / "calibration-freeze.json", LifecycleCalibrationFreeze)
    target = _read_model(authority / "target-freeze.json", LifecycleHoldoutTargetFreeze)
    claim = _read_model(authority / "claim.json", LifecycleHoldoutAuditClaim)
    run_start = _read_model(artifact_dir / "run" / "run-start.json", LifecycleHoldoutRunStart)
    _validate_authority(calibration, target, claim)
    if (
        calibration.freeze_sha256 != manifest.calibration_freeze_sha256
        or target.target_freeze_sha256 != manifest.target_freeze_sha256
        or target.public_target_commitment_sha256 != manifest.target_commitment_sha256
        or claim.claim_sha256 != manifest.claim_sha256
        or run_start.run_start_sha256 != manifest.run_start_sha256
        or calibration.selected_condition != manifest.selected_condition
        or run_start.selected_condition != manifest.selected_condition
        or run_start.claim_sha256 != claim.claim_sha256
        or run_start.calibration_freeze_sha256 != calibration.freeze_sha256
        or run_start.target_freeze_sha256 != target.target_freeze_sha256
        or run_start.python_version != manifest.python_version
    ):
        raise ValueError("sealed holdout authority does not match the audit manifest")
    normalized = validate_lifecycle_verification(manifest.verification)
    with tempfile.TemporaryDirectory(prefix="aec-bench-sealed-replay-") as temporary_name:
        temporary = Path(temporary_name)
        replay_package = temporary / "package"
        replay_run = temporary / "run"
        _copy_tree_exact(artifact_dir / "package", replay_package)
        _copy_tree_exact(artifact_dir / "run", replay_run)
        rebound = bind_sealed_lifecycle(mount.provider, replay_package)
        if (
            rebound.package_sha256 != mount.package_sha256
            or rebound.package_tree_sha256 != mount.package_tree_sha256
            or rebound.package_sha256 != manifest.package_sha256
            or rebound.package_tree_sha256 != manifest.package_tree_sha256
        ):
            raise ValueError("sealed holdout snapshot does not match the explicit provider mount")
        validate_lifecycle_holdout_target_mount(
            target_freeze_path=authority / "target-freeze.json",
            mount=rebound,
            require_authority_location=False,
        )
        with rebound.activate():
            validate_lifecycle_snapshot_state(replay_package, replay_run)
            state = read_evidence_lifecycle_state(replay_package, replay_run)
            _validate_run_authorization(state, run_start, replay_run)
            verification = (
                normalized
                if normalized["overall"] == "incomplete"
                else verify_lifecycle_template(replay_package, replay_run)
            )
    if verification != normalized:
        raise ValueError("sealed holdout verifier replay does not match the audit manifest")
    _validate_target_state(target, state, normalized)
    _validate_agent_condition(manifest.agent_evidence, manifest.selected_condition)
    _validate_agent_state(manifest.agent_evidence, state, normalized, artifact_dir / "run")


def _build_trial_record(
    artifact_dir: Path,
    ledger_root: Path,
    manifest: LifecycleHoldoutAuditManifest,
    artifacts: list[ArtifactReference],
) -> TrialRecord:
    condition = manifest.selected_condition
    evidence = manifest.agent_evidence
    verification = validate_lifecycle_verification(manifest.verification)
    repository = manifest.repository
    audit_manifest = _single_artifact(artifacts, "lifecycle_sealed_audit_manifest")
    calibration_freeze = _single_artifact(artifacts, "lifecycle_calibration_freeze")
    target_freeze = _single_artifact(artifacts, "lifecycle_sealed_target_freeze")
    claim = _single_artifact(artifacts, "lifecycle_sealed_audit_claim")
    state = _read_json(artifact_dir / "run" / "state.json")
    sessions = _parse_holdout_sessions(
        run_dir=artifact_dir / "run",
        artifacts=artifacts,
        state=state,
        evidence=evidence,
        verification=verification,
    )
    if any(not session.artifacts for session in sessions):
        raise ValueError("holdout session has no immutable on-disk artifacts")
    input_files = [
        FileReference(
            path=artifact.path,
            hash=artifact.sha256,
            source=artifact.path.split("/package/", maxsplit=1)[-1],
        )
        for artifact in artifacts
        if "/package/" in f"/{artifact.path}"
    ]
    raw_outputs = [artifact.path for artifact in artifacts if artifact.kind == "raw_output"]
    conversations = [artifact.path for artifact in artifacts if artifact.kind == "conversation"]
    trajectories = [artifact.path for artifact in artifacts if artifact.kind == "trajectory"]
    verifier_completed = verification["overall"] != "incomplete"
    execution_status = _record_status(evidence.status)
    repository_kind = repository.get("repository_kind", "source_tree")
    if repository_kind not in {"git", "source_tree"}:
        raise ValueError("sealed holdout repository provenance kind is invalid")
    repository_commit = str(repository.get("commit") or "unknown")
    repository_dirty_digest = str(repository.get("dirty_digest") or "")
    source_inventory = str(repository.get("source_inventory_sha256") or "")
    ArtifactReference.validate_sha256(repository_dirty_digest)
    ArtifactReference.validate_sha256(source_inventory)
    record = TrialRecord(
        trial_id=manifest.trial_id,
        experiment_id=manifest.experiment_id,
        timestamp=datetime.fromisoformat(manifest.created_at.replace("Z", "+00:00")),
        task=TaskReference(
            task_id=manifest.lifecycle_id,
            task_revision=manifest.package_sha256,
            visibility=Visibility.HOLDOUT,
        ),
        agent=AgentReference(
            adapter=condition.resolved_adapter,
            model=condition.resolved_model,
            adapter_revision=repository_commit,
            configuration={
                "requested_model": condition.requested_model,
                "requested_adapter": condition.requested_adapter,
                "execution_mode": condition.execution_mode.value,
                "memory_visibility_policy": condition.memory_visibility_policy.value,
                "max_turns_per_session": condition.max_turns_per_session,
                "calibration_freeze_sha256": manifest.calibration_freeze_sha256,
                "target_freeze_sha256": manifest.target_freeze_sha256,
                "claim_sha256": manifest.claim_sha256,
                "run_start_sha256": manifest.run_start_sha256,
            },
        ),
        environment=EnvironmentSnapshot(
            runtime_image=f"python:{manifest.python_version}",
            compute_backend="local_private_holdout",
            tool_versions={
                "aec_bench_revision": repository_commit,
                "aec_bench_source_inventory_sha256": source_inventory,
                "python": manifest.python_version,
            },
        ),
        inputs=InputRecord(
            instruction=_lifecycle_instruction(artifact_dir / "package"),
            input_files=input_files,
        ),
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=(AgentOutputStatus.COMPLETED if execution_status == "completed" else AgentOutputStatus.FAILED),
                output_path=(Path(manifest.experiment_id) / "_artifacts" / manifest.trial_id / "run").as_posix(),
                output_format="evidence_lifecycle",
                error_message=(None if execution_status == "completed" else "sealed lifecycle execution failed"),
            ),
            raw_output_path=_single_path(raw_outputs),
            conversation_path=_single_path(conversations),
            trajectory_path=_single_path(trajectories),
            agent_result={
                "execution_status": evidence.status,
                "audit_manifest": audit_manifest.path,
                "verification": verification,
                "sessions": evidence.model_dump(mode="json")["sessions"],
            },
            artifacts=artifacts,
        ),
        evaluation=EvaluationResult(
            reward=float(verification["reward"]),
            validity=ValidityCheck(
                output_parseable=state.get("status") == "complete",
                schema_valid=state.get("status") == "complete" and verifier_completed,
                verifier_completed=verifier_completed,
                errors=_verification_failures(verification),
            ),
            breakdown={
                "lifecycle_gates": verification.get("gates", {}),
                "semantic_transition": verification.get("semantic_metrics"),
            },
        ),
        timing=TimingRecord(
            total_seconds=_ledger_duration_seconds(artifact_dir / "run" / "lifecycle_ledger.jsonl"),
        ),
        cost=CostRecord(
            tokens_in=evidence.totals.input_tokens,
            tokens_out=evidence.totals.output_tokens,
            cache_read_tokens=evidence.totals.cache_read_tokens,
            cache_write_tokens=evidence.totals.cache_write_tokens,
        ),
        lifecycle_execution=LifecycleExecutionRecord(
            execution_mode=evidence.execution_mode,
            memory_visibility_policy=evidence.memory_visibility_policy,
            max_turns_per_session=evidence.max_turns_per_session,
            status=execution_status,
            sessions=sessions,
        ),
        lifecycle_provenance=LifecycleTrialProvenance(
            lifecycle_id=manifest.lifecycle_id,
            world_id=manifest.world_id,
            spec_sha256=manifest.lifecycle_spec_sha256,
            package_sha256=manifest.package_sha256,
            repository_commit=repository_commit,
            repository_kind=cast(Literal["git", "source_tree"], repository_kind),
            repository_dirty=bool(repository.get("dirty")),
            repository_dirty_digest=repository_dirty_digest,
            runtime_provider=evidence.runtime.provider,
            runtime_distributions=evidence.runtime.distributions,
            runtime_dependency_sha256=evidence.runtime.dependency_sha256,
            verifier_qualified_name="sealed_lifecycle_provider.verify",
            verifier_source_sha256=_read_model(
                artifact_dir / "authority" / "target-freeze.json",
                LifecycleHoldoutTargetFreeze,
            ).provider_identity.verifier_contract_sha256,
            invocation_manifest=audit_manifest,
            calibration_freeze=calibration_freeze,
            sealed_target_freeze=target_freeze,
            sealed_audit_claim=claim,
            sealed_audit_manifest=audit_manifest,
        ),
        completeness=(
            Completeness.COMPLETE
            if all(session.resolved_model != "unresolved" and session.adapter != "unresolved" for session in sessions)
            else Completeness.PARTIAL
        ),
    )
    return record


def _validate_artifact_references(
    record: TrialRecord,
    ledger_root: Path,
    artifact_dir: Path,
) -> list[ArtifactReference]:
    artifacts = list(record.outputs.artifacts or ())
    if not artifacts:
        raise ValueError("private holdout TrialRecord has no artifact references")
    referenced: set[str] = set()
    for artifact in artifacts:
        _validate_relative_path(artifact.path)
        if artifact.path in referenced:
            raise ValueError("private holdout TrialRecord contains duplicate artifact paths")
        referenced.add(artifact.path)
        path = ledger_root / artifact.path
        _require_regular_file(path, label="holdout snapshot artifact")
        try:
            path.resolve().relative_to(artifact_dir)
        except ValueError as exc:
            raise ValueError("holdout artifact reference escapes the immutable snapshot") from exc
        if _sha256(path) != artifact.sha256:
            raise ValueError("holdout artifact hash does not match the immutable snapshot")
    actual = {
        path.relative_to(ledger_root).as_posix()
        for path in artifact_dir.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    if referenced != actual:
        raise ValueError("holdout artifact references do not match the snapshot inventory")
    return artifacts


def _audit_manifest_from_record(record: TrialRecord, ledger_root: Path) -> LifecycleHoldoutAuditManifest:
    provenance = record.lifecycle_provenance
    if provenance is None or provenance.sealed_audit_manifest is None:
        raise ValueError("private holdout TrialRecord has no sealed audit manifest")
    if provenance.invocation_manifest != provenance.sealed_audit_manifest:
        raise ValueError("private holdout invocation and audit manifests must be identical")
    path = ledger_root / provenance.sealed_audit_manifest.path
    _require_regular_file(path, label="sealed audit manifest")
    if _sha256(path) != provenance.sealed_audit_manifest.sha256:
        raise ValueError("sealed audit manifest artifact hash mismatch")
    return _read_model(path, LifecycleHoldoutAuditManifest)


def _snapshot_references(staging: Path, final: Path, ledger_root: Path) -> list[ArtifactReference]:
    references = [
        ArtifactReference(
            kind=_artifact_kind(path.relative_to(staging)),
            path=(final / path.relative_to(staging)).relative_to(ledger_root).as_posix(),
            sha256=_sha256(path),
            media_type=_media_type(path),
        )
        for path in sorted(staging.rglob("*"))
        if path.is_file() and not path.is_symlink()
    ]
    if not references:
        raise ValueError("sealed holdout snapshot is empty")
    return references


def _artifact_kind(relative: Path) -> str:
    path = relative.as_posix()
    if path == "authority/audit-manifest.json":
        return "lifecycle_sealed_audit_manifest"
    if path == "authority/calibration-freeze.json":
        return "lifecycle_calibration_freeze"
    if path == "authority/target-freeze.json":
        return "lifecycle_sealed_target_freeze"
    if path == "authority/claim.json":
        return "lifecycle_sealed_audit_claim"
    if path.startswith("package/"):
        return "lifecycle_package"
    if path == "run/verification.json":
        return "lifecycle_verification"
    if path == "run/state.json":
        return "lifecycle_state"
    if path == "run/lifecycle_ledger.jsonl":
        return "lifecycle_ledger"
    if path.endswith("/trajectory.jsonl"):
        return "trajectory"
    if path.endswith("/conversation.jsonl"):
        return "conversation"
    if path.endswith("/raw_output.md"):
        return "raw_output"
    return "lifecycle_run_artifact"


def _single_artifact(artifacts: list[ArtifactReference], kind: str) -> ArtifactReference:
    matches = [artifact for artifact in artifacts if artifact.kind == kind]
    if len(matches) != 1:
        raise ValueError(f"sealed holdout snapshot requires exactly one {kind}")
    return matches[0]


def _lifecycle_instruction(package_dir: Path) -> str:
    parts = [path.read_text(encoding="utf-8").strip() for path in sorted((package_dir / "instructions").glob("*.md"))]
    instruction = "\n\n".join(part for part in parts if part)
    if not instruction:
        raise ValueError("sealed lifecycle package instructions are empty")
    return instruction


def _single_path(paths: list[str]) -> str | None:
    return paths[0] if len(paths) == 1 else None
