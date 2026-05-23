# ABOUTME: Tests for the TUI triage screen: annotation I/O, filtering, sorting, DataTable.
# ABOUTME: Validates annotation persistence in _annotations/ subdirectories within the ledger.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import DataTable

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.tui.screens.triage import (
    FilterState,
    TriageAnnotation,
    TriageScreen,
    apply_filters,
    apply_sort,
    delete_annotation,
    load_annotations,
    save_annotation,
)
from tests.support.trial_record_factories import make_trial_record


def test_save_annotation_creates_directory_and_file(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "experiment-001"
    experiment_dir.mkdir()

    annotation = TriageAnnotation.create(verdict="pass", notes="looks good")
    save_annotation(experiment_dir, "trial-abc", annotation)

    annotation_path = experiment_dir / "_annotations" / "trial-abc.json"
    assert annotation_path.exists()
    data = json.loads(annotation_path.read_text(encoding="utf-8"))
    assert data["verdict"] == "pass"
    assert data["notes"] == "looks good"
    assert "timestamp" in data


def test_save_annotation_overwrites_existing(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "experiment-001"
    experiment_dir.mkdir()

    first = TriageAnnotation.create(verdict="pass", notes="")
    save_annotation(experiment_dir, "trial-abc", first)
    second = TriageAnnotation.create(verdict="fail", notes="actually bad")
    save_annotation(experiment_dir, "trial-abc", second)

    data = json.loads((experiment_dir / "_annotations" / "trial-abc.json").read_text(encoding="utf-8"))
    assert data["verdict"] == "fail"
    assert data["notes"] == "actually bad"


def test_load_annotations_reads_all_files(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "experiment-001"
    ann_dir = experiment_dir / "_annotations"
    ann_dir.mkdir(parents=True)

    (ann_dir / "trial-a.json").write_text(
        json.dumps({"verdict": "pass", "notes": "", "timestamp": "2026-03-20T10:00:00Z"})
    )
    (ann_dir / "trial-b.json").write_text(
        json.dumps({"verdict": "fail", "notes": "broken", "timestamp": "2026-03-20T10:01:00Z"})
    )

    annotations = load_annotations(experiment_dir)
    assert len(annotations) == 2
    assert annotations["trial-a"].verdict == "pass"
    assert annotations["trial-b"].verdict == "fail"
    assert annotations["trial-b"].notes == "broken"


def test_load_annotations_returns_empty_when_no_directory(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "experiment-001"
    experiment_dir.mkdir()

    annotations = load_annotations(experiment_dir)
    assert annotations == {}


def test_delete_annotation_removes_file(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "experiment-001"
    ann_dir = experiment_dir / "_annotations"
    ann_dir.mkdir(parents=True)
    (ann_dir / "trial-a.json").write_text(
        json.dumps({"verdict": "pass", "notes": "", "timestamp": "2026-03-20T10:00:00Z"})
    )

    delete_annotation(experiment_dir, "trial-a")
    assert not (ann_dir / "trial-a.json").exists()


def test_delete_annotation_noop_when_missing(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "experiment-001"
    experiment_dir.mkdir()

    delete_annotation(experiment_dir, "nonexistent")  # should not raise


# --- Filter and sort tests ---

_VALID = ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True)


def _make_records() -> list[TrialRecord]:
    return [
        make_trial_record(trial_id="t1", evaluation=EvaluationResult(reward=0.0, validity=_VALID)),
        make_trial_record(trial_id="t2", evaluation=EvaluationResult(reward=0.5, validity=_VALID)),
        make_trial_record(trial_id="t3", evaluation=EvaluationResult(reward=1.0, validity=_VALID)),
    ]


def test_filter_by_reward_zero() -> None:
    records = _make_records()
    filters = FilterState(reward="zero")
    result = apply_filters(records, filters, annotations={})
    assert len(result) == 1
    assert result[0].trial_id == "t1"


def test_filter_by_reward_partial() -> None:
    records = _make_records()
    filters = FilterState(reward="partial")
    result = apply_filters(records, filters, annotations={})
    assert len(result) == 1
    assert result[0].trial_id == "t2"


def test_filter_by_reward_perfect() -> None:
    records = _make_records()
    filters = FilterState(reward="perfect")
    result = apply_filters(records, filters, annotations={})
    assert len(result) == 1
    assert result[0].trial_id == "t3"


def test_filter_by_annotated() -> None:
    records = _make_records()
    annotations = {"t2": TriageAnnotation.create(verdict="pass")}
    filters = FilterState(annotated="annotated")
    result = apply_filters(records, filters, annotations=annotations)
    assert len(result) == 1
    assert result[0].trial_id == "t2"


def test_filter_by_unannotated() -> None:
    records = _make_records()
    annotations = {"t2": TriageAnnotation.create(verdict="pass")}
    filters = FilterState(annotated="unannotated")
    result = apply_filters(records, filters, annotations=annotations)
    assert len(result) == 2
    assert all(r.trial_id != "t2" for r in result)


def test_sort_reward_ascending() -> None:
    records = _make_records()
    result = apply_sort(records, sort_key="reward_asc")
    assert [r.evaluation.reward for r in result] == [0.0, 0.5, 1.0]


def test_sort_reward_descending() -> None:
    records = _make_records()
    result = apply_sort(records, sort_key="reward_desc")
    assert [r.evaluation.reward for r in result] == [1.0, 0.5, 0.0]


# --- Screen tests ---


class TriageTestApp(App[None]):
    """Minimal App wrapper for testing TriageScreen."""

    def __init__(self, ledger_root: Path, experiment_id: str | None = None) -> None:
        super().__init__()
        self._ledger_root = ledger_root
        self._experiment_id = experiment_id

    def on_mount(self) -> None:
        self.push_screen(TriageScreen(ledger_root=self._ledger_root, experiment_id=self._experiment_id))


def _populate_ledger(tmp_path: Path) -> Path:
    """Create a minimal ledger with 3 trial records for testing."""
    ledger_root = tmp_path / "ledger"
    exp_dir = ledger_root / "experiment-001"
    exp_dir.mkdir(parents=True)
    for trial_id, reward in [("t1", 0.0), ("t2", 0.5), ("t3", 1.0)]:
        record = make_trial_record(
            trial_id=trial_id,
            experiment_id="experiment-001",
            evaluation=EvaluationResult(reward=reward, validity=_VALID),
        )
        (exp_dir / f"{trial_id}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return ledger_root


@pytest.mark.anyio
async def test_triage_screen_has_datatable(tmp_path: Path) -> None:
    ledger_root = _populate_ledger(tmp_path)
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        table = app.screen.query_one("#triage-table", DataTable)
        assert table is not None
        assert table.cursor_type == "row"


@pytest.mark.anyio
async def test_triage_table_has_correct_columns(tmp_path: Path) -> None:
    ledger_root = _populate_ledger(tmp_path)
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        table = app.screen.query_one("#triage-table", DataTable)
        col_labels = [str(col.label) for col in table.columns.values()]
        assert "Ann" in col_labels
        assert "Model" in col_labels
        assert "Task" in col_labels
        assert "Reward" in col_labels
        assert "Turns" in col_labels
        assert "Errors" in col_labels


@pytest.mark.anyio
async def test_triage_table_has_correct_row_count(tmp_path: Path) -> None:
    ledger_root = _populate_ledger(tmp_path)
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        table = app.screen.query_one("#triage-table", DataTable)
        assert table.row_count == 3


@pytest.mark.anyio
async def test_triage_has_filter_display(tmp_path: Path) -> None:
    ledger_root = _populate_ledger(tmp_path)
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        from textual.widgets import Static

        bar = app.screen.query_one("#triage-filter-bar", Static)
        assert bar is not None


@pytest.mark.anyio
async def test_triage_has_details_panel(tmp_path: Path) -> None:
    ledger_root = _populate_ledger(tmp_path)
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        from textual.widgets import Static

        details = app.screen.query_one("#triage-details", Static)
        assert details is not None


@pytest.mark.anyio
async def test_triage_screen_renders_trial_list(tmp_path: Path) -> None:
    ledger_root = _populate_ledger(tmp_path)
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, TriageScreen)
        assert len(screen._filtered_records) == 3


@pytest.mark.anyio
async def test_triage_screen_cycles_reward_filter(tmp_path: Path) -> None:
    ledger_root = _populate_ledger(tmp_path)
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        assert len(screen._filtered_records) == 3

        await pilot.press("r")  # All -> Zero
        await pilot.pause()
        assert screen._filters.reward == "zero"
        assert len(screen._filtered_records) == 1

        await pilot.press("r")  # Zero -> Partial
        await pilot.pause()
        assert screen._filters.reward == "partial"
        assert len(screen._filtered_records) == 1

        await pilot.press("r")  # Partial -> Perfect
        await pilot.pause()
        assert screen._filters.reward == "perfect"
        assert len(screen._filtered_records) == 1

        await pilot.press("r")  # Perfect -> All
        await pilot.pause()
        assert screen._filters.reward == "all"
        assert len(screen._filtered_records) == 3


@pytest.mark.anyio
async def test_triage_screen_annotate_pass(tmp_path: Path) -> None:
    ledger_root = _populate_ledger(tmp_path)
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = app.screen

        await pilot.press("1")  # Annotate pass on first trial
        await pilot.pause()
        current_id = screen._current_trial_id()
        assert current_id in screen._annotations
        assert screen._annotations[current_id].verdict == "pass"

        # Verify file was written
        ann_dir = ledger_root / "experiment-001" / "_annotations"
        assert (ann_dir / f"{current_id}.json").exists()


@pytest.mark.anyio
async def test_triage_screen_empty_ledger(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir()
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        assert len(screen._filtered_records) == 0


@pytest.mark.anyio
async def test_triage_table_row_count_updates_on_filter(tmp_path: Path) -> None:
    ledger_root = _populate_ledger(tmp_path)
    app = TriageTestApp(ledger_root=ledger_root, experiment_id="experiment-001")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        table = app.screen.query_one("#triage-table", DataTable)
        assert table.row_count == 3

        await pilot.press("r")  # Filter to zero reward
        await pilot.pause()
        assert table.row_count == 1

        await pilot.press("f")  # Reset filters
        await pilot.pause()
        assert table.row_count == 3
