# ABOUTME: Tests for TrajectoryEntry Pydantic contract and read_trajectory reader function.
# ABOUTME: Covers entry parsing, validation, version header skipping, and OutputRecord integration.

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.trial_record import OutputRecord
from aec_bench.trajectory.writer import TrajectoryWriter

# ---------------------------------------------------------------------------
# TrajectoryEntry parsing
# ---------------------------------------------------------------------------


def test_parse_assistant_entry() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(
        step=1,
        role="assistant",
        content="I will look up the cable table.",
        timestamp="2026-03-21T10:00:00.000Z",
    )
    assert entry.step == 1
    assert entry.role == "assistant"
    assert entry.content == "I will look up the cable table."
    assert entry.timestamp == "2026-03-21T10:00:00.000Z"


def test_parse_tool_call_entry_all_fields() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(
        step=2,
        role="tool_call",
        tool_name="bash",
        command="run_command",
        arguments={"cmd": "python size_cable.py"},
        timestamp="2026-03-21T10:00:01.000Z",
    )
    assert entry.step == 2
    assert entry.role == "tool_call"
    assert entry.tool_name == "bash"
    assert entry.command == "run_command"
    assert entry.arguments == {"cmd": "python size_cable.py"}


def test_parse_tool_result_entry_with_exit_code_and_duration() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(
        step=2,
        role="tool_result",
        tool_name="bash",
        stdout="4 mm²\n",
        stderr="",
        exit_code=0,
        duration_ms=42,
        timestamp="2026-03-21T10:00:02.000Z",
    )
    assert entry.exit_code == 0
    assert entry.duration_ms == 42
    assert entry.stdout == "4 mm²\n"


def test_parse_tool_result_with_media_list() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(
        step=3,
        role="tool_result",
        tool_name="generate_chart",
        stdout="chart.png",
        stderr="",
        exit_code=0,
        media=["base64img1==", "base64img2=="],
    )
    assert entry.media == ["base64img1==", "base64img2=="]


def test_step_must_be_non_negative() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    with pytest.raises(ValidationError):
        TrajectoryEntry(step=-1, role="assistant")


def test_step_zero_is_valid() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(step=0, role="system", content="You are an engineer.")
    assert entry.step == 0


def test_optional_fields_default_to_none() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(step=1, role="assistant")
    assert entry.content is None
    assert entry.tool_name is None
    assert entry.command is None
    assert entry.arguments is None
    assert entry.stdout is None
    assert entry.stderr is None
    assert entry.exit_code is None
    assert entry.duration_ms is None
    assert entry.media is None
    assert entry.timestamp is None


# ---------------------------------------------------------------------------
# read_trajectory
# ---------------------------------------------------------------------------


def test_read_trajectory_skips_version_header(tmp_path: Path) -> None:
    from aec_bench.contracts.trajectory import read_trajectory

    writer = TrajectoryWriter(str(tmp_path / "trace.jsonl"))
    writer.system("You are an engineer.")
    writer.close()

    entries = read_trajectory(tmp_path / "trace.jsonl")
    # Only the system entry — version header must be skipped
    assert len(entries) == 1
    assert entries[0].role == "system"


def test_read_trajectory_returns_empty_for_missing_file(tmp_path: Path) -> None:
    from aec_bench.contracts.trajectory import read_trajectory

    result = read_trajectory(tmp_path / "does_not_exist.jsonl")
    assert result == []


def test_read_trajectory_returns_empty_for_version_only_file(tmp_path: Path) -> None:
    from aec_bench.contracts.trajectory import read_trajectory

    writer = TrajectoryWriter(str(tmp_path / "trace.jsonl"))
    writer.close()

    entries = read_trajectory(tmp_path / "trace.jsonl")
    assert entries == []


