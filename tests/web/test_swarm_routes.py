# ABOUTME: Integration tests for swarm Mission Control API endpoints.
# ABOUTME: Tests state snapshot, event log, and run listing against fixture data.

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aec_bench.web.app import create_app


@pytest.fixture()
def swarm_workspace(tmp_path: Path):
    ws = tmp_path / "workspaces" / "test-swarm"
    ws.mkdir(parents=True)
    (ws / "manifest.yaml").write_text("task_path: tasks/test\n")
    (ws / "evolution.yaml").write_text("strategy: qd\nmodel: sonnet-4.6\n")

    swarm_dir = ws / "_swarm_runs"
    swarm_dir.mkdir()

    events = [
        {
            "event_type": "swarm_started",
            "timestamp": "2026-04-08T02:19:14Z",
            "agent_id": None,
            "payload": {"run_id": "abc123", "agent_count": 2, "max_cost_usd": 5.0},
            "sequence_number": 0,
        },
        {
            "event_type": "agent_spawned",
            "timestamp": "2026-04-08T02:19:15Z",
            "agent_id": "agent-0",
            "payload": {"model": "sonnet-4.6"},
            "sequence_number": 1,
        },
        {
            "event_type": "eval_completed",
            "timestamp": "2026-04-08T02:20:00Z",
            "agent_id": "agent-0",
            "payload": {"score": 0.87, "version": "evo-1"},
            "sequence_number": 2,
        },
    ]
    with open(swarm_dir / "events.jsonl", "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    summary = {
        "run_id": "abc123",
        "workspace_name": "test-swarm",
        "total_evals": 1,
        "total_cost_usd": 1.5,
        "elapsed_seconds": 60.0,
        "best_score": 0.87,
        "agent_count": 2,
    }
    (swarm_dir / "summary.json").write_text(json.dumps(summary))

    return tmp_path


@pytest.fixture()
def client(swarm_workspace: Path):
    app = create_app(
        ledger_root=swarm_workspace / "ledger",
        tasks_root=swarm_workspace / "tasks",
        workspaces_root=swarm_workspace / "workspaces",
    )
    return TestClient(app)


def test_swarm_runs_list(client):
    resp = client.get("/api/evolution/swarm/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert len(data["runs"]) >= 1
    assert data["runs"][0]["run_id"] == "abc123"


def test_swarm_state_snapshot(client):
    resp = client.get("/api/evolution/swarm/test-swarm/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "abc123"
    assert "agents" in data
    assert "budget" in data
    assert "centroids" in data
    assert "events" in data


def test_swarm_events_with_after(client):
    resp = client.get("/api/evolution/swarm/test-swarm/events?after=0")
    assert resp.status_code == 200
    data = resp.json()
    assert all(e["sequence_number"] > 0 for e in data["events"])


def test_swarm_state_404_unknown_workspace(client):
    resp = client.get("/api/evolution/swarm/nonexistent/state")
    assert resp.status_code == 404
