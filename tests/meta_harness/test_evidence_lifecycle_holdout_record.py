# ABOUTME: Tests private immutable TrialRecords for one completed sealed holdout lifecycle.
# ABOUTME: Proves exact authority binding, full snapshots, tamper detection, and safe idempotence.

from __future__ import annotations

import json
import os
import platform
import stat
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, cast

import pytest

from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import Completeness, TrialRecord
from aec_bench.meta_harness.evidence_lifecycle_holdout_record import (
    finalize_lifecycle_holdout_trial_record,
    validate_lifecycle_holdout_trial_record,
)
from aec_bench.meta_harness.evidence_lifecycle_session_records import (
    parse_lifecycle_session_records,
)
from aec_bench.meta_harness.evidence_lifecycle_trial_record import (
    finalize_lifecycle_trial_record,
)
from tests.support.sealed_lifecycle_audit import (
    CompletedSealedLifecycleAudit,
    build_completed_sealed_lifecycle_audit,
)


def test_finalizer_snapshots_complete_private_holdout_record_with_exact_authority(
    tmp_path: Path,
) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root

    record_path = _finalize(audit, private_ledger_root=ledger_root)
    record = TrialRecord.model_validate_json(record_path.read_bytes())

    assert record.completeness is Completeness.COMPLETE
    assert record.task.visibility is Visibility.HOLDOUT
    assert record.agent.model == audit.selected_condition.resolved_model
    assert record.agent.adapter == audit.selected_condition.resolved_adapter
    assert record.evaluation.reward == audit.verified_result["reward"]
    assert record.evaluation.validity.model_dump(mode="json") == {
        "output_parseable": True,
        "schema_valid": True,
        "verifier_completed": True,
        "errors": [],
    }
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.execution_mode == audit.selected_condition.execution_mode.value
    assert (
        record.lifecycle_execution.memory_visibility_policy == audit.selected_condition.memory_visibility_policy.value
    )
    assert record.lifecycle_execution.max_turns_per_session == audit.selected_condition.max_turns_per_session
    assert record.lifecycle_execution.status == "completed"
    assert [session.session_id for session in record.lifecycle_execution.sessions] == [
        audit.agent_evidence["sessions"][0]["session_id"]
    ]
    assert record.lifecycle_provenance is not None
    assert record.lifecycle_provenance.repository_kind == "git"
    assert record.lifecycle_provenance.repository_dirty is False
    target = _read_json(audit.target_freeze_path)
    assert record.task.task_id == target["lifecycle_id"]
    assert record.lifecycle_provenance.lifecycle_id == target["lifecycle_id"]
    assert record.lifecycle_provenance.world_id == target["world_id"]
    assert record.lifecycle_provenance.spec_sha256 == target["lifecycle_spec_sha256"]
    assert record.lifecycle_provenance.package_sha256 == target["package_sha256"]

    artifacts = record.outputs.artifacts
    assert artifacts
    artifact_root = ledger_root / record.experiment_id / "_artifacts" / record.trial_id
    assert _file_inventory(artifact_root / "package") == _file_inventory(audit.mount.package_dir)
    assert _file_inventory(artifact_root / "run") == _file_inventory(audit.run_dir)
    assert _file_inventory(artifact_root / "authority") == {
        "audit-manifest.json",
        "calibration-freeze.json",
        "claim.json",
        "target-freeze.json",
    }
    expected_artifact_paths = {
        path.relative_to(ledger_root).as_posix() for path in artifact_root.rglob("*") if path.is_file()
    }
    assert {artifact.path for artifact in artifacts} == expected_artifact_paths
    for artifact in artifacts:
        relative = Path(artifact.path)
        assert not relative.is_absolute()
        assert ".." not in relative.parts
        path = ledger_root / relative
        assert path.is_file()
        assert not path.is_symlink()
    for path in [ledger_root, *ledger_root.rglob("*")]:
        assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0

    assert (
        validate_lifecycle_holdout_trial_record(
            record_path=record_path,
            private_ledger_root=ledger_root,
            mount=audit.mount,
        )
        == record
    )


