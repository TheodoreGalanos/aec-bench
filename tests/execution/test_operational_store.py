# ABOUTME: Defines focused behavior tests for the mutable SQLite operational store.
# ABOUTME: Protects migration application, state records, and lease ownership semantics.

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
    OperationalStoreNotFound,
)


def _id(kind: EntityKind) -> str:
    return str(new_entity_id(kind))


def test_store_applies_numbered_migrations_and_keeps_operational_records_mutable(tmp_path: Path) -> None:
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
    item = store.create_work_item(
        work_id,
        work_key="0001-monitoring-dam-seepage",
        run_id=run.run_id,
        trial_id=trial.trial_id,
        kind="trial",
    )
    attempt = store.create_attempt(attempt_id, work_id=item.work_id, trial_id=trial.trial_id)
    store.record_backend_submission(submission_id, attempt_id=attempt.attempt_id, backend="local", external_id="job-1")

    assert store.schema_version() == 1
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
        migration = connection.execute(
            "SELECT version, application_version, status FROM operational_schema_migrations"
        ).fetchone()
        assert migration == (1, "test-version", "applied")
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
    store.create_work_item(work_id, work_key="0001-monitoring-dam-seepage", run_id=run_id, trial_id=trial_id)
    created = store.create_attempt(attempt_id, work_id=work_id, trial_id=trial_id)

    assert store.create_attempt(attempt_id, work_id=work_id, trial_id=trial_id) == created
    with pytest.raises(OperationalStoreConflict):
        store.put_plan(plan_id, run_id=other_run_id, plan_ref="runs/run-1/plan.json")
    with pytest.raises(OperationalStoreConflict):
        store.create_work_item(
            work_id,
            work_key="0001-monitoring-dam-seepage",
            run_id=run_id,
            trial_id=trial_id,
            priority=1,
        )
    with pytest.raises(OperationalStoreConflict, match="already belongs"):
        store.create_work_item(
            _id(EntityKind.WORK_ITEM),
            work_key="0002-monitoring-dam-seepage",
            run_id=run_id,
            trial_id=trial_id,
        )

    with pytest.raises(OperationalStoreConflict, match="attempt number"):
        store.create_attempt(_id(EntityKind.ATTEMPT), work_id=work_id, trial_id=trial_id)


def test_leases_are_exclusive_and_expired_leases_are_retained_before_reclaim(tmp_path: Path) -> None:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    run_id = _id(EntityKind.RUN)
    plan_id = _id(EntityKind.PLAN)
    trial_id = _id(EntityKind.TRIAL)
    work_id = _id(EntityKind.WORK_ITEM)
    store.create_run(run_id, spec_ref="runs/run-1/spec.json")
    store.put_plan(plan_id, run_id=run_id, plan_ref="runs/run-1/plan.json")
    store.put_planned_trial(trial_id, plan_id=plan_id, run_id=run_id, ordinal=1)
    store.create_work_item(work_id, work_key="0001-monitoring-dam-seepage", run_id=run_id, trial_id=trial_id)
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
    store.create_work_item(work_id, work_key="0001-monitoring-dam-seepage", run_id=run_id, trial_id=trial_id)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    lease = store.acquire_lease(work_id, owner="worker-a", now=now, ttl=timedelta(minutes=5))

    with pytest.raises(OperationalStoreConflict, match="expired"):
        store.create_attempt(
            _id(EntityKind.ATTEMPT),
            work_id=work_id,
            trial_id=trial_id,
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
    store.create_work_item(work_id, work_key="0001-monitoring-dam-seepage", run_id=run_id, trial_id=trial_id)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    lease = store.acquire_lease(work_id, owner="worker-a", now=now, ttl=timedelta(minutes=5))

    attempt = store.create_attempt(
        _id(EntityKind.ATTEMPT),
        work_id=work_id,
        trial_id=trial_id,
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
        assert connection.execute("SELECT COUNT(*) FROM operational_schema_migrations").fetchone() == (1,)
    finally:
        connection.close()


def test_concurrent_first_open_applies_each_migration_once(tmp_path: Path) -> None:
    path = tmp_path / "operational.sqlite3"

    with ThreadPoolExecutor(max_workers=2) as executor:
        stores = tuple(executor.map(lambda _: OperationalStore(path), range(2)))

    assert tuple(store.schema_version() for store in stores) == (1, 1)
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM operational_schema_migrations").fetchone() == (1,)
    finally:
        connection.close()


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
