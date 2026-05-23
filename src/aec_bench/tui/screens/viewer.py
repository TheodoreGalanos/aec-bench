# ABOUTME: Trial viewer screen for the aec-bench TUI.
# ABOUTME: Step-based trajectory viewer with split pane layout and keyboard navigation.

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Header,
    Label,
    OptionList,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from aec_bench.config import resolve_artifact_path
from aec_bench.contracts.trajectory import TrajectoryEntry
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.trace_summary import extract_trial_trace_signals
from aec_bench.ledger.annotations import (
    TriageAnnotation,
    load_annotations,
    save_annotation,
)
from aec_bench.tui.widgets.shared import reward_color

# ---------------------------------------------------------------------------
# Step grouping helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StepSummary:
    """Aggregated view of one trajectory step for display in the step list."""

    step: int
    status: str  # "success", "fail", "incomplete"
    total_duration_ms: int
    primary_tool: str
    entries: list[TrajectoryEntry] = field(default_factory=list)
    call_type: str | None = None  # warmup, main, or subagent
    output_summary: str | None = None  # truncated preview of tool stdout


def _group_entries_by_step(entries: list[TrajectoryEntry]) -> list[_StepSummary]:
    """Group trajectory entries by step number into _StepSummary objects."""
    from collections import OrderedDict

    buckets: OrderedDict[int, list[TrajectoryEntry]] = OrderedDict()
    for entry in entries:
        buckets.setdefault(entry.step, []).append(entry)

    summaries: list[_StepSummary] = []
    for step_num, step_entries in buckets.items():
        total_ms = 0
        primary_tool = ""
        has_failure = False
        has_result = False

        for e in step_entries:
            if e.duration_ms is not None:
                total_ms += e.duration_ms
            if e.role == "tool_call" and e.tool_name and not primary_tool:
                primary_tool = e.tool_name
            if e.role == "tool_result":
                has_result = True
                if e.exit_code is not None and e.exit_code != 0:
                    has_failure = True

        if has_failure:
            status = "fail"
        elif has_result:
            status = "success"
        else:
            status = "incomplete"

        # Extract call_type from the first entry that carries one
        call_type = next(
            (e.call_type for e in step_entries if e.call_type is not None),
            None,
        )

        # Extract output_summary from the first tool_result that has one
        output_summary = next(
            (e.output_summary for e in step_entries if e.role == "tool_result" and e.output_summary),
            None,
        )

        summaries.append(
            _StepSummary(
                step=step_num,
                status=status,
                total_duration_ms=total_ms,
                primary_tool=primary_tool or ("Init" if step_num == 0 else ""),
                entries=step_entries,
                call_type=call_type,
                output_summary=output_summary,
            )
        )

    return summaries


# ---------------------------------------------------------------------------
# Rendering helpers for the split trajectory pane
# ---------------------------------------------------------------------------


def _render_step_list(steps: list[_StepSummary], selected_index: int) -> str:
    """Render the left-hand step list as Rich markup."""
    if not steps:
        return "[dim]No steps.[/dim]"

    lines: list[str] = []
    for i, step in enumerate(steps):
        icon_map = {
            "success": "[green]✓[/green]",
            "fail": "[red]✗[/red]",
            "incomplete": "[dim]○[/dim]",
        }
        icon = icon_map.get(step.status, "[dim]?[/dim]")

        label = "Init" if step.step == 0 else f"Step {step.step}"

        duration = f"{step.total_duration_ms}ms" if step.total_duration_ms > 0 else ""

        tool_display = step.primary_tool if step.primary_tool != "Init" else ""

        cursor = "▸ " if i == selected_index else "  "
        row = f"{cursor}{icon} {label:<8} {duration:>6}  {tool_display}"

        is_warmup = step.call_type == "warmup"

        if i == selected_index:
            line = f"[on #40403E]{row}[/on #40403E]"
        elif is_warmup:
            line = f"[dim]{row}[/dim]"
        else:
            line = row
        lines.append(line)

        # Show output_summary as a dim hint below the step row
        if step.output_summary:
            preview = step.output_summary[:40]
            lines.append(f"         [dim]{preview}[/dim]")

    return "\n".join(lines)


