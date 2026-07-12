# ABOUTME: Persists conditional-evidence transactions, workspace projections, recovery, and ledgers.
# ABOUTME: Provides the shared durable file primitives used by the lifecycle executor.

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import ValidationError

from aec_bench.ledger.durability import fsync_directory, fsync_tree, mkdir_durable
from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointRunRecord,
    CheckpointRunStatus,
    EvidenceLifecycleRunState,
    EvidenceRequestActionRecord,
    EvidenceRequestOutcome,
    EvidenceRequestRejection,
    LifecycleTransitionKind,
    ReleasedEvidenceArtifact,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    EvidenceLifecycleError,
    EvidenceRequestResolution,
    EvidenceRequestResolutionManifest,
    _append_transition,
    _checkpoint,
    _evidence_request_catalog,
    _evidence_request_state_sha256,
    _validate_evidence_request_state_contract,
)
from aec_bench.meta_harness.ledger import append_ledger_entry, read_ledger
from aec_bench.task_world_templates.contracts import EvidenceCheckpointSpec, EvidenceLifecycleSpec


def _load_evidence_request_resolutions(
    package_dir: Path,
    spec: EvidenceLifecycleSpec,
) -> dict[tuple[str, str], EvidenceRequestResolution]:
    expected = {
        (checkpoint.checkpoint_id, request.request_id)
        for checkpoint in spec.checkpoints
        if checkpoint.conditional_evidence is not None
        for request in checkpoint.conditional_evidence.requests
    }
    if not expected:
        return {}

    manifest_path = package_dir / "hidden" / "evidence-request-resolutions.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise EvidenceLifecycleError(f"evidence request resolution manifest not found: {manifest_path}")
    try:
        manifest = EvidenceRequestResolutionManifest.model_validate(_read_json(manifest_path))
    except ValidationError as exc:
        raise EvidenceLifecycleError(f"invalid evidence request resolution manifest: {manifest_path}") from exc
    if manifest.lifecycle_id != spec.lifecycle_id:
        raise EvidenceLifecycleError("evidence request resolution manifest lifecycle does not match")

    resolutions = {(resolution.checkpoint_id, resolution.request_id): resolution for resolution in manifest.resolutions}
    if set(resolutions) != expected:
        raise EvidenceLifecycleError("evidence request resolutions do not match the public request catalogue")
    for resolution in resolutions.values():
        source = package_dir / resolution.source_path
        if not source.is_dir() or source.is_symlink():
            raise EvidenceLifecycleError(f"evidence request source not found: {source}")
    return resolutions


def _write_evidence_request_catalog(
    run_dir: Path,
    checkpoint: EvidenceCheckpointSpec,
    checkpoint_run: CheckpointRunRecord,
) -> None:
    catalog = _evidence_request_catalog(checkpoint, checkpoint_run)
    if catalog is None:
        return
    destination = _workspace(run_dir) / "checkpoints" / checkpoint.checkpoint_id / "evidence-requests.json"
    if checkpoint_run.status == CheckpointRunStatus.PENDING:
        if destination.exists():
            raise EvidenceLifecycleError("pending checkpoint cannot publish an evidence request catalogue")
        return
    _write_json_atomic_durable(destination, catalog)


