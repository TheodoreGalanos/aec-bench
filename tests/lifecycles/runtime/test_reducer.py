# ABOUTME: Tests pure lifecycle transition decisions without filesystem effects.
# ABOUTME: Covers state isolation, transition identities, and public lifecycle errors.

from __future__ import annotations

import pytest

from aec_bench.contracts.evidence_lifecycle import (
    ConditionalEvidenceSpec,
    EvidenceCheckpointSpec,
    EvidenceRequestSpec,
)
from aec_bench.lifecycles.runtime.reducer import (
    LifecycleReduction,
    reduce_branch,
    reduce_fail_attempt,
    reduce_open_attempt,
    reduce_release,
    reduce_revisit,
    reduce_submit,
)
from aec_bench.lifecycles.runtime.request_protocol import EvidenceLifecycleError
from aec_bench.lifecycles.runtime.state import (
    CheckpointAttemptRecord,
    CheckpointAttemptStatus,
    CheckpointRunRecord,
    CheckpointRunStatus,
    EvidenceLifecycleRunState,
    LifecycleBranchRecord,
    LifecycleRunStatus,
)


def _state(*checkpoint_runs: CheckpointRunRecord, **updates: object) -> EvidenceLifecycleRunState:
    return EvidenceLifecycleRunState(
        lifecycle_id="lifecycle.test",
        lifecycle_spec_sha256="a" * 64,
        package_sha256="b" * 64,
        checkpoint_runs=list(checkpoint_runs),
        **updates,
    )


def _submitted(checkpoint_id: str = "first") -> CheckpointRunRecord:
    return CheckpointRunRecord(
        checkpoint_id=checkpoint_id,
        status=CheckpointRunStatus.SUBMITTED,
        submission_path=f"submissions/{checkpoint_id}.json",
        submission_sha256="c" * 64,
    )


def _active(checkpoint_id: str = "first") -> CheckpointRunRecord:
    return CheckpointRunRecord(checkpoint_id=checkpoint_id, status=CheckpointRunStatus.ACTIVE)


def _checkpoint_spec(checkpoint_id: str, *, request_budget: int | None = None) -> EvidenceCheckpointSpec:
    conditional_evidence = None
    if request_budget is not None:
        conditional_evidence = ConditionalEvidenceSpec(
            request_budget=request_budget,
            requests=tuple(
                EvidenceRequestSpec(
                    request_id=f"request-{index}",
                    title="Request",
                    description="Request declared evidence.",
                )
                for index in range(request_budget)
            ),
        )
    return EvidenceCheckpointSpec(
        checkpoint_id=checkpoint_id,
        title=checkpoint_id,
        release_path=f"releases/{checkpoint_id}",
        instruction_path=f"instructions/{checkpoint_id}.md",
        submission_path=f"submissions/{checkpoint_id}.json",
        conditional_evidence=conditional_evidence,
    )


def test_release_returns_detached_state_and_event() -> None:
    original = _state(CheckpointRunRecord(checkpoint_id="first"))

    reduction = reduce_release(
        original,
        checkpoint_id="first",
        released_files=("source/input.txt",),
        previous_checkpoint_id=None,
        reason="release",
    )

    assert isinstance(reduction, LifecycleReduction)
    assert original.status == LifecycleRunStatus.AWAITING_EVIDENCE_RELEASE
    assert original.checkpoint("first").status == CheckpointRunStatus.PENDING
    assert reduction.state.status == LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION
    assert reduction.state.checkpoint("first").released_files == ["source/input.txt"]
    assert reduction.events[0].transition_id == "transition-001"


def test_submit_updates_attempt_and_does_not_mutate_input() -> None:
    attempt = CheckpointAttemptRecord(
        attempt_id="first.attempt-001",
        session_id="session-001",
        sequence=1,
        execution_mode="fresh_context",
        status=CheckpointAttemptStatus.ACTIVE,
    )
    original = _state(
        _active("first").model_copy(update={"attempts": [attempt]}),
        status=LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION,
        active_checkpoint_id="first",
    )

    reduction = reduce_submit(
        original,
        checkpoint_id="first",
        submission_path="submissions/first.json",
        submission_sha256="d" * 64,
        reason="submit",
    )

    assert original.checkpoint("first").status == CheckpointRunStatus.ACTIVE
    assert original.checkpoint("first").active_attempt is not None
    assert reduction.state.checkpoint("first").status == CheckpointRunStatus.SUBMITTED
    assert reduction.state.checkpoint("first").attempts[0].status == CheckpointAttemptStatus.SUBMITTED


def test_open_and_fail_attempt_keep_prior_state_unchanged() -> None:
    original = _state(
        _active(),
        status=LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION,
        active_checkpoint_id="first",
    )
    opened = reduce_open_attempt(
        original,
        checkpoint_id="first",
        session_id="session-001",
        execution_mode="fresh_context",
        episode_request_sha256=None,
    )
    failed = reduce_fail_attempt(
        opened.state,
        checkpoint_id="first",
        session_id="session-001",
        failure_kind="provider_error",
    )

    assert original.checkpoint("first").attempts == []
    assert opened.state.checkpoint("first").active_attempt is not None
    assert failed.state.checkpoint("first").last_attempt is not None
    assert failed.state.checkpoint("first").last_attempt.status == CheckpointAttemptStatus.FAILED