def _render_step_detail(step: _StepSummary) -> str:
    """Render full detail for a single step as Rich markup."""
    lines: list[str] = []
    label = "Init" if step.step == 0 else f"Step {step.step}"
    if step.call_type == "warmup":
        lines.append(f"[dim italic]{label} (warmup)[/dim italic]")
    else:
        lines.append(f"[bold]{label}[/bold]")
    lines.append("")

    for entry in step.entries:
        if entry.role == "system":
            lines.append("[italic dim]\\[system][/italic dim]")
            if entry.content:
                lines.append(f"[dim]{entry.content}[/dim]")
            lines.append("")

        elif entry.role == "user":
            lines.append("[bold]\\[user][/bold]")
            if entry.content:
                lines.append(entry.content)
            lines.append("")

        elif entry.role == "assistant":
            lines.append("[#D4A27F]\\[assistant][/]")
            if entry.content:
                lines.append(entry.content)
            lines.append("")

        elif entry.role == "tool_call":
            tool = entry.tool_name or "unknown"
            lines.append(f"[#61AAF2]\\[tool_call] {tool}[/]")
            if entry.command:
                lines.append(f"[dim]{entry.command}[/dim]")
            if entry.arguments:
                args_str = json.dumps(entry.arguments, indent=2)
                lines.append(f"[dim]{args_str}[/dim]")
            lines.append("")

        elif entry.role == "tool_result":
            rc = entry.exit_code if entry.exit_code is not None else 0
            rc_color = "green" if rc == 0 else "red"
            duration = f" {entry.duration_ms}ms" if entry.duration_ms is not None else ""
            lines.append(f"[{rc_color}]\\[tool_result] exit:{rc}{duration}[/]")
            if entry.stdout:
                lines.append(entry.stdout)
            if entry.stderr:
                lines.append(f"[#BF4D43]{entry.stderr}[/]")
            lines.append("")

    return "\n".join(lines)


def _render_trajectory_flat(path: Path) -> str:
    """Render trajectory.jsonl as flat Rich markup.

    Used by render_transcript for external callers (review.py, compare.py).
    """
    from aec_bench.contracts.trajectory import read_trajectory

    entries = read_trajectory(path)
    if not entries:
        return "[dim]Empty trajectory.[/dim]"

    lines: list[str] = []
    current_step = -1

    for entry in entries:
        if entry.step != current_step and entry.step > 0:
            current_step = entry.step
            if entry.call_type == "warmup":
                lines.append(f"\n[dim]Step {current_step} (warmup)[/dim]")
            else:
                lines.append(f"\n[bold]Step {current_step}[/bold]")

        if entry.role == "system":
            text = (entry.content or "")[:200]
            lines.append(f"[italic dim]system: {text}[/italic dim]")
        elif entry.role == "user":
            text = (entry.content or "")[:300]
            lines.append("\n[bold]user[/bold]")
            lines.append(f"  {text}")
        elif entry.role == "assistant":
            text = (entry.content or "")[:300]
            lines.append("  [#D4A27F]assistant[/]")
            lines.append(f"  {text}")
        elif entry.role == "tool_call":
            lines.append(f"  [#61AAF2]tool call: {entry.tool_name}[/]")
            if entry.command:
                lines.append(f"    [dim]{entry.command[:150]}[/dim]")
        elif entry.role == "tool_result":
            rc = entry.exit_code if entry.exit_code is not None else 0
            duration = f" {entry.duration_ms}ms" if entry.duration_ms is not None else ""
            color = "#BF4D43" if rc != 0 else "dim"
            lines.append(f"  [{color}]exit:{rc}{duration}[/]")
            preview = entry.output_summary or (entry.stdout[:200] if entry.stdout else None)
            if preview:
                lines.append(f"    {preview}")
            if entry.stderr:
                lines.append(f"    [#BF4D43]{entry.stderr[:200]}[/]")

    return "\n".join(lines) if lines else "[dim]Empty trajectory.[/dim]"


