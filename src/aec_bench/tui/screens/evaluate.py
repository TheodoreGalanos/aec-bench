# ABOUTME: Evaluate screen with adapter x task heatmap DataTable and detail panel.
# ABOUTME: Pure data structures, matrix builders, and the EvaluateScreen Textual widget.

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label, Static

from aec_bench.communication.metrics import split_task_id
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.tui.widgets.shared import reward_style

# ---------------------------------------------------------------------------
# Data structures and builders
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluateCell:
    """Aggregate metrics for one (adapter, task_prefix) pair."""

    adapter: str
    task_prefix: str
    n_trials: int
    mean_reward: float
    perfect_count: int
    zero_count: int
    total_cost: float


@dataclass(frozen=True)
class EvaluateMatrix:
    """Adapter x task_prefix grid of EvaluateCells."""

    adapters: list[str]
    task_prefixes: list[str]
    cells: dict[tuple[str, str], EvaluateCell]
    adapter_totals: dict[str, EvaluateCell] = field(default_factory=dict)
    prefix_totals: dict[str, EvaluateCell] = field(default_factory=dict)


def build_evaluate_matrix(records: Sequence[TrialRecord]) -> EvaluateMatrix:
    """Group trial records into an adapter x task_prefix evaluation grid."""
    grouped: dict[tuple[str, str], list[TrialRecord]] = defaultdict(list)
    for record in records:
        adapter = record.agent.adapter
        task_prefix, _ = split_task_id(record.task.task_id)
        grouped[(adapter, task_prefix)].append(record)

    cells: dict[tuple[str, str], EvaluateCell] = {}
    for (adapter, task_prefix), group in grouped.items():
        rewards = [r.evaluation.reward for r in group]
        costs = [r.cost.estimated_cost_usd or 0.0 for r in group if r.cost is not None]
        cells[(adapter, task_prefix)] = EvaluateCell(
            adapter=adapter,
            task_prefix=task_prefix,
            n_trials=len(group),
            mean_reward=sum(rewards) / len(rewards),
            perfect_count=sum(1 for r in rewards if r >= 1.0),
            zero_count=sum(1 for r in rewards if r == 0.0),
            total_cost=sum(costs),
        )

    adapters = sorted({a for a, _ in cells})
    task_prefixes = sorted({t for _, t in cells})

    adapter_totals: dict[str, EvaluateCell] = {}
    for adapter in adapters:
        adapter_cells = [c for (a, _), c in cells.items() if a == adapter]
        total_trials = sum(c.n_trials for c in adapter_cells)
        total_reward = sum(c.mean_reward * c.n_trials for c in adapter_cells)
        total_perfect = sum(c.perfect_count for c in adapter_cells)
        total_zero = sum(c.zero_count for c in adapter_cells)
        total_cost = sum(c.total_cost for c in adapter_cells)
        adapter_totals[adapter] = EvaluateCell(
            adapter=adapter,
            task_prefix="__overall__",
            n_trials=total_trials,
            mean_reward=total_reward / total_trials if total_trials else 0.0,
            perfect_count=total_perfect,
            zero_count=total_zero,
            total_cost=total_cost,
        )

    prefix_totals: dict[str, EvaluateCell] = {}
    for task_prefix in task_prefixes:
        prefix_cells = [c for (_, t), c in cells.items() if t == task_prefix]
        total_trials = sum(c.n_trials for c in prefix_cells)
        total_reward = sum(c.mean_reward * c.n_trials for c in prefix_cells)
        total_perfect = sum(c.perfect_count for c in prefix_cells)
        total_zero = sum(c.zero_count for c in prefix_cells)
        total_cost = sum(c.total_cost for c in prefix_cells)
        prefix_totals[task_prefix] = EvaluateCell(
            adapter=task_prefix,
            task_prefix="__overall__",
            n_trials=total_trials,
            mean_reward=total_reward / total_trials if total_trials else 0.0,
            perfect_count=total_perfect,
            zero_count=total_zero,
            total_cost=total_cost,
        )

    return EvaluateMatrix(
        adapters=adapters,
        task_prefixes=task_prefixes,
        cells=cells,
        adapter_totals=adapter_totals,
        prefix_totals=prefix_totals,
    )


# ---------------------------------------------------------------------------
# Rendering helpers (pure functions)
# ---------------------------------------------------------------------------


