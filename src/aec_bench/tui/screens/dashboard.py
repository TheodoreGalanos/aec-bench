# ABOUTME: Dashboard screen for the aec-bench TUI — replaces the original LandingScreen.
# ABOUTME: Shows ASCII title, pixel art, stat cards, sparkline, and experiment DataTable.

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Sparkline, Static

from aec_bench import __version__
from aec_bench.ledger.reader import read_trial_records
from aec_bench.tui.assets.pixel_art import ASCII_TITLE
from aec_bench.tui.widgets.live_stats import (
    DatasetSummaryItem,
    DisciplineSummary,
    ExperimentSummary,
    build_datasets_summary,
    build_disciplines_summary,
    build_experiments_summary,
)
from aec_bench.tui.widgets.shared import reward_style
from aec_bench.tui.widgets.stat_card import StatCard

# Characters that belong to the block-art portion of the title
_BLOCK_CHARS = frozenset("█▀▄▌▐░▓")

# Characters that form the box-drawing shadow layer
_SHADOW_CHARS = frozenset("╔╗╚╝║═╠╣╦╩╬")


class DashboardScreen(Screen):
    """Dashboard hub: ASCII title, pixel art, stat cards, sparkline, experiment table."""

    CSS = """
    #ascii-title {
        width: 100%;
        color: $primary;
        margin: 1 0 0 2;
        height: auto;
    }

    .dashboard-body {
        height: 1fr;
        border: round #D4A27F;
        border-title-align: center;
        border-title-color: #D4A27F;
        border-title-style: bold;
        margin: 0 1;
    }
    .dashboard-body:light {
        border: round #CC785C;
    }

    .dashboard-columns {
        height: 1fr;
    }

    .branding-panel {
        width: 100;
        height: 100%;
        padding: 1 0 0 2;
        overflow: hidden;
    }

    #branding {
        margin: 1 0 0 2;
    }

    #tagline {
        color: $primary;
        text-style: italic bold;
        margin: 1 0 0 2;
        padding: 0;
    }

    #status-bar {
        margin: 0 0 0 2;
        padding: 0;
        color: $secondary;
    }

    .data-panel {
        width: 1fr;
        height: 100%;
        padding: 2 2;
    }

    .stat-row {
        height: auto;
        width: 100%;
        margin: 0 0 1 0;
    }

    .sparkline-section {
        height: auto;
        margin: 0 0 1 0;
    }

    #sparkline-label {
        height: 1;
        color: $secondary;
    }

    #reward-sparkline {
        height: 3;
        margin: 0;
        color: $accent;
    }

    #experiment-table {
        height: auto;
        max-height: 50%;
    }

    #cli-commands {
        margin: 1 0 0 0;
    }

    #agent-skills {
        margin: 1 0 0 0;
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
    ) -> None:
        super().__init__()
        self.ledger_root = ledger_root
        self.tasks_root = tasks_root
        self.feedback_root = feedback_root
        self.experiment_id = experiment_id
        self.reviewer_id = reviewer_id
        self.datasets_root = datasets_root
        self.project_root = project_root

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(self._render_title(), id="ascii-title")

        with Container(classes="dashboard-body") as body:
            body.border_title = f"aec-bench v{__version__}"
            with Horizontal(classes="dashboard-columns"):
                with Container(classes="branding-panel"):
                    yield Static(self._render_mascot(), id="pixel-art")
                    yield Static(self._render_branding(), id="branding")
                    tagline = Text(
                        '"Engineering intelligence, benchmarked."',
                        style="italic bold #D4A27F",
                    )
                    yield Static(tagline, id="tagline")
                    yield Static(
                        Text("Loading...", style="#91918D"),
                        id="status-bar",
                    )
                with VerticalScroll(classes="data-panel"):
                    with Horizontal(classes="stat-row"):
                        yield StatCard("--", "Trials", id="stat-trials")
                        yield StatCard("--", "Templates", id="stat-templates")
                        yield StatCard("--", "Mean Reward", id="stat-reward")
                        yield StatCard("--", "Disciplines", id="stat-disciplines")
                    with Container(classes="sparkline-section"):
                        yield Static(
                            "[dim]Reward Distribution (sorted)[/dim]",
                            id="sparkline-label",
                            markup=True,
                        )
                        yield Sparkline([], id="reward-sparkline")
                    table = DataTable(id="experiment-table", cursor_type="row")
                    table.loading = True
                    yield table
                    yield Static(self._render_cli_commands(), id="cli-commands")
                    yield Static(self._render_agent_skills(), id="agent-skills")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#experiment-table", DataTable)
        table.add_columns("Experiment", "Trials", "Mean Reward")
        self._load_dashboard_data()

    # ------------------------------------------------------------------
    # Async data loading
    # ------------------------------------------------------------------

    @work(thread=True, exclusive=True)
    def _load_dashboard_data(self) -> None:
        """Load live stats in a background thread, then update widgets."""
        try:
            templates_root = self.tasks_root.parent / "src" / "aec_bench" / "templates" / "builtin"

            experiments = build_experiments_summary(self.ledger_root, experiment_id=self.experiment_id)
            disciplines = build_disciplines_summary(self.tasks_root, templates_root)
            datasets = build_datasets_summary(self.datasets_root)

            # Load individual trial rewards for the sparkline distribution
            records = read_trial_records(self.ledger_root, experiment_id=self.experiment_id)
            trial_rewards = sorted([r.evaluation.reward for r in records])

            self.app.call_from_thread(self._update_widgets, experiments, disciplines, datasets, trial_rewards)
        except Exception:
            self.app.call_from_thread(self.notify, "Failed to load dashboard data", severity="error")

    def _update_widgets(
        self,
        experiments: list[ExperimentSummary],
        disciplines: list[DisciplineSummary],
        datasets: list[DatasetSummaryItem],
        trial_rewards: list[float] | None = None,
    ) -> None:
        """Populate stat cards, sparkline, and experiment table on the main thread."""
        total_trials = sum(e.trial_count for e in experiments)
        total_templates = sum(d.template_count for d in disciplines)
        total_seeds = sum(d.seed_count for d in disciplines)

        # Compute overall mean reward across all experiments
        if experiments:
            weighted_sum = sum(e.mean_reward * e.trial_count for e in experiments)
            overall_mean = weighted_sum / total_trials if total_trials else 0.0
        else:
            overall_mean = 0.0

        # Update stat cards
        try:
            self.query_one("#stat-trials", StatCard).value = str(total_trials)
            self.query_one("#stat-templates", StatCard).value = str(total_templates)

            reward_text = f"{overall_mean:.2f}"
            reward_card = self.query_one("#stat-reward", StatCard)
            reward_card.value = reward_text
            reward_card.color = reward_style(overall_mean)

            self.query_one("#stat-disciplines", StatCard).value = str(len(disciplines))
        except Exception:
            pass

        # Update sparkline with sorted individual trial rewards (distribution)
        try:
            sparkline = self.query_one("#reward-sparkline", Sparkline)
            sparkline.data = trial_rewards if trial_rewards else [0.0]
        except Exception:
            pass

        # Populate experiment table
        try:
            table = self.query_one("#experiment-table", DataTable)
            table.clear()
            for exp in experiments:
                color = reward_style(exp.mean_reward)
                reward_cell = Text(f"★ {exp.mean_reward:.2f}", style=color)
                table.add_row(
                    exp.experiment_id,
                    str(exp.trial_count),
                    reward_cell,
                    key=exp.experiment_id,
                )
            table.loading = False
        except Exception:
            pass

        # Update status bar
        try:
            status_text = Text(
                f"{len(disciplines)} disciplines \u00b7 {total_seeds} seeds \u00b7 "
                f"{total_templates} templates \u00b7 {total_trials} trials",
                style="#91918D",
            )
            self.query_one("#status-bar", Static).update(status_text)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Drill-through
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Drill through to Triage filtered by the selected experiment."""
        if event.row_key is None:
            return
        experiment_id = str(event.row_key.value)
        from aec_bench.tui.screens.triage import TriageScreen

        self.app.switch_mode("review")
        self.app.push_screen(
            TriageScreen(
                ledger_root=self.ledger_root,
                experiment_id=experiment_id,
            )
        )

    # ------------------------------------------------------------------
    # Renderers
    # ------------------------------------------------------------------

    def _render_mascot(self) -> object:
        """Render the mascot image from the JPEG asset using rich-pixels."""
        try:
            from pathlib import Path

            from PIL import Image
            from rich_pixels import Pixels

            mascot_path = Path(__file__).parent.parent / "assets" / "mascot.jpg"
            if mascot_path.exists():
                img = Image.open(mascot_path)
                # Render at 95 cols wide — fits the 100-char branding panel
                target_w = 95
                target_h = int(target_w * img.height / img.width)
                img = img.resize((target_w, target_h), Image.LANCZOS)
                return Pixels.from_image(img)
        except Exception:
            pass
        return Text("aec-bench", style="bold #D4A27F")

    def _render_title(self) -> Text:
        """Build a styled Rich Text from the ASCII_TITLE constant.

        Block and shadow characters render in Kraft (#D4A27F), except the
        bottom shadow line which uses dim grey (#40403E) for 3D depth.
        """
        lines = ASCII_TITLE.split("\n")
        last_line_idx = len(lines) - 1
        result = Text()
        for line_idx, line in enumerate(lines):
            is_bottom = line_idx == last_line_idx
            for char in line:
                if char in _BLOCK_CHARS:
                    result.append(char, style="bold #D4A27F")
                elif char in _SHADOW_CHARS:
                    result.append(char, style="#40403E" if is_bottom else "#D4A27F")
                else:
                    result.append(char, style="#D4A27F")
            if line_idx < last_line_idx:
                result.append("\n")
        return result

    def _render_branding(self) -> Text:
        """Render the branding block below the pixel art."""
        text = Text()
        text.append("aec-bench", style="bold #D4A27F")
        return text

    def _render_cli_commands(self) -> Text:
        """Render the CLI commands quick-reference section."""
        text = Text()
        text.append("CLI Commands", style="bold #E5E4DF")
        text.append("\n")
        cli_commands = [
            ("aec-bench run", "run an experiment"),
            ("aec-bench init", "scaffold a new project"),
            ("aec-bench generate task", "create instances from template"),
            ("aec-bench generate dataset", "build dataset from suite.toml"),
            ("aec-bench evaluate", "score trial results"),
            ("aec-bench search", "search tasks and templates"),
            ("aec-bench tui", "launch this interface"),
        ]
        max_cmd = max(len(c) for c, _ in cli_commands)
        for cmd, description in cli_commands:
            text.append(f"  {cmd:<{max_cmd}}", style="#61AAF2")
            text.append(f"  {description}", style="#91918D")
            text.append("\n")
        return text

    def _render_agent_skills(self) -> Text:
        """Render the agent skills quick-reference section."""
        text = Text()
        text.append("Agent Skills", style="bold #E5E4DF")
        text.append("\n")
        skills = [
            ("/add-task", "interview-driven seed creation"),
            ("/create-template", "build generation template from seed"),
            ("/create-dataset", "compose a versioned benchmark dataset"),
            ("/configure-experiment", "set up an experiment config"),
            ("/hardening-pass", "quality-gate template or instance"),
            ("/domain-check", "verify architectural invariants"),
        ]
        max_skill = max(len(s) for s, _ in skills)
        for skill, description in skills:
            text.append(f"  {skill:<{max_skill}}", style="#61AAF2")
            text.append(f"  {description}", style="#91918D")
            text.append("\n")
        return text