def _render_conversation_flat(record: TrialRecord) -> str:
    """Render conversation.jsonl as flat Rich markup for the detail pane."""
    conversation_path = record.outputs.conversation_path
    if not conversation_path:
        return "[dim]No conversation transcript available.[/dim]"

    path = resolve_artifact_path(conversation_path)
    if path is None:
        return f"[dim]Transcript file not found: {conversation_path}[/dim]"

    try:
        messages = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (json.JSONDecodeError, OSError) as exc:
        return f"[red]Error reading transcript: {exc}[/red]"

    lines: list[str] = []
    turn = 0
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if role == "user":
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        tool_content = str(item.get("content", ""))[:200]
                        lines.append(
                            f"  [dim]tool result:[/dim] {tool_content}..."
                            if len(str(item.get("content", ""))) > 200
                            else f"  [dim]tool result:[/dim] {tool_content}"
                        )
            else:
                turn += 1
                text = str(content)[:300]
                lines.append(f"\n[bold]{turn}. user[/bold]")
                lines.append(f"  {text}")

        elif role == "assistant":
            turn += 1
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text = str(block.get("text", ""))[:300]
                            lines.append(f"\n[bold #D4A27F]{turn}. assistant[/]")
                            lines.append(f"  {text}")
                        elif block.get("type") == "tool_use":
                            tool_name = block.get("name", "?")
                            tool_input = block.get("input", {})
                            input_preview = json.dumps(tool_input)[:150]
                            lines.append(f"\n  [#61AAF2]tool call: {tool_name}[/]")
                            lines.append(f"    [dim]{input_preview}[/dim]")
            elif isinstance(content, str) and content:
                text = content[:300]
                lines.append(f"\n[bold #D4A27F]{turn}. assistant[/]")
                lines.append(f"  {text}")

            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "?")
                    args = func.get("arguments", "")[:150]
                    lines.append(f"\n  [#61AAF2]tool call: {name}[/]")
                    lines.append(f"    [dim]{args}[/dim]")

        elif role == "tool":
            tool_content = str(content)[:200]
            lines.append(f"  [dim]tool result:[/dim] {tool_content}")

        elif role == "system":
            text = str(content)[:200]
            lines.append(f"\n[italic dim]system: {text}...[/italic dim]")

    if not lines:
        return "[dim]Empty transcript.[/dim]"

    return "\n".join(lines)


def render_transcript(record: TrialRecord) -> str:
    """Render a trial's conversation transcript as Rich markup.

    This is a public function imported by review.py and compare.py.
    It returns a flat text rendering suitable for Static widgets.
    """
    # Try trajectory first (structured format)
    trajectory_path = record.outputs.trajectory_path
    if trajectory_path:
        path = resolve_artifact_path(trajectory_path)
        if path is not None:
            return _render_trajectory_flat(path)

    # Fall back to conversation.jsonl rendering
    return _render_conversation_flat(record)


def _load_trajectory_steps(record: TrialRecord) -> list[_StepSummary] | None:
    """Try to load and group trajectory entries; return None when unavailable."""
    from aec_bench.contracts.trajectory import read_trajectory

    trajectory_path = record.outputs.trajectory_path
    if not trajectory_path:
        return None

    path = resolve_artifact_path(trajectory_path)
    if path is None:
        return None

    entries = read_trajectory(path)
    if not entries:
        return None

    return _group_entries_by_step(entries)


# Reusable names for REPL commands that should be filtered from variable display
_REPL_COMMANDS = frozenset(
    {
        "cat",
        "cd",
        "cp",
        "echo",
        "find",
        "grep",
        "head",
        "ls",
        "mkdir",
        "mv",
        "pwd",
        "rm",
        "sed",
        "tail",
        "touch",
        "wc",
        "python",
        "python3",
        "pip",
        "node",
        "npm",
        "git",
        "curl",
        "wget",
    }
)


