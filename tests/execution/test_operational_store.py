# ABOUTME: Defines focused behavior tests for the mutable SQLite operational store.
# ABOUTME: Protects current-schema initialization, state records, and lease ownership semantics.

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.execution.operational import (
    LeaseUnavailable,
    OperationalStore,
    OperationalStoreConflict,
    OperationalStoreError,
    OperationalStoreNotFound,
    WorkItemRecord,
)


def _id(kind: EntityKind) -> str:
    return str(new_entity_id(kind))


def _create_work_item(
    store: OperationalStore,
    work_id: str,
    *,
    work_key: str,
    run_id: str,
    plan_id: str,
    trial_id: str,
    now: datetime | None = None,
    kind: str = "trial",
    priority: int = 0,
) -> WorkItemRecord:
    stamp = now or datetime.now(UTC)
    return store.create_work_item(
        work_id,
        work_key=work_key,
        run_id=run_id,
        trial_id=trial_id,
        plan_id=plan_id,
        ordinal=1,
        execution_family="artifact",
        backend="local",
        provider_route="default",
        model_route="default",
        resource_class="default",
        available_at=stamp,
        now=stamp,
        kind=kind,
        priority=priority,
    )


def test_store_initializes_current_schema_and_keeps_operational_records_mutable(tmp_path: Path) -> None:
    store = OperationalStore(tmp_path / "operational.sqlite3", application_version="test-version")
    run_id = _id(EntityKind.RUN)
    plan_id = _id(EntityKind.PLAN)
    trial_id = _id(EntityKind.TRIAL)
    work_id = _id(EntityKind.WORK_ITEM)
    attempt_id = _id(EntityKind.ATTEMPT)
    submission_id = _id(EntityKind.BACKEND_SUBMISSION)

    run = store.create_run(run_id, spec_ref="runs/run-1/spec.json")
    plan = store.put_plan(plan_id, run_id=run.run_id, plan_ref="runs/run-1/plan.json")
    trial = store.put_planned_trial(trial_id, plan_id=plan.plan_id, run_id=run.run_id, ordinal=1)
    item = _create_work_item(
        store,
        work_id,
        work_key="0001-monitoring-dam-seepage",
        run_id=run.run_id,
        plan_id=plan.plan_id,
        trial_id=trial.trial_id,
        kind="trial",
    )
    attempt = store.create_attempt(
        attempt_id, work_id=item.work_id, trial_id=trial.trial_id, candidate_index=1, retry_number=0
    )
    store.record_backend_submission(submission_id, attempt_id=attempt.attempt_id, backend="local", external_id="job-1")

    assert store.schema_version() == 3
    assert store.get_run(run_id).spec_ref == "runs/run-1/spec.json"
    assert store.get_plan(plan_id).run_id == run_id
    assert store.get_planned_trial(trial_id).ordinal == 1
    assert store.get_work_item(work_id).state == "queued"
    assert store.get_work_item(work_id).work_key == "0001-monitoring-dam-seepage"
    assert store.get_attempt(attempt_id).state == "created"
    assert store.get_backend_submission(submission_id).external_id == "job-1"

    store.update_work_item(work_id, state="running")
    assert store.get_work_item(work_id).state == "running"

    connection = sqlite3.connect(tmp_path / "operational.sqlite3")
    try:
        schema = connection.execute("SELECT schema_version, application_version FROM operational_schema").fetchone()
        assert schema == (3, "test-version")
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'operational_schema_migrations'"
        ).fetchone() == (0,)
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    finally:
        connection.close()


def test_store_rejects_conflicting_portable_references(tmp_path: Path) -> None:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    run_id = _id(EntityKind.RUN)
    store.create_run(run_id, spec_ref="runs/run-1/spec.json")

    with pytest.raises(OperationalStoreConflict):
        store.create_run(run_id, spec_ref="runs/run-2/spec.json")


def test_identity_relationships_are_idempotent_but_conflicts_are_rejected(tmp_path: Path) -> None:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    run_id = _id(EntityKind.RUN)
    other_run_id = _id(EntityKind.RUN)
    plan_id = _id(EntityKind.PLAN)
    trial_id = _id(EntityKind.TRIAL)
    work_id = _id(EntityKind.WORK_ITEM)
    attempt_id = _id(EntityKind.ATTEMPT)
    store.create_run(run_id, spec_ref="runs/run-1/spec.json")
    store.create_run(other_run_id, spec_ref="runs/run-2/spec.json")
    store.put_plan(plan_id, run_id=run_id, plan_ref="runs/run-1/plan.json")
    store.put_planned_trial(trial_id, plan_id=plan_id, run_id=run_id, ordinal=1)
    _create_work_item(
        store, work_id, work_key="0001-monitoring-dam-seepage", run_id=run_id, plan_id=plan_id, trial_id=trial_id
    )
    created = store.create_attempt(attempt_id, work_id=work_id, trial_id=trial_id, candidate_index=1, retry_number=0)

    assert (
        store.create_attempt(attempt_id, work_id=work_id, trial_id=trial_id, candidate_index=1, retry_number=0)
        == created
    )
    with pytest.raises(OperationalStoreConflict):
        store.put_plan(plan_id, run_id=other_run_id, plan_ref="runs/run-1/plan.json")
    with pytest.raises(OperationalStoreConflict):
        _create_work_item(
            store,
            work_id,
            work_key="0001-monitoring-dam-seepage",
            run_id=run_id,
            plan_id=plan_id,
            trial_id=trial_id,
            priority=1,
        )
    with pytest.raises(OperationalStoreConflict, match="already belongs"):
        _create_work_item(
            store,
            _id(EntityKind.WORK_ITEM),
            work_key="0002-monitoring-dam-seepage",
            run_id=run_id,
            plan_id=plan_id,
            trial_id=trial_id,
        )

    with pytest.raises(OperationalStoreConflict, match="attempt number"):
        store.create_attempt(
            _id(EntityKind.ATTEMPT), work_id=work_id, trial_id=trial_id, candidate_index=1, retry_number=0
        )


