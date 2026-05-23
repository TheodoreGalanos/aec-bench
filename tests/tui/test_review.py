# ABOUTME: Tests for the Review screen annotation workflow.
# ABOUTME: Validates queue loading, annotation submission, and async widget rendering.

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import DataTable, Static

from aec_bench.contracts.evaluation_result import Judgment
from aec_bench.contracts.task_definition import Visibility
from aec_bench.feedback.annotation_consumer import write_reviewer_profile
from aec_bench.feedback.review_service import submit_review_annotation
from aec_bench.ledger.writer import write_trial_record
from aec_bench.tui.screens.review import ReviewScreen
from tests.support.feedback_factories import make_reviewer_profile
from tests.support.trial_record_factories import make_trial_record


def _write_task_instance(tasks_root: Path, task_id: str, visibility: Visibility = Visibility.PUBLIC) -> None:
    """Create a minimal task instance on disk matching the task loader's TOML schema."""
    parts = task_id.split("/")
    task_dir = tasks_root.joinpath(*parts)
    (task_dir / "environment").mkdir(parents=True, exist_ok=True)
    (task_dir / "tests").mkdir(parents=True, exist_ok=True)
    (task_dir / "instruction.md").write_text("Write findings to /workspace/output.jsonl.\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        f'[agent]\ntimeout_sec = 600\n\n[metadata]\nvisibility = "{visibility.value}"\n',
        encoding="utf-8",
    )


def _bootstrap_review_env(
    tmp_path: Path,
) -> tuple[Path, Path, Path, str]:
    """Set up ledger, tasks, feedback dirs with a reviewer and trial."""
    ledger_root = tmp_path / "ledger"
    tasks_root = tmp_path / "tasks"
    feedback_root = tmp_path / "feedback"

    task_id = "mechanical/heat-load/public-task"
    _write_task_instance(tasks_root, task_id)

    record = make_trial_record(
        trial_id="trial-001",
        experiment_id="exp-001",
        task={"task_id": task_id, "task_revision": "sha"},
    )
    write_trial_record(ledger_root=ledger_root, record=record)

    reviewer = make_reviewer_profile(
        reviewer_id="theo",
        discipline="mechanical",
    )
    write_reviewer_profile(feedback_root=feedback_root, reviewer=reviewer)

    return ledger_root, tasks_root, feedback_root, "theo"


# ---------------------------------------------------------------------------
# Synchronous state tests
# ---------------------------------------------------------------------------


def test_review_screen_loads_queue(tmp_path: Path) -> None:
    ledger_root, tasks_root, feedback_root, reviewer_id = _bootstrap_review_env(tmp_path)

    screen = ReviewScreen(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id=reviewer_id,
    )
    screen.load_review_state()

    assert len(screen.assignments) == 1
    assert screen.assignments[0].trial_id == "trial-001"


def test_review_screen_reloads_after_annotation(tmp_path: Path) -> None:
    ledger_root, tasks_root, feedback_root, reviewer_id = _bootstrap_review_env(tmp_path)

    screen = ReviewScreen(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id=reviewer_id,
    )
    screen.load_review_state()
    assert screen.current_bundle is not None
    assert len(screen.current_bundle.annotations) == 0

    submit_review_annotation(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id=reviewer_id,
        trial_id="trial-001",
        judgment=Judgment.PASS,
        categories=["verifier.output"],
        notes="Looks correct",
    )

    screen.load_review_state()
    assert len(screen.current_bundle.annotations) == 1


# ---------------------------------------------------------------------------
# Async widget tests
# ---------------------------------------------------------------------------


class ReviewTestApp(App[None]):
    """Minimal App wrapper for testing ReviewScreen."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__()
        self._review_kwargs = kwargs

    def on_mount(self) -> None:
        self.push_screen(ReviewScreen(**self._review_kwargs))


@pytest.mark.anyio
async def test_review_screen_mounts_and_renders_queue(tmp_path: Path) -> None:
    ledger_root, tasks_root, feedback_root, reviewer_id = _bootstrap_review_env(tmp_path)

    app = ReviewTestApp(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id=reviewer_id,
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        queue_table = screen.query_one("#review-queue-table", DataTable)
        assert queue_table.row_count == 1

        summary = screen.query_one("#review-trial-summary", Static)
        assert "trial-001" in str(summary.render())


@pytest.mark.anyio
async def test_review_screen_handles_empty_queue(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    tasks_root = tmp_path / "tasks"
    feedback_root = tmp_path / "feedback"

    reviewer = make_reviewer_profile(reviewer_id="empty-reviewer")
    write_reviewer_profile(feedback_root=feedback_root, reviewer=reviewer)

    app = ReviewTestApp(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id="empty-reviewer",
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        queue_table = screen.query_one("#review-queue-table", DataTable)
        # "No assignments" row
        assert queue_table.row_count == 1
