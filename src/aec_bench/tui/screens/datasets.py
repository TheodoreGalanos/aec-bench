# ABOUTME: Datasets screen for browsing versioned benchmark dataset snapshots.
# ABOUTME: DataTable listing with drill-down detail panel and difficulty sparkline.

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
    domains_str = ", ".join(manifest.description.domains) if manifest.description.domains else "-"
    created_str = manifest.created_at.strftime("%Y-%m-%d")
    content_hash = manifest.content_hash
    hash_short = content_hash[:12] + "..." if len(content_hash) > 12 else content_hash

    diff_dist = manifest.description.difficulty_distribution
    diff_lines = []
    if diff_dist:
        for level, count in sorted(diff_dist.items()):
            diff_lines.append(f"  {level}: {count}")

    lines = [
        f"[bold]{manifest.name}@{manifest.version}[/bold]",
        "",
        f"  Tasks:    {len(manifest.tasks)}",
        f"  Domains:  {domains_str}",
        f"  Created:  {created_str}",
        f"  Hash:     {hash_short}",
    ]

    if manifest.description.summary:
        lines.extend(["", f"  [dim]{manifest.description.summary}[/dim]"])

    if diff_lines:
        lines.extend(["", "[bold]Difficulty Distribution:[/bold]", *diff_lines])

    return "\n".join(lines)


def _difficulty_sparkline_data(manifest: DatasetManifest) -> list[float]:
    """Extract sparkline-friendly data from difficulty distribution.

    Returns values in a stable sorted order of difficulty keys.
    """
    diff_dist = manifest.description.difficulty_distribution
    if not diff_dist:
        return []
    return [float(v) for _, v in sorted(diff_dist.items())]


# ---------------------------------------------------------------------------
# DatasetsScreen — DataTable with detail panel
# ---------------------------------------------------------------------------


class DatasetsScreen(Screen):
    """Versioned benchmark dataset browser with DataTable and drill-down detail."""

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
        table.add_column("Name", key="name")
        table.add_column("Version", key="version")
        table.add_column("Tasks", key="tasks")
        table.add_column("Domains", key="domains")
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
            domains = manifest.description.domains
            domains_str = ", ".join(domains) if domains else "-"
            row_key = f"{manifest.name}@{manifest.version}"
            table.add_row(
                Text(manifest.name),
                Text(manifest.version),
                Text(str(len(manifest.tasks))),
                Text(domains_str),
                key=row_key,
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
