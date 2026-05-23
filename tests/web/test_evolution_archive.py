# ABOUTME: Tests for the archive API endpoint on the evolution web routes.
# ABOUTME: Verifies the /evolution/{workspace}/archive endpoint is registered and returns real data.

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from aec_bench.web.app import create_app


def _make_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal valid evolution workspace directory.

    Returns (workspaces_root, workspace_dir).
    """
    workspaces_root = tmp_path / "workspaces"
    ws = workspaces_root / "test-ws"
    ws.mkdir(parents=True)
    (ws / "manifest.yaml").write_text(yaml.dump({"name": "test-ws"}), encoding="utf-8")
    (ws / "evolution.yaml").write_text(yaml.dump({"models": {"evolver": "claude-sonnet-4-20250514"}}), encoding="utf-8")
    return workspaces_root, ws


def _make_client(tmp_path: Path, workspaces_root: Path | None = None) -> TestClient:
    """Create a TestClient configured with the given workspaces_root."""
    ledger = tmp_path / "ledger"
    ledger.mkdir(exist_ok=True)
    tasks = tmp_path / "tasks"
    tasks.mkdir(exist_ok=True)
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks, workspaces_root=workspaces_root))


def test_archive_endpoint_exists() -> None:
    """The /archive route is registered on the evolution router."""
    from aec_bench.web.routes.evolution import router

    paths = [getattr(route, "path", "") for route in router.routes]
    assert any("archive" in p for p in paths)


def test_archive_no_workspaces_root_returns_404(tmp_path: Path) -> None:
    """Returns 404 when no workspaces root is configured."""
    client = _make_client(tmp_path, workspaces_root=None)
    response = client.get("/api/evolution/any-workspace/archive")
    assert response.status_code == 404


def test_archive_missing_workspace_returns_404(tmp_path: Path) -> None:
    """Returns 404 when the workspace directory does not exist."""
    workspaces_root = tmp_path / "workspaces"
    workspaces_root.mkdir()
    client = _make_client(tmp_path, workspaces_root=workspaces_root)
    response = client.get("/api/evolution/does-not-exist/archive")
    assert response.status_code == 404


def test_archive_no_archive_file_returns_empty_data(tmp_path: Path) -> None:
    """Returns empty summary and points when archive.json does not exist yet."""
    workspaces_root, _ws = _make_workspace(tmp_path)
    client = _make_client(tmp_path, workspaces_root=workspaces_root)
    response = client.get("/api/evolution/test-ws/archive")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["size"] == 0
    assert data["summary"]["coverage"] == 0.0
    assert data["summary"]["n_centroids"] == 200
    assert data["points_2d"] == []


def test_archive_loads_persisted_data(tmp_path: Path) -> None:
    """Returns real archive data when archive.json exists in the workspace."""
    from aec_bench.contracts.evolution import BehaviourDescriptor, WorkspaceSnapshot
    from aec_bench.evolution.archive import QDArchive

    workspaces_root, ws = _make_workspace(tmp_path)

    # Build and save a minimal archive with one entry.
    archive = QDArchive(n_centroids=10)
    bd = BehaviourDescriptor(
        token_cost=1000.0,
        verification_depth=0.5,
        tool_density=0.3,
        exploration_ratio=0.2,
        deliberation_ratio=0.1,
        reward=0.75,
    )
    snapshot = WorkspaceSnapshot(
        system_prompt="You are a helpful assistant.",
        workspace_version="evo-1",
    )
    archive.insert(bd, snapshot)
    archive.save(ws / "archive.json")

    client = _make_client(tmp_path, workspaces_root=workspaces_root)
    response = client.get("/api/evolution/test-ws/archive")
    assert response.status_code == 200
    data = response.json()

    summary = data["summary"]
    assert summary["size"] == 1
    assert summary["n_centroids"] == 10
    assert summary["coverage"] == 1 / 10
    assert summary["best_reward"] == 0.75

    points = data["points_2d"]
    assert len(points) == 1
    point = points[0]
    assert point["reward"] == 0.75
    assert point["version"] == "evo-1"
    assert "x" in point
    assert "y" in point
