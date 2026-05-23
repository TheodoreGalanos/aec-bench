# ABOUTME: Tests for the compare screen: data module aggregation logic and widget composition.
# ABOUTME: Validates matrix computation, model totals, trial pairing, and TUI rendering.

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import DataTable, Static

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import AgentReference, CostRecord, TaskReference
from aec_bench.tui.screens.compare import (
    CompareScreen,
    build_comparison_matrix,
    find_paired_trials,
)
from tests.support.trial_record_factories import make_trial_record

_VALID = ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True)


def _make(
    *,
    trial_id: str,
    model: str,
    task_id: str,
    reward: float = 1.0,
    cost_usd: float | None = None,
    experiment_id: str = "exp-1",
) -> object:
    overrides: dict = {
        "trial_id": trial_id,
        "experiment_id": experiment_id,
        "task": TaskReference(task_id=task_id, task_revision="sha"),
        "agent": AgentReference(adapter="tool_loop", model=model, adapter_revision="1.0.0"),
        "evaluation": EvaluationResult(reward=reward, validity=_VALID),
    }
    if cost_usd is not None:
        overrides["cost"] = CostRecord(estimated_cost_usd=cost_usd)
    return make_trial_record(**overrides)


def test_build_comparison_matrix_groups_by_model_and_task_type() -> None:
    records = [
        _make(
            trial_id="t1",
            model="sonnet",
            task_id="mechanical/heat-load/room-a",
            reward=1.0,
            cost_usd=0.10,
        ),
        _make(
            trial_id="t2",
            model="sonnet",
            task_id="mechanical/heat-load/room-b",
            reward=0.5,
            cost_usd=0.12,
        ),
        _make(
            trial_id="t3",
            model="haiku",
            task_id="mechanical/heat-load/room-a",
            reward=0.0,
            cost_usd=0.02,
        ),
    ]

    matrix = build_comparison_matrix(records)

    assert set(matrix.models) == {"sonnet", "haiku"}
    assert set(matrix.task_types) == {"heat-load"}

    sonnet_hl = matrix.cells[("sonnet", "heat-load")]
    assert sonnet_hl.n_trials == 2
    assert sonnet_hl.mean_reward == 0.75
    assert sonnet_hl.total_cost == 0.22

    haiku_hl = matrix.cells[("haiku", "heat-load")]
    assert haiku_hl.n_trials == 1
    assert haiku_hl.mean_reward == 0.0
    assert haiku_hl.total_cost == 0.02


def test_comparison_matrix_computes_model_totals() -> None:
    records = [
        _make(
            trial_id="t1",
            model="sonnet",
            task_id="mechanical/heat-load/r1",
            reward=1.0,
            cost_usd=0.10,
        ),
        _make(
            trial_id="t2",
            model="sonnet",
            task_id="electrical/voltage-drop/r2",
            reward=0.5,
            cost_usd=0.20,
        ),
    ]

    matrix = build_comparison_matrix(records)
    total = matrix.model_totals["sonnet"]

    assert total.n_trials == 2
    assert total.mean_reward == 0.75
    assert total.total_cost == pytest.approx(0.30)
    assert total.reward_per_dollar == pytest.approx(0.75 / 0.30)


def test_find_paired_trials_matches_same_task_across_models() -> None:
    records = [
        _make(trial_id="t1", model="sonnet", task_id="mechanical/heat-load/room-a"),
        _make(trial_id="t2", model="haiku", task_id="mechanical/heat-load/room-a"),
        _make(trial_id="t3", model="sonnet", task_id="mechanical/heat-load/room-b"),
    ]

    pairs = find_paired_trials(records)

    assert "mechanical/heat-load/room-a" in pairs
    paired = pairs["mechanical/heat-load/room-a"]
    assert set(paired.keys()) == {"sonnet", "haiku"}

    assert "mechanical/heat-load/room-b" in pairs


# ---------------------------------------------------------------------------
# Widget composition tests
# ---------------------------------------------------------------------------


def _write_trial(ledger: Path, record) -> None:
    """Write a trial record to the ledger directory."""
    trial_dir = ledger / record.experiment_id / record.trial_id
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "trial_record.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")


class CompareTestApp(App[None]):
    """Minimal App wrapper for testing CompareScreen."""

    def __init__(self, ledger_root: Path, experiment_id: str | None = None) -> None:
        super().__init__()
        self._ledger_root = ledger_root
        self._experiment_id = experiment_id

    def on_mount(self) -> None:
        self.push_screen(
            CompareScreen(
                ledger_root=self._ledger_root,
                experiment_id=self._experiment_id,
            )
        )


@pytest.mark.anyio
async def test_compare_screen_has_datatable(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", model="sonnet", task_id="electrical/voltage-drop/r1", reward=1.0),
        _make(trial_id="t2", model="haiku", task_id="electrical/voltage-drop/r2", reward=0.5),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = CompareTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#compare-table", DataTable)
        assert table is not None
        assert table.row_count >= 1


@pytest.mark.anyio
async def test_compare_table_has_fixed_columns(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", model="sonnet", task_id="electrical/voltage-drop/r1", reward=1.0),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = CompareTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#compare-table", DataTable)
        assert table.fixed_columns == 1


@pytest.mark.anyio
async def test_compare_table_has_row_cursor(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", model="sonnet", task_id="electrical/voltage-drop/r1"),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = CompareTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#compare-table", DataTable)
        assert table.cursor_type == "row"


@pytest.mark.anyio
async def test_compare_screen_has_detail_panel(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", model="sonnet", task_id="electrical/voltage-drop/r1"),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = CompareTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        detail = app.screen.query_one("#compare-detail", Static)
        assert detail is not None


@pytest.mark.anyio
async def test_compare_empty_ledger_renders_without_crash(tmp_path: Path) -> None:
    """CompareScreen handles empty ledger gracefully."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()

    app = CompareTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#compare-table", DataTable)
        assert table.row_count == 0


@pytest.mark.anyio
async def test_compare_table_has_correct_row_count(tmp_path: Path) -> None:
    """Two task types should produce 3 rows (2 task type rows + 1 overall row)."""
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", model="sonnet", task_id="electrical/voltage-drop/r1", reward=1.0),
        _make(trial_id="t2", model="sonnet", task_id="civil/drainage/r1", reward=0.5),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = CompareTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#compare-table", DataTable)
        # 2 task type rows + 1 overall row = 3
        assert table.row_count == 3


@pytest.mark.anyio
async def test_compare_back_binding_pops_screen(tmp_path: Path) -> None:
    """Pressing escape should pop the CompareScreen."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()

    app = CompareTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, CompareScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, CompareScreen)
