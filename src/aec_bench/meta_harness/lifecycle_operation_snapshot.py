# ABOUTME: Validates immutable lifecycle-operation catalogues, transactions, and visible projections.
# ABOUTME: Provides one generic v5 snapshot contract for TrialRecord import and transfer evaluation.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleOperationCatalog,
    LifecycleOperationCurrentSource,
)
from aec_bench.meta_harness.evidence_lifecycle_state import (
    EvidenceLifecycleRunState,
    LifecycleOperationActionRecord,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
    LifecycleOperationRejection,
)
from aec_bench.meta_harness.evidence_request_protocol import EvidenceLifecycleError
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_source_identity,
    lifecycle_operation_source_state_bytes,
    validate_lifecycle_operation_run_state,
)
from aec_bench.task_world_templates.contracts import EvidenceLifecycleSpec


def expected_lifecycle_operation_run_artifact_paths(
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
) -> frozenset[str]:
    """Return the exact generic operation-controlled file inventory for one v5 run."""
    supports_operations = any(checkpoint.conditional_operations is not None for checkpoint in spec.checkpoints)
    expected: set[str] = set()
    if supports_operations and any(checkpoint.status.value != "pending" for checkpoint in state.checkpoint_runs):
        expected.add("workspace/hydraulics/current-source.json")
    checkpoint_specs = {checkpoint.checkpoint_id: checkpoint for checkpoint in spec.checkpoints}
    for checkpoint in state.checkpoint_runs:
        checkpoint_spec = checkpoint_specs[checkpoint.checkpoint_id]
        if checkpoint_spec.conditional_operations is not None and checkpoint.status.value != "pending":
            expected.add(f"workspace/checkpoints/{checkpoint.checkpoint_id}/operations.json")
        for action in checkpoint.operation_actions:
            transaction = f"lifecycle_operations/{action.action_id}"
            expected.update(
                {
                    f"{transaction}/request.json",
                    f"{transaction}/action.json",
                    f"{transaction}/committed.json",
                }
            )
            if action.outcome is LifecycleOperationOutcome.COMPLETED:
                expected.add(f"{transaction}/result-manifest.json")
            for artifact in action.artifacts:
                expected.add(artifact.path)
                if artifact.workspace_path is not None:
                    expected.add(f"workspace/{artifact.workspace_path}")
    return frozenset(expected)


def is_lifecycle_operation_run_artifact_path(relative: str) -> bool:
    """Identify files governed by the generic lifecycle-operation snapshot contract."""
    path = Path(relative)
    return (
        path.parts[:1] == ("lifecycle_operations",)
        or (path.parts[:2] == ("workspace", "inbox") and "operations" in path.parts[2:])
        or (path.parts[:2] == ("workspace", "checkpoints") and path.name == "operations.json")
        or path.parts == ("workspace", "hydraulics", "current-source.json")
    )


def validate_lifecycle_operation_snapshot(
    run_dir: Path,
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
    *,
    expected_current_source: LifecycleOperationCurrentSource | None = None,
) -> None:
    """Validate a filesystem-backed v5 operation snapshot without executing an operation."""
    expected = expected_lifecycle_operation_run_artifact_paths(state, spec)
    actual: set[str] = set()
    for path in sorted(run_dir.rglob("*")):
        relative = path.relative_to(run_dir).as_posix()
        if not is_lifecycle_operation_run_artifact_path(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"snapshotted lifecycle operation artifact is a symlink: {relative}")
        if path.is_file():
            actual.add(relative)
    _validate_inventory(actual, expected)

    def read_artifact(relative: str) -> bytes | None:
        path = run_dir / relative
        return path.read_bytes() if path.is_file() and not path.is_symlink() else None

    validate_lifecycle_operation_snapshot_payloads(
        state=state,
        spec=spec,
        artifact_paths=frozenset(actual),
        read_artifact=read_artifact,
        expected_current_source=expected_current_source,
    )


