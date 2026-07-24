# ABOUTME: Tests one-shot execution and recovery for a sealed lifecycle holdout audit.
# ABOUTME: Proves claims and run markers precede real local adapter work without model calls.

from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.meta_harness.evidence_lifecycle import (
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationCondition,
    LifecycleAblationManifest,
)
from aec_bench.meta_harness.evidence_lifecycle_calibration import (
    FrozenLifecycleCondition,
    LifecycleCalibrationCandidateResult,
    LifecycleCalibrationFreeze,
    LifecycleCalibrationPlannedCondition,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_audit import (
    claim_lifecycle_holdout_audit,
    write_lifecycle_holdout_target_freeze,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_execution import (
    LifecycleHoldoutRunStart,
    execute_lifecycle_holdout_audit_once,
    recover_lifecycle_holdout_audit_once,
)
from aec_bench.meta_harness.evidence_lifecycle_holdout_execution_contract import (
    build_lifecycle_holdout_run_start,
)
from aec_bench.meta_harness.evidence_lifecycle_local import (
    EvidenceLifecycleControlTool,
    EvidenceLifecycleWorkspaceTool,
    build_lifecycle_tool_schema,
)
from aec_bench.task_world_templates.lifecycles import (
    SealedLifecycleMount,
    materialize_sealed_lifecycle,
)
from tests.support.sealed_lifecycle_audit import (
    _campaign_manifest,
    _copy_repository_source,
    _write_calibration_freeze,
)
from tests.support.sealed_lifecycle_provider import (
    FIXTURE_CHECKPOINT_ID,
    FIXTURE_OPERATION_ID,
    FakeSealedLifecycleProvider,
)


@pytest.mark.parametrize(
    ("execution_mode", "visibility_policy"),
    [
        (LifecycleExecutionMode.PERSISTENT_CONTEXT, LifecycleVisibilityPolicy.PERSISTENT_CONTEXT),
        (LifecycleExecutionMode.FRESH_CONTEXT, LifecycleVisibilityPolicy.ARTIFACT_MEMORY),
    ],
)
def test_one_shot_execution_claims_and_marks_before_exactly_one_bound_local_run(
    tmp_path: Path,
    execution_mode: LifecycleExecutionMode,
    visibility_policy: LifecycleVisibilityPolicy,
) -> None:
    prepared = _prepare_audit(
        tmp_path,
        execution_mode=execution_mode,
        visibility_policy=visibility_policy,
    )
    execution_root = prepared.private_root / "execution"
    private_ledger_root = prepared.private_root / "ledger"
    run_start_path = execution_root / "run-start.json"
    registry = _SealedOperationRegistry(
        claim_path=prepared.claim_path,
        run_start_path=run_start_path,
    )

    result = execute_lifecycle_holdout_audit_once(
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        mount=prepared.mount,
        claim_path=prepared.claim_path,
        private_execution_root=execution_root,
        private_ledger_root=private_ledger_root,
        repository_dir=prepared.repository_dir,
        registry=registry,
    )

    assert registry.build_count == 1
    assert registry.execute_count == 1
    assert registry.claim_seen_before_build is True
    assert registry.run_start_seen_before_build is True
    assert result.claim_path == prepared.claim_path
    assert result.run_start_path == run_start_path
    assert result.run_dir == execution_root / "run"
    assert result.record_path.is_file()
    assert not (result.run_dir / "experiment-manifest.json").exists()
    assert not (result.run_dir / "metrics.json").exists()
    assert not (result.run_dir / "verification.json").exists()
    assert not (execution_root / "experiment-index.jsonl").exists()

    claim = _read_json(prepared.claim_path)
    calibration = LifecycleCalibrationFreeze.model_validate_json(prepared.calibration_freeze_path.read_bytes())
    target = _read_json(prepared.target_freeze_path)
    run_start = LifecycleHoldoutRunStart.model_validate_json(run_start_path.read_bytes())
    assert run_start.claim_sha256 == claim["claim_sha256"]
    assert run_start.calibration_freeze_sha256 == calibration.freeze_sha256
    assert run_start.target_freeze_sha256 == target["target_freeze_sha256"]
    assert run_start.selected_condition == calibration.selected_condition
    assert Path(run_start.run_dir) == (execution_root / "run").resolve()
    assert Path(run_start.private_ledger_root) == private_ledger_root.resolve()
    assert run_start.execution_mode is execution_mode
    assert run_start.memory_visibility_policy is visibility_policy
    assert stat.S_IMODE(execution_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(run_start_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(private_ledger_root.stat().st_mode) == 0o700

    record = TrialRecord.model_validate_json(result.record_path.read_bytes())
    assert record.evaluation.reward == 1.0
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.execution_mode == execution_mode.value
    assert len(record.lifecycle_execution.sessions) == 1


def test_same_claim_cannot_start_a_second_run_or_call_a_second_adapter(tmp_path: Path) -> None:
    prepared = _prepare_audit(tmp_path)
    first_root = prepared.private_root / "execution"
    second_root = prepared.private_root / "alternate-execution"
    private_ledger_root = prepared.private_root / "ledger"
    registry = _SealedOperationRegistry(
        claim_path=prepared.claim_path,
        run_start_path=first_root / "run-start.json",
    )
    first = execute_lifecycle_holdout_audit_once(
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        mount=prepared.mount,
        claim_path=prepared.claim_path,
        private_execution_root=first_root,
        private_ledger_root=private_ledger_root,
        repository_dir=prepared.repository_dir,
        registry=registry,
    )

    registry.run_start_path = second_root / "run-start.json"
    with pytest.raises(ValueError, match="target-bound private audit layout"):
        execute_lifecycle_holdout_audit_once(
            calibration_freeze_path=prepared.calibration_freeze_path,
            target_freeze_path=prepared.target_freeze_path,
            mount=prepared.mount,
            claim_path=prepared.claim_path,
            private_execution_root=second_root,
            private_ledger_root=private_ledger_root,
            repository_dir=prepared.repository_dir,
            registry=registry,
        )

    assert registry.build_count == 1
    assert registry.execute_count == 1
    assert not second_root.exists()
    assert list(private_ledger_root.rglob("*.json")).count(first.record_path) == 1


@pytest.mark.parametrize("changed_path", ["claim", "execution", "ledger"])
def test_target_bound_private_layout_rejects_alternate_audit_paths_before_adapter_work(
    tmp_path: Path,
    changed_path: str,
) -> None:
    prepared = _prepare_audit(tmp_path)
    claim_path = prepared.claim_path
    execution_root = prepared.private_root / "execution"
    ledger_root = prepared.private_root / "ledger"
    if changed_path == "claim":
        claim_path = prepared.private_root / "alternate-authority" / "claim.json"
    elif changed_path == "execution":
        execution_root = prepared.private_root / "alternate-execution"
    else:
        ledger_root = prepared.private_root / "alternate-ledger"
    registry = _SealedOperationRegistry(
        claim_path=claim_path,
        run_start_path=execution_root / "run-start.json",
    )

    with pytest.raises(ValueError, match="target-bound private audit layout"):
        execute_lifecycle_holdout_audit_once(
            calibration_freeze_path=prepared.calibration_freeze_path,
            target_freeze_path=prepared.target_freeze_path,
            mount=prepared.mount,
            claim_path=claim_path,
            private_execution_root=execution_root,
            private_ledger_root=ledger_root,
            repository_dir=prepared.repository_dir,
            registry=registry,
        )

    assert registry.build_count == 0
    assert registry.execute_count == 0
    assert not claim_path.exists()


def test_recovery_refuses_a_complete_run_created_before_claim_without_a_run_start_binding(
    tmp_path: Path,
) -> None:
    prepared = _prepare_audit(tmp_path)
    execution_root = prepared.private_root / "unbound-execution"
    run_dir = execution_root / "run"
    _complete_run_without_claim(prepared.mount, run_dir)
    assert not prepared.claim_path.exists()
    claim_lifecycle_holdout_audit(
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        mount=prepared.mount,
        output_path=prepared.claim_path,
    )
    private_ledger_root = prepared.private_root / "ledger"

    with pytest.raises(ValueError, match="bound run-start marker"):
        recover_lifecycle_holdout_audit_once(
            run_start_path=execution_root / "run-start.json",
            calibration_freeze_path=prepared.calibration_freeze_path,
            target_freeze_path=prepared.target_freeze_path,
            claim_path=prepared.claim_path,
            mount=prepared.mount,
            repository_dir=prepared.repository_dir,
        )

    assert run_dir.is_dir()
    assert not private_ledger_root.exists()


def test_recovery_rejects_a_retrofitted_marker_for_work_completed_before_the_claim(
    tmp_path: Path,
) -> None:
    prepared = _prepare_audit(tmp_path)
    execution_root = prepared.private_root / "execution"
    run_dir = execution_root / "run"
    _complete_run_without_claim(prepared.mount, run_dir, write_agent_result=True)
    os.chmod(execution_root, 0o700)
    os.chmod(run_dir, 0o700)
    claim = claim_lifecycle_holdout_audit(
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        mount=prepared.mount,
        output_path=prepared.claim_path,
    )
    calibration = LifecycleCalibrationFreeze.model_validate_json(prepared.calibration_freeze_path.read_bytes())
    target = _read_json(prepared.target_freeze_path)
    run_start = build_lifecycle_holdout_run_start(
        claim_sha256=claim.claim_sha256,
        calibration_freeze_sha256=calibration.freeze_sha256,
        target_freeze_sha256=target["target_freeze_sha256"],
        selected_condition=calibration.selected_condition,
        private_execution_root=str(execution_root),
        run_dir=str(run_dir),
        private_ledger_root=str(prepared.private_root / "ledger"),
        python_version=platform.python_version(),
    )
    marker = json.dumps(run_start.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    run_start_path = execution_root / "run-start.json"
    run_start_path.write_text(marker, encoding="utf-8")
    (run_dir / "run-start.json").write_text(marker, encoding="utf-8")
    os.chmod(run_start_path, 0o600)
    os.chmod(run_dir / "run-start.json", 0o600)

    with pytest.raises(ValueError, match="run authorization"):
        recover_lifecycle_holdout_audit_once(
            run_start_path=run_start_path,
            calibration_freeze_path=prepared.calibration_freeze_path,
            target_freeze_path=prepared.target_freeze_path,
            claim_path=prepared.claim_path,
            mount=prepared.mount,
            repository_dir=prepared.repository_dir,
        )

    assert not (prepared.private_root / "ledger").exists()


def test_recovery_seals_a_terminal_crash_without_rerunning_the_adapter(
    tmp_path: Path,
) -> None:
    prepared = _prepare_audit(tmp_path)
    claim = claim_lifecycle_holdout_audit(
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        mount=prepared.mount,
        output_path=prepared.claim_path,
    )
    calibration = LifecycleCalibrationFreeze.model_validate_json(prepared.calibration_freeze_path.read_bytes())
    target = _read_json(prepared.target_freeze_path)
    execution_root = prepared.private_root / "execution"
    execution_root.mkdir(mode=0o700)
    run_dir = execution_root / "run"
    run_dir.mkdir(mode=0o700)
    run_start = build_lifecycle_holdout_run_start(
        claim_sha256=claim.claim_sha256,
        calibration_freeze_sha256=calibration.freeze_sha256,
        target_freeze_sha256=target["target_freeze_sha256"],
        selected_condition=calibration.selected_condition,
        private_execution_root=str(execution_root),
        run_dir=str(run_dir),
        private_ledger_root=str(prepared.private_root / "ledger"),
        python_version=platform.python_version(),
    )
    marker = json.dumps(run_start.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    run_start_path = execution_root / "run-start.json"
    run_start_path.write_text(marker, encoding="utf-8")
    (run_dir / "run-start.json").write_text(marker, encoding="utf-8")
    os.chmod(run_start_path, 0o600)
    os.chmod(run_dir / "run-start.json", 0o600)
    _complete_run_without_claim(
        prepared.mount,
        run_dir,
        run_authorization_sha256=run_start.run_start_sha256,
        write_trajectory=True,
    )
    assert not list(run_dir.rglob("agent_result.json"))

    recovered = recover_lifecycle_holdout_audit_once(
        run_start_path=run_start_path,
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        claim_path=prepared.claim_path,
        mount=prepared.mount,
        repository_dir=prepared.repository_dir,
    )

    record = TrialRecord.model_validate_json(recovered.record_path.read_bytes())
    assert record.evaluation.reward == 0.0
    assert record.completeness.value == "partial"
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.status == "failed"
    assert len(list(run_dir.rglob("agent_result.json"))) == 1


def test_recovery_seals_an_active_checkpoint_crash_without_rerunning_the_adapter(
    tmp_path: Path,
) -> None:
    prepared = _prepare_audit(tmp_path)
    run_start_path, run_dir, run_start = _claim_and_write_bound_run_start(prepared)
    session_id = "interrupted-active.session-001"
    with prepared.mount.activate():
        prepare_evidence_checkpoint(
            prepared.mount.package_dir,
            run_dir,
            run_authorization_sha256=run_start.run_start_sha256,
        )
        trajectory_path = run_dir / "sessions" / session_id / "trajectory.jsonl"
        trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        trajectory_path.write_text("", encoding="utf-8")
        open_checkpoint_attempt(
            prepared.mount.package_dir,
            run_dir,
            session_id=session_id,
            execution_mode="persistent_context",
        )
    assert not list(run_dir.rglob("agent_result.json"))
    assert _read_json(run_dir / "state.json")["status"] == "awaiting_checkpoint_submission"

    recovered = recover_lifecycle_holdout_audit_once(
        run_start_path=run_start_path,
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        claim_path=prepared.claim_path,
        mount=prepared.mount,
        repository_dir=prepared.repository_dir,
    )

    record = TrialRecord.model_validate_json(recovered.record_path.read_bytes())
    assert record.evaluation.reward == 0.0
    assert record.completeness.value == "partial"
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.status == "failed"
    assert len(list(run_dir.rglob("agent_result.json"))) == 1


def test_recovery_seals_a_fresh_context_crash_without_rerunning_the_adapter(
    tmp_path: Path,
) -> None:
    prepared = _prepare_audit(
        tmp_path,
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    )
    run_start_path, run_dir, run_start = _claim_and_write_bound_run_start(prepared)
    session_id = f"{FIXTURE_CHECKPOINT_ID}.session-001"
    with prepared.mount.activate():
        prepare_evidence_checkpoint(
            prepared.mount.package_dir,
            run_dir,
            run_authorization_sha256=run_start.run_start_sha256,
        )
        trajectory_path = run_dir / "episodes" / FIXTURE_CHECKPOINT_ID / session_id / "trajectory.jsonl"
        trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        trajectory_path.write_text("", encoding="utf-8")
        open_checkpoint_attempt(
            prepared.mount.package_dir,
            run_dir,
            session_id=session_id,
            execution_mode="fresh_context",
        )
    assert not list(run_dir.rglob("agent_result.json"))

    recovered = recover_lifecycle_holdout_audit_once(
        run_start_path=run_start_path,
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        claim_path=prepared.claim_path,
        mount=prepared.mount,
        repository_dir=prepared.repository_dir,
    )

    record = TrialRecord.model_validate_json(recovered.record_path.read_bytes())
    assert record.evaluation.reward == 0.0
    assert record.completeness.value == "partial"
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.execution_mode == "fresh_context"
    assert record.lifecycle_execution.status == "failed"
    assert len(list(run_dir.rglob("agent_result.json"))) == 1


def test_adapter_exception_is_recorded_once_with_zero_reward_and_recovery_never_reruns(
    tmp_path: Path,
) -> None:
    prepared = _prepare_audit(tmp_path)
    execution_root = prepared.private_root / "execution"
    run_start_path = execution_root / "run-start.json"
    private_ledger_root = prepared.private_root / "ledger"
    registry = _SealedOperationRegistry(
        claim_path=prepared.claim_path,
        run_start_path=run_start_path,
        raise_before_tools=True,
    )

    with pytest.raises(RuntimeError, match="deterministic local adapter failed"):
        execute_lifecycle_holdout_audit_once(
            calibration_freeze_path=prepared.calibration_freeze_path,
            target_freeze_path=prepared.target_freeze_path,
            mount=prepared.mount,
            claim_path=prepared.claim_path,
            private_execution_root=execution_root,
            private_ledger_root=private_ledger_root,
            repository_dir=prepared.repository_dir,
            registry=registry,
        )

    record_paths = _private_record_paths(private_ledger_root)
    assert len(record_paths) == 1
    failed_record = TrialRecord.model_validate_json(record_paths[0].read_bytes())
    assert failed_record.evaluation.reward == 0.0
    assert failed_record.lifecycle_execution is not None
    assert failed_record.lifecycle_execution.status == "failed"
    assert failed_record.outputs.agent_output.error_message == "sealed lifecycle execution failed"

    recovered = recover_lifecycle_holdout_audit_once(
        run_start_path=run_start_path,
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        claim_path=prepared.claim_path,
        mount=prepared.mount,
        repository_dir=prepared.repository_dir,
    )

    assert recovered.record_path == record_paths[0]
    assert registry.build_count == 1
    assert registry.execute_count == 1
    assert _private_record_paths(private_ledger_root) == record_paths


def test_recovery_finalizes_bound_completed_artifacts_without_calling_an_adapter_again(
    tmp_path: Path,
) -> None:
    prepared = _prepare_audit(tmp_path)
    execution_root = prepared.private_root / "execution"
    run_start_path = execution_root / "run-start.json"
    private_ledger_root = prepared.private_root / "ledger"
    registry = _SealedOperationRegistry(
        claim_path=prepared.claim_path,
        run_start_path=run_start_path,
        private_ledger_root_to_expose=private_ledger_root,
    )

    with pytest.raises(ValueError, match="owner-only"):
        execute_lifecycle_holdout_audit_once(
            calibration_freeze_path=prepared.calibration_freeze_path,
            target_freeze_path=prepared.target_freeze_path,
            mount=prepared.mount,
            claim_path=prepared.claim_path,
            private_execution_root=execution_root,
            private_ledger_root=private_ledger_root,
            repository_dir=prepared.repository_dir,
            registry=registry,
        )

    assert registry.build_count == 1
    assert registry.execute_count == 1
    assert _read_json(execution_root / "run" / "state.json")["status"] == "complete"
    assert _private_record_paths(private_ledger_root) == []

    os.chmod(private_ledger_root, 0o700)
    os.chmod(execution_root, 0o755)
    with pytest.raises(ValueError, match="owner-only"):
        recover_lifecycle_holdout_audit_once(
            run_start_path=run_start_path,
            calibration_freeze_path=prepared.calibration_freeze_path,
            target_freeze_path=prepared.target_freeze_path,
            claim_path=prepared.claim_path,
            mount=prepared.mount,
            repository_dir=prepared.repository_dir,
        )
    assert _private_record_paths(private_ledger_root) == []

    os.chmod(execution_root, 0o700)
    recovered = recover_lifecycle_holdout_audit_once(
        run_start_path=run_start_path,
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        claim_path=prepared.claim_path,
        mount=prepared.mount,
        repository_dir=prepared.repository_dir,
    )

    record = TrialRecord.model_validate_json(recovered.record_path.read_bytes())
    assert record.evaluation.reward == 1.0
    assert registry.build_count == 1
    assert registry.execute_count == 1


@dataclass(frozen=True)
class _PreparedAudit:
    private_root: Path
    mount: SealedLifecycleMount
    calibration_manifest: LifecycleAblationManifest
    calibration_freeze_path: Path
    target_freeze_path: Path
    claim_path: Path
    repository_dir: Path


def _prepare_audit(
    tmp_path: Path,
    *,
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.PERSISTENT_CONTEXT,
    visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
) -> _PreparedAudit:
    private_root = (tmp_path / "private").resolve()
    private_root.mkdir(mode=0o700)
    os.chmod(private_root, 0o700)
    provider = FakeSealedLifecycleProvider()
    mount = materialize_sealed_lifecycle(provider, private_root / "package")
    manifest = _campaign_manifest(tmp_path)
    if execution_mode is not LifecycleExecutionMode.PERSISTENT_CONTEXT:
        manifest = manifest.model_copy(
            update={
                "conditions": (
                    LifecycleAblationCondition(
                        execution_mode=execution_mode,
                        memory_visibility_policy=visibility_policy,
                    ),
                )
            }
        )
    calibration_freeze_path, calibration = _write_calibration_freeze(
        private_root / "authority" / "calibration-freeze.json",
        manifest=manifest,
        tmp_path=tmp_path,
    )
    if (
        calibration.selected_condition.execution_mode is not execution_mode
        or calibration.selected_condition.memory_visibility_policy is not visibility_policy
    ):
        calibration = _replace_selected_condition(
            calibration,
            execution_mode=execution_mode,
            visibility_policy=visibility_policy,
        )
        calibration_freeze_path.write_text(
            json.dumps(calibration.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(calibration_freeze_path, 0o600)
    target_freeze_path = write_lifecycle_holdout_target_freeze(
        calibration_manifest=manifest,
        mount=mount,
        commitment_salt="f" * 64,
        output_path=private_root / "authority" / "target-freeze.json",
    )
    return _PreparedAudit(
        private_root=private_root,
        mount=mount,
        calibration_manifest=manifest,
        calibration_freeze_path=calibration_freeze_path,
        target_freeze_path=target_freeze_path,
        claim_path=private_root / "authority" / "claim.json",
        repository_dir=_copy_repository_source(private_root / "repository"),
    )


def _replace_selected_condition(
    calibration: LifecycleCalibrationFreeze,
    *,
    execution_mode: LifecycleExecutionMode,
    visibility_policy: LifecycleVisibilityPolicy,
) -> LifecycleCalibrationFreeze:
    selected_payload = calibration.selected_condition.model_dump(mode="json")
    selected_payload.update(
        {
            "execution_mode": execution_mode.value,
            "memory_visibility_policy": visibility_policy.value,
            "tool_schema_sha256": _canonical_sha256(
                build_lifecycle_tool_schema(
                    execution_mode.value,
                    supports_evidence_requests=False,
                    supports_lifecycle_operations=True,
                )
            ),
        }
    )
    selected = FrozenLifecycleCondition.model_validate(selected_payload)
    planned = LifecycleCalibrationPlannedCondition.model_validate(
        {field: getattr(selected, field) for field in LifecycleCalibrationPlannedCondition.model_fields}
    )
    candidate = LifecycleCalibrationCandidateResult.model_validate(
        {
            **calibration.candidates[0].model_dump(mode="json"),
            "candidate_id": f"condition-{_canonical_sha256(planned.model_dump(mode='json'))}",
            "planned_condition": planned.model_dump(mode="json"),
            "frozen_condition": selected.model_dump(mode="json"),
        }
    )
    payload = calibration.model_dump(mode="json", exclude={"freeze_sha256"})
    payload.update(
        {
            "selected_candidate_id": candidate.candidate_id,
            "selected_condition": selected.model_dump(mode="json"),
            "candidates": [candidate.model_dump(mode="json")],
        }
    )
    return LifecycleCalibrationFreeze.model_validate({**payload, "freeze_sha256": _canonical_sha256(payload)})


class _SealedOperationRegistry:
    def __init__(
        self,
        *,
        claim_path: Path,
        run_start_path: Path,
        raise_before_tools: bool = False,
        private_ledger_root_to_expose: Path | None = None,
    ) -> None:
        self.claim_path = claim_path
        self.run_start_path = run_start_path
        self.raise_before_tools = raise_before_tools
        self.private_ledger_root_to_expose = private_ledger_root_to_expose
        self.build_count = 0
        self.execute_count = 0
        self.claim_seen_before_build = False
        self.run_start_seen_before_build = False

    def build(self, *, native_tools: list[Any], **_kwargs: Any) -> Any:
        self.build_count += 1
        self.claim_seen_before_build = self.claim_path.is_file()
        self.run_start_seen_before_build = self.run_start_path.is_file()
        assert self.claim_seen_before_build
        assert self.run_start_seen_before_build
        tools = {tool.__name__: tool for tool in native_tools}
        registry = self

        class _SealedOperationAdapter:
            def execute(self, _request: Any) -> SimpleNamespace:
                registry.execute_count += 1
                if registry.raise_before_tools:
                    raise RuntimeError("deterministic local adapter failed")
                source_response = json.loads(tools["read_workspace_file"]("hydraulics/current-source.json"))
                source = json.loads(source_response["content"])
                operation = json.loads(
                    tools["execute_operation"](
                        FIXTURE_CHECKPOINT_ID,
                        FIXTURE_OPERATION_ID,
                        source["visible_source_state_sha256"],
                        "Derive the declared deterministic observation.",
                    )
                )
                artifact_response = json.loads(tools["read_workspace_file"](operation["artifacts"][0]["path"]))
                artifact = json.loads(artifact_response["content"])
                written = json.loads(
                    tools["write_checkpoint_submission"](
                        FIXTURE_CHECKPOINT_ID,
                        json.dumps(
                            {
                                "checkpoint_id": FIXTURE_CHECKPOINT_ID,
                                "selected_action_id": operation["action_id"],
                                "observed_value": artifact["observed_value"],
                            }
                        ),
                    )
                )
                assert written["status"] == "written"
                if "submit_checkpoint" in tools:
                    submitted = json.loads(tools["submit_checkpoint"](FIXTURE_CHECKPOINT_ID))
                    assert submitted["status"] == "complete"
                if registry.private_ledger_root_to_expose is not None:
                    registry.private_ledger_root_to_expose.mkdir(mode=0o700, parents=True, exist_ok=True)
                    os.chmod(registry.private_ledger_root_to_expose, 0o755)
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="anthropic:fixture-model",
                    configuration_record={"model": "anthropic:fixture-model", "max_turns": 12},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text="Lifecycle complete.",
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=0,
                    usage_output_tokens=0,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _SealedOperationAdapter()


def _claim_and_write_bound_run_start(
    prepared: _PreparedAudit,
) -> tuple[Path, Path, LifecycleHoldoutRunStart]:
    claim = claim_lifecycle_holdout_audit(
        calibration_freeze_path=prepared.calibration_freeze_path,
        target_freeze_path=prepared.target_freeze_path,
        mount=prepared.mount,
        output_path=prepared.claim_path,
    )
    calibration = LifecycleCalibrationFreeze.model_validate_json(prepared.calibration_freeze_path.read_bytes())
    target = _read_json(prepared.target_freeze_path)
    execution_root = prepared.private_root / "execution"
    execution_root.mkdir(mode=0o700)
    run_dir = execution_root / "run"
    run_dir.mkdir(mode=0o700)
    run_start = build_lifecycle_holdout_run_start(
        claim_sha256=claim.claim_sha256,
        calibration_freeze_sha256=calibration.freeze_sha256,
        target_freeze_sha256=target["target_freeze_sha256"],
        selected_condition=calibration.selected_condition,
        private_execution_root=str(execution_root),
        run_dir=str(run_dir),
        private_ledger_root=str(prepared.private_root / "ledger"),
        python_version=platform.python_version(),
    )
    marker = json.dumps(run_start.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    run_start_path = execution_root / "run-start.json"
    run_start_path.write_text(marker, encoding="utf-8")
    (run_dir / "run-start.json").write_text(marker, encoding="utf-8")
    os.chmod(run_start_path, 0o600)
    os.chmod(run_dir / "run-start.json", 0o600)
    return run_start_path, run_dir, run_start


def _complete_run_without_claim(
    mount: SealedLifecycleMount,
    run_dir: Path,
    *,
    run_authorization_sha256: str | None = None,
    write_agent_result: bool = False,
    write_trajectory: bool = False,
) -> None:
    session_id = "unbound-preclaim.session-001"
    with mount.activate():
        prepare_evidence_checkpoint(
            mount.package_dir,
            run_dir,
            run_authorization_sha256=run_authorization_sha256,
        )
        if write_trajectory:
            trajectory_path = run_dir / "sessions" / session_id / "trajectory.jsonl"
            trajectory_path.parent.mkdir(parents=True, exist_ok=True)
            trajectory_path.write_text("", encoding="utf-8")
        open_checkpoint_attempt(
            mount.package_dir,
            run_dir,
            session_id=session_id,
            execution_mode="persistent_context",
        )
        workspace = EvidenceLifecycleWorkspaceTool(
            package_dir=mount.package_dir,
            run_dir=run_dir,
            visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        )
        control = EvidenceLifecycleControlTool(
            package_dir=mount.package_dir,
            run_dir=run_dir,
            session_id=session_id,
        )
        source_response = json.loads(workspace.read_workspace_file("hydraulics/current-source.json"))
        source = json.loads(source_response["content"])
        operation = json.loads(
            control.execute_operation(
                FIXTURE_CHECKPOINT_ID,
                FIXTURE_OPERATION_ID,
                source["visible_source_state_sha256"],
                "Derive the declared deterministic observation.",
            )
        )
        artifact_response = json.loads(workspace.read_workspace_file(operation["artifacts"][0]["path"]))
        artifact = json.loads(artifact_response["content"])
        workspace.write_checkpoint_submission(
            FIXTURE_CHECKPOINT_ID,
            json.dumps(
                {
                    "checkpoint_id": FIXTURE_CHECKPOINT_ID,
                    "selected_action_id": operation["action_id"],
                    "observed_value": artifact["observed_value"],
                }
            ),
        )
        submitted = json.loads(control.submit_checkpoint(FIXTURE_CHECKPOINT_ID))
        assert submitted["status"] == "complete"
    if write_agent_result:
        result_path = run_dir / "sessions" / session_id / "agent_result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "model": "anthropic:fixture-model",
                    "adapter": "tool_loop",
                    "adapter_name": "tool_loop",
                    "resolved_model": "anthropic:fixture-model",
                    "configuration_record": {"model": "anthropic:fixture-model", "max_turns": 12},
                    "session_id": session_id,
                    "session_mode": "persistent",
                    "memory_visibility_policy": "persistent_context",
                    "max_turns": 12,
                    "status": "completed",
                    "checkpoint_ids": [FIXTURE_CHECKPOINT_ID],
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "failure_kind": None,
                    "provider_error": None,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


def _private_record_paths(private_ledger_root: Path) -> list[Path]:
    return sorted(path for path in private_ledger_root.rglob("*.json") if "_artifacts" not in path.parts)


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload
