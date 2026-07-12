# ABOUTME: Persists generic lifecycle-operation transactions and model-visible projections.
# ABOUTME: Reuses the lifecycle lock, durability, ledger, and recovery boundaries established by PR17.

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import ValidationError

from aec_bench.ledger.durability import fsync_directory, fsync_tree, mkdir_durable
from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointAttemptStatus,
    CheckpointRunStatus,
    EvidenceLifecycleRunState,
    LifecycleOperationActionRecord,
    LifecycleOperationArtifact,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
    LifecycleOperationRejection,
    LifecycleTransitionKind,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    EvidenceLifecycleError,
    _append_transition,
    _checkpoint,
)
from aec_bench.meta_harness.evidence_request_store import (
    _assert_ledger_entry_matches,
    _copy_release,
    _ledger_entries_by_summary_id,
    _ledger_path,
    _read_json,
    _sha256,
    _sync_transition_ledger,
    _workspace,
    _write_json,
    _write_json_atomic_durable,
    _write_state,
)
from aec_bench.meta_harness.ledger import append_ledger_entry
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    LifecycleOperationPlan,
    LifecycleOperationPrerequisiteError,
    LifecycleOperationResolver,
    LifecycleOperationSourceContext,
    current_lifecycle_operation_action,
    lifecycle_operation_state_sha256,
    validate_lifecycle_operation_run_state,
)
from aec_bench.task_world_templates.contracts import EvidenceCheckpointSpec, EvidenceLifecycleSpec


def _resolver_for_package(package_dir: Path, run_dir: Path) -> LifecycleOperationResolver:
    from aec_bench.task_world_templates.lifecycles import lifecycle_operation_resolver

    resolver = lifecycle_operation_resolver(package_dir, run_dir)
    if resolver is None:
        raise EvidenceLifecycleError("lifecycle package does not support model-facing operations")
    return cast(LifecycleOperationResolver, resolver)


def _all_operation_actions(state: EvidenceLifecycleRunState) -> list[LifecycleOperationActionRecord]:
    return sorted(
        (action for checkpoint in state.checkpoint_runs for action in checkpoint.operation_actions),
        key=lambda action: action.sequence,
    )


def resolve_lifecycle_operation_current_source(
    package_dir: Path,
    run_dir: Path,
    state: EvidenceLifecycleRunState,
) -> LifecycleOperationSourceContext:
    """Resolve the current source from the registered package and immutable action history."""
    resolver = _resolver_for_package(Path(package_dir), Path(run_dir))
    return resolver.current_source(_all_operation_actions(state))


def validate_lifecycle_operation_resolver_replay(
    package_dir: Path,
    run_dir: Path,
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
) -> None:
    """Replay immutable operation history against the registered live resolver without mutation."""
    package = Path(package_dir)
    run = Path(run_dir)
    validate_lifecycle_operation_run_state(state, spec)
    actions = _all_operation_actions(state)
    resolver = _resolver_for_package(package, run)
    transaction_root = _validate_operation_transaction_inventory(run, actions)
    _validate_operation_catalog_replay(run, state, spec, resolver)
    prior_actions: list[LifecycleOperationActionRecord] = []
    remaining_budgets = {checkpoint.checkpoint_id: checkpoint.operation_budget for checkpoint in state.checkpoint_runs}
    for expected_sequence, action in enumerate(actions, start=1):
        if action.sequence != expected_sequence or action.action_id != f"operation-{expected_sequence:06d}":
            raise EvidenceLifecycleError("operation resolver replay sequence is not contiguous")
        transaction = transaction_root / action.action_id
        transaction_action = _read_operation_transaction_action(run, transaction)
        if transaction_action != action:
            raise EvidenceLifecycleError("operation transaction action does not match resolver replay state")
        budget_before = remaining_budgets[action.checkpoint_id]
        supplied_source_sha256 = _validate_operation_transaction(
            run,
            transaction,
            action,
            prior_actions,
        )
        _validate_operation_resolver_action(
            state,
            spec,
            resolver,
            action,
            prior_actions,
            budget_before=budget_before,
            supplied_source_sha256=supplied_source_sha256,
        )
        remaining_budgets[action.checkpoint_id] = action.budget_after
        prior_actions.append(action)
    for checkpoint in state.checkpoint_runs:
        if remaining_budgets[checkpoint.checkpoint_id] != checkpoint.operation_budget_remaining:
            raise EvidenceLifecycleError("operation resolver replay remaining budget does not match lifecycle state")
    _validate_lifecycle_operation_ledger(run, state)


def _assert_run_path_not_symlinked(run_dir: Path, path: Path, *, label: str) -> None:
    run = Path(run_dir)
    target = Path(path)
    try:
        relative = target.relative_to(run)
    except ValueError as exc:
        raise EvidenceLifecycleError(f"{label} escapes the lifecycle run directory") from exc
    if ".." in relative.parts:
        raise EvidenceLifecycleError(f"{label} escapes the lifecycle run directory")
    current = run
    if current.is_symlink():
        raise EvidenceLifecycleError(f"{label} contains a symlink at the lifecycle run directory")
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise EvidenceLifecycleError(f"{label} contains a symlink: {current}")


def _require_operation_directory(run_dir: Path, path: Path, *, label: str) -> None:
    _assert_run_path_not_symlinked(run_dir, path, label=label)
    if not path.is_dir():
        raise EvidenceLifecycleError(f"{label} is not a directory: {path}")


def _require_operation_file(run_dir: Path, path: Path, *, label: str) -> None:
    _assert_run_path_not_symlinked(run_dir, path, label=label)
    if not path.is_file():
        raise EvidenceLifecycleError(f"{label} is not a regular file: {path}")


def _validate_operation_transaction_inventory(
    run_dir: Path,
    actions: list[LifecycleOperationActionRecord],
) -> Path:
    transaction_root = run_dir / "lifecycle_operations"
    _assert_run_path_not_symlinked(run_dir, transaction_root, label="operation transaction root")
    expected = {action.action_id for action in actions}
    if not transaction_root.exists():
        if expected:
            raise EvidenceLifecycleError("operation transaction inventory is missing canonical actions")
        return transaction_root
    _require_operation_directory(run_dir, transaction_root, label="operation transaction root")
    entries = sorted(transaction_root.iterdir(), key=lambda entry: entry.name)
    for entry in entries:
        _assert_run_path_not_symlinked(run_dir, entry, label="operation transaction inventory entry")
    actual = {entry.name for entry in entries}
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        unexpected = ", ".join(sorted(actual - expected)) or "none"
        raise EvidenceLifecycleError(
            "operation transaction inventory does not match lifecycle state: "
            f"missing={missing}; unexpected={unexpected}"
        )
    for entry in entries:
        _require_operation_directory(run_dir, entry, label="operation transaction directory")
    return transaction_root


