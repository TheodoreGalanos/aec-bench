# ABOUTME: Integration-tests lifecycle branches that inherit durable operation histories.
# ABOUTME: Proves v5 budgets, transactions, source state, and parent-history binding survive branching.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    branch_evidence_lifecycle,
    execute_lifecycle_operation,
    load_evidence_lifecycle_spec,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    submit_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_lifecycle_state import EvidenceLifecycleRunState
from aec_bench.meta_harness.lifecycle_operation_snapshot import validate_lifecycle_operation_snapshot
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import materialize_lifecycle_template

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def _read_json(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _materialize(tmp_path: Path) -> tuple[Path, Path]:
    package = materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id="tailwater_revision",
    )
    return package, tmp_path / "parent"


def _open(package: Path, run: Path, session_id: str) -> None:
    prepare_evidence_checkpoint(package, run)
    open_checkpoint_attempt(
        package,
        run,
        session_id=session_id,
        execution_mode="persistent_context",
    )


def _execute(package: Path, run: Path, operation_id: str, session_id: str) -> dict[str, object]:
    source = _read_json(run / "workspace" / "hydraulics" / "current-source.json")
    return execute_lifecycle_operation(
        package,
        run,
        checkpoint_id=str(_read_json(run / "state.json")["active_checkpoint_id"]),
        operation_id=operation_id,
        visible_source_state_sha256=str(source["visible_source_state_sha256"]),
        reason=f"Execute {operation_id} for branch-history coverage.",
        session_id=session_id,
    )


def _submit_active(package: Path, run: Path) -> None:
    state = _read_json(run / "state.json")
    checkpoint_id = str(state["active_checkpoint_id"])
    checkpoint = next(
        item for item in load_evidence_lifecycle_spec(package).checkpoints if item.checkpoint_id == checkpoint_id
    )
    payload: dict[str, object] = {field: [] for field in checkpoint.required_submission_fields}
    payload["checkpoint_id"] = checkpoint_id
    _write_json(run / "workspace" / checkpoint.submission_path, payload)
    submit_evidence_checkpoint(package, run)


def _parent_through_revision(tmp_path: Path) -> tuple[Path, Path]:
    package, parent = _materialize(tmp_path)
    _open(package, parent, "baseline.session-001")
    _execute(package, parent, "hydrology.design-10yr", "baseline.session-001")
    _submit_active(package, parent)
    _open(package, parent, "revision.session-001")
    _execute(package, parent, "source-revision.current", "revision.session-001")
    _submit_active(package, parent)
    return package, parent


def test_branch_preserves_v5_operation_budgets_actions_transactions_and_source(tmp_path: Path) -> None:
    package, parent = _parent_through_revision(tmp_path)
    branch_run = tmp_path / "branch"
    parent_source = _read_json(parent / "workspace" / "hydraulics" / "current-source.json")

    branch = branch_evidence_lifecycle(
        package,
        parent,
        branch_run,
        checkpoint_id="revision_analysis",
        branch_id="branch.recheck-revision",
        reason="Reconsider the revision without discarding durable operation evidence.",
    )

    state = _read_json(branch_run / "state.json")
    assert state["schema_version"] == "5"
    baseline, revision, closeout = branch["checkpoint_runs"]
    assert (baseline["operation_budget"], baseline["operation_budget_remaining"]) == (6, 5)
    assert (revision["operation_budget"], revision["operation_budget_remaining"]) == (7, 6)
    assert (closeout["operation_budget"], closeout["operation_budget_remaining"]) == (0, 0)
    assert [baseline["operation_actions"][0]["action_id"], revision["operation_actions"][0]["action_id"]] == [
        "operation-000001",
        "operation-000002",
    ]
    assert baseline["operation_actions"][0]["inherited_from_parent"] is True
    assert revision["operation_actions"][0]["inherited_from_parent"] is True
    assert (
        _read_json(branch_run / "lifecycle_operations" / "operation-000001" / "action.json")
        == baseline["operation_actions"][0]
    )
    assert (
        _read_json(branch_run / "lifecycle_operations" / "operation-000002" / "action.json")
        == revision["operation_actions"][0]
    )
    assert _read_json(branch_run / "workspace" / "hydraulics" / "current-source.json") == parent_source
    assert _read_json(branch_run / "workspace/checkpoints/baseline_analysis/operations.json") == _read_json(
        parent / "workspace/checkpoints/baseline_analysis/operations.json"
    )
    validate_lifecycle_operation_snapshot(
        branch_run,
        EvidenceLifecycleRunState.model_validate(state),
        load_evidence_lifecycle_spec(package),
    )

    open_checkpoint_attempt(
        package,
        branch_run,
        session_id="branch.session-001",
        execution_mode="persistent_context",
    )
    continued = _execute(package, branch_run, "hydrology.design-10yr", "branch.session-001")
    assert continued["action_id"] == "operation-000003"
    assert continued["budget_before"] == 6


def test_branch_rejects_tampered_historical_operation_catalogue(tmp_path: Path) -> None:
    package, parent = _parent_through_revision(tmp_path)
    parent_catalogue_path = parent / "workspace/checkpoints/baseline_analysis/operations.json"
    parent_catalogue = _read_json(parent_catalogue_path)
    operations = parent_catalogue["operations"]
    assert isinstance(operations, list)
    operations[0]["kind"] = "forged_kind"
    _write_json(parent_catalogue_path, parent_catalogue)
    branch_run = tmp_path / "branch"

    with pytest.raises(ValueError, match="operation catalogue does not match"):
        branch_evidence_lifecycle(
            package,
            parent,
            branch_run,
            checkpoint_id="revision_analysis",
            branch_id="branch.catalogue-integrity",
            reason="Reject a branch whose inherited public catalogue was changed.",
        )

    assert not branch_run.exists()


def test_branch_origin_hash_binds_inherited_operation_history(tmp_path: Path) -> None:
    package, parent = _parent_through_revision(tmp_path)
    branch_run = tmp_path / "branch"
    branch_evidence_lifecycle(
        package,
        parent,
        branch_run,
        checkpoint_id="revision_analysis",
        branch_id="branch.operation-history",
        reason="Bind every inherited action in the branch origin.",
    )
    state = _read_json(branch_run / "state.json")
    checkpoint_runs = state["checkpoint_runs"]
    assert isinstance(checkpoint_runs, list)
    action = checkpoint_runs[0]["operation_actions"][0]
    action["reason"] = "Tampered inherited reason."
    request_path = branch_run / "lifecycle_operations" / "operation-000001" / "request.json"
    request = _read_json(request_path)
    request["reason"] = action["reason"]
    _write_json(request_path, request)
    action["request_sha256"] = hashlib.sha256(request_path.read_bytes()).hexdigest()
    _write_json(branch_run / "state.json", state)
    _write_json(branch_run / "lifecycle_operations" / "operation-000001" / "action.json", action)
    ledger_path = branch_run / "lifecycle_ledger.jsonl"
    ledger_entries = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    operation_entry = next(
        entry
        for entry in ledger_entries
        if entry["stage"] == "lifecycle_operation" and entry["summary"]["action_id"] == "operation-000001"
    )
    operation_entry["summary"] = action
    ledger_path.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in ledger_entries),
        encoding="utf-8",
    )

    with pytest.raises(EvidenceLifecycleError, match="branch origin action state changed"):
        _submit_active(package, branch_run)
