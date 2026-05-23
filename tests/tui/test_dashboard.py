# ABOUTME: Tests for the TUI dashboard screen with stat cards, sparkline, and experiment table.
# ABOUTME: Validates ASCII title, widget composition, async data loading, and error handling.

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import DataTable, Sparkline, Static

from aec_bench.tui.widgets.live_stats import (
    DatasetSummaryItem,
    DisciplineSummary,
    ExperimentSummary,
)
from aec_bench.tui.widgets.stat_card import StatCard


class DashboardTestApp(App[None]):
    """Minimal App wrapper for testing DashboardScreen."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__()
        self._kwargs = kwargs

    def on_mount(self) -> None:
        from aec_bench.tui.screens.dashboard import DashboardScreen

        self.push_screen(DashboardScreen(**self._kwargs))


def _make_app(**extra: object) -> DashboardTestApp:
    defaults: dict[str, object] = {
        "ledger_root": Path("/tmp/test-ledger"),
        "tasks_root": Path("/tmp/test-tasks"),
    }
    defaults.update(extra)
    return DashboardTestApp(**defaults)


# ---------------------------------------------------------------------------
# Widget composition tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_has_four_stat_cards() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        cards = app.screen.query(StatCard)
        assert len(cards) == 4


@pytest.mark.anyio
async def test_dashboard_has_sparkline() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        sparklines = app.screen.query(Sparkline)
        assert len(sparklines) >= 1


@pytest.mark.anyio
async def test_dashboard_has_experiment_table() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#experiment-table", DataTable)
        assert table is not None
        assert table.cursor_type == "row"


@pytest.mark.anyio
async def test_ascii_title_renders_block_art() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        title_widget = app.screen.query_one("#ascii-title", Static)
        plain = str(title_widget.render())
        assert "\u2588" in plain  # block character


@pytest.mark.anyio
async def test_pixel_art_renders() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        pixel_widget = app.screen.query_one("#pixel-art", Static)
        assert pixel_widget is not None


@pytest.mark.anyio
async def test_tagline_shows_benchmarked() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        tagline = app.screen.query_one("#tagline", Static)
        text = str(tagline.render())
        assert "benchmarked" in text.lower()


@pytest.mark.anyio
async def test_dashboard_advertises_agent_skills_without_vendor_lock_in() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        skills = app.screen.query_one("#agent-skills", Static)
        text = str(skills.render())
        assert "Agent Skills" in text
        assert "Claude" not in text


# ---------------------------------------------------------------------------
# Async data loading tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_async_loading_populates_experiment_table() -> None:
    experiments = [
        ExperimentSummary("voltage-drop-v2", 45, 0.82),
        ExperimentSummary("rlm-test", 5, 1.0),
    ]
    disciplines = [
        DisciplineSummary("electrical", 75, 14),
        DisciplineSummary("civil", 88, 72),
    ]
    datasets = [DatasetSummaryItem("my-suite", "1.0.0", 45)]

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        with (
            patch(
                "aec_bench.tui.screens.dashboard.build_experiments_summary",
                return_value=experiments,
            ),
            patch(
                "aec_bench.tui.screens.dashboard.build_disciplines_summary",
                return_value=disciplines,
            ),
            patch(
                "aec_bench.tui.screens.dashboard.build_datasets_summary",
                return_value=datasets,
            ),
        ):
            from aec_bench.tui.screens.dashboard import DashboardScreen

            screen = app.screen
            assert isinstance(screen, DashboardScreen)
            screen._load_dashboard_data()
            await pilot.pause()
            await pilot.pause()

        table = app.screen.query_one("#experiment-table", DataTable)
        assert table.row_count == 2


@pytest.mark.anyio
async def test_async_loading_updates_stat_cards() -> None:
    experiments = [
        ExperimentSummary("voltage-drop-v2", 45, 0.82),
        ExperimentSummary("rlm-test", 5, 1.0),
    ]
    disciplines = [
        DisciplineSummary("electrical", 75, 14),
        DisciplineSummary("civil", 88, 72),
    ]
    datasets = [DatasetSummaryItem("my-suite", "1.0.0", 45)]

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        with (
            patch(
                "aec_bench.tui.screens.dashboard.build_experiments_summary",
                return_value=experiments,
            ),
            patch(
                "aec_bench.tui.screens.dashboard.build_disciplines_summary",
                return_value=disciplines,
            ),
            patch(
                "aec_bench.tui.screens.dashboard.build_datasets_summary",
                return_value=datasets,
            ),
        ):
            from aec_bench.tui.screens.dashboard import DashboardScreen

            screen = app.screen
            assert isinstance(screen, DashboardScreen)
            screen._load_dashboard_data()
            await pilot.pause()
            await pilot.pause()

        cards = app.screen.query(StatCard)
        # Trials card should show "50" (45 + 5)
        values = [c.value for c in cards]
        assert "50" in values
        # Disciplines card should show "2"
        assert "2" in values


@pytest.mark.anyio
async def test_async_loading_updates_sparkline() -> None:
    experiments = [
        ExperimentSummary("voltage-drop-v2", 45, 0.82),
        ExperimentSummary("rlm-test", 5, 1.0),
    ]

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        with (
            patch(
                "aec_bench.tui.screens.dashboard.build_experiments_summary",
                return_value=experiments,
            ),
            patch(
                "aec_bench.tui.screens.dashboard.build_disciplines_summary",
                return_value=[],
            ),
            patch(
                "aec_bench.tui.screens.dashboard.build_datasets_summary",
                return_value=[],
            ),
            patch(
                "aec_bench.tui.screens.dashboard.read_trial_records",
                return_value=[],
            ),
        ):
            from aec_bench.tui.screens.dashboard import DashboardScreen

            screen = app.screen
            assert isinstance(screen, DashboardScreen)
            screen._load_dashboard_data()
            await pilot.pause()
            await pilot.pause()

        sparkline = app.screen.query_one(Sparkline)
        assert sparkline.data is not None
        assert len(sparkline.data) >= 1


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_screen_accepts_datasets_root() -> None:
    datasets_root = Path("/tmp/test-datasets")
    project_root = Path("/tmp/test-project")
    app = _make_app(datasets_root=datasets_root, project_root=project_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert hasattr(screen, "datasets_root")
        assert screen.datasets_root == datasets_root
        assert screen.project_root == project_root


@pytest.mark.anyio
async def test_experiment_table_starts_with_loading() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#experiment-table", DataTable)
        # Table should have columns configured even before data loads
        assert len(table.columns) == 3