def _discard_operation_staging(path: Path) -> None:
    if path.is_symlink():
        path.unlink(missing_ok=True)
    else:
        shutil.rmtree(path, ignore_errors=True)


def _completed_operation_ids(actions: list[LifecycleOperationActionRecord]) -> set[str]:
    return {
        action.operation_id
        for action in actions
        if action.outcome in {LifecycleOperationOutcome.COMPLETED, LifecycleOperationOutcome.ALREADY_CURRENT}
    }


def _write_current_source_projection(
    run_dir: Path,
    resolver: LifecycleOperationResolver,
    state: EvidenceLifecycleRunState,
) -> LifecycleOperationSourceContext:
    source = resolver.current_source(_all_operation_actions(state))
    destination = _workspace(run_dir) / "hydraulics" / "current-source.json"
    _assert_run_path_not_symlinked(run_dir, destination, label="operation current-source projection")
    _write_json_atomic_durable(
        destination,
        {
            "schema_version": "1",
            "revision_id": source.revision_id,
            "physical_source_state_sha256": source.physical_source_state_sha256,
            "visible_source_state_sha256": source.visible_source_state_sha256,
            "source_state": source.source_state,
        },
    )
    return source


def _operation_catalog_payload(
    checkpoint: EvidenceCheckpointSpec,
    *,
    operation_budget: int,
    operation_budget_remaining: int,
    actions: list[LifecycleOperationActionRecord],
    source: LifecycleOperationSourceContext,
    resolver: LifecycleOperationResolver,
) -> dict[str, Any] | None:
    conditional = checkpoint.conditional_operations
    if conditional is None:
        return None
    completed_ids = _completed_operation_ids(actions)
    operations = []
    for operation in conditional.operations:
        if not set(operation.prerequisite_operation_ids).issubset(completed_ids):
            status = "prerequisites_incomplete"
        else:
            try:
                plan = resolver.plan(operation, actions)
            except LifecycleOperationPrerequisiteError:
                status = "prerequisites_incomplete"
            else:
                if current_lifecycle_operation_action(actions, plan) is not None:
                    status = "current_or_reusable"
                elif operation_budget_remaining == 0:
                    status = "budget_exhausted"
                else:
                    status = "available"
        payload = operation.model_dump(mode="json")
        payload["status"] = status
        operations.append(payload)
    return {
        "schema_version": "1",
        "checkpoint_id": checkpoint.checkpoint_id,
        "operation_budget": operation_budget,
        "remaining_budget": operation_budget_remaining,
        "visible_source_state_sha256": source.visible_source_state_sha256,
        "operations": operations,
    }


def _validate_operation_catalog_replay(
    run_dir: Path,
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
    resolver: LifecycleOperationResolver,
) -> None:
    cumulative_actions: list[LifecycleOperationActionRecord] = []
    for checkpoint_run, checkpoint in zip(state.checkpoint_runs, spec.checkpoints, strict=True):
        cumulative_actions.extend(sorted(checkpoint_run.operation_actions, key=lambda action: action.sequence))
        if checkpoint.conditional_operations is None or checkpoint_run.status == CheckpointRunStatus.PENDING:
            continue
        source = resolver.current_source(cumulative_actions)
        expected = _operation_catalog_payload(
            checkpoint,
            operation_budget=checkpoint_run.operation_budget,
            operation_budget_remaining=checkpoint_run.operation_budget_remaining,
            actions=cumulative_actions,
            source=source,
            resolver=resolver,
        )
        catalog_path = _workspace(run_dir) / "checkpoints" / checkpoint.checkpoint_id / "operations.json"
        _require_operation_file(run_dir, catalog_path, label="operation catalogue projection")
        if expected is None or _read_json(catalog_path) != expected:
            raise EvidenceLifecycleError(
                f"operation catalogue does not match the live resolver plan: {checkpoint.checkpoint_id}"
            )


def _write_lifecycle_operation_catalog(
    package_dir: Path,
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
    state: EvidenceLifecycleRunState,
) -> None:
    resolver = _resolver_for_package(package_dir, run_dir)
    source = _write_current_source_projection(run_dir, resolver, state)
    active_checkpoint_id = state.active_checkpoint_id
    if active_checkpoint_id is None:
        return
    checkpoint = _checkpoint(spec, active_checkpoint_id)
    checkpoint_run = state.checkpoint(active_checkpoint_id)
    catalog = _operation_catalog_payload(
        checkpoint,
        operation_budget=checkpoint_run.operation_budget,
        operation_budget_remaining=checkpoint_run.operation_budget_remaining,
        actions=_all_operation_actions(state),
        source=source,
        resolver=resolver,
    )
    if catalog is not None:
        destination = _workspace(run_dir) / "checkpoints" / active_checkpoint_id / "operations.json"
        _assert_run_path_not_symlinked(run_dir, destination, label="operation catalogue projection")
        _write_json_atomic_durable(
            destination,
            catalog,
        )


def _record_rejection(
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
    state: EvidenceLifecycleRunState,
    resolver: LifecycleOperationResolver,
    *,
    requested_checkpoint_id: str,
    operation_id: str,
    operation_kind: str,
    reason: str,
    session_id: str,
    supplied_visible_source_sha256: str,
    rejection: LifecycleOperationRejection,
) -> dict[str, Any]:
    source = resolver.current_source(_all_operation_actions(state))
    return _publish_operation_action(
        run_dir,
        spec,
        state,
        resolver,
        requested_checkpoint_id=requested_checkpoint_id,
        operation_id=operation_id,
        operation_kind=operation_kind,
        reason=reason,
        session_id=session_id,
        supplied_visible_source_sha256=supplied_visible_source_sha256,
        plan=None,
        prior=None,
        rejection=rejection,
        source=source,
    )


