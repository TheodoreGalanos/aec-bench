# ABOUTME: Tests cancellation, retry backoff, and unknown-state handling in the local scheduler.
# ABOUTME: Uses provider-free work items to protect operational decisions without task execution semantics.

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan
from aec_bench.execution import FailureKind, RetryPolicy, TrialWorkItem
from aec_bench.execution.models import (
    AttemptProcessStatus,
    AttemptReceipt,
    AttemptResourceUsage,
    BackendCancellationResult,
    CancellationStatus,
    FailureClass,
    FailureClassification,
    ReconciliationState,
    WorkerOutcome,
)
from aec_bench.execution.operational import LeaseUnavailable, OperationalStore, OperationalStoreError, WorkItemRecord
from aec_bench.execution.scheduler import LocalScheduler


def _identity(kind: EntityKind, key: str) -> EntityIdentity:
    return EntityIdentity(id=new_entity_id(kind), key=key, version=1)


def _plan() -> RunPlan:
    run = _identity(EntityKind.RUN, "cancel-retry-run")
    return RunPlan.model_construct(
        plan_identity=_identity(EntityKind.PLAN, "cancel-retry-plan"),
        run_identity=run,
        state="ready",
        trials=(
            PlannedTrial.model_construct(
                trial_identity=_identity(EntityKind.TRIAL, "trial-1"),
                ordinal=1,
                run_identity=run,
                execution_family="artifact",
            ),
        ),
    )


def _item(plan: RunPlan, now: datetime, retry_policy: RetryPolicy | None = None) -> TrialWorkItem:
    trial = plan.trials[0]
    return TrialWorkItem(
        work_id=new_entity_id(EntityKind.WORK_ITEM),
        work_key="work-1",
        run_id=plan.run_id,
        plan_id=plan.plan_id,
        trial_id=trial.trial_id,
        ordinal=1,
        execution_family="artifact",
        backend="local",
        provider_route="default",
        model_route="default",
        resource_class="cpu-small",
        retry_policy=retry_policy or RetryPolicy(),
        state="planned",
        created_at=now,
        available_at=now,
    )


def _scheduler(tmp_path: Path, plan: RunPlan, item: TrialWorkItem) -> tuple[OperationalStore, LocalScheduler, datetime]:
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    store = OperationalStore(tmp_path / "operational.sqlite3")
    store.create_run(plan.run_id, spec_ref="runs/run/spec.json", status="ready", now=now)
    store.put_plan(plan.plan_id, run_id=plan.run_id, plan_ref="runs/run/plan.json", state="ready", now=now)
    scheduler = LocalScheduler(store, ExecutionPolicy(max_concurrency=1, retry_policy=item.retry_policy))
    scheduler.enqueue_ready_plan(plan, (item,))
    return store, scheduler, now


def test_run_cancellation_cancels_queued_work_and_stops_leasing(tmp_path: Path) -> None:
    plan = _plan()
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    store, scheduler, _ = _scheduler(tmp_path, plan, _item(plan, now))

    scheduler.request_cancellation(plan.run_id, now=now + timedelta(seconds=1))

    assert store.get_work_item(store.list_work_items(plan.run_id)[0].work_id).state == "cancelled"
    assert store.get_planned_trial(plan.trials[0].trial_id).state == "cancelled"
    assert scheduler.dispatch_once(lambda *_: None, owner="scheduler", now=now + timedelta(seconds=1)).idle


def test_work_item_persists_its_retry_policy(tmp_path: Path) -> None:
    plan = _plan()
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    policy = RetryPolicy(
        maximum_attempts=2,
        retryable_failure_kinds=(FailureKind.TRANSPORT_UNAVAILABLE,),
    )
    store, _, _ = _scheduler(tmp_path, plan, _item(plan, now, policy))

    assert store.list_work_items(plan.run_id)[0].retry_policy == policy