def test_read_trajectory_logs_warning_for_unknown_version(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    import json

    from aec_bench.contracts.trajectory import read_trajectory

    out = tmp_path / "trace.jsonl"
    header = {"version": 99, "format": "aec-bench-trajectory"}
    entry = {"step": 1, "role": "assistant", "content": "hello"}
    out.write_text(
        json.dumps(header) + "\n" + json.dumps(entry) + "\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        entries = read_trajectory(out)

    assert any("version" in record.message.lower() for record in caplog.records)
    assert len(entries) == 1


# ---------------------------------------------------------------------------
# Round-trip: TrajectoryWriter → read_trajectory
# ---------------------------------------------------------------------------


def test_round_trip_writer_to_read_trajectory(tmp_path: Path) -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry, read_trajectory

    out = tmp_path / "trace.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.system("You are an engineer.")
    writer.user("Size the cable for 20 A at 100 m.")
    writer.new_step()
    writer.thinking("I will use the voltage-drop formula.")
    writer.tool_call("bash", "run_command", {"cmd": "python size_cable.py"})
    writer.tool_result("bash", stdout="4 mm²\n", stderr="", exit_code=0, duration_ms=130)
    writer.close()

    entries = read_trajectory(out)

    assert len(entries) == 5
    assert all(isinstance(e, TrajectoryEntry) for e in entries)

    roles = [e.role for e in entries]
    assert roles == ["system", "user", "assistant", "tool_call", "tool_result"]

    # system and user at step 0
    assert entries[0].step == 0
    assert entries[1].step == 0

    # remaining at step 1
    for entry in entries[2:]:
        assert entry.step == 1

    # check tool_result fields specifically
    tr = entries[4]
    assert tr.tool_name == "bash"
    assert tr.stdout == "4 mm²\n"
    assert tr.exit_code == 0
    assert tr.duration_ms == 130


# ---------------------------------------------------------------------------
# OutputRecord.trajectory_path
# ---------------------------------------------------------------------------


def test_output_record_accepts_trajectory_path() -> None:
    record = OutputRecord(trajectory_path="/workspace/trajectory.jsonl")
    assert record.trajectory_path == "/workspace/trajectory.jsonl"


def test_output_record_defaults_trajectory_path_to_none() -> None:
    record = OutputRecord()
    assert record.trajectory_path is None


def test_output_record_trajectory_path_coexists_with_other_fields() -> None:
    from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus

    record = OutputRecord(
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.json",
            output_format="json",
        ),
        raw_output_path="/workspace/output.json",
        conversation_path="/workspace/conversation.jsonl",
        trajectory_path="/workspace/trajectory.jsonl",
    )
    assert record.trajectory_path == "/workspace/trajectory.jsonl"
    assert record.conversation_path == "/workspace/conversation.jsonl"


# ---------------------------------------------------------------------------
# TrajectoryEntry metadata field
# ---------------------------------------------------------------------------


def test_trajectory_entry_accepts_metadata() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(
        step=1,
        role="tool_result",
        tool_name="repl",
        stdout="ok",
        metadata={"var_diff": {"new": ["x"]}, "tokens": {"call_input": 5000}},
    )
    assert entry.metadata is not None
    assert entry.metadata["var_diff"]["new"] == ["x"]


def test_trajectory_entry_metadata_defaults_to_none() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(step=1, role="tool_result", tool_name="repl", stdout="ok")
    assert entry.metadata is None


# ---------------------------------------------------------------------------
# TrajectoryEntry call_type field
# ---------------------------------------------------------------------------


def test_trajectory_entry_accepts_call_type() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(
        step=1,
        role="assistant",
        content="Priming the cache.",
        call_type="warmup",
    )
    assert entry.call_type == "warmup"


def test_trajectory_entry_call_type_defaults_to_none() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(step=1, role="assistant")
    assert entry.call_type is None


def test_read_trajectory_preserves_call_type(tmp_path: Path) -> None:
    import json

    from aec_bench.contracts.trajectory import read_trajectory

    traj = tmp_path / "trajectory.jsonl"
    lines = [
        json.dumps({"version": 1, "format": "aec-bench-trajectory"}),
        json.dumps(
            {
                "role": "assistant",
                "step": 1,
                "content": "warmup",
                "call_type": "warmup",
                "timestamp": "2026-03-30T00:00:00.000Z",
            }
        ),
        json.dumps(
            {
                "role": "assistant",
                "step": 2,
                "content": "real reasoning",
                "call_type": "main",
                "timestamp": "2026-03-30T00:00:01.000Z",
            }
        ),
    ]
    traj.write_text("\n".join(lines))
    entries = read_trajectory(traj)
    assert len(entries) == 2
    assert entries[0].call_type == "warmup"
    assert entries[1].call_type == "main"


# ---------------------------------------------------------------------------
# TrajectoryEntry output_summary field
# ---------------------------------------------------------------------------


def test_trajectory_entry_accepts_output_summary() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(
        step=1,
        role="tool_result",
        tool_name="bash",
        stdout="x" * 5000,
        output_summary="x" * 200 + "…",
    )
    assert entry.output_summary == "x" * 200 + "…"


def test_trajectory_entry_output_summary_defaults_to_none() -> None:
    from aec_bench.contracts.trajectory import TrajectoryEntry

    entry = TrajectoryEntry(step=1, role="tool_result", tool_name="bash", stdout="ok")
    assert entry.output_summary is None


def test_read_trajectory_preserves_output_summary(tmp_path: Path) -> None:
    import json

    from aec_bench.contracts.trajectory import read_trajectory

    traj = tmp_path / "trajectory.jsonl"
    lines = [
        json.dumps({"version": 1, "format": "aec-bench-trajectory"}),
        json.dumps(
            {
                "role": "tool_result",
                "step": 1,
                "tool_name": "bash",
                "stdout": "long output...",
                "output_summary": "long ou…",
                "timestamp": "2026-03-30T00:00:00.000Z",
            }
        ),
    ]
    traj.write_text("\n".join(lines))
    entries = read_trajectory(traj)
    assert len(entries) == 1
    assert entries[0].output_summary == "long ou…"


def test_read_trajectory_preserves_metadata(tmp_path: Path) -> None:
    import json

    from aec_bench.contracts.trajectory import read_trajectory

    traj = tmp_path / "trajectory.jsonl"
    lines = [
        json.dumps({"version": 1, "format": "aec-bench-trajectory"}),
        json.dumps(
            {
                "role": "tool_result",
                "step": 1,
                "tool_name": "repl",
                "stdout": "ok",
                "metadata": {"tokens": {"cost_cumulative": 0.13}},
                "timestamp": "2026-03-27T00:00:00.000Z",
            }
        ),
    ]
    traj.write_text("\n".join(lines))
    entries = read_trajectory(traj)
    assert len(entries) == 1
    assert entries[0].metadata is not None
    assert entries[0].metadata["tokens"]["cost_cumulative"] == 0.13
