# ABOUTME: Leaderboard screen ranking models by mean reward from ledger trial records.
# ABOUTME: Two-panel layout with DataTable summary and drill-down detail panel.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label, Static

from aec_bench.tui.widgets.shared import reward_style

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelStats:
    """Aggregated statistics for a single model across all trials."""

    model: str
    trial_count: int
    mean_reward: float
    total_cost_usd: float


# ---------------------------------------------------------------------------
# Rendering helpers (pure functions)
# ---------------------------------------------------------------------------


def _compute_model_stats(records: list) -> list[ModelStats]:
    """Aggregate trial records by model, sorted by mean reward descending."""
    from collections import defaultdict

    groups: dict[str, list] = defaultdict(list)
    for record in records:
        groups[record.agent.model].append(record)

    stats: list[ModelStats] = []
    for model, model_records in groups.items():
        rewards = [r.evaluation.reward for r in model_records]
        mean_reward = sum(rewards) / len(rewards) if rewards else 0.0
        total_cost = sum(
            r.cost.estimated_cost_usd
            for r in model_records
            if r.cost is not None and r.cost.estimated_cost_usd is not None
        )
        stats.append(
            ModelStats(
                model=model,
                trial_count=len(model_records),
                mean_reward=mean_reward,
                total_cost_usd=total_cost,
            )
        )

    return sorted(stats, key=lambda s: s.mean_reward, reverse=True)


def _render_model_detail(rank: int, stats: ModelStats) -> str:
    """Format the detail pane content for a highlighted model row."""
    lines = [
        f"[bold]Rank #{rank} — {stats.model}[/bold]",
        "",
        f"  Trials:     {stats.trial_count}",
        f"  Mean Reward: {stats.mean_reward:.3f}",
        f"  Total Cost:  ${stats.total_cost_usd:.4f}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LeaderboardScreen — DataTable with detail panel
# ---------------------------------------------------------------------------


class LeaderboardScreen(Screen):
    """Model leaderboard ranked by mean reward with drill-down detail panel."""

    BINDINGS = [
        Binding("enter", "select_row", "Drill-through", show=True),
        Binding("escape", "go_back", "Back", show=True),
        Binding("b", "go_back", "Back", show=False),
    ]

    CSS = """
    .leaderboard-body {
        height: 1fr;
        margin: 0 1;
    }

    .leaderboard-table-panel {
        width: 2fr;
        border: round #40403E;
        padding: 1 2;
    }
    .leaderboard-table-panel:light {
        border: round #BFBFBA;
    }

    .leaderboard-detail-panel {
        width: 1fr;
        border: round #40403E;
        padding: 1 2;
        margin: 0 0 0 1;
    }
    .leaderboard-detail-panel:light {
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
        self._model_stats: list[ModelStats] = []

    def compose(self) -> ComposeResult:
        yield Static("Leaderboard", classes="panel-title")
        with Horizontal(classes="leaderboard-body"):
            with Container(classes="leaderboard-table-panel"):
                yield DataTable(
                    id="leaderboard-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )
            with Container(classes="leaderboard-detail-panel"):
                yield Label(
                    Text("Model Details", style="bold"),
                    classes="panel-title",
                )
                yield Static(
                    "[dim]Select a model to view details.[/dim]",
                    id="leaderboard-detail",
                    markup=True,
                )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#leaderboard-table", DataTable)
        table.loading = True
        table.add_column("Rank", key="rank")
        table.add_column("Model", key="model")
        table.add_column("Trials", key="trials")
        table.add_column("Mean Reward", key="mean_reward")
        table.add_column("Cost", key="cost")
        self._load_leaderboard()

    @work(thread=True, exclusive=True)
    def _load_leaderboard(self) -> None:
        """Load and aggregate trial records from ledger in a background thread."""
        from aec_bench.ledger.reader import read_trial_records

        if not self.ledger_root.exists():
            records = []
        else:
            records = read_trial_records(self.ledger_root, experiment_id=self.experiment_id)

        stats = _compute_model_stats(records)
        self.app.call_from_thread(self._on_leaderboard_loaded, stats)

    def _on_leaderboard_loaded(self, stats: list[ModelStats]) -> None:
        """Populate state and table on the main thread after data loads."""
        self._model_stats = stats
        table = self.query_one("#leaderboard-table", DataTable)
        table.loading = False

        if self._model_stats:
            self._populate_table()

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def _populate_table(self) -> None:
        """Add rows for each model ranked by mean reward."""
        table = self.query_one("#leaderboard-table", DataTable)
        table.clear()

        for rank, stats in enumerate(self._model_stats, start=1):
            color = reward_style(stats.mean_reward)
            reward_text = Text(f"★ {stats.mean_reward:.3f}", style=color)
            cost_text = Text(f"${stats.total_cost_usd:.4f}") if stats.total_cost_usd > 0 else Text("-")
            table.add_row(
                Text(str(rank)),
                Text(stats.model),
                Text(str(stats.trial_count)),
                reward_text,
                cost_text,
                key=stats.model,
            )

    # ------------------------------------------------------------------
    # Detail panel updates
    # ------------------------------------------------------------------

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update the detail pane when the cursor moves to a row."""
        detail = self.query_one("#leaderboard-detail", Static)

        row_idx = event.cursor_row
        if row_idx < 0 or row_idx >= len(self._model_stats):
            detail.update("[dim]Select a model to view details.[/dim]")
            return

        stats = self._model_stats[row_idx]
        detail.update(_render_model_detail(row_idx + 1, stats))

    # ------------------------------------------------------------------
    # Drill-through
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Drill through to Triage filtered by the selected model."""
        if event.row_key is None:
            return
        model = str(event.row_key.value)
        from aec_bench.tui.screens.triage import FilterState, TriageScreen

        self.app.switch_mode("review")
        self.app.push_screen(
            TriageScreen(
                ledger_root=self.ledger_root,
                experiment_id=self.experiment_id,
                pre_filters=FilterState(model=model),
            )
        )

    def action_select_row(self) -> None:
        """Trigger row selection on the leaderboard table."""
        table = self.query_one("#leaderboard-table", DataTable)
        table.action_select_cursor()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.switch_mode("dashboard")
