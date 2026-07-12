# ABOUTME: Integration-tests host-owned lifecycle operation execution and immutable projections.
# ABOUTME: Covers source binding, idempotent reuse, typed stale rejection, and action ownership.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    execute_lifecycle_operation,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
)
from aec_bench.meta_harness.evidence_lifecycle_local import EvidenceLifecycleControlTool
from aec_bench.meta_harness.evidence_lifecycle_state import EvidenceLifecycleRunState
from aec_bench.meta_harness.lifecycle_operation_store import resolve_lifecycle_operation_current_source
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import materialize_lifecycle_template

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


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
    identity = _read_json(run / "workspace" / "hydraulics" / "current-source.json")
    return package, run, str(identity["visible_source_state_sha256"])


def test_prepare_publishes_source_bound_operation_catalogue(tmp_path: Path) -> None:
    _package, run, visible_source_sha256 = _prepare(tmp_path)
    catalogue = _read_json(run / "workspace" / "checkpoints" / "baseline_analysis" / "operations.json")
    source = _read_json(run / "workspace" / "hydraulics" / "current-source.json")

    assert catalogue["checkpoint_id"] == "baseline_analysis"
    assert catalogue["operation_budget"] == 6
    assert catalogue["remaining_budget"] == 6
    assert catalogue["visible_source_state_sha256"] == visible_source_sha256
    assert source["revision_id"] == "baseline"
    assert source["visible_source_state_sha256"] == visible_source_sha256
    assert source["physical_source_state_sha256"] != ""
    assert "payload" in source["source_state"]


def test_real_hydrology_action_is_immutable_projected_and_host_owned(tmp_path: Path) -> None:
    package, run, visible_source_sha256 = _prepare(tmp_path)
    action = execute_lifecycle_operation(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=visible_source_sha256,
        reason="Establish the design-scenario hydrology baseline.",
        session_id="baseline.session-001",
    )

    assert action["action_id"] == "operation-000001"
    assert action["outcome"] == "completed"
    assert action["disposition"] == "computed"
    assert action["session_id"] == "baseline.session-001"
    assert action["attempt_id"] == "baseline_analysis.attempt-001"
    assert action["visible_source_state_before_sha256"] == visible_source_sha256
    assert action["visible_source_state_after_sha256"] == visible_source_sha256
    transaction = run / "lifecycle_operations" / "operation-000001"
    assert set(path.relative_to(transaction).as_posix() for path in transaction.rglob("*") if path.is_file()) == {
        "action.json",
        "artifacts/hydrology.json",
        "committed.json",
        "request.json",
        "result-manifest.json",
    }
    assert _read_json(transaction / "committed.json") == {
        "action_id": "operation-000001",
        "status": "committed",
    }
    projected = _read_json(
        run / "workspace" / "inbox" / "baseline_analysis" / "operations" / "operation-000001" / "hydrology.json"
    )
    assert projected["scenario_id"] == "design-10yr"
    assert set(projected["catchment_peak_flows_m3_s"]) == {"CATCH-A", "CATCH-B"}
    assert projected["peak_total_inflow_m3_s"] > 0.0
    assert "maximum_node_hgl_m" not in projected
    state = read_evidence_lifecycle_state(package, run)
    checkpoint = state["checkpoint_runs"][0]
    assert checkpoint["operation_budget_remaining"] == 5
    assert len(checkpoint["operation_actions"]) == 1


def test_identical_operation_reuses_original_artifacts_without_budget(tmp_path: Path) -> None:
    package, run, visible_source_sha256 = _prepare(tmp_path)
    first = execute_lifecycle_operation(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=visible_source_sha256,
        reason="Establish hydrology.",
        session_id="baseline.session-001",
    )
    repeated = execute_lifecycle_operation(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=visible_source_sha256,
        reason="Confirm the same declared operation.",
        session_id="baseline.session-001",
    )

    assert repeated["action_id"] == "operation-000002"
    assert repeated["outcome"] == "already_current"
    assert repeated["retained_from_action_id"] == first["action_id"]
    assert repeated["budget_consumed"] == 0
    assert repeated["artifacts"] == first["artifacts"]
    assert not (run / "lifecycle_operations" / "operation-000002" / "result-manifest.json").exists()
    state = read_evidence_lifecycle_state(package, run)
    assert state["checkpoint_runs"][0]["operation_budget_remaining"] == 5


