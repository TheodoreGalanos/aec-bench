# ABOUTME: Datasets screen for browsing semantic dataset manifests by stable ID.
# ABOUTME: Shows task selection and description without routine version or hash fields.

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label, Sparkline, Static

from aec_bench.contracts.dataset import DatasetManifest

# ---------------------------------------------------------------------------
# Rendering helpers (pure functions)
# ---------------------------------------------------------------------------


def _render_dataset_detail(manifest: DatasetManifest) -> str:
    """Format the detail pane content for a highlighted dataset row."""
    lines = [
        f"[bold]{manifest.dataset_id}[/bold]",
        "",
        f"  Tasks: {len(manifest.tasks)}",
        "",
        f"  [dim]{manifest.description}[/dim]",
    ]
    return "\n".join(lines)


def _difficulty_sparkline_data(manifest: DatasetManifest) -> list[float]:
    """Return task-kind counts in a stable order for the compact sparkline."""

    counts: dict[str, int] = {}
    for task in manifest.tasks:
        counts[task.task_kind] = counts.get(task.task_kind, 0) + 1
    return [float(counts[key]) for key in sorted(counts)]


# ---------------------------------------------------------------------------
# DatasetsScreen — DataTable with detail panel
# ---------------------------------------------------------------------------


class DatasetsScreen(Screen[None]):
    """Benchmark dataset browser with DataTable and drill-down detail."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("b", "go_back", "Back", show=False),
    ]

    CSS = """
    .datasets-body {
        height: 1fr;
        margin: 0 1;
    }

    .datasets-table-panel {
        width: 2fr;
        border: round #40403E;
        padding: 1 2;
    }
    .datasets-table-panel:light {
        border: round #BFBFBA;
    }

    .datasets-detail-panel {
        width: 1fr;
        border: round #40403E;
        padding: 1 2;
        margin: 0 0 0 1;
    }
    .datasets-detail-panel:light {
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
        datasets_root: Path | None = None,
        ledger_root: Path | None = None,
    ) -> None:
        super().__init__()
        self.datasets_root = datasets_root
        self.ledger_root = ledger_root
        self._manifests: list[DatasetManifest] = []

    def compose(self) -> ComposeResult:
        yield Static("Datasets", classes="panel-title")
        with Horizontal(classes="datasets-body"):
            with Container(classes="datasets-table-panel"):
                yield DataTable(
                    id="datasets-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )
            with Container(classes="datasets-detail-panel"):
                yield Label(
                    Text("Dataset Details", style="bold"),
                    classes="panel-title",
                )
                yield Static(
                    "[dim]Select a dataset to view details.[/dim]",
                    id="datasets-detail",
                    markup=True,
                )
                yield Sparkline([], id="datasets-sparkline")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#datasets-table", DataTable)
        table.loading = True
        table.add_column("Dataset", key="dataset")
        table.add_column("Tasks", key="tasks")
        table.add_column("Description", key="description")
        self._load_datasets()

    @work(thread=True, exclusive=True)
    def _load_datasets(self) -> None:
        """Load dataset manifests from disk in a background thread."""
        from aec_bench.dataset.storage import list_datasets

        if self.datasets_root is None:
            manifests: list[DatasetManifest] = []
        else:
            manifests = list_datasets(self.datasets_root)

        self.app.call_from_thread(self._on_datasets_loaded, manifests)

    def _on_datasets_loaded(self, manifests: list[DatasetManifest]) -> None:
        """Populate state and table on the main thread after data loads."""
        self._manifests = manifests
        table = self.query_one("#datasets-table", DataTable)
        table.loading = False

        if self._manifests:
            self._populate_table()

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def _populate_table(self) -> None:
        """Add rows for each dataset manifest."""
        table = self.query_one("#datasets-table", DataTable)
        table.clear()

        for manifest in self._manifests:
            table.add_row(
                Text(manifest.dataset_id),
                Text(str(len(manifest.tasks))),
                Text(manifest.description),
                key=manifest.dataset_id,
            )

    # ------------------------------------------------------------------
    # Detail panel updates
    # ------------------------------------------------------------------

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update the detail pane and sparkline when the cursor moves to a row."""
        details = self.query_one("#datasets-detail", Static)
        sparkline = self.query_one("#datasets-sparkline", Sparkline)

        row_idx = event.cursor_row
        if row_idx < 0 or row_idx >= len(self._manifests):
            details.update("[dim]Select a dataset to view details.[/dim]")
            sparkline.data = []
            return

        manifest = self._manifests[row_idx]
        details.update(_render_dataset_detail(manifest))
        sparkline.data = _difficulty_sparkline_data(manifest)

    # ------------------------------------------------------------------
    # Drill-through
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Drill through to Library with dataset context."""
        if event.row_key is None:
            return
        dataset_key = str(event.row_key.value)
        self.notify(f"Selected: {dataset_key}", severity="information")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.switch_mode("dashboard")