def test_finalizer_rejects_any_selected_condition_drift_before_writing(tmp_path: Path) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root
    different = audit.selected_condition.model_copy(update={"resolved_model": "different-model"})

    with pytest.raises(ValueError, match="selected condition|frozen public condition"):
        finalize_lifecycle_holdout_trial_record(
            run_dir=audit.run_dir,
            run_start_path=audit.run_start_path,
            calibration_freeze_path=audit.calibration_freeze_path,
            target_freeze_path=audit.target_freeze_path,
            claim_path=audit.claim_path,
            mount=audit.mount,
            selected_condition=different,
            private_ledger_root=ledger_root,
            repository_dir=audit.repository_dir,
            agent_evidence=audit.agent_evidence,
            verified_result=audit.verified_result,
        )

    assert not ledger_root.exists()


@pytest.mark.parametrize("tamper", ["configuration", "tokens", "missing_result"])
def test_finalizer_derives_session_provenance_from_on_disk_results(
    tmp_path: Path,
    tamper: str,
) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root
    evidence = deepcopy(audit.agent_evidence)
    if tamper == "configuration":
        evidence["sessions"][0]["configuration_record"] = {"fabricated": "not-on-disk"}
    elif tamper == "tokens":
        evidence["sessions"][0]["input_tokens"] = 123456
        evidence["totals"]["input_tokens"] = 123456
    else:
        for result_path in audit.run_dir.rglob("agent_result.json"):
            result_path.unlink()

    with pytest.raises(ValueError, match="session|artifact|canonical|configuration|token"):
        finalize_lifecycle_holdout_trial_record(
            run_dir=audit.run_dir,
            run_start_path=audit.run_start_path,
            calibration_freeze_path=audit.calibration_freeze_path,
            target_freeze_path=audit.target_freeze_path,
            claim_path=audit.claim_path,
            mount=audit.mount,
            selected_condition=audit.selected_condition,
            private_ledger_root=ledger_root,
            repository_dir=audit.repository_dir,
            agent_evidence=evidence,
            verified_result=audit.verified_result,
        )

    assert not ledger_root.exists()


def test_finalizer_rejects_clean_checkout_that_is_not_the_executing_source(
    tmp_path: Path,
) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root
    source_file = audit.repository_dir / "aec_bench" / "__init__.py"
    source_file.write_text(
        source_file.read_text(encoding="utf-8") + "\nUNRELATED_CHECKOUT_MARKER = True\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "aec_bench/__init__.py"], cwd=audit.repository_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Diverge source fixture"],
        cwd=audit.repository_dir,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Lifecycle Test",
            "GIT_AUTHOR_EMAIL": "lifecycle@example.invalid",
            "GIT_COMMITTER_NAME": "Lifecycle Test",
            "GIT_COMMITTER_EMAIL": "lifecycle@example.invalid",
        },
    )
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=audit.repository_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""

    with pytest.raises(ValueError, match="executing|inventory|repository|source"):
        _finalize(audit, private_ledger_root=ledger_root)

    assert not ledger_root.exists()


@pytest.mark.parametrize(
    ("execution_mode", "session_mode", "memory_visibility_policy"),
    [
        ("persistent_context", "persistent", "persistent_context"),
        ("fresh_context", "fresh", "artifact_memory"),
    ],
)
def test_session_parser_rejects_nested_noncanonical_agent_result_path(
    tmp_path: Path,
    execution_mode: Literal["persistent_context", "fresh_context"],
    session_mode: Literal["persistent", "fresh"],
    memory_visibility_policy: Literal[
        "persistent_context",
        "artifact_memory",
        "raw_evidence_only",
        "current_release_only",
    ],
) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    state = _read_json(audit.run_dir / "state.json")
    evidence = audit.agent_evidence
    session_id = str(evidence["sessions"][0]["session_id"])
    checkpoint_id = str(state["checkpoint_runs"][0]["checkpoint_id"])
    source = next(audit.run_dir.rglob("agent_result.json"))
    if execution_mode == "persistent_context":
        destination = audit.run_dir / "sessions" / session_id / "nested" / "agent_result.json"
    else:
        destination = audit.run_dir / "episodes" / checkpoint_id / session_id / "nested" / "agent_result.json"
        state["checkpoint_runs"][0]["attempts"][0]["execution_mode"] = execution_mode
    payload = _read_json(source)
    payload["session_mode"] = session_mode
    payload["memory_visibility_policy"] = memory_visibility_policy
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source.unlink()
    declared_run_artifacts = {
        path.relative_to(audit.run_dir).as_posix(): "0" * 64 for path in audit.run_dir.rglob("*") if path.is_file()
    }

    with pytest.raises(ValueError, match="canonical|path"):
        parse_lifecycle_session_records(
            run_dir=audit.run_dir,
            artifact_references=[],
            state=state,
            declared_run_artifacts=declared_run_artifacts,
            requested_model=str(evidence["model"]),
            requested_adapter=str(evidence["adapter"]),
            execution_mode=execution_mode,
            memory_visibility_policy=memory_visibility_policy,
            max_turns_per_session=int(evidence["max_turns_per_session"]),
            execution_status="completed",
            verification=audit.verified_result,
        )


