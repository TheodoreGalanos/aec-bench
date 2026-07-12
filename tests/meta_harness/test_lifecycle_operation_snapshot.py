# ABOUTME: Tests generic replay and source binding for immutable lifecycle-operation snapshots.
# ABOUTME: Covers cumulative catalogues, typed rejections, state hashes, and expected source identity.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.meta_harness.evidence_lifecycle import (
    execute_lifecycle_operation,
    load_evidence_lifecycle_spec,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    submit_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import LifecycleOperationCurrentSource
from aec_bench.meta_harness.evidence_lifecycle_state import EvidenceLifecycleRunState
from aec_bench.meta_harness.evidence_request_protocol import EvidenceLifecycleError
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_source_identity,
    validate_lifecycle_operation_run_state,
)
from aec_bench.meta_harness.lifecycle_operation_snapshot import validate_lifecycle_operation_snapshot
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.contracts import EvidenceLifecycleSpec
from aec_bench.task_world_templates.lifecycles import materialize_lifecycle_template

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _materialize(tmp_path: Path, *, variant_id: str = "administrative_no_op") -> tuple[Path, Path]:
    package = materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id=variant_id,
    )
    return package, tmp_path / "run"


def _open(package: Path, run_dir: Path, session_id: str) -> None:
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id=session_id,
        execution_mode="persistent_context",
    )


def _execute(package: Path, run_dir: Path, operation_id: str, session_id: str) -> dict[str, Any]:
    source = _read_json(run_dir / "workspace" / "hydraulics" / "current-source.json")
    state = _read_json(run_dir / "state.json")
    return execute_lifecycle_operation(
        package,
        run_dir,
        checkpoint_id=str(state["active_checkpoint_id"]),
        operation_id=operation_id,
        visible_source_state_sha256=str(source["visible_source_state_sha256"]),
        reason=f"Execute {operation_id} for snapshot replay coverage.",
        session_id=session_id,
    )


def _submit_active(package: Path, run_dir: Path) -> None:
    state = _read_json(run_dir / "state.json")
    checkpoint_id = str(state["active_checkpoint_id"])
    checkpoint = next(
        item for item in load_evidence_lifecycle_spec(package).checkpoints if item.checkpoint_id == checkpoint_id
    )
    payload: dict[str, Any] = {field: [] for field in checkpoint.required_submission_fields}
    payload["checkpoint_id"] = checkpoint_id
    _write_json(run_dir / "workspace" / checkpoint.submission_path, payload)
    submit_evidence_checkpoint(package, run_dir)


def _state(package: Path, run_dir: Path) -> tuple[EvidenceLifecycleRunState, EvidenceLifecycleSpec]:
    return (
        EvidenceLifecycleRunState.model_validate(_read_json(run_dir / "state.json")),
        load_evidence_lifecycle_spec(package),
    )


def _replace_action_fields(run_dir: Path, action_id: str, updates: dict[str, object]) -> None:
    state_path = run_dir / "state.json"
    state = _read_json(state_path)
    for checkpoint in cast(list[dict[str, Any]], state["checkpoint_runs"]):
        for action in cast(list[dict[str, Any]], checkpoint["operation_actions"]):
            if action["action_id"] == action_id:
                action.update(updates)
    _write_json(state_path, state)
    action_path = run_dir / "lifecycle_operations" / action_id / "action.json"
    action = _read_json(action_path)
    action.update(updates)
    _write_json(action_path, action)


