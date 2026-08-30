# ABOUTME: Defines focused tests for provider-neutral PRD3 execution contracts.
# ABOUTME: Protects strict identity, state, timestamp, failure, receipt, and finalization boundaries.

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.execution.models import (
    Attempt,
    AttemptReceipt,
    AttemptResourceUsage,
    BackendSubmission,
    FailureClass,
    FailureClassification,
    FinalizationState,
    Lease,
    LeaseState,
    RetryPolicy,
    TrialFinalization,
    TrialWorkItem,
    WorkItemState,
)


def _id(kind: EntityKind) -> str:
    return str(new_entity_id(kind))


def test_work_item_requires_uuidv7_keys_and_explicit_execution_policy() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    item = TrialWorkItem(
        work_id=_id(EntityKind.WORK_ITEM),
        work_key="0042-monitoring-dam-seepage-prime-rep-03",
        run_id=_id(EntityKind.RUN),
        plan_id=_id(EntityKind.PLAN),
        trial_id=_id(EntityKind.TRIAL),
        ordinal=42,
        execution_family="world",
        backend="local",
        resource_class="cpu-small",
        retry_policy=RetryPolicy(maximum_attempts=2, retryable_failure_kinds=("transport_unavailable",)),
        state=WorkItemState.PLANNED,
        created_at=now,
        available_at=now,
    )

    assert item.work_key == "0042-monitoring-dam-seepage-prime-rep-03"
    assert item.current_attempt_number == 0
    with pytest.raises(ValueError, match="valid UUID"):
        TrialWorkItem(
            work_id="work-1",
            work_key="work-1",
            run_id=_id(EntityKind.RUN),
            plan_id=_id(EntityKind.PLAN),
            trial_id=_id(EntityKind.TRIAL),
            ordinal=1,
            execution_family="artifact",
            backend="local",
            resource_class="cpu-small",
            retry_policy=RetryPolicy(),
            state=WorkItemState.PLANNED,
            created_at=now,
            available_at=now,
        )

    with pytest.raises(ValueError, match="infrastructure failures"):
        RetryPolicy(maximum_attempts=2, retryable_failure_kinds=("invalid_output",))
    with pytest.raises(ValueError, match="requires retryable"):
        RetryPolicy(maximum_attempts=2)


def test_attempt_requires_consistent_timestamps_and_failure_classification() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    failure = FailureClassification(
        failure_class=FailureClass.INFRASTRUCTURE,
        kind="transport_unavailable",
        message="provider connection reset",
    )
    attempt = Attempt(
        attempt_id=_id(EntityKind.ATTEMPT),
        attempt_key="trial-0042-attempt-01",
        run_id=_id(EntityKind.RUN),
        trial_id=_id(EntityKind.TRIAL),
        work_id=_id(EntityKind.WORK_ITEM),
        attempt_number=1,
        lease_id=_id(EntityKind.LEASE),
        worker_id="worker-a",
        state="failed",
        started_at=now,
        finished_at=now + timedelta(seconds=2),
        failure=failure,
    )

    assert attempt.failure == failure
    assert attempt.version == 1
    with pytest.raises(ValueError, match="requires class"):
        FailureClassification(
            failure_class=FailureClass.BENCHMARK,
            kind="transport_unavailable",
            message="wrong class",
        )
    with pytest.raises(ValueError, match="failure classification"):
        Attempt(
            attempt_id=_id(EntityKind.ATTEMPT),
            attempt_key="trial-0042-attempt-02",
            run_id=_id(EntityKind.RUN),
            trial_id=_id(EntityKind.TRIAL),
            work_id=_id(EntityKind.WORK_ITEM),
            attempt_number=2,
            state="failed",
            started_at=now,
            finished_at=now + timedelta(seconds=1),
        )