def validate_lifecycle_operation_snapshot_payloads(
    *,
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
    artifact_paths: frozenset[str],
    read_artifact: Callable[[str], bytes | None],
    expected_current_source: LifecycleOperationCurrentSource | None = None,
) -> None:
    """Validate a v5 operation snapshot through an immutable relative-path byte reader."""
    try:
        validate_lifecycle_operation_run_state(state, spec)
    except EvidenceLifecycleError as exc:
        raise ValueError(str(exc)) from exc
    expected = expected_lifecycle_operation_run_artifact_paths(state, spec)
    _validate_inventory(set(artifact_paths), expected)
    supports_operations = any(checkpoint.conditional_operations is not None for checkpoint in spec.checkpoints)
    if not supports_operations:
        return

    current_source_path = "workspace/hydraulics/current-source.json"
    current_source: LifecycleOperationCurrentSource | None = None
    if current_source_path in expected:
        current_source = LifecycleOperationCurrentSource.model_validate(
            _read_object(read_artifact, current_source_path)
        )
        _validate_current_source_identity(current_source)
        if expected_current_source is not None and current_source != expected_current_source:
            raise ValueError("snapshotted current source does not match the expected packaged source")
    elif expected_current_source is not None:
        raise ValueError("snapshotted lifecycle operation state lacks the expected packaged source")
    actions = sorted(
        (action for checkpoint in state.checkpoint_runs for action in checkpoint.operation_actions),
        key=lambda action: action.sequence,
    )
    _validate_action_history(actions)
    if actions and current_source is not None:
        last_action = actions[-1]
        if (
            current_source.visible_source_state_sha256 != last_action.visible_source_state_after_sha256
            or current_source.physical_source_state_sha256 != last_action.physical_source_state_after_sha256
        ):
            raise ValueError("snapshotted current source does not match the operation history")
    if current_source is not None:
        _validate_source_activation_projection(actions, current_source, read_artifact)

    checkpoint_specs = {checkpoint.checkpoint_id: checkpoint for checkpoint in spec.checkpoints}
    cumulative_actions: list[LifecycleOperationActionRecord] = []
    prior_checkpoint_source_sha256: str | None = None
    for checkpoint in state.checkpoint_runs:
        checkpoint_spec = checkpoint_specs[checkpoint.checkpoint_id]
        conditional = checkpoint_spec.conditional_operations
        checkpoint_actions = sorted(checkpoint.operation_actions, key=lambda action: action.sequence)
        cumulative_actions.extend(checkpoint_actions)
        checkpoint_source_sha256 = (
            cumulative_actions[-1].visible_source_state_after_sha256
            if cumulative_actions
            else prior_checkpoint_source_sha256
        )
        if conditional is not None and checkpoint.status.value != "pending":
            catalog_path = f"workspace/checkpoints/{checkpoint.checkpoint_id}/operations.json"
            catalog = LifecycleOperationCatalog.model_validate(_read_object(read_artifact, catalog_path))
            if current_source is None:
                raise ValueError("snapshotted operation catalogue lacks a current source")
            if (
                catalog.checkpoint_id != checkpoint.checkpoint_id
                or catalog.operation_budget != checkpoint.operation_budget
                or catalog.remaining_budget != checkpoint.operation_budget_remaining
            ):
                raise ValueError("snapshotted operation catalogue does not match lifecycle state")
            if checkpoint_source_sha256 is not None and catalog.visible_source_state_sha256 != checkpoint_source_sha256:
                raise ValueError("snapshotted operation catalogue does not match its checkpoint source")
            expected_operations = [operation.model_dump(mode="json") for operation in conditional.operations]
            actual_operations = [
                operation.model_dump(mode="json", exclude={"status"}) for operation in catalog.operations
            ]
            if actual_operations != expected_operations:
                raise ValueError("snapshotted operation catalogue does not match the lifecycle contract")
            completed_operation_ids = {
                action.operation_id
                for action in cumulative_actions
                if action.outcome in {LifecycleOperationOutcome.COMPLETED, LifecycleOperationOutcome.ALREADY_CURRENT}
            }
            for operation in catalog.operations:
                required = set(operation.prerequisite_operation_ids)
                if not required.issubset(completed_operation_ids) and operation.status != "prerequisites_incomplete":
                    raise ValueError("snapshotted operation catalogue exposes an operation before its prerequisites")
                matching_completed = any(
                    action.operation_id == operation.operation_id
                    and action.outcome is LifecycleOperationOutcome.COMPLETED
                    for action in cumulative_actions
                )
                if operation.status == "current_or_reusable" and not matching_completed:
                    raise ValueError("snapshotted operation catalogue marks an uncomputed operation as current")
                if checkpoint.operation_budget_remaining == 0 and operation.status == "available":
                    raise ValueError(
                        "snapshotted operation catalogue exposes a budget-consuming operation without budget"
                    )
                if checkpoint.operation_budget_remaining > 0 and operation.status == "budget_exhausted":
                    raise ValueError("snapshotted operation catalogue hides available operation budget")

        for action in checkpoint.operation_actions:
            _validate_action_transaction(action, read_artifact)
        if checkpoint_source_sha256 is not None:
            prior_checkpoint_source_sha256 = checkpoint_source_sha256


