# ABOUTME: Data structures, builders, and CompareScreen for the model comparison matrix.
# ABOUTME: Groups trial records into model x task_type grids plus the TUI screen.

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
class ComparisonCell:
    """Aggregate metrics for one (model, task_type) pair."""

    model: str
    task_type: str
    n_trials: int
    mean_reward: float
    total_cost: float

    @property
    def reward_per_dollar(self) -> float:
        if self.total_cost == 0.0:
            return 0.0
        return self.mean_reward / self.total_cost


@dataclass(frozen=True)
class ComparisonMatrix:
    """Model x task_type grid of ComparisonCells."""

    models: list[str]
    task_types: list[str]
    cells: dict[tuple[str, str], ComparisonCell]
    model_totals: dict[str, ComparisonCell] = field(default_factory=dict)


def build_comparison_matrix(records: Sequence[TrialRecord]) -> ComparisonMatrix:
    """Group trial records into a model x task_type comparison grid."""
    grouped: dict[tuple[str, str], list[TrialRecord]] = defaultdict(list)
    for record in records:
        model = record.agent.model
        task_type, _ = split_task_id(record.task.task_id)
        grouped[(model, task_type)].append(record)

    cells: dict[tuple[str, str], ComparisonCell] = {}
    for (model, task_type), group in grouped.items():
        rewards = [r.evaluation.reward for r in group]
        costs = [r.cost.estimated_cost_usd or 0.0 for r in group if r.cost is not None]
        cells[(model, task_type)] = ComparisonCell(
            model=model,
            task_type=task_type,
            n_trials=len(group),
            mean_reward=sum(rewards) / len(rewards),
            total_cost=sum(costs),
        )

    models = sorted({m for m, _ in cells})
    task_types = sorted({t for _, t in cells})

    model_totals: dict[str, ComparisonCell] = {}
    for model in models:
        model_cells = [c for (m, _), c in cells.items() if m == model]
        total_trials = sum(c.n_trials for c in model_cells)
        total_reward = sum(c.mean_reward * c.n_trials for c in model_cells)
        total_cost = sum(c.total_cost for c in model_cells)
        model_totals[model] = ComparisonCell(
            model=model,
            task_type="__overall__",
            n_trials=total_trials,
            mean_reward=total_reward / total_trials if total_trials else 0.0,
            total_cost=total_cost,
        )

    return ComparisonMatrix(
        models=models,
        task_types=task_types,
        cells=cells,
        model_totals=model_totals,
    )


def find_paired_trials(
    records: Sequence[TrialRecord],
) -> dict[str, dict[str, TrialRecord]]:
    """Group trials by task_id, returning {task_id: {model: record}}.

    When multiple trials exist for the same (task_id, model) pair,
    the first record encountered is kept.
    """
    result: dict[str, dict[str, TrialRecord]] = defaultdict(dict)
    for record in records:
        task_id = record.task.task_id
        model = record.agent.model
        if model not in result[task_id]:
            result[task_id][model] = record
    return dict(result)


# ---------------------------------------------------------------------------
# Rendering helpers (pure functions)
# ---------------------------------------------------------------------------


