# ABOUTME: Exercises a provider-free 500-trial execution run across all current task-family labels.
# ABOUTME: Proves bounded dispatch, restart discovery, exact accounting, cancellation, retry, and reconciliation facts.

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from time import sleep
from uuid import UUID

import pytest

from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan
from aec_bench.contracts.trial_record import TrialTaskKind
from aec_bench.execution.models import (
    AttemptProcessStatus,
    AttemptReceipt,
    AttemptResourceUsage,
    CancellationStatus,
    FailureClass,
    FailureClassification,
    FailureKind,
    ReconciliationState,
    RetryPolicy,
    TrialWorkItem,
    WorkerOutcome,
)
from aec_bench.execution.operational import (
    AttemptRecord,
    LeaseUnavailable,
    OperationalStore,
    WorkItemRecord,
)
from aec_bench.execution.progress import project_run_progress
from aec_bench.execution.scheduler import LocalScheduler

_FAMILIES: tuple[TrialTaskKind, ...] = ("artifact", "world", "lifecycle")
_TRIAL_COUNT = 500
_MAX_CONCURRENCY = 16
_NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


def _identity(kind: EntityKind, key: str) -> EntityIdentity:
    return EntityIdentity(id=new_entity_id(kind), key=key, version=1)


def _plan(trial_count: int = _TRIAL_COUNT, *, key: str = "scale-plan") -> RunPlan:
    run_identity = _identity(EntityKind.RUN, f"{key}-run")
    trials = tuple(
        PlannedTrial.model_construct(
            trial_identity=_identity(EntityKind.TRIAL, f"{key}-trial-{ordinal}"),
            ordinal=ordinal,
            run_identity=run_identity,
            execution_family=_FAMILIES[(ordinal - 1) % len(_FAMILIES)],
        )
        for ordinal in range(1, trial_count + 1)
    )
    return RunPlan.model_construct(
        plan_identity=_identity(EntityKind.PLAN, key),
        run_identity=run_identity,
        created_at=_NOW,
        state="ready",
        trials=trials,
    )


def _work_item(plan: RunPlan, trial: PlannedTrial, retry_policy: RetryPolicy) -> TrialWorkItem:
    return TrialWorkItem(
        work_id=new_entity_id(EntityKind.WORK_ITEM),
        work_key=f"{plan.plan_key}-work-{trial.ordinal}",
        run_id=plan.run_id,
        plan_id=plan.plan_id,
        trial_id=trial.trial_id,
        ordinal=trial.ordinal,
        execution_family=trial.execution_family,
        backend="local",
        provider_route=f"provider-{trial.execution_family}",
        model_route="synthetic",
        resource_class="cpu-small",
        priority=0,
        retry_policy=retry_policy,
        state="planned",
        created_at=_NOW,
        available_at=_NOW,
    )


def _scenario(
    tmp_path: Path,
    *,
    trial_count: int = _TRIAL_COUNT,
    policy: ExecutionPolicy | None = None,
    key: str = "scale-plan",
) -> tuple[OperationalStore, LocalScheduler, RunPlan, tuple[TrialWorkItem, ...]]:
    plan = _plan(trial_count, key=key)
    selected_policy = policy or ExecutionPolicy(max_concurrency=_MAX_CONCURRENCY)
    store = OperationalStore(tmp_path / f"{key}.sqlite3")
    store.create_run(plan.run_id, spec_ref=f"runs/{key}/resolved-run-spec.json", status="ready", now=_NOW)
    store.put_plan(plan.plan_id, run_id=plan.run_id, plan_ref=f"runs/{key}/run-plan.json", state="ready", now=_NOW)
    items = tuple(_work_item(plan, trial, selected_policy.retry_policy) for trial in plan.trials)
    return store, LocalScheduler(store, selected_policy), plan, items