def test_lease_and_receipt_contracts_bind_ids_and_reconciliation_state() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    lease = Lease(
        lease_id=_id(EntityKind.LEASE),
        work_id=_id(EntityKind.WORK_ITEM),
        worker_id="worker-a",
        acquired_at=now,
        expires_at=now + timedelta(minutes=5),
        heartbeat_at=now,
        state=LeaseState.ACTIVE,
    )
    receipt = AttemptReceipt(
        receipt_id=_id(EntityKind.RECEIPT),
        receipt_key="trial-0042-attempt-01-receipt",
        attempt_id=_id(EntityKind.ATTEMPT),
        backend="local",
        submission_id=_id(EntityKind.BACKEND_SUBMISSION),
        requested_condition={
            "id": _id(EntityKind.AGENT_CONDITION),
            "key": "prime-baseline",
            "version": 1,
        },
        started_at=now,
        finished_at=now + timedelta(seconds=1),
        process_status="succeeded",
        cancellation_status="not_requested",
        resource_usage=AttemptResourceUsage(wall_seconds=1.0),
        output_references=(
            {
                "artifact_id": "outputs/result.json",
                "sha256": "0" * 64,
                "size_bytes": 1,
                "media_type": "application/json",
            },
        ),
        reconciliation_status="not_required",
    )

    assert lease.expires_at > lease.heartbeat_at
    assert receipt.reconciliation_status == "not_required"
    assert receipt.version == 1


def test_terminal_attempt_and_receipt_require_truthful_outcomes() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="result_ref"):
        Attempt(
            attempt_id=_id(EntityKind.ATTEMPT),
            attempt_key="trial-0042-attempt-01",
            run_id=_id(EntityKind.RUN),
            trial_id=_id(EntityKind.TRIAL),
            work_id=_id(EntityKind.WORK_ITEM),
            attempt_number=1,
            backend_submission_id=_id(EntityKind.BACKEND_SUBMISSION),
            state="succeeded",
            started_at=now,
            finished_at=now + timedelta(seconds=1),
        )


def test_backend_submission_requires_ordered_aware_timestamps() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    submission = BackendSubmission(
        submission_id=_id(EntityKind.BACKEND_SUBMISSION),
        attempt_id=_id(EntityKind.ATTEMPT),
        backend="local",
        external_id="job-1",
        state="accepted",
        submitted_at=now,
        updated_at=now + timedelta(seconds=1),
    )

    assert submission.external_id == "job-1"
    with pytest.raises(ValueError, match="must not precede"):
        BackendSubmission(
            submission_id=_id(EntityKind.BACKEND_SUBMISSION),
            attempt_id=_id(EntityKind.ATTEMPT),
            backend="local",
            external_id="job-1",
            state="accepted",
            submitted_at=now,
            updated_at=now - timedelta(seconds=1),
        )
    with pytest.raises(ValueError, match="requires external_id"):
        BackendSubmission(
            submission_id=_id(EntityKind.BACKEND_SUBMISSION),
            attempt_id=_id(EntityKind.ATTEMPT),
            backend="local",
            state="running",
            submitted_at=now,
            updated_at=now,
        )

    with pytest.raises(ValueError, match="failure classification"):
        AttemptReceipt(
            receipt_id=_id(EntityKind.RECEIPT),
            receipt_key="trial-0042-attempt-01-receipt",
            attempt_id=_id(EntityKind.ATTEMPT),
            backend="local",
            submission_id=_id(EntityKind.BACKEND_SUBMISSION),
            requested_condition={
                "id": _id(EntityKind.AGENT_CONDITION),
                "key": "prime-baseline",
                "version": 1,
            },
            started_at=now,
            finished_at=now + timedelta(seconds=1),
            process_status="unknown",
            cancellation_status="unknown",
            resource_usage=AttemptResourceUsage(wall_seconds=1.0),
            reconciliation_status="unknown",
        )


def test_finalization_is_versioned_and_rejects_self_supersession() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    finalization_id = _id(EntityKind.RECEIPT)
    finalization = TrialFinalization(
        finalization_id=finalization_id,
        trial_id=_id(EntityKind.TRIAL),
        attempt_id=_id(EntityKind.ATTEMPT),
        record_version=1,
        trial_record_ref="runs/run-1/trials/trial-1.json",
        published_at=now,
        state=FinalizationState.CURRENT,
    )

    assert finalization.record_version == 1
    with pytest.raises(ValueError, match="must not supersede itself"):
        TrialFinalization(
            finalization_id=finalization_id,
            trial_id=_id(EntityKind.TRIAL),
            attempt_id=_id(EntityKind.ATTEMPT),
            record_version=1,
            trial_record_ref="runs/run-1/trials/trial-1.json",
            published_at=now,
            state=FinalizationState.CURRENT,
            supersedes_finalization_id=finalization.finalization_id,
        )