def _execute_lifecycle_operation_locked(
    package_dir: Path,
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
    state: EvidenceLifecycleRunState,
    *,
    requested_checkpoint_id: str,
    operation_id: str,
    visible_source_state_sha256: str,
    reason: str,
    session_id: str,
) -> dict[str, Any]:
    resolver = _resolver_for_package(package_dir, run_dir)
    current_source = resolver.current_source(_all_operation_actions(state))
    active_checkpoint_id = state.active_checkpoint_id
    if active_checkpoint_id is None:
        raise EvidenceLifecycleError("no checkpoint is active")
    checkpoint = _checkpoint(spec, active_checkpoint_id)
    checkpoint_run = state.checkpoint(active_checkpoint_id)
    attempt = checkpoint_run.active_attempt
    if attempt is None:
        raise EvidenceLifecycleError("no checkpoint attempt is active")
    if attempt.session_id != session_id:
        raise EvidenceLifecycleError(
            f"active attempt belongs to {attempt.session_id}; cannot execute operation from {session_id}"
        )
    if requested_checkpoint_id != active_checkpoint_id:
        return _record_rejection(
            run_dir,
            spec,
            state,
            resolver,
            requested_checkpoint_id=requested_checkpoint_id,
            operation_id=operation_id,
            operation_kind="unknown",
            reason=reason,
            session_id=session_id,
            supplied_visible_source_sha256=visible_source_state_sha256,
            rejection=LifecycleOperationRejection.INACTIVE_CHECKPOINT,
        )
    conditional = checkpoint.conditional_operations
    if conditional is None:
        return _record_rejection(
            run_dir,
            spec,
            state,
            resolver,
            requested_checkpoint_id=requested_checkpoint_id,
            operation_id=operation_id,
            operation_kind="unknown",
            reason=reason,
            session_id=session_id,
            supplied_visible_source_sha256=visible_source_state_sha256,
            rejection=LifecycleOperationRejection.NOT_SUPPORTED,
        )
    operation = next((item for item in conditional.operations if item.operation_id == operation_id), None)
    if operation is None:
        return _record_rejection(
            run_dir,
            spec,
            state,
            resolver,
            requested_checkpoint_id=requested_checkpoint_id,
            operation_id=operation_id,
            operation_kind="unknown",
            reason=reason,
            session_id=session_id,
            supplied_visible_source_sha256=visible_source_state_sha256,
            rejection=LifecycleOperationRejection.UNKNOWN_OPERATION,
        )
    if visible_source_state_sha256 != current_source.visible_source_state_sha256:
        return _record_rejection(
            run_dir,
            spec,
            state,
            resolver,
            requested_checkpoint_id=requested_checkpoint_id,
            operation_id=operation_id,
            operation_kind=operation.kind,
            reason=reason,
            session_id=session_id,
            supplied_visible_source_sha256=visible_source_state_sha256,
            rejection=LifecycleOperationRejection.STALE_VISIBLE_SOURCE,
        )
    actions = _all_operation_actions(state)
    if not set(operation.prerequisite_operation_ids).issubset(_completed_operation_ids(actions)):
        return _record_rejection(
            run_dir,
            spec,
            state,
            resolver,
            requested_checkpoint_id=requested_checkpoint_id,
            operation_id=operation_id,
            operation_kind=operation.kind,
            reason=reason,
            session_id=session_id,
            supplied_visible_source_sha256=visible_source_state_sha256,
            rejection=LifecycleOperationRejection.PREREQUISITES_INCOMPLETE,
        )
    try:
        plan = resolver.plan(operation, actions)
    except LifecycleOperationPrerequisiteError:
        return _record_rejection(
            run_dir,
            spec,
            state,
            resolver,
            requested_checkpoint_id=requested_checkpoint_id,
            operation_id=operation_id,
            operation_kind=operation.kind,
            reason=reason,
            session_id=session_id,
            supplied_visible_source_sha256=visible_source_state_sha256,
            rejection=LifecycleOperationRejection.PREREQUISITES_INCOMPLETE,
        )
    prior = current_lifecycle_operation_action(actions, plan)
    if prior is None and checkpoint_run.operation_budget_remaining == 0:
        return _record_rejection(
            run_dir,
            spec,
            state,
            resolver,
            requested_checkpoint_id=requested_checkpoint_id,
            operation_id=operation_id,
            operation_kind=operation.kind,
            reason=reason,
            session_id=session_id,
            supplied_visible_source_sha256=visible_source_state_sha256,
            rejection=LifecycleOperationRejection.BUDGET_EXHAUSTED,
        )
    return _publish_operation_action(
        run_dir,
        spec,
        state,
        resolver,
        requested_checkpoint_id=requested_checkpoint_id,
        operation_id=operation_id,
        operation_kind=operation.kind,
        reason=reason,
        session_id=session_id,
        supplied_visible_source_sha256=visible_source_state_sha256,
        plan=plan,
        prior=prior,
        rejection=None,
        source=current_source,
    )