def _admin_revision_after_activation(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    package, run_dir = _materialize(tmp_path)
    _open(package, run_dir, "baseline.session-001")
    for operation_id in (
        "hydrology.design-10yr",
        "detention-outlet.design-10yr.declared-outlet",
        "network-hgl.design-10yr.declared-tailwater",
        "hydrology.major-100yr",
        "detention-outlet.major-100yr.declared-outlet",
        "network-hgl.major-100yr.declared-tailwater",
    ):
        _execute(package, run_dir, operation_id, "baseline.session-001")
    _submit_active(package, run_dir)
    _open(package, run_dir, "revision.session-001")
    activation = _execute(package, run_dir, "source-revision.current", "revision.session-001")
    return package, run_dir, activation


def test_source_identity_hashes_deterministic_pretty_source_bytes_and_revision() -> None:
    source_state = {"z": 2, "a": {"nested": True}}

    physical, visible = lifecycle_operation_source_identity(
        source_state=source_state,
        revision_id="revision_alpha",
    )

    pretty = (json.dumps(source_state, indent=2, sort_keys=True) + "\n").encode("utf-8")
    assert physical == hashlib.sha256(pretty).hexdigest()
    visible_payload = {
        "schema_version": "1",
        "physical_source_state_sha256": physical,
        "revision_id": "revision_alpha",
    }
    encoded = json.dumps(visible_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert visible == hashlib.sha256(encoded).hexdigest()


def test_snapshot_accepts_admin_no_op_catalogue_using_cumulative_history(tmp_path: Path) -> None:
    package, run_dir, _activation = _admin_revision_after_activation(tmp_path)
    state, spec = _state(package, run_dir)

    validate_lifecycle_operation_snapshot(run_dir, state, spec)

    catalogue = _read_json(run_dir / "workspace/checkpoints/revision_analysis/operations.json")
    statuses = {item["operation_id"]: item["status"] for item in catalogue["operations"]}
    assert set(statuses.values()) == {"current_or_reusable"}


@pytest.mark.parametrize("tamper", ["source_state", "revision_id"])
def test_snapshot_self_binds_current_source_content_and_revision(tmp_path: Path, tamper: str) -> None:
    package, run_dir, _activation = _admin_revision_after_activation(tmp_path)
    current_path = run_dir / "workspace/hydraulics/current-source.json"
    current = _read_json(current_path)
    if tamper == "source_state":
        current["source_state"]["payload"]["catchments"][0]["area_ha"] = 999.0
    else:
        current["revision_id"] = "relabeled_revision"
    _write_json(current_path, current)
    state, spec = _state(package, run_dir)

    with pytest.raises(ValueError, match="current source .* identity"):
        validate_lifecycle_operation_snapshot(run_dir, state, spec)


def test_snapshot_can_require_resolver_derived_current_source(tmp_path: Path) -> None:
    package, run_dir, _activation = _admin_revision_after_activation(tmp_path)
    current = LifecycleOperationCurrentSource.model_validate(
        _read_json(run_dir / "workspace/hydraulics/current-source.json")
    )
    expected = current.model_copy(update={"revision_id": "different_revision"})
    state, spec = _state(package, run_dir)

    with pytest.raises(ValueError, match="expected packaged source"):
        validate_lifecycle_operation_snapshot(
            run_dir,
            state,
            spec,
            expected_current_source=expected,
        )


def test_snapshot_replays_internal_pre_action_state_hash(tmp_path: Path) -> None:
    package, run_dir = _materialize(tmp_path, variant_id="tailwater_revision")
    _open(package, run_dir, "baseline.session-001")
    action = _execute(package, run_dir, "hydrology.design-10yr", "baseline.session-001")
    _replace_action_fields(run_dir, str(action["action_id"]), {"pre_action_state_sha256": "f" * 64})
    state, spec = _state(package, run_dir)

    with pytest.raises(ValueError, match="pre-action state hash"):
        validate_lifecycle_operation_snapshot(run_dir, state, spec)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("operation_id", "undeclared.operation", "absent from the public operation catalogue"),
        ("operation_kind", "forged_kind", "kind does not match the public operation catalogue"),
    ],
)
def test_snapshot_replays_public_operation_membership_and_kind(
    tmp_path: Path,
    field_name: str,
    value: str,
    message: str,
) -> None:
    package, run_dir = _materialize(tmp_path, variant_id="tailwater_revision")
    _open(package, run_dir, "baseline.session-001")
    action = _execute(package, run_dir, "hydrology.design-10yr", "baseline.session-001")
    _replace_action_fields(run_dir, str(action["action_id"]), {field_name: value})
    state, spec = _state(package, run_dir)

    with pytest.raises(ValueError, match=message):
        validate_lifecycle_operation_snapshot(run_dir, state, spec)


def test_run_state_replays_declared_checkpoint_budget(tmp_path: Path) -> None:
    package, run_dir = _materialize(tmp_path, variant_id="tailwater_revision")
    _open(package, run_dir, "baseline.session-001")
    state, spec = _state(package, run_dir)
    checkpoint = state.checkpoint("baseline_analysis").model_copy(
        update={"operation_budget": 7, "operation_budget_remaining": 7}
    )
    forged = state.model_copy(update={"checkpoint_runs": [checkpoint, *state.checkpoint_runs[1:]]})

    with pytest.raises(EvidenceLifecycleError, match="budget does not match"):
        validate_lifecycle_operation_run_state(forged, spec)


