# ABOUTME: Executes staged evidence lifecycles inside one existing meta-harness task-run boundary.
# ABOUTME: Controls release visibility, checkpoint persistence, tamper checks, and parent-run evidence.

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from aec_bench.ledger.durability import fsync_directory, fsync_tree, mkdir_durable
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleEpisodeContext,
    LifecycleEpisodeEnvironment,
    LifecycleEpisodeEnvironmentFailure,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
    validate_episode_result_identity,
)
from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointAttemptRecord,
    CheckpointAttemptStatus,
    CheckpointRevisitRecord,
    CheckpointRunRecord,
    CheckpointRunStatus,
    EvidenceLifecycleRunState,
    EvidenceRequestOutcome,
    EvidenceRequestRejection,
    LifecycleBranchRecord,
    LifecycleRunStatus,
    LifecycleTransitionKind,
    LifecycleVerificationResult,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    EvidenceLifecycleError as EvidenceLifecycleError,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    EvidenceRequestResolution as EvidenceRequestResolution,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    EvidenceRequestResolutionManifest as EvidenceRequestResolutionManifest,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    _append_transition,
    _branch_action_state_sha256,
    _checkpoint,
    _evidence_request_catalog,
    _validate_evidence_request_state_contract,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    evidence_request_catalog_payload as evidence_request_catalog_payload,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    evidence_request_protocol_identity as evidence_request_protocol_identity,
)
from aec_bench.meta_harness.evidence_request_protocol import (
    validate_evidence_request_run_state as validate_evidence_request_run_state,
)
from aec_bench.meta_harness.evidence_request_store import (
    _assert_evidence_request_artifacts_unchanged,
    _copy_file_atomic,
    _copy_release,
    _inherit_evidence_request_transactions,
    _ledger_path,
    _load_evidence_request_resolutions,
    _read_json,
    _record_evidence_request_action,
    _recover_evidence_request_transactions,
    _sha256,
    _state_path,
    _sync_evidence_request_ledger,
    _sync_transition_ledger,
    _workspace,
    _write_evidence_request_catalog,
    _write_json,
    _write_state,
)
from aec_bench.meta_harness.ledger import append_ledger_entry
from aec_bench.meta_harness.lifecycle_operation_protocol import validate_lifecycle_operation_run_state
from aec_bench.meta_harness.lifecycle_operation_store import (
    _execute_lifecycle_operation_locked,
    _inherit_lifecycle_operation_transactions,
    _recover_lifecycle_operation_transactions,
    _sync_lifecycle_operation_ledger,
    _write_lifecycle_operation_catalog,
)
from aec_bench.task_world_templates.contracts import EvidenceCheckpointSpec, EvidenceLifecycleSpec

LifecycleVerifier = Callable[[Path, Path], dict[str, Any] | LifecycleVerificationResult]


class LifecycleEpisodeExecutionError(EvidenceLifecycleError):
    """Raised when an environment returns a durable failed episode result."""


def load_evidence_lifecycle_spec(package_dir: Path) -> EvidenceLifecycleSpec:
    """Load and validate one lifecycle package contract."""
    path = Path(package_dir) / "lifecycle.json"
    if not path.is_file():
        raise EvidenceLifecycleError(f"lifecycle contract not found: {path}")
    payload = _read_json(path)
    return EvidenceLifecycleSpec.model_validate(payload)


def canonical_evidence_lifecycle_spec_payload(spec: EvidenceLifecycleSpec) -> dict[str, Any]:
    """Return a canonical spec payload without behavior-neutral default-true policy fields."""
    payload = spec.model_dump(mode="json", exclude_none=True)
    for checkpoint in payload["checkpoints"]:
        if checkpoint.get("allow_additional_submission_fields") is True:
            checkpoint.pop("allow_additional_submission_fields")
    return payload


def validate_evidence_checkpoint_submission(
    checkpoint: EvidenceCheckpointSpec,
    submission: dict[str, Any],
) -> None:
    """Validate the public checkpoint field contract without invoking its verifier."""
    checkpoint_id = checkpoint.checkpoint_id
    if submission.get("checkpoint_id") != checkpoint_id:
        raise EvidenceLifecycleError(
            f"checkpoint submission id must be {checkpoint_id!r}, got {submission.get('checkpoint_id')!r}"
        )
    declared_fields = set(checkpoint.required_submission_fields)
    missing_fields = sorted(declared_fields - set(submission))
    if missing_fields:
        raise EvidenceLifecycleError(f"checkpoint submission missing required fields: {', '.join(missing_fields)}")
    if not checkpoint.allow_additional_submission_fields:
        undeclared_fields = sorted(set(submission) - declared_fields)
        if undeclared_fields:
            raise EvidenceLifecycleError(
                f"checkpoint submission contains undeclared fields: {', '.join(undeclared_fields)}"
            )


def evidence_lifecycle_package_identity(package_dir: Path) -> dict[str, str]:
    """Return the content-bound identity of one validated lifecycle package."""
    package = Path(package_dir)
    spec = load_evidence_lifecycle_spec(package)
    return {
        "lifecycle_id": spec.lifecycle_id,
        "world_id": spec.world_id,
        "spec_sha256": _spec_sha256(spec),
        "package_sha256": _package_sha256(package),
    }


def prepare_evidence_checkpoint(
    package_dir: Path,
    run_dir: Path,
    *,
    run_authorization_sha256: str | None = None,
) -> dict[str, Any]:
    """Release exactly the next checkpoint into the persistent agent workspace."""
    package = Path(package_dir)
    _require_active_sealed_lifecycle_mount(package)
    run = Path(run_dir)
    with _lifecycle_state_lock(run):
        return _prepare_evidence_checkpoint_locked(
            package,
            run,
            run_authorization_sha256=run_authorization_sha256,
        )


def _prepare_evidence_checkpoint_locked(
    package: Path,
    run: Path,
    *,
    run_authorization_sha256: str | None,
) -> dict[str, Any]:
    """Release the next checkpoint while holding the per-run mutation lock."""
    spec = load_evidence_lifecycle_spec(package)
    if any(checkpoint.conditional_evidence is not None for checkpoint in spec.checkpoints):
        _load_evidence_request_resolutions(package, spec)
    if _state_path(run).exists():
        state = _load_state(package, run, spec, lock_held=True)
        if run_authorization_sha256 is not None and state.run_authorization_sha256 != run_authorization_sha256:
            raise EvidenceLifecycleError("lifecycle run authorization does not match existing state")
    else:
        _preflight_checkpoint(package, spec.checkpoints[0])
        state = _initialize_state(
            package,
            run,
            spec,
            run_authorization_sha256=run_authorization_sha256,
        )

    if state.status == LifecycleRunStatus.COMPLETE:
        return _result_context(run, state)
    if state.active_checkpoint_id:
        checkpoint = _checkpoint(spec, state.active_checkpoint_id)
        return _checkpoint_context(run, checkpoint, state)
    _assert_prior_submissions_unchanged(run, state)
    checkpoint_index = sum(checkpoint.status == CheckpointRunStatus.SUBMITTED for checkpoint in state.checkpoint_runs)
    checkpoint = spec.checkpoints[checkpoint_index]
    completed_ids = {
        item.checkpoint_id for item in state.checkpoint_runs if item.status == CheckpointRunStatus.SUBMITTED
    }
    if not set(checkpoint.depends_on).issubset(completed_ids):
        raise EvidenceLifecycleError(f"checkpoint dependencies are incomplete: {checkpoint.checkpoint_id}")

    instruction = _preflight_checkpoint(package, checkpoint)
    released_files = _materialize_checkpoint_release(package, run, checkpoint, instruction)

    checkpoint_run = state.checkpoint(checkpoint.checkpoint_id)
    checkpoint_run.status = CheckpointRunStatus.ACTIVE
    checkpoint_run.released_files = released_files
    previous_checkpoint_id = next(
        (
            item.checkpoint_id
            for item in reversed(state.checkpoint_runs)
            if item.status == CheckpointRunStatus.SUBMITTED
        ),
        None,
    )
    _append_transition(
        state,
        kind=LifecycleTransitionKind.RELEASE,
        from_checkpoint_id=previous_checkpoint_id,
        to_checkpoint_id=checkpoint.checkpoint_id,
        reason="Evidence released for active review.",
    )
    state.status = LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION
    state.active_checkpoint_id = checkpoint.checkpoint_id
    _write_evidence_request_catalog(run, checkpoint, checkpoint_run)
    if state.schema_version == "5":
        _write_lifecycle_operation_catalog(package, run, spec, state)
    _write_state(run, state)
    _sync_transition_ledger(run, state)
    release_summary: dict[str, Any] = {
        "checkpoint_id": checkpoint.checkpoint_id,
        "released_files": released_files,
    }
    if state.run_authorization_sha256 is not None:
        release_summary["run_authorization_sha256"] = state.run_authorization_sha256
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="evidence_release",
        status="awaiting_checkpoint_submission",
        summary=release_summary,
        artifact_refs=[str(_workspace(run) / "inbox" / checkpoint.checkpoint_id / path) for path in released_files],
    )
    return _checkpoint_context(run, checkpoint, state)


def _require_active_sealed_lifecycle_mount(package_dir: Path) -> None:
    """Fail before run mutation when a sealed package lacks its exact active provider."""
    from aec_bench.task_world_templates.lifecycles.provider import (
        active_sealed_lifecycle_mount,
        is_sealed_lifecycle_package,
    )

    if is_sealed_lifecycle_package(package_dir):
        active_sealed_lifecycle_mount(package_dir)


