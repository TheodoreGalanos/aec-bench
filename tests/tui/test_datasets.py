# ABOUTME: Tests for the Datasets screen with DataTable and drill-down.
# ABOUTME: Verifies dataset listing, async loading, and detail rendering.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import DataTable, Sparkline, Static

from aec_bench.tui.screens.datasets import DatasetsScreen


def _write_manifest(datasets_root: Path, name: str, version: str, task_count: int = 3) -> None:
    """Write a minimal valid DatasetManifest to the expected directory."""
    manifest_dir = datasets_root / name / version
    manifest_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        {
            "task_id": f"electrical/voltage-drop/inst-{i}",
            "task_path": f"tasks/electrical/voltage-drop/inst-{i}",
            "content_hash": f"hash-{i:04d}",
            "domain": "electrical",
            "difficulty": "medium",
            "tags": ["voltage"],
        }
        for i in range(task_count)
    ]
    manifest = {
        "name": name,
        "version": version,
        "content_hash": "abc123",
        "description": {
            "summary": f"Test dataset {name}",
            "domains": ["electrical"],
            "difficulty_distribution": {"easy": 1, "medium": 1, "hard": 1},
        },
        "created_at": datetime.now(UTC).isoformat(),
        "tasks": tasks,
        "source": {"method": "manual"},
    }
    (manifest_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class DatasetsTestApp(App[None]):
    """Minimal App wrapper for testing DatasetsScreen."""

    def __init__(self, datasets_root: Path) -> None:
        super().__init__()
        self._datasets_root = datasets_root

    def on_mount(self) -> None:
        self.push_screen(DatasetsScreen(datasets_root=self._datasets_root))


# ---------------------------------------------------------------------------
# Widget composition tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_datasets_screen_has_datatable(tmp_path: Path) -> None:
    """DatasetsScreen contains a DataTable with the correct id."""
    ds_root = tmp_path / "datasets"
    _write_manifest(ds_root, "bench-v1", "1.0.0")

    app = DatasetsTestApp(ds_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#datasets-table", DataTable)
        assert table is not None
        assert table.cursor_type == "row"


@pytest.mark.anyio
async def test_datasets_table_shows_loaded_data(tmp_path: Path) -> None:
    """Writing a manifest to the datasets root produces at least one row."""
    ds_root = tmp_path / "datasets"
    _write_manifest(ds_root, "bench-v1", "1.0.0", task_count=5)

    app = DatasetsTestApp(ds_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#datasets-table", DataTable)
        assert table.row_count >= 1


@pytest.mark.anyio
async def test_datasets_empty_state(tmp_path: Path) -> None:
    """When no datasets exist the table has zero rows."""
    ds_root = tmp_path / "datasets"
    ds_root.mkdir()

    app = DatasetsTestApp(ds_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#datasets-table", DataTable)
        assert table.row_count == 0


@pytest.mark.anyio
async def test_datasets_detail_panel_exists(tmp_path: Path) -> None:
    """The detail panel Static widget is present."""
    ds_root = tmp_path / "datasets"
    _write_manifest(ds_root, "bench-v1", "1.0.0")

    app = DatasetsTestApp(ds_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        detail = app.screen.query_one("#datasets-detail", Static)
        assert detail is not None


@pytest.mark.anyio
async def test_datasets_sparkline_exists(tmp_path: Path) -> None:
    """The Sparkline widget for difficulty distribution is present."""
    ds_root = tmp_path / "datasets"
    _write_manifest(ds_root, "bench-v1", "1.0.0")

    app = DatasetsTestApp(ds_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        sparkline = app.screen.query_one("#datasets-sparkline", Sparkline)
        assert sparkline is not None


@pytest.mark.anyio
async def test_datasets_multiple_manifests(tmp_path: Path) -> None:
    """Multiple dataset manifests produce matching row count."""
    ds_root = tmp_path / "datasets"
    _write_manifest(ds_root, "bench-v1", "1.0.0")
    _write_manifest(ds_root, "bench-v1", "2.0.0", task_count=10)
    _write_manifest(ds_root, "bench-v2", "1.0.0", task_count=2)

    app = DatasetsTestApp(ds_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#datasets-table", DataTable)
        assert table.row_count == 3


@pytest.mark.anyio
async def test_datasets_back_binding_pops_screen(tmp_path: Path) -> None:
    """Pressing escape pops the DatasetsScreen."""
    ds_root = tmp_path / "datasets"
    ds_root.mkdir()

    app = DatasetsTestApp(ds_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, DatasetsScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DatasetsScreen)
