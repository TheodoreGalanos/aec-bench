# ABOUTME: Tests for the TrialViewerScreen with OptionList, RichLog, and Collapsible widgets.
# ABOUTME: Covers pure function tests and widget smoke tests for the viewer screen.

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import (
    Collapsible,
    OptionList,
    RichLog,
    TabbedContent,
)

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trajectory import TrajectoryEntry
from aec_bench.contracts.trial_record import OutputRecord
from aec_bench.tui.screens.viewer import (
    TrialViewerScreen,
    _group_entries_by_step,
    _StepSummary,
    render_transcript,
)
from tests.support.trial_record_factories import make_trial_record

_VALID = ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True)

_AGENT_OUTPUT = AgentOutput(
    status=AgentOutputStatus.COMPLETED,
    output_path="/workspace/output.md",
    output_format="md",
)


# ---------------------------------------------------------------------------
# Pure function tests: _StepSummary
# ---------------------------------------------------------------------------


def test_step_summary_frozen() -> None:
    summary = _StepSummary(step=0, status="success", total_duration_ms=100, primary_tool="bash")
    assert summary.step == 0
    assert summary.status == "success"
    assert summary.total_duration_ms == 100
    assert summary.primary_tool == "bash"
    assert summary.entries == []


# ---------------------------------------------------------------------------
# Pure function tests: _group_entries_by_step
# ---------------------------------------------------------------------------


def test_group_entries_by_step_empty() -> None:
    assert _group_entries_by_step([]) == []


def test_group_entries_by_step_single_step() -> None:
    entries = [
        TrajectoryEntry(step=1, role="assistant", content="Hello"),
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="ls"),
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", exit_code=0, duration_ms=50),
    ]
    groups = _group_entries_by_step(entries)
    assert len(groups) == 1
    assert groups[0].step == 1
    assert groups[0].status == "success"
    assert groups[0].total_duration_ms == 50
    assert groups[0].primary_tool == "bash"
    assert len(groups[0].entries) == 3


def test_group_entries_by_step_failure_status() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="bad_cmd"),
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="bash",
            exit_code=127,
            duration_ms=10,
        ),
    ]
    groups = _group_entries_by_step(entries)
    assert groups[0].status == "fail"


def test_group_entries_by_step_incomplete() -> None:
    entries = [
        TrajectoryEntry(step=0, role="system", content="You are a helpful agent."),
    ]
    groups = _group_entries_by_step(entries)
    assert groups[0].status == "incomplete"
    assert groups[0].primary_tool == "Init"


def test_group_entries_by_step_multiple_steps() -> None:
    entries = [
        TrajectoryEntry(step=0, role="system", content="system prompt"),
        TrajectoryEntry(step=1, role="assistant", content="thinking"),
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="calc"),
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", exit_code=0, duration_ms=100),
        TrajectoryEntry(step=2, role="tool_call", tool_name="python", command="run"),
        TrajectoryEntry(
            step=2,
            role="tool_result",
            tool_name="python",
            exit_code=1,
            duration_ms=200,
        ),
    ]
    groups = _group_entries_by_step(entries)
    assert len(groups) == 3
    assert groups[0].step == 0
    assert groups[1].step == 1
    assert groups[1].status == "success"
    assert groups[1].primary_tool == "bash"
    assert groups[2].step == 2
    assert groups[2].status == "fail"
    assert groups[2].primary_tool == "python"


# ---------------------------------------------------------------------------
# Pure function tests: _group_entries_by_step call_type and output_summary
# ---------------------------------------------------------------------------


def test_group_entries_by_step_extracts_call_type() -> None:
    entries = [
        TrajectoryEntry(step=1, role="assistant", content="warmup", call_type="warmup"),
        TrajectoryEntry(
            step=1,
            role="tool_call",
            tool_name="bash",
            command="echo hi",
            call_type="warmup",
        ),
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="bash",
            exit_code=0,
            duration_ms=10,
            call_type="warmup",
        ),
    ]
    groups = _group_entries_by_step(entries)
    assert groups[0].call_type == "warmup"


def test_group_entries_by_step_call_type_none_when_absent() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="ls"),
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", exit_code=0, duration_ms=10),
    ]
    groups = _group_entries_by_step(entries)
    assert groups[0].call_type is None


def test_group_entries_by_step_extracts_output_summary() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="cat big.txt"),
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="bash",
            stdout="x" * 500,
            exit_code=0,
            duration_ms=10,
            output_summary="x" * 200 + "\u2026",
        ),
    ]
    groups = _group_entries_by_step(entries)
    assert groups[0].output_summary == "x" * 200 + "\u2026"


def test_group_entries_by_step_output_summary_none_when_absent() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="ls"),
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", stdout="ok", exit_code=0, duration_ms=10),
    ]
    groups = _group_entries_by_step(entries)
    assert groups[0].output_summary is None


# ---------------------------------------------------------------------------
# Pure function tests: render_transcript
# ---------------------------------------------------------------------------


