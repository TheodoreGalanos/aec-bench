# ABOUTME: Tests trace summary helpers over imported TrialRecord conversations.
# ABOUTME: Verifies real transcript extraction and missing-transcript behavior.

from pathlib import Path

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.trial_record import OutputRecord
from aec_bench.evaluation.trace_summary import (
    extract_trial_trace_signals,
    summarize_trial_trace,
    summarize_trial_traces,
)
from aec_bench.harness.harbor_import import import_harbor_trial
from tests.support.trial_record_factories import make_trial_record

REPO_ROOT = Path(__file__).resolve().parents[2]
HARBOR_TRIAL_DIR = REPO_ROOT / "jobs" / "2026-03-04__17-57-43" / "brisbane-8rm__BHVuXg2"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_TRIAL_DIR.exists(),
    reason="requires archived Harbor job data in jobs/",
)


@_skip_no_job_data
def test_summarize_trial_trace_extracts_real_tool_use_metrics() -> None:
    record = import_harbor_trial(trial_dir=HARBOR_TRIAL_DIR, repo_root=REPO_ROOT)

    summary = summarize_trial_trace(record)

    assert summary["has_transcript"] == 1
    assert summary["assistant_messages"] > 0
    assert summary["tool_call_count"] > 0
    assert summary["bash_tool_call_count"] > 0


def test_summarize_trial_traces_handles_missing_transcripts() -> None:
    record = make_trial_record(
        outputs={
            "agent_output": {
                "status": "completed",
                "output_path": "/workspace/output.jsonl",
                "output_format": "jsonl",
            },
            "raw_output_path": "/workspace/output.jsonl",
            "conversation_path": None,
            "agent_result": {"completion_status": "completed"},
        }
    )

    summary = summarize_trial_traces([record])

    assert summary["n_trials"] == 1
    assert summary["trials_with_transcript"] == 0
    assert summary["mean_tool_call_count"] == 0.0


def test_extract_signals_from_trajectory(tmp_path: Path) -> None:
    """Trajectory-first reading with structured data."""
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text(
        '{"version": 1, "format": "aec-bench-trajectory"}\n'
        '{"step": 0, "role": "system", "content": "prompt"}\n'
        '{"step": 0, "role": "user", "content": "instruction"}\n'
        '{"step": 1, "role": "assistant", "content": "Thinking..."}\n'
        '{"step": 1, "role": "tool_call", "tool_name": "bash", "command": "ls"}\n'
        '{"step": 1, "role": "tool_result", "tool_name": "bash", "stdout": "file.txt", '
        '"exit_code": 0, "duration_ms": 50}\n'
        '{"step": 2, "role": "assistant", "content": "Writing output."}\n'
        '{"step": 2, "role": "tool_call", "tool_name": "bash", "command": "cat > output.md"}\n'
        '{"step": 2, "role": "tool_result", "tool_name": "bash", "stdout": "", "exit_code": 0, "duration_ms": 10}\n'
    )

    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.md",
                output_format="md",
            ),
            conversation_path=None,
            trajectory_path=str(trajectory_path),
        )
    )

    signals = extract_trial_trace_signals(record)
    assert signals["has_transcript"] == 1
    assert signals["assistant_messages"] == 2
    assert signals["tool_call_count"] == 2
    assert signals["bash_tool_call_count"] == 2
    assert signals["tool_errors"] == 0
    assert signals["wrote_output"] is True


def test_extract_signals_trajectory_with_errors(tmp_path: Path) -> None:
    """Tool errors are counted from non-zero exit_code in tool_result entries."""
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text(
        '{"version": 1, "format": "aec-bench-trajectory"}\n'
        '{"step": 1, "role": "tool_call", "tool_name": "bash", "command": "bad_cmd"}\n'
        '{"step": 1, "role": "tool_result", "tool_name": "bash", "stdout": "", '
        '"stderr": "command not found", "exit_code": 127, "duration_ms": 5}\n'
    )

    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.md",
                output_format="md",
            ),
            trajectory_path=str(trajectory_path),
        )
    )

    signals = extract_trial_trace_signals(record)
    assert signals["tool_errors"] == 1
    assert signals["first_error"] is not None
    assert "command not found" in signals["first_error"]


def test_extract_signals_falls_back_to_conversation_when_trajectory_missing(tmp_path: Path) -> None:
    """When trajectory_path is set but file is missing, fall back to conversation."""
    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.md",
                output_format="md",
            ),
            conversation_path=None,
            trajectory_path=str(tmp_path / "nonexistent.jsonl"),
        )
    )

    signals = extract_trial_trace_signals(record)
    # Falls through to conversation fallback, which is also None.
    assert signals["has_transcript"] == 0


def test_extract_signals_skips_warmup_entries(tmp_path: Path) -> None:
    """Warmup entries (call_type=warmup) should be excluded from trace signal counts."""
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text(
        '{"version": 1, "format": "aec-bench-trajectory"}\n'
        '{"step": 1, "role": "assistant", "content": "warmup", "call_type": "warmup"}\n'
        '{"step": 1, "role": "tool_call", "tool_name": "bash", "command": "echo warmup", "call_type": "warmup"}\n'
        '{"step": 1, "role": "tool_result", "tool_name": "bash", "stdout": "warmup", '
        '"exit_code": 0, "call_type": "warmup"}\n'
        '{"step": 2, "role": "assistant", "content": "Thinking..."}\n'
        '{"step": 2, "role": "tool_call", "tool_name": "bash", "command": "ls"}\n'
        '{"step": 2, "role": "tool_result", "tool_name": "bash", "stdout": "file.txt", "exit_code": 0}\n'
    )

    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.md",
                output_format="md",
            ),
            trajectory_path=str(trajectory_path),
        )
    )

    signals = extract_trial_trace_signals(record)
    assert signals["assistant_messages"] == 1  # only non-warmup
    assert signals["tool_call_count"] == 1
    assert signals["bash_tool_call_count"] == 1


def test_extract_signals_partial_trajectory(tmp_path: Path) -> None:
    """Incomplete trajectory (tool_call without tool_result) is handled gracefully."""
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text(
        '{"version": 1, "format": "aec-bench-trajectory"}\n'
        '{"step": 1, "role": "assistant", "content": "Running..."}\n'
        '{"step": 1, "role": "tool_call", "tool_name": "bash", "command": "long_cmd"}\n'
    )

    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.md",
                output_format="md",
            ),
            trajectory_path=str(trajectory_path),
        )
    )

    signals = extract_trial_trace_signals(record)
    assert signals["has_transcript"] == 1
    assert signals["tool_call_count"] == 1
    assert signals["tool_errors"] == 0  # incomplete != error
