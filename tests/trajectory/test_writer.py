# ABOUTME: Tests for TrajectoryWriter — structured JSONL trace recorder for agent execution.
# ABOUTME: Covers header writing, step counting, all entry types, flush behaviour, and timestamps.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.trajectory.writer import TrajectoryWriter


def read_jsonl(path: Path) -> list[dict]:
    """Parse all JSONL lines from the given path."""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


def test_constructor_writes_version_header(tmp_path: Path) -> None:
    out = tmp_path / "trace.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.close()

    entries = read_jsonl(out)
    assert len(entries) >= 1
    header = entries[0]
    assert header["version"] == 1
    assert header["format"] == "aec-bench-trajectory"


# ---------------------------------------------------------------------------
# Step numbering
# ---------------------------------------------------------------------------


def test_new_step_starts_at_one(tmp_path: Path) -> None:
    writer = TrajectoryWriter(str(tmp_path / "t.jsonl"))
    step = writer.new_step()
    writer.close()
    assert step == 1


def test_new_step_increments_sequentially(tmp_path: Path) -> None:
    writer = TrajectoryWriter(str(tmp_path / "t.jsonl"))
    assert writer.new_step() == 1
    assert writer.new_step() == 2
    assert writer.new_step() == 3
    writer.close()


# ---------------------------------------------------------------------------
# system() and user() write at step 0
# ---------------------------------------------------------------------------