def request_evidence_checkpoint(
    package_dir: Path,
    run_dir: Path,
    *,
    checkpoint_id: str,
    request_id: str,
    reason: str,
    session_id: str,
) -> dict[str, Any]:
    """Release one declared conditional evidence packet for the active attempt."""
    if not checkpoint_id.strip() or not request_id.strip() or not reason.strip():
        raise EvidenceLifecycleError("evidence request checkpoint, request, and reason must not be blank")
    package = Path(package_dir)
    run = Path(run_dir)
    with _lifecycle_state_lock(run):
        return _request_evidence_checkpoint_locked(
            package,
            run,
            checkpoint_id=checkpoint_id,
            request_id=request_id,
            reason=reason,
            session_id=session_id,
        )


def _request_evidence_checkpoint_locked(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    request_id: str,
    reason: str,
    session_id: str,
) -> dict[str, Any]:
    spec = load_evidence_lifecycle_spec(package)
    resolutions = _load_evidence_request_resolutions(package, spec)
    state = _load_state(package, run, spec, lock_held=True)
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
            f"active attempt belongs to {attempt.session_id}; cannot request evidence from {session_id}"
        )

    if checkpoint_id != active_checkpoint_id:
        return _record_evidence_request_action(
            run,
            spec,
            state,
            requested_checkpoint_id=checkpoint_id,
            request_id=request_id,
            reason=reason,
            session_id=session_id,
            outcome=EvidenceRequestOutcome.REJECTED,
            rejection=EvidenceRequestRejection.INACTIVE_CHECKPOINT,
        )

    conditional = checkpoint.conditional_evidence
    if conditional is None:
        return _record_evidence_request_action(
            run,
            spec,
            state,
            requested_checkpoint_id=checkpoint_id,
            request_id=request_id,
            reason=reason,
            session_id=session_id,
            outcome=EvidenceRequestOutcome.REJECTED,
            rejection=EvidenceRequestRejection.NOT_SUPPORTED,
        )

    request = next((item for item in conditional.requests if item.request_id == request_id), None)
    if request is None:
        return _record_evidence_request_action(
            run,
            spec,
            state,
            requested_checkpoint_id=checkpoint_id,
            request_id=request_id,
            reason=reason,
            session_id=session_id,
            outcome=EvidenceRequestOutcome.REJECTED,
            rejection=EvidenceRequestRejection.UNKNOWN_REQUEST,
        )

    prior_release = next(
        (
            action
            for action in checkpoint_run.evidence_request_actions
            if action.request_id == request_id and action.outcome == EvidenceRequestOutcome.RELEASED
        ),
        None,
    )
    if prior_release is not None:
        _assert_evidence_request_artifacts_unchanged(run, prior_release)
        return _record_evidence_request_action(
            run,
            spec,
            state,
            requested_checkpoint_id=checkpoint_id,
            request_id=request_id,
            reason=reason,
            session_id=session_id,
            outcome=EvidenceRequestOutcome.ALREADY_RELEASED,
            released_artifacts=prior_release.released_artifacts,
        )

    released_ids = {
        action.request_id
        for action in checkpoint_run.evidence_request_actions
        if action.outcome == EvidenceRequestOutcome.RELEASED
    }
    if not set(request.prerequisite_request_ids).issubset(released_ids):
        return _record_evidence_request_action(
            run,
            spec,
            state,
            requested_checkpoint_id=checkpoint_id,
            request_id=request_id,
            reason=reason,
            session_id=session_id,
            outcome=EvidenceRequestOutcome.REJECTED,
            rejection=EvidenceRequestRejection.PREREQUISITES_INCOMPLETE,
        )
    if checkpoint_run.evidence_request_budget_remaining < 1:
        return _record_evidence_request_action(
            run,
            spec,
            state,
            requested_checkpoint_id=checkpoint_id,
            request_id=request_id,
            reason=reason,
            session_id=session_id,
            outcome=EvidenceRequestOutcome.REJECTED,
            rejection=EvidenceRequestRejection.BUDGET_EXHAUSTED,
        )

    resolution = resolutions[(checkpoint_id, request_id)]
    source = package / resolution.source_path
    return _record_evidence_request_action(
        run,
        spec,
        state,
        requested_checkpoint_id=checkpoint_id,
        request_id=request_id,
        reason=reason,
        session_id=session_id,
        outcome=EvidenceRequestOutcome.RELEASED,
        release_source=source,
    )


def execute_lifecycle_operation(
    package_dir: Path,
    run_dir: Path,
    *,
    checkpoint_id: str,
    operation_id: str,
    visible_source_state_sha256: str,
    reason: str,
    session_id: str,
) -> dict[str, Any]:
    """Execute one declared source-bound operation for the active host attempt."""
    arguments = (checkpoint_id, operation_id, visible_source_state_sha256, reason, session_id)
    if any(not isinstance(argument, str) or not argument.strip() for argument in arguments):
        raise EvidenceLifecycleError(
            "operation checkpoint, id, visible source hash, reason, and session must not be blank"
        )
    if len(visible_source_state_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in visible_source_state_sha256
    ):
        raise EvidenceLifecycleError("visible source state sha256 must contain 64 lowercase hexadecimal characters")
    package = Path(package_dir)
    run = Path(run_dir)
    with _lifecycle_state_lock(run):
        spec = load_evidence_lifecycle_spec(package)
        state = _load_state(package, run, spec, lock_held=True)
        _assert_prior_submissions_unchanged(run, state)
        return _execute_lifecycle_operation_locked(
            package,
            run,
            spec,
            state,
            requested_checkpoint_id=checkpoint_id,
            operation_id=operation_id,
            visible_source_state_sha256=visible_source_state_sha256,
            reason=reason,
            session_id=session_id,
        )


def submit_evidence_checkpoint(
    package_dir: Path,
    run_dir: Path,
    *,
    episode_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Accept one structurally valid submission and preserve it outside the workspace."""
    package = Path(package_dir)
    run = Path(run_dir)
    with _lifecycle_state_lock(run):
        return _submit_evidence_checkpoint_locked(package, run, episode_result=episode_result)


def _submit_evidence_checkpoint_locked(
    package: Path,
    run: Path,
    *,
    episode_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Submit the active checkpoint while holding the per-run mutation lock."""
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec, lock_held=True)
    checkpoint_id = state.active_checkpoint_id
    if not checkpoint_id:
        raise EvidenceLifecycleError("no checkpoint is awaiting submission")

    _assert_prior_submissions_unchanged(run, state)
    checkpoint = _checkpoint(spec, checkpoint_id)
    submission_path = _workspace(run) / checkpoint.submission_path
    if not submission_path.is_file():
        raise EvidenceLifecycleError(f"checkpoint submission not found: {submission_path}")
    submission = _read_json(submission_path)
    validate_evidence_checkpoint_submission(checkpoint, submission)

    episode_dir = run / "episodes" / checkpoint_id
    episode_dir.mkdir(parents=True, exist_ok=True)
    archive_path = episode_dir / "submission.json"
    archive_temp = archive_path.with_suffix(".json.tmp")
    shutil.copy2(submission_path, archive_temp)
    archive_temp.replace(archive_path)
    submission_sha256 = _sha256(archive_path)
    _write_json(episode_dir / "result.json", copy.deepcopy(episode_result or {}))

    checkpoint_run = state.checkpoint(checkpoint_id)
    checkpoint_run.status = CheckpointRunStatus.SUBMITTED
    checkpoint_run.submission_path = checkpoint.submission_path
    checkpoint_run.submission_sha256 = submission_sha256
    if checkpoint_run.active_attempt is not None:
        checkpoint_run.active_attempt.status = CheckpointAttemptStatus.SUBMITTED
    _append_transition(
        state,
        kind=LifecycleTransitionKind.SUBMIT,
        from_checkpoint_id=checkpoint_id,
        to_checkpoint_id=None,
        reason="Checkpoint submission archived.",
    )
    state.active_checkpoint_id = None
    state.status = (
        LifecycleRunStatus.COMPLETE
        if all(item.status == CheckpointRunStatus.SUBMITTED for item in state.checkpoint_runs)
        else LifecycleRunStatus.AWAITING_EVIDENCE_RELEASE
    )
    _write_state(run, state)
    _sync_transition_ledger(run, state)
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="checkpoint_submission",
        status=state.status.value,
        summary={
            "checkpoint_id": checkpoint_id,
            "submission_sha256": submission_sha256,
        },
        artifact_refs=[str(archive_path)],
    )
    return _result_context(run, state)


def branch_evidence_lifecycle(
    package_dir: Path,
    parent_run_dir: Path,
    branch_run_dir: Path,
    *,
    checkpoint_id: str,
    branch_id: str,
    reason: str,
) -> dict[str, Any]:
    """Create an isolated derived run that reopens one submitted checkpoint."""
    package = Path(package_dir)
    parent_run = Path(parent_run_dir)
    branch_run = Path(branch_run_dir)
    with _lifecycle_state_lock(parent_run):
        return _branch_evidence_lifecycle_locked(
            package,
            parent_run,
            branch_run,
            checkpoint_id=checkpoint_id,
            branch_id=branch_id,
            reason=reason,
        )


