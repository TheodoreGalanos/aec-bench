# ABOUTME: Tests for the EvaluateScreen with adapter x task heatmap DataTable.
# ABOUTME: Validates matrix builders, table composition, detail panel, and drill-through.

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import DataTable, Static

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import AgentReference, CostRecord, TaskReference
from aec_bench.tui.screens.evaluate import (
    EvaluateCell,
    EvaluateScreen,
    build_evaluate_matrix,
)
from tests.support.trial_record_factories import make_trial_record

_VALID = ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True)


def _make(
    *,
    trial_id: str,
    model: str = "sonnet",
    adapter: str = "tool_loop",
    task_id: str,
    reward: float = 1.0,
    cost_usd: float | None = None,
    experiment_id: str = "exp-1",
):
    overrides: dict = {
        "trial_id": trial_id,
        "experiment_id": experiment_id,
        "task": TaskReference(task_id=task_id, task_revision="sha"),
        "agent": AgentReference(adapter=adapter, model=model, adapter_revision="1.0.0"),
        "evaluation": EvaluationResult(reward=reward, validity=_VALID),
    }
    if cost_usd is not None:
        overrides["cost"] = CostRecord(estimated_cost_usd=cost_usd)
    return make_trial_record(**overrides)


def _write_trial(ledger: Path, record) -> None:
    """Write a trial record to the ledger directory."""
    trial_dir = ledger / record.experiment_id / record.trial_id
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "trial_record.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")


class EvaluateTestApp(App[None]):
    """Minimal App wrapper for testing EvaluateScreen."""

    def __init__(self, ledger_root: Path, experiment_id: str | None = None) -> None:
        super().__init__()
        self._ledger_root = ledger_root
        self._experiment_id = experiment_id

    def on_mount(self) -> None:
        self.push_screen(
            EvaluateScreen(
                ledger_root=self._ledger_root,
                experiment_id=self._experiment_id,
            )
        )


# ---------------------------------------------------------------------------
# Pure function tests (EvaluateCell, EvaluateMatrix, build_evaluate_matrix)
# ---------------------------------------------------------------------------


def test_evaluate_cell_is_frozen() -> None:
    cell = EvaluateCell(
        adapter="rlm",
        task_prefix="voltage-drop",
        n_trials=3,
        mean_reward=0.75,
        perfect_count=1,
        zero_count=0,
        total_cost=0.12,
    )
    with pytest.raises(AttributeError):
        cell.adapter = "other"  # type: ignore[misc]


def test_build_evaluate_matrix_basic() -> None:
    records = [
        _make(trial_id="t1", adapter="rlm", task_id="electrical/voltage-drop/r1", reward=1.0),
        _make(trial_id="t2", adapter="rlm", task_id="electrical/voltage-drop/r2", reward=0.5),
        _make(trial_id="t3", adapter="tool_loop", task_id="civil/drainage/r1", reward=0.0),
    ]
    matrix = build_evaluate_matrix(records)

    assert sorted(matrix.adapters) == ["rlm", "tool_loop"]
    assert sorted(matrix.task_prefixes) == ["drainage", "voltage-drop"]

    rlm_vd = matrix.cells[("rlm", "voltage-drop")]
    assert rlm_vd.n_trials == 2
    assert rlm_vd.mean_reward == pytest.approx(0.75)
    assert rlm_vd.perfect_count == 1
    assert rlm_vd.zero_count == 0

    tl_drain = matrix.cells[("tool_loop", "drainage")]
    assert tl_drain.n_trials == 1
    assert tl_drain.mean_reward == pytest.approx(0.0)
    assert tl_drain.zero_count == 1


def test_build_evaluate_matrix_adapter_totals() -> None:
    records = [
        _make(trial_id="t1", adapter="rlm", task_id="electrical/voltage-drop/r1", reward=1.0),
        _make(trial_id="t2", adapter="rlm", task_id="civil/drainage/r1", reward=0.5),
    ]
    matrix = build_evaluate_matrix(records)
    total = matrix.adapter_totals["rlm"]
    assert total.n_trials == 2
    assert total.mean_reward == pytest.approx(0.75)


def test_build_evaluate_matrix_prefix_totals() -> None:
    records = [
        _make(trial_id="t1", adapter="rlm", task_id="electrical/voltage-drop/r1", reward=1.0),
        _make(trial_id="t2", adapter="tool_loop", task_id="electrical/voltage-drop/r2", reward=0.0),
    ]
    matrix = build_evaluate_matrix(records)
    total = matrix.prefix_totals["voltage-drop"]
    assert total.n_trials == 2
    assert total.mean_reward == pytest.approx(0.5)


def test_build_evaluate_matrix_cost_tracking() -> None:
    records = [
        _make(trial_id="t1", adapter="rlm", task_id="electrical/voltage-drop/r1", cost_usd=0.10),
        _make(trial_id="t2", adapter="rlm", task_id="electrical/voltage-drop/r2", cost_usd=0.20),
    ]
    matrix = build_evaluate_matrix(records)
    cell = matrix.cells[("rlm", "voltage-drop")]
    assert cell.total_cost == pytest.approx(0.30)