def test_plan_completion_waits_for_all_plans_before_completing_run(tmp_path: Path) -> None:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    run_id = _id(EntityKind.RUN)
    plan_a = _id(EntityKind.PLAN)
    plan_b = _id(EntityKind.PLAN)
    trial_a = _id(EntityKind.TRIAL)
    trial_b = _id(EntityKind.TRIAL)
    now = datetime(2026, 1, 1, tzinfo=UTC)

    store.create_run(run_id, spec_ref="runs/run-1/spec.json", status="running", now=now)
    store.put_plan(plan_a, run_id=run_id, plan_ref="runs/run-1/plan-a.json", state="started", now=now)
    store.put_plan(plan_b, run_id=run_id, plan_ref="runs/run-1/plan-b.json", state="started", now=now)
    store.put_planned_trial(trial_a, plan_id=plan_a, run_id=run_id, ordinal=1, now=now)
    store.put_planned_trial(trial_b, plan_id=plan_b, run_id=run_id, ordinal=1, state="queued", now=now)
    work_a = _create_work_item(
        store, _id(EntityKind.WORK_ITEM), work_key="work-a", run_id=run_id, plan_id=plan_a, trial_id=trial_a, now=now
    )
    work_b = _create_work_item(
        store, _id(EntityKind.WORK_ITEM), work_key="work-b", run_id=run_id, plan_id=plan_b, trial_id=trial_b, now=now
    )

    completed_at = now + timedelta(seconds=1)
    store.update_planned_trial(trial_a, state="succeeded", now=completed_at)
    store.update_work_item(work_a.work_id, state="succeeded", now=completed_at)
    first = store.complete_plan_if_terminal(plan_a, run_id=run_id, now=now + timedelta(seconds=2))

    assert first is not None
    assert first[0].state == "closed"
    assert first[1].status == "running"
    assert store.get_plan(plan_b).state == "started"
    assert store.get_planned_trial(trial_b).state == "queued"
    assert store.get_work_item(work_b.work_id).state == "queued"

    store.update_planned_trial(trial_b, state="failed", now=now + timedelta(seconds=3))
    store.update_work_item(work_b.work_id, state="failed", now=now + timedelta(seconds=3))
    second = store.complete_plan_if_terminal(plan_b, run_id=run_id, now=now + timedelta(seconds=4))

    assert second is not None
    assert second[0].state == "closed"
    assert second[1].status == "completed"


def test_leases_are_exclusive_and_expired_leases_are_retained_before_reclaim(tmp_path: Path) -> None:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    run_id = _id(EntityKind.RUN)
    plan_id = _id(EntityKind.PLAN)
    trial_id = _id(EntityKind.TRIAL)
    work_id = _id(EntityKind.WORK_ITEM)
    store.create_run(run_id, spec_ref="runs/run-1/spec.json")
    store.put_plan(plan_id, run_id=run_id, plan_ref="runs/run-1/plan.json")
    store.put_planned_trial(trial_id, plan_id=plan_id, run_id=run_id, ordinal=1)
    _create_work_item(
        store, work_id, work_key="0001-monitoring-dam-seepage", run_id=run_id, plan_id=plan_id, trial_id=trial_id
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)

    lease = store.acquire_lease(work_id, owner="worker-a", now=now, ttl=timedelta(minutes=5))
    assert lease.owner == "worker-a"
    with pytest.raises(LeaseUnavailable):
        store.acquire_lease(work_id, owner="worker-b", now=now, ttl=timedelta(minutes=5))

    reclaimed = store.acquire_lease(work_id, owner="worker-b", now=now + timedelta(minutes=6), ttl=timedelta(minutes=5))
    assert reclaimed.owner == "worker-b"
    assert reclaimed.lease_id != lease.lease_id
    assert store.get_lease(lease.lease_id).state == "expired"
    assert store.get_lease(reclaimed.lease_id).state == "active"