def _branch_evidence_lifecycle_locked(
    package: Path,
    parent_run: Path,
    branch_run: Path,
    *,
    checkpoint_id: str,
    branch_id: str,
    reason: str,
) -> dict[str, Any]:
    """Create a branch from a stable parent state held under its mutation lock."""
    spec = load_evidence_lifecycle_spec(package)
    parent_state = _load_state(package, parent_run, spec, lock_held=True)
    _assert_prior_submissions_unchanged(parent_run, parent_state)
    try:
        branch_index = next(
            index for index, checkpoint in enumerate(spec.checkpoints) if checkpoint.checkpoint_id == checkpoint_id
        )
    except StopIteration as exc:
        raise EvidenceLifecycleError(f"unknown checkpoint: {checkpoint_id}") from exc
    parent_checkpoint = parent_state.checkpoint(checkpoint_id)
    if parent_checkpoint.status != CheckpointRunStatus.SUBMITTED:
        raise EvidenceLifecycleError(f"checkpoint is not available for branching: {checkpoint_id}")
    if branch_run.exists():
        raise EvidenceLifecycleError(f"branch run directory already exists: {branch_run}")
    if parent_checkpoint.submission_sha256 is None:
        raise EvidenceLifecycleError(f"submitted checkpoint is missing its sha256: {checkpoint_id}")

    checkpoint_runs: list[CheckpointRunRecord] = []
    for index, checkpoint in enumerate(spec.checkpoints):
        if index < branch_index:
            inherited = parent_state.checkpoint(checkpoint.checkpoint_id)
            if inherited.status != CheckpointRunStatus.SUBMITTED:
                raise EvidenceLifecycleError(f"parent checkpoint dependency is incomplete: {checkpoint.checkpoint_id}")
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    status=CheckpointRunStatus.SUBMITTED,
                    released_files=list(inherited.released_files),
                    submission_path=inherited.submission_path,
                    submission_sha256=inherited.submission_sha256,
                    attempts=[
                        attempt.model_copy(deep=True, update={"inherited_from_parent": True})
                        for attempt in inherited.attempts
                    ],
                    evidence_request_budget=inherited.evidence_request_budget,
                    evidence_request_budget_remaining=inherited.evidence_request_budget_remaining,
                    evidence_request_actions=[
                        action.model_copy(deep=True, update={"inherited_from_parent": True})
                        for action in inherited.evidence_request_actions
                    ],
                    operation_budget=inherited.operation_budget,
                    operation_budget_remaining=inherited.operation_budget_remaining,
                    operation_actions=[
                        action.model_copy(deep=True, update={"inherited_from_parent": True})
                        for action in inherited.operation_actions
                    ],
                    inherited_from_parent=True,
                )
            )
        elif index == branch_index:
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    status=CheckpointRunStatus.ACTIVE,
                    released_files=list(parent_checkpoint.released_files),
                    attempts=[
                        attempt.model_copy(deep=True, update={"inherited_from_parent": True})
                        for attempt in parent_checkpoint.attempts
                    ],
                    evidence_request_budget=parent_checkpoint.evidence_request_budget,
                    evidence_request_budget_remaining=parent_checkpoint.evidence_request_budget_remaining,
                    evidence_request_actions=[
                        action.model_copy(deep=True, update={"inherited_from_parent": True})
                        for action in parent_checkpoint.evidence_request_actions
                    ],
                    operation_budget=parent_checkpoint.operation_budget,
                    operation_budget_remaining=parent_checkpoint.operation_budget_remaining,
                    operation_actions=[
                        action.model_copy(deep=True, update={"inherited_from_parent": True})
                        for action in parent_checkpoint.operation_actions
                    ],
                )
            )
        else:
            request_budget = (
                checkpoint.conditional_evidence.request_budget if checkpoint.conditional_evidence is not None else 0
            )
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    evidence_request_budget=request_budget,
                    evidence_request_budget_remaining=request_budget,
                    operation_budget=(
                        checkpoint.conditional_operations.operation_budget
                        if checkpoint.conditional_operations is not None
                        else 0
                    ),
                    operation_budget_remaining=(
                        checkpoint.conditional_operations.operation_budget
                        if checkpoint.conditional_operations is not None
                        else 0
                    ),
                )
            )

    state = EvidenceLifecycleRunState(
        schema_version=parent_state.schema_version,
        lifecycle_id=spec.lifecycle_id,
        world_id=spec.world_id,
        lifecycle_spec_sha256=parent_state.lifecycle_spec_sha256,
        package_sha256=parent_state.package_sha256,
        status=LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION,
        active_checkpoint_id=checkpoint_id,
        checkpoint_runs=checkpoint_runs,
        branch=LifecycleBranchRecord(
            branch_id=branch_id,
            parent_run_dir=str(parent_run),
            branched_from_checkpoint_id=checkpoint_id,
            parent_submission_sha256=parent_checkpoint.submission_sha256,
            parent_action_state_sha256=_branch_action_state_sha256(
                parent_state,
                branch_index=branch_index,
                inherited_only=False,
            ),
            reason=reason,
        ),
    )
    _append_transition(
        state,
        kind=LifecycleTransitionKind.BRANCH,
        from_checkpoint_id=checkpoint_id,
        to_checkpoint_id=checkpoint_id,
        reason=reason,
    )

    branch_run.parent.mkdir(parents=True, exist_ok=True)
    staging_run = Path(tempfile.mkdtemp(prefix=f".{branch_run.name}.tmp-", dir=branch_run.parent))
    try:
        workspace = _workspace(staging_run)
        workspace.mkdir(parents=True)
        for index, checkpoint in enumerate(spec.checkpoints[: branch_index + 1]):
            _copy_release(
                _workspace(parent_run) / "inbox" / checkpoint.checkpoint_id,
                workspace / "inbox" / checkpoint.checkpoint_id,
            )
            _copy_file_atomic(
                _workspace(parent_run) / "checkpoints" / checkpoint.checkpoint_id / "instruction.md",
                workspace / "checkpoints" / checkpoint.checkpoint_id / "instruction.md",
            )
            if state.schema_version == "5" and checkpoint.conditional_operations is not None:
                _copy_file_atomic(
                    _workspace(parent_run) / "checkpoints" / checkpoint.checkpoint_id / "operations.json",
                    workspace / "checkpoints" / checkpoint.checkpoint_id / "operations.json",
                )
            if index < branch_index:
                _inherit_submission(parent_run, staging_run, checkpoint)

        _inherit_evidence_request_transactions(parent_run, staging_run, state)
        if state.schema_version == "5":
            _inherit_lifecycle_operation_transactions(parent_run, staging_run, state)
        for checkpoint in spec.checkpoints[: branch_index + 1]:
            _write_evidence_request_catalog(
                staging_run,
                checkpoint,
                state.checkpoint(checkpoint.checkpoint_id),
            )
        if state.schema_version == "5":
            _write_lifecycle_operation_catalog(package, staging_run, spec, state)
            from aec_bench.meta_harness.lifecycle_operation_snapshot import validate_lifecycle_operation_snapshot

            validate_lifecycle_operation_snapshot(staging_run, state, spec)

        parent_archive = parent_run / "episodes" / checkpoint_id / "submission.json"
        staged_origin = workspace / "branch_origin" / f"{checkpoint_id}.json"
        staged_submission = workspace / _checkpoint(spec, checkpoint_id).submission_path
        _copy_file_atomic(parent_archive, staged_origin)
        _copy_file_atomic(parent_archive, staged_submission)
        _write_text_atomic(
            workspace / "instruction.md",
            (workspace / "checkpoints" / checkpoint_id / "instruction.md").read_text(encoding="utf-8"),
        )
        _write_state(staging_run, state)
        _sync_transition_ledger(staging_run, state)
        _sync_evidence_request_ledger(staging_run, state)
        if state.schema_version == "5":
            _sync_lifecycle_operation_ledger(staging_run, state)
        final_origin = _workspace(branch_run) / "branch_origin" / f"{checkpoint_id}.json"
        final_submission = _workspace(branch_run) / _checkpoint(spec, checkpoint_id).submission_path
        append_ledger_entry(
            _ledger_path(staging_run),
            process_id=spec.lifecycle_id,
            stage="lifecycle_branch",
            status="awaiting_checkpoint_submission",
            summary=state.branch.model_dump(mode="json") if state.branch is not None else {},
            artifact_refs=[str(final_origin), str(final_submission)],
        )
        staging_run.replace(branch_run)
    except Exception:
        shutil.rmtree(staging_run, ignore_errors=True)
        raise
    return _checkpoint_context(branch_run, _checkpoint(spec, checkpoint_id), state)


def open_checkpoint_attempt(
    package_dir: Path,
    run_dir: Path,
    *,
    session_id: str,
    execution_mode: str,
    episode_request_sha256: str | None = None,
) -> dict[str, Any]:
    """Open a checkpoint attempt, interrupting an abandoned active attempt."""
    package = Path(package_dir)
    run = Path(run_dir)
    with _lifecycle_state_lock(run):
        return _open_checkpoint_attempt_locked(
            package,
            run,
            session_id=session_id,
            execution_mode=execution_mode,
            episode_request_sha256=episode_request_sha256,
        )


def _open_checkpoint_attempt_locked(
    package: Path,
    run: Path,
    *,
    session_id: str,
    execution_mode: str,
    episode_request_sha256: str | None,
) -> dict[str, Any]:
    """Open an attempt while holding the per-run mutation lock."""
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec, lock_held=True)
    checkpoint_id = state.active_checkpoint_id
    if checkpoint_id is None:
        raise EvidenceLifecycleError("no checkpoint is active")
    checkpoint_run = state.checkpoint(checkpoint_id)
    active_attempt = checkpoint_run.active_attempt
    if active_attempt is not None and active_attempt.session_id == session_id:
        if episode_request_sha256 is not None and active_attempt.episode_request_sha256 != episode_request_sha256:
            raise EvidenceLifecycleError("active checkpoint attempt request hash changed")
        return _attempt_context(active_attempt)
    if active_attempt is not None:
        active_attempt.status = CheckpointAttemptStatus.INTERRUPTED
    previous = checkpoint_run.last_attempt

    sequence = len(checkpoint_run.attempts) + 1
    attempt = CheckpointAttemptRecord(
        attempt_id=f"{checkpoint_id}.attempt-{sequence:03d}",
        session_id=session_id,
        sequence=sequence,
        execution_mode=execution_mode,
        status=CheckpointAttemptStatus.ACTIVE,
        resumed_from_attempt_id=previous.attempt_id if previous is not None else None,
        episode_request_sha256=episode_request_sha256,
    )
    checkpoint_run.attempts.append(attempt)
    _write_state(run, state)
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="checkpoint_attempt",
        status="active",
        summary={
            "checkpoint_id": checkpoint_id,
            "attempt_id": attempt.attempt_id,
            "session_id": session_id,
            "resumed_from_attempt_id": attempt.resumed_from_attempt_id,
            "episode_request_sha256": attempt.episode_request_sha256,
        },
        artifact_refs=[],
    )
    return _attempt_context(attempt)


