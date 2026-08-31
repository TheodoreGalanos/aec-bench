# ABOUTME: Applies pure lifecycle checkpoint transition decisions.
# ABOUTME: Returns detached canonical state with transition events for the lifecycle application.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aec_bench.contracts.evidence_lifecycle import EvidenceCheckpointSpec
from aec_bench.lifecycles.runtime.request_protocol import EvidenceLifecycleError
from aec_bench.lifecycles.runtime.state import (
    CheckpointAttemptRecord,
    CheckpointAttemptStatus,
    CheckpointRevisitRecord,
    CheckpointRunRecord,
    CheckpointRunStatus,
    EvidenceLifecycleRunState,
    LifecycleBranchRecord,
    LifecycleRunStatus,
    LifecycleTransitionKind,
    LifecycleTransitionRecord,
)


@dataclass(frozen=True, slots=True)
class LifecycleReduction:
    """Pure lifecycle decision output consumed by the application and stores."""

    state: EvidenceLifecycleRunState
    events: tuple[LifecycleTransitionRecord, ...] = ()


def reduce_release(
    state: EvidenceLifecycleRunState,
    *,
    checkpoint_id: str,
    released_files: tuple[str, ...],
    reason: str,
    previous_checkpoint_id: str | None,
) -> LifecycleReduction:
    """Release the next checkpoint in a detached state copy."""
    if state.status != LifecycleRunStatus.AWAITING_EVIDENCE_RELEASE or state.active_checkpoint_id is not None:
        raise EvidenceLifecycleError("lifecycle is not awaiting evidence release")
    checkpoint = _checkpoint(state, checkpoint_id)
    if checkpoint.status != CheckpointRunStatus.PENDING:
        raise EvidenceLifecycleError(f"checkpoint is not pending: {checkpoint_id}")
    updated = state.model_copy(deep=True)
    checkpoint = updated.checkpoint(checkpoint_id)
    checkpoint.status = CheckpointRunStatus.ACTIVE
    checkpoint.released_files = list(released_files)
    updated.active_checkpoint_id = checkpoint_id
    updated.status = LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION
    event = _transition(
        updated,
        kind=LifecycleTransitionKind.RELEASE,
        from_checkpoint_id=previous_checkpoint_id,
        to_checkpoint_id=checkpoint_id,
        reason=reason,
    )
    return _result(updated, event)


def reduce_submit(
    state: EvidenceLifecycleRunState,
    *,
    checkpoint_id: str,
    submission_path: str,
    submission_sha256: str,
    reason: str,
) -> LifecycleReduction:
    """Submit the active checkpoint in a detached state copy."""
    if state.status != LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION:
        raise EvidenceLifecycleError("lifecycle is not awaiting checkpoint submission")
    if state.active_checkpoint_id != checkpoint_id:
        raise EvidenceLifecycleError(f"checkpoint is not active: {checkpoint_id}")
    updated = state.model_copy(deep=True)
    checkpoint = updated.checkpoint(checkpoint_id)
    checkpoint.status = CheckpointRunStatus.SUBMITTED
    checkpoint.submission_path = submission_path
    checkpoint.submission_sha256 = submission_sha256
    if checkpoint.active_attempt is not None:
        checkpoint.active_attempt.status = CheckpointAttemptStatus.SUBMITTED
    updated.active_checkpoint_id = None
    updated.status = (
        LifecycleRunStatus.COMPLETE
        if all(item.status == CheckpointRunStatus.SUBMITTED for item in updated.checkpoint_runs)
        else LifecycleRunStatus.AWAITING_EVIDENCE_RELEASE
    )
    event = _transition(
        updated,
        kind=LifecycleTransitionKind.SUBMIT,
        from_checkpoint_id=checkpoint_id,
        to_checkpoint_id=None,
        reason=reason,
    )
    return _result(updated, event)


def reduce_open_attempt(
    state: EvidenceLifecycleRunState,
    *,
    checkpoint_id: str,
    session_id: str,
    execution_mode: str,
    episode_request_sha256: str | None,
) -> LifecycleReduction:
    """Open or resume one checkpoint attempt without performing I/O."""
    if state.active_checkpoint_id != checkpoint_id:
        raise EvidenceLifecycleError("no checkpoint is active")
    updated = state.model_copy(deep=True)
    checkpoint = updated.checkpoint(checkpoint_id)
    active_attempt = checkpoint.active_attempt
    if active_attempt is not None and active_attempt.session_id == session_id:
        if episode_request_sha256 is not None and active_attempt.episode_request_sha256 != episode_request_sha256:
            raise EvidenceLifecycleError("active checkpoint attempt request hash changed")
        return LifecycleReduction(state=updated)
    if active_attempt is not None:
        active_attempt.status = CheckpointAttemptStatus.INTERRUPTED
    previous = checkpoint.last_attempt
    attempt = CheckpointAttemptRecord(
        attempt_id=f"{checkpoint_id}.attempt-{len(checkpoint.attempts) + 1:03d}",
        session_id=session_id,
        sequence=len(checkpoint.attempts) + 1,
        execution_mode=execution_mode,
        status=CheckpointAttemptStatus.ACTIVE,
        resumed_from_attempt_id=previous.attempt_id if previous is not None else None,
        episode_request_sha256=episode_request_sha256,
    )
    checkpoint.attempts.append(attempt)
    return _result(updated, None)