def test_validator_detects_tampering_of_every_snapshotted_artifact(tmp_path: Path) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root
    record_path = _finalize(audit, private_ledger_root=ledger_root)
    record = TrialRecord.model_validate_json(record_path.read_bytes())
    assert record.outputs.artifacts

    for artifact in record.outputs.artifacts:
        path = ledger_root / artifact.path
        original = path.read_bytes()
        path.write_bytes(original + b"\ntampered")
        try:
            with pytest.raises(ValueError, match="artifact|hash|snapshot|tamper"):
                validate_lifecycle_holdout_trial_record(
                    record_path=record_path,
                    private_ledger_root=ledger_root,
                    mount=audit.mount,
                )
        finally:
            path.write_bytes(original)

    assert (
        validate_lifecycle_holdout_trial_record(
            record_path=record_path,
            private_ledger_root=ledger_root,
            mount=audit.mount,
        )
        == record
    )


@pytest.mark.parametrize("relative", ["run/undeclared-empty", "authority/undeclared-empty"])
def test_validator_rejects_empty_directory_snapshot_tampering(
    tmp_path: Path,
    relative: str,
) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root
    record_path = _finalize(audit, private_ledger_root=ledger_root)
    record = TrialRecord.model_validate_json(record_path.read_bytes())
    tampered = ledger_root / record.experiment_id / "_artifacts" / record.trial_id / relative
    tampered.mkdir(mode=0o700)

    with pytest.raises(ValueError, match="inventory|snapshot|tamper|tree"):
        validate_lifecycle_holdout_trial_record(
            record_path=record_path,
            private_ledger_root=ledger_root,
            mount=audit.mount,
        )


def test_validator_uses_captured_python_version_and_requires_canonical_record_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root
    record_path = _finalize(audit, private_ledger_root=ledger_root)
    expected = TrialRecord.model_validate_json(record_path.read_bytes())
    monkeypatch.setattr(platform, "python_version", lambda: "different-validator-python")

    assert (
        validate_lifecycle_holdout_trial_record(
            record_path=record_path,
            private_ledger_root=ledger_root,
            mount=audit.mount,
        )
        == expected
    )

    copied_path = ledger_root / "copied-record.json"
    copied_path.write_bytes(record_path.read_bytes())
    os.chmod(copied_path, 0o600)
    with pytest.raises(ValueError, match="canonical"):
        validate_lifecycle_holdout_trial_record(
            record_path=copied_path,
            private_ledger_root=ledger_root,
            mount=audit.mount,
        )


@pytest.mark.parametrize("escape_kind", ["run_symlink", "ledger_symlink"])
def test_finalizer_rejects_symlinks_and_private_ledger_root_escape(
    tmp_path: Path,
    escape_kind: str,
) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root
    outside = tmp_path / "outside"
    outside.mkdir()
    if escape_kind == "run_symlink":
        secret = outside / "secret.txt"
        secret.write_text("must not cross the snapshot root", encoding="utf-8")
        (audit.run_dir / "escaped.txt").symlink_to(secret)
    else:
        os.chmod(outside, 0o700)
        ledger_root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink|canonical|root|escape"):
        _finalize(audit, private_ledger_root=ledger_root)

    if escape_kind == "ledger_symlink":
        assert not any(path.is_file() for path in outside.rglob("*"))