def fail_checkpoint_attempt(
    package_dir: Path,
    run_dir: Path,
    *,
    session_id: str,
    failure_kind: str,
) -> dict[str, Any]:
    """Close the active checkpoint attempt after an execution failure."""
    package = Path(package_dir)
    run = Path(run_dir)
    with _lifecycle_state_lock(run):
        return _fail_checkpoint_attempt_locked(
            package,
            run,
            session_id=session_id,
            failure_kind=failure_kind,
        )


def _fail_checkpoint_attempt_locked(
    package: Path,
    run: Path,
    *,
    session_id: str,
    failure_kind: str,
) -> dict[str, Any]:
    """Fail an attempt while holding the per-run mutation lock."""
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec, lock_held=True)
    checkpoint_id = state.active_checkpoint_id
    if checkpoint_id is None:
        raise EvidenceLifecycleError("no checkpoint is active")
    checkpoint_run = state.checkpoint(checkpoint_id)
    attempt = checkpoint_run.active_attempt
    if attempt is None:
        raise EvidenceLifecycleError("no checkpoint attempt is active")
    if attempt.session_id != session_id:
        raise EvidenceLifecycleError(
            f"active attempt belongs to {attempt.session_id}; cannot fail it from {session_id}"
        )

    attempt.status = CheckpointAttemptStatus.FAILED
    attempt.failure_kind = failure_kind
    _write_state(run, state)
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="checkpoint_attempt",
        status="failed",
        summary={
            "checkpoint_id": checkpoint_id,
            "attempt_id": attempt.attempt_id,
            "session_id": session_id,
            "failure_kind": failure_kind,
        },
        artifact_refs=[],
    )
    return _attempt_context(attempt)


def revisit_evidence_checkpoint(
    package_dir: Path,
    run_dir: Path,
    *,
    checkpoint_id: str,
    reason: str,
) -> dict[str, Any]:
    """Return and log an immutable prior checkpoint without rewinding the run."""
    package = Path(package_dir)
    run = Path(run_dir)
    with _lifecycle_state_lock(run):
        return _revisit_evidence_checkpoint_locked(
            package,
            run,
            checkpoint_id=checkpoint_id,
            reason=reason,
        )


def _revisit_evidence_checkpoint_locked(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    reason: str,
) -> dict[str, Any]:
    """Record a revisit while holding the per-run mutation lock."""
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec, lock_held=True)
    _assert_prior_submissions_unchanged(run, state)
    try:
        checkpoint_run = state.checkpoint(checkpoint_id)
    except KeyError as exc:
        raise EvidenceLifecycleError(f"unknown checkpoint: {checkpoint_id}") from exc
    if checkpoint_run.status != CheckpointRunStatus.SUBMITTED:
        raise EvidenceLifecycleError(f"checkpoint is not available for revisit: {checkpoint_id}")

    archive_path = run / "episodes" / checkpoint_id / "submission.json"
    instruction_path = _workspace(run) / "checkpoints" / checkpoint_id / "instruction.md"
    revisit = CheckpointRevisitRecord(
        revisit_id=f"revisit-{len(state.revisits) + 1:03d}",
        checkpoint_id=checkpoint_id,
        requested_from_checkpoint_id=state.active_checkpoint_id,
        reason=reason,
    )
    state.revisits.append(revisit)
    _append_transition(
        state,
        kind=LifecycleTransitionKind.REVISIT,
        from_checkpoint_id=revisit.requested_from_checkpoint_id,
        to_checkpoint_id=checkpoint_id,
        reason=reason,
    )
    _write_state(run, state)
    _sync_transition_ledger(run, state)
    append_ledger_entry(
        _ledger_path(run),
        process_id=spec.lifecycle_id,
        stage="checkpoint_revisit",
        status="recorded",
        summary=revisit.model_dump(mode="json"),
        artifact_refs=[str(archive_path), str(instruction_path)],
    )
    return {
        **revisit.model_dump(mode="json"),
        "instruction": instruction_path.read_text(encoding="utf-8"),
        "submission": _read_json(archive_path),
        "released_files": list(checkpoint_run.released_files),
    }


def run_evidence_lifecycle(
    package_dir: Path,
    run_dir: Path,
    *,
    episode_environment: LifecycleEpisodeEnvironment,
    run_authorization_sha256: str | None = None,
) -> dict[str, Any]:
    """Run every checkpoint in a fresh typed episode and one persistent workspace."""
    execution_mode = LifecycleExecutionMode(episode_environment.execution_mode)
    if execution_mode is not LifecycleExecutionMode.FRESH_CONTEXT:
        raise ValueError("checkpoint lifecycle runner requires fresh_context episode execution")
    while True:
        raw_context = prepare_evidence_checkpoint(
            package_dir,
            run_dir,
            run_authorization_sha256=run_authorization_sha256,
        )
        if raw_context["status"] == "complete":
            return raw_context
        context = LifecycleEpisodeContext.from_runtime_context(
            raw_context,
            visibility_policy=episode_environment.memory_visibility_policy,
        )
        _recover_host_episode_attempt(context, episode_environment)
        episode_environment.recover(context)
        context = LifecycleEpisodeContext.from_runtime_context(
            prepare_evidence_checkpoint(
                package_dir,
                run_dir,
                run_authorization_sha256=run_authorization_sha256,
            ),
            visibility_policy=episode_environment.memory_visibility_policy,
        )
        _preserve_prior_attempt_submission(context)
        checkpoint_run = next(item for item in context.checkpoint_runs if item.checkpoint_id == context.checkpoint_id)
        attempt_sequence = len(checkpoint_run.attempts) + 1
        session_id = f"{context.checkpoint_id}.session-{attempt_sequence:03d}"
        attempt_id = f"{context.checkpoint_id}.attempt-{attempt_sequence:03d}"
        request = _build_episode_request(
            context,
            episode_environment,
            attempt_id=attempt_id,
            session_id=session_id,
        )
        request = _adopt_compatible_durable_episode_request(request)
        try:
            episode_environment.prepare(request)
        except Exception as exc:
            _quarantine_prepared_host_artifacts(request)
            request_path = _persist_episode_request(request)
            attempt = open_checkpoint_attempt(
                package_dir,
                run_dir,
                session_id=session_id,
                execution_mode=execution_mode.value,
                episode_request_sha256=_sha256(request_path),
            )
            if attempt["attempt_id"] != request.attempt_id or attempt["session_id"] != request.session_id:
                raise EvidenceLifecycleError(
                    "published checkpoint attempt does not match allocated episode request"
                ) from exc
            failure_kind = "episode_preparation_exception"
            failure = _failed_episode_result(
                request,
                failure_kind=failure_kind,
                provider_error=str(exc),
            )
            _persist_episode_result_or_close(
                episode_environment,
                request,
                failure,
                package_dir=package_dir,
                run_dir=run_dir,
            )
            reconciliation_errors = _close_episode_failure(
                episode_environment,
                request,
                package_dir=package_dir,
                run_dir=run_dir,
                failure_kind=failure_kind,
                provider_error=str(exc),
            )
            _annotate_reconciliation_errors(exc, reconciliation_errors)
            raise
        prepared_host_artifacts = _quarantine_prepared_host_artifacts(request)
        request_path = _persist_episode_request(request)
        attempt = open_checkpoint_attempt(
            package_dir,
            run_dir,
            session_id=session_id,
            execution_mode=execution_mode.value,
            episode_request_sha256=_sha256(request_path),
        )
        if attempt["attempt_id"] != request.attempt_id or attempt["session_id"] != request.session_id:
            raise EvidenceLifecycleError("published checkpoint attempt does not match allocated episode request")
        preparation_violations = list(prepared_host_artifacts)
        if Path(request.submission_path).exists():
            preparation_violations.append("checkpoint submission")
        if preparation_violations:
            failure_kind = "episode_preparation_invalid"
            provider_error = "episode preparation created reserved artifacts: " + ", ".join(preparation_violations)
            failure = _failed_episode_result(
                request,
                failure_kind=failure_kind,
                provider_error=provider_error,
            )
            _persist_episode_result_or_close(
                episode_environment,
                request,
                failure,
                package_dir=package_dir,
                run_dir=run_dir,
            )
            reconciliation_errors = _close_episode_failure(
                episode_environment,
                request,
                package_dir=package_dir,
                run_dir=run_dir,
                failure_kind=failure_kind,
                provider_error=provider_error,
            )
            error = EvidenceLifecycleError(provider_error)
            _annotate_reconciliation_errors(error, reconciliation_errors)
            raise error
        try:
            raw_episode_result = episode_environment.execute(request)
        except LifecycleEpisodeEnvironmentFailure as exc:
            failure = _failed_episode_result(
                request,
                failure_kind=exc.failure_kind,
                provider_error=str(exc),
            )
            _persist_episode_result_or_close(
                episode_environment,
                request,
                failure,
                package_dir=package_dir,
                run_dir=run_dir,
            )
            reconciliation_errors = _close_episode_failure(
                episode_environment,
                request,
                package_dir=package_dir,
                run_dir=run_dir,
                failure_kind=exc.failure_kind,
                provider_error=str(exc),
            )
            _annotate_reconciliation_errors(exc, reconciliation_errors)
            raise
        except Exception as exc:
            failure_kind = "episode_environment_exception"
            failure = _failed_episode_result(
                request,
                failure_kind=failure_kind,
                provider_error=str(exc),
            )
            _persist_episode_result_or_close(
                episode_environment,
                request,
                failure,
                package_dir=package_dir,
                run_dir=run_dir,
            )
            reconciliation_errors = _close_episode_failure(
                episode_environment,
                request,
                package_dir=package_dir,
                run_dir=run_dir,
                failure_kind="episode_environment_exception",
                provider_error=str(exc),
            )
            _annotate_reconciliation_errors(exc, reconciliation_errors)
            raise
        try:
            episode_result = LifecycleEpisodeResult.model_validate(raw_episode_result)
        except ValidationError as exc:
            failure_kind = "episode_result_invalid"
            failure = _failed_episode_result(
                request,
                failure_kind=failure_kind,
                provider_error=str(exc),
            )
            _persist_episode_result_or_close(
                episode_environment,
                request,
                failure,
                package_dir=package_dir,
                run_dir=run_dir,
            )
            reconciliation_errors = _close_episode_failure(
                episode_environment,
                request,
                package_dir=package_dir,
                run_dir=run_dir,
                failure_kind=failure_kind,
                provider_error=str(exc),
            )
            error = EvidenceLifecycleError("environment returned an invalid episode result")
            _annotate_reconciliation_errors(error, reconciliation_errors)
            raise error from exc
        try:
            validate_episode_result_identity(request, episode_result)
        except ValueError as exc:
            failure_kind = "episode_result_identity_mismatch"
            _persist_episode_result_or_close(
                episode_environment,
                request,
                episode_result,
                package_dir=package_dir,
                run_dir=run_dir,
                filename="rejected_episode_result.json",
            )
            failure = _failed_episode_result(
                request,
                failure_kind=failure_kind,
                provider_error=str(exc),
            )
            _persist_episode_result_or_close(
                episode_environment,
                request,
                failure,
                package_dir=package_dir,
                run_dir=run_dir,
            )
            reconciliation_errors = _close_episode_failure(
                episode_environment,
                request,
                package_dir=package_dir,
                run_dir=run_dir,
                failure_kind=failure_kind,
                provider_error=str(exc),
            )
            error = EvidenceLifecycleError(str(exc))
            _annotate_reconciliation_errors(error, reconciliation_errors)
            raise error from exc
        _persist_episode_result_or_close(
            episode_environment,
            request,
            episode_result,
            package_dir=package_dir,
            run_dir=run_dir,
        )
        if episode_result.status == "failed":
            failure_kind = episode_result.failure_kind or "episode_failed"
            reconciliation_errors = _close_episode_failure(
                episode_environment,
                request,
                package_dir=package_dir,
                run_dir=run_dir,
                failure_kind=failure_kind,
                provider_error=episode_result.provider_error,
            )
            error = LifecycleEpisodeExecutionError(
                f"episode failed at checkpoint {context.checkpoint_id}: {failure_kind}"
            )
            _annotate_reconciliation_errors(error, reconciliation_errors)
            raise error
        try:
            result = submit_evidence_checkpoint(
                package_dir,
                run_dir,
                episode_result=episode_result.model_dump(mode="json"),
            )
        except Exception as exc:
            failure_kind = "episode_submission_invalid"
            reconciliation_errors = _close_episode_failure(
                episode_environment,
                request,
                package_dir=package_dir,
                run_dir=run_dir,
                failure_kind=failure_kind,
                provider_error=str(exc),
            )
            _annotate_reconciliation_errors(exc, reconciliation_errors)
            raise
        if result["status"] == "complete":
            return result