def _publish_operation_action(
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
    state: EvidenceLifecycleRunState,
    resolver: LifecycleOperationResolver,
    *,
    requested_checkpoint_id: str,
    operation_id: str,
    operation_kind: str,
    reason: str,
    session_id: str,
    supplied_visible_source_sha256: str,
    plan: LifecycleOperationPlan | None,
    prior: LifecycleOperationActionRecord | None,
    rejection: LifecycleOperationRejection | None,
    source: LifecycleOperationSourceContext,
) -> dict[str, Any]:
    active_checkpoint_id = state.active_checkpoint_id
    if active_checkpoint_id is None:
        raise EvidenceLifecycleError("no checkpoint is active")
    checkpoint_run = state.checkpoint(active_checkpoint_id)
    attempt = checkpoint_run.active_attempt
    if attempt is None or attempt.session_id != session_id:
        raise EvidenceLifecycleError("operation action has no matching active attempt")
    sequence = 1 + len(_all_operation_actions(state))
    action_id = f"operation-{sequence:06d}"
    transaction_root = run_dir / "lifecycle_operations"
    _assert_run_path_not_symlinked(run_dir, transaction_root, label="operation transaction root")
    mkdir_durable(transaction_root)
    _require_operation_directory(run_dir, transaction_root, label="operation transaction root")
    staging = Path(tempfile.mkdtemp(prefix=f".{action_id}.tmp-", dir=transaction_root))
    _require_operation_directory(run_dir, staging, label="operation staging directory")
    transaction = transaction_root / action_id
    _assert_run_path_not_symlinked(run_dir, transaction, label="operation transaction directory")
    if transaction.exists():
        _discard_operation_staging(staging)
        raise EvidenceLifecycleError(f"operation transaction already exists: {action_id}")

    request_payload = {
        "schema_version": "1",
        "action_id": action_id,
        "checkpoint_id": requested_checkpoint_id,
        "operation_id": operation_id,
        "visible_source_state_sha256": supplied_visible_source_sha256,
        "reason": reason,
    }
    try:
        _write_json(staging / "request.json", request_payload)
        request_sha256 = _sha256(staging / "request.json")
    except Exception:
        _discard_operation_staging(staging)
        raise
    artifacts: tuple[LifecycleOperationArtifact, ...] = ()
    result_manifest_sha256: str | None = None
    budget_consumed: Literal[0, 1]
    if rejection is not None:
        outcome = LifecycleOperationOutcome.REJECTED
        disposition = None
        source_after = source
        input_projection_sha256 = _rejection_projection_sha256(operation_id, supplied_visible_source_sha256)
        prerequisite_action_ids: tuple[str, ...] = ()
        retained_from_action_id = None
        budget_consumed = 0
    elif prior is not None and plan is not None:
        outcome = LifecycleOperationOutcome.ALREADY_CURRENT
        disposition = LifecycleOperationDisposition.REUSED
        source_after = plan.source_after
        input_projection_sha256 = plan.input_projection_sha256
        prerequisite_action_ids = plan.prerequisite_action_ids
        retained_from_action_id = prior.action_id
        artifacts = prior.artifacts
        budget_consumed = 0
    elif plan is not None:
        try:
            outcome = LifecycleOperationOutcome.COMPLETED
            disposition = plan.disposition
            source_after = plan.source_after
            input_projection_sha256 = plan.input_projection_sha256
            prerequisite_action_ids = plan.prerequisite_action_ids
            retained_from_action_id = None
            budget_consumed = 1
            artifact_root = staging / "artifacts"
            resolver.execute(plan, artifact_root)
            artifact_hashes = _artifact_inventory(run_dir, artifact_root)
            visible_artifact_paths = _validated_visible_artifact_paths(plan, artifact_hashes)
            artifacts = tuple(
                LifecycleOperationArtifact(
                    path=(Path("lifecycle_operations") / action_id / "artifacts" / relative).as_posix(),
                    workspace_path=(
                        (Path("inbox") / active_checkpoint_id / "operations" / action_id / relative).as_posix()
                        if relative in visible_artifact_paths
                        else None
                    ),
                    sha256=sha256,
                )
                for relative, sha256 in sorted(artifact_hashes.items())
            )
            result_manifest = {
                "schema_version": "1",
                "action_id": action_id,
                "operation_id": operation_id,
                "input_projection_sha256": input_projection_sha256,
                "physical_source_state_sha256": source_after.physical_source_state_sha256,
                "visible_source_state_sha256": source_after.visible_source_state_sha256,
                "prerequisite_action_ids": list(prerequisite_action_ids),
                "artifact_sha256": artifact_hashes,
            }
            _write_json(staging / "result-manifest.json", result_manifest)
            result_manifest_sha256 = _sha256(staging / "result-manifest.json")
        except Exception:
            _discard_operation_staging(staging)
            raise
    else:  # pragma: no cover - all call paths provide a rejection or plan
        _discard_operation_staging(staging)
        raise AssertionError("operation action requires a plan or rejection")

    try:
        budget_before = checkpoint_run.operation_budget_remaining
        pre_state_sha256 = lifecycle_operation_state_sha256(
            state,
            checkpoint_id=active_checkpoint_id,
            source=source,
            operation_budget_remaining=budget_before,
            actions=_all_operation_actions(state),
        )
        checkpoint_run.operation_budget_remaining -= budget_consumed
        action = LifecycleOperationActionRecord(
            action_id=action_id,
            sequence=sequence,
            checkpoint_id=active_checkpoint_id,
            requested_checkpoint_id=requested_checkpoint_id,
            operation_id=operation_id,
            operation_kind=operation_kind,
            reason=reason,
            session_id=session_id,
            attempt_id=attempt.attempt_id,
            outcome=outcome,
            rejection=rejection,
            disposition=disposition,
            visible_source_state_before_sha256=source.visible_source_state_sha256,
            visible_source_state_after_sha256=source_after.visible_source_state_sha256,
            physical_source_state_before_sha256=source.physical_source_state_sha256,
            physical_source_state_after_sha256=source_after.physical_source_state_sha256,
            input_projection_sha256=input_projection_sha256,
            request_sha256=request_sha256,
            result_manifest_sha256=result_manifest_sha256,
            prerequisite_action_ids=prerequisite_action_ids,
            retained_from_action_id=retained_from_action_id,
            pre_action_state_sha256=pre_state_sha256,
            post_action_state_sha256="0" * 64,
            artifacts=artifacts,
            budget_before=budget_before,
            budget_consumed=budget_consumed,
            budget_after=checkpoint_run.operation_budget_remaining,
        )
        checkpoint_run.operation_actions.append(action)
        action.post_action_state_sha256 = lifecycle_operation_state_sha256(
            state,
            checkpoint_id=active_checkpoint_id,
            source=source_after,
            operation_budget_remaining=checkpoint_run.operation_budget_remaining,
            actions=_all_operation_actions(state),
        )
    except Exception:
        _discard_operation_staging(staging)
        raise
    try:
        _write_json(staging / "action.json", action.model_dump(mode="json"))
        fsync_tree(staging)
        _assert_run_path_not_symlinked(run_dir, transaction, label="operation transaction directory")
        staging.replace(transaction)
        fsync_directory(transaction_root)
        if outcome == LifecycleOperationOutcome.COMPLETED:
            _materialize_operation_projection(run_dir, action)
        _append_transition(
            state,
            kind=LifecycleTransitionKind.OPERATION,
            from_checkpoint_id=active_checkpoint_id,
            to_checkpoint_id=active_checkpoint_id,
            reason=f"Lifecycle operation {outcome.value}.",
        )
        _write_state(run_dir, state)
        _sync_transition_ledger(run_dir, state)
        _sync_lifecycle_operation_ledger(run_dir, state)
        _write_lifecycle_operation_catalog(resolver.package_dir, run_dir, spec, state)
        committed = transaction / "committed.json"
        _assert_run_path_not_symlinked(run_dir, committed, label="operation commit metadata")
        _write_json_atomic_durable(
            committed,
            {"action_id": action_id, "status": "committed"},
        )
        fsync_tree(transaction)
        fsync_directory(transaction_root)
    except Exception:
        _discard_operation_staging(staging)
        raise
    return action.model_dump(mode="json")