def test_render_transcript_from_trajectory(tmp_path: Path) -> None:
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text(
        '{"version": 1, "format": "aec-bench-trajectory"}\n'
        '{"step": 1, "role": "assistant", "content": "I will calculate."}\n'
        '{"step": 1, "role": "tool_call", "tool_name": "bash", "command": "python3 calc.py"}\n'
        '{"step": 1, "role": "tool_result", "tool_name": "bash",'
        ' "stdout": "result: 42", "exit_code": 0, "duration_ms": 100}\n'
    )

    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=_AGENT_OUTPUT,
            trajectory_path=str(trajectory_path),
        )
    )

    markup = render_transcript(record)
    assert "Step 1" in markup
    assert "assistant" in markup
    assert "bash" in markup
    assert "result: 42" in markup
    assert "exit:0" in markup


def test_render_transcript_shows_errors(tmp_path: Path) -> None:
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text(
        '{"version": 1, "format": "aec-bench-trajectory"}\n'
        '{"step": 1, "role": "tool_call", "tool_name": "bash", "command": "bad_cmd"}\n'
        '{"step": 1, "role": "tool_result", "tool_name": "bash",'
        ' "stdout": "", "stderr": "not found", "exit_code": 127}\n'
    )

    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=_AGENT_OUTPUT,
            trajectory_path=str(trajectory_path),
        )
    )

    markup = render_transcript(record)
    assert "exit:127" in markup
    assert "not found" in markup


def test_render_transcript_empty_trajectory(tmp_path: Path) -> None:
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text('{"version": 1, "format": "aec-bench-trajectory"}\n')

    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=_AGENT_OUTPUT,
            trajectory_path=str(trajectory_path),
        )
    )

    markup = render_transcript(record)
    assert "Empty trajectory" in markup


def test_render_transcript_falls_back_when_no_trajectory() -> None:
    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=_AGENT_OUTPUT,
            conversation_path=None,
            trajectory_path=None,
        )
    )

    markup = render_transcript(record)
    assert "No conversation transcript" in markup


# ---------------------------------------------------------------------------
# Widget tests: TrialViewerScreen
# ---------------------------------------------------------------------------


class ViewerTestApp(App[None]):
    """Minimal App wrapper for testing TrialViewerScreen."""

    def __init__(self, record: object, siblings: object = None) -> None:
        super().__init__()
        self._record = record
        self._siblings = siblings

    def on_mount(self) -> None:
        self.push_screen(TrialViewerScreen(record=self._record, siblings=self._siblings))


@pytest.mark.anyio
async def test_viewer_has_option_list() -> None:
    record = make_trial_record(trial_id="t1")
    app = ViewerTestApp(record=record)

    async with app.run_test() as pilot:
        await pilot.pause()
        option_list = app.screen.query_one("#step-list", OptionList)
        assert option_list is not None


@pytest.mark.anyio
async def test_viewer_has_rich_log() -> None:
    record = make_trial_record(trial_id="t1")
    app = ViewerTestApp(record=record)

    async with app.run_test() as pilot:
        await pilot.pause()
        rich_log = app.screen.query_one("#transcript-log", RichLog)
        assert rich_log is not None


@pytest.mark.anyio
async def test_viewer_has_tabbed_content() -> None:
    record = make_trial_record(trial_id="t1")
    app = ViewerTestApp(record=record)

    async with app.run_test() as pilot:
        await pilot.pause()
        tabbed = app.screen.query_one(TabbedContent)
        assert tabbed is not None


@pytest.mark.anyio
async def test_viewer_has_collapsibles() -> None:
    record = make_trial_record(trial_id="t1")
    app = ViewerTestApp(record=record)

    async with app.run_test() as pilot:
        await pilot.pause()
        collapsibles = app.screen.query(Collapsible)
        assert len(collapsibles) >= 2  # Variables + Scratchpad


@pytest.mark.anyio
async def test_viewer_renders_without_crash() -> None:
    record = make_trial_record(trial_id="t1")
    app = ViewerTestApp(record=record)

    async with app.run_test() as pilot:
        await pilot.pause()
        # Verify the screen mounted and has the expected structure
        assert app.screen is not None
        assert app.screen.query("Header")


@pytest.mark.anyio
async def test_viewer_next_prev_navigation() -> None:
    records = [
        make_trial_record(
            trial_id="t1",
            evaluation=EvaluationResult(reward=1.0, validity=_VALID),
        ),
        make_trial_record(
            trial_id="t2",
            evaluation=EvaluationResult(reward=0.5, validity=_VALID),
        ),
    ]
    app = ViewerTestApp(record=records[0], siblings=records)

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert screen._current_index == 0

        await pilot.press("n")
        await pilot.pause()
        assert screen._current_index == 1
        assert screen._record.trial_id == "t2"


@pytest.mark.anyio
async def test_viewer_back_keybind_exists() -> None:
    """The 'b' key is bound to action_go_back for back navigation."""
    record = make_trial_record(trial_id="t1")
    app = ViewerTestApp(record=record)

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        binding_actions = {b.action for b in screen.BINDINGS}
        assert "go_back" in binding_actions