def _build_episode_request(
    context: LifecycleEpisodeContext,
    environment: LifecycleEpisodeEnvironment,
    *,
    attempt_id: str,
    session_id: str,
) -> LifecycleEpisodeRequest:
    """Construct the full host-authored identity for one environment attempt."""
    return LifecycleEpisodeRequest(
        episode_id=f"{context.lifecycle_id}.{attempt_id}",
        lifecycle_id=context.lifecycle_id,
        world_id=context.world_id,
        lifecycle_spec_sha256=context.lifecycle_spec_sha256,
        package_sha256=context.package_sha256,
        checkpoint_id=context.checkpoint_id,
        checkpoint_ids=(context.checkpoint_id,),
        attempt_id=attempt_id,
        session_id=session_id,
        execution_mode=LifecycleExecutionMode(environment.execution_mode),
        memory_visibility_policy=LifecycleVisibilityPolicy(environment.memory_visibility_policy),
        requested_adapter=environment.requested_adapter,
        requested_model=environment.requested_model,
        max_turns_per_session=environment.max_turns_per_session,
        title=context.title,
        instruction=context.instruction,
        workspace=context.workspace,
        run_dir=context.run_dir,
        instruction_path=context.instruction_path,
        submission_path=context.submission_path,
        released_files=context.released_files,
        evidence_request_catalog=context.evidence_request_catalog,
        released_evidence_artifacts=context.released_evidence_artifacts,
        operation_catalog=context.operation_catalog,
        current_source=context.current_source,
        visible_operation_artifacts=context.visible_operation_artifacts,
        completed_checkpoint_ids=context.completed_checkpoint_ids,
    )


def _failed_episode_result(
    request: LifecycleEpisodeRequest,
    *,
    failure_kind: str,
    provider_error: str | None,
) -> LifecycleEpisodeResult:
    return LifecycleEpisodeResult(
        episode_id=request.episode_id,
        attempt_id=request.attempt_id,
        session_id=request.session_id,
        checkpoint_ids=request.checkpoint_ids,
        execution_mode=request.execution_mode,
        memory_visibility_policy=request.memory_visibility_policy,
        status="failed",
        requested_adapter=request.requested_adapter,
        requested_model=request.requested_model,
        max_turns_per_session=request.max_turns_per_session,
        adapter="unresolved",
        resolved_model="unresolved",
        configuration={},
        failure_kind=failure_kind,
        provider_error=provider_error or failure_kind,
    )


def _persist_episode_request(request: LifecycleEpisodeRequest) -> Path:
    """Publish the host-authored request before making its attempt active."""
    request_dir = Path(request.run_dir) / "episodes" / request.checkpoint_id / request.session_id
    request_path = request_dir / "episode_request.json"
    payload = _episode_request_json(request)
    return _persist_host_json(
        request_path,
        payload,
        conflict_message=f"episode request conflicts with durable attempt: {request.attempt_id}",
    )


def _recover_host_episode_attempt(
    context: LifecycleEpisodeContext,
    environment: LifecycleEpisodeEnvironment,
) -> None:
    """Ensure an interrupted host attempt retains request and result identity."""
    checkpoint_run = next(item for item in context.checkpoint_runs if item.checkpoint_id == context.checkpoint_id)
    attempt = checkpoint_run.active_attempt
    if attempt is None:
        return
    result_dir = Path(context.run_dir) / "episodes" / context.checkpoint_id / attempt.session_id
    request_path = result_dir / "episode_request.json"
    if not request_path.is_file():
        if attempt.episode_request_sha256 is not None:
            raise EvidenceLifecycleError(f"interrupted episode request is missing: {attempt.attempt_id}")
        return
    if attempt.episode_request_sha256 is not None and _sha256(request_path) != attempt.episode_request_sha256:
        raise EvidenceLifecycleError(f"interrupted episode request hash mismatch: {attempt.attempt_id}")
    request = LifecycleEpisodeRequest.model_validate(_read_json(request_path))
    expected_request = _build_episode_request(
        context,
        environment,
        attempt_id=attempt.attempt_id,
        session_id=attempt.session_id,
    )
    if request != expected_request and not _matches_legacy_episode_request(request, expected_request):
        raise EvidenceLifecycleError(f"interrupted episode request identity mismatch: {attempt.attempt_id}")
    result_path = result_dir / "episode_result.json"
    if result_path.is_file():
        result = LifecycleEpisodeResult.model_validate(_read_json(result_path))
        try:
            validate_episode_result_identity(request, result)
        except ValueError as exc:
            raise EvidenceLifecycleError(f"interrupted episode result identity mismatch: {attempt.attempt_id}") from exc
        return
    _persist_episode_result(
        request,
        _failed_episode_result(
            request,
            failure_kind="interrupted",
            provider_error="episode interrupted before a durable result was recorded",
        ),
    )


def _persist_episode_result(
    request: LifecycleEpisodeRequest,
    result: LifecycleEpisodeResult,
    *,
    filename: str = "episode_result.json",
) -> Path:
    """Publish one host-validated per-attempt result before state progression."""
    result_dir = Path(request.run_dir) / "episodes" / request.checkpoint_id / request.session_id
    result_path = result_dir / filename
    payload = json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    return _persist_host_json(
        result_path,
        payload,
        conflict_message=f"episode result conflicts with durable attempt: {request.attempt_id}",
    )


def _persist_host_json(path: Path, payload: str, *, conflict_message: str) -> Path:
    """Publish one deterministic host JSON artifact with conflict detection."""
    mkdir_durable(path.parent)
    if path.exists():
        if not path.is_file() or path.read_text(encoding="utf-8") != payload:
            raise EvidenceLifecycleError(conflict_message)
        return path

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
        fsync_directory(path.parent)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return path


def _persist_episode_result_or_close(
    environment: LifecycleEpisodeEnvironment,
    request: LifecycleEpisodeRequest,
    result: LifecycleEpisodeResult,
    *,
    package_dir: Path,
    run_dir: Path,
    filename: str = "episode_result.json",
) -> Path:
    """Publish a result or close the host attempt if durable publication fails."""
    try:
        return _persist_episode_result(request, result, filename=filename)
    except Exception as exc:
        reconciliation_errors = _close_episode_failure(
            environment,
            request,
            package_dir=package_dir,
            run_dir=run_dir,
            failure_kind="episode_result_persistence_error",
            provider_error=str(exc),
        )
        _annotate_reconciliation_errors(exc, reconciliation_errors)
        raise