def reduce_fail_attempt(
    state: EvidenceLifecycleRunState,
    *,
    checkpoint_id: str,
    session_id: str,
    failure_kind: str,
) -> LifecycleReduction:
    """Fail the active checkpoint attempt in a detached state copy."""
    if state.active_checkpoint_id != checkpoint_id:
        raise EvidenceLifecycleError("no checkpoint is active")
    updated = state.model_copy(deep=True)
    attempt = updated.checkpoint(checkpoint_id).active_attempt
    if attempt is None:
        raise EvidenceLifecycleError("no checkpoint attempt is active")
    if attempt.session_id != session_id:
        raise EvidenceLifecycleError(
            f"active attempt belongs to {attempt.session_id}; cannot fail it from {session_id}"
        )
    attempt.status = CheckpointAttemptStatus.FAILED
    attempt.failure_kind = failure_kind
    return _result(updated, None)


def reduce_revisit(
    state: EvidenceLifecycleRunState,
    *,
    checkpoint_id: str,
    reason: str,
) -> LifecycleReduction:
    """Record a revisit of a submitted checkpoint in a detached state copy."""
    updated = state.model_copy(deep=True)
    checkpoint = updated.checkpoint(checkpoint_id)
    if checkpoint.status != CheckpointRunStatus.SUBMITTED:
        raise EvidenceLifecycleError(f"checkpoint is not available for revisit: {checkpoint_id}")
    revisit = CheckpointRevisitRecord(
        revisit_id=f"revisit-{len(updated.revisits) + 1:03d}",
        checkpoint_id=checkpoint_id,
        requested_from_checkpoint_id=updated.active_checkpoint_id,
        reason=reason,
    )
    updated.revisits.append(revisit)
    event = _transition(
        updated,
        kind=LifecycleTransitionKind.REVISIT,
        from_checkpoint_id=revisit.requested_from_checkpoint_id,
        to_checkpoint_id=checkpoint_id,
        reason=reason,
    )
    return _result(updated, event)


def reduce_branch(
    parent_state: EvidenceLifecycleRunState,
    *,
    checkpoints: Sequence[EvidenceCheckpointSpec],
    branch_index: int,
    branch: LifecycleBranchRecord,
    checkpoint_id: str,
    reason: str,
) -> LifecycleReduction:
    """Construct inherited, reopened, and pending branch state and its transition."""
    if branch_index < 0 or branch_index >= len(checkpoints):
        raise EvidenceLifecycleError(f"branch checkpoint index is out of range: {branch_index}")
    if checkpoints[branch_index].checkpoint_id != checkpoint_id:
        raise EvidenceLifecycleError("branch checkpoint index does not match checkpoint id")
    parent_checkpoint = _checkpoint(parent_state, checkpoint_id)
    if parent_checkpoint.status != CheckpointRunStatus.SUBMITTED:
        raise EvidenceLifecycleError(f"checkpoint is not available for branching: {checkpoint_id}")
    checkpoint_runs: list[CheckpointRunRecord] = []
    for index, checkpoint in enumerate(checkpoints):
        if index < branch_index:
            inherited = _checkpoint(parent_state, checkpoint.checkpoint_id)
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
            operation_budget = (
                checkpoint.conditional_operations.operation_budget
                if checkpoint.conditional_operations is not None
                else 0
            )
            checkpoint_runs.append(
                CheckpointRunRecord(
                    checkpoint_id=checkpoint.checkpoint_id,
                    evidence_request_budget=request_budget,
                    evidence_request_budget_remaining=request_budget,
                    operation_budget=operation_budget,
                    operation_budget_remaining=operation_budget,
                )
            )
    updated = EvidenceLifecycleRunState(
        schema_version=parent_state.schema_version,
        lifecycle_id=parent_state.lifecycle_id,
        lifecycle_spec_sha256=parent_state.lifecycle_spec_sha256,
        package_sha256=parent_state.package_sha256,
        status=LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION,
        active_checkpoint_id=checkpoint_id,
        checkpoint_runs=checkpoint_runs,
        branch=branch.model_copy(deep=True),
    )
    event = _transition(
        updated,
        kind=LifecycleTransitionKind.BRANCH,
        from_checkpoint_id=checkpoint_id,
        to_checkpoint_id=checkpoint_id,
        reason=reason,
    )
    return _result(updated, event)


def _transition(
    state: EvidenceLifecycleRunState,
    *,
    kind: LifecycleTransitionKind,
    from_checkpoint_id: str | None,
    to_checkpoint_id: str | None,
    reason: str,
) -> LifecycleTransitionRecord:
    event = LifecycleTransitionRecord(
        transition_id=f"transition-{len(state.transitions) + 1:03d}",
        kind=kind,
        from_checkpoint_id=from_checkpoint_id,
        to_checkpoint_id=to_checkpoint_id,
        reason=reason,
    )
    state.transitions.append(event)
    return event


def _checkpoint(state: EvidenceLifecycleRunState, checkpoint_id: str) -> CheckpointRunRecord:
    try:
        return state.checkpoint(checkpoint_id)
    except KeyError as exc:
        raise EvidenceLifecycleError(f"unknown checkpoint: {checkpoint_id}") from exc


def _result(
    state: EvidenceLifecycleRunState,
    event: LifecycleTransitionRecord | None,
) -> LifecycleReduction:
    return LifecycleReduction(state=state, events=() if event is None else (event,))


__all__ = (
    "LifecycleReduction",
    "reduce_fail_attempt",
    "reduce_branch",
    "reduce_open_attempt",
    "reduce_release",
    "reduce_revisit",
    "reduce_submit",
)
