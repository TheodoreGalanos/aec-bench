# ABOUTME: Tests the read-only run progress projection over plan and SQLite state.
# ABOUTME: Protects exact plan totals, state counts, lease visibility, retries, and completion blockers.

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan
from aec_bench.execution.operational import OperationalStore, OperationalStoreError
from aec_bench.execution.progress import project_run_progress


def _identity(kind: EntityKind, key: str) -> EntityIdentity:
    return EntityIdentity(id=new_entity_id(kind), key=key, version=1)


def _plan(
    trial_count: int = 2,
    *,
    run_identity: EntityIdentity | None = None,
    plan_key: str = "progress-plan",
) -> RunPlan:
    run_identity = run_identity or _identity(EntityKind.RUN, "progress-run")
    trials = tuple(
        PlannedTrial.model_construct(
            trial_identity=_identity(EntityKind.TRIAL, f"trial-{ordinal}"),
            ordinal=ordinal,
            run_identity=run_identity,
        )
        for ordinal in range(1, trial_count + 1)
    )
    return RunPlan.model_construct(
        plan_identity=_identity(EntityKind.PLAN, plan_key),
        run_identity=run_identity,
        trials=trials,
    )


def _store_for_plan(tmp_path: Path, plan: RunPlan) -> OperationalStore:
    store = OperationalStore(tmp_path / "operational.sqlite3")
    created_at = datetime(2026, 8, 30, 11, tzinfo=UTC)
    store.create_run(plan.run_id, spec_ref="runs/progress-run/spec.json", now=created_at)
    store.put_plan(plan.plan_id, run_id=plan.run_id, plan_ref="runs/progress-run/plan.json", now=created_at)
    for trial in plan.trials:
        store.put_planned_trial(
            trial.trial_id,
            plan_id=plan.plan_id,
            run_id=plan.run_id,
            ordinal=trial.ordinal,
            state="succeeded" if trial.ordinal == 1 else "running",
            now=created_at,
        )
        store.create_work_item(
            new_entity_id(EntityKind.WORK_ITEM),
            work_key=f"work-{trial.ordinal}",
            run_id=plan.run_id,
            trial_id=trial.trial_id,
            plan_id=plan.plan_id,
            ordinal=trial.ordinal,
            execution_family="artifact",
            backend="local",
            provider_route="default",
            model_route="default",
            resource_class="default",
            available_at=created_at,
            now=created_at,
        )
    return store


def test_progress_uses_authoritative_plan_and_reports_operational_counts(tmp_path: Path) -> None:
    plan = _plan()
    store = _store_for_plan(tmp_path, plan)
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    work_items = {item.trial_id: item for item in store.list_work_items(plan.run_id)}
    store.update_work_item(work_items[str(plan.trials[0].trial_id)].work_id, state="succeeded", now=now)
    store.acquire_lease(
        work_items[str(plan.trials[1].trial_id)].work_id,
        owner="worker-a",
        now=now,
        ttl=timedelta(minutes=5),
    )
    attempt = store.create_attempt(
        new_entity_id(EntityKind.ATTEMPT),
        work_id=work_items[str(plan.trials[0].trial_id)].work_id,
        trial_id=plan.trials[0].trial_id,
        attempt_number=1,
        state="succeeded",
        now=now + timedelta(seconds=1),
    )
    store.create_attempt(
        new_entity_id(EntityKind.ATTEMPT),
        work_id=work_items[str(plan.trials[0].trial_id)].work_id,
        trial_id=plan.trials[0].trial_id,
        attempt_number=2,
        state="failed",
        now=now + timedelta(seconds=2),
    )
    store.create_attempt(
        new_entity_id(EntityKind.ATTEMPT),
        work_id=work_items[str(plan.trials[0].trial_id)].work_id,
        trial_id=plan.trials[0].trial_id,
        attempt_number=3,
        state="failed",
        now=now + timedelta(seconds=2),
    )
    store.record_backend_submission(
        new_entity_id(EntityKind.BACKEND_SUBMISSION),
        attempt_id=attempt.attempt_id,
        backend="local",
        state="completed",
        now=now + timedelta(seconds=3),
    )

    progress = project_run_progress(plan, store)

    assert progress.planned == 2
    assert progress.trials.succeeded == 1
    assert progress.trials.running == 1
    assert progress.work_items.succeeded == 1
    assert progress.work_items.leased == 1
    assert progress.attempts.succeeded == 1
    assert progress.attempts.failed == 2
    assert progress.backend_submissions.completed == 1
    assert progress.active_leases == 1
    assert progress.retries == 2
    assert progress.completion_blocked
    assert progress.completion_blocked_by_non_terminal
    assert not progress.completion_blocked_by_unknown
    assert progress.estimated_remaining_work_count == 1
    assert progress.started_at is None
    assert progress.last_activity_at == now + timedelta(seconds=3)


