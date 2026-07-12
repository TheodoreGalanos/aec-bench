# ABOUTME: Integration-tests crash recovery for durable lifecycle-operation transactions.
# ABOUTME: Covers orphan adoption, commit-marker repair, ledger repair, and tamper rejection.

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.meta_harness import lifecycle_operation_store
from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    execute_lifecycle_operation,
    load_evidence_lifecycle_spec,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
)
from aec_bench.meta_harness.evidence_lifecycle_state import (
    EvidenceLifecycleRunState,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
)
from aec_bench.meta_harness.ledger import read_ledger
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import materialize_lifecycle_template

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def _read_json(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _rewrite_action(
    run: Path,
    mutate: Callable[[dict[str, Any]], None],
    *,
    action_id: str = "operation-000001",
) -> dict[str, Any]:
    state = cast(dict[str, Any], _read_json(run / "state.json"))
    action = cast(
        dict[str, Any],
        next(
            item
            for checkpoint in state["checkpoint_runs"]
            for item in checkpoint["operation_actions"]
            if item["action_id"] == action_id
        ),
    )
    mutate(action)
    _write_json(run / "state.json", cast(dict[str, object], state))
    _write_json(
        run / "lifecycle_operations" / action_id / "action.json",
        cast(dict[str, object], action),
    )
    return action


def _prepare(tmp_path: Path) -> tuple[Path, Path, str]:
    package = materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id="tailwater_revision",
    )
    run = tmp_path / "run"
    prepare_evidence_checkpoint(package, run)
    open_checkpoint_attempt(
        package,
        run,
        session_id="baseline.session-001",
        execution_mode="persistent_context",
    )
    source = _read_json(run / "workspace" / "hydraulics" / "current-source.json")
    return package, run, str(source["visible_source_state_sha256"])


def _execute(package: Path, run: Path, source_sha256: str) -> dict[str, object]:
    return execute_lifecycle_operation(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=source_sha256,
        reason="Exercise the durable recovery boundary.",
        session_id="baseline.session-001",
    )


def _crash_after_transaction_publish(
    monkeypatch: pytest.MonkeyPatch,
    package: Path,
    run: Path,
    source_sha256: str,
) -> Path:
    def fail_state_commit(_run_dir: Path, _state: object) -> None:
        raise RuntimeError("simulated state commit failure")

    with monkeypatch.context() as patcher:
        patcher.setattr(
            "aec_bench.meta_harness.lifecycle_operation_store._write_state",
            fail_state_commit,
        )
        with pytest.raises(RuntimeError, match="simulated state commit failure"):
            _execute(package, run, source_sha256)
    transaction = run / "lifecycle_operations" / "operation-000001"
    assert (transaction / "action.json").is_file()
    assert not (transaction / "committed.json").exists()
    assert _read_json(run / "state.json")["checkpoint_runs"][0]["operation_actions"] == []  # type: ignore[index]
    return transaction


def test_recovery_adopts_transaction_published_before_lifecycle_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    transaction = _crash_after_transaction_publish(monkeypatch, package, run, source_sha256)

    recovered = read_evidence_lifecycle_state(package, run)

    checkpoint = recovered["checkpoint_runs"][0]
    assert checkpoint["operation_budget_remaining"] == 5
    assert [action["action_id"] for action in checkpoint["operation_actions"]] == ["operation-000001"]
    assert _read_json(transaction / "committed.json") == {
        "action_id": "operation-000001",
        "status": "committed",
    }
    entries = read_ledger(run / "lifecycle_ledger.jsonl")
    assert [entry["summary"]["action_id"] for entry in entries if entry["stage"] == "lifecycle_operation"] == [
        "operation-000001"
    ]
    assert (
        sum(entry["stage"] == "lifecycle_transition" and entry["summary"]["kind"] == "operation" for entry in entries)
        == 1
    )


def test_recovery_repairs_missing_commit_marker_and_operation_ledger(tmp_path: Path) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    _execute(package, run, source_sha256)
    transaction = run / "lifecycle_operations" / "operation-000001"
    (transaction / "committed.json").unlink()
    ledger = run / "lifecycle_ledger.jsonl"
    retained = [entry for entry in read_ledger(ledger) if entry["stage"] != "lifecycle_operation"]
    ledger.write_text("".join(json.dumps(entry, sort_keys=True) + "\n" for entry in retained), encoding="utf-8")

    recovered = read_evidence_lifecycle_state(package, run)

    assert recovered["checkpoint_runs"][0]["operation_budget_remaining"] == 5
    assert _read_json(transaction / "committed.json")["status"] == "committed"
    assert sum(entry["stage"] == "lifecycle_operation" for entry in read_ledger(ledger)) == 1