def _validate_action_transaction(
    action: LifecycleOperationActionRecord,
    read_artifact: Callable[[str], bytes | None],
) -> None:
    transaction = f"lifecycle_operations/{action.action_id}"
    request_content = _required_content(read_artifact, f"{transaction}/request.json")
    if hashlib.sha256(request_content).hexdigest() != action.request_sha256:
        raise ValueError("snapshotted operation request hash mismatch")
    request = _decode_object(request_content, f"{transaction}/request.json")
    if (
        set(request)
        != {
            "schema_version",
            "action_id",
            "checkpoint_id",
            "operation_id",
            "visible_source_state_sha256",
            "reason",
        }
        or not _is_sha256(request.get("visible_source_state_sha256"))
        or request.get("schema_version") != "1"
        or request.get("action_id") != action.action_id
        or request.get("checkpoint_id") != action.requested_checkpoint_id
        or request.get("operation_id") != action.operation_id
        or request.get("reason") != action.reason
    ):
        raise ValueError("snapshotted operation request does not match lifecycle state")
    if action.outcome is LifecycleOperationOutcome.REJECTED:
        supplied_source_sha256 = str(request["visible_source_state_sha256"])
        if action.input_projection_sha256 != _rejection_projection_sha256(
            action.operation_id,
            supplied_source_sha256,
        ):
            raise ValueError("rejected operation input projection does not match its request")
        if (
            action.rejection is LifecycleOperationRejection.STALE_VISIBLE_SOURCE
            and supplied_source_sha256 == action.visible_source_state_before_sha256
        ):
            raise ValueError("stale-source rejection is not plausible for the supplied current source")
        if (
            action.rejection
            in {
                LifecycleOperationRejection.PREREQUISITES_INCOMPLETE,
                LifecycleOperationRejection.BUDGET_EXHAUSTED,
            }
            and supplied_source_sha256 != action.visible_source_state_before_sha256
        ):
            raise ValueError("operation rejection bypasses the earlier stale-source check")
    elif request["visible_source_state_sha256"] != action.visible_source_state_before_sha256:
        raise ValueError("successful operation request does not match its source-before identity")

    persisted = LifecycleOperationActionRecord.model_validate(_read_object(read_artifact, f"{transaction}/action.json"))
    if persisted != action:
        raise ValueError("snapshotted operation action does not match lifecycle state")
    committed = _read_object(read_artifact, f"{transaction}/committed.json")
    if committed != {"action_id": action.action_id, "status": "committed"}:
        raise ValueError("snapshotted operation transaction is not committed")

    if action.outcome is LifecycleOperationOutcome.COMPLETED:
        manifest_path = f"{transaction}/result-manifest.json"
        manifest_content = _required_content(read_artifact, manifest_path)
        if hashlib.sha256(manifest_content).hexdigest() != action.result_manifest_sha256:
            raise ValueError("snapshotted operation result manifest hash mismatch")
        relative_prefix = f"{transaction}/artifacts/"
        if any(not artifact.path.startswith(relative_prefix) for artifact in action.artifacts):
            raise ValueError("completed operation artifacts must belong to their transaction")
        artifact_sha256 = {
            artifact.path.removeprefix(relative_prefix): artifact.sha256 for artifact in action.artifacts
        }
        expected_manifest = {
            "schema_version": "1",
            "action_id": action.action_id,
            "operation_id": action.operation_id,
            "input_projection_sha256": action.input_projection_sha256,
            "physical_source_state_sha256": action.physical_source_state_after_sha256,
            "visible_source_state_sha256": action.visible_source_state_after_sha256,
            "prerequisite_action_ids": list(action.prerequisite_action_ids),
            "artifact_sha256": artifact_sha256,
        }
        if _decode_object(manifest_content, manifest_path) != expected_manifest:
            raise ValueError("snapshotted operation result manifest does not match lifecycle state")
    elif action.outcome is LifecycleOperationOutcome.ALREADY_CURRENT:
        retained_prefix = f"lifecycle_operations/{action.retained_from_action_id}/artifacts/"
        if any(not artifact.path.startswith(retained_prefix) for artifact in action.artifacts):
            raise ValueError("reused operation artifacts must belong to the retained transaction")

    for artifact in action.artifacts:
        canonical = _required_content(read_artifact, artifact.path)
        if hashlib.sha256(canonical).hexdigest() != artifact.sha256:
            raise ValueError("snapshotted operation artifact hash mismatch")
        if artifact.workspace_path is not None:
            projection = _required_content(read_artifact, f"workspace/{artifact.workspace_path}")
            if hashlib.sha256(projection).hexdigest() != artifact.sha256 or projection != canonical:
                raise ValueError("snapshotted operation workspace projection mismatch")