def test_progress_is_scoped_to_the_authoritative_plan(tmp_path: Path) -> None:
    plan = _plan(trial_count=1)
    other_plan = _plan(trial_count=1, run_identity=plan.run_identity, plan_key="other-plan")
    store = _store_for_plan(tmp_path, plan)
    created_at = datetime(2026, 8, 30, 11, tzinfo=UTC)
    trial = other_plan.trials[0]
    store.put_plan(other_plan.plan_id, run_id=plan.run_id, plan_ref="runs/other-plan/plan.json", now=created_at)
    store.put_planned_trial(
        trial.trial_id,
        plan_id=other_plan.plan_id,
        run_id=plan.run_id,
        ordinal=trial.ordinal,
        state="running",
        now=created_at,
    )
    work_id = new_entity_id(EntityKind.WORK_ITEM)
    store.create_work_item(
        work_id,
        work_key="other-work",
        run_id=plan.run_id,
        trial_id=trial.trial_id,
        plan_id=other_plan.plan_id,
        ordinal=trial.ordinal,
        execution_family="artifact",
        backend="local",
        provider_route="default",
        model_route="default",
        resource_class="default",
        available_at=created_at,
        now=created_at,
    )
    lease = store.acquire_lease(work_id, owner="other-worker", now=created_at, ttl=timedelta(minutes=5))
    attempt = store.create_attempt(
        new_entity_id(EntityKind.ATTEMPT),
        work_id=work_id,
        trial_id=trial.trial_id,
        lease_id=lease.lease_id,
        now=created_at,
    )
    store.record_backend_submission(
        new_entity_id(EntityKind.BACKEND_SUBMISSION),
        attempt_id=attempt.attempt_id,
        backend="other-backend",
        now=created_at,
    )

    progress = project_run_progress(plan, store)

    assert progress.planned == 1
    assert progress.attempts.model_dump() == {
        "created": 0,
        "submitted": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
        "cancelled": 0,
        "unknown": 0,
    }
    assert progress.active_leases == 0
    assert sum(progress.backend_submissions.model_dump().values()) == 0


def test_progress_rejects_plan_from_a_different_run(tmp_path: Path) -> None:
    plan = _plan(trial_count=1)
    other_run = _identity(EntityKind.RUN, "other-run")
    store = OperationalStore(tmp_path / "operational.sqlite3")
    created_at = datetime(2026, 8, 30, 11, tzinfo=UTC)
    store.create_run(plan.run_id, spec_ref="runs/progress-run/spec.json", now=created_at)
    store.create_run(other_run.id, spec_ref="runs/other-run/spec.json", now=created_at)
    store.put_plan(plan.plan_id, run_id=other_run.id, plan_ref="runs/other-run/plan.json", now=created_at)

    with pytest.raises(OperationalStoreError, match="not authoritative run"):
        project_run_progress(plan, store)