def test_retry_uses_new_attempt_id_and_persisted_backoff(tmp_path: Path) -> None:
    plan = _plan()
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    policy = RetryPolicy(
        maximum_attempts=2,
        retryable_failure_kinds=(FailureKind.WORKER_LOST_BEFORE_SUBMISSION,),
        backoff_seconds=10,
    )
    store, scheduler, _ = _scheduler(tmp_path, plan, _item(plan, now, policy))

    def lost_worker(*_: object) -> None:
        raise RuntimeError("worker stopped before submission")

    first = scheduler.dispatch_once(lost_worker, owner="scheduler", now=now)
    first_attempt = store.list_attempts(plan.trials[0].trial_id)[0]
    queued = store.get_work_item(first_attempt.work_id)
    assert first.retried_count == 1
    assert first.failed_count == 0
    assert first_attempt.retry_number == 0
    assert first_attempt.state == "failed"
    assert queued.state == "queued"
    assert queued.available_at == now + timedelta(seconds=10)

    assert scheduler.dispatch_once(lambda *_: None, owner="scheduler", now=now + timedelta(seconds=5)).idle
    second = scheduler.dispatch_once(lambda *_: None, owner="scheduler", now=now + timedelta(seconds=10))
    attempts = store.list_attempts(plan.trials[0].trial_id)
    assert second.succeeded_count == 1
    assert len(attempts) == 2
    assert attempts[1].attempt_id != attempts[0].attempt_id
    assert attempts[1].retry_number == 1


def test_retry_exhaustion_leaves_the_second_attempt_failed(tmp_path: Path) -> None:
    plan = _plan()
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    policy = RetryPolicy(
        maximum_attempts=2,
        retryable_failure_kinds=(FailureKind.WORKER_LOST_BEFORE_SUBMISSION,),
    )
    store, scheduler, _ = _scheduler(tmp_path, plan, _item(plan, now, policy))

    def lost_worker(*_: object) -> None:
        raise RuntimeError("worker stopped before submission")

    assert scheduler.dispatch_once(lost_worker, owner="scheduler", now=now).retried_count == 1
    exhausted = scheduler.dispatch_once(lost_worker, owner="scheduler", now=now)

    assert exhausted.retried_count == 0
    assert exhausted.failed_count == 1
    assert store.list_work_items(plan.run_id)[0].state == "failed"
    assert len(store.list_attempts(plan.trials[0].trial_id)) == 2


def test_non_retryable_failure_and_elapsed_window_do_not_requeue(tmp_path: Path) -> None:
    plan = _plan()
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    policy = RetryPolicy(
        maximum_attempts=2,
        retryable_failure_kinds=(FailureKind.TRANSPORT_UNAVAILABLE,),
    )
    store, scheduler, _ = _scheduler(tmp_path, plan, _item(plan, now, policy))

    non_retryable = scheduler.dispatch_once(
        lambda *_: (_ for _ in ()).throw(RuntimeError("lost")), owner="scheduler", now=now
    )

    assert non_retryable.failed_count == 1
    assert non_retryable.retried_count == 0
    assert store.list_work_items(plan.run_id)[0].state == "failed"

    other_plan = _plan()
    elapsed_policy = RetryPolicy(
        maximum_attempts=2,
        retryable_failure_kinds=(FailureKind.WORKER_LOST_BEFORE_SUBMISSION,),
        backoff_seconds=10,
        maximum_elapsed_seconds=5,
    )
    other_store, other_scheduler, _ = _scheduler(
        tmp_path / "elapsed", other_plan, _item(other_plan, now, elapsed_policy)
    )
    elapsed = other_scheduler.dispatch_once(
        lambda *_: (_ for _ in ()).throw(RuntimeError("lost")), owner="scheduler", now=now
    )

    assert elapsed.failed_count == 1
    assert elapsed.retried_count == 0
    assert other_store.list_work_items(other_plan.run_id)[0].state == "failed"


class _CancellationBackend:
    def __init__(self, status: str) -> None:
        self.status = status

    def cancel(self, *_: object) -> BackendCancellationResult:
        return BackendCancellationResult(status=self.status, message=f"cancel {self.status}")