def _validate_inventory(actual: set[str], expected: frozenset[str]) -> None:
    if actual == set(expected):
        return
    missing = ", ".join(sorted(set(expected) - actual)) or "none"
    unexpected = ", ".join(sorted(actual - set(expected))) or "none"
    raise ValueError(
        "snapshotted lifecycle operation artifact inventory does not match lifecycle state: "
        f"missing={missing}; unexpected={unexpected}"
    )


def _validate_action_history(actions: list[LifecycleOperationActionRecord]) -> None:
    prior_actions: dict[str, LifecycleOperationActionRecord] = {}
    for action in actions:
        if action.outcome is LifecycleOperationOutcome.ALREADY_CURRENT:
            retained = prior_actions.get(str(action.retained_from_action_id))
            if retained is None or retained.outcome is not LifecycleOperationOutcome.COMPLETED:
                raise ValueError("reused operation must retain a prior completed action")
            if (
                action.operation_id != retained.operation_id
                or action.input_projection_sha256 != retained.input_projection_sha256
                or action.prerequisite_action_ids != retained.prerequisite_action_ids
                or action.artifacts != retained.artifacts
            ):
                raise ValueError("reused operation does not match its retained completed action")
        prior_actions[action.action_id] = action


def _validate_current_source_identity(current_source: LifecycleOperationCurrentSource) -> None:
    physical_sha256, visible_sha256 = lifecycle_operation_source_identity(
        source_state=current_source.source_state,
        revision_id=current_source.revision_id,
    )
    if current_source.physical_source_state_sha256 != physical_sha256:
        raise ValueError("snapshotted current source physical identity does not match its source state")
    if current_source.visible_source_state_sha256 != visible_sha256:
        raise ValueError("snapshotted current source visible identity does not match its revision")


def _validate_source_activation_projection(
    actions: list[LifecycleOperationActionRecord],
    current_source: LifecycleOperationCurrentSource,
    read_artifact: Callable[[str], bytes | None],
) -> None:
    activation = next(
        (
            action
            for action in reversed(actions)
            if action.outcome is LifecycleOperationOutcome.COMPLETED
            and action.disposition is LifecycleOperationDisposition.ACTIVATED
        ),
        None,
    )
    if activation is None:
        return
    identity_paths = [
        artifact.path for artifact in activation.artifacts if artifact.path.endswith("/source-identity.json")
    ]
    if len(identity_paths) > 1:
        raise ValueError("source activation contains multiple canonical source identities")
    if identity_paths:
        identity = _read_object(read_artifact, identity_paths[0])
        if identity != current_source.model_dump(mode="json"):
            raise ValueError("source activation identity does not match the snapshotted current source")
    source_state_paths = [
        artifact.path for artifact in activation.artifacts if artifact.path.endswith("/source-state.json")
    ]
    if len(source_state_paths) > 1:
        raise ValueError("source activation contains multiple canonical source states")
    if source_state_paths:
        content = _required_content(read_artifact, source_state_paths[0])
        if content != lifecycle_operation_source_state_bytes(current_source.source_state):
            raise ValueError("source activation state does not match the snapshotted current source")


def _rejection_projection_sha256(operation_id: str, supplied_visible_source_sha256: str) -> str:
    encoded = json.dumps(
        {
            "schema_version": "1",
            "operation_id": operation_id,
            "supplied_visible_source_sha256": supplied_visible_source_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_object(read_artifact: Callable[[str], bytes | None], relative: str) -> dict[str, Any]:
    return _decode_object(_required_content(read_artifact, relative), relative)


def _required_content(read_artifact: Callable[[str], bytes | None], relative: str) -> bytes:
    content = read_artifact(relative)
    if content is None:
        raise ValueError(f"snapshotted lifecycle operation artifact is missing: {relative}")
    return content


def _decode_object(content: bytes, relative: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"snapshotted lifecycle operation artifact is invalid JSON: {relative}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"snapshotted lifecycle operation artifact must contain an object: {relative}")
    return payload


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)
