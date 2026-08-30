# ABOUTME: Tests the HTTP boundary for provider-neutral run progress.
# ABOUTME: Verifies configured status reads and missing configuration without attachment hydration.

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.execution.operational import OperationalStore
from aec_bench.web.app import create_app
from tests.harness.test_persisted_artifact_plan import _ready_store, _spec, _task


def test_run_progress_endpoint_returns_the_shared_projection(tmp_path: Path) -> None:
    task = _task(tmp_path)
    evidence_store, plan = _ready_store(tmp_path, _spec(task))
    operational = OperationalStore(tmp_path / "operational.sqlite3")
    operational.create_run(plan.run_id, spec_ref="run/resolved-run-spec.json")
    operational.put_plan(plan.plan_id, run_id=plan.run_id, plan_ref="run/run-plan.json")
    for trial in plan.trials:
        operational.put_planned_trial(
            trial.trial_id,
            plan_id=plan.plan_id,
            run_id=plan.run_id,
            ordinal=trial.ordinal,
        )
    client = TestClient(
        create_app(
            ledger_root=tmp_path / "ledger",
            tasks_root=tmp_path / "tasks",
            operational_store_path=operational.path,
            plan_root=evidence_store.root,
        )
    )

    response = client.get(f"/api/runs/{plan.run_id}/status")

    assert response.status_code == 200
    assert response.json()["run_id"] == str(plan.run_id)
    assert response.json()["status"] == "created"
    assert response.json()["planned"] == len(plan.trials)


def test_run_progress_endpoint_requires_explicit_roots(tmp_path: Path) -> None:
    client = TestClient(create_app(ledger_root=tmp_path / "ledger", tasks_root=tmp_path / "tasks"))

    response = client.get("/api/runs/019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa/status")

    assert response.status_code == 503
    assert "explicit operational_store_path and plan_root" in response.json()["detail"]