def test_snapshot_rejects_implausible_stale_source_rejection(tmp_path: Path) -> None:
    package, run_dir = _materialize(tmp_path, variant_id="tailwater_revision")
    _open(package, run_dir, "baseline.session-001")
    current = _read_json(run_dir / "workspace/hydraulics/current-source.json")
    rejected = execute_lifecycle_operation(
        package,
        run_dir,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256="f" * 64,
        reason="Record a stale-source rejection for replay coverage.",
        session_id="baseline.session-001",
    )
    action_id = str(rejected["action_id"])
    request_path = run_dir / "lifecycle_operations" / action_id / "request.json"
    request = _read_json(request_path)
    request["visible_source_state_sha256"] = current["visible_source_state_sha256"]
    _write_json(request_path, request)
    rejection_projection = {
        "schema_version": "1",
        "operation_id": "hydrology.design-10yr",
        "supplied_visible_source_sha256": current["visible_source_state_sha256"],
    }
    encoded_projection = json.dumps(rejection_projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    _replace_action_fields(
        run_dir,
        action_id,
        {
            "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
            "input_projection_sha256": hashlib.sha256(encoded_projection).hexdigest(),
        },
    )
    state, spec = _state(package, run_dir)

    with pytest.raises(ValueError, match="stale-source rejection"):
        validate_lifecycle_operation_snapshot(run_dir, state, spec)


def test_snapshot_rejects_implausible_budget_rejection(tmp_path: Path) -> None:
    package, run_dir = _materialize(tmp_path, variant_id="tailwater_revision")
    _open(package, run_dir, "baseline.session-001")
    current = _read_json(run_dir / "workspace/hydraulics/current-source.json")
    rejected = execute_lifecycle_operation(
        package,
        run_dir,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256="f" * 64,
        reason="Record a rejection whose type will be forged.",
        session_id="baseline.session-001",
    )
    action_id = str(rejected["action_id"])
    request_path = run_dir / "lifecycle_operations" / action_id / "request.json"
    request = _read_json(request_path)
    request["visible_source_state_sha256"] = current["visible_source_state_sha256"]
    _write_json(request_path, request)
    rejection_projection = {
        "schema_version": "1",
        "operation_id": "hydrology.design-10yr",
        "supplied_visible_source_sha256": current["visible_source_state_sha256"],
    }
    encoded_projection = json.dumps(rejection_projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    _replace_action_fields(
        run_dir,
        action_id,
        {
            "rejection": "budget_exhausted",
            "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
            "input_projection_sha256": hashlib.sha256(encoded_projection).hexdigest(),
        },
    )
    state, spec = _state(package, run_dir)

    with pytest.raises(ValueError, match="retains available budget"):
        validate_lifecycle_operation_snapshot(run_dir, state, spec)


def test_snapshot_reconciles_source_activation_identity_artifact(tmp_path: Path) -> None:
    package, run_dir, activation = _admin_revision_after_activation(tmp_path)
    identity_artifact = next(
        item
        for item in cast(list[dict[str, Any]], activation["artifacts"])
        if item["path"].endswith("source-identity.json")
    )
    identity_path = run_dir / str(identity_artifact["path"])
    identity = _read_json(identity_path)
    identity["revision_id"] = "forged_revision"
    _write_json(identity_path, identity)
    state, spec = _state(package, run_dir)

    with pytest.raises(ValueError, match="source activation identity"):
        validate_lifecycle_operation_snapshot(run_dir, state, spec)


def test_snapshot_requires_action_attempt_owner(tmp_path: Path) -> None:
    package, run_dir = _materialize(tmp_path, variant_id="tailwater_revision")
    _open(package, run_dir, "baseline.session-001")
    action = _execute(package, run_dir, "hydrology.design-10yr", "baseline.session-001")
    _replace_action_fields(run_dir, str(action["action_id"]), {"attempt_id": "missing.attempt"})
    state, spec = _state(package, run_dir)

    with pytest.raises(ValueError, match="matching checkpoint attempt"):
        validate_lifecycle_operation_snapshot(run_dir, state, spec)