def _record_evidence_request_action(
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
    state: EvidenceLifecycleRunState,
    *,
    requested_checkpoint_id: str,
    request_id: str,
    reason: str,
    session_id: str,
    outcome: EvidenceRequestOutcome,
    rejection: EvidenceRequestRejection | None = None,
    released_artifacts: tuple[ReleasedEvidenceArtifact, ...] = (),
    release_source: Path | None = None,
) -> dict[str, Any]:
    active_checkpoint_id = state.active_checkpoint_id
    if active_checkpoint_id is None:
        raise EvidenceLifecycleError("no checkpoint is active")
    checkpoint_run = state.checkpoint(active_checkpoint_id)
    attempt = checkpoint_run.active_attempt
    if attempt is None or attempt.session_id != session_id:
        raise EvidenceLifecycleError("evidence request action has no matching active attempt")

    sequence = 1 + sum(len(item.evidence_request_actions) for item in state.checkpoint_runs)
    action_id = f"evidence-request-{sequence:06d}"
    transaction_root = run_dir / "evidence_requests"
    mkdir_durable(transaction_root)
    staging = Path(tempfile.mkdtemp(prefix=f".{action_id}.tmp-", dir=transaction_root))
    transaction = transaction_root / action_id
    if transaction.exists():
        shutil.rmtree(staging, ignore_errors=True)
        raise EvidenceLifecycleError(f"evidence request transaction already exists: {action_id}")

    if outcome == EvidenceRequestOutcome.RELEASED:
        if release_source is None or released_artifacts:
            shutil.rmtree(staging, ignore_errors=True)
            raise EvidenceLifecycleError("released evidence request requires one canonical source")
        artifact_root = staging / "artifacts"
        released_files = _copy_release(release_source, artifact_root)
        if not released_files:
            shutil.rmtree(staging, ignore_errors=True)
            raise EvidenceLifecycleError("evidence request source must contain at least one file")
        destination = _workspace(run_dir) / "inbox" / active_checkpoint_id / "requests" / request_id
        released_artifacts = tuple(
            ReleasedEvidenceArtifact(
                path=(Path("evidence_requests") / action_id / "artifacts" / relative).as_posix(),
                workspace_path=(destination / relative).relative_to(_workspace(run_dir)).as_posix(),
                sha256=_sha256(artifact_root / relative),
            )
            for relative in released_files
        )
    elif release_source is not None:
        shutil.rmtree(staging, ignore_errors=True)
        raise EvidenceLifecycleError("only released evidence requests may publish canonical artifacts")

    budget_before = checkpoint_run.evidence_request_budget_remaining
    budget_consumed: Literal[0, 1] = 1 if outcome == EvidenceRequestOutcome.RELEASED else 0
    pre_action_state_sha256 = _evidence_request_state_sha256(state, active_checkpoint_id)
    checkpoint_run.evidence_request_budget_remaining -= budget_consumed
    action = EvidenceRequestActionRecord(
        action_id=action_id,
        sequence=sequence,
        checkpoint_id=active_checkpoint_id,
        requested_checkpoint_id=requested_checkpoint_id,
        request_id=request_id,
        reason=reason,
        session_id=session_id,
        attempt_id=attempt.attempt_id,
        outcome=outcome,
        rejection=rejection,
        pre_action_state_sha256=pre_action_state_sha256,
        post_action_state_sha256="0" * 64,
        released_artifacts=released_artifacts,
        budget_before=budget_before,
        budget_consumed=budget_consumed,
        budget_after=checkpoint_run.evidence_request_budget_remaining,
    )
    checkpoint_run.evidence_request_actions.append(action)
    action.post_action_state_sha256 = _evidence_request_state_sha256(state, active_checkpoint_id)
    try:
        _write_json(staging / "action.json", action.model_dump(mode="json"))
        fsync_tree(staging)
        staging.replace(transaction)
        fsync_directory(transaction_root)
        if outcome == EvidenceRequestOutcome.RELEASED:
            _materialize_evidence_request_projection(run_dir, action)
        _write_evidence_request_catalog(
            run_dir,
            _checkpoint(spec, active_checkpoint_id),
            checkpoint_run,
        )
        _append_transition(
            state,
            kind=LifecycleTransitionKind.EVIDENCE_REQUEST,
            from_checkpoint_id=active_checkpoint_id,
            to_checkpoint_id=active_checkpoint_id,
            reason=f"Conditional evidence request {outcome.value}.",
        )
        _write_state(run_dir, state)
        _sync_transition_ledger(run_dir, state)
        _sync_evidence_request_ledger(run_dir, state)
        _write_json_atomic_durable(
            transaction / "committed.json",
            {"action_id": action_id, "status": "committed"},
        )
        fsync_tree(transaction)
        fsync_directory(transaction_root)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return action.model_dump(mode="json")