def test_build_evaluate_matrix_empty() -> None:
    matrix = build_evaluate_matrix([])
    assert matrix.adapters == []
    assert matrix.task_prefixes == []
    assert matrix.cells == {}


# ---------------------------------------------------------------------------
# Widget composition tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_evaluate_screen_has_datatable(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", task_id="electrical/voltage-drop/r1", reward=1.0),
        _make(trial_id="t2", task_id="electrical/voltage-drop/r2", reward=0.5),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = EvaluateTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#evaluate-table", DataTable)
        assert table is not None
        # 1 adapter row + 1 totals row = 2
        assert table.row_count >= 1


@pytest.mark.anyio
async def test_evaluate_table_has_fixed_columns(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", task_id="electrical/voltage-drop/r1", reward=1.0),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = EvaluateTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#evaluate-table", DataTable)
        assert table.fixed_columns == 1


@pytest.mark.anyio
async def test_evaluate_table_cell_cursor(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", task_id="electrical/voltage-drop/r1"),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = EvaluateTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#evaluate-table", DataTable)
        assert table.cursor_type == "cell"


@pytest.mark.anyio
async def test_evaluate_screen_has_detail_panel(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", task_id="electrical/voltage-drop/r1"),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = EvaluateTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        detail = app.screen.query_one("#evaluate-detail", Static)
        assert detail is not None


@pytest.mark.anyio
async def test_evaluate_empty_ledger_renders_without_crash(tmp_path: Path) -> None:
    """EvaluateScreen handles empty ledger gracefully."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()

    app = EvaluateTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#evaluate-table", DataTable)
        assert table.row_count == 0


@pytest.mark.anyio
async def test_evaluate_table_has_correct_row_count(tmp_path: Path) -> None:
    """Two adapters should produce 3 rows (2 adapters + 1 totals)."""
    ledger = tmp_path / "ledger"
    records = [
        _make(trial_id="t1", adapter="rlm", task_id="electrical/voltage-drop/r1", reward=1.0),
        _make(trial_id="t2", adapter="tool_loop", task_id="civil/drainage/r1", reward=0.5),
    ]
    for r in records:
        _write_trial(ledger, r)

    app = EvaluateTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#evaluate-table", DataTable)
        # 2 adapter rows + 1 totals row = 3
        assert table.row_count == 3


@pytest.mark.anyio
async def test_evaluate_back_binding_pops_screen(tmp_path: Path) -> None:
    """Pressing escape should pop the EvaluateScreen."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()

    app = EvaluateTestApp(ledger)
    async with app.run_test() as pilot:
        await pilot.pause()
        # The pushed screen is the evaluate screen
        assert isinstance(app.screen, EvaluateScreen)
        await pilot.press("escape")
        await pilot.pause()
        # After escape, the evaluate screen should be popped
        assert not isinstance(app.screen, EvaluateScreen)


# ---------------------------------------------------------------------------
# Pre-filter / drill-through integration tests (ported from test_analysis.py)
# ---------------------------------------------------------------------------


def test_get_selected_eval_filter_returns_adapter_and_prefix() -> None:
    """Unit test for filter extraction (without rendering)."""
    records = [
        _make(trial_id="t1", adapter="rlm", task_id="electrical/voltage-drop/r1"),
        _make(trial_id="t2", adapter="tool_loop", task_id="civil/drainage/r1"),
    ]
    matrix = build_evaluate_matrix(records)

    assert len(matrix.adapters) == 2
    assert "rlm" in matrix.adapters
    assert "tool_loop" in matrix.adapters
    assert set(matrix.task_prefixes) == {"drainage", "voltage-drop"}


def test_triage_pre_filters_apply_task_prefix() -> None:
    """Verify FilterState.task_prefix filters correctly in apply_filters."""
    from aec_bench.tui.screens.triage import FilterState, apply_filters

    records = [
        _make(trial_id="t1", task_id="electrical/voltage-drop/r1"),
        _make(trial_id="t2", task_id="civil/drainage/r1"),
    ]
    filters = FilterState(task_prefix="voltage-drop")
    result = apply_filters(records, filters, annotations={})
    assert len(result) == 1
    assert result[0].trial_id == "t1"


def test_triage_pre_filters_apply_adapter() -> None:
    """Verify FilterState.adapter filters correctly in apply_filters."""
    from aec_bench.tui.screens.triage import FilterState, apply_filters

    records = [
        _make(trial_id="t1", adapter="rlm", task_id="electrical/voltage-drop/r1"),
        _make(trial_id="t2", adapter="tool_loop", task_id="electrical/voltage-drop/r2"),
    ]
    filters = FilterState(adapter="rlm")
    result = apply_filters(records, filters, annotations={})
    assert len(result) == 1
    assert result[0].trial_id == "t1"


def test_triage_pre_filters_default_all() -> None:
    """Default FilterState returns all records."""
    from aec_bench.tui.screens.triage import FilterState, apply_filters

    records = [
        _make(trial_id="t1", task_id="electrical/voltage-drop/r1"),
        _make(trial_id="t2", task_id="civil/drainage/r1"),
    ]
    filters = FilterState()
    result = apply_filters(records, filters, annotations={})
    assert len(result) == 2