class VariableDetailModal(ModalScreen[None]):
    """Modal showing the full value of an RLM variable or scratchpad entry."""

    CSS = """
    VariableDetailModal {
        align: center middle;
    }
    .modal-container {
        width: 80%;
        max-width: 100;
        height: 70%;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    .modal-title {
        dock: top;
        height: 1;
        text-style: bold;
        color: $primary;
        margin: 0 0 1 0;
    }
    .modal-body {
        height: 1fr;
        overflow-y: auto;
    }
    .modal-close {
        dock: bottom;
        height: 3;
        width: 100%;
        margin: 1 0 0 0;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, title: str, content: str) -> None:
        super().__init__()
        self._title = title
        self._content = content

    def compose(self) -> ComposeResult:
        with Container(classes="modal-container"):
            yield Static(f"[bold]{self._title}[/bold]", classes="modal-title", markup=True)
            with VerticalScroll(classes="modal-body"):
                yield Static(self._content, id="modal-content", markup=True)
            yield Button("Close (Esc)", classes="modal-close", id="modal-close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "modal-close-btn":
            self.dismiss()


class TrialViewerScreen(Screen):
    """Three-pane trial viewer: OptionList steps, RichLog transcript, tabbed details."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "go_back", "Back"),
        Binding("r", "review", "Review"),
        Binding("n", "next_trial", "Next trial"),
        Binding("p", "prev_trial", "Prev trial"),
        Binding("1", "annotate_pass", "Pass"),
        Binding("2", "annotate_fail", "Fail"),
        Binding("3", "annotate_defer", "Defer"),
        Binding("u", "undo_annotation", "Undo"),
        Binding("tab", "cycle_pane", "Next pane"),
        Binding("j", "step_next", "Next step"),
        Binding("k", "step_prev", "Prev step"),
        Binding("down", "step_next", "Next step", show=False),
        Binding("up", "step_prev", "Prev step", show=False),
        Binding("v", "inspect_variable", "Var", show=True),
        Binding("w", "inspect_scratchpad", "Scratch", show=True),
    ]

    CSS = """
    .header-bar {
        height: 6;
        layout: horizontal;
        margin: 0 1 1 1;
    }

    .header-section {
        width: 1fr;
        border: round #40403E;
        padding: 1 2;
        margin: 0 1 0 0;
    }

    .header-reward {
        width: 22;
        border: round #40403E;
        padding: 1 2;
        content-align: center middle;
    }

    .viewer-columns {
        height: 1fr;
        margin: 0 1;
    }

    .trial-list-panel {
        width: 22;
        min-width: 18;
        border: round #40403E;
        padding: 1 1;
        margin: 0 1 0 0;
    }

    .transcript-panel {
        width: 2fr;
        border: round #40403E;
        padding: 0;
        margin: 0 1 0 0;
    }

    #step-list {
        width: 30;
        min-width: 24;
        border-right: solid #40403E;
        height: 1fr;
    }

    #step-list:focus {
        border: solid #61AAF2;
    }

    #transcript-log {
        width: 1fr;
        height: 1fr;
        padding: 1 1;
    }

    #transcript-log:focus {
        border: solid #61AAF2;
    }

    .transcript-row {
        height: 1fr;
        layout: horizontal;
    }

    .details-panel {
        width: 30;
        min-width: 28;
        border: round #40403E;
        padding: 1 1;
        overflow-y: auto;
    }

    .rlm-section {
        margin-top: 1;
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
        record: TrialRecord,
        siblings: list[TrialRecord] | None = None,
    ) -> None:
        super().__init__()
        self._record = record
        self._siblings = siblings or [record]
        self._current_index = next(
            (i for i, r in enumerate(self._siblings) if r.trial_id == record.trial_id),
            0,
        )
        self._annotations: dict[str, TriageAnnotation] = {}
        self._experiment_dir: Path | None = None
        self._last_action: tuple[str, TriageAnnotation | None] | None = None
        self._steps: list[_StepSummary] = []
        self._selected_step: int = 0
        self._has_trajectory: bool = False
        self._current_variables: dict[str, object] = {}
        self._current_scratchpad_keys: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(classes="header-bar"):
            yield Static(id="header-experiment", classes="header-section")
            yield Static(id="header-metrics", classes="header-section")
            yield Static(id="header-reward", classes="header-reward")

        with Container():
            with Horizontal(classes="viewer-columns"):
                with Container(classes="trial-list-panel"):
                    yield Label("Trials", classes="panel-title")
                    yield VerticalScroll(
                        Static(id="trial-list-content", markup=True),
                        id="scroll-trials",
                    )
                with Container(classes="transcript-panel"):
                    yield Label("Trajectory", classes="panel-title", id="transcript-panel-title")
                    with Horizontal(classes="transcript-row"):
                        yield OptionList(id="step-list")
                        yield RichLog(id="transcript-log", wrap=True, highlight=True, markup=True)
                with VerticalScroll(classes="details-panel"):
                    with TabbedContent("Task", "Score", "Trace", "Cost"):
                        with TabPane("Task", id="tab-task"):
                            yield Static(id="tab-task-content", markup=True)
                        with TabPane("Score", id="tab-score"):
                            yield Static(id="tab-score-content", markup=True)
                        with TabPane("Trace", id="tab-trace"):
                            yield Static(id="tab-trace-content", markup=True)
                        with TabPane("Cost", id="tab-cost"):
                            yield Static(id="tab-cost-content", markup=True)
                    with Collapsible(title="RLM Variables", collapsed=True, classes="rlm-section"):
                        yield Static(id="rlm-variables", markup=True)
                    with Collapsible(title="Scratchpad", collapsed=True, classes="rlm-section"):
                        yield Static(id="rlm-scratchpad", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        ledger_root = getattr(self.app, "ledger_root", None)
        if ledger_root is not None:
            self._experiment_dir = ledger_root / self._record.experiment_id
            self._annotations = load_annotations(self._experiment_dir)
        self._refresh_header()
        self._refresh_trial_list()
        self._refresh_tabs()
        self._load_trajectory()

    # --- Navigation ---

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.switch_mode("dashboard")

    def action_review(self) -> None:
        """Launch Review screen if reviewer is configured on the app."""
        app = self.app
        feedback_root = getattr(app, "feedback_root", None)
        reviewer_id = getattr(app, "reviewer_id", None)
        if feedback_root is None or reviewer_id is None:
            return
        from aec_bench.tui.screens.review import ReviewScreen

        self.app.push_screen(
            ReviewScreen(
                ledger_root=app.ledger_root,
                tasks_root=app.tasks_root,
                feedback_root=feedback_root,
                reviewer_id=reviewer_id,
            )
        )

    def action_next_trial(self) -> None:
        if self._current_index < len(self._siblings) - 1:
            self._current_index += 1
            self._record = self._siblings[self._current_index]
            self._refresh_on_trial_change()

    def action_prev_trial(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._record = self._siblings[self._current_index]
            self._refresh_on_trial_change()

    _FOCUS_CYCLE = ("scroll-trials", "step-list", "transcript-log")

    def action_cycle_pane(self) -> None:
        """Cycle focus between the three scrollable panes."""
        current = self.focused
        current_id = current.id if current else None
        try:
            idx = self._FOCUS_CYCLE.index(current_id)
            next_idx = (idx + 1) % len(self._FOCUS_CYCLE)
        except (ValueError, TypeError):
            next_idx = 0
        target_id = self._FOCUS_CYCLE[next_idx]
        try:
            target = self.query_one(f"#{target_id}")
            target.focus()
        except Exception:
            pass

    def action_step_next(self) -> None:
        """Move to the next step in the trajectory."""
        if self._has_trajectory and self._selected_step < len(self._steps) - 1:
            self._selected_step += 1
            option_list = self.query_one("#step-list", OptionList)
            option_list.highlighted = self._selected_step
            self._show_step_detail(self._selected_step)

    def action_step_prev(self) -> None:
        """Move to the previous step in the trajectory."""
        if self._has_trajectory and self._selected_step > 0:
            self._selected_step -= 1
            option_list = self.query_one("#step-list", OptionList)
            option_list.highlighted = self._selected_step
            self._show_step_detail(self._selected_step)

    # --- OptionList event ---

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Show step detail when a step is selected in the OptionList."""
        if event.option.id is not None:
            step_idx = int(event.option.id)
            self._selected_step = step_idx
            self._show_step_detail(step_idx)

    # --- Annotation ---

    def _annotate(self, verdict: str) -> None:
        """Apply a triage annotation to the current trial."""
        trial_id = self._record.trial_id
        if self._experiment_dir is None:
            return
        previous = self._annotations.get(trial_id)
        self._last_action = (trial_id, previous)
        existing_notes = previous.notes if previous else ""
        annotation = TriageAnnotation.create(verdict=verdict, notes=existing_notes)  # type: ignore[arg-type]
        self._annotations[trial_id] = annotation
        save_annotation(self._experiment_dir, trial_id, annotation)
        self._refresh_header()
        self._refresh_trial_list()

    def action_annotate_pass(self) -> None:
        self._annotate("pass")

    def action_annotate_fail(self) -> None:
        self._annotate("fail")

    def action_annotate_defer(self) -> None:
        self._annotate("defer")

    def action_undo_annotation(self) -> None:
        """Undo the last annotation."""
        if self._last_action is None or self._experiment_dir is None:
            return
        trial_id, previous = self._last_action
        self._last_action = None
        if previous is None:
            self._annotations.pop(trial_id, None)
            from aec_bench.ledger.annotations import delete_annotation

            delete_annotation(self._experiment_dir, trial_id)
        else:
            self._annotations[trial_id] = previous
            save_annotation(self._experiment_dir, trial_id, previous)
        self._refresh_header()
        self._refresh_trial_list()

    # --- Trajectory loading via @work ---

    @work(thread=True, exclusive=True)
    def _load_trajectory(self) -> None:
        """Load trajectory steps in a background thread."""
        steps = _load_trajectory_steps(self._record)
        self.app.call_from_thread(self._on_trajectory_loaded, steps)

    def _on_trajectory_loaded(self, steps: list[_StepSummary] | None) -> None:
        """Handle trajectory data once loaded; populate OptionList and RichLog."""
        transcript_log = self.query_one("#transcript-log", RichLog)
        option_list = self.query_one("#step-list", OptionList)
        title_widget = self.query_one("#transcript-panel-title", Label)

        if steps is None or len(steps) == 0:
            # No trajectory; show flat transcript in RichLog
            self._has_trajectory = False
            self._steps = []
            self._selected_step = 0
            title_widget.update("Completion History")
            option_list.clear_options()
            option_list.display = False
            transcript_log.clear()
            transcript_log.write(render_transcript(self._record))
            self._update_rlm_state(None)
            return

        self._has_trajectory = True
        self._steps = steps
        self._selected_step = 0

        title_widget.update("Trajectory")
        option_list.display = True

        # Populate OptionList with one option per step
        option_list.clear_options()
        for step in steps:
            icon_map = {
                "success": "\u2713",
                "fail": "\u2717",
                "incomplete": "\u2026",
            }
            icon = icon_map.get(step.status, "?")
            label = "Init" if step.step == 0 else f"Step {step.step}"
            has_tool = step.primary_tool and step.primary_tool != "Init"
            tool_part = f" {step.primary_tool}" if has_tool else ""
            duration_part = f" ({step.total_duration_ms}ms)" if step.total_duration_ms > 0 else ""
            option_text = f"{icon} {label}{tool_part}{duration_part}"
            option_list.add_option(Option(option_text, id=str(step.step)))

        # Show first step in the RichLog
        option_list.highlighted = 0
        self._show_step_detail(0)

    def _show_step_detail(self, step_index: int) -> None:
        """Write the step detail for step_index into the RichLog and update RLM state."""
        transcript_log = self.query_one("#transcript-log", RichLog)
        transcript_log.clear()

        if 0 <= step_index < len(self._steps):
            step = self._steps[step_index]
            transcript_log.write(_render_step_detail(step))
            self._update_rlm_state(step)
        else:
            transcript_log.write("[dim]No step selected.[/dim]")
            self._update_rlm_state(None)

    def _update_rlm_state(self, step: _StepSummary | None) -> None:
        """Update the RLM Variables and Scratchpad collapsibles from step metadata."""
        variables_widget = self.query_one("#rlm-variables", Static)
        scratchpad_widget = self.query_one("#rlm-scratchpad", Static)

        if step is None:
            variables_widget.update("[dim]No RLM data.[/dim]")
            scratchpad_widget.update("[dim]No scratchpad data.[/dim]")
            self._current_variables = {}
            self._current_scratchpad_keys = []
            return

        # Collect metadata from the step entries (last one wins)
        metadata: dict[str, object] | None = None
        for entry in step.entries:
            if entry.metadata:
                metadata = entry.metadata

        if metadata is None:
            variables_widget.update("[dim]No RLM metadata for this step.[/dim]")
            scratchpad_widget.update("[dim]No scratchpad for this step.[/dim]")
            self._current_variables = {}
            self._current_scratchpad_keys = []
            return

        # RLM Variables — filter out functions and REPL commands
        variables = metadata.get("variables", {})
        self._current_variables = {}
        if variables and isinstance(variables, dict):
            var_lines: list[str] = []
            for key, value in variables.items():
                # Skip REPL commands and function-type variables
                if key.lower() in _REPL_COMMANDS:
                    continue
                if isinstance(value, dict) and value.get("type") == "function":
                    continue
                if isinstance(value, str) and value.startswith("function"):
                    continue
                self._current_variables[key] = value
                preview = str(value)[:60]
                idx = len(self._current_variables)
                var_lines.append(f"  [bold #61AAF2]{idx}. {key}[/bold #61AAF2]  {preview}")
            if var_lines:
                var_lines.insert(0, "[dim]Press 'v' to inspect a variable[/dim]")
                variables_widget.update("\n".join(var_lines))
            else:
                variables_widget.update("[dim]No variables recorded.[/dim]")
        else:
            variables_widget.update("[dim]No variables recorded.[/dim]")

        # Scratchpad — clickable keys
        scratchpad = metadata.get("scratchpad", {})
        scratchpad_keys = metadata.get("scratchpad_keys", [])
        self._current_scratchpad_keys = []
        if isinstance(scratchpad, dict) and scratchpad:
            sp_lines = ["[dim]Press 'w' to inspect a scratchpad entry[/dim]"]
            for idx, (key, value) in enumerate(scratchpad.items(), 1):
                self._current_scratchpad_keys.append(key)
                preview = str(value)[:60]
                sp_lines.append(f"  [bold #D4A27F]{idx}. {key}[/bold #D4A27F]  {preview}")
            scratchpad_widget.update("\n".join(sp_lines))
        elif scratchpad_keys:
            sp_lines = ["[dim]Press 'w' to inspect a scratchpad entry[/dim]"]
            for idx, key in enumerate(scratchpad_keys, 1):
                self._current_scratchpad_keys.append(key)
                sp_lines.append(f"  [bold #D4A27F]{idx}. {key}[/bold #D4A27F]")
            scratchpad_widget.update("\n".join(sp_lines))
        elif isinstance(scratchpad, str) and scratchpad:
            scratchpad_widget.update(str(scratchpad)[:500])
        else:
            scratchpad_widget.update("[dim]No scratchpad content.[/dim]")

    def action_inspect_variable(self) -> None:
        """Show variable values in a modal. If one variable, show it. If many, show all."""
        if not self._current_variables:
            self.notify("No variables for this step", severity="information")
            return
        if len(self._current_variables) == 1:
            key = next(iter(self._current_variables))
            self._show_variable_modal(key)
        else:
            # Show all variables in one modal
            lines: list[str] = []
            for key, value in self._current_variables.items():
                formatted = self._format_value(value)
                lines.append(f"[bold #61AAF2]{key}[/bold #61AAF2]\n{formatted}\n")
            self.app.push_screen(VariableDetailModal(title="RLM Variables", content="\n".join(lines)))

    def action_inspect_scratchpad(self) -> None:
        """Show scratchpad values in a modal."""
        if not self._current_scratchpad_keys:
            self.notify("No scratchpad for this step", severity="information")
            return
        # Gather values from current step metadata
        values: dict[str, object] = {}
        if self._steps and 0 <= self._selected_step < len(self._steps):
            step = self._steps[self._selected_step]
            for entry in reversed(step.entries):
                if entry.metadata:
                    sp = entry.metadata.get("scratchpad", {})
                    if isinstance(sp, dict):
                        values = sp
                        break
        lines: list[str] = []
        for key in self._current_scratchpad_keys:
            value = values.get(key, "Value not available")
            formatted = self._format_value(value)
            lines.append(f"[bold #D4A27F]{key}[/bold #D4A27F]\n{formatted}\n")
        self.app.push_screen(VariableDetailModal(title="Scratchpad", content="\n".join(lines)))

    def _show_variable_modal(self, key: str) -> None:
        """Show a single variable's full value in a modal."""
        value = self._current_variables.get(key, "Not found")
        content = self._format_value(value)
        self.app.push_screen(VariableDetailModal(title=f"Variable: {key}", content=content))

    def _format_value(self, value: object) -> str:
        """Format a value for modal display."""
        if isinstance(value, dict | list):
            try:
                return json.dumps(value, indent=2, default=str)
            except Exception:
                return str(value)
        return str(value)

    # --- Refresh helpers ---

    def _refresh_on_trial_change(self) -> None:
        """Full refresh when switching between sibling trials."""
        self._selected_step = 0
        self._refresh_header()
        self._refresh_trial_list()
        self._refresh_tabs()
        self._load_trajectory()

    def _refresh_header(self) -> None:
        """Update the top bar with experiment, metrics, and reward info."""
        record = self._record
        reward = record.evaluation.reward
        r_color = reward_color(reward)

        # Header bar — experiment info
        exp = self.query_one("#header-experiment", Static)
        task_parts = record.task.task_id.split("/")
        task_short = "/".join(task_parts[-2:]) if len(task_parts) > 1 else record.task.task_id
        exp.update(
            f"[bold]Task:[/bold] {task_short}\n"
            f"[dim]Model:[/dim] {record.agent.model}  "
            f"[dim]Trial:[/dim] {self._current_index + 1}/{len(self._siblings)}"
        )

        # Header bar — metrics + annotation
        metrics = self.query_one("#header-metrics", Static)
        agent_result = record.outputs.agent_result or {}
        turns = agent_result.get("turns_used", "?")
        max_turns = agent_result.get("max_turns", "?")
        ann = self._annotations.get(record.trial_id)
        if ann is not None:
            verdict_colors = {"pass": "green", "fail": "red", "defer": "yellow", "note": "dim"}
            ann_color = verdict_colors.get(ann.verdict, "dim")
            ann_display = f"[{ann_color}]{ann.verdict}[/]"
        else:
            ann_display = "[dim]—[/dim]"
        metrics.update(
            f"[dim]Turns:[/dim] {turns}/{max_turns}\n"
            f"[dim]Adapter:[/dim] {record.agent.adapter}  [dim]Ann:[/dim] {ann_display}"
        )

        # Header bar — reward (big, colored, with label)
        rw = self.query_one("#header-reward", Static)
        rw.update(f"[dim]Score[/dim]\n[bold {r_color}]{reward:.3f}[/]")

    def _refresh_trial_list(self) -> None:
        """Update the trial sidebar with annotation markers."""
        trial_list = self.query_one("#trial-list-content", Static)
        trial_lines = []
        for i, sibling in enumerate(self._siblings):
            r = sibling.evaluation.reward
            color = reward_color(r)
            cursor = ">" if i == self._current_index else " "
            bg = " on #40403E" if i == self._current_index else ""
            sib_ann = self._annotations.get(sibling.trial_id)
            if sib_ann is not None:
                ann_icons = {
                    "pass": "[green]v[/]",
                    "fail": "[red]x[/]",
                    "defer": "[yellow]?[/]",
                    "note": "[dim].[/]",
                }
                ann_mark = ann_icons.get(sib_ann.verdict, " ")
            else:
                ann_mark = " "
            trial_lines.append(f"[{color}{bg}]{cursor}{ann_mark}{sibling.trial_id[:15]} {r:.3f}[/]")
        trial_list.update("\n".join(trial_lines))

    def _refresh_tabs(self) -> None:
        """Update the detail tabs with task, score, trace, and cost info."""
        record = self._record
        self.query_one("#tab-task-content", Static).update(self._render_task_tab(record))
        self.query_one("#tab-score-content", Static).update(self._render_score_tab(record))
        self.query_one("#tab-trace-content", Static).update(self._render_trace_tab(record))
        self.query_one("#tab-cost-content", Static).update(self._render_cost_tab(record))

    def _render_task_tab(self, record: TrialRecord) -> str:
        return "\n".join(
            [
                "[bold #D4A27F]Task[/]",
                f"  ID:       {record.task.task_id}",
                f"  Revision: {record.task.task_revision}",
                "",
                "[bold #61AAF2]Agent[/]",
                f"  Adapter:  {record.agent.adapter}",
                f"  Model:    {record.agent.model}",
                f"  Revision: {record.agent.adapter_revision or 'n/a'}",
                "",
                "[bold #CC785C]Environment[/]",
                f"  Image:    {record.environment.runtime_image}",
                f"  Backend:  {record.environment.compute_backend}",
                "",
                f"[bold]Completeness[/]: {record.completeness.value}",
            ]
        )

    def _render_score_tab(self, record: TrialRecord) -> str:
        ev = record.evaluation
        r_color = reward_color(ev.reward)
        lines = [
            f"[bold]Reward[/]: [{r_color}]{ev.reward:.3f}[/]",
            "",
            "[bold #61AAF2]Validity[/]",
            f"  Output parseable: {ev.validity.output_parseable}",
            f"  Schema valid:     {ev.validity.schema_valid}",
            f"  Verifier ran:     {ev.validity.verifier_completed}",
        ]
        if ev.validity.errors:
            lines.append(f"  [#BF4D43]Errors: {', '.join(ev.validity.errors)}[/]")

        if ev.breakdown:
            lines.append("")
            lines.append("[bold #CC785C]Breakdown[/]")
            for key, value in ev.breakdown.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def _render_trace_tab(self, record: TrialRecord) -> str:
        signals = extract_trial_trace_signals(record)
        lines = [
            "[bold #91918D]Trace Signals[/]",
            f"  Has transcript:  {bool(signals['has_transcript'])}",
            f"  Total messages:  {signals['total_messages']}",
            f"  Assistant msgs:  {signals['assistant_messages']}",
            f"  Tool calls:      {signals['tool_call_count']}",
            f"  Tool errors:     {signals['tool_errors']}",
            f"  Bash calls:      {signals['bash_tool_call_count']}",
            f"  Used calc tool:  {signals['used_calc_tool']}",
            f"  Wrote output:    {signals['wrote_output']}",
        ]
        if signals["first_error"]:
            lines.append(f"  [#BF4D43]First error: {signals['first_error'][:80]}[/]")
        return "\n".join(lines)

    def _render_cost_tab(self, record: TrialRecord) -> str:
        lines = ["[bold #CC785C]Cost & Usage[/]"]

        if record.cost:
            if record.cost.tokens_in is not None:
                lines.append(f"  Input tokens:  {record.cost.tokens_in:,}")
            if record.cost.tokens_out is not None:
                lines.append(f"  Output tokens: {record.cost.tokens_out:,}")
            if record.cost.estimated_cost_usd is not None:
                lines.append(f"  Estimated USD: [#D4A27F]${record.cost.estimated_cost_usd:.4f}[/]")
        else:
            lines.append("  [dim]No cost data available.[/dim]")

        lines.extend(
            [
                "",
                "[bold #666663]Timing[/]",
                f"  Total seconds: {record.timing.total_seconds:.1f}",
            ]
        )
        if record.timing.agent_seconds is not None:
            lines.append(f"  Agent seconds: {record.timing.agent_seconds:.1f}")

        agent_result = record.outputs.agent_result or {}
        turns = agent_result.get("turns_used")
        max_turns = agent_result.get("max_turns")
        if turns is not None:
            lines.extend(
                [
                    "",
                    "[bold #EBDBBC]Turns[/]",
                    f"  Used: {turns}" + (f" / {max_turns}" if max_turns else ""),
                ]
            )

        return "\n".join(lines)