def _assert_evidence_request_artifacts_unchanged(
    run_dir: Path,
    action: EvidenceRequestActionRecord,
) -> None:
    first = action.released_artifacts[0]
    canonical_path = PurePosixPath(first.path)
    canonical_prefix = PurePosixPath(*canonical_path.parts[:3])
    workspace_prefix = PurePosixPath("inbox") / action.checkpoint_id / "requests" / action.request_id
    expected_canonical = {
        PurePosixPath(artifact.path).relative_to(canonical_prefix).as_posix(): artifact.sha256
        for artifact in action.released_artifacts
    }
    expected_workspace = {
        PurePosixPath(artifact.workspace_path).relative_to(workspace_prefix).as_posix(): artifact.sha256
        for artifact in action.released_artifacts
    }
    if len(expected_canonical) != len(action.released_artifacts) or len(expected_workspace) != len(
        action.released_artifacts
    ):
        raise EvidenceLifecycleError("released evidence request artifact paths are not unique")

    canonical_root = run_dir / canonical_prefix
    workspace_root = _workspace(run_dir) / workspace_prefix
    actual_canonical = _artifact_tree_inventory(canonical_root, confined_to=run_dir)
    actual_workspace = _artifact_tree_inventory(
        workspace_root,
        confined_to=_workspace(run_dir),
    )
    if set(actual_canonical) != set(expected_canonical) or set(actual_workspace) != set(expected_workspace):
        raise EvidenceLifecycleError(f"released evidence request artifact file set changed: {action.action_id}")
    for artifact in action.released_artifacts:
        canonical_relative = PurePosixPath(artifact.path).relative_to(canonical_prefix).as_posix()
        workspace_relative = PurePosixPath(artifact.workspace_path).relative_to(workspace_prefix).as_posix()
        if (
            actual_canonical[canonical_relative] != artifact.sha256
            or actual_workspace[workspace_relative] != artifact.sha256
        ):
            raise EvidenceLifecycleError(f"released evidence request artifact changed: {artifact.path}")