def _artifact_inventory(run_dir: Path, root: Path) -> dict[str, str]:
    _require_operation_directory(run_dir, root, label="operation artifact directory")
    inventory: dict[str, str] = {}

    def visit(directory: Path) -> None:
        for path in sorted(directory.iterdir()):
            _assert_run_path_not_symlinked(run_dir, path, label="operation artifact path")
            if path.is_dir():
                visit(path)
            elif path.is_file():
                inventory[path.relative_to(root).as_posix()] = _sha256(path)
            else:
                raise EvidenceLifecycleError(f"operation artifact is not a regular file or directory: {path}")

    visit(root)
    if not inventory:
        raise EvidenceLifecycleError("completed operation must produce at least one artifact")
    return inventory


def _validated_visible_artifact_paths(
    plan: LifecycleOperationPlan,
    artifact_hashes: dict[str, str],
) -> set[str]:
    declared = plan.model_visible_artifact_paths
    if not declared:
        raise EvidenceLifecycleError("completed operation must declare a model-visible artifact")
    if len(declared) != len(set(declared)):
        raise EvidenceLifecycleError("model-visible operation artifact paths must be unique")
    visible: set[str] = set()
    for relative in declared:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
            raise EvidenceLifecycleError("model-visible operation artifact path is unsafe")
        if relative not in artifact_hashes:
            raise EvidenceLifecycleError("model-visible operation artifact was not produced")
        visible.add(relative)
    return visible


def _materialize_operation_projection(run_dir: Path, action: LifecycleOperationActionRecord) -> None:
    destination = _workspace(run_dir) / "inbox" / action.checkpoint_id / "operations" / action.action_id
    _assert_run_path_not_symlinked(run_dir, destination, label="operation workspace projection")
    destination_relative = destination.relative_to(_workspace(run_dir))
    visible_artifacts = tuple(artifact for artifact in action.artifacts if artifact.workspace_path is not None)
    if not visible_artifacts:
        raise EvidenceLifecycleError("completed operation has no model-visible artifacts")
    expected = {
        Path(artifact.workspace_path).relative_to(destination_relative).as_posix(): artifact.sha256
        for artifact in visible_artifacts
        if artifact.workspace_path is not None
    }
    if destination.exists():
        actual = _artifact_inventory(run_dir, destination)
        if actual != expected:
            raise EvidenceLifecycleError("operation workspace projection conflicts with canonical artifacts")
        return

    staging_root = _workspace(run_dir) / ".staging" / "lifecycle_operations" / action.action_id
    staging_projection = staging_root / "projection"
    _assert_run_path_not_symlinked(run_dir, staging_root, label="operation workspace staging directory")
    if staging_root.exists():
        _discard_operation_staging(staging_root)
    try:
        staging_projection.mkdir(parents=True)
        _require_operation_directory(run_dir, staging_projection, label="operation workspace staging projection")
        for artifact in visible_artifacts:
            if artifact.workspace_path is None:  # pragma: no cover - filtered above
                continue
            relative = Path(artifact.workspace_path).relative_to(destination_relative)
            canonical = run_dir / artifact.path
            _require_operation_file(run_dir, canonical, label="canonical operation artifact")
            if _sha256(canonical) != artifact.sha256:
                raise EvidenceLifecycleError("canonical operation artifact does not match the action record")
            projected = staging_projection / relative
            _assert_run_path_not_symlinked(run_dir, projected, label="operation staged workspace artifact")
            projected.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(canonical, projected)
        if _artifact_inventory(run_dir, staging_projection) != expected:
            raise EvidenceLifecycleError("operation projection does not match the declared visible artifacts")
        fsync_tree(staging_projection)
        mkdir_durable(destination.parent)
        _assert_run_path_not_symlinked(run_dir, destination, label="operation workspace projection")
        staging_projection.replace(destination)
        fsync_directory(destination.parent)
    finally:
        _discard_operation_staging(staging_root)


