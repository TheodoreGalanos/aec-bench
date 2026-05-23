# ABOUTME: Tests for the evolution API endpoints serving workspace discovery and git-based diffs.
# ABOUTME: Verifies workspace listing, cycle detail, file tree, file content, and diff retrieval.

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from aec_bench.web.app import create_app


def _git(cwd: Path, *args: str) -> None:
    """Run a git command in the given directory, raising on failure."""
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _make_evolution_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal evolution workspace with git history and evo tags.

    Returns (workspaces_root, workspace_dir).
    """
    workspaces_root = tmp_path / "workspaces"
    ws = workspaces_root / "my-workspace"
    ws.mkdir(parents=True)

    # Write manifest.yaml
    manifest = {"name": "my-workspace", "version": "0.1.0"}
    (ws / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")

    # Write evolution.yaml
    evolution = {"models": {"evolver": "claude-sonnet-4-20250514"}}
    (ws / "evolution.yaml").write_text(yaml.dump(evolution), encoding="utf-8")

    # Write initial prompt file
    prompts_dir = ws / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are an engineering assistant.", encoding="utf-8")

    # Init git and create evo-0 tag
    _git(ws, "init")
    _git(ws, "add", ".")
    _git(ws, "commit", "-m", "initial commit")
    _git(ws, "tag", "-a", "evo-0", "-m", "score 0.50")

    # Modify prompt and create evo-1 tag
    (prompts_dir / "system.md").write_text(
        "You are an expert engineering assistant with deep domain knowledge.",
        encoding="utf-8",
    )
    _git(ws, "add", ".")
    _git(ws, "commit", "-m", "cycle 1 improvements")
    _git(ws, "tag", "-a", "evo-1", "-m", "score 0.75")

    return workspaces_root, ws


def _make_client(
    tmp_path: Path,
    *,
    workspaces_root: Path | None = None,
) -> TestClient:
    """Create a TestClient with the given workspaces_root."""
    ledger = tmp_path / "ledger"
    ledger.mkdir(exist_ok=True)
    tasks = tmp_path / "tasks"
    tasks.mkdir(exist_ok=True)
    return TestClient(
        create_app(
            ledger_root=ledger,
            tasks_root=tasks,
            workspaces_root=workspaces_root,
        )
    )


# ── Workspace listing ────────────────────────────────────────────────────


def test_workspaces_list(tmp_path: Path) -> None:
    """GET /api/evolution/workspaces returns discovered workspaces."""
    workspaces_root, _ws = _make_evolution_workspace(tmp_path)
    client = _make_client(tmp_path, workspaces_root=workspaces_root)

    resp = client.get("/api/evolution/workspaces")
    assert resp.status_code == 200
    data = resp.json()
    assert "workspaces" in data
    assert len(data["workspaces"]) == 1

    ws_data = data["workspaces"][0]
    assert ws_data["name"] == "my-workspace"
    assert ws_data["cycles"] == 1
    assert ws_data["best_score"] == 0.75
    assert ws_data["model"] == "claude-sonnet-4-20250514"


def test_workspaces_list_empty_when_no_root(tmp_path: Path) -> None:
    """GET /api/evolution/workspaces returns empty list when no workspaces_root."""
    client = _make_client(tmp_path, workspaces_root=None)

    resp = client.get("/api/evolution/workspaces")
    assert resp.status_code == 200
    data = resp.json()
    assert data["workspaces"] == []


# ── Workspace detail ─────────────────────────────────────────────────────


def test_workspace_detail(tmp_path: Path) -> None:
    """GET /api/evolution/{workspace} returns full cycle data."""
    workspaces_root, _ws = _make_evolution_workspace(tmp_path)
    client = _make_client(tmp_path, workspaces_root=workspaces_root)

    resp = client.get("/api/evolution/my-workspace")
    assert resp.status_code == 200
    data = resp.json()
    assert data["workspace_name"] == "my-workspace"
    assert data["model"] == "claude-sonnet-4-20250514"
    assert data["total_cycles"] == 1
    assert len(data["cycles"]) == 1

    cycle = data["cycles"][0]
    assert cycle["cycle"] == 1
    assert cycle["version_tag"] == "evo-1"
    assert cycle["score"] == 0.75
    # prompt_diff should contain something since we changed the prompt
    assert len(cycle["prompt_diff"]) > 0


# ── File tree ────────────────────────────────────────────────────────────


def test_workspace_tree(tmp_path: Path) -> None:
    """GET /api/evolution/{workspace}/tree/{version} returns file tree."""
    workspaces_root, _ws = _make_evolution_workspace(tmp_path)
    client = _make_client(tmp_path, workspaces_root=workspaces_root)

    resp = client.get("/api/evolution/my-workspace/tree/evo-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "evo-1"
    assert "tree" in data
    # The tree should contain our files
    tree = data["tree"]
    assert isinstance(tree, list)
    # Should have at least manifest.yaml, evolution.yaml, and prompts/ dir
    names = {node["name"] for node in tree}
    assert "manifest.yaml" in names or "prompts" in names


# ── File content ─────────────────────────────────────────────────────────


def test_workspace_file(tmp_path: Path) -> None:
    """GET /api/evolution/{workspace}/file/{version}/{path} returns file content."""
    workspaces_root, _ws = _make_evolution_workspace(tmp_path)
    client = _make_client(tmp_path, workspaces_root=workspaces_root)

    resp = client.get("/api/evolution/my-workspace/file/evo-1/prompts/system.md")
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "prompts/system.md"
    assert data["version"] == "evo-1"
    assert "expert engineering assistant" in data["content"]
    assert data["language"] == "markdown"


# ── File diff ────────────────────────────────────────────────────────────


def test_workspace_diff(tmp_path: Path) -> None:
    """GET /api/evolution/{workspace}/diff/{version}/{path} returns unified diff."""
    workspaces_root, _ws = _make_evolution_workspace(tmp_path)
    client = _make_client(tmp_path, workspaces_root=workspaces_root)

    resp = client.get("/api/evolution/my-workspace/diff/evo-1/prompts/system.md")
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "prompts/system.md"
    assert data["to_version"] == "evo-1"
    assert data["from_version"] == "evo-0"
    # The diff should show old and new lines
    assert len(data["diff"]) > 0


# ── 404 handling ─────────────────────────────────────────────────────────


def test_workspace_not_found(tmp_path: Path) -> None:
    """GET /api/evolution/{workspace} returns 404 for nonexistent workspace."""
    workspaces_root = tmp_path / "workspaces"
    workspaces_root.mkdir()
    client = _make_client(tmp_path, workspaces_root=workspaces_root)

    resp = client.get("/api/evolution/nonexistent-workspace")
    assert resp.status_code == 404