def test_finalizer_rejects_lock_symlink_without_touching_external_file(tmp_path: Path) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root
    ledger_root.mkdir(mode=0o700)
    calibration = _read_json(audit.calibration_freeze_path)
    claim = _read_json(audit.claim_path)
    lock_path = ledger_root / (f".sealed-holdout-{calibration['freeze_sha256']}.holdout-{claim['claim_sha256']}.lock")
    outside = tmp_path / "outside-lock.txt"
    outside.write_text("outside bytes\n", encoding="utf-8")
    os.chmod(outside, 0o644)
    before_mode = stat.S_IMODE(outside.stat().st_mode)
    lock_path.symlink_to(outside)

    with pytest.raises(ValueError, match="lock|symlink"):
        _finalize(audit, private_ledger_root=ledger_root)

    assert outside.read_text(encoding="utf-8") == "outside bytes\n"
    assert stat.S_IMODE(outside.stat().st_mode) == before_mode


def test_public_finalizer_remains_forbidden_for_sealed_holdout_package(tmp_path: Path) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    public_ledger = tmp_path / "public-ledger"
    manifest = cast(
        Any,
        SimpleNamespace(ledger_root=str(public_ledger), experiment_id="forbidden-holdout"),
    )
    trial = cast(
        Any,
        SimpleNamespace(
            ledger_path=str(public_ledger / "forbidden-holdout.json"),
            trial_id="forbidden-holdout",
        ),
    )

    with pytest.raises(ValueError, match="^sealed_holdout_public_record_forbidden$"):
        finalize_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=audit.mount.package_dir,
            run_dir=audit.run_dir,
        )

    assert not public_ledger.exists()


def test_identical_finalization_is_idempotent_and_different_evidence_conflicts(
    tmp_path: Path,
) -> None:
    audit = build_completed_sealed_lifecycle_audit(tmp_path)
    ledger_root = audit.private_ledger_root
    first = _finalize(audit, private_ledger_root=ledger_root)
    record_bytes = first.read_bytes()
    snapshot_bytes = {
        path.relative_to(ledger_root).as_posix(): path.read_bytes() for path in ledger_root.rglob("*") if path.is_file()
    }

    second = _finalize(audit, private_ledger_root=ledger_root)

    assert second == first
    assert second.read_bytes() == record_bytes
    assert {
        path.relative_to(ledger_root).as_posix(): path.read_bytes() for path in ledger_root.rglob("*") if path.is_file()
    } == snapshot_bytes

    conflicting_evidence = dict(audit.agent_evidence)
    conflicting_evidence["sessions"] = [{**session, "input_tokens": 1} for session in audit.agent_evidence["sessions"]]
    conflicting_evidence["totals"] = {**audit.agent_evidence["totals"], "input_tokens": 1}
    with pytest.raises(ValueError, match="conflict|different content|already finalized|canonical on-disk"):
        finalize_lifecycle_holdout_trial_record(
            run_dir=audit.run_dir,
            run_start_path=audit.run_start_path,
            calibration_freeze_path=audit.calibration_freeze_path,
            target_freeze_path=audit.target_freeze_path,
            claim_path=audit.claim_path,
            mount=audit.mount,
            selected_condition=audit.selected_condition,
            private_ledger_root=ledger_root,
            repository_dir=audit.repository_dir,
            agent_evidence=conflicting_evidence,
            verified_result=audit.verified_result,
        )
    assert first.read_bytes() == record_bytes
    assert {
        path.relative_to(ledger_root).as_posix(): path.read_bytes() for path in ledger_root.rglob("*") if path.is_file()
    } == snapshot_bytes


def _finalize(
    audit: CompletedSealedLifecycleAudit,
    *,
    private_ledger_root: Path,
) -> Path:
    return finalize_lifecycle_holdout_trial_record(
        run_dir=audit.run_dir,
        run_start_path=audit.run_start_path,
        calibration_freeze_path=audit.calibration_freeze_path,
        target_freeze_path=audit.target_freeze_path,
        claim_path=audit.claim_path,
        mount=audit.mount,
        selected_condition=audit.selected_condition,
        private_ledger_root=private_ledger_root,
        repository_dir=audit.repository_dir,
        agent_evidence=audit.agent_evidence,
        verified_result=audit.verified_result,
    )


def _file_inventory(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload
