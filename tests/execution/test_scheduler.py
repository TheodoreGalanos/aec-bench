# ABOUTME: Tests the provider-neutral local bounded scheduler over SQLite queue state.
# ABOUTME: Protects exact enqueue, eligibility, fairness, concurrency caps, leases, and truthful worker failure.

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan
from aec_bench.execution.models import RetryPolicy, TrialWorkItem
from aec_bench.execution.operational import AttemptRecord, LeaseUnavailable, OperationalStore, WorkItemRecord
from aec_bench.execution.progress import project_run_progress
from aec_bench.execution.scheduler import LocalScheduler


def _identity(kind: EntityKind, key: str) -> EntityIdentity:
    return EntityIdentity(id=new_entity_id(kind), key=key, version=1)


def _plan(trial_count: int = 2) -> RunPlan:
    run_identity = _identity(EntityKind.RUN, "scheduler-run")
    trials = tuple(
        PlannedTrial.model_construct(
            trial_identity=_identity(EntityKind.TRIAL, f"trial-{ordinal}"),
            ordinal=ordinal,
            run_identity=run_identity,
            execution_family="artifact",
        )
        for ordinal in range(1, trial_count + 1)
    )
    return RunPlan.model_construct(
        plan_identity=_identity(EntityKind.PLAN, "scheduler-plan"),
        run_identity=run_identity,
        state="ready",
        trials=trials,
    )


def _item(
    plan: RunPlan,
    trial: PlannedTrial,
    *,
    created_at: datetime,
    priority: int = 0,
    backend: str = "local",
    provider_route: str = "default",
    model_route: str = "default",
    resource_class: str = "cpu-small",
    execution_family: str = "artifact",
    available_at: datetime | None = None,
) -> TrialWorkItem:
    return TrialWorkItem(
        work_id=new_entity_id(EntityKind.WORK_ITEM),
        work_key=f"work-{trial.ordinal}",
        run_id=plan.run_id,
        plan_id=plan.plan_id,
        trial_id=trial.trial_id,
        ordinal=trial.ordinal,
        execution_family=execution_family,
        backend=backend,
        provider_route=provider_route,
        model_route=model_route,
        resource_class=resource_class,
        priority=priority,
        retry_policy=RetryPolicy(),
        state="planned",
        created_at=created_at,
        available_at=available_at or created_at,
    )


def _store_and_scheduler(
    tmp_path: Path, plan: RunPlan, policy: ExecutionPolicy
) -> tuple[OperationalStore, LocalScheduler]:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    store.create_run(plan.run_id, spec_ref="runs/scheduler-run/spec.json", status="ready")
    store.put_plan(plan.plan_id, run_id=plan.run_id, plan_ref="runs/scheduler-run/plan.json", state="ready")
    return store, LocalScheduler(store, policy)


def test_ready_plan_trials_are_enqueued_once_with_ordinals_and_queue_counts(tmp_path: Path) -> None:
    plan = _plan(2)
    policy = ExecutionPolicy(max_concurrency=2)
    store, scheduler = _store_and_scheduler(tmp_path, plan, policy)
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    items = tuple(_item(plan, trial, created_at=now, backend=f"backend-{trial.ordinal}") for trial in plan.trials)

    first = scheduler.enqueue_ready_plan(plan, items)
    second = scheduler.enqueue_ready_plan(plan, items)

    assert tuple(record.work_id for record in first) == tuple(record.work_id for record in second)
    assert [(record.ordinal, record.available_at) for record in store.list_work_items(plan.run_id)] == [
        (1, now),
        (2, now),
    ]
    assert [(count.backend, count.state, count.count) for count in scheduler.queue_counts(plan.run_id)] == [
        ("backend-1", "queued", 1),
        ("backend-2", "queued", 1),
    ]


@pytest.mark.parametrize(
    ("policy_field", "item_kwargs"),
    (
        ("run_limits", {}),
        ("backend_limits", {"backend": "local"}),
        ("provider_route_limits", {"provider_route": "route-a"}),
        ("model_route_limits", {"model_route": "model-a"}),
        ("resource_class_limits", {"resource_class": "cpu-small"}),
        ("execution_family_limits", {"execution_family": "artifact"}),
    ),
)
def test_dispatch_respects_each_scoped_concurrency_limit(
    tmp_path: Path, policy_field: str, item_kwargs: dict[str, str]
) -> None:
    plan = _plan(2)
    policy_values: dict[str, object] = {"max_concurrency": 2, policy_field: {}}
    if policy_field == "run_limits":
        policy_values[policy_field] = {str(plan.run_id): 1}
    else:
        policy_values[policy_field] = {item_kwargs.get(policy_field.removesuffix("_limits"), ""): 1}
    policy = ExecutionPolicy.model_validate(policy_values)
    store, scheduler = _store_and_scheduler(tmp_path, plan, policy)
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    items = tuple(_item(plan, trial, created_at=now, **item_kwargs) for trial in plan.trials)
    scheduler.enqueue_ready_plan(plan, items)

    report = scheduler.dispatch_once(lambda _, __: None, owner="scheduler", now=now)

    assert report.leased_count == 1
    assert report.succeeded_count == 1
    assert report.failed_count == 0
    assert [item.state for item in store.list_work_items(plan.run_id)].count("succeeded") == 1
    assert [item.state for item in store.list_work_items(plan.run_id)].count("queued") == 1


def test_dispatch_respects_global_concurrency_limit(tmp_path: Path) -> None:
    plan = _plan(2)
    policy = ExecutionPolicy(max_concurrency=1)
    store, scheduler = _store_and_scheduler(tmp_path, plan, policy)
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    scheduler.enqueue_ready_plan(plan, tuple(_item(plan, trial, created_at=now) for trial in plan.trials))

    report = scheduler.dispatch_once(lambda _, __: None, owner="scheduler", now=now)

    assert report.leased_count == 1
    assert [item.state for item in store.list_work_items(plan.run_id)].count("queued") == 1


def test_dispatch_creates_one_attempt_per_work_item_and_passes_it_to_worker(tmp_path: Path) -> None:
    plan = _plan(2)
    store, scheduler = _store_and_scheduler(tmp_path, plan, ExecutionPolicy(max_concurrency=2))
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    scheduler.enqueue_ready_plan(plan, tuple(_item(plan, trial, created_at=now) for trial in plan.trials))
    seen: list[tuple[str, str]] = []

    def worker(work_item: WorkItemRecord, attempt: AttemptRecord) -> None:
        seen.append((work_item.work_id, attempt.attempt_id))

    report = scheduler.dispatch_once(worker, owner="scheduler", now=now)

    assert report.succeeded_count == 2
    assert len(seen) == 2
    for trial in plan.trials:
        attempts = store.list_attempts(trial.trial_id)
        assert len(attempts) == 1
        assert attempts[0].attempt_id in {attempt_id for _, attempt_id in seen}
        assert attempts[0].state == "succeeded"
        assert attempts[0].started_at is not None
        assert attempts[0].finished_at is not None


def test_full_dispatch_closes_plan_and_run_for_progress_projection(tmp_path: Path) -> None:
    plan = _plan(2)
    store, scheduler = _store_and_scheduler(tmp_path, plan, ExecutionPolicy(max_concurrency=2))
    now = datetime.now(UTC)
    scheduler.enqueue_ready_plan(plan, tuple(_item(plan, trial, created_at=now) for trial in plan.trials))

    report = scheduler.dispatch_once(lambda _, __: None, owner="scheduler", now=now)
    progress = project_run_progress(plan, store)

    assert report.succeeded_count == 2
    assert store.get_run(plan.run_id).started_at == now
    assert store.get_plan(plan.plan_id).state == "closed"
    assert progress.trials.succeeded == 2
    assert progress.work_items.succeeded == 2
    assert progress.started_at == now
    assert not progress.completion_blocked


def test_dispatch_renews_a_long_running_lease_before_worker_completion(tmp_path: Path) -> None:
    plan = _plan(1)
    policy = ExecutionPolicy(max_concurrency=1, lease_ttl_seconds=2, lease_heartbeat_seconds=1)
    store, scheduler = _store_and_scheduler(tmp_path, plan, policy)
    now = datetime.now(UTC)
    scheduler.enqueue_ready_plan(plan, (_item(plan, plan.trials[0], created_at=now),))
    acquisition = now + timedelta(seconds=2.1)

    def worker(work_item: WorkItemRecord, _: AttemptRecord) -> None:
        time.sleep(2.2)
        with pytest.raises(LeaseUnavailable):
            store.acquire_lease(work_item.work_id, owner="other", now=acquisition, ttl=timedelta(seconds=2))

    report = scheduler.dispatch_once(worker, owner="scheduler", now=now)

    assert report.succeeded_count == 1
    assert store.list_leases_for_run(plan.run_id)[0].state == "released"


def test_execution_policy_requires_heartbeat_shorter_than_lease_ttl() -> None:
    with pytest.raises(ValueError, match="heartbeat interval"):
        ExecutionPolicy(max_concurrency=1, lease_ttl_seconds=2, lease_heartbeat_seconds=2)


def test_priority_aging_prevents_an_old_low_priority_item_from_starving(tmp_path: Path) -> None:
    plan = _plan(2)
    policy = ExecutionPolicy(max_concurrency=1, priority_aging_seconds=60)
    store, scheduler = _store_and_scheduler(tmp_path, plan, policy)
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    old = _item(plan, plan.trials[0], created_at=now - timedelta(minutes=2), priority=-100)
    new = _item(plan, plan.trials[1], created_at=now, priority=100)
    scheduler.enqueue_ready_plan(plan, (old, new))

    selected = store.lease_next_work_item(
        owner="scheduler",
        now=now,
        ttl=timedelta(minutes=5),
        global_limit=1,
        priority_aging_seconds=policy.priority_aging_seconds,
    )

    assert selected is not None
    assert selected[0].trial_id == str(plan.trials[0].trial_id)


def test_future_available_work_does_not_busy_loop(tmp_path: Path) -> None:
    plan = _plan(1)
    policy = ExecutionPolicy(max_concurrency=1)
    store, scheduler = _store_and_scheduler(tmp_path, plan, policy)
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    available_at = now + timedelta(hours=1)
    records = scheduler.enqueue_ready_plan(
        plan, (_item(plan, plan.trials[0], created_at=now, available_at=available_at),)
    )
    called = False

    def worker(_: WorkItemRecord, __: AttemptRecord) -> None:
        nonlocal called
        called = True

    report = scheduler.dispatch_once(worker, owner="scheduler", now=now)

    assert report.idle
    assert report.leased_count == 0
    assert report.next_available_at == available_at
    assert not called
    assert store.get_work_item(records[0].work_id).state == "queued"
    assert store.get_work_item(records[0].work_id).available_at == available_at


def test_lease_exclusion_and_worker_failure_keep_state_truthful(tmp_path: Path) -> None:
    plan = _plan(1)
    policy = ExecutionPolicy(max_concurrency=1)
    store, scheduler = _store_and_scheduler(tmp_path, plan, policy)
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    scheduler.enqueue_ready_plan(plan, (_item(plan, plan.trials[0], created_at=now),))
    first = store.lease_next_work_item(owner="other", now=now, ttl=timedelta(minutes=5), global_limit=1)
    assert first is not None
    assert store.lease_next_work_item(owner="scheduler", now=now, ttl=timedelta(minutes=5), global_limit=1) is None
    store.release_lease(first[1].lease_id, owner="other", now=now)

    def failing_worker(_: WorkItemRecord, __: AttemptRecord) -> None:
        raise RuntimeError("worker failed")

    report = scheduler.dispatch_once(failing_worker, owner="scheduler", now=now)

    assert report.failed_count == 1
    assert report.succeeded_count == 0
    assert store.list_work_items(plan.run_id)[0].state == "failed"
    attempts = store.list_attempts(plan.trials[0].trial_id)
    assert len(attempts) == 1
    assert attempts[0].state == "failed"
    assert attempts[0].started_at is not None
    assert attempts[0].finished_at is not None
    assert store.list_leases_for_run(plan.run_id)[0].state == "released"
