# ABOUTME: Triage screen for rapid trial scanning, filtering, and annotation.
# ABOUTME: Flat list view with inline pass/fail/defer verdicts persisted in ledger _annotations/.

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Collapsible, DataTable, Footer, Input, Static

from aec_bench.communication.metrics import split_task_id
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.trace_summary import extract_trial_trace_signals
from aec_bench.ledger.annotations import (
    TriageAnnotation,
    delete_annotation,
    load_annotations,
    save_annotation,
)
from aec_bench.ledger.reader import read_trial_records
from aec_bench.tui.widgets.shared import reward_color

# --- Filtering and sorting ---


@dataclass(frozen=True)
class FilterState:
    """Current filter settings for the triage list. Immutable — use replace() to change."""

    model: str = "all"
    reward: Literal["all", "zero", "partial", "perfect"] = "all"
    errors: Literal["all", "with_errors", "no_errors"] = "all"
    annotated: Literal["all", "annotated", "unannotated"] = "all"
    task_prefix: str = "all"
    adapter: str = "all"


def apply_filters(
    records: list[TrialRecord],
    filters: FilterState,
    *,
    annotations: dict[str, TriageAnnotation],
    error_counts: dict[str, int] | None = None,
) -> list[TrialRecord]:
    """Filter trial records based on current filter state."""
    result = list(records)

    if filters.model != "all":
        result = [r for r in result if r.agent.model == filters.model]

    if filters.reward == "zero":
        result = [r for r in result if r.evaluation.reward == 0.0]
    elif filters.reward == "partial":
        result = [r for r in result if 0.0 < r.evaluation.reward < 1.0]
    elif filters.reward == "perfect":
        result = [r for r in result if r.evaluation.reward >= 1.0]

    if filters.errors != "all" and error_counts is not None:
        if filters.errors == "with_errors":
            result = [r for r in result if error_counts.get(r.trial_id, 0) > 0]
        elif filters.errors == "no_errors":
            result = [r for r in result if error_counts.get(r.trial_id, 0) == 0]

    if filters.annotated == "annotated":
        result = [r for r in result if r.trial_id in annotations]
    elif filters.annotated == "unannotated":
        result = [r for r in result if r.trial_id not in annotations]

    if filters.task_prefix != "all":
        result = [r for r in result if split_task_id(r.task.task_id)[0] == filters.task_prefix]

    if filters.adapter != "all":
        result = [r for r in result if r.agent.adapter == filters.adapter]

    return result


def apply_sort(records: list[TrialRecord], sort_key: str = "reward_asc") -> list[TrialRecord]:
    """Sort trial records by the given key."""
    if sort_key == "reward_asc":
        return sorted(records, key=lambda r: r.evaluation.reward)
    elif sort_key == "reward_desc":
        return sorted(records, key=lambda r: r.evaluation.reward, reverse=True)
    elif sort_key == "model":
        return sorted(records, key=lambda r: r.agent.model)
    elif sort_key == "task":
        return sorted(records, key=lambda r: r.task.task_id)
    return list(records)  # "default" — ledger insertion order


# --- Cycle helpers for filter values ---

_REWARD_CYCLE: list[Literal["all", "zero", "partial", "perfect"]] = [
    "all",
    "zero",
    "partial",
    "perfect",
]
_ERRORS_CYCLE: list[Literal["all", "with_errors", "no_errors"]] = [
    "all",
    "with_errors",
    "no_errors",
]
_ANNOTATED_CYCLE: list[Literal["all", "annotated", "unannotated"]] = [
    "all",
    "annotated",
    "unannotated",
]
_SORT_CYCLE: list[str] = ["reward_asc", "reward_desc", "model", "task", "default"]


def _next_in_cycle(current: str, cycle: list[str]) -> str:
    """Return the next value in a cycle list, wrapping around to the start."""
    idx = cycle.index(current) if current in cycle else 0
    return cycle[(idx + 1) % len(cycle)]


# --- TUI screen ---