def test_attempt_rejects_an_expired_lease_before_reclamation(tmp_path: Path) -> None:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    run_id = _id(EntityKind.RUN)
    plan_id = _id(EntityKind.PLAN)
    trial_id = _id(EntityKind.TRIAL)
    work_id = _id(EntityKind.WORK_ITEM)
    store.create_run(run_id, spec_ref="runs/run-1/spec.json")
    store.put_plan(plan_id, run_id=run_id, plan_ref="runs/run-1/plan.json")
    store.put_planned_trial(trial_id, plan_id=plan_id, run_id=run_id, ordinal=1)
    _create_work_item(
        store, work_id, work_key="0001-monitoring-dam-seepage", run_id=run_id, plan_id=plan_id, trial_id=trial_id
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    lease = store.acquire_lease(work_id, owner="worker-a", now=now, ttl=timedelta(minutes=5))

    with pytest.raises(OperationalStoreConflict, match="expired"):
        store.create_attempt(
            _id(EntityKind.ATTEMPT),
            work_id=work_id,
            trial_id=trial_id,
            candidate_index=1,
            retry_number=0,
            lease_id=lease.lease_id,
            now=now + timedelta(minutes=5),
        )


def test_attempt_can_bind_active_lease_and_release_keeps_lease_history(tmp_path: Path) -> None:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    run_id = _id(EntityKind.RUN)
    plan_id = _id(EntityKind.PLAN)
    trial_id = _id(EntityKind.TRIAL)
    work_id = _id(EntityKind.WORK_ITEM)
    store.create_run(run_id, spec_ref="runs/run-1/spec.json")
    store.put_plan(plan_id, run_id=run_id, plan_ref="runs/run-1/plan.json")
    store.put_planned_trial(trial_id, plan_id=plan_id, run_id=run_id, ordinal=1)
    _create_work_item(
        store, work_id, work_key="0001-monitoring-dam-seepage", run_id=run_id, plan_id=plan_id, trial_id=trial_id
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    lease = store.acquire_lease(work_id, owner="worker-a", now=now, ttl=timedelta(minutes=5))

    attempt = store.create_attempt(
        _id(EntityKind.ATTEMPT),
        work_id=work_id,
        trial_id=trial_id,
        candidate_index=1,
        retry_number=0,
        lease_id=lease.lease_id,
        now=now + timedelta(minutes=1),
    )
    released = store.release_lease(lease.lease_id, owner="worker-a", now=now + timedelta(minutes=1))

    assert attempt.lease_id == lease.lease_id
    assert released.state == "released"
    assert released.released_at == now + timedelta(minutes=1)
    assert store.get_work_item(work_id).state == "queued"
    with pytest.raises(LeaseUnavailable, match="not active"):
        store.renew_lease(lease.lease_id, owner="worker-a", now=now + timedelta(minutes=2), ttl=timedelta(minutes=5))


def test_store_uses_foreign_keys_and_short_connections(tmp_path: Path) -> None:
    path = tmp_path / "operational.sqlite3"
    store = OperationalStore(path)

    with pytest.raises(OperationalStoreNotFound):
        store.put_plan(
            _id(EntityKind.PLAN),
            run_id=_id(EntityKind.RUN),
            plan_ref="runs/missing/plan.json",
        )

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM operational_schema").fetchone() == (1,)
    finally:
        connection.close()


def test_concurrent_first_open_initializes_current_schema_once(tmp_path: Path) -> None:
    path = tmp_path / "operational.sqlite3"

    with ThreadPoolExecutor(max_workers=2) as executor:
        stores = tuple(executor.map(lambda _: OperationalStore(path), range(2)))

    assert tuple(store.schema_version() for store in stores) == (3, 3)
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM operational_schema").fetchone() == (1,)
    finally:
        connection.close()


def test_store_rejects_stale_disposable_schema(tmp_path: Path) -> None:
    path = tmp_path / "operational.sqlite3"
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE operational_schema "
            "(singleton INTEGER PRIMARY KEY, schema_version INTEGER NOT NULL, "
            "application_version TEXT NOT NULL, initialized_at TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO operational_schema VALUES (1, 999, 'old', '2026-01-01T00:00:00+00:00')")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(OperationalStoreError, match="delete and recreate"):
        OperationalStore(path)


def test_store_requires_uuidv7_ids_and_portable_authority_references(tmp_path: Path) -> None:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    with pytest.raises(ValueError, match="UUIDv7"):
        store.create_run("run-1", spec_ref="runs/run-1/spec.json")

    run_id = _id(EntityKind.RUN)
    store.create_run(run_id, spec_ref="runs/run-1/spec.json")
    with pytest.raises(ValueError, match="portable relative"):
        store.put_plan(_id(EntityKind.PLAN), run_id=run_id, plan_ref="../plan.json")

    connection = sqlite3.connect(tmp_path / "operational.sqlite3")
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(operational_runs)")}
        assert "spec_ref" in columns
        assert "spec_json" not in columns
    finally:
        connection.close()