def _render_eval_details(
    adapter: str,
    task_prefix: str,
    cell: EvaluateCell,
) -> str:
    """Format the details pane content for a selected evaluate cell."""
    n = cell.n_trials
    perfect_rate = cell.perfect_count / n if n else 0.0
    zero_rate = cell.zero_count / n if n else 0.0

    lines = [
        f"[bold]Adapter:[/bold]      {adapter}",
        f"[bold]Task prefix:[/bold]  {task_prefix}",
        "",
        f"  Trials:        {n}",
        f"  Mean reward:   [{reward_style(cell.mean_reward)}]{cell.mean_reward:.3f}[/]",
        f"  Perfect (1.0): {cell.perfect_count} ({perfect_rate:.0%})",
        f"  Zero (0.0):    {cell.zero_count} ({zero_rate:.0%})",
        f"  Total cost:    ${cell.total_cost:.2f}",
        "",
        "[dim]Enter: view trials in Triage[/dim]",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# EvaluateScreen — standalone heatmap with detail panel
# ---------------------------------------------------------------------------


class EvaluateScreen(Screen):
    """Adapter x task_prefix heatmap with colour-coded cells and drill-through to Triage."""

    BINDINGS = [
        Binding("enter", "drill_through", "Triage", show=True),
        Binding("c", "push_compare", "Compare", show=True),
        Binding("escape", "go_back", "Back", show=True),
        Binding("b", "go_back", "Back", show=False),
    ]

    CSS = """
    .evaluate-body {
        height: 1fr;
        margin: 0 1;
    }

    .evaluate-table-panel {
        width: 2fr;
        border: round #40403E;
        padding: 1 2;
    }
    .evaluate-table-panel:light {
        border: round #BFBFBA;
    }

    .evaluate-details-panel {
        width: 1fr;
        border: round #40403E;
        padding: 1 2;
        margin: 0 0 0 1;
    }
    .evaluate-details-panel:light {
        border: round #BFBFBA;
    }

    .panel-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        ledger_root: Path,
        experiment_id: str | None = None,
    ) -> None:
        super().__init__()
        self.ledger_root = ledger_root
        self.experiment_id = experiment_id
        self._records: list[TrialRecord] = []
        self._matrix: EvaluateMatrix | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            "Evaluate — Adapter × Task Heatmap  [dim]enter:drill c:compare[/dim]",
            classes="panel-title",
            markup=True,
        )
        with Horizontal(classes="evaluate-body"):
            with Container(classes="evaluate-table-panel"):
                yield DataTable(
                    id="evaluate-table",
                    cursor_type="cell",
                    fixed_columns=1,
                )
            with Container(classes="evaluate-details-panel"):
                yield Label(
                    Text("Cell Details", style="bold"),
                    classes="panel-title",
                )
                yield Static(
                    "[dim]Select a cell to view details.[/dim]",
                    id="evaluate-detail",
                    markup=True,
                )
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    @work(thread=True, exclusive=True)
    def _load_data(self) -> None:
        """Load trial records and build the evaluate matrix in a background thread."""
        from aec_bench.ledger.reader import read_trial_records

        records = read_trial_records(self.ledger_root, experiment_id=self.experiment_id)
        matrix = build_evaluate_matrix(records)
        self.app.call_from_thread(self._on_data_loaded, records, matrix)

    def _on_data_loaded(
        self,
        records: list[TrialRecord],
        matrix: EvaluateMatrix,
    ) -> None:
        """Populate state and table on the main thread after data loads."""
        self._records = records
        self._matrix = matrix
        if self._records:
            self._populate_table(matrix)

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def _populate_table(self, matrix: EvaluateMatrix) -> None:
        """Build columns and rows for the adapter x task heatmap."""
        table = self.query_one("#evaluate-table", DataTable)
        table.clear(columns=True)

        table.add_column("Adapter", key="adapter")
        for task_prefix in matrix.task_prefixes:
            table.add_column(task_prefix, key=f"prefix_{task_prefix}")
        table.add_column("Total", key="total")

        for adapter in matrix.adapters:
            row: list[str | Text] = [Text(adapter)]
            for task_prefix in matrix.task_prefixes:
                cell = matrix.cells.get((adapter, task_prefix))
                if cell is None:
                    row.append(Text("-", style="dim"))
                else:
                    style = reward_style(cell.mean_reward)
                    row.append(
                        Text.assemble(
                            (f"★ {cell.mean_reward:.3f}", style),
                            (f" ({cell.n_trials})", "dim"),
                        )
                    )
            total = matrix.adapter_totals.get(adapter)
            if total is None:
                row.append(Text("-", style="dim"))
            else:
                style = reward_style(total.mean_reward)
                row.append(
                    Text.assemble(
                        (f"★ {total.mean_reward:.3f}", style),
                        (f" ({total.n_trials})", "dim"),
                    )
                )
            table.add_row(*row)

        # Totals row
        totals_row: list[str | Text] = [Text("Total", style="bold")]
        for task_prefix in matrix.task_prefixes:
            total = matrix.prefix_totals.get(task_prefix)
            if total is None:
                totals_row.append(Text("-", style="dim"))
            else:
                style = reward_style(total.mean_reward)
                totals_row.append(
                    Text.assemble(
                        (f"★ {total.mean_reward:.3f}", style),
                        (f" ({total.n_trials})", "dim"),
                    )
                )
        all_rewards = [r.evaluation.reward for r in self._records]
        grand_mean = sum(all_rewards) / len(all_rewards) if all_rewards else 0.0
        grand_style = reward_style(grand_mean)
        totals_row.append(
            Text.assemble(
                (f"★ {grand_mean:.3f}", grand_style),
                (f" ({len(all_rewards)})", "dim"),
            )
        )
        table.add_row(*totals_row)

    # ------------------------------------------------------------------
    # Detail panel updates
    # ------------------------------------------------------------------

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        """Update the detail pane when the cursor moves over a cell."""
        if self._matrix is None:
            return

        matrix = self._matrix
        row_idx = event.coordinate.row
        col_idx = event.coordinate.column
        details = self.query_one("#evaluate-detail", Static)
        num_adapters = len(matrix.adapters)
        num_prefixes = len(matrix.task_prefixes)

        # Adapter column (col 0)
        if col_idx == 0:
            if row_idx < num_adapters:
                adapter = matrix.adapters[row_idx]
                cell = matrix.adapter_totals.get(adapter)
                if cell:
                    details.update(_render_eval_details(adapter, "All tasks", cell))
                    return
            details.update("[dim]Select a cell to view details.[/dim]")
            return

        # Totals row (last row)
        if row_idx == num_adapters:
            if 1 <= col_idx <= num_prefixes:
                task_prefix = matrix.task_prefixes[col_idx - 1]
                cell = matrix.prefix_totals.get(task_prefix)
                if cell:
                    details.update(_render_eval_details("All adapters", task_prefix, cell))
                    return
            details.update("[dim]Select a cell to view details.[/dim]")
            return

        # Data cell (adapter x task_prefix)
        if row_idx < num_adapters and 1 <= col_idx <= num_prefixes:
            adapter = matrix.adapters[row_idx]
            task_prefix = matrix.task_prefixes[col_idx - 1]
            cell = matrix.cells.get((adapter, task_prefix))
            if cell:
                details.update(_render_eval_details(adapter, task_prefix, cell))
                return

        # Total column for a specific adapter
        if row_idx < num_adapters and col_idx == num_prefixes + 1:
            adapter = matrix.adapters[row_idx]
            cell = matrix.adapter_totals.get(adapter)
            if cell:
                details.update(_render_eval_details(adapter, "All tasks", cell))
                return

        details.update("[dim]Select a cell to view details.[/dim]")

    # ------------------------------------------------------------------
    # Drill-through
    # ------------------------------------------------------------------

    def _get_selected_filter(self) -> tuple[str, str] | None:
        """Return (adapter, task_prefix) for the currently highlighted cell."""
        if self._matrix is None:
            return None
        try:
            table = self.query_one("#evaluate-table", DataTable)
        except Exception:
            return None
        row_idx = table.cursor_coordinate.row
        col_idx = table.cursor_coordinate.column
        matrix = self._matrix

        adapter = "all"
        task_prefix = "all"

        if row_idx < len(matrix.adapters):
            adapter = matrix.adapters[row_idx]
        if 1 <= col_idx <= len(matrix.task_prefixes):
            task_prefix = matrix.task_prefixes[col_idx - 1]

        return (adapter, task_prefix)

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Drill through when a cell is clicked or Enter is pressed."""
        self.action_drill_through()

    def action_drill_through(self) -> None:
        """Push Triage filtered to the current selection."""
        from aec_bench.tui.screens.triage import FilterState, TriageScreen

        selection = self._get_selected_filter()
        if selection is None:
            return
        adapter, task_prefix = selection
        pre_filters = FilterState(adapter=adapter, task_prefix=task_prefix)

        self.app.push_screen(
            TriageScreen(
                ledger_root=self.ledger_root,
                experiment_id=self.experiment_id,
                pre_filters=pre_filters,
            )
        )

    def action_push_compare(self) -> None:
        """Push CompareScreen for side-by-side model comparison."""
        from aec_bench.tui.screens.compare import CompareScreen

        self.app.push_screen(
            CompareScreen(
                ledger_root=self.ledger_root,
                experiment_id=self.experiment_id,
            )
        )

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.switch_mode("dashboard")
