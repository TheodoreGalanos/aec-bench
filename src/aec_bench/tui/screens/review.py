# ABOUTME: Review screen for the aec-bench TUI.
# ABOUTME: Annotation queue, transcript viewer, and judgment/calibration/adjudication forms.

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    TextArea,
)

from aec_bench.contracts.evaluation_result import Judgment
from aec_bench.feedback.models import (
    CalibrationReference,
    ReviewAssignment,
    parse_categories,
)
from aec_bench.feedback.review_service import (
    ReviewQueueSnapshot,
    ReviewTrialBundle,
    adjudicate_review_trial,
    load_review_bundle,
    load_review_queue,
    score_review_calibration,
    submit_review_annotation,
)
from aec_bench.tui.screens.viewer import render_transcript
from aec_bench.tui.widgets.shared import reward_color


class ReviewScreen(Screen):
    """Three-pane review screen: queue, transcript, annotation/calibration/adjudication form."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "go_back", "Back"),
    ]

    CSS = """
    .review-columns {
        height: 1fr;
        margin: 0 1;
    }

    .review-queue-panel {
        width: 24;
        min-width: 20;
        border: round #40403E;
        padding: 1 1;
        margin: 0 1 0 0;
    }

    .review-transcript-panel {
        width: 2fr;
        border: round #40403E;
        padding: 1 1;
        margin: 0 1 0 0;
    }

    .review-form-panel {
        width: 1fr;
        min-width: 36;
        border: round #40403E;
        padding: 1 1;
        overflow-y: auto;
    }

    .panel-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    .form-section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }

    .review-transcript-scroll {
        height: 1fr;
    }

    #review-status {
        margin-top: 1;
        color: $success;
    }

    Button {
        margin-top: 1;
    }
    """

    def __init__(
        self,
        *,
        ledger_root: Path,
        tasks_root: Path,
        feedback_root: Path,
        reviewer_id: str,
    ) -> None:
        super().__init__()
        self.ledger_root = ledger_root
        self.tasks_root = tasks_root
        self.feedback_root = feedback_root
        self.reviewer_id = reviewer_id
        self.queue_snapshot: ReviewQueueSnapshot | None = None
        self.assignments: list[ReviewAssignment] = []
        self.selected_index: int = 0
        self.current_bundle: ReviewTrialBundle | None = None
        self.calibration_references: dict[str, CalibrationReference] = {}

    def compose(self) -> ComposeResult:
        with Container():
            with Horizontal(classes="review-columns"):
                # Left pane: queue
                with Container(classes="review-queue-panel"):
                    yield Label("Review Queue", classes="panel-title")
                    yield DataTable(id="review-queue-table", cursor_type="row")

                # Centre pane: transcript
                with Container(classes="review-transcript-panel"):
                    yield Label("Trial Transcript", classes="panel-title")
                    yield Static(id="review-trial-summary", markup=True)
                    yield VerticalScroll(
                        Static(id="review-transcript", markup=True),
                        classes="review-transcript-scroll",
                    )

                # Right pane: annotation + calibration + adjudication
                with VerticalScroll(classes="review-form-panel"):
                    # Annotation section
                    yield Label("Annotate", classes="panel-title")
                    yield Static(id="review-handoff", markup=True)
                    yield Select[str](
                        [("Pass", "pass"), ("Fail", "fail"), ("Defer", "defer")],
                        value="pass",
                        id="review-judgment",
                    )
                    yield Input(
                        placeholder="categories, comma separated",
                        id="review-categories",
                    )
                    yield TextArea(id="review-notes")
                    yield Button(
                        "Submit annotation",
                        id="submit-annotation",
                        variant="primary",
                    )

                    # Calibration section
                    yield Label("Calibration", classes="form-section-title")
                    yield Input(
                        placeholder="calibration version",
                        id="review-cal-version",
                    )
                    yield Static(id="review-cal-target")
                    yield Select[str](
                        [("Pass", "pass"), ("Fail", "fail"), ("Defer", "defer")],
                        value="pass",
                        id="review-cal-judgment",
                    )
                    yield Input(
                        placeholder="reference categories, comma separated",
                        id="review-cal-categories",
                    )
                    yield Button(
                        "Add calibration reference",
                        id="add-cal-reference",
                    )
                    yield RichLog(
                        id="review-cal-log",
                        wrap=True,
                        highlight=True,
                    )
                    yield Button(
                        "Score calibration",
                        id="score-calibration",
                    )

                    # Adjudication section
                    yield Label("Adjudication", classes="form-section-title")
                    yield Input(
                        placeholder="decision id",
                        id="review-decision-id",
                    )
                    yield Select[str](
                        [
                            ("Pass", "pass"),
                            ("Fail", "fail"),
                            ("Defer", "defer"),
                            ("Contested", "contested"),
                        ],
                        value="fail",
                        id="review-adj-judgment",
                    )
                    yield TextArea(id="review-adj-rationale")
                    yield Button(
                        "Submit adjudication",
                        id="submit-adjudication",
                    )

                    yield Static(id="review-status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#review-queue-table", DataTable)
        table.add_columns("Trial", "Visibility")
        table.loading = True
        self._load_review_data()

    @work(thread=True, exclusive=True)
    def _load_review_data(self) -> None:
        """Load reviewer queue in background thread to avoid blocking the UI."""
        snapshot = load_review_queue(
            ledger_root=self.ledger_root,
            tasks_root=self.tasks_root,
            feedback_root=self.feedback_root,
            reviewer_id=self.reviewer_id,
        )
        self.app.call_from_thread(self._on_review_data_loaded, snapshot)

    def _on_review_data_loaded(self, snapshot: ReviewQueueSnapshot) -> None:
        """Called on the main thread once background load completes."""
        table = self.query_one("#review-queue-table", DataTable)
        table.loading = False
        self.queue_snapshot = snapshot
        self.assignments = snapshot.assignments
        if self.assignments and self.current_bundle is None:
            self.selected_index = 0
            self._select_trial(self.assignments[0].trial_id)
        elif self.current_bundle is not None:
            self._select_trial(self.current_bundle.trial.trial_id)
        self._refresh_widgets()

    def load_review_state(self) -> None:
        """Reload reviewer queue and refresh widgets synchronously."""
        self.queue_snapshot = load_review_queue(
            ledger_root=self.ledger_root,
            tasks_root=self.tasks_root,
            feedback_root=self.feedback_root,
            reviewer_id=self.reviewer_id,
        )
        self.assignments = self.queue_snapshot.assignments
        if self.assignments and self.current_bundle is None:
            self.selected_index = 0
            self._select_trial(self.assignments[0].trial_id)
        elif self.current_bundle is not None:
            self._select_trial(self.current_bundle.trial.trial_id)

    def _select_trial(self, trial_id: str) -> None:
        self.current_bundle = load_review_bundle(
            ledger_root=self.ledger_root,
            tasks_root=self.tasks_root,
            feedback_root=self.feedback_root,
            reviewer_id=self.reviewer_id,
            trial_id=trial_id,
        )
        for i, a in enumerate(self.assignments):
            if a.trial_id == trial_id:
                self.selected_index = i
                break

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.switch_mode("dashboard")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = getattr(event.button, "id", None)
        if button_id == "submit-annotation":
            self._handle_submit_annotation()
        elif button_id == "add-cal-reference":
            self._handle_add_calibration_reference()
        elif button_id == "score-calibration":
            self._handle_score_calibration()
        elif button_id == "submit-adjudication":
            self._handle_submit_adjudication()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "review-queue-table":
            return
        if event.cursor_row >= len(self.assignments):
            return
        self.selected_index = event.cursor_row
        self._select_trial(self.assignments[event.cursor_row].trial_id)
        self._refresh_widgets()

    # --- Annotation ---

    def _handle_submit_annotation(self) -> None:
        if self.current_bundle is None:
            return
        judgment = self.query_one("#review-judgment", Select).value
        categories = self.query_one("#review-categories", Input).value
        notes = self.query_one("#review-notes", TextArea).text
        if not isinstance(judgment, str):
            self._set_status("Choose a judgment before submitting.")
            return
        annotation = submit_review_annotation(
            ledger_root=self.ledger_root,
            tasks_root=self.tasks_root,
            feedback_root=self.feedback_root,
            reviewer_id=self.reviewer_id,
            trial_id=self.current_bundle.trial.trial_id,
            judgment=Judgment(judgment),
            categories=parse_categories(categories),
            notes=notes.strip() or None,
        )
        self._set_status(f"Saved {annotation.annotation_id}")
        self.notify("Annotation submitted", severity="information")
        self.query_one("#review-categories", Input).value = ""
        self.query_one("#review-notes", TextArea).text = ""
        self.load_review_state()
        self._refresh_widgets()

    # --- Calibration ---

    def _handle_add_calibration_reference(self) -> None:
        if self.current_bundle is None:
            return
        version = self.query_one("#review-cal-version", Input).value.strip()
        judgment = self.query_one("#review-cal-judgment", Select).value
        categories = self.query_one("#review-cal-categories", Input).value
        if not version:
            self._set_status("Enter a calibration version.")
            return
        if not isinstance(judgment, str):
            self._set_status("Choose a calibration reference judgment.")
            return
        reference = CalibrationReference(
            trial_id=self.current_bundle.trial.trial_id,
            reference_judgment=Judgment(judgment),
            reference_categories=parse_categories(categories),
            calibration_version=version,
        )
        self.calibration_references[reference.trial_id] = reference
        self._set_status(f"Staged calibration reference for {reference.trial_id}")
        self.query_one("#review-cal-categories", Input).value = ""
        self._refresh_calibration_log()

    def _handle_score_calibration(self) -> None:
        version = self.query_one("#review-cal-version", Input).value.strip()
        if not version:
            self._set_status("Enter a calibration version.")
            return
        references = {
            tid: ref for tid, ref in self.calibration_references.items() if ref.calibration_version == version
        }
        result, reviewer = score_review_calibration(
            feedback_root=self.feedback_root,
            reviewer_id=self.reviewer_id,
            calibration_version=version,
            references=references,
        )
        self._set_status(
            f"Calibration {result.calibration_version}: "
            f"{result.agreement_rate:.2f} ({reviewer.calibration_status.value})"
        )
        self.load_review_state()
        self._refresh_widgets()

    # --- Adjudication ---

    def _handle_submit_adjudication(self) -> None:
        if self.current_bundle is None:
            return
        decision_id = self.query_one("#review-decision-id", Input).value.strip()
        judgment = self.query_one("#review-adj-judgment", Select).value
        rationale = self.query_one("#review-adj-rationale", TextArea).text
        if not decision_id:
            self._set_status("Enter a decision ID.")
            return
        if not isinstance(judgment, str):
            self._set_status("Choose an adjudication judgment.")
            return
        contested = judgment == "contested"
        final_judgment = None if contested else Judgment(judgment)
        adjudication, _ = adjudicate_review_trial(
            feedback_root=self.feedback_root,
            reviewer_id=self.reviewer_id,
            trial_id=self.current_bundle.trial.trial_id,
            decision_id=decision_id,
            final_judgment=final_judgment,
            rationale=rationale.strip() or None,
            contested=contested,
        )
        self._set_status(f"Adjudication {adjudication.decision_id}: {adjudication.status.value}")
        self.notify("Adjudication submitted", severity="information")
        self.load_review_state()
        self._refresh_widgets()

    # --- Widget refresh ---

    def _set_status(self, message: str) -> None:
        self.query_one("#review-status", Static).update(message)

    def _refresh_widgets(self) -> None:
        self._refresh_queue_table()
        self._refresh_trial_summary()
        self._refresh_transcript()
        self._refresh_handoff()
        self._refresh_calibration_target()
        self._refresh_calibration_log()

    def _refresh_queue_table(self) -> None:
        table = self.query_one("#review-queue-table", DataTable)
        table.clear(columns=False)
        if not self.assignments:
            table.add_row("No assignments", "-")
            return
        for i, assignment in enumerate(self.assignments):
            marker = "> " if i == self.selected_index else "  "
            table.add_row(
                f"{marker}{assignment.trial_id[:18]}",
                assignment.task_visibility.value,
            )

    def _refresh_trial_summary(self) -> None:
        summary = self.query_one("#review-trial-summary", Static)
        if self.current_bundle is None:
            summary.update("[dim]No trial selected.[/dim]")
            return
        trial = self.current_bundle.trial
        reward = trial.evaluation.reward
        r_color = reward_color(reward)
        summary.update(
            f"[bold]Trial:[/bold] {trial.trial_id}\n"
            f"[dim]Task:[/dim] {trial.task.task_id}\n"
            f"[dim]Reward:[/dim] [{r_color}]{reward:.3f}[/]"
        )

    def _refresh_transcript(self) -> None:
        transcript_widget = self.query_one("#review-transcript", Static)
        if self.current_bundle is None:
            transcript_widget.update("[dim]Select a trial to view transcript.[/dim]")
            return
        transcript_widget.update(render_transcript(self.current_bundle.trial))

    def _refresh_handoff(self) -> None:
        handoff_widget = self.query_one("#review-handoff", Static)
        if self.current_bundle is None:
            handoff_widget.update("")
            return
        confidence = self.current_bundle.handoff.confidence
        annotations = self.current_bundle.annotations
        lines = [
            f"[bold]Annotations:[/bold] {len(annotations)}",
        ]
        for ann in annotations:
            categories = ", ".join(ann.categories) or "uncategorised"
            lines.append(f"  {ann.reviewer_id}: {ann.judgment.value} [{categories}]")
        if self.current_bundle.adjudication is not None:
            adj = self.current_bundle.adjudication
            lines.append(f"\n[bold]Adjudication:[/bold] {adj.status.value} ({adj.final_judgment or 'pending'})")
        lines.extend(
            [
                "",
                f"[dim]Agreement: {confidence.inter_rater_agreement}[/dim]",
                f"[dim]Method: {confidence.confidence_method}[/dim]",
            ]
        )
        handoff_widget.update("\n".join(lines))

    def _refresh_calibration_target(self) -> None:
        target = self.query_one("#review-cal-target", Static)
        if self.current_bundle is None:
            target.update("Target: no trial selected")
            return
        target.update(f"Target: {self.current_bundle.trial.trial_id}")

    def _refresh_calibration_log(self) -> None:
        cal_log = self.query_one("#review-cal-log", RichLog)
        cal_log.clear()
        if not self.calibration_references:
            cal_log.write("No staged calibration references")
            return
        for reference in self.calibration_references.values():
            categories = ", ".join(reference.reference_categories) or "uncategorised"
            cal_log.write(
                f"{reference.trial_id}: {reference.reference_judgment.value} "
                f"[{categories}] {reference.calibration_version}"
            )
