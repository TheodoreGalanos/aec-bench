# ABOUTME: Tests the feedback terminal compatibility entrypoint.
# ABOUTME: Verifies it now launches the unified Textual TUI review surface.

from pathlib import Path

import pytest
from textual.widgets import DataTable

from aec_bench.contracts.task_definition import Visibility
from aec_bench.feedback.annotation_consumer import write_reviewer_profile
from aec_bench.feedback.textual_app import ReviewTerminalApp
from aec_bench.ledger.writer import write_trial_record
from aec_bench.tui.app import AecBenchTUI
from aec_bench.tui.screens.review import ReviewScreen
from tests.support.feedback_factories import make_reviewer_profile
from tests.support.trial_record_factories import make_trial_record


@pytest.mark.anyio
async def test_review_terminal_app_launches_unified_review_surface(tmp_path: Path) -> None:
    ledger_root, tasks_root, feedback_root, reviewer_id = _bootstrap_review_env(tmp_path)
    app = ReviewTerminalApp(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        feedback_root=feedback_root,
        reviewer_id=reviewer_id,
    )

    assert isinstance(app, AecBenchTUI)

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.current_mode == "review"
        assert isinstance(app.screen, ReviewScreen)
        queue_table = app.screen.query_one("#review-queue-table", DataTable)
        assert queue_table.row_count == 1


def _bootstrap_review_env(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    tasks_root = tmp_path / "tasks"
    feedback_root = tmp_path / "feedback"
    ledger_root = tmp_path / "ledger"
    task_id = "mechanical/heat-load/public-task"

    _write_task_instance(tasks_root=tasks_root, relative_path=task_id, visibility=Visibility.PUBLIC)
    write_trial_record(
        ledger_root=ledger_root,
        record=make_trial_record(
            trial_id="trial-public",
            task={"task_id": task_id, "task_revision": "git"},
        ),
    )
    write_reviewer_profile(
        feedback_root=feedback_root,
        reviewer=make_reviewer_profile(reviewer_id="reviewer-public"),
    )
    return ledger_root, tasks_root, feedback_root, "reviewer-public"


def _write_task_instance(
    *,
    tasks_root: Path,
    relative_path: str,
    visibility: Visibility,
) -> None:
    task_dir = tasks_root / relative_path
    (task_dir / "environment").mkdir(parents=True, exist_ok=True)
    (task_dir / "tests").mkdir(parents=True, exist_ok=True)
    (task_dir / "instruction.md").write_text("Write findings to /workspace/output.jsonl.\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        f'[agent]\ntimeout_sec = 600\n\n[metadata]\nvisibility = "{visibility.value}"\n',
        encoding="utf-8",
    )