def _annotation_marker(annotation: TriageAnnotation | None) -> Text:
    """Build a Rich Text annotation marker for a DataTable cell."""
    if annotation is None:
        return Text(". ", style="dim")
    if annotation.verdict == "pass":
        marker = Text("v", style="green")
    elif annotation.verdict == "fail":
        marker = Text("x", style="red")
    elif annotation.verdict == "note":
        marker = Text(".", style="dim")
    else:
        marker = Text("?", style="yellow")
    note_flag = Text("*", style="#D4A27F") if annotation.notes else Text(" ")
    return marker + note_flag


def _reward_cell(reward: float) -> Text:
    """Build a Rich Text cell for a reward value with colour coding."""
    color = reward_color(reward)
    return Text(f"★ {reward:.3f}", style=color)


def _error_cell(count: int) -> Text:
    """Build a Rich Text cell for an error count."""
    label = str(count)
    if count > 0:
        return Text(label, style="red")
    return Text(label, style="dim")


class TriageScreen(Screen):
    """DataTable-based trial list with keyboard filtering and inline annotation."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "go_back", "Back"),
        Binding("enter", "open_viewer", "View"),
        Binding("1", "annotate_pass", "Pass"),
        Binding("2", "annotate_fail", "Fail"),
        Binding("3", "annotate_defer", "Defer"),
        Binding("n", "edit_note", "Note"),
        Binding("u", "undo", "Undo"),
        Binding("m", "cycle_model", "Model"),
        Binding("r", "cycle_reward", "Reward"),
        Binding("x", "cycle_errors", "Errors"),
        Binding("g", "cycle_annotated", "Ann"),
        Binding("s", "cycle_sort", "Sort"),
        Binding("f", "reset_filters", "Reset"),
    ]

    CSS = """
    .triage-filter-bar {
        height: 3;
        border: round #40403E;
        padding: 0 2;
        margin: 0 1 0 1;
    }

    .triage-filter-collapsible {
        margin: 0 1 0 1;
    }

    .triage-table-panel {
        height: 1fr;
        margin: 0 1 0 1;
    }

    #triage-table {
        height: 1fr;
    }

    .triage-details-panel {
        height: 6;
        border: round #40403E;
        padding: 0 2;
        margin: 0 1 0 1;
    }

    .triage-note-input {
        height: 3;
        margin: 0 1 0 1;
        display: none;
    }

    .triage-note-input.visible {
        display: block;
    }
    """

    def __init__(
        self,
        *,
        ledger_root: Path,
        experiment_id: str | None = None,
        pre_filters: FilterState | None = None,
    ) -> None:
        super().__init__()
        self.ledger_root = ledger_root
        self.experiment_id = experiment_id
        self._all_records: list[TrialRecord] = []
        self._filtered_records: list[TrialRecord] = []
        self._filters: FilterState = pre_filters or FilterState()
        self._sort_key: str = "reward_asc"
        self._annotations: dict[str, TriageAnnotation] = {}
        self._error_counts: dict[str, int] = {}
        self._last_action: tuple[str, TriageAnnotation | None] | None = None
        self._experiment_dir: Path | None = None
        self._model_cycle: list[str] = ["all"]
        # Maps trial_id -> TrialRecord for quick lookup from DataTable row keys
        self._record_index: dict[str, TrialRecord] = {}

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(id="triage-filter-bar", markup=True, classes="triage-filter-bar")
            with Collapsible(title="Filters", collapsed=True, classes="triage-filter-collapsible"):
                yield Static(id="triage-filter-detail", markup=True)
            with Container(classes="triage-table-panel"):
                table = DataTable(id="triage-table", cursor_type="row")
                table.loading = True
                yield table
            yield Input(
                placeholder="Type note and press Enter (Escape to cancel)",
                id="triage-note-input",
                classes="triage-note-input",
            )
            yield Static(id="triage-details", markup=True, classes="triage-details-panel")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#triage-table", DataTable)
        table.add_columns("Ann", "Model", "Task", "Reward", "Turns", "Errors")
        self._load_data()

    # ------------------------------------------------------------------
    # Async data loading
    # ------------------------------------------------------------------

    @work(thread=True, exclusive=True)
    def _load_data(self) -> None:
        """Load trial records and pre-compute error counts in a background thread."""
        records = read_trial_records(self.ledger_root, experiment_id=self.experiment_id)
        error_counts: dict[str, int] = {}
        for record in records:
            signals = extract_trial_trace_signals(record)
            error_counts[record.trial_id] = signals["tool_errors"]
        self.app.call_from_thread(self._on_data_loaded, records, error_counts)

    def _on_data_loaded(
        self,
        records: list[TrialRecord],
        error_counts: dict[str, int],
    ) -> None:
        """Populate state and table on the main thread after data loads."""
        self._all_records = records
        self._error_counts = error_counts
        self._record_index = {f"{r.experiment_id}/{r.trial_id}": r for r in records}

        if self._all_records:
            first_exp_id = self._all_records[0].experiment_id
            self._experiment_dir = self.ledger_root / first_exp_id
            self._annotations = load_annotations(self._experiment_dir)
            models = sorted({r.agent.model for r in self._all_records})
            self._model_cycle = ["all"] + models

        self._apply_filters_and_sort()
        self._render_filter_bar()
        self._render_filter_detail()
        self._populate_table()
        self._render_details()

    # ------------------------------------------------------------------
    # DataTable events
    # ------------------------------------------------------------------

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update the details panel when the DataTable cursor moves."""
        self._render_details()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open viewer when a row is selected (Enter key)."""
        self.action_open_viewer()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.switch_mode("dashboard")

    def action_open_viewer(self) -> None:
        """Open the TrialViewerScreen for the currently selected trial."""
        row_key = self._current_row_key()
        if row_key is None:
            return
        record = self._record_index.get(row_key)
        if record is None:
            return
        from aec_bench.tui.screens.viewer import TrialViewerScreen

        self.app.push_screen(TrialViewerScreen(record=record, siblings=self._filtered_records))

    # ------------------------------------------------------------------
    # Annotation
    # ------------------------------------------------------------------

    def _current_row_key(self) -> str | None:
        """Return the composite row key (experiment_id/trial_id) of the highlighted row."""
        table = self.query_one("#triage-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            return str(row_key.value) if row_key else None
        except Exception:
            return None

    def _current_trial_id(self) -> str | None:
        """Return just the trial_id of the currently highlighted row."""
        key = self._current_row_key()
        if key is None:
            return None
        # Key format: "experiment_id/trial_id"
        return key.split("/", 1)[1] if "/" in key else key

    def _annotate(self, verdict: Literal["pass", "fail", "defer", "note"]) -> None:
        """Apply an annotation to the current trial and persist it, preserving existing notes."""
        trial_id = self._current_trial_id()
        if trial_id is None or self._experiment_dir is None:
            return
        previous = self._annotations.get(trial_id)
        self._last_action = (trial_id, previous)
        existing_notes = previous.notes if previous else ""
        annotation = TriageAnnotation.create(verdict=verdict, notes=existing_notes)
        self._annotations[trial_id] = annotation
        save_annotation(self._experiment_dir, trial_id, annotation)
        self._update_row_annotation(trial_id, self._current_row_key())
        self._render_details()

    def _update_row_annotation(self, trial_id: str, row_key: str | None = None) -> None:
        """Update the annotation cell for a single row without full table rebuild."""
        table = self.query_one("#triage-table", DataTable)
        annotation = self._annotations.get(trial_id)
        marker = _annotation_marker(annotation)
        if row_key is None:
            self._populate_table()
            return
        try:
            ann_col_key = list(table.columns.keys())[0]
            table.update_cell(row_key, ann_col_key, marker)
        except Exception:
            self._populate_table()

    def action_annotate_pass(self) -> None:
        self._annotate("pass")

    def action_annotate_fail(self) -> None:
        self._annotate("fail")

    def action_annotate_defer(self) -> None:
        self._annotate("defer")

    def action_edit_note(self) -> None:
        """Show the note input for the current trial."""
        trial_id = self._current_trial_id()
        if trial_id is None:
            return
        note_input = self.query_one("#triage-note-input", Input)
        existing = self._annotations.get(trial_id)
        note_input.value = existing.notes if existing else ""
        note_input.add_class("visible")
        note_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Save the note when Enter is pressed in the input."""
        trial_id = self._current_trial_id()
        if trial_id is None or self._experiment_dir is None:
            return
        note_text = event.value.strip()
        existing = self._annotations.get(trial_id)
        if existing:
            # Update existing annotation with new note, keep verdict
            updated = TriageAnnotation(
                verdict=existing.verdict,
                notes=note_text,
                timestamp=existing.timestamp,
            )
        else:
            # Note-only: no verdict yet
            updated = TriageAnnotation.create(verdict="note", notes=note_text)
        self._annotations[trial_id] = updated
        save_annotation(self._experiment_dir, trial_id, updated)
        # Hide input and return focus to table
        note_input = self.query_one("#triage-note-input", Input)
        note_input.remove_class("visible")
        note_input.value = ""
        self._update_row_annotation(trial_id, self._current_row_key())
        self._render_details()

    def on_key(self, event: object) -> None:
        """Handle Escape to cancel note input."""
        key = getattr(event, "key", "")
        if key == "escape":
            note_input = self.query_one("#triage-note-input", Input)
            if note_input.has_class("visible"):
                note_input.remove_class("visible")
                note_input.value = ""
                event.prevent_default()  # type: ignore[union-attr]
                event.stop()  # type: ignore[union-attr]

    def action_undo(self) -> None:
        """Undo the last annotation action."""
        if self._last_action is None or self._experiment_dir is None:
            return
        trial_id, previous = self._last_action
        self._last_action = None
        if previous is None:
            self._annotations.pop(trial_id, None)
            delete_annotation(self._experiment_dir, trial_id)
        else:
            self._annotations[trial_id] = previous
            save_annotation(self._experiment_dir, trial_id, previous)
        self._update_row_annotation(trial_id)  # falls back to full repopulate
        self._render_details()

    # ------------------------------------------------------------------
    # Filter cycling
    # ------------------------------------------------------------------

    def action_cycle_reward(self) -> None:
        next_val = _next_in_cycle(self._filters.reward, _REWARD_CYCLE)
        self._filters = replace(self._filters, reward=next_val)
        self._apply_filters_and_sort()
        self._render_all()

    def action_cycle_errors(self) -> None:
        next_val = _next_in_cycle(self._filters.errors, _ERRORS_CYCLE)
        self._filters = replace(self._filters, errors=next_val)
        self._apply_filters_and_sort()
        self._render_all()

    def action_cycle_annotated(self) -> None:
        next_val = _next_in_cycle(self._filters.annotated, _ANNOTATED_CYCLE)
        self._filters = replace(self._filters, annotated=next_val)
        self._apply_filters_and_sort()
        self._render_all()

    def action_cycle_model(self) -> None:
        next_val = _next_in_cycle(self._filters.model, self._model_cycle)
        self._filters = replace(self._filters, model=next_val)
        self._apply_filters_and_sort()
        self._render_all()

    def action_cycle_sort(self) -> None:
        self._sort_key = _next_in_cycle(self._sort_key, _SORT_CYCLE)
        self._apply_filters_and_sort()
        self._render_all()

    def action_reset_filters(self) -> None:
        self._filters = FilterState()
        self._sort_key = "reward_asc"
        self._apply_filters_and_sort()
        self._render_all()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_filters_and_sort(self) -> None:
        """Recompute _filtered_records from _all_records using current filters and sort."""
        filtered = apply_filters(
            self._all_records,
            self._filters,
            annotations=self._annotations,
            error_counts=self._error_counts if self._error_counts else None,
        )
        self._filtered_records = apply_sort(filtered, sort_key=self._sort_key)

    def _render_all(self) -> None:
        """Re-render filter bar, filter detail, table, and details pane."""
        self._render_filter_bar()
        self._render_filter_detail()
        self._populate_table()
        self._render_details()

    def _render_filter_bar(self) -> None:
        """Update the filter bar Static with current settings and trial count."""
        bar = self.query_one("#triage-filter-bar", Static)
        total = len(self._all_records)
        shown = len(self._filtered_records)
        parts = [
            f"[bold]Triage[/bold]  {shown}/{total} trials",
            f"  [dim]model:[/dim] {self._filters.model}",
            f"  [dim]reward:[/dim] {self._filters.reward}",
            f"  [dim]errors:[/dim] {self._filters.errors}",
            f"  [dim]ann:[/dim] {self._filters.annotated}",
            f"  [dim]sort:[/dim] {self._sort_key}",
            "  [dim]m:model r:reward x:errors s:sort f:reset[/dim]",
        ]
        bar.update("  ".join(parts))

    def _render_filter_detail(self) -> None:
        """Update the collapsible filter detail with readable filter state."""
        try:
            detail = self.query_one("#triage-filter-detail", Static)
        except Exception:
            return
        lines = [
            f"  [dim]m[/dim] Model: {self._filters.model}",
            f"  [dim]r[/dim] Reward: {self._filters.reward}",
            f"  [dim]x[/dim] Errors: {self._filters.errors}",
            f"  [dim]g[/dim] Annotated: {self._filters.annotated}",
            f"  [dim]s[/dim] Sort: {self._sort_key}",
            "  [dim]f[/dim] Reset all filters",
        ]
        detail.update("\n".join(lines))

    def _populate_table(self) -> None:
        """Clear and repopulate the DataTable with current filtered records."""
        table = self.query_one("#triage-table", DataTable)
        table.clear()

        if not self._all_records:
            table.loading = False
            return

        for record in self._filtered_records:
            trial_id = record.trial_id
            annotation = self._annotations.get(trial_id)

            ann_cell = _annotation_marker(annotation)
            model_cell = record.agent.model[:20]
            task_cell = record.task.task_id[:28]
            reward_cell_val = _reward_cell(record.evaluation.reward)

            # Turns info
            agent_result = record.outputs.agent_result or {}
            turns_used = agent_result.get("turns_used", "?")
            max_turns = agent_result.get("max_turns", "?")
            turns_cell = f"{turns_used}/{max_turns}"

            # Error count
            err_count = self._error_counts.get(trial_id, 0)
            err_cell = _error_cell(err_count)

            row_key = f"{record.experiment_id}/{trial_id}"
            table.add_row(
                ann_cell,
                model_cell,
                task_cell,
                reward_cell_val,
                turns_cell,
                err_cell,
                key=row_key,
            )

        table.loading = False

    def _render_details(self) -> None:
        """Update the details pane for the currently highlighted trial."""
        details = self.query_one("#triage-details", Static)
        row_key = self._current_row_key()
        trial_id = self._current_trial_id()
        if row_key is None or trial_id is None:
            details.update("")
            return

        record = self._record_index.get(row_key)
        if record is None:
            details.update("")
            return

        annotation = self._annotations.get(trial_id)
        r_color = reward_color(record.evaluation.reward)

        ann_str = (
            f"[bold]{annotation.verdict}[/bold] ({annotation.timestamp})" if annotation else "[dim]unannotated[/dim]"
        )

        note_str = f"  note: {annotation.notes}" if annotation and annotation.notes else ""

        parts = [
            f"[bold]{trial_id}[/bold]  [{r_color}]{record.evaluation.reward:.3f}[/]",
            f"  model: {record.agent.model}  task: {record.task.task_id}",
            f"  annotation: {ann_str}{note_str}",
            "  [dim]1=pass  2=fail  3=defer  n=note  u=undo  enter=view[/dim]",
        ]
        details.update("\n".join(parts))