def test_recovery_rejects_orphan_with_invalid_pre_action_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    transaction = _crash_after_transaction_publish(monkeypatch, package, run, source_sha256)
    action = _read_json(transaction / "action.json")
    action["pre_action_state_sha256"] = "0" * 64
    _write_json(transaction / "action.json", action)

    with pytest.raises(EvidenceLifecycleError, match="operation recovery pre-state hash does not match"):
        read_evidence_lifecycle_state(package, run)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("operation_kind", "run_network_hgl", "kind does not match"),
        ("disposition", "activated", "disposition does not match"),
    ],
)
def test_recovery_replays_public_operation_kind_and_disposition(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    _execute(package, run, source_sha256)
    _rewrite_action(run, lambda action: action.__setitem__(field, value))

    with pytest.raises(EvidenceLifecycleError, match=message):
        read_evidence_lifecycle_state(package, run)


def test_recovery_replays_exact_typed_rejection_reason(tmp_path: Path) -> None:
    package, run, _source_sha256 = _prepare(tmp_path)
    execute_lifecycle_operation(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256="0" * 64,
        reason="Record a real stale-source rejection.",
        session_id="baseline.session-001",
    )
    _rewrite_action(
        run,
        lambda action: action.__setitem__("rejection", "prerequisites_incomplete"),
    )

    with pytest.raises(EvidenceLifecycleError, match="rejection reason does not match"):
        read_evidence_lifecycle_state(package, run)


def test_recovery_requires_every_action_to_have_its_declared_owner_attempt(tmp_path: Path) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    _execute(package, run, source_sha256)

    def remove_owner(action: dict[str, Any]) -> None:
        action["attempt_id"] = "baseline_analysis.attempt-999"
        action["session_id"] = "missing.session"

    _rewrite_action(run, remove_owner)

    with pytest.raises(EvidenceLifecycleError, match="attempt owner|owner attempt"):
        read_evidence_lifecycle_state(package, run)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda action: action.model_copy(update={"operation_id": "hydrology.unknown"}), "public catalogue"),
        (lambda action: action.model_copy(update={"operation_kind": "run_network_hgl"}), "kind does not match"),
        (
            lambda action: action.model_copy(update={"disposition": LifecycleOperationDisposition.ACTIVATED}),
            "disposition does not match",
        ),
        (
            lambda action: action.model_copy(update={"input_projection_sha256": "f" * 64}),
            "input projection does not match",
        ),
        (
            lambda action: action.model_copy(update={"prerequisite_action_ids": ("operation-000000",)}),
            "prerequisites do not match",
        ),
        (
            lambda action: action.model_copy(
                update={
                    "outcome": LifecycleOperationOutcome.ALREADY_CURRENT,
                    "disposition": LifecycleOperationDisposition.REUSED,
                }
            ),
            "currentness does not match",
        ),
    ],
)
def test_replay_helper_enforces_public_resolver_semantics(
    tmp_path: Path,
    mutate: Callable[[Any], Any],
    message: str,
) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    _execute(package, run, source_sha256)
    state = EvidenceLifecycleRunState.model_validate(_read_json(run / "state.json"))
    action = mutate(state.checkpoint_runs[0].operation_actions[0])
    resolver = lifecycle_operation_store._resolver_for_package(package, run)

    with pytest.raises(EvidenceLifecycleError, match=message):
        lifecycle_operation_store._validate_operation_replay(
            load_evidence_lifecycle_spec(package),
            resolver,
            action,
            [],
            budget_before=6,
            supplied_source_sha256=source_sha256,
        )


def test_recovery_rejects_symlinked_transaction_root(tmp_path: Path) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    _execute(package, run, source_sha256)
    root = run / "lifecycle_operations"
    outside = tmp_path / "outside-root"
    root.replace(outside)
    root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(EvidenceLifecycleError, match="symlink"):
        read_evidence_lifecycle_state(package, run)


def test_recovery_rejects_symlinked_transaction_directory(tmp_path: Path) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    _execute(package, run, source_sha256)
    transaction = run / "lifecycle_operations" / "operation-000001"
    outside = tmp_path / "outside-transaction"
    transaction.replace(outside)
    transaction.symlink_to(outside, target_is_directory=True)

    with pytest.raises(EvidenceLifecycleError, match="symlink"):
        read_evidence_lifecycle_state(package, run)


@pytest.mark.parametrize(
    "relative_path",
    [
        "request.json",
        "result-manifest.json",
        "action.json",
        "committed.json",
    ],
)
def test_recovery_rejects_symlinked_transaction_metadata(
    tmp_path: Path,
    relative_path: str,
) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    _execute(package, run, source_sha256)
    metadata = run / "lifecycle_operations" / "operation-000001" / relative_path
    outside = tmp_path / f"outside-{relative_path}"
    outside.write_bytes(metadata.read_bytes())
    metadata.unlink()
    metadata.symlink_to(outside)

    with pytest.raises(EvidenceLifecycleError, match="symlink"):
        read_evidence_lifecycle_state(package, run)


def test_recovery_rejects_symlinked_artifact_ancestor(tmp_path: Path) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    _execute(package, run, source_sha256)
    artifacts = run / "lifecycle_operations" / "operation-000001" / "artifacts"
    outside = tmp_path / "outside-artifacts"
    artifacts.replace(outside)
    artifacts.symlink_to(outside, target_is_directory=True)

    with pytest.raises(EvidenceLifecycleError, match="symlink"):
        read_evidence_lifecycle_state(package, run)


def test_recovery_rejects_symlinked_workspace_projection_ancestor(tmp_path: Path) -> None:
    package, run, source_sha256 = _prepare(tmp_path)
    _execute(package, run, source_sha256)
    operations = run / "workspace" / "inbox" / "baseline_analysis" / "operations"
    outside = tmp_path / "outside-projection"
    shutil.move(operations, outside)
    operations.symlink_to(outside, target_is_directory=True)

    with pytest.raises(EvidenceLifecycleError, match="symlink"):
        read_evidence_lifecycle_state(package, run)