def _render_compare_details(
    model: str,
    task_type: str,
    cell: ComparisonCell,
) -> str:
    """Format the details pane content for a selected comparison cell."""
    n = cell.n_trials

    lines = [
        f"[bold]Model:[/bold]      {model}",
        f"[bold]Task type:[/bold]  {task_type}",
        "",
        f"  Trials:        {n}",
        f"  Mean reward:   [{reward_style(cell.mean_reward)}]{cell.mean_reward:.3f}[/]",
        f"  Total cost:    ${cell.total_cost:.2f}",
        f"  Reward/$:      {cell.reward_per_dollar:.3f}",
        "",
        "[dim]Enter: view trials in Triage[/dim]",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CompareScreen — standalone model x task_type matrix with detail panel
# ---------------------------------------------------------------------------


class CompareScreen(Screen):
    """Model x task_type comparison matrix with colour-coded cells and drill-through to Triage."""

    BINDINGS = [
        Binding("enter", "drill_through", "Triage", show=True),
        Binding("escape", "go_back", "Back", show=True),
        Binding("b", "go_back", "Back", show=False),
    ]

    CSS = """
    .compare-body {
        height: 1fr;
        margin: 0 1;
    }

    .compare-table-panel {
        width: 2fr;
        border: round #40403E;
        padding: 1 2;
    }
    .compare-table-panel:light {
        border: round #BFBFBA;
    }

    .compare-details-panel {
        width: 1fr;
        border: round #40403E;
        padding: 1 2;
        margin: 0 0 0 1;
    }
    .compare-details-panel:light {
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
        self._matrix: ComparisonMatrix | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            "Compare — Model × Task Type  [dim]enter:drill b:back[/dim]",
            classes="panel-title",
            markup=True,
        )
        with Horizontal(classes="compare-body"):
            with Container(classes="compare-table-panel"):
                yield DataTable(
                    id="compare-table",
                    cursor_type="row",
                    fixed_columns=1,
                )
            with Container(classes="compare-details-panel"):
                yield Label(
                    Text("Row Details", style="bold"),
                    classes="panel-title",
                )
                yield Static(
                    "[dim]Select a row to view details.[/dim]",
                    id="compare-detail",
                    markup=True,
                )
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    @work(thread=True, exclusive=True)
    def _load_data(self) -> None:
        """Load trial records and build the comparison matrix in a background thread."""
        from aec_bench.ledger.reader import read_trial_records

        records = read_trial_records(self.ledger_root, experiment_id=self.experiment_id)
        matrix = build_comparison_matrix(records)
        self.app.call_from_thread(self._on_data_loaded, records, matrix)

    def _on_data_loaded(
        self,
        records: list[TrialRecord],
        matrix: ComparisonMatrix,
    ) -> None:
        """Populate state and table on the main thread after data loads."""
        self._records = records
        self._matrix = matrix
        if self._records:
            self._populate_table(matrix)

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def _populate_table(self, matrix: ComparisonMatrix) -> None:
        """Build columns and rows for the model x task_type comparison grid."""
        table = self.query_one("#compare-table", DataTable)
        table.clear(columns=True)

        table.add_column("Task Type", key="task_type")
        for model in matrix.models:
            table.add_column(model, key=f"model_{model}")
        table.add_column("Overall", key="overall")

        for task_type in matrix.task_types:
            row: list[str | Text] = [Text(task_type)]
            for model in matrix.models:
                cell = matrix.cells.get((model, task_type))
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
            # Overall column: mean across all models for this task_type
            task_cells = [c for (m, t), c in matrix.cells.items() if t == task_type]
            if task_cells:
                total_trials = sum(c.n_trials for c in task_cells)
                overall_mean = (
                    sum(c.mean_reward * c.n_trials for c in task_cells) / total_trials if total_trials else 0.0
                )
                style = reward_style(overall_mean)
                row.append(
                    Text.assemble(
                        (f"★ {overall_mean:.3f}", style),
                        (f" ({total_trials})", "dim"),
                    )
                )
            else:
                row.append(Text("-", style="dim"))
            table.add_row(*row)

        # Overall row: model totals
        overall_row: list[str | Text] = [Text("Overall", style="bold")]
        for model in matrix.models:
            total = matrix.model_totals.get(model)
            if total is None:
                overall_row.append(Text("-", style="dim"))
            else:
                style = reward_style(total.mean_reward)
                overall_row.append(
                    Text.assemble(
                        (f"★ {total.mean_reward:.3f}", style),
                        (f" ({total.n_trials})", "dim"),
                    )
                )
        all_rewards = [r.evaluation.reward for r in self._records]
        grand_mean = sum(all_rewards) / len(all_rewards) if all_rewards else 0.0
        grand_style = reward_style(grand_mean)
        overall_row.append(
            Text.assemble(
                (f"★ {grand_mean:.3f}", grand_style),
                (f" ({len(all_rewards)})", "dim"),
            )
        )
        table.add_row(*overall_row)

    # ------------------------------------------------------------------
    # Detail panel updates
    # ------------------------------------------------------------------

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update the detail pane when the cursor moves to a row."""
        if self._matrix is None:
            return

        matrix = self._matrix
        row_idx = event.cursor_row
        details = self.query_one("#compare-detail", Static)
        num_task_types = len(matrix.task_types)

        # Overall row (last row)
        if row_idx == num_task_types:
            all_rewards = [r.evaluation.reward for r in self._records]
            grand_mean = sum(all_rewards) / len(all_rewards) if all_rewards else 0.0
            grand_total = sum(c.total_cost for c in matrix.model_totals.values())
            grand_cell = ComparisonCell(
                model="All models",
                task_type="All task types",
                n_trials=len(all_rewards),
                mean_reward=grand_mean,
                total_cost=grand_total,
            )
            details.update(_render_compare_details("All models", "All task types", grand_cell))
            return

        # Task type row
        if row_idx < num_task_types:
            task_type = matrix.task_types[row_idx]
            task_cells = [c for (m, t), c in matrix.cells.items() if t == task_type]
            if task_cells:
                total_trials = sum(c.n_trials for c in task_cells)
                overall_mean = (
                    sum(c.mean_reward * c.n_trials for c in task_cells) / total_trials if total_trials else 0.0
                )
                total_cost = sum(c.total_cost for c in task_cells)
                summary_cell = ComparisonCell(
                    model="All models",
                    task_type=task_type,
                    n_trials=total_trials,
                    mean_reward=overall_mean,
                    total_cost=total_cost,
                )
                details.update(_render_compare_details("All models", task_type, summary_cell))
                return

        details.update("[dim]Select a row to view details.[/dim]")

    # ------------------------------------------------------------------
    # Drill-through
    # ------------------------------------------------------------------

    def _get_selected_filter(self) -> tuple[str, str] | None:
        """Return (model, task_type) for the currently highlighted row."""
        if self._matrix is None:
            return None
        try:
            table = self.query_one("#compare-table", DataTable)
        except Exception:
            return None
        row_idx = table.cursor_coordinate.row
        matrix = self._matrix

        model = "all"
        task_type = "all"

        if row_idx < len(matrix.task_types):
            task_type = matrix.task_types[row_idx]

        return (model, task_type)

    def action_drill_through(self) -> None:
        """Push Triage filtered to the current task type selection."""
        from aec_bench.tui.screens.triage import FilterState, TriageScreen

        selection = self._get_selected_filter()
        if selection is None:
            return
        _, task_type = selection
        pre_filters = FilterState(task_prefix=task_type)

        self.app.push_screen(
            TriageScreen(
                ledger_root=self.ledger_root,
                experiment_id=self.experiment_id,
                pre_filters=pre_filters,
            )
        )

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.switch_mode("dashboard")