def test_500_mixed_family_trials_complete_after_restart_with_exact_order_and_bounds(tmp_path: Path) -> None:
    store, scheduler, plan, items = _scenario(tmp_path)
    first_enqueue = scheduler.enqueue_ready_plan(plan, items)
    second_enqueue = scheduler.enqueue_ready_plan(plan, items)
    assert tuple(item.work_id for item in first_enqueue) == tuple(item.work_id for item in second_enqueue)

    active = 0
    maximum_active = 0
    lock = Lock()
    completed_ordinals: list[int] = []

    def worker(work_item: WorkItemRecord, _: object) -> None:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        sleep(0.001)
        with lock:
            completed_ordinals.append(work_item.ordinal)
            active -= 1

    first = scheduler.dispatch_once(worker, owner="scale-worker", now=_NOW)
    assert first.leased_count == _MAX_CONCURRENCY
    assert len(store.list_work_items(plan.run_id)) == _TRIAL_COUNT
    assert sum(count.count for count in scheduler.queue_counts(plan.run_id) if count.state == "queued") == (
        _TRIAL_COUNT - _MAX_CONCURRENCY
    )

    restarted_store = OperationalStore(store.path)
    restarted_scheduler = LocalScheduler(restarted_store, scheduler.policy)
    for batch in range(100):
        terminal = {"succeeded", "failed", "cancelled", "invalid"}
        if all(item.state in terminal for item in restarted_store.list_work_items(plan.run_id)):
            break
        report = restarted_scheduler.dispatch_once(
            worker,
            owner="restarted-scale-worker",
            now=_NOW + timedelta(seconds=batch + 1),
        )
        assert report.leased_count > 0
    else:
        pytest.fail("500-trial queue did not reach a terminal state")

    records = restarted_store.list_work_items(plan.run_id)
    planned_trials = restarted_store.list_planned_trials(plan.plan_id)
    assert len(planned_trials) == _TRIAL_COUNT
    assert [trial.ordinal for trial in planned_trials] == list(range(1, _TRIAL_COUNT + 1))
    assert [record.ordinal for record in records] == list(range(1, _TRIAL_COUNT + 1))
    assert [record.execution_family for record in records] == [
        _FAMILIES[(ordinal - 1) % len(_FAMILIES)] for ordinal in range(1, _TRIAL_COUNT + 1)
    ]
    assert all(record.state == "succeeded" for record in records)
    assert sorted(completed_ordinals) == list(range(1, _TRIAL_COUNT + 1))
    assert maximum_active <= _MAX_CONCURRENCY

    attempts = restarted_store.list_attempts_for_run(plan.run_id)
    assert len(attempts) == _TRIAL_COUNT
    assert len({attempt.attempt_id for attempt in attempts}) == _TRIAL_COUNT
    assert {UUID(attempt.attempt_id).version for attempt in attempts} == {7}
    assert {attempt.attempt_number for attempt in attempts} == {1}
    assert {attempt.retry_number for attempt in attempts} == {0}

    progress = project_run_progress(plan, restarted_store)
    assert progress.planned == _TRIAL_COUNT
    assert progress.work_items.succeeded == _TRIAL_COUNT
    assert progress.trials.succeeded == _TRIAL_COUNT
    assert progress.attempts.succeeded == _TRIAL_COUNT
    assert progress.completion_blocked is False
    assert restarted_store.get_run(plan.run_id).status == "completed"
    assert restarted_scheduler.dispatch_once(worker, owner="restarted-scale-worker", now=_NOW).idle
    assert len(restarted_store.list_attempts_for_run(plan.run_id)) == _TRIAL_COUNT

    other_store_plan = _plan(1, key="other-run")
    restarted_store.create_run(other_store_plan.run_id, spec_ref="runs/other-run/spec.json", status="ready", now=_NOW)
    restarted_store.put_plan(
        other_store_plan.plan_id,
        run_id=other_store_plan.run_id,
        plan_ref="runs/other-run/plan.json",
        state="ready",
        now=_NOW,
    )
    other_items = (_work_item(other_store_plan, other_store_plan.trials[0], RetryPolicy()),)
    other_scheduler = LocalScheduler(restarted_store, ExecutionPolicy(max_concurrency=1))
    other_scheduler.enqueue_ready_plan(other_store_plan, other_items)
    isolated = project_run_progress(plan, restarted_store)
    assert isolated.planned == _TRIAL_COUNT
    assert isolated.work_items.succeeded == _TRIAL_COUNT
    assert len(restarted_store.list_work_items(other_store_plan.run_id)) == 1


