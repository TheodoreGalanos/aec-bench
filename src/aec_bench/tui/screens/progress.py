# ABOUTME: Displays one provider-neutral read-only run progress projection.
# ABOUTME: Loads only explicit operational and portable plan roots and never reads trial attachments.

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static

from aec_bench.tui.progress import load_run_progress_view_model, render_run_progress


class RunProgressScreen(Screen[None]):
    """Show the shared run progress view model in the terminal UI."""

    def __init__(
        self,
        *,
        run_id: str,
        operational_store_path: Path,
        plan_root: Path,
    ) -> None:
        super().__init__()
        self.run_id = run_id
        self.operational_store_path = operational_store_path
        self.plan_root = plan_root

    def compose(self) -> ComposeResult:
        yield Static("Run status", id="run-progress-title")
        yield Static("Loading…", id="run-progress-body")
        yield Footer()

    def on_mount(self) -> None:
        self._load_progress()

    @work(thread=True, exclusive=True)
    def _load_progress(self) -> None:
        try:
            view_model = load_run_progress_view_model(
                self.run_id,
                operational_store_path=self.operational_store_path,
                plan_root=self.plan_root,
            )
            message = render_run_progress(view_model)
        except (OSError, RuntimeError, ValueError) as error:
            message = f"Unable to load run status: {error}"
        self.app.call_from_thread(self._show_progress, message)

    def _show_progress(self, message: str) -> None:
        self.query_one("#run-progress-body", Static).update(message)