def test_stale_source_hash_is_a_zero_cost_non_leaking_action(tmp_path: Path) -> None:
    package, run, _visible_source_sha256 = _prepare(tmp_path)
    action = execute_lifecycle_operation(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256="0" * 64,
        reason="Attempt against stale visible state.",
        session_id="baseline.session-001",
    )

    assert action["outcome"] == "rejected"
    assert action["rejection"] == "stale_visible_source"
    assert action["budget_consumed"] == 0
    assert action["artifacts"] == []
    encoded = json.dumps(action).lower()
    for forbidden in ("tailwater_revision", "hidden/", "expected", "valid operation"):
        assert forbidden not in encoded


def test_blank_operation_call_creates_no_lifecycle_action(tmp_path: Path) -> None:
    package, run, visible_source_sha256 = _prepare(tmp_path)

    with pytest.raises(EvidenceLifecycleError, match="must not be blank"):
        execute_lifecycle_operation(
            package,
            run,
            checkpoint_id="baseline_analysis",
            operation_id=" ",
            visible_source_state_sha256=visible_source_sha256,
            reason="blank operation id",
            session_id="baseline.session-001",
        )

    assert not (run / "lifecycle_operations").exists()


@pytest.mark.parametrize(
    "invalid_sha256",
    [
        "0" * 63,
        "A" * 64,
        "g" * 64,
        "not-a-hash",
    ],
)
def test_malformed_visible_source_hash_is_rejected_before_state_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_sha256: str,
) -> None:
    package, run, _visible_source_sha256 = _prepare(tmp_path)

    def fail_if_locked(_run_dir: Path) -> None:
        raise AssertionError("state lock must not be entered")

    monkeypatch.setattr(
        "aec_bench.meta_harness.evidence_lifecycle._lifecycle_state_lock",
        fail_if_locked,
    )

    with pytest.raises(EvidenceLifecycleError, match="64 lowercase hexadecimal"):
        execute_lifecycle_operation(
            package,
            run,
            checkpoint_id="baseline_analysis",
            operation_id="hydrology.design-10yr",
            visible_source_state_sha256=invalid_sha256,
            reason="Reject malformed source identity before locking.",
            session_id="baseline.session-001",
        )

    assert not (run / "lifecycle_operations").exists()


def test_control_tool_rejects_malformed_hash_without_creating_action(tmp_path: Path) -> None:
    package, run, _visible_source_sha256 = _prepare(tmp_path)
    tool = EvidenceLifecycleControlTool(
        package_dir=package,
        run_dir=run,
        session_id="baseline.session-001",
    )

    response = json.loads(
        tool.execute_operation(
            "baseline_analysis",
            "hydrology.design-10yr",
            "A" * 64,
            "Reject a malformed model-supplied source identity.",
        )
    )

    assert response == {
        "status": "rejected",
        "error": "visible source state sha256 must contain 64 lowercase hexadecimal characters",
    }
    assert not (run / "lifecycle_operations").exists()


def test_control_tool_rejects_blank_arguments_without_creating_action(tmp_path: Path) -> None:
    package, run, visible_source_sha256 = _prepare(tmp_path)
    tool = EvidenceLifecycleControlTool(
        package_dir=package,
        run_dir=run,
        session_id="baseline.session-001",
    )

    response = json.loads(
        tool.execute_operation(
            "baseline_analysis",
            " ",
            visible_source_sha256,
            "Reject a blank model-supplied operation identity.",
        )
    )

    assert response == {
        "status": "rejected",
        "error": "operation arguments must not be blank",
    }
    assert not (run / "lifecycle_operations").exists()