def _artifact_tree_inventory(root: Path, *, confined_to: Path) -> dict[str, str]:
    try:
        relative_root = root.relative_to(confined_to)
    except ValueError as exc:
        raise EvidenceLifecycleError(f"evidence request artifact tree escapes its run: {root}") from exc
    cursor = confined_to
    for part in relative_root.parts:
        cursor /= part
        if cursor.is_symlink():
            raise EvidenceLifecycleError(f"evidence request artifact tree may not contain symlinks: {cursor}")
    if not root.is_dir():
        raise EvidenceLifecycleError(f"evidence request artifact tree is missing: {root}")

    inventory: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise EvidenceLifecycleError(f"evidence request artifact tree may not contain symlinks: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise EvidenceLifecycleError(f"evidence request artifact tree contains a non-file: {path}")
        inventory[path.relative_to(root).as_posix()] = _sha256(path)
    return inventory


def _recover_evidence_request_transactions(
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
    state: EvidenceLifecycleRunState,
) -> None:
    transaction_root = run_dir / "evidence_requests"
    actions = [action for checkpoint in state.checkpoint_runs for action in checkpoint.evidence_request_actions]
    if not transaction_root.exists():
        if actions:
            raise EvidenceLifecycleError("evidence request state is missing its canonical transactions")
        return

    for staging in transaction_root.glob(".*.tmp-*"):
        if staging.is_dir():
            shutil.rmtree(staging)

    by_id = {action.action_id: action for action in actions}
    changed = False
    pending_commits: list[tuple[Path, str]] = []
    transactions = sorted(
        path for path in transaction_root.iterdir() if path.is_dir() and not path.name.startswith(".")
    )
    for transaction in transactions:
        action_path = transaction / "action.json"
        if not action_path.is_file() or action_path.is_symlink():
            raise EvidenceLifecycleError(f"invalid evidence request transaction: {transaction}")
        try:
            action = EvidenceRequestActionRecord.model_validate(_read_json(action_path))
        except ValidationError as exc:
            raise EvidenceLifecycleError(f"invalid evidence request action: {action_path}") from exc
        if action.action_id != transaction.name:
            raise EvidenceLifecycleError("evidence request action id does not match its transaction")

        existing = by_id.get(action.action_id)
        if existing is None:
            expected_sequence = 1 + sum(
                len(checkpoint.evidence_request_actions) for checkpoint in state.checkpoint_runs
            )
            if action.sequence != expected_sequence:
                raise EvidenceLifecycleError("evidence request recovery sequence is not contiguous")
            checkpoint_run = state.checkpoint(action.checkpoint_id)
            owner = next(
                (
                    attempt
                    for attempt in checkpoint_run.attempts
                    if attempt.attempt_id == action.attempt_id and attempt.session_id == action.session_id
                ),
                None,
            )
            if owner is None:
                raise EvidenceLifecycleError("evidence request action owner is not present in checkpoint attempts")
            if checkpoint_run.evidence_request_budget_remaining != action.budget_before:
                raise EvidenceLifecycleError("evidence request recovery budget does not match state")
            if _evidence_request_state_sha256(state, action.checkpoint_id) != action.pre_action_state_sha256:
                raise EvidenceLifecycleError("evidence request recovery pre-state hash does not match")

            if action.outcome == EvidenceRequestOutcome.RELEASED:
                _materialize_evidence_request_projection(run_dir, action)
            elif action.outcome == EvidenceRequestOutcome.ALREADY_RELEASED:
                _assert_evidence_request_artifacts_unchanged(run_dir, action)
            checkpoint_run.evidence_request_budget_remaining = action.budget_after
            checkpoint_run.evidence_request_actions.append(action)
            if _evidence_request_state_sha256(state, action.checkpoint_id) != action.post_action_state_sha256:
                raise EvidenceLifecycleError("evidence request recovery post-state hash does not match")
            _append_transition(
                state,
                kind=LifecycleTransitionKind.EVIDENCE_REQUEST,
                from_checkpoint_id=action.checkpoint_id,
                to_checkpoint_id=action.checkpoint_id,
                reason=f"Conditional evidence request {action.outcome.value}.",
            )
            by_id[action.action_id] = action
            changed = True
        elif existing.model_dump(mode="json") != action.model_dump(mode="json"):
            raise EvidenceLifecycleError("evidence request state does not match its canonical transaction")

        if action.outcome == EvidenceRequestOutcome.RELEASED:
            _materialize_evidence_request_projection(run_dir, action)
        elif action.outcome == EvidenceRequestOutcome.ALREADY_RELEASED:
            _assert_evidence_request_artifacts_unchanged(run_dir, action)
        committed = transaction / "committed.json"
        if not committed.exists():
            pending_commits.append((committed, action.action_id))
        elif committed.is_symlink() or _read_json(committed) != {
            "action_id": action.action_id,
            "status": "committed",
        }:
            raise EvidenceLifecycleError("evidence request transaction commit marker is invalid")

    transaction_ids = {transaction.name for transaction in transactions}
    missing = sorted(set(by_id) - transaction_ids)
    if missing:
        raise EvidenceLifecycleError(f"evidence request state is missing canonical transactions: {', '.join(missing)}")
    if changed:
        _validate_evidence_request_state_contract(state, spec)
        for checkpoint in spec.checkpoints:
            _write_evidence_request_catalog(
                run_dir,
                checkpoint,
                state.checkpoint(checkpoint.checkpoint_id),
            )
        _write_state(run_dir, state)
        _sync_transition_ledger(run_dir, state)
        _sync_evidence_request_ledger(run_dir, state)
    for committed, action_id in pending_commits:
        _write_json_atomic_durable(
            committed,
            {"action_id": action_id, "status": "committed"},
        )
    if pending_commits:
        fsync_directory(transaction_root)


def _materialize_evidence_request_projection(
    run_dir: Path,
    action: EvidenceRequestActionRecord,
) -> None:
    if action.outcome != EvidenceRequestOutcome.RELEASED:
        return
    source = run_dir / "evidence_requests" / action.action_id / "artifacts"
    destination = _workspace(run_dir) / "inbox" / action.checkpoint_id / "requests" / action.request_id
    if destination.exists():
        _assert_evidence_request_artifacts_unchanged(run_dir, action)
        return

    staging_root = _workspace(run_dir) / ".staging" / "evidence_requests" / action.action_id
    staging_release = staging_root / "release"
    if staging_root.exists():
        shutil.rmtree(staging_root)
    try:
        copied = _copy_release(source, staging_release)
        destination_relative = destination.relative_to(_workspace(run_dir))
        expected = [
            Path(artifact.workspace_path).relative_to(destination_relative).as_posix()
            for artifact in action.released_artifacts
        ]
        if copied != expected:
            raise EvidenceLifecycleError("canonical evidence request artifacts do not match the action record")
        fsync_tree(staging_release)
        mkdir_durable(destination.parent)
        staging_release.replace(destination)
        fsync_directory(destination.parent)
        _assert_evidence_request_artifacts_unchanged(run_dir, action)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def _inherit_evidence_request_transactions(
    parent_run: Path,
    branch_run: Path,
    state: EvidenceLifecycleRunState,
) -> None:
    inherited_actions = sorted(
        (
            action
            for checkpoint in state.checkpoint_runs
            for action in checkpoint.evidence_request_actions
            if action.inherited_from_parent
        ),
        key=lambda action: action.sequence,
    )
    if not inherited_actions:
        return
    destination_root = branch_run / "evidence_requests"
    destination_root.mkdir(parents=True, exist_ok=True)
    for action in inherited_actions:
        source = parent_run / "evidence_requests" / action.action_id
        destination = destination_root / action.action_id
        _copy_release(source, destination)
        _write_json(destination / "action.json", action.model_dump(mode="json"))
        _write_json(
            destination / "committed.json",
            {"action_id": action.action_id, "status": "committed"},
        )
    fsync_tree(destination_root)


def _copy_release(source: Path, destination: Path) -> list[str]:
    if not source.is_dir() or source.is_symlink():
        raise EvidenceLifecycleError(f"checkpoint release not found: {source}")
    destination.mkdir(parents=True, exist_ok=False)
    released: list[str] = []
    for source_path in sorted(source.rglob("*")):
        if source_path.is_symlink():
            raise EvidenceLifecycleError(f"checkpoint releases may not contain symlinks: {source_path}")
        relative = source_path.relative_to(source)
        destination_path = destination / relative
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        released.append(relative.as_posix())
    return released


def _copy_file_atomic(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise EvidenceLifecycleError(f"branch source artifact not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copy2(source, temporary)
    temporary.replace(destination)


def _sync_transition_ledger(run_dir: Path, state: EvidenceLifecycleRunState) -> None:
    ledger_path = _ledger_path(run_dir)
    recorded = _ledger_entries_by_summary_id(
        ledger_path,
        stage="lifecycle_transition",
        identity_field="transition_id",
        label="lifecycle transition",
    )
    expected_ids = {transition.transition_id for transition in state.transitions}
    unexpected = sorted(set(recorded) - expected_ids)
    if unexpected:
        raise EvidenceLifecycleError(
            "lifecycle transition ledger contains entries absent from state: " + ", ".join(unexpected)
        )
    for transition in state.transitions:
        summary = transition.model_dump(mode="json")
        existing = recorded.get(transition.transition_id)
        if existing is not None:
            _assert_ledger_entry_matches(
                existing,
                process_id=state.lifecycle_id,
                status=transition.kind.value,
                summary=summary,
                artifact_refs=[],
                label="lifecycle transition",
            )
            continue
        append_ledger_entry(
            ledger_path,
            process_id=state.lifecycle_id,
            stage="lifecycle_transition",
            status=transition.kind.value,
            summary=summary,
            artifact_refs=[],
        )


def _sync_evidence_request_ledger(
    run_dir: Path,
    state: EvidenceLifecycleRunState,
) -> None:
    ledger_path = _ledger_path(run_dir)
    recorded = _ledger_entries_by_summary_id(
        ledger_path,
        stage="evidence_request",
        identity_field="action_id",
        label="evidence request",
    )
    actions = sorted(
        (action for checkpoint in state.checkpoint_runs for action in checkpoint.evidence_request_actions),
        key=lambda action: action.sequence,
    )
    expected_ids = {action.action_id for action in actions}
    unexpected = sorted(set(recorded) - expected_ids)
    if unexpected:
        raise EvidenceLifecycleError(
            f"evidence request ledger contains entries absent from state: {', '.join(unexpected)}"
        )
    for action in actions:
        summary = action.model_dump(mode="json")
        artifact_refs = [artifact.path for artifact in action.released_artifacts]
        existing = recorded.get(action.action_id)
        if existing is not None:
            _assert_ledger_entry_matches(
                existing,
                process_id=state.lifecycle_id,
                status=action.outcome.value,
                summary=summary,
                artifact_refs=artifact_refs,
                label="evidence request",
            )
            continue
        append_ledger_entry(
            ledger_path,
            process_id=state.lifecycle_id,
            stage="evidence_request",
            status=action.outcome.value,
            summary=summary,
            artifact_refs=artifact_refs,
        )


def _ledger_entries_by_summary_id(
    ledger_path: Path,
    *,
    stage: str,
    identity_field: str,
    label: str,
) -> dict[str, dict[str, Any]]:
    recorded: dict[str, dict[str, Any]] = {}
    for entry in read_ledger(ledger_path):
        if entry.get("stage") != stage:
            continue
        summary = entry.get("summary")
        identity = summary.get(identity_field) if isinstance(summary, dict) else None
        if not isinstance(identity, str) or not identity:
            raise EvidenceLifecycleError(f"{label} ledger entry is missing its canonical identity")
        if identity in recorded:
            raise EvidenceLifecycleError(f"{label} ledger contains duplicate entry: {identity}")
        recorded[identity] = entry
    return recorded


def _assert_ledger_entry_matches(
    entry: dict[str, Any],
    *,
    process_id: str,
    status: str,
    summary: dict[str, Any],
    artifact_refs: list[str],
    label: str,
) -> None:
    if (
        entry.get("process_id") != process_id
        or entry.get("status") != status
        or entry.get("summary") != summary
        or entry.get("artifact_refs") != artifact_refs
    ):
        raise EvidenceLifecycleError(f"{label} ledger entry conflicts with canonical state")


def _workspace(run_dir: Path) -> Path:
    return run_dir / "workspace"


def _state_path(run_dir: Path) -> Path:
    return run_dir / "state.json"


def _ledger_path(run_dir: Path) -> Path:
    return run_dir / "lifecycle_ledger.jsonl"


def _write_state(run_dir: Path, state: EvidenceLifecycleRunState) -> None:
    path = _state_path(run_dir)
    _write_json_atomic_durable(path, state.model_dump(mode="json"))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceLifecycleError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise EvidenceLifecycleError(f"JSON artifact must contain an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_json_atomic_durable(path: Path, payload: dict[str, Any]) -> None:
    mkdir_durable(path.parent)
    temporary = path.with_suffix(path.suffix + ".tmp")
    _write_json(temporary, payload)
    descriptor = os.open(temporary, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    temporary.replace(path)
    fsync_directory(path.parent)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
