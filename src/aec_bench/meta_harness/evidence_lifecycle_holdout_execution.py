# ABOUTME: Executes or recovers exactly one claim-bound sealed lifecycle audit under private roots.
# ABOUTME: Supplies the production private recorder while keeping public recording guards unchanged.

from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.durability import fsync_directory, mkdir_durable
from aec_bench.meta_harness.evidence_lifecycle import (
    load_evidence_lifecycle_spec,
    read_evidence_lifecycle_state,
    validate_lifecycle_verification,
)
from aec_bench.meta_harness.evidence_lifecycle_calibration import (
    FrozenLifecycleCondition,
    LifecycleCalibrationFreeze,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import (
    LifecycleExperimentRecordingResult,
    LifecycleExperimentSweepContext,
    runtime_dependency_provenance,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_audit import (
    LifecycleHoldoutAuditClaim,
    LifecycleHoldoutTargetFreeze,
    claim_lifecycle_holdout_audit,
    lifecycle_holdout_private_layout,
    validate_lifecycle_holdout_target_mount,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_execution_contract import (
    LifecycleHoldoutRunStart,
    build_lifecycle_holdout_run_start,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_record import (
    finalize_lifecycle_holdout_trial_record,
    validate_lifecycle_holdout_trial_record,
)
from aec_bench.meta_harness.evidence_lifecycle_local import (
    build_lifecycle_tool_schema,
    run_local_evidence_lifecycle_fresh_context,
    run_local_evidence_lifecycle_session,
    seal_interrupted_lifecycle_session_results,
)
from aec_bench.meta_harness.lifecycle_operation_protocol import lifecycle_operation_protocol_identity
from aec_bench.task_world_templates.lifecycles import (
    SealedLifecycleMount,
    verify_lifecycle_template,
)

__all__ = [
    "LifecycleHoldoutExecutionResult",
    "LifecycleHoldoutExperimentRecorder",
    "LifecycleHoldoutRunStart",
    "execute_lifecycle_holdout_audit_once",
    "recover_lifecycle_holdout_audit_once",
]


@dataclass(frozen=True)
class LifecycleHoldoutExecutionResult:
    claim_path: Path
    run_start_path: Path
    run_dir: Path
    record_path: Path


@dataclass(frozen=True)
class LifecycleHoldoutExperimentRecorder:
    """Bind the local runner's observed evidence to one claimed private finalizer."""

    calibration_freeze_path: Path
    target_freeze_path: Path
    claim_path: Path
    run_start_path: Path
    mount: SealedLifecycleMount
    selected_condition: FrozenLifecycleCondition
    private_ledger_root: Path
    repository_dir: Path
    _record_path: Path | None = None

    def __call__(
        self,
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
    ) -> LifecycleExperimentRecordingResult:
        if not callable(verifier):
            raise ValueError("sealed holdout recorder requires a host verifier")
        if index_path is not None or sweep_context is not None:
            raise ValueError("sealed holdout recorder does not accept public index or sweep authority")
        if Path(package_dir).resolve() != self.mount.package_dir or Path(run_dir).resolve() != self.run_dir:
            raise ValueError("sealed holdout recorder received a different package or run")
        selected_repository = Path(repository_dir or self.repository_dir)
        if selected_repository.resolve() != self.repository_dir.resolve():
            raise ValueError("sealed holdout recorder received different repository provenance")
        runtime = runtime_dependency_provenance(
            adapter_kind=str(agent.get("adapter") or ""),
            model_name=str(agent.get("model") or ""),
        )
        marker = _read_model(self.run_start_path, LifecycleHoldoutRunStart)
        observed = {
            **agent,
            "runtime": {
                "provider": runtime["provider"],
                "distributions": runtime["distributions"],
                "dependency_sha256": runtime["dependency_inventory_sha256"],
                "python_version": marker.python_version,
            },
            "interaction": {
                "protocol": "lifecycle_operation",
                "protocol_sha256": lifecycle_operation_protocol_identity()["sha256"],
                "tool_schema": tool_schema,
                "tool_schema_sha256": _canonical_sha256(tool_schema),
            },
        }
        record_path = finalize_lifecycle_holdout_trial_record(
            run_dir=Path(run_dir),
            run_start_path=self.run_start_path,
            calibration_freeze_path=self.calibration_freeze_path,
            target_freeze_path=self.target_freeze_path,
            claim_path=self.claim_path,
            mount=self.mount,
            selected_condition=self.selected_condition,
            private_ledger_root=self.private_ledger_root,
            repository_dir=self.repository_dir,
            agent_evidence=observed,
            verified_result=verification,
        )
        object.__setattr__(self, "_record_path", record_path)
        record = TrialRecord.model_validate_json(record_path.read_bytes())
        provenance = record.lifecycle_provenance
        if provenance is None or provenance.sealed_audit_manifest is None:
            raise ValueError("sealed holdout recorder produced no audit manifest")
        manifest_path = self.private_ledger_root / provenance.sealed_audit_manifest.path
        return LifecycleExperimentRecordingResult(
            experiment_id=record.experiment_id,
            manifest=str(manifest_path),
            canonical_manifest=str(manifest_path),
            manifest_sha256=provenance.sealed_audit_manifest.sha256,
            metrics=str(record_path),
            verification=str(record_path),
            index=str(record_path),
        )

    @property
    def run_dir(self) -> Path:
        return Path(_read_model(self.run_start_path, LifecycleHoldoutRunStart).run_dir)

    @property
    def record_path(self) -> Path:
        if self._record_path is None:
            raise ValueError("sealed holdout recorder has not finalized a record")
        return self._record_path


def execute_lifecycle_holdout_audit_once(
    *,
    calibration_freeze_path: Path,
    target_freeze_path: Path,
    mount: SealedLifecycleMount,
    claim_path: Path,
    private_execution_root: Path,
    private_ledger_root: Path,
    repository_dir: Path,
    registry: Any,
) -> LifecycleHoldoutExecutionResult:
    """Claim, bind, and execute exactly one sealed audit through the selected local condition."""
    execution_root = Path(private_execution_root)
    ledger_root = Path(private_ledger_root)
    _validate_new_private_root(execution_root, label="private execution root")
    _validate_private_root_destination(ledger_root, label="private ledger root")
    calibration = _read_model(Path(calibration_freeze_path), LifecycleCalibrationFreeze)
    target = validate_lifecycle_holdout_target_mount(
        target_freeze_path=Path(target_freeze_path),
        mount=mount,
    )
    layout = lifecycle_holdout_private_layout(target)
    if (
        Path(calibration_freeze_path) != layout.calibration_freeze_path
        or Path(claim_path) != layout.claim_path
        or execution_root != layout.execution_root
        or ledger_root != layout.ledger_root
    ):
        raise ValueError("sealed holdout paths do not match the target-bound private audit layout")
    claim = claim_lifecycle_holdout_audit(
        calibration_freeze_path=Path(calibration_freeze_path),
        target_freeze_path=Path(target_freeze_path),
        mount=mount,
        output_path=Path(claim_path),
    )
    _validate_claim_authority(calibration, target, claim)
    _create_private_directory(execution_root)
    _create_private_directory(ledger_root)
    run_dir = execution_root / "run"
    _create_private_directory(run_dir)
    run_start = build_lifecycle_holdout_run_start(
        claim_sha256=claim.claim_sha256,
        calibration_freeze_sha256=calibration.freeze_sha256,
        target_freeze_sha256=target.target_freeze_sha256,
        selected_condition=calibration.selected_condition,
        private_execution_root=str(execution_root.resolve()),
        run_dir=str(run_dir.resolve()),
        private_ledger_root=str(ledger_root.resolve()),
        python_version=platform.python_version(),
    )
    run_start_path = execution_root / "run-start.json"
    content = _model_bytes(run_start)
    _write_private_exclusive(run_start_path, content)
    _write_private_exclusive(run_dir / "run-start.json", content)
    recorder = LifecycleHoldoutExperimentRecorder(
        calibration_freeze_path=Path(calibration_freeze_path),
        target_freeze_path=Path(target_freeze_path),
        claim_path=Path(claim_path),
        run_start_path=run_start_path,
        mount=mount,
        selected_condition=calibration.selected_condition,
        private_ledger_root=ledger_root,
        repository_dir=Path(repository_dir),
    )
    condition = calibration.selected_condition
    with mount.activate():
        if condition.execution_mode.value == "persistent_context":
            run_local_evidence_lifecycle_session(
                package_dir=mount.package_dir,
                run_dir=run_dir,
                model=condition.requested_model,
                verifier=verify_lifecycle_template,
                adapter_kind=condition.requested_adapter,
                max_turns=condition.max_turns_per_session,
                process_id="process.sealed-holdout",
                registry=registry,
                visibility_policy=condition.memory_visibility_policy,
                repository_dir=Path(repository_dir),
                require_adapter_identity_match=True,
                experiment_recorder=recorder,
                run_authorization_sha256=run_start.run_start_sha256,
            )
        else:
            run_local_evidence_lifecycle_fresh_context(
                package_dir=mount.package_dir,
                run_dir=run_dir,
                model=condition.requested_model,
                verifier=verify_lifecycle_template,
                adapter_kind=condition.requested_adapter,
                max_turns=condition.max_turns_per_session,
                process_id="process.sealed-holdout",
                registry=registry,
                visibility_policy=condition.memory_visibility_policy,
                repository_dir=Path(repository_dir),
                require_adapter_identity_match=True,
                experiment_recorder=recorder,
                run_authorization_sha256=run_start.run_start_sha256,
            )
    return LifecycleHoldoutExecutionResult(
        claim_path=Path(claim_path),
        run_start_path=run_start_path,
        run_dir=run_dir,
        record_path=recorder.record_path,
    )


def recover_lifecycle_holdout_audit_once(
    *,
    run_start_path: Path,
    calibration_freeze_path: Path,
    target_freeze_path: Path,
    claim_path: Path,
    mount: SealedLifecycleMount,
    repository_dir: Path,
) -> LifecycleHoldoutExecutionResult:
    """Finalize already-bound artifacts without accepting an adapter or rerunning model work."""
    marker_path = Path(run_start_path)
    if not marker_path.is_file() or marker_path.is_symlink():
        raise ValueError("recovery requires a bound run-start marker")
    marker = _read_model(marker_path, LifecycleHoldoutRunStart)
    run_dir = Path(marker.run_dir)
    ledger_root = Path(marker.private_ledger_root)
    _validate_private_execution_boundary(marker_path, run_dir)
    calibration = _read_model(Path(calibration_freeze_path), LifecycleCalibrationFreeze)
    target = validate_lifecycle_holdout_target_mount(
        target_freeze_path=Path(target_freeze_path),
        mount=mount,
    )
    layout = lifecycle_holdout_private_layout(target)
    if (
        Path(calibration_freeze_path) != layout.calibration_freeze_path
        or Path(claim_path) != layout.claim_path
        or marker_path != layout.run_start_path
        or run_dir != layout.run_dir
        or ledger_root != layout.ledger_root
    ):
        raise ValueError("sealed holdout paths do not match the target-bound private audit layout")
    claim = _read_model(Path(claim_path), LifecycleHoldoutAuditClaim)
    _validate_claim_authority(calibration, target, claim)
    _validate_marker_paths(marker, marker_path=marker_path, run_dir=run_dir, ledger_root=ledger_root)
    if (
        marker.claim_sha256 != claim.claim_sha256
        or marker.calibration_freeze_sha256 != calibration.freeze_sha256
        or marker.target_freeze_sha256 != target.target_freeze_sha256
        or marker.selected_condition != calibration.selected_condition
    ):
        raise ValueError("recovery run-start marker does not bind the claimed frozen authority")
    record_path = _record_path(ledger_root, calibration, claim)
    if record_path.is_file():
        validate_lifecycle_holdout_trial_record(
            record_path=record_path,
            private_ledger_root=ledger_root,
            mount=mount,
        )
        return LifecycleHoldoutExecutionResult(
            claim_path=Path(claim_path),
            run_start_path=marker_path,
            run_dir=run_dir,
            record_path=record_path,
        )
    condition = calibration.selected_condition
    if not list(run_dir.rglob("agent_result.json")):
        with mount.activate():
            seal_interrupted_lifecycle_session_results(
                package_dir=mount.package_dir,
                run_dir=run_dir,
                model=condition.requested_model,
                adapter_kind=condition.requested_adapter,
                max_turns=condition.max_turns_per_session,
                execution_mode=condition.execution_mode,
                visibility_policy=condition.memory_visibility_policy,
            )
    agent = _recover_agent_evidence(run_dir, condition)
    with mount.activate():
        state = read_evidence_lifecycle_state(mount.package_dir, run_dir)
        if state["status"] == "complete" and agent["status"] == "completed":
            verification = verify_lifecycle_template(mount.package_dir, run_dir)
        else:
            verification = _incomplete_verification(calibration.selected_condition, state)
    tool_schema = _tool_schema(mount.package_dir, condition)
    recorder = LifecycleHoldoutExperimentRecorder(
        calibration_freeze_path=Path(calibration_freeze_path),
        target_freeze_path=Path(target_freeze_path),
        claim_path=Path(claim_path),
        run_start_path=marker_path,
        mount=mount,
        selected_condition=condition,
        private_ledger_root=ledger_root,
        repository_dir=Path(repository_dir),
    )
    recorder(
        package_dir=mount.package_dir,
        run_dir=run_dir,
        agent=agent,
        verifier=verify_lifecycle_template,
        verification=verification,
        tool_schema=tool_schema,
        repository_dir=Path(repository_dir),
    )
    return LifecycleHoldoutExecutionResult(
        claim_path=Path(claim_path),
        run_start_path=marker_path,
        run_dir=run_dir,
        record_path=recorder.record_path,
    )


def _recover_agent_evidence(run_dir: Path, condition: FrozenLifecycleCondition) -> dict[str, Any]:
    paths = sorted(Path(run_dir).rglob("agent_result.json"))
    sessions = [_read_json(path) for path in paths]
    if not sessions:
        raise ValueError("bound sealed run has no recoverable session results")
    token_fields = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
    totals = {field: sum(int(session.get(field, 0)) for session in sessions) for field in token_fields}
    totals["failures"] = sum(session.get("status") not in {"completed", "ok"} for session in sessions)
    return {
        "schema_version": "1",
        "model": condition.requested_model,
        "adapter": condition.requested_adapter,
        "resolved_adapters": sorted({str(session.get("adapter_name") or "unresolved") for session in sessions}),
        "execution_mode": condition.execution_mode.value,
        "memory_visibility_policy": condition.memory_visibility_policy.value,
        "max_turns_per_session": condition.max_turns_per_session,
        "status": "failed" if totals["failures"] else "completed",
        "sessions": sessions,
        "totals": totals,
    }


def _tool_schema(package_dir: Path, condition: FrozenLifecycleCondition) -> list[dict[str, str]]:
    spec = load_evidence_lifecycle_spec(package_dir)
    return build_lifecycle_tool_schema(
        condition.execution_mode.value,
        supports_evidence_requests=any(item.conditional_evidence is not None for item in spec.checkpoints),
        supports_lifecycle_operations=any(item.conditional_operations is not None for item in spec.checkpoints),
    )


def _incomplete_verification(
    condition: FrozenLifecycleCondition,
    state: dict[str, Any],
) -> dict[str, Any]:
    del condition
    return validate_lifecycle_verification(
        {
            "lifecycle_id": state["lifecycle_id"],
            "overall": "incomplete",
            "passed": False,
            "reward": 0.0,
            "gates": {
                "lifecycle_runtime": {
                    "passed": False,
                    "score": 0.0,
                    "failures": [f"stopped_at:{state.get('active_checkpoint_id') or state['status']}"],
                }
            },
        }
    )


def _validate_claim_authority(
    calibration: LifecycleCalibrationFreeze,
    target: LifecycleHoldoutTargetFreeze,
    claim: LifecycleHoldoutAuditClaim,
) -> None:
    if (
        claim.calibration_freeze_sha256 != calibration.freeze_sha256
        or claim.target_freeze_sha256 != target.target_freeze_sha256
    ):
        raise ValueError("sealed holdout claim does not bind the selected campaign and target")


def _validate_marker_paths(
    marker: LifecycleHoldoutRunStart,
    *,
    marker_path: Path,
    run_dir: Path,
    ledger_root: Path,
) -> None:
    if (
        marker_path.resolve() != Path(marker.private_execution_root) / "run-start.json"
        or run_dir.resolve() != Path(marker.private_execution_root) / "run"
        or ledger_root.resolve(strict=False) != Path(marker.private_ledger_root)
    ):
        raise ValueError("recovery requires the canonical bound run-start marker")
    mirrored = run_dir / "run-start.json"
    if mirrored.is_symlink() or not mirrored.is_file() or mirrored.read_bytes() != marker_path.read_bytes():
        raise ValueError("recovery requires a bound run-start marker inside the run")


def _validate_private_execution_boundary(marker_path: Path, run_dir: Path) -> None:
    for directory in (Path(marker_path).parent, Path(run_dir)):
        if directory.is_symlink() or not directory.is_dir() or stat.S_IMODE(directory.stat().st_mode) & 0o077:
            raise ValueError("private execution boundary must be owner-only")
    for file_path in (Path(marker_path), Path(run_dir) / "run-start.json"):
        if file_path.is_symlink() or not file_path.is_file() or stat.S_IMODE(file_path.stat().st_mode) & 0o077:
            raise ValueError("private execution authority must be owner-only")


def _record_path(
    ledger_root: Path,
    calibration: LifecycleCalibrationFreeze,
    claim: LifecycleHoldoutAuditClaim,
) -> Path:
    experiment_id = f"sealed-holdout-{calibration.freeze_sha256}"
    trial_id = f"holdout-{claim.claim_sha256}"
    return ledger_root / experiment_id / f"{trial_id}.json"


def _validate_new_private_root(path: Path, *, label: str) -> None:
    if not path.is_absolute() or path.resolve(strict=False) != path or path.exists() or path.is_symlink():
        raise ValueError(f"{label} must be a new canonical absolute path")


def _validate_private_root_destination(path: Path, *, label: str) -> None:
    if not path.is_absolute() or path.resolve(strict=False) != path or path.is_symlink():
        raise ValueError(f"{label} must be a canonical absolute path")
    if path.exists() and (not path.is_dir() or stat.S_IMODE(path.stat().st_mode) & 0o077):
        raise ValueError(f"{label} must be owner-only")


def _create_private_directory(path: Path) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_dir() or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError("private audit directory must be owner-only")
        return
    path.mkdir(mode=0o700, parents=True)
    os.chmod(path, 0o700)
    fsync_directory(path.parent)


def _write_private_exclusive(path: Path, content: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("private run-start marker already exists")
    mkdir_durable(path.parent)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read_model(path: Path, model_type: type[Any]) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError("private audit authority must be a regular file")
    return model_type.model_validate_json(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _model_bytes(value: Any) -> bytes:
    return (json.dumps(value.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