def _rejection_projection_sha256(operation_id: str, supplied_visible_source_sha256: str) -> str:
    payload = json.dumps(
        {
            "schema_version": "1",
            "operation_id": operation_id,
            "supplied_visible_source_sha256": supplied_visible_source_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _validate_lifecycle_operation_ledger(run_dir: Path, state: EvidenceLifecycleRunState) -> None:
    recorded = _ledger_entries_by_summary_id(
        _ledger_path(run_dir),
        stage="lifecycle_operation",
        identity_field="action_id",
        label="lifecycle operation",
    )
    actions = _all_operation_actions(state)
    expected = {action.action_id for action in actions}
    if set(recorded) != expected:
        actual = set(recorded)
        missing = ", ".join(sorted(expected - actual)) or "none"
        unexpected = ", ".join(sorted(actual - expected)) or "none"
        raise EvidenceLifecycleError(
            "lifecycle operation ledger inventory does not match lifecycle state: "
            f"missing={missing}; unexpected={unexpected}"
        )
    for action in actions:
        _assert_ledger_entry_matches(
            recorded[action.action_id],
            process_id=state.lifecycle_id,
            status=action.outcome.value,
            summary=action.model_dump(mode="json"),
            artifact_refs=[artifact.path for artifact in action.artifacts],
            label="lifecycle operation",
        )


def _sync_lifecycle_operation_ledger(run_dir: Path, state: EvidenceLifecycleRunState) -> None:
    ledger_path = _ledger_path(run_dir)
    recorded = _ledger_entries_by_summary_id(
        ledger_path,
        stage="lifecycle_operation",
        identity_field="action_id",
        label="lifecycle operation",
    )
    actions = _all_operation_actions(state)
    expected_ids = {action.action_id for action in actions}
    unexpected = sorted(set(recorded) - expected_ids)
    if unexpected:
        raise EvidenceLifecycleError(
            "lifecycle operation ledger contains entries absent from state: " + ", ".join(unexpected)
        )
    for action in actions:
        summary = action.model_dump(mode="json")
        artifact_refs = [artifact.path for artifact in action.artifacts]
        existing = recorded.get(action.action_id)
        if existing is not None:
            _assert_ledger_entry_matches(
                existing,
                process_id=state.lifecycle_id,
                status=action.outcome.value,
                summary=summary,
                artifact_refs=artifact_refs,
                label="lifecycle operation",
            )
            continue
        append_ledger_entry(
            ledger_path,
            process_id=state.lifecycle_id,
            stage="lifecycle_operation",
            status=action.outcome.value,
            summary=summary,
            artifact_refs=artifact_refs,
        )


def _inherit_lifecycle_operation_transactions(
    parent_run: Path,
    branch_run: Path,
    state: EvidenceLifecycleRunState,
) -> None:
    inherited_actions = [action for action in _all_operation_actions(state) if action.inherited_from_parent]
    if not inherited_actions:
        return
    destination_root = branch_run / "lifecycle_operations"
    destination_root.mkdir(parents=True, exist_ok=True)
    for action in inherited_actions:
        source = parent_run / "lifecycle_operations" / action.action_id
        destination = destination_root / action.action_id
        _copy_release(source, destination)
        _write_json(destination / "action.json", action.model_dump(mode="json"))
        _write_json(
            destination / "committed.json",
            {"action_id": action.action_id, "status": "committed"},
        )
    fsync_tree(destination_root)


def _read_operation_transaction_action(
    run_dir: Path,
    transaction: Path,
) -> LifecycleOperationActionRecord:
    _require_operation_directory(run_dir, transaction, label="operation transaction directory")
    action_path = transaction / "action.json"
    _require_operation_file(run_dir, action_path, label="operation action metadata")
    try:
        return LifecycleOperationActionRecord.model_validate(_read_json(action_path))
    except ValidationError as exc:
        raise EvidenceLifecycleError(f"invalid lifecycle operation action: {action_path}") from exc


def _validate_operation_transaction(
    run_dir: Path,
    transaction: Path,
    action: LifecycleOperationActionRecord,
    prior_actions: list[LifecycleOperationActionRecord],
) -> str:
    _require_operation_directory(run_dir, transaction, label="operation transaction directory")
    request_path = transaction / "request.json"
    _require_operation_file(run_dir, request_path, label="operation request metadata")
    request = _read_json(request_path)
    expected_request = {
        "schema_version": "1",
        "action_id": action.action_id,
        "checkpoint_id": action.requested_checkpoint_id,
        "operation_id": action.operation_id,
        "visible_source_state_sha256": request.get("visible_source_state_sha256"),
        "reason": action.reason,
    }
    if request != expected_request or _sha256(request_path) != action.request_sha256:
        raise EvidenceLifecycleError("operation request does not match its action")
    supplied_source_sha256 = request.get("visible_source_state_sha256")
    if (
        not isinstance(supplied_source_sha256, str)
        or len(supplied_source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in supplied_source_sha256)
    ):
        raise EvidenceLifecycleError("operation request visible source identity is invalid")
    if action.outcome == LifecycleOperationOutcome.REJECTED:
        if action.input_projection_sha256 != _rejection_projection_sha256(
            action.operation_id,
            supplied_source_sha256,
        ):
            raise EvidenceLifecycleError("rejected operation projection does not match its request")
    elif supplied_source_sha256 != action.visible_source_state_before_sha256:
        raise EvidenceLifecycleError("operation request does not match its source-before identity")

    prior_ids = {prior.action_id for prior in prior_actions}
    if not set(action.prerequisite_action_ids).issubset(prior_ids):
        raise EvidenceLifecycleError("operation prerequisites do not precede their action")
    result_manifest = transaction / "result-manifest.json"
    _assert_run_path_not_symlinked(run_dir, result_manifest, label="operation result metadata")
    if action.outcome == LifecycleOperationOutcome.COMPLETED:
        _require_operation_file(run_dir, result_manifest, label="operation result metadata")
        if _sha256(result_manifest) != action.result_manifest_sha256:
            raise EvidenceLifecycleError("operation result manifest hash mismatch")
        prefix = Path("lifecycle_operations") / action.action_id / "artifacts"
        artifact_hashes: dict[str, str] = {}
        for artifact in action.artifacts:
            canonical_relative = Path(artifact.path)
            try:
                relative = canonical_relative.relative_to(prefix)
            except ValueError as exc:
                raise EvidenceLifecycleError("completed operation artifact belongs to another transaction") from exc
            canonical = run_dir / canonical_relative
            _require_operation_file(run_dir, canonical, label="canonical operation artifact")
            if _sha256(canonical) != artifact.sha256:
                raise EvidenceLifecycleError("operation artifact hash mismatch")
            artifact_hashes[relative.as_posix()] = artifact.sha256
        expected_manifest = {
            "schema_version": "1",
            "action_id": action.action_id,
            "operation_id": action.operation_id,
            "input_projection_sha256": action.input_projection_sha256,
            "physical_source_state_sha256": action.physical_source_state_after_sha256,
            "visible_source_state_sha256": action.visible_source_state_after_sha256,
            "prerequisite_action_ids": list(action.prerequisite_action_ids),
            "artifact_sha256": artifact_hashes,
        }
        if _read_json(result_manifest) != expected_manifest:
            raise EvidenceLifecycleError("operation result manifest does not match its action")
        if _artifact_inventory(run_dir, transaction / "artifacts") != artifact_hashes:
            raise EvidenceLifecycleError("operation artifact inventory does not match its action")
    elif action.outcome == LifecycleOperationOutcome.ALREADY_CURRENT:
        if result_manifest.exists():
            raise EvidenceLifecycleError("already-current operation has unexpected result metadata")
        retained = next(
            (prior for prior in prior_actions if prior.action_id == action.retained_from_action_id),
            None,
        )
        if retained is None or retained.outcome != LifecycleOperationOutcome.COMPLETED:
            raise EvidenceLifecycleError("already-current operation does not retain a prior completed action")
        if action.artifacts != retained.artifacts:
            raise EvidenceLifecycleError("already-current operation artifacts do not match their retained action")
    else:
        if result_manifest.exists():
            raise EvidenceLifecycleError("rejected operation has unexpected result metadata")
        if action.prerequisite_action_ids:
            raise EvidenceLifecycleError("rejected operation cannot record prerequisite actions")
    return supplied_source_sha256


def _validate_operation_replay(
    spec: EvidenceLifecycleSpec,
    resolver: LifecycleOperationResolver,
    action: LifecycleOperationActionRecord,
    prior_actions: list[LifecycleOperationActionRecord],
    *,
    budget_before: int,
    supplied_source_sha256: str,
) -> None:
    """Replay the public decision tree and resolver plan for one stored action."""
    checkpoint = _checkpoint(spec, action.checkpoint_id)

    def require_rejection(
        rejection: LifecycleOperationRejection,
        *,
        operation_kind: str,
        membership_error: str | None = None,
    ) -> None:
        if action.outcome != LifecycleOperationOutcome.REJECTED or action.rejection != rejection:
            raise EvidenceLifecycleError(
                membership_error or "operation replay rejection reason does not match the live decision"
            )
        if action.operation_kind != operation_kind:
            raise EvidenceLifecycleError("operation replay kind does not match the public catalogue")

    if action.requested_checkpoint_id != action.checkpoint_id:
        require_rejection(
            LifecycleOperationRejection.INACTIVE_CHECKPOINT,
            operation_kind="unknown",
        )
        return
    conditional = checkpoint.conditional_operations
    if conditional is None:
        require_rejection(
            LifecycleOperationRejection.NOT_SUPPORTED,
            operation_kind="unknown",
        )
        return
    operation = next((item for item in conditional.operations if item.operation_id == action.operation_id), None)
    if operation is None:
        require_rejection(
            LifecycleOperationRejection.UNKNOWN_OPERATION,
            operation_kind="unknown",
            membership_error="operation replay action is absent from the public catalogue",
        )
        return
    if action.operation_kind != operation.kind:
        raise EvidenceLifecycleError("operation replay kind does not match the public catalogue")

    source_before = resolver.current_source(prior_actions)
    if supplied_source_sha256 != source_before.visible_source_state_sha256:
        require_rejection(
            LifecycleOperationRejection.STALE_VISIBLE_SOURCE,
            operation_kind=operation.kind,
        )
        return
    if not set(operation.prerequisite_operation_ids).issubset(_completed_operation_ids(prior_actions)):
        require_rejection(
            LifecycleOperationRejection.PREREQUISITES_INCOMPLETE,
            operation_kind=operation.kind,
        )
        return
    try:
        plan = resolver.plan(operation, prior_actions)
    except LifecycleOperationPrerequisiteError:
        require_rejection(
            LifecycleOperationRejection.PREREQUISITES_INCOMPLETE,
            operation_kind=operation.kind,
        )
        return
    if (
        action.visible_source_state_before_sha256 != plan.source_before.visible_source_state_sha256
        or action.physical_source_state_before_sha256 != plan.source_before.physical_source_state_sha256
    ):
        raise EvidenceLifecycleError("operation replay source before does not match the live resolver plan")
    current = current_lifecycle_operation_action(prior_actions, plan)
    if current is not None:
        expected_outcome = LifecycleOperationOutcome.ALREADY_CURRENT
        expected_disposition = LifecycleOperationDisposition.REUSED
    elif budget_before == 0:
        require_rejection(
            LifecycleOperationRejection.BUDGET_EXHAUSTED,
            operation_kind=operation.kind,
        )
        return
    else:
        expected_outcome = LifecycleOperationOutcome.COMPLETED
        expected_disposition = plan.disposition

    if action.outcome != expected_outcome:
        raise EvidenceLifecycleError("operation replay currentness does not match the live resolver plan")
    if action.disposition != expected_disposition:
        raise EvidenceLifecycleError("operation replay disposition does not match the live resolver plan")
    if action.input_projection_sha256 != plan.input_projection_sha256:
        raise EvidenceLifecycleError("operation replay input projection does not match the live resolver plan")
    if action.prerequisite_action_ids != plan.prerequisite_action_ids:
        raise EvidenceLifecycleError("operation replay prerequisites do not match the live resolver plan")
    if (
        action.visible_source_state_after_sha256 != plan.source_after.visible_source_state_sha256
        or action.physical_source_state_after_sha256 != plan.source_after.physical_source_state_sha256
    ):
        raise EvidenceLifecycleError("operation replay source after does not match the live resolver plan")
    if expected_outcome == LifecycleOperationOutcome.ALREADY_CURRENT:
        if current is None or action.retained_from_action_id != current.action_id:
            raise EvidenceLifecycleError("operation replay currentness does not match the retained result")
        return
    if action.retained_from_action_id is not None:
        raise EvidenceLifecycleError("operation replay completed action cannot retain a prior result")

    prefix = Path("inbox") / action.checkpoint_id / "operations" / action.action_id
    visible_paths: set[str] = set()
    for artifact in action.artifacts:
        if artifact.workspace_path is None:
            continue
        try:
            visible_paths.add(Path(artifact.workspace_path).relative_to(prefix).as_posix())
        except ValueError as exc:
            raise EvidenceLifecycleError("operation replay workspace artifacts do not belong to their action") from exc
    if visible_paths != set(plan.model_visible_artifact_paths):
        raise EvidenceLifecycleError("operation replay visible artifacts do not match the live resolver plan")


def _validate_operation_owner(
    state: EvidenceLifecycleRunState,
    action: LifecycleOperationActionRecord,
) -> CheckpointAttemptStatus:
    checkpoint = state.checkpoint(action.checkpoint_id)
    owner = next(
        (
            attempt
            for attempt in checkpoint.attempts
            if attempt.attempt_id == action.attempt_id and attempt.session_id == action.session_id
        ),
        None,
    )
    if owner is None:
        raise EvidenceLifecycleError("operation recovery action has no matching owner attempt")
    if owner.inherited_from_parent != action.inherited_from_parent:
        raise EvidenceLifecycleError("operation recovery owner attempt inheritance does not match its action")
    return owner.status


def _validate_operation_state_transition(
    state: EvidenceLifecycleRunState,
    resolver: LifecycleOperationResolver,
    action: LifecycleOperationActionRecord,
    prior_actions: list[LifecycleOperationActionRecord],
    *,
    budget_before: int,
) -> None:
    source_before = resolver.current_source(prior_actions)
    if (
        action.visible_source_state_before_sha256 != source_before.visible_source_state_sha256
        or action.physical_source_state_before_sha256 != source_before.physical_source_state_sha256
    ):
        raise EvidenceLifecycleError("operation recovery source-before identity does not match")
    expected_pre = lifecycle_operation_state_sha256(
        state,
        checkpoint_id=action.checkpoint_id,
        source=source_before,
        operation_budget_remaining=budget_before,
        actions=prior_actions,
    )
    if action.pre_action_state_sha256 != expected_pre:
        raise EvidenceLifecycleError("operation recovery pre-state hash does not match")

    source_after = resolver.current_source([*prior_actions, action])
    if (
        action.visible_source_state_after_sha256 != source_after.visible_source_state_sha256
        or action.physical_source_state_after_sha256 != source_after.physical_source_state_sha256
    ):
        raise EvidenceLifecycleError("operation recovery source-after identity does not match")
    expected_post = lifecycle_operation_state_sha256(
        state,
        checkpoint_id=action.checkpoint_id,
        source=source_after,
        operation_budget_remaining=action.budget_after,
        actions=[*prior_actions, action],
    )
    if action.post_action_state_sha256 != expected_post:
        raise EvidenceLifecycleError("operation recovery post-state hash does not match")


def _validate_operation_resolver_action(
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
    resolver: LifecycleOperationResolver,
    action: LifecycleOperationActionRecord,
    prior_actions: list[LifecycleOperationActionRecord],
    *,
    budget_before: int,
    supplied_source_sha256: str,
) -> CheckpointAttemptStatus:
    expected_budget_consumed = 1 if action.outcome == LifecycleOperationOutcome.COMPLETED else 0
    if (
        action.budget_before != budget_before
        or action.budget_consumed != expected_budget_consumed
        or action.budget_after != budget_before - expected_budget_consumed
    ):
        raise EvidenceLifecycleError("operation resolver replay budget does not match the live decision")
    owner_status = _validate_operation_owner(state, action)
    _validate_operation_replay(
        spec,
        resolver,
        action,
        prior_actions,
        budget_before=budget_before,
        supplied_source_sha256=supplied_source_sha256,
    )
    _validate_operation_state_transition(
        state,
        resolver,
        action,
        prior_actions,
        budget_before=budget_before,
    )
    return owner_status


def _recover_lifecycle_operation_transactions(
    package_dir: Path,
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
    state: EvidenceLifecycleRunState,
) -> None:
    root = run_dir / "lifecycle_operations"
    state_actions = _all_operation_actions(state)
    _assert_run_path_not_symlinked(run_dir, root, label="operation transaction root")
    if not root.exists():
        if state_actions:
            raise EvidenceLifecycleError("operation state is missing canonical transactions")
        return
    _require_operation_directory(run_dir, root, label="operation transaction root")
    entries = sorted(root.iterdir())
    for entry in entries:
        _assert_run_path_not_symlinked(run_dir, entry, label="operation transaction entry")
    for staging in (entry for entry in entries if entry.name.startswith(".") and ".tmp-" in entry.name):
        _require_operation_directory(run_dir, staging, label="operation staging directory")
        _discard_operation_staging(staging)
    transactions: list[Path] = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        _require_operation_directory(run_dir, entry, label="operation transaction directory")
        transactions.append(entry)
    state_by_id = {action.action_id: action for action in state_actions}
    recovered_actions: list[LifecycleOperationActionRecord] = []
    remaining_budgets = {checkpoint.checkpoint_id: checkpoint.operation_budget for checkpoint in state.checkpoint_runs}
    changed = False
    pending_commits: list[tuple[Path, str]] = []
    completed_actions: list[LifecycleOperationActionRecord] = []
    resolver = _resolver_for_package(package_dir, run_dir)
    for expected_sequence, transaction in enumerate(transactions, start=1):
        action = _read_operation_transaction_action(run_dir, transaction)
        if action.sequence != expected_sequence or action.action_id != f"operation-{expected_sequence:06d}":
            raise EvidenceLifecycleError("operation recovery sequence is not contiguous")
        if action.action_id != transaction.name:
            raise EvidenceLifecycleError("operation action id does not match its transaction")
        existing = state_by_id.get(action.action_id)
        if existing is not None and existing != action:
            raise EvidenceLifecycleError("operation transaction action does not match lifecycle state")

        try:
            checkpoint_run = state.checkpoint(action.checkpoint_id)
        except KeyError as exc:
            raise EvidenceLifecycleError("operation action checkpoint is not present in lifecycle state") from exc
        budget_before = remaining_budgets[action.checkpoint_id]
        if action.budget_before != budget_before:
            raise EvidenceLifecycleError("operation recovery budget does not match prior actions")
        supplied_source_sha256 = _validate_operation_transaction(
            run_dir,
            transaction,
            action,
            recovered_actions,
        )
        owner_status = _validate_operation_resolver_action(
            state,
            spec,
            resolver,
            action,
            recovered_actions,
            budget_before=budget_before,
            supplied_source_sha256=supplied_source_sha256,
        )
        remaining_budgets[action.checkpoint_id] = action.budget_after

        if existing is None:
            if (
                state.active_checkpoint_id != action.checkpoint_id
                or owner_status != CheckpointAttemptStatus.ACTIVE
                or checkpoint_run.operation_budget_remaining != action.budget_before
            ):
                raise EvidenceLifecycleError("operation recovery action has no active lifecycle owner")
            checkpoint_run.operation_budget_remaining = action.budget_after
            checkpoint_run.operation_actions.append(action)
            _append_transition(
                state,
                kind=LifecycleTransitionKind.OPERATION,
                from_checkpoint_id=action.checkpoint_id,
                to_checkpoint_id=action.checkpoint_id,
                reason=f"Lifecycle operation {action.outcome.value}.",
            )
            state_by_id[action.action_id] = action
            changed = True
        recovered_actions.append(action)
        if action.outcome == LifecycleOperationOutcome.COMPLETED:
            completed_actions.append(action)

        committed = transaction / "committed.json"
        _assert_run_path_not_symlinked(run_dir, committed, label="operation commit metadata")
        if not committed.exists():
            pending_commits.append((committed, action.action_id))
        else:
            _require_operation_file(run_dir, committed, label="operation commit metadata")
        if committed.exists() and _read_json(committed) != {
            "action_id": action.action_id,
            "status": "committed",
        }:
            raise EvidenceLifecycleError("operation transaction commit marker is invalid")

    missing = sorted(set(state_by_id) - {transaction.name for transaction in transactions})
    if missing:
        raise EvidenceLifecycleError(f"operation state is missing canonical transactions: {', '.join(missing)}")
    for action in completed_actions:
        _materialize_operation_projection(run_dir, action)
    if changed:
        validate_lifecycle_operation_run_state(state, spec)
        _write_state(run_dir, state)
        _sync_transition_ledger(run_dir, state)
        _sync_lifecycle_operation_ledger(run_dir, state)
    _write_lifecycle_operation_catalog(package_dir, run_dir, spec, state)
    _sync_lifecycle_operation_ledger(run_dir, state)
    for committed, action_id in pending_commits:
        _assert_run_path_not_symlinked(run_dir, committed, label="operation commit metadata")
        _write_json_atomic_durable(
            committed,
            {"action_id": action_id, "status": "committed"},
        )
    if pending_commits:
        fsync_directory(root)