def _active_attempt(
    tmp_path: Path, *, with_submission: bool = True, retry_policy: RetryPolicy | None = None
) -> tuple[OperationalStore, LocalScheduler, RunPlan, WorkItemRecord, datetime]:
    plan = _plan()
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    store, scheduler, _ = _scheduler(tmp_path, plan, _item(plan, now, retry_policy))
    item, lease = store.lease_next_work_item(owner="scheduler", now=now, ttl=timedelta(minutes=5)) or (None, None)
    assert item is not None and lease is not None
    attempt = store.create_attempt_for_lease(
        item.work_id,
        trial_id=item.trial_id,
        lease_id=lease.lease_id,
        candidate_index=1,
        retry_number=0,
        now=now,
    )
    store.update_work_item(item.work_id, state="running", now=now)
    store.update_planned_trial(item.trial_id, state="running", now=now)
    store.transition_attempt(attempt.attempt_id, state="running", now=now)
    if with_submission:
        store.record_backend_submission(
            new_entity_id(EntityKind.BACKEND_SUBMISSION),
            attempt_id=attempt.attempt_id,
            backend=item.backend,
            state="running",
            external_id="external-1",
            external_work_id="trial-1",
            now=now,
        )
    return store, scheduler, plan, item, now


@pytest.mark.parametrize("status", ("unknown", "unsupported", "rejected"))
def test_cancellation_uncertain_keeps_work_unknown(tmp_path: Path, status: str) -> None:
    store, scheduler, plan, item, now = _active_attempt(tmp_path)

    scheduler.request_cancellation(plan.run_id, now=now + timedelta(seconds=1))
    report = scheduler.cancel_active(
        plan.run_id,
        owner="scheduler",
        backends={"local": _CancellationBackend(status)},
        now=now + timedelta(seconds=1),
    )

    assert report.unknown_count == 1
    assert store.get_work_item(item.work_id).state == "unknown"
    assert store.get_attempt(store.list_attempts(plan.trials[0].trial_id)[0].attempt_id).state == "unknown"


def test_cancellation_without_external_submission_is_confirmed(tmp_path: Path) -> None:
    store, scheduler, plan, item, now = _active_attempt(tmp_path, with_submission=False)

    scheduler.request_cancellation(plan.run_id, now=now + timedelta(seconds=1))
    report = scheduler.cancel_active(
        plan.run_id,
        owner="scheduler",
        backends={},
        now=now + timedelta(seconds=1),
    )

    assert report.cancelled_count == 1
    assert store.get_work_item(item.work_id).state == "cancelled"


def test_late_worker_result_does_not_overwrite_confirmed_cancellation(tmp_path: Path) -> None:
    plan = _plan()
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    store, scheduler, _ = _scheduler(tmp_path, plan, _item(plan, now))

    def worker(*_: object) -> None:
        scheduler.request_cancellation(plan.run_id, now=now + timedelta(seconds=1))
        scheduler.cancel_active(plan.run_id, owner="scheduler", backends={}, now=now + timedelta(seconds=1))

    report = scheduler.dispatch_once(worker, owner="scheduler", now=now)

    assert report.succeeded_count == 0
    assert store.list_work_items(plan.run_id)[0].state == "cancelled"
    assert store.get_planned_trial(plan.trials[0].trial_id).state == "cancelled"


def test_unknown_lease_release_reclassifies_completed_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    store, scheduler, _ = _scheduler(tmp_path, plan, _item(plan, now))

    def fail_release(*_: object, **__: object) -> None:
        raise OperationalStoreError("lease release status is unknown")

    monkeypatch.setattr(store, "release_lease", fail_release)

    report = scheduler.dispatch_once(lambda *_: None, owner="scheduler", now=now)

    assert report.succeeded_count == 0
    assert report.unknown_count == 1
    assert store.list_work_items(plan.run_id)[0].state == "unknown"
    assert store.list_attempts(plan.trials[0].trial_id)[0].state == "unknown"


