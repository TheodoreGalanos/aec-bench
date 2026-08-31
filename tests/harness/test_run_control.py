# ABOUTME: Tests persisted run start and resume composition at the scheduler boundary.
# ABOUTME: Uses an injected provider-free worker to prove exact enqueue and interruption recovery.

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.execution.operational import OperationalStore
from aec_bench.harness.run_control import ResolvedExecution, RunControlError, start_or_resume_run
from tests.harness.test_persisted_artifact_plan import _ready_store, _spec, _task


def _resolver(calls: list[str]):
    def resolve(plan, evidence, operational):
        def worker(work_item, attempt):
            calls.append(work_item.trial_id)
            return None

        return ResolvedExecution(worker=worker, backends={})

    return resolve


def test_start_loads_ready_plan_and_dispatches_exact_work_once(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    evidence, plan = _ready_store(tmp_path, spec)
    calls: list[str] = []
    operational_path = tmp_path / "operational.sqlite3"

    result = start_or_resume_run(
        run_selector=str(plan.run_id),
        operation="start",
        plan_root=evidence.root,
        operational_store_path=operational_path,
        worker_resolver=_resolver(calls),
        now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
    )

    assert calls == [str(plan.trials[0].trial_id)]
    assert result.operation == "start"
    assert operational_path.is_file()
    store = OperationalStore.open_existing(operational_path)
    assert len(store.list_work_items(plan.run_id)) == 1
    assert len(store.list_attempts_for_run(plan.run_id)) == 1
    assert evidence.read_run(plan.run_identity).state.state == "started"


def test_resume_can_start_a_ready_run(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    evidence, plan = _ready_store(tmp_path, spec)
    calls: list[str] = []
    operational_path = tmp_path / "operational.sqlite3"
    OperationalStore(operational_path)

    result = start_or_resume_run(
        run_selector=str(plan.run_id),
        operation="resume",
        plan_root=evidence.root,
        operational_store_path=operational_path,
        worker_resolver=_resolver(calls),
        now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
    )

    assert result.operation == "resume"
    assert calls == [str(plan.trials[0].trial_id)]
    assert evidence.read_run(plan.run_identity).state.state == "started"


def test_resume_reconciles_unknown_before_refusing_new_leases(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    evidence, plan = _ready_store(tmp_path, spec)
    now = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    operational_path = tmp_path / "operational.sqlite3"
    calls: list[str] = []
    start_or_resume_run(
        run_selector=str(plan.run_id),
        operation="start",
        plan_root=evidence.root,
        operational_store_path=operational_path,
        worker_resolver=_resolver(calls),
        now=now,
    )
    store = OperationalStore.open_existing(operational_path)
    work = store.list_work_items(plan.run_id)[0]
    store.update_work_item(work.work_id, state="unknown", now=now + timedelta(seconds=1))
    with pytest.raises(RunControlError, match="unresolved external state"):
        start_or_resume_run(
            run_selector=str(plan.run_id),
            operation="resume",
            plan_root=evidence.root,
            operational_store_path=operational_path,
            worker_resolver=_resolver(calls),
            now=now + timedelta(seconds=2),
        )
    assert calls == [str(plan.trials[0].trial_id)]


def test_resume_expires_interrupted_active_attempt_before_new_leasing(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    evidence, plan = _ready_store(tmp_path, spec)
    initial = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    operational_path = tmp_path / "operational.sqlite3"
    calls: list[str] = []
    start_or_resume_run(
        run_selector=str(plan.run_id),
        operation="start",
        plan_root=evidence.root,
        operational_store_path=operational_path,
        worker_resolver=_resolver(calls),
        now=initial,
    )
    store = OperationalStore.open_existing(operational_path)
    work = store.list_work_items(plan.run_id)[0]
    store.update_work_item(work.work_id, state="queued", now=initial + timedelta(seconds=1))
    store.update_planned_trial(work.trial_id, state="queued", now=initial + timedelta(seconds=1))
    lease = store.acquire_lease(
        work.work_id,
        owner="interrupted-owner",
        now=initial + timedelta(seconds=2),
        ttl=timedelta(seconds=1),
    )
    attempt = store.create_attempt_for_lease(
        work.work_id,
        trial_id=work.trial_id,
        lease_id=lease.lease_id,
        candidate_index=1,
        retry_number=1,
        now=initial + timedelta(seconds=2),
    )
    store.update_work_item(work.work_id, state="running", now=initial + timedelta(seconds=2))
    store.update_planned_trial(work.trial_id, state="running", now=initial + timedelta(seconds=2))
    store.transition_attempt(attempt.attempt_id, state="running", now=initial + timedelta(seconds=2))

    with pytest.raises(RunControlError, match="unresolved external state"):
        start_or_resume_run(
            run_selector=str(plan.run_id),
            operation="resume",
            plan_root=evidence.root,
            operational_store_path=operational_path,
            worker_resolver=_resolver(calls),
            now=initial + timedelta(seconds=4),
        )
    assert store.get_work_item(work.work_id).state == "unknown"
    assert store.get_attempt(attempt.attempt_id).state == "unknown"
    assert calls == [str(plan.trials[0].trial_id)]


def test_local_preflight_failure_has_no_operational_side_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    evidence, plan = _ready_store(tmp_path, spec)
    monkeypatch.setattr(
        "aec_bench.harness.run_control._preflight_local_plan",
        lambda plan, tasks_root: (_ for _ in ()).throw(RunControlError("unsupported execution family")),
    )
    operational_path = tmp_path / "operational.sqlite3"

    with pytest.raises(RunControlError, match="unsupported execution family"):
        start_or_resume_run(
            run_selector=str(plan.run_id),
            operation="start",
            plan_root=evidence.root,
            operational_store_path=operational_path,
            tasks_root=tmp_path,
        )
    assert not operational_path.exists()


def test_cli_start_routes_explicit_paths_to_run_control(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Result:
        def as_dict(self) -> dict[str, object]:
            return {"operation": "start", "run_id": "run", "plan_id": "plan", "report": {}, "totals": {}}

    seen: dict[str, object] = {}

    def fake_start_or_resume_run(**kwargs: object) -> Result:
        seen.update(kwargs)
        return Result()

    monkeypatch.setattr("aec_bench.harness.run_control.start_or_resume_run", fake_start_or_resume_run)
    result = CliRunner().invoke(
        app,
        [
            "--json",
            "run",
            "start",
            "run",
            "--tasks-root",
            str(tmp_path / "tasks"),
            "--operational-store",
            str(tmp_path / "state.sqlite3"),
            "--plan-root",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert seen["run_selector"] == "run"
    assert seen["operation"] == "start"
    assert seen["tasks_root"] == tmp_path / "tasks"