def test_system_writes_at_step_zero(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.system("You are a helpful engineer.")
    writer.close()

    entries = read_jsonl(out)
    system_entry = next(e for e in entries if e.get("role") == "system")
    assert system_entry["step"] == 0
    assert system_entry["content"] == "You are a helpful engineer."


def test_user_writes_at_step_zero(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.user("Calculate the cable size.")
    writer.close()

    entries = read_jsonl(out)
    user_entry = next(e for e in entries if e.get("role") == "user")
    assert user_entry["step"] == 0
    assert user_entry["content"] == "Calculate the cable size."


def test_system_and_user_both_write_at_step_zero_before_new_step(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.system("System prompt.")
    writer.user("User prompt.")
    writer.close()

    entries = read_jsonl(out)
    system_entry = next(e for e in entries if e.get("role") == "system")
    user_entry = next(e for e in entries if e.get("role") == "user")
    assert system_entry["step"] == 0
    assert user_entry["step"] == 0


# ---------------------------------------------------------------------------
# thinking()
# ---------------------------------------------------------------------------


def test_thinking_writes_assistant_role_at_current_step(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.thinking("I need to look up the cable table.")
    writer.close()

    entries = read_jsonl(out)
    thinking_entry = next(e for e in entries if e.get("role") == "assistant")
    assert thinking_entry["step"] == 1
    assert thinking_entry["content"] == "I need to look up the cable table."


def test_thinking_at_step_two(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.new_step()
    writer.thinking("Second turn reasoning.")
    writer.close()

    entries = read_jsonl(out)
    thinking_entry = next(e for e in entries if e.get("role") == "assistant")
    assert thinking_entry["step"] == 2


# ---------------------------------------------------------------------------
# tool_call()
# ---------------------------------------------------------------------------


def test_tool_call_writes_correct_fields(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_call("bash", "run_command", {"cmd": "ls /workspace"})
    writer.close()

    entries = read_jsonl(out)
    tc = next(e for e in entries if e.get("role") == "tool_call")
    assert tc["step"] == 1
    assert tc["tool_name"] == "bash"
    assert tc["command"] == "run_command"
    assert tc["arguments"] == {"cmd": "ls /workspace"}


def test_tool_call_without_arguments_omits_field(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_call("bash", "run_command")
    writer.close()

    entries = read_jsonl(out)
    tc = next(e for e in entries if e.get("role") == "tool_call")
    assert "arguments" not in tc


def test_tool_call_at_current_step(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.new_step()
    writer.tool_call("python", "exec", {"code": "print(1)"})
    writer.close()

    entries = read_jsonl(out)
    tc = next(e for e in entries if e.get("role") == "tool_call")
    assert tc["step"] == 2


# ---------------------------------------------------------------------------
# tool_result()
# ---------------------------------------------------------------------------


def test_tool_result_writes_correct_fields(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_result("bash", stdout="file.txt\n", stderr="", exit_code=0, duration_ms=42)
    writer.close()

    entries = read_jsonl(out)
    tr = next(e for e in entries if e.get("role") == "tool_result")
    assert tr["step"] == 1
    assert tr["tool_name"] == "bash"
    assert tr["stdout"] == "file.txt\n"
    assert tr["stderr"] == ""
    assert tr["exit_code"] == 0
    assert tr["duration_ms"] == 42


def test_tool_result_omits_none_fields(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_result("bash", stdout="ok")
    writer.close()

    entries = read_jsonl(out)
    tr = next(e for e in entries if e.get("role") == "tool_result")
    assert "duration_ms" not in tr
    assert "media" not in tr


def test_tool_result_with_media_list(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_result(
        "generate_chart",
        stdout="chart.png",
        media=["base64encodedpng==", "base64encodedpng2=="],
    )
    writer.close()

    entries = read_jsonl(out)
    tr = next(e for e in entries if e.get("role") == "tool_result")
    assert tr["media"] == ["base64encodedpng==", "base64encodedpng2=="]


# ---------------------------------------------------------------------------
# Full turn sequence
# ---------------------------------------------------------------------------


def test_full_turn_sequence_ordering(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.system("You are an engineer.")
    writer.user("Size the cable for 20 A at 100 m.")
    writer.new_step()
    writer.thinking("I will use the voltage-drop formula.")
    writer.tool_call("bash", "run_command", {"cmd": "python size_cable.py"})
    writer.tool_result("bash", stdout="4 mm²\n", exit_code=0, duration_ms=130)
    writer.close()

    entries = read_jsonl(out)
    roles = [e.get("role") for e in entries]

    # header has no role; the rest should follow in order
    assert entries[0]["format"] == "aec-bench-trajectory"
    assert roles[1] == "system"
    assert roles[2] == "user"
    assert roles[3] == "assistant"
    assert roles[4] == "tool_call"
    assert roles[5] == "tool_result"

    # step values
    assert entries[1]["step"] == 0
    assert entries[2]["step"] == 0
    assert entries[3]["step"] == 1
    assert entries[4]["step"] == 1
    assert entries[5]["step"] == 1


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def test_all_entries_have_utc_iso8601_z_timestamp(tmp_path: Path) -> None:
    import re

    iso_z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.system("sys")
    writer.user("usr")
    writer.new_step()
    writer.thinking("think")
    writer.tool_call("bash", "cmd")
    writer.tool_result("bash", stdout="out")
    writer.close()

    entries = read_jsonl(out)
    for entry in entries:
        assert "timestamp" in entry, f"Missing timestamp in {entry}"
        assert iso_z.match(entry["timestamp"]), f"Bad timestamp format: {entry['timestamp']}"


# ---------------------------------------------------------------------------
# Flush on every write (crash resilience)
# ---------------------------------------------------------------------------


def test_data_readable_before_close(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.system("Hello")

    # Read without closing the writer
    entries = read_jsonl(out)
    system_entry = next((e for e in entries if e.get("role") == "system"), None)
    assert system_entry is not None, "system entry should be readable before close()"
    writer.close()


def test_multiple_writes_flushed_before_close(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.system("sys")
    writer.user("usr")
    writer.new_step()
    writer.thinking("think")

    # Read without closing
    entries = read_jsonl(out)
    roles = [e.get("role") for e in entries]
    assert "system" in roles
    assert "user" in roles
    assert "assistant" in roles
    writer.close()


# ---------------------------------------------------------------------------
# tool_result() metadata parameter
# ---------------------------------------------------------------------------


def test_tool_result_with_metadata(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_result(
        "repl",
        stdout="OK: Section 'background' filled",
        metadata={
            "var_diff": {"new": ["result"], "removed": []},
            "tokens": {"call_input": 11096, "cost_cumulative": 0.13},
        },
    )
    writer.close()

    entries = read_jsonl(out)
    tr = next(e for e in entries if e.get("role") == "tool_result")
    assert tr["metadata"]["var_diff"]["new"] == ["result"]
    assert tr["metadata"]["tokens"]["call_input"] == 11096


# ---------------------------------------------------------------------------
# system() deduplication
# ---------------------------------------------------------------------------


def test_duplicate_system_prompt_is_skipped(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.system("You are a helpful engineer.")
    writer.system("You are a helpful engineer.")  # duplicate
    writer.close()

    entries = read_jsonl(out)
    system_entries = [e for e in entries if e.get("role") == "system"]
    assert len(system_entries) == 1


def test_different_system_prompt_is_written(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.system("You are a helpful engineer.")
    writer.system("You are a senior electrical engineer.")  # different
    writer.close()

    entries = read_jsonl(out)
    system_entries = [e for e in entries if e.get("role") == "system"]
    assert len(system_entries) == 2
    assert system_entries[0]["content"] == "You are a helpful engineer."
    assert system_entries[1]["content"] == "You are a senior electrical engineer."


# ---------------------------------------------------------------------------
# new_step() call_type parameter
# ---------------------------------------------------------------------------


def test_new_step_with_call_type_tags_entries(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step(call_type="warmup")
    writer.thinking("Cache priming.")
    writer.tool_call("bash", "echo hi")
    writer.tool_result("bash", stdout="hi")
    writer.close()

    entries = read_jsonl(out)
    for entry in entries:
        if entry.get("role") in ("assistant", "tool_call", "tool_result"):
            assert entry["call_type"] == "warmup"


def test_new_step_without_call_type_omits_field(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.thinking("Normal reasoning.")
    writer.close()

    entries = read_jsonl(out)
    assistant = next(e for e in entries if e.get("role") == "assistant")
    assert "call_type" not in assistant


def test_call_type_resets_between_steps(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step(call_type="warmup")
    writer.thinking("Warmup thinking.")
    writer.new_step()  # no call_type
    writer.thinking("Normal thinking.")
    writer.close()

    entries = read_jsonl(out)
    assistants = [e for e in entries if e.get("role") == "assistant"]
    assert assistants[0]["call_type"] == "warmup"
    assert "call_type" not in assistants[1]


def test_system_dedup_across_many_calls(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    prompt = "You are an engineer."
    for _ in range(10):
        writer.system(prompt)
    writer.close()

    entries = read_jsonl(out)
    system_entries = [e for e in entries if e.get("role") == "system"]
    assert len(system_entries) == 1


# ---------------------------------------------------------------------------
# tool_result() metadata parameter
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# tool_result() output_summary auto-generation
# ---------------------------------------------------------------------------


def test_tool_result_auto_generates_output_summary_for_long_stdout(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    long_output = "x" * 500
    writer.tool_result("bash", stdout=long_output)
    writer.close()

    entries = read_jsonl(out)
    tr = next(e for e in entries if e.get("role") == "tool_result")
    assert tr["output_summary"] == "x" * 200 + "…"
    assert tr["stdout"] == long_output  # full output still present


def test_tool_result_omits_output_summary_for_short_stdout(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_result("bash", stdout="short output")
    writer.close()

    entries = read_jsonl(out)
    tr = next(e for e in entries if e.get("role") == "tool_result")
    assert "output_summary" not in tr


def test_tool_result_explicit_output_summary_overrides_auto(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_result("bash", stdout="x" * 500, output_summary="custom preview")
    writer.close()

    entries = read_jsonl(out)
    tr = next(e for e in entries if e.get("role") == "tool_result")
    assert tr["output_summary"] == "custom preview"


def test_tool_result_empty_stdout_no_output_summary(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_result("bash", stdout="")
    writer.close()

    entries = read_jsonl(out)
    tr = next(e for e in entries if e.get("role") == "tool_result")
    assert "output_summary" not in tr


# ---------------------------------------------------------------------------
# tool_result() metadata parameter
# ---------------------------------------------------------------------------


def test_tool_result_without_metadata_omits_field(tmp_path: Path) -> None:
    out = tmp_path / "t.jsonl"
    writer = TrajectoryWriter(str(out))
    writer.new_step()
    writer.tool_result("bash", stdout="ok")
    writer.close()

    entries = read_jsonl(out)
    tr = next(e for e in entries if e.get("role") == "tool_result")
    assert "metadata" not in tr