def test_expired_lease_with_submission_requires_reconciliation_before_retry(tmp_path: Path) -> None:
    store, _, plan, item, now = _active_attempt(tmp_path)
    attempt = store.list_attempts(plan.trials[0].trial_id)[0]
    submission = store.list_backend_submissions(attempt.attempt_id)[0]

    with pytest.raises(LeaseUnavailable, match="not queued"):
        store.acquire_lease(
            item.work_id,
            owner="replacement-worker",
            now=now + timedelta(minutes=6),
            ttl=timedelta(minutes=5),
        )

    assert store.get_work_item(item.work_id).state == "unknown"
    assert store.get_attempt(attempt.attempt_id).state == "unknown"
    assert store.get_attempt(attempt.attempt_id).reconciliation_state == "pending"
    assert store.get_backend_submission(submission.submission_id).state == "unknown"


class _ReconciliationBackend:
    def __init__(self, outcome: WorkerOutcome) -> None:
        self.outcome = outcome

    def cancel(self, *_: object) -> BackendCancellationResult:
        return BackendCancellationResult(status="confirmed", message="cancelled")

    def reconcile(self, *_: object) -> WorkerOutcome:
        return self.outcome


@pytest.mark.parametrize(
    ("unknown_state_policy", "expected_retries", "expected_state"),
    (("reconcile_before_retry", 1, "queued"), ("never_retry", 0, "failed")),
)
def test_unknown_attempt_must_reconcile_before_policy_allows_retry(
    tmp_path: Path,
    unknown_state_policy: str,
    expected_retries: int,
    expected_state: str,
) -> None:
    policy = RetryPolicy(
        maximum_attempts=2,
        retryable_failure_kinds=(FailureKind.RESULT_IMPORT_FAILED,),
        unknown_state_policy=unknown_state_policy,
    )
    store, scheduler, plan, item, now = _active_attempt(tmp_path, retry_policy=policy)
    attempt = store.list_attempts(plan.trials[0].trial_id)[0]
    submission = store.list_backend_submissions(attempt.attempt_id)[0]
    unknown_failure = FailureClassification(
        failure_class=FailureClass.UNKNOWN,
        kind=FailureKind.UNKNOWN_EXTERNAL_STATE,
        message="host lost the remote result",
    )
    store.transition_attempt(
        attempt.attempt_id,
        state="unknown",
        failure=unknown_failure,
        reconciliation_state="pending",
        now=now,
    )
    store.transition_backend_submission(
        submission.submission_id,
        state="unknown",
        reconciliation_state="pending",
        now=now,
    )
    store.update_work_item(item.work_id, state="unknown", now=now)
    store.update_planned_trial(item.trial_id, state="unknown", now=now)
    receipt = AttemptReceipt(
        receipt_id=new_entity_id(EntityKind.RECEIPT),
        receipt_key="reconciled-import-failure",
        attempt_id=attempt.attempt_id,
        backend=item.backend,
        submission_id=submission.submission_id,
        requested_condition=_identity(EntityKind.AGENT_CONDITION, "condition"),
        started_at=now,
        finished_at=now + timedelta(seconds=1),
        process_status=AttemptProcessStatus.FAILED,
        cancellation_status=CancellationStatus.NOT_REQUESTED,
        resource_usage=AttemptResourceUsage(wall_seconds=1.0),
        failure=FailureClassification(
            failure_class=FailureClass.INFRASTRUCTURE,
            kind=FailureKind.RESULT_IMPORT_FAILED,
            message="remote result could not be imported",
        ),
        reconciliation_status=ReconciliationState.RECONCILED,
    )
    backend = _ReconciliationBackend(WorkerOutcome(terminal_state="failed", receipts=(receipt,)))

    report = scheduler.reconcile_unknown(plan.run_id, backends={"local": backend}, now=now + timedelta(seconds=1))

    assert report.retried_count == expected_retries
    assert store.get_work_item(item.work_id).state == expected_state
    assert store.get_attempt(attempt.attempt_id).state == "failed"
    assert store.get_attempt(attempt.attempt_id).reconciliation_state == "reconciled"