def test_revisit_returns_detached_state_and_rejects_unsubmitted_checkpoint() -> None:
    original = _state(_submitted())
    reduction = reduce_revisit(original, checkpoint_id="first", reason="inspect")

    assert original.revisits == []
    assert reduction.state.revisits[0].revisit_id == "revisit-001"
    assert reduction.events[0].kind.value == "revisit"

    with pytest.raises(EvidenceLifecycleError, match="checkpoint is not available for revisit: second"):
        reduce_revisit(_state(CheckpointRunRecord(checkpoint_id="second")), checkpoint_id="second", reason="inspect")


def test_branch_constructs_canonical_state_and_does_not_mutate_parent() -> None:
    parent = _state(
        _submitted("first"),
        _submitted("second"),
        run_authorization_sha256="f" * 64,
    )
    branch = LifecycleBranchRecord(
        branch_id="branch-001",
        parent_run_dir="/tmp/parent",
        branched_from_checkpoint_id="first",
        parent_submission_sha256="c" * 64,
        parent_action_state_sha256="e" * 64,
        reason="recheck",
    )

    reduction = reduce_branch(
        parent,
        checkpoints=[_checkpoint_spec("first"), _checkpoint_spec("second")],
        branch_index=1,
        branch=branch,
        checkpoint_id="second",
        reason="recheck",
    )

    assert parent.branch is None
    assert parent.status == LifecycleRunStatus.AWAITING_EVIDENCE_RELEASE
    assert reduction.state.branch is not None
    assert reduction.state.active_checkpoint_id == "second"
    assert reduction.state.status == LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION
    assert reduction.state.run_authorization_sha256 is None
    assert reduction.events[0].kind.value == "branch"


def test_branch_rejects_incomplete_inherited_dependency() -> None:
    parent = EvidenceLifecycleRunState.model_construct(
        lifecycle_id="lifecycle.test",
        lifecycle_spec_sha256="a" * 64,
        package_sha256="b" * 64,
        status=LifecycleRunStatus.AWAITING_CHECKPOINT_SUBMISSION,
        active_checkpoint_id="second",
        checkpoint_runs=[_submitted("first"), _active("second"), _submitted("third")],
        revisits=[],
        transitions=[],
        branch=None,
    )
    branch = LifecycleBranchRecord(
        branch_id="branch-001",
        parent_run_dir="/tmp/parent",
        branched_from_checkpoint_id="third",
        parent_submission_sha256="c" * 64,
        parent_action_state_sha256="e" * 64,
        reason="recheck",
    )

    with pytest.raises(EvidenceLifecycleError, match="parent checkpoint dependency is incomplete: second"):
        reduce_branch(
            parent,
            checkpoints=[_checkpoint_spec("first"), _checkpoint_spec("second"), _checkpoint_spec("third")],
            branch_index=2,
            branch=branch,
            checkpoint_id="third",
            reason="recheck",
        )


def test_branch_rejects_invalid_index_and_unsubmitted_target() -> None:
    parent = _state(_submitted("first"), CheckpointRunRecord(checkpoint_id="second"))
    branch = LifecycleBranchRecord(
        branch_id="branch-001",
        parent_run_dir="/tmp/parent",
        branched_from_checkpoint_id="second",
        parent_submission_sha256="c" * 64,
        parent_action_state_sha256="e" * 64,
        reason="recheck",
    )
    checkpoints = [_checkpoint_spec("first"), _checkpoint_spec("second")]

    with pytest.raises(EvidenceLifecycleError, match="branch checkpoint index is out of range: 2"):
        reduce_branch(
            parent,
            checkpoints=checkpoints,
            branch_index=2,
            branch=branch,
            checkpoint_id="second",
            reason="recheck",
        )
    with pytest.raises(EvidenceLifecycleError, match="branch checkpoint index does not match checkpoint id"):
        reduce_branch(
            parent,
            checkpoints=checkpoints,
            branch_index=0,
            branch=branch,
            checkpoint_id="second",
            reason="recheck",
        )
    with pytest.raises(EvidenceLifecycleError, match="checkpoint is not available for branching: second"):
        reduce_branch(
            parent,
            checkpoints=checkpoints,
            branch_index=1,
            branch=branch,
            checkpoint_id="second",
            reason="recheck",
        )


def test_branch_initialises_future_checkpoint_budgets_from_specs() -> None:
    parent = _state(_submitted("first"), _submitted("second"))
    branch = LifecycleBranchRecord(
        branch_id="branch-001",
        parent_run_dir="/tmp/parent",
        branched_from_checkpoint_id="second",
        parent_submission_sha256="c" * 64,
        parent_action_state_sha256="e" * 64,
        reason="recheck",
    )

    reduction = reduce_branch(
        parent,
        checkpoints=[
            _checkpoint_spec("first"),
            _checkpoint_spec("second"),
            _checkpoint_spec("third", request_budget=2),
        ],
        branch_index=1,
        branch=branch,
        checkpoint_id="second",
        reason="recheck",
    )

    future = reduction.state.checkpoint("third")
    assert future.evidence_request_budget == 2
    assert future.evidence_request_budget_remaining == 2


def test_reducer_maps_invalid_checkpoint_to_evidence_lifecycle_error() -> None:
    with pytest.raises(EvidenceLifecycleError, match="unknown checkpoint: missing"):
        reduce_release(
            _state(CheckpointRunRecord(checkpoint_id="first")),
            checkpoint_id="missing",
            released_files=(),
            previous_checkpoint_id=None,
            reason="release",
        )