def _quarantine_prepared_host_artifacts(request: LifecycleEpisodeRequest) -> tuple[str, ...]:
    """Move environment-created host-result paths aside before attempt publication."""
    result_dir = Path(request.run_dir) / "episodes" / request.checkpoint_id / request.session_id
    quarantined: list[str] = []
    for filename in ("episode_request.json", "episode_result.json", "rejected_episode_result.json"):
        source = result_dir / filename
        if not source.exists():
            continue
        if not source.is_file():
            raise EvidenceLifecycleError(f"reserved episode result path is not a file: {source}")
        if filename == "episode_request.json":
            expected = _episode_request_json(request)
            if source.read_text(encoding="utf-8") == expected:
                continue
        destination = result_dir / f"environment_prepared_{filename}"
        if destination.exists():
            raise EvidenceLifecycleError(f"prepared episode result quarantine already exists: {destination}")
        source.replace(destination)
        fsync_directory(result_dir)
        quarantined.append(filename)
    return tuple(quarantined)


def _adopt_compatible_durable_episode_request(
    request: LifecycleEpisodeRequest,
) -> LifecycleEpisodeRequest:
    """Reuse an exact durable request, including the pre-v2 shape, before environment preparation."""
    request_path = (
        Path(request.run_dir) / "episodes" / request.checkpoint_id / request.session_id / "episode_request.json"
    )
    if not request_path.is_file():
        return request
    try:
        durable = LifecycleEpisodeRequest.model_validate(_read_json(request_path))
    except (EvidenceLifecycleError, ValidationError):
        return request
    if durable == request or _matches_legacy_episode_request(durable, request):
        return durable
    return request


def _matches_legacy_episode_request(
    durable: LifecycleEpisodeRequest,
    expected: LifecycleEpisodeRequest,
) -> bool:
    return _matches_legacy_v2_episode_request(durable, expected) or _matches_legacy_v1_episode_request(
        durable,
        expected,
    )


def _matches_legacy_v2_episode_request(
    durable: LifecycleEpisodeRequest,
    expected: LifecycleEpisodeRequest,
) -> bool:
    """Accept the exact field projection emitted before operation state was bound."""
    v3_fields = {"operation_catalog", "current_source", "visible_operation_artifacts"}
    if (
        durable.schema_version != "2"
        or expected.schema_version != "3"
        or not v3_fields.isdisjoint(durable.model_fields_set)
        or durable.operation_catalog is not None
        or durable.current_source is not None
        or durable.visible_operation_artifacts
        or expected.operation_catalog is not None
        or expected.current_source is not None
        or expected.visible_operation_artifacts
    ):
        return False
    return durable == expected.model_copy(update={"schema_version": "2"})


def _matches_legacy_v1_episode_request(
    durable: LifecycleEpisodeRequest,
    expected: LifecycleEpisodeRequest,
) -> bool:
    """Accept only the exact field projection emitted by the v1 episode contract."""
    later_fields = {
        "evidence_request_catalog",
        "released_evidence_artifacts",
        "operation_catalog",
        "current_source",
        "visible_operation_artifacts",
    }
    if (
        durable.schema_version != "1"
        or expected.schema_version not in {"2", "3"}
        or not later_fields.isdisjoint(durable.model_fields_set)
        or durable.evidence_request_catalog is not None
        or durable.released_evidence_artifacts
        or durable.operation_catalog is not None
        or durable.current_source is not None
        or durable.visible_operation_artifacts
        or expected.evidence_request_catalog is not None
        or expected.released_evidence_artifacts
        or expected.operation_catalog is not None
        or expected.current_source is not None
        or expected.visible_operation_artifacts
    ):
        return False
    return durable == expected.model_copy(update={"schema_version": "1"})


def _episode_request_json(request: LifecycleEpisodeRequest) -> str:
    excluded: set[str] = set()
    if request.schema_version == "1":
        excluded.update({"evidence_request_catalog", "released_evidence_artifacts"})
    if request.schema_version in {"1", "2"}:
        excluded.update({"operation_catalog", "current_source", "visible_operation_artifacts"})
    payload = request.model_dump(mode="json", exclude=excluded)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _close_episode_failure(
    environment: LifecycleEpisodeEnvironment,
    request: LifecycleEpisodeRequest,
    *,
    package_dir: Path,
    run_dir: Path,
    failure_kind: str,
    provider_error: str | None,
) -> tuple[str, ...]:
    """Close host state, then reconcile environment artifacts without masking failure."""
    attempt_closed = _fail_episode_attempt_if_active(
        package_dir,
        run_dir,
        session_id=request.session_id,
        failure_kind=failure_kind,
    )
    if not attempt_closed:
        return ("host attempt was no longer active; environment artifacts were left unchanged",)
    reconciliation_errors: list[str] = []
    try:
        environment.record_failure(
            request,
            failure_kind=failure_kind,
            provider_error=provider_error,
        )
    except Exception as exc:
        reconciliation_errors.append(f"environment failure reconciliation failed: {exc}")
    try:
        _preserve_submission_candidate(
            submission=Path(request.submission_path),
            run_dir=Path(request.run_dir),
            checkpoint_id=request.checkpoint_id,
            session_id=request.session_id,
            attempt_id=request.attempt_id,
        )
    except Exception as exc:
        reconciliation_errors.append(f"submission candidate preservation failed: {exc}")
    return tuple(reconciliation_errors)


def _annotate_reconciliation_errors(error: BaseException, messages: tuple[str, ...]) -> None:
    for message in messages:
        error.add_note(message)


def _preserve_prior_attempt_submission(context: LifecycleEpisodeContext) -> None:
    """Move an unsubmitted candidate under its owning attempt before a retry."""
    submission = Path(context.submission_path)
    if not submission.exists():
        return
    checkpoint_run = next(item for item in context.checkpoint_runs if item.checkpoint_id == context.checkpoint_id)
    previous_attempt = checkpoint_run.last_attempt
    if previous_attempt is None:
        raise EvidenceLifecycleError("checkpoint submission exists before the first episode attempt")
    if previous_attempt.status is CheckpointAttemptStatus.SUBMITTED:
        raise EvidenceLifecycleError("submitted attempt left a mutable active checkpoint candidate")

    _preserve_submission_candidate(
        submission=submission,
        run_dir=Path(context.run_dir),
        checkpoint_id=context.checkpoint_id,
        session_id=previous_attempt.session_id,
        attempt_id=previous_attempt.attempt_id,
    )


def _preserve_submission_candidate(
    *,
    submission: Path,
    run_dir: Path,
    checkpoint_id: str,
    session_id: str,
    attempt_id: str,
) -> bool:
    """Atomically preserve and remove one attempt-owned mutable submission candidate."""
    if not submission.exists():
        return False
    if not submission.is_file():
        raise EvidenceLifecycleError(f"checkpoint submission path is not a file: {submission}")
    archive_dir = run_dir / "episodes" / checkpoint_id / session_id / "failed_submission"
    archive = archive_dir / "submission.json"
    mkdir_durable(archive_dir)
    if archive.exists():
        if not archive.is_file() or _sha256(archive) != _sha256(submission):
            raise EvidenceLifecycleError(f"preserved checkpoint candidate conflicts with retry source: {attempt_id}")
    else:
        _copy_file_atomic(submission, archive)
        fsync_tree(archive_dir)
    submission.unlink()
    fsync_directory(submission.parent)
    return True


def _fail_episode_attempt_if_active(
    package_dir: Path,
    run_dir: Path,
    *,
    session_id: str,
    failure_kind: str,
) -> bool:
    """Fail the allocated attempt without masking an already-committed transition."""
    package = Path(package_dir)
    run = Path(run_dir)
    try:
        spec = load_evidence_lifecycle_spec(package)
        state = _load_state(package, run, spec)
    except EvidenceLifecycleError:
        return False
    checkpoint_id = state.active_checkpoint_id
    if checkpoint_id is None:
        return False
    attempt = state.checkpoint(checkpoint_id).active_attempt
    if attempt is None or attempt.session_id != session_id:
        return False
    fail_checkpoint_attempt(
        package,
        run,
        session_id=session_id,
        failure_kind=failure_kind,
    )
    return True


def build_evidence_lifecycle_task_run_resolver(
    *,
    package_dir: Path,
    run_dir: Path,
    episode_environment: LifecycleEpisodeEnvironment,
    verifier: LifecycleVerifier,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Wrap a complete evidence lifecycle as one existing meta-harness task_run."""

    def resolve(runtime_result: dict[str, Any]) -> dict[str, Any]:
        lifecycle = run_evidence_lifecycle(
            package_dir,
            run_dir,
            episode_environment=episode_environment,
        )
        verification = validate_lifecycle_verification(verifier(Path(package_dir), Path(run_dir)))
        reward = float(verification["reward"])
        passed = bool(verification["passed"])
        process_id = runtime_result.get("process_id") or "process"
        spec = load_evidence_lifecycle_spec(Path(package_dir))
        return {
            "run_id": f"{process_id}.{spec.lifecycle_id}",
            "evidence": {
                "score": {"reward": reward, "passed": passed},
                "gates": copy.deepcopy(verification.get("gates", {})),
                "lifecycle": lifecycle,
                "verification": verification,
                "artifacts": {
                    "run_dir": str(Path(run_dir)),
                    "ledger": str(_ledger_path(Path(run_dir))),
                },
            },
        }

    return resolve


def read_evidence_lifecycle_state(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Read current lifecycle state without releasing or accepting evidence."""
    package = Path(package_dir)
    run = Path(run_dir)
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec)
    _assert_prior_submissions_unchanged(run, state)
    return _result_context(run, state)


