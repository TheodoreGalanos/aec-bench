# ABOUTME: Main Textual application for the aec-bench TUI.
# ABOUTME: Manages screen modes, global navigation, theme, and shared state.

from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding
from textual.screen import Screen
from textual.theme import Theme

from aec_bench import __version__
from aec_bench.tui.commands import AecBenchProvider

# aec-bench interface palette — dark variant
AEC_BENCH_DARK = Theme(
    name="aec-bench-dark",
    primary="#D4A27F",  # Kraft
    secondary="#91918D",  # Cloud Medium
    accent="#61AAF2",  # Focus (blue)
    warning="#D4A27F",  # Kraft
    error="#BF4D43",  # Error (red)
    success="#BFBFBA",  # Cloud Light
    background="#191919",  # Slate Dark
    surface="#262625",  # Slate Medium
    panel="#262625",  # Slate Medium
    foreground="#E5E4DF",  # Ivory Dark
    dark=True,
)

# aec-bench interface palette — light variant
AEC_BENCH_LIGHT = Theme(
    name="aec-bench-light",
    primary="#CC785C",  # Book Cloth
    secondary="#BFBFBA",  # Cloud Light (border colour)
    accent="#61AAF2",  # Focus (blue)
    warning="#D4A27F",  # Kraft
    error="#BF4D43",  # Error (red)
    success="#666663",  # Cloud Dark
    background="#FAFAF7",  # Ivory Light
    surface="#F0F0EB",  # Ivory Medium
    panel="#F0F0EB",  # Ivory Medium
    foreground="#191919",  # Slate Dark
    dark=False,
)


class AecBenchTUI(App[None]):
    """Interactive terminal UI for browsing, viewing, and reviewing AEC-Bench trials."""

    TITLE = "aec-bench"
    SUB_TITLE = f"AEC Benchmark Platform v{__version__}"
    ENABLE_COMMAND_PALETTE = True
    COMMANDS = App.COMMANDS | {AecBenchProvider}

    MODES = {
        "dashboard": Screen,
        "explore": Screen,
        "review": Screen,
        "analyse": Screen,
    }

    BINDINGS = [
        Binding("d", "switch_mode('dashboard')", "Dashboard", show=True),
        Binding("e", "switch_mode('explore')", "Explore", show=True),
        Binding("r", "switch_mode('review')", "Review", show=True),
        Binding("a", "switch_mode('analyse')", "Analyse", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+p", "command_palette", "Search", show=True),
        Binding("D", "toggle_dark", "Dark mode", show=False),
    ]

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
        height: 100%;
        min-height: 100%;
    }

    .header-section,
    .header-reward,
    .trial-list-panel,
    .transcript-panel,
    .details-panel,
    .triage-filter-bar,
    .triage-list-panel,
    .triage-details-panel,
    .library-summary-panel,
    .library-tree-panel,
    .library-details-panel,
    .review-queue-panel,
    .review-transcript-panel,
    .review-form-panel {
        &:light {
            border: round #BFBFBA;
        }
    }
    """

    def __init__(
        self,
        *,
        ledger_root: Path,
        tasks_root: Path,
        feedback_root: Path | None = None,
        experiment_id: str | None = None,
        reviewer_id: str | None = None,
        datasets_root: Path | None = None,
        project_root: Path | None = None,
        initial_mode: str = "dashboard",
    ) -> None:
        super().__init__()
        self.ledger_root = ledger_root
        self.tasks_root = tasks_root
        self.feedback_root = feedback_root
        self.initial_experiment_id = experiment_id
        self.reviewer_id = reviewer_id
        self.datasets_root = datasets_root
        self.project_root = project_root
        self.initial_mode = initial_mode

        # Replace the placeholder MODES callables with real screen factories.
        # Textual calls each callable with no arguments, so we use lambdas
        # that close over self to pass the constructor arguments through.
        self._modes = {
            "dashboard": lambda: self._make_dashboard(),
            "explore": lambda: self._make_explore(),
            "review": lambda: self._make_review(),
            "analyse": lambda: self._make_analyse(),
        }

    # ------------------------------------------------------------------
    # Mode screen factories — lazy imports to avoid circular dependencies
    # ------------------------------------------------------------------

    def _make_dashboard(self) -> Screen:
        """Build the DashboardScreen for the dashboard mode."""
        from aec_bench.tui.screens.dashboard import DashboardScreen

        return DashboardScreen(
            ledger_root=self.ledger_root,
            tasks_root=self.tasks_root,
            feedback_root=self.feedback_root,
            experiment_id=self.initial_experiment_id,
            reviewer_id=self.reviewer_id,
            datasets_root=self.datasets_root,
            project_root=self.project_root,
        )

    def _make_explore(self) -> Screen:
        """Build the LibraryScreen for the explore mode."""
        from aec_bench.tui.screens.library import LibraryScreen

        return LibraryScreen(
            tasks_root=self.tasks_root,
            datasets_root=self.datasets_root,
            ledger_root=self.ledger_root,
        )

    def _make_review(self) -> Screen:
        """Build the TriageScreen for the review mode."""
        from aec_bench.tui.screens.triage import TriageScreen

        return TriageScreen(
            ledger_root=self.ledger_root,
            experiment_id=self.initial_experiment_id,
        )

    def _make_analyse(self) -> Screen:
        """Build the EvaluateScreen for the analyse mode."""
        from aec_bench.tui.screens.evaluate import EvaluateScreen

        return EvaluateScreen(
            ledger_root=self.ledger_root,
            experiment_id=self.initial_experiment_id,
        )

    def on_mount(self) -> None:
        self.register_theme(AEC_BENCH_DARK)
        self.register_theme(AEC_BENCH_LIGHT)
        self.theme = "aec-bench-dark"
        self.switch_mode(self.initial_mode)