def test_faults_preserve_retry_history_and_require_reconciliation(tmp_path: Path) -> None:
    retry_policy = RetryPolicy(
        maximum_attempts=2,
        retryable_failure_kinds=(FailureKind.WORKER_LOST_BEFORE_SUBMISSION, FailureKind.RESULT_IMPORT_FAILED),
    )
    policy = ExecutionPolicy(max_concurrency=3, retry_policy=retry_policy)
    store, scheduler, plan, items = _scenario(tmp_path, trial_count=3, policy=policy, key="faults")
    scheduler.enqueue_ready_plan(plan, items)
    calls: Counter[int] = Counter()

    def faulty_worker(work_item: WorkItemRecord, attempt: AttemptRecord) -> None:
        calls[work_item.ordinal] += 1
        if work_item.ordinal == 1 and calls[work_item.ordinal] == 1:
            raise RuntimeError("worker stopped before submission")
        if work_item.ordinal == 2 and calls[work_item.ordinal] == 1:
            store.record_backend_submission(
                new_entity_id(EntityKind.BACKEND_SUBMISSION),
                attempt_id=attempt.attempt_id,
                backend=work_item.backend,
                state="running",
                now=_NOW,
            )
            raise RuntimeError("submission accepted but result was not collected")

    first = scheduler.dispatch_once(faulty_worker, owner="fault-worker", now=_NOW)
    assert first.retried_count == 1
    assert first.unknown_count == 1
    assert first.succeeded_count == 1
    work_by_ordinal = {item.ordinal: item for item in store.list_work_items(plan.run_id)}
    assert store.get_work_item(work_by_ordinal[1].work_id).state == "queued"
    assert store.get_work_item(work_by_ordinal[2].work_id).state == "unknown"

    uncertain_attempt = store.list_attempts(plan.trials[1].trial_id)[0]
    submission = store.list_backend_submissions(uncertain_attempt.attempt_id)[0]
    receipt = AttemptReceipt(
        receipt_id=new_entity_id(EntityKind.RECEIPT),
        receipt_key="fault-reconciliation-receipt",
        attempt_id=uncertain_attempt.attempt_id,
        backend="local",
        submission_id=submission.submission_id,
        requested_condition=_identity(EntityKind.AGENT_CONDITION, "synthetic"),
        started_at=_NOW,
        finished_at=_NOW + timedelta(seconds=1),
        process_status=AttemptProcessStatus.FAILED,
        cancellation_status=CancellationStatus.NOT_REQUESTED,
        resource_usage=AttemptResourceUsage(wall_seconds=1.0),
        failure=FailureClassification(
            failure_class=FailureClass.INFRASTRUCTURE,
            kind=FailureKind.RESULT_IMPORT_FAILED,
            message="synthetic import failure",
        ),
        reconciliation_status=ReconciliationState.RECONCILED,
    )

    class Backend:
        def reconcile(self, *_: object) -> WorkerOutcome:
            return WorkerOutcome(terminal_state="failed", receipts=(receipt,))

    reconciled = scheduler.reconcile_unknown(
        plan.run_id,
        backends={"local": Backend()},
        now=_NOW + timedelta(seconds=2),
    )
    assert reconciled.retried_count == 1
    assert store.get_work_item(work_by_ordinal[2].work_id).state == "queued"

    second = scheduler.dispatch_once(faulty_worker, owner="fault-worker", now=_NOW + timedelta(seconds=3))
    assert second.succeeded_count == 2
    for ordinal in (1, 2):
        attempts = store.list_attempts(plan.trials[ordinal - 1].trial_id)
        assert len(attempts) == 2
        assert attempts[0].attempt_id != attempts[1].attempt_id
        assert all(UUID(attempt.attempt_id).version == 7 for attempt in attempts)
        assert [attempt.retry_number for attempt in attempts] == [0, 1]
        assert attempts[0].state == "failed"
        assert attempts[1].state == "succeeded"
    assert len(store.list_attempts(plan.trials[2].trial_id)) == 1


def test_queued_cancellation_is_idempotent_and_stops_new_leases(tmp_path: Path) -> None:
    store, scheduler, plan, items = _scenario(tmp_path, trial_count=3, key="cancelled")
    scheduler.enqueue_ready_plan(plan, items)
    scheduler.request_cancellation(plan.run_id, now=_NOW + timedelta(seconds=1))
    scheduler.request_cancellation(plan.run_id, now=_NOW + timedelta(seconds=2))

    assert {item.state for item in store.list_work_items(plan.run_id)} == {"cancelled"}
    assert {trial.state for trial in store.list_planned_trials(plan.plan_id)} == {"cancelled"}
    report = scheduler.dispatch_once(lambda *_: None, owner="cancel-worker", now=_NOW + timedelta(seconds=3))
    assert report.idle
    assert report.leased_count == 0


def test_expired_submitted_work_is_unknown_until_reconciliation(tmp_path: Path) -> None:
    store, _, plan, items = _scenario(tmp_path, trial_count=3, key="expired")
    scheduler = LocalScheduler(store, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, items)
    selected = store.lease_next_work_item(owner="expiring-worker", now=_NOW, ttl=timedelta(seconds=1), global_limit=1)
    assert selected is not None
    work_item, lease = selected
    attempt = store.create_attempt_for_lease(
        work_item.work_id,
        trial_id=work_item.trial_id,
        lease_id=lease.lease_id,
        candidate_index=1,
        retry_number=0,
        now=_NOW,
    )
    store.transition_attempt(attempt.attempt_id, state="running", now=_NOW)
    store.record_backend_submission(
        new_entity_id(EntityKind.BACKEND_SUBMISSION),
        attempt_id=attempt.attempt_id,
        backend=work_item.backend,
        state="running",
        now=_NOW,
    )

    with pytest.raises(LeaseUnavailable, match="not queued"):
        store.acquire_lease(
            work_item.work_id,
            owner="replacement-worker",
            now=_NOW + timedelta(seconds=2),
            ttl=timedelta(seconds=1),
        )

    assert store.get_work_item(work_item.work_id).state == "unknown"
    assert store.get_attempt(attempt.attempt_id).state == "unknown"
    assert store.list_backend_submissions(attempt.attempt_id)[0].state == "unknown"