def load_validated_lifecycle_submissions(
    package_dir: Path,
    run_dir: Path,
    *,
    require_complete: bool = True,
) -> dict[str, dict[str, Any]]:
    """Load immutable checkpoint submissions after validating state and archive hashes."""
    package = Path(package_dir)
    run = Path(run_dir)
    spec = load_evidence_lifecycle_spec(package)
    state = _load_state(package, run, spec)
    _assert_prior_submissions_unchanged(run, state)
    if require_complete and state.status != LifecycleRunStatus.COMPLETE:
        raise EvidenceLifecycleError("lifecycle run is not complete")
    return {
        checkpoint.checkpoint_id: _read_json(run / "episodes" / checkpoint.checkpoint_id / "submission.json")
        for checkpoint in state.checkpoint_runs
        if checkpoint.status == CheckpointRunStatus.SUBMITTED
    }


def validate_lifecycle_verification(
    payload: dict[str, Any] | LifecycleVerificationResult,
) -> dict[str, Any]:
    """Validate the shared verifier-result boundary and return its JSON representation."""
    result = (
        payload
        if isinstance(payload, LifecycleVerificationResult)
        else LifecycleVerificationResult.model_validate(payload)
    )
    excluded = {"semantic_metrics"} if result.semantic_metrics is None else None
    return result.model_dump(mode="json", exclude=excluded)


def _initialize_state(
    package_dir: Path,
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
    *,
    run_authorization_sha256: str | None,
) -> EvidenceLifecycleRunState:
    if _state_path(run_dir).exists():
        raise EvidenceLifecycleError(f"lifecycle state already exists: {_state_path(run_dir)}")
    _workspace(run_dir).mkdir(parents=True, exist_ok=True)
    supports_operations = any(item.conditional_operations is not None for item in spec.checkpoints)
    state = EvidenceLifecycleRunState(
        schema_version="5" if supports_operations else "4",
        lifecycle_id=spec.lifecycle_id,
        world_id=spec.world_id,
        lifecycle_spec_sha256=_spec_sha256(spec),
        package_sha256=_package_sha256(package_dir),
        run_authorization_sha256=run_authorization_sha256,
        checkpoint_runs=[
            CheckpointRunRecord(
                checkpoint_id=item.checkpoint_id,
                evidence_request_budget=(
                    item.conditional_evidence.request_budget if item.conditional_evidence is not None else 0
                ),
                evidence_request_budget_remaining=(
                    item.conditional_evidence.request_budget if item.conditional_evidence is not None else 0
                ),
                operation_budget=(
                    item.conditional_operations.operation_budget if item.conditional_operations is not None else 0
                ),
                operation_budget_remaining=(
                    item.conditional_operations.operation_budget if item.conditional_operations is not None else 0
                ),
            )
            for item in spec.checkpoints
        ],
    )
    _write_state(run_dir, state)
    if run_authorization_sha256 is not None:
        append_ledger_entry(
            _ledger_path(run_dir),
            process_id=spec.lifecycle_id,
            stage="run_authorization",
            status="authorized",
            summary={"run_authorization_sha256": run_authorization_sha256},
        )
    return state


def _load_state(
    package_dir: Path,
    run_dir: Path,
    spec: EvidenceLifecycleSpec,
    *,
    lock_held: bool = False,
) -> EvidenceLifecycleRunState:
    if not _state_path(run_dir).is_file():
        raise EvidenceLifecycleError(f"lifecycle state not found: {_state_path(run_dir)}")
    if not lock_held:
        with _lifecycle_state_lock(run_dir):
            return _load_state(package_dir, run_dir, spec, lock_held=True)
    path = _state_path(run_dir)
    if not path.is_file():
        raise EvidenceLifecycleError(f"lifecycle state not found: {path}")
    payload = _read_json(path)
    version = payload.get("schema_version")
    try:
        if version in {"4", "5"}:
            state = EvidenceLifecycleRunState.model_validate(payload)
            migrated = False
        elif version == "3":
            state = _migrate_v3_state(payload, spec)
            migrated = True
        elif version == "2":
            state = _migrate_v2_state(payload, package_dir, spec)
            migrated = True
        elif version in {None, "1"}:
            state = _migrate_legacy_state(payload, package_dir, spec)
            migrated = True
        else:
            raise EvidenceLifecycleError(f"unsupported lifecycle state schema version: {version}")
    except ValidationError as exc:
        raise EvidenceLifecycleError(f"invalid lifecycle state: {path}") from exc

    expected_ids = [checkpoint.checkpoint_id for checkpoint in spec.checkpoints]
    actual_ids = [checkpoint.checkpoint_id for checkpoint in state.checkpoint_runs]
    if state.lifecycle_id != spec.lifecycle_id or state.world_id != spec.world_id or actual_ids != expected_ids:
        raise EvidenceLifecycleError("run state does not match the lifecycle package")
    if state.lifecycle_spec_sha256 != _spec_sha256(spec):
        raise EvidenceLifecycleError("lifecycle contract does not match lifecycle run")
    if state.package_sha256 != _package_sha256(package_dir):
        raise EvidenceLifecycleError("package does not match lifecycle run")
    _validate_evidence_request_state_contract(state, spec)
    validate_lifecycle_operation_run_state(state, spec)
    if migrated:
        _write_state(run_dir, state)
    _recover_evidence_request_transactions(run_dir, spec, state)
    if state.schema_version == "5":
        _recover_lifecycle_operation_transactions(package_dir, run_dir, spec, state)
    _sync_transition_ledger(run_dir, state)
    _sync_evidence_request_ledger(run_dir, state)
    if state.schema_version == "5":
        _sync_lifecycle_operation_ledger(run_dir, state)
    return state


def _assert_prior_submissions_unchanged(run_dir: Path, state: EvidenceLifecycleRunState) -> None:
    if state.branch is not None:
        checkpoint_id = state.branch.branched_from_checkpoint_id
        branch_origin = _workspace(run_dir) / "branch_origin" / f"{checkpoint_id}.json"
        if not branch_origin.is_file() or _sha256(branch_origin) != state.branch.parent_submission_sha256:
            raise EvidenceLifecycleError(f"branch origin submission changed: {checkpoint_id}")
        branch_index = next(
            index for index, checkpoint in enumerate(state.checkpoint_runs) if checkpoint.checkpoint_id == checkpoint_id
        )
        action_state_sha256 = _branch_action_state_sha256(
            state,
            branch_index=branch_index,
            inherited_only=True,
        )
        if action_state_sha256 != state.branch.parent_action_state_sha256:
            raise EvidenceLifecycleError(f"branch origin action state changed: {checkpoint_id}")
    for completed in state.checkpoint_runs:
        if completed.status != CheckpointRunStatus.SUBMITTED:
            continue
        if completed.submission_path is None or completed.submission_sha256 is None:
            raise EvidenceLifecycleError(
                f"submitted checkpoint is missing immutable metadata: {completed.checkpoint_id}"
            )
        archive_path = run_dir / "episodes" / completed.checkpoint_id / "submission.json"
        if not archive_path.is_file() or _sha256(archive_path) != completed.submission_sha256:
            checkpoint_id = completed.checkpoint_id
            raise EvidenceLifecycleError(f"archived checkpoint submission changed: {checkpoint_id}")
        workspace_path = _workspace(run_dir) / completed.submission_path
        if not workspace_path.is_file() or _sha256(workspace_path) != completed.submission_sha256:
            checkpoint_id = completed.checkpoint_id
            raise EvidenceLifecycleError(f"prior checkpoint submission changed: {checkpoint_id}")


def _preflight_checkpoint(package_dir: Path, checkpoint: EvidenceCheckpointSpec) -> str:
    release_source = package_dir / checkpoint.release_path
    instruction_source = package_dir / checkpoint.instruction_path
    if not release_source.is_dir() or release_source.is_symlink():
        raise EvidenceLifecycleError(f"checkpoint release not found: {release_source}")
    if not instruction_source.is_file() or instruction_source.is_symlink():
        raise EvidenceLifecycleError(f"checkpoint instruction not found: {instruction_source}")
    if checkpoint.conditional_evidence is not None and (release_source / "requests").exists():
        raise EvidenceLifecycleError("checkpoint release uses the reserved requests namespace")
    return instruction_source.read_text(encoding="utf-8")


def _materialize_checkpoint_release(
    package_dir: Path,
    run_dir: Path,
    checkpoint: EvidenceCheckpointSpec,
    instruction: str,
) -> list[str]:
    workspace = _workspace(run_dir)
    staging_root = workspace / ".staging" / checkpoint.checkpoint_id
    release_destination = workspace / "inbox" / checkpoint.checkpoint_id
    checkpoint_instruction = workspace / "checkpoints" / checkpoint.checkpoint_id / "instruction.md"
    if staging_root.exists():
        shutil.rmtree(staging_root)
    if release_destination.exists():
        shutil.rmtree(release_destination)
    staging_release = staging_root / "release"
    staging_instruction = staging_root / "instruction.md"
    try:
        released_files = _copy_release(package_dir / checkpoint.release_path, staging_release)
        _write_text_atomic(staging_instruction, instruction)
        release_destination.parent.mkdir(parents=True, exist_ok=True)
        staging_release.replace(release_destination)
        _copy_file_atomic(staging_instruction, checkpoint_instruction)
        _write_text_atomic(workspace / "instruction.md", instruction)
        return released_files
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def _copy_checkpoint_instruction(
    package_dir: Path,
    workspace: Path,
    checkpoint: EvidenceCheckpointSpec,
) -> None:
    source = package_dir / checkpoint.instruction_path
    destination = workspace / "checkpoints" / checkpoint.checkpoint_id / "instruction.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _inherit_submission(
    parent_run: Path,
    branch_run: Path,
    checkpoint: EvidenceCheckpointSpec,
) -> None:
    source = parent_run / "episodes" / checkpoint.checkpoint_id / "submission.json"
    archive = branch_run / "episodes" / checkpoint.checkpoint_id / "submission.json"
    workspace_submission = _workspace(branch_run) / checkpoint.submission_path
    _copy_file_atomic(source, archive)
    _copy_file_atomic(source, workspace_submission)
    _write_json(
        branch_run / "episodes" / checkpoint.checkpoint_id / "result.json",
        {"inherited_from_parent": str(parent_run)},
    )


