# ABOUTME: Compatibility entrypoint for terminal feedback review workflows.
# ABOUTME: Launches the unified aec-bench Textual TUI directly into review mode.

from __future__ import annotations

from pathlib import Path

from aec_bench.tui.app import AecBenchTUI


class ReviewTerminalApp(AecBenchTUI):
    """Compatibility wrapper that starts the unified TUI in review mode."""

    def __init__(
        self,
        *,
        ledger_root: Path,
        tasks_root: Path,
        feedback_root: Path,
        reviewer_id: str,
    ) -> None:
        super().__init__(
            ledger_root=ledger_root,
            tasks_root=tasks_root,
            feedback_root=feedback_root,
            reviewer_id=reviewer_id,
            initial_mode="review",
        )

    def on_mount(self) -> None:
        super().on_mount()
        if self.feedback_root is None or self.reviewer_id is None:
            return

        from aec_bench.tui.screens.review import ReviewScreen

        self.push_screen(
            ReviewScreen(
                ledger_root=self.ledger_root,
                tasks_root=self.tasks_root,
                feedback_root=self.feedback_root,
                reviewer_id=self.reviewer_id,
            )
        )
