# ABOUTME: Tests for the Leaderboard screen ranking models by reward.
# ABOUTME: Verifies DataTable population, sorting, and detail panel display.

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import DataTable, Static

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import CostRecord
from aec_bench.ledger.writer import write_trial_record
from aec_bench.tui.screens.leaderboard import (
    LeaderboardScreen,
    ModelStats,
    _compute_model_stats,
    _render_model_detail,
)
from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Helper wrappers
# ---------------------------------------------------------------------------


class LeaderboardTestApp(App[None]):
    """Minimal App wrapper for testing LeaderboardScreen."""

    def __init__(self, ledger_root: Path) -> None:
        super().__init__()
        self._ledger_root = ledger_root

    def on_mount(self) -> None:
        self.push_screen(LeaderboardScreen(ledger_root=self._ledger_root))


async def _wait_for_rows(pilot: object, table: DataTable, expected: int) -> None:
    """Wait for background screen loading to settle."""
    for _ in range(5):
        if table.row_count == expected:
            return
        await pilot.pause()


# ---------------------------------------------------------------------------
# Pure function unit tests
# ---------------------------------------------------------------------------


def test_compute_model_stats_empty() -> None:
    """Empty record list produces empty stats."""
    result = _compute_model_stats([])
    assert result == []


def test_compute_model_stats_single_model() -> None:
    """Single model with one trial produces one ModelStats entry."""
    record = make_trial_record(
        evaluation=EvaluationResult(
            reward=0.8,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
        cost=CostRecord(estimated_cost_usd=0.01),
    )
    stats = _compute_model_stats([record])
    assert len(stats) == 1
    assert stats[0].mean_reward == pytest.approx(0.8)
    assert stats[0].trial_count == 1
    assert stats[0].total_cost_usd == pytest.approx(0.01)


def test_compute_model_stats_sorted_descending() -> None:
    """Models are sorted by mean reward descending (rank 1 = highest)."""
    from aec_bench.contracts.trial_record import AgentReference

    record_a = make_trial_record(
        trial_id="trial-a",
        evaluation=EvaluationResult(
            reward=0.3,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
    )
    record_b = make_trial_record(
        trial_id="trial-b",
        agent=AgentReference(
            adapter="tool_loop",
            model="openai:gpt-4o",
            adapter_revision="git-sha-adapter",
            configuration={},
        ),
        evaluation=EvaluationResult(
            reward=0.9,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
    )

    stats = _compute_model_stats([record_a, record_b])
    assert stats[0].mean_reward > stats[1].mean_reward
    assert stats[0].mean_reward == pytest.approx(0.9)
    assert stats[1].mean_reward == pytest.approx(0.3)


def test_render_model_detail_format() -> None:
    """_render_model_detail returns a multi-line string with rank and model."""
    stats = ModelStats(
        model="anthropic:claude-sonnet-4-20250514",
        trial_count=5,
        mean_reward=0.72,
        total_cost_usd=0.0345,
    )
    text = _render_model_detail(1, stats)
    assert "Rank #1" in text
    assert "anthropic:claude-sonnet-4-20250514" in text
    assert "5" in text


# ---------------------------------------------------------------------------
# Widget tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_leaderboard_has_datatable(tmp_path: Path) -> None:
    """LeaderboardScreen contains a DataTable with the correct id."""
    app = LeaderboardTestApp(tmp_path / "ledger")
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#leaderboard-table", DataTable)
        assert table is not None
        assert table.cursor_type == "row"


@pytest.mark.anyio
async def test_leaderboard_ranks_models(tmp_path: Path) -> None:
    """Two distinct models from ledger produce two rows."""
    ledger_root = tmp_path / "ledger"
    from aec_bench.contracts.trial_record import AgentReference

    record_a = make_trial_record(
        trial_id="trial-a",
        experiment_id="exp-1",
        evaluation=EvaluationResult(
            reward=1.0,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
    )
    record_b = make_trial_record(
        trial_id="trial-b",
        experiment_id="exp-1",
        agent=AgentReference(
            adapter="tool_loop",
            model="openai:gpt-4o",
            adapter_revision="git-sha-adapter",
            configuration={},
        ),
        evaluation=EvaluationResult(
            reward=0.5,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
    )
    write_trial_record(ledger_root=ledger_root, record=record_a)
    write_trial_record(ledger_root=ledger_root, record=record_b)

    app = LeaderboardTestApp(ledger_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#leaderboard-table", DataTable)
        await _wait_for_rows(pilot, table, 2)
        assert table.row_count == 2


@pytest.mark.anyio
async def test_leaderboard_empty_state(tmp_path: Path) -> None:
    """Empty ledger root produces a table with zero rows."""
    ledger_root = tmp_path / "ledger"

    app = LeaderboardTestApp(ledger_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#leaderboard-table", DataTable)
        assert table.row_count == 0


@pytest.mark.anyio
async def test_leaderboard_detail_panel_exists(tmp_path: Path) -> None:
    """The detail panel Static widget is present."""
    app = LeaderboardTestApp(tmp_path / "ledger")
    async with app.run_test() as pilot:
        await pilot.pause()
        detail = app.screen.query_one("#leaderboard-detail", Static)
        assert detail is not None


@pytest.mark.anyio
async def test_leaderboard_back_binding_pops_screen(tmp_path: Path) -> None:
    """Pressing escape pops the LeaderboardScreen."""
    app = LeaderboardTestApp(tmp_path / "ledger")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LeaderboardScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, LeaderboardScreen)
