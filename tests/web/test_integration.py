# ABOUTME: End-to-end integration tests for the full web API navigation flow.
# ABOUTME: Verifies all API endpoints respond, links connect, and annotation round-trips work.

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from tests.support.trial_record_factories import make_trial_record


def _write_task_instance(tasks_root: Path, task_id: str) -> None:
    """Write minimal task files so the leaderboard visibility filter can find them."""
    instance_dir = tasks_root / task_id
    (instance_dir / "environment").mkdir(parents=True, exist_ok=True)
    (instance_dir / "tests").mkdir(parents=True, exist_ok=True)
    (instance_dir / "instruction.md").write_text(
        "Write output to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        '[agent]\ntimeout_sec = 600\n\n[metadata]\nvisibility = "public"\n',
        encoding="utf-8",
    )


def _make_full_app(tmp_path: Path) -> TestClient:
    """Build a TestClient with 5 trial records and matching task files on disk."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()

    task_id = "electrical/voltage-drop/au-office-fitout"
    _write_task_instance(tasks, task_id)

    for i in range(5):
        write_trial_record(
            ledger_root=ledger,
            record=make_trial_record(
                experiment_id="exp-01",
                trial_id=f"trial-{i}",
                task={"task_id": task_id, "task_revision": "git-sha"},
            ),
        )
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks))


def test_full_api_navigation_flow(tmp_path: Path) -> None:
    """All API endpoints should return 200 with valid JSON."""
    client = _make_full_app(tmp_path)

    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    assert "experiments" in resp.json()

    resp = client.get("/api/triage?experiment=exp-01")
    assert resp.status_code == 200
    assert "trials" in resp.json()

    resp = client.get("/api/viewer/exp-01/trial-0")
    assert resp.status_code == 200
    assert "trial_id" in resp.json()

    resp = client.get("/api/analyze?rows=adapter&cols=discipline&metrics=mean_reward&experiment=exp-01")
    assert resp.status_code == 200
    assert "row_labels" in resp.json()

    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    assert "model_rows" in resp.json()


def test_annotation_round_trip(tmp_path: Path) -> None:
    """Annotate via API, verify it appears in triage API response."""
    client = _make_full_app(tmp_path)

    resp = client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-0",
            "experiment_id": "exp-01",
            "verdict": "fail",
            "notes": "wrong calculation",
        },
    )
    assert resp.status_code == 201

    resp = client.get("/api/triage/annotations?experiment=exp-01")
    assert resp.status_code == 200
    assert resp.json()["trial-0"]["verdict"] == "fail"

    resp = client.get("/api/triage?experiment=exp-01")
    assert resp.status_code == 200
    data = resp.json()
    annotated_trials = [t for t in data["trials"] if t["trial_id"] == "trial-0"]
    assert len(annotated_trials) == 1
    assert annotated_trials[0]["annotation_verdict"] == "fail"