def _write_text_atomic(destination: Path, content: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(destination)


def _checkpoint_context(
    run_dir: Path,
    checkpoint: EvidenceCheckpointSpec,
    state: EvidenceLifecycleRunState,
) -> dict[str, Any]:
    workspace = _workspace(run_dir)
    checkpoint_run = state.checkpoint(checkpoint.checkpoint_id)
    context = {
        "lifecycle_id": state.lifecycle_id,
        "world_id": state.world_id,
        "lifecycle_spec_sha256": state.lifecycle_spec_sha256,
        "package_sha256": state.package_sha256,
        "status": state.status.value,
        "active_checkpoint_id": state.active_checkpoint_id,
        "checkpoint_id": checkpoint.checkpoint_id,
        "title": checkpoint.title,
        "workspace": str(workspace),
        "run_dir": str(run_dir),
        "instruction": (workspace / "instruction.md").read_text(encoding="utf-8"),
        "instruction_path": str(workspace / "instruction.md"),
        "submission_path": str(workspace / checkpoint.submission_path),
        "released_files": list(checkpoint_run.released_files),
        "completed_checkpoints": _completed_checkpoints(state),
        "checkpoint_runs": [item.model_dump(mode="json") for item in state.checkpoint_runs],
        "revisits": [item.model_dump(mode="json") for item in state.revisits],
        "transitions": [item.model_dump(mode="json") for item in state.transitions],
        "branch": state.branch.model_dump(mode="json") if state.branch is not None else None,
    }
    if state.run_authorization_sha256 is not None:
        context["run_authorization_sha256"] = state.run_authorization_sha256
    catalog = _evidence_request_catalog(checkpoint, checkpoint_run)
    if catalog is not None:
        context["evidence_request_catalog"] = catalog
    operation_catalog_path = workspace / "checkpoints" / checkpoint.checkpoint_id / "operations.json"
    current_source_path = workspace / "hydraulics" / "current-source.json"
    if current_source_path.is_file():
        context["current_source"] = _read_json(current_source_path)
    if operation_catalog_path.is_file():
        context["operation_catalog"] = _read_json(operation_catalog_path)
        if not current_source_path.is_file():
            raise EvidenceLifecycleError("operation catalogue exists without a visible current source")
    return context


def _result_context(run_dir: Path, state: EvidenceLifecycleRunState) -> dict[str, Any]:
    context = {
        "lifecycle_id": state.lifecycle_id,
        "world_id": state.world_id,
        "lifecycle_spec_sha256": state.lifecycle_spec_sha256,
        "package_sha256": state.package_sha256,
        "status": state.status.value,
        "workspace": str(_workspace(run_dir)),
        "run_dir": str(run_dir),
        "active_checkpoint_id": state.active_checkpoint_id,
        "completed_checkpoints": _completed_checkpoints(state),
        "checkpoint_runs": [item.model_dump(mode="json") for item in state.checkpoint_runs],
        "revisits": [item.model_dump(mode="json") for item in state.revisits],
        "transitions": [item.model_dump(mode="json") for item in state.transitions],
        "branch": state.branch.model_dump(mode="json") if state.branch is not None else None,
    }
    if state.run_authorization_sha256 is not None:
        context["run_authorization_sha256"] = state.run_authorization_sha256
    return context


def _completed_checkpoints(state: EvidenceLifecycleRunState) -> list[dict[str, Any]]:
    return [
        {
            "checkpoint_id": item.checkpoint_id,
            "submission_path": item.submission_path,
            "submission_sha256": item.submission_sha256,
            "released_files": list(item.released_files),
        }
        for item in state.checkpoint_runs
        if item.status == CheckpointRunStatus.SUBMITTED
    ]


def _attempt_context(attempt: CheckpointAttemptRecord) -> dict[str, Any]:
    return attempt.model_dump(mode="json")


def _migrate_v3_state(
    payload: dict[str, Any],
    spec: EvidenceLifecycleSpec,
) -> EvidenceLifecycleRunState:
    if any(checkpoint.conditional_evidence is not None for checkpoint in spec.checkpoints):
        raise EvidenceLifecycleError("v3 lifecycle state cannot be paired with conditional evidence")
    for checkpoint in payload.get("checkpoint_runs", []):
        if not isinstance(checkpoint, dict):
            raise EvidenceLifecycleError("invalid v3 lifecycle checkpoint state")
        if checkpoint.get("inherited_from_parent") and checkpoint.get("attempts"):
            raise EvidenceLifecycleError("v3 inherited checkpoint cannot contain attempts")
        forbidden = {
            "evidence_request_budget",
            "evidence_request_budget_remaining",
            "evidence_request_actions",
        }
        if forbidden.intersection(checkpoint):
            raise EvidenceLifecycleError("v3 lifecycle state cannot contain evidence request fields")
    migrated = copy.deepcopy(payload)
    for checkpoint in migrated.get("checkpoint_runs", []):
        checkpoint["evidence_request_budget"] = 0
        checkpoint["evidence_request_budget_remaining"] = 0
        checkpoint["evidence_request_actions"] = []
    migrated["schema_version"] = "3"
    branch = migrated.get("branch")
    if isinstance(branch, dict):
        branch.pop("parent_action_state_sha256", None)
        provisional = EvidenceLifecycleRunState.model_validate(migrated)
        branch_checkpoint_id = str(branch["branched_from_checkpoint_id"])
        branch_index = next(
            index
            for index, checkpoint in enumerate(provisional.checkpoint_runs)
            if checkpoint.checkpoint_id == branch_checkpoint_id
        )
        branch["parent_action_state_sha256"] = _branch_action_state_sha256(
            provisional,
            branch_index=branch_index,
            inherited_only=False,
        )
    migrated["schema_version"] = "4"
    return EvidenceLifecycleRunState.model_validate(migrated)


def _migrate_v2_state(
    payload: dict[str, Any],
    package_dir: Path,
    spec: EvidenceLifecycleSpec,
) -> EvidenceLifecycleRunState:
    if any(checkpoint.conditional_evidence is not None for checkpoint in spec.checkpoints):
        raise EvidenceLifecycleError("v2 lifecycle state cannot be paired with conditional evidence")
    migrated = copy.deepcopy(payload)
    migrated["lifecycle_spec_sha256"] = _spec_sha256(spec)
    migrated["package_sha256"] = _package_sha256(package_dir)
    migrated["schema_version"] = "3"
    branch = migrated.get("branch")
    if isinstance(branch, dict):
        branch.pop("parent_action_state_sha256", None)
        provisional = EvidenceLifecycleRunState.model_validate(migrated)
        branch_checkpoint_id = str(branch["branched_from_checkpoint_id"])
        branch_index = next(
            index
            for index, checkpoint in enumerate(provisional.checkpoint_runs)
            if checkpoint.checkpoint_id == branch_checkpoint_id
        )
        branch["parent_action_state_sha256"] = _branch_action_state_sha256(
            provisional,
            branch_index=branch_index,
            inherited_only=False,
        )
    migrated["schema_version"] = "4"
    return EvidenceLifecycleRunState.model_validate(migrated)


def _migrate_legacy_state(
    payload: dict[str, Any],
    package_dir: Path,
    spec: EvidenceLifecycleSpec,
) -> EvidenceLifecycleRunState:
    if any(checkpoint.conditional_evidence is not None for checkpoint in spec.checkpoints):
        raise EvidenceLifecycleError("legacy lifecycle state cannot be paired with conditional evidence")
    completed = {item["checkpoint_id"]: item for item in payload.get("completed_checkpoints", [])}
    active_checkpoint_id = payload.get("active_checkpoint_id")
    checkpoint_runs = []
    for checkpoint in spec.checkpoints:
        legacy = completed.get(checkpoint.checkpoint_id)
        if legacy is not None:
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    status=CheckpointRunStatus.SUBMITTED,
                    released_files=list(legacy.get("released_files", [])),
                    submission_path=legacy.get("submission_path"),
                    submission_sha256=legacy.get("submission_sha256"),
                )
            )
        elif checkpoint.checkpoint_id == active_checkpoint_id:
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    status=CheckpointRunStatus.ACTIVE,
                    released_files=list(payload.get("active_released_files", [])),
                )
            )
        else:
            checkpoint_runs.append(CheckpointRunRecord(checkpoint_id=checkpoint.checkpoint_id))
    return EvidenceLifecycleRunState(
        lifecycle_id=str(payload["lifecycle_id"]),
        world_id=str(payload["world_id"]),
        lifecycle_spec_sha256=_spec_sha256(spec),
        package_sha256=_package_sha256(package_dir),
        status=LifecycleRunStatus(str(payload.get("status", "awaiting_evidence_release"))),
        active_checkpoint_id=active_checkpoint_id,
        checkpoint_runs=checkpoint_runs,
    )


@contextmanager
def _lifecycle_state_lock(run_dir: Path) -> Iterator[None]:
    lock_dir = run_dir / ".locks"
    mkdir_durable(lock_dir)
    lock_path = lock_dir / "lifecycle-state.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _spec_sha256(spec: EvidenceLifecycleSpec) -> str:
    payload = json.dumps(
        canonical_evidence_lifecycle_spec_payload(spec),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _package_sha256(package_dir: Path) -> str:
    package = Path(package_dir)
    if not package.is_dir():
        raise EvidenceLifecycleError(f"lifecycle package not found: {package}")
    digest = hashlib.sha256()
    files = sorted(path for path in package.rglob("*") if path.is_file() or path.is_symlink())
    for path in files:
        if path.is_symlink():
            raise EvidenceLifecycleError(f"lifecycle packages may not contain symlinks: {path}")
        relative = path.relative_to(package).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()
