# ABOUTME: Tests for the dashboard API endpoint with experiment cards.
# ABOUTME: Verifies summary stats and experiment data via JSON API.

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from tests.support.trial_record_factories import make_trial_record


def _make_client(tmp_path: Path, n_trials: int = 3) -> TestClient:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    for i in range(n_trials):
        record = make_trial_record(
            experiment_id="exp-01",
            trial_id=f"trial-{i}",
        )
        write_trial_record(ledger_root=ledger, record=record)
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks))


def _make_client_with_trials(tmp_path: Path, n: int) -> TestClient:
    return _make_client(tmp_path, n_trials=n)


def test_dashboard_api_returns_json(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "experiments" in data
    assert "total_trials" in data
    assert "total_experiments" in data
    assert "mean_reward" in data
    assert "annotated_count" in data


def test_dashboard_api_with_data(tmp_path: Path) -> None:
    client = _make_client_with_trials(tmp_path, n=3)
    resp = client.get("/api/dashboard")
    data = resp.json()
    assert data["total_trials"] == 3
    assert data["total_experiments"] >= 1
    assert len(data["experiments"]) >= 1
    exp = data["experiments"][0]
    assert "experiment_id" in exp
    assert "trial_count" in exp
    assert "mean_reward" in exp
    assert "models" in exp
    assert "disciplines" in exp
    assert "adapters" in exp


def test_dashboard_api_empty_ledger(tmp_path: Path) -> None:
    client = _make_client(tmp_path, n_trials=0)
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_trials"] == 0
    assert data["total_experiments"] == 0


def test_dashboard_api_experiment_id_present(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/dashboard")
    data = resp.json()
    assert any(e["experiment_id"] == "exp-01" for e in data["experiments"])


def test_dashboard_api_trial_count_correct(tmp_path: Path) -> None:
    client = _make_client_with_trials(tmp_path, n=5)
    resp = client.get("/api/dashboard")
    data = resp.json()
    assert data["total_trials"] == 5