def test_progress_rejects_stored_trial_outside_or_mismatched_with_the_plan(tmp_path: Path) -> None:
    plan = _plan(trial_count=1)
    store = _store_for_plan(tmp_path, plan)
    other_trial = _identity(EntityKind.TRIAL, "not-in-plan")
    store.put_planned_trial(
        other_trial.id,
        plan_id=plan.plan_id,
        run_id=plan.run_id,
        ordinal=2,
        now=datetime(2026, 8, 30, 11, tzinfo=UTC),
    )

    with pytest.raises(OperationalStoreError, match="not present in authoritative run plan"):
        project_run_progress(plan, store)

    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "DELETE FROM operational_planned_trials WHERE trial_id = ?",
            (str(other_trial.id),),
        )
        connection.execute(
            "UPDATE operational_planned_trials SET ordinal = 99 WHERE trial_id = ?",
            (str(plan.trials[0].trial_id),),
        )

    with pytest.raises(OperationalStoreError, match="does not match authoritative ordinal"):
        project_run_progress(plan, store)

    other_run = _identity(EntityKind.RUN, "other-run")
    store.create_run(other_run.id, spec_ref="runs/other-run/spec.json")
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE operational_planned_trials SET ordinal = 1, run_id = ? WHERE trial_id = ?",
            (str(other_run.id), str(plan.trials[0].trial_id)),
        )

    with pytest.raises(OperationalStoreError, match="not authoritative run"):
        project_run_progress(plan, store)


def test_terminal_progress_uses_run_and_plan_activity_timestamps(tmp_path: Path) -> None:
    plan = _plan()
    store = _store_for_plan(tmp_path, plan)
    started_at = datetime(2026, 8, 30, 12, tzinfo=UTC)
    finished_at = started_at + timedelta(minutes=2)
    plan_activity_at = finished_at + timedelta(minutes=1)
    for work_item in store.list_work_items(plan.run_id):
        store.update_work_item(work_item.work_id, state="succeeded", now=started_at + timedelta(minutes=1))
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE operational_planned_trials SET state = 'succeeded', updated_at = ? WHERE plan_id = ?",
            (finished_at.isoformat(), str(plan.plan_id)),
        )
        connection.execute(
            "UPDATE operational_plans SET updated_at = ? WHERE plan_id = ?",
            (plan_activity_at.isoformat(), str(plan.plan_id)),
        )
    store.update_run(plan.run_id, status="running", now=started_at)
    store.update_run(plan.run_id, status="completed", now=finished_at)

    progress = project_run_progress(plan, store)

    assert progress.started_at == started_at
    assert progress.last_activity_at == plan_activity_at
    assert not progress.completion_blocked
    assert progress.estimated_remaining_work_count == 0


def test_progress_marks_missing_and_unknown_planned_trials_as_blocking(tmp_path: Path) -> None:
    plan = _plan()
    store = OperationalStore(tmp_path / "operational.sqlite3")
    created_at = datetime(2026, 8, 30, 11, tzinfo=UTC)
    store.create_run(plan.run_id, spec_ref="runs/progress-run/spec.json", now=created_at)
    store.put_plan(plan.plan_id, run_id=plan.run_id, plan_ref="runs/progress-run/plan.json", now=created_at)
    trial = plan.trials[1]
    store.put_planned_trial(
        trial.trial_id,
        plan_id=plan.plan_id,
        run_id=plan.run_id,
        ordinal=trial.ordinal,
        state="unknown",
        now=created_at,
    )
    work_id = new_entity_id(EntityKind.WORK_ITEM)
    store.create_work_item(
        work_id,
        work_key="work-2",
        run_id=plan.run_id,
        trial_id=trial.trial_id,
        plan_id=plan.plan_id,
        ordinal=trial.ordinal,
        execution_family="artifact",
        backend="local",
        provider_route="default",
        model_route="default",
        resource_class="default",
        available_at=created_at,
        now=created_at,
    )
    store.update_work_item(work_id, state="unknown", now=created_at)

    progress = project_run_progress(plan, store)

    assert progress.trials.missing == 1
    assert progress.work_items.missing == 1
    assert progress.completion_blocked_by_non_terminal
    assert progress.completion_blocked_by_unknown
    assert progress.completion_blocked