def test_control_tool_propagates_session_infrastructure_failure(tmp_path: Path) -> None:
    package, run, visible_source_sha256 = _prepare(tmp_path)
    tool = EvidenceLifecycleControlTool(
        package_dir=package,
        run_dir=run,
        session_id="wrong.session",
    )

    with pytest.raises(EvidenceLifecycleError, match="active attempt belongs"):
        tool.execute_operation(
            "baseline_analysis",
            "hydrology.design-10yr",
            visible_source_sha256,
            "Do not mask an invalid host session as a model rejection.",
        )

    assert not (run / "lifecycle_operations").exists()


@pytest.mark.parametrize("failure_mode", ["request_hash", "resolver", "validation"])
def test_operation_staging_is_removed_when_execution_cannot_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    package, run, visible_source_sha256 = _prepare(tmp_path)

    def fail_execution(_self: object, _plan: object, artifact_dir: Path) -> None:
        if failure_mode == "resolver":
            raise RuntimeError("resolver execution failed")
        artifact_dir.mkdir(parents=True)

    if failure_mode == "request_hash":

        def fail_request_hash(_path: Path) -> str:
            raise RuntimeError("request hashing failed")

        monkeypatch.setattr(
            "aec_bench.meta_harness.lifecycle_operation_store._sha256",
            fail_request_hash,
        )
    else:
        monkeypatch.setattr(
            "aec_bench.task_world_templates.hydraulics.operations.Ssc03HydraulicOperationResolver.execute",
            fail_execution,
        )

    expected = {
        "request_hash": "request hashing failed",
        "resolver": "resolver execution failed",
        "validation": "at least one artifact",
    }[failure_mode]
    with pytest.raises((RuntimeError, EvidenceLifecycleError), match=expected):
        execute_lifecycle_operation(
            package,
            run,
            checkpoint_id="baseline_analysis",
            operation_id="hydrology.design-10yr",
            visible_source_state_sha256=visible_source_sha256,
            reason="Exercise staging cleanup.",
            session_id="baseline.session-001",
        )

    root = run / "lifecycle_operations"
    assert root.is_dir()
    assert list(root.iterdir()) == []


def test_execute_rejects_symlinked_transaction_root_before_outside_write(tmp_path: Path) -> None:
    package, run, visible_source_sha256 = _prepare(tmp_path)
    outside = tmp_path / "outside-transactions"
    outside.mkdir()
    (run / "lifecycle_operations").symlink_to(outside, target_is_directory=True)

    with pytest.raises(EvidenceLifecycleError, match="symlink"):
        execute_lifecycle_operation(
            package,
            run,
            checkpoint_id="baseline_analysis",
            operation_id="hydrology.design-10yr",
            visible_source_state_sha256=visible_source_sha256,
            reason="Reject a symlinked transaction root.",
            session_id="baseline.session-001",
        )

    assert list(outside.iterdir()) == []


def test_execute_rejects_symlinked_workspace_projection_ancestor(tmp_path: Path) -> None:
    package, run, visible_source_sha256 = _prepare(tmp_path)
    outside = tmp_path / "outside-workspace"
    outside.mkdir()
    operations = run / "workspace" / "inbox" / "baseline_analysis" / "operations"
    operations.symlink_to(outside, target_is_directory=True)

    with pytest.raises(EvidenceLifecycleError, match="symlink"):
        execute_lifecycle_operation(
            package,
            run,
            checkpoint_id="baseline_analysis",
            operation_id="hydrology.design-10yr",
            visible_source_state_sha256=visible_source_sha256,
            reason="Reject a symlinked workspace projection ancestor.",
            session_id="baseline.session-001",
        )

    assert list(outside.iterdir()) == []


def test_read_only_current_source_resolver_matches_published_projection(tmp_path: Path) -> None:
    package, run, _visible_source_sha256 = _prepare(tmp_path)
    state = EvidenceLifecycleRunState.model_validate(_read_json(run / "state.json"))
    before = _read_json(run / "workspace" / "hydraulics" / "current-source.json")

    source = resolve_lifecycle_operation_current_source(package, run, state)

    assert source.visible_source_state_sha256 == before["visible_source_state_sha256"]
    assert source.physical_source_state_sha256 == before["physical_source_state_sha256"]
    assert _read_json(run / "workspace" / "hydraulics" / "current-source.json") == before
