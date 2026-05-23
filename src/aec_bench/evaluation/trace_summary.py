# ABOUTME: Deterministic trace metrics over imported TrialRecord conversations.
# ABOUTME: Extracts tool-use and transcript-structure signals from ledger artifacts.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from aec_bench.config import resolve_artifact_path
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.stats import mean as _mean

_TOOL_ERROR_PATTERNS = (
    "Syntax error",
    "Error:",
    "Traceback (most recent",
    "command not found",
    "No such file or directory",
    "Permission denied",
)


class TrialTraceSignals(TypedDict):
    has_transcript: int
    total_messages: int
    assistant_messages: int
    tool_result_messages: int
    tool_call_count: int
    bash_tool_call_count: int
    tool_errors: int
    used_calc_tool: bool
    wrote_output: bool
    first_error: str | None


def summarize_trial_trace(record: TrialRecord) -> dict[str, int]:
    signals = extract_trial_trace_signals(record)
    return {
        "has_transcript": signals["has_transcript"],
        "total_messages": signals["total_messages"],
        "assistant_messages": signals["assistant_messages"],
        "tool_result_messages": signals["tool_result_messages"],
        "tool_call_count": signals["tool_call_count"],
        "bash_tool_call_count": signals["bash_tool_call_count"],
    }


def extract_trial_trace_signals(record: TrialRecord) -> TrialTraceSignals:
    # Try trajectory first (structured format)
    trajectory_path = record.outputs.trajectory_path
    if trajectory_path is not None:
        path = resolve_artifact_path(trajectory_path)
        if path is not None:
            return _extract_from_trajectory(path)

    conversation_path = record.outputs.conversation_path
    if conversation_path is None:
        return _empty_trace_summary(has_transcript=0)

    path = resolve_artifact_path(conversation_path)
    if path is None:
        return _empty_trace_summary(has_transcript=0)

    assistant_messages = 0
    tool_result_messages = 0
    tool_call_count = 0
    bash_tool_call_count = 0
    total_messages = 0
    tool_errors = 0
    used_calc_tool = False
    wrote_output = False
    first_error: str | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            continue
        total_messages += 1
        role = payload.get("role")
        if role == "assistant":
            assistant_messages += 1
            tool_calls, bash_calls = _assistant_tool_counts(payload)
            tool_call_count += tool_calls
            bash_tool_call_count += bash_calls
            commands = _assistant_commands(payload)
            if any("heat_load_calc.py" in command for command in commands):
                used_calc_tool = True
            if any(_writes_output(command) for command in commands):
                wrote_output = True
        elif role in {"tool", "user"}:
            tool_result_messages += _tool_result_count(payload)
            content = _tool_result_content(payload)
            if content and _is_tool_error(content):
                tool_errors += 1
                if first_error is None:
                    first_error = content[:200]

    return {
        "has_transcript": 1,
        "total_messages": total_messages,
        "assistant_messages": assistant_messages,
        "tool_result_messages": tool_result_messages,
        "tool_call_count": tool_call_count,
        "bash_tool_call_count": bash_tool_call_count,
        "tool_errors": tool_errors,
        "used_calc_tool": used_calc_tool,
        "wrote_output": wrote_output,
        "first_error": first_error,
    }


def summarize_trial_traces(records: list[TrialRecord]) -> dict[str, float | int]:
    summaries = [summarize_trial_trace(record) for record in records]
    n_trials = len(summaries)
    if n_trials == 0:
        return {
            "n_trials": 0,
            "trials_with_transcript": 0,
            "mean_assistant_messages": 0.0,
            "mean_tool_call_count": 0.0,
            "mean_bash_tool_call_count": 0.0,
        }

    return {
        "n_trials": n_trials,
        "trials_with_transcript": sum(item["has_transcript"] for item in summaries),
        "mean_assistant_messages": _mean(item["assistant_messages"] for item in summaries),
        "mean_tool_call_count": _mean(item["tool_call_count"] for item in summaries),
        "mean_bash_tool_call_count": _mean(item["bash_tool_call_count"] for item in summaries),
    }


def _assistant_tool_counts(payload: dict[str, Any]) -> tuple[int, int]:
    content = payload.get("content")
    if isinstance(content, list):
        tool_uses = [block for block in content if isinstance(block, dict) and block.get("type") == "tool_use"]
        bash_calls = sum(1 for block in tool_uses if block.get("name") == "bash")
        return len(tool_uses), bash_calls

    tool_calls = payload.get("tool_calls")
    if isinstance(tool_calls, list):
        bash_calls = 0
        total_calls = 0
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            total_calls += 1
            function_payload = tool_call.get("function", {})
            if isinstance(function_payload, dict) and function_payload.get("name") == "bash":
                bash_calls += 1
        return total_calls, bash_calls

    return 0, 0


def _assistant_commands(payload: dict[str, Any]) -> list[str]:
    content = payload.get("content")
    if isinstance(content, list):
        commands: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            tool_input = block.get("input", {})
            if not isinstance(tool_input, dict):
                continue
            command = tool_input.get("command")
            if isinstance(command, str) and command:
                commands.append(command)
        return commands

    tool_calls = payload.get("tool_calls")
    if isinstance(tool_calls, list):
        commands = []
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function_payload = tool_call.get("function", {})
            if not isinstance(function_payload, dict):
                continue
            if function_payload.get("name") != "bash":
                continue
            arguments = function_payload.get("arguments", "{}")
            if not isinstance(arguments, str):
                continue
            try:
                parsed_arguments = json.loads(arguments)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed_arguments, dict):
                continue
            command = parsed_arguments.get("command")
            if isinstance(command, str) and command:
                commands.append(command)
        return commands

    return []


def _tool_result_count(payload: dict[str, Any]) -> int:
    content = payload.get("content")
    if isinstance(content, list):
        return sum(1 for block in content if isinstance(block, dict) and block.get("type") == "tool_result")
    if payload.get("role") == "tool":
        return 1
    return 0


def _tool_result_content(payload: dict[str, Any]) -> str:
    if payload.get("role") == "tool":
        content = payload.get("content")
        return content if isinstance(content, str) else ""

    content = payload.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            inner_content = block.get("content", "")
            if isinstance(inner_content, str):
                return inner_content
            if isinstance(inner_content, list):
                return " ".join(part.get("text", "") for part in inner_content if isinstance(part, dict))
    return ""


def _is_tool_error(content: str) -> bool:
    if "[exit code: " in content and "[exit code: 0]" not in content:
        return True
    return any(pattern in content for pattern in _TOOL_ERROR_PATTERNS)


def _writes_output(command: str) -> bool:
    return "output.md" in command or "output.jsonl" in command


def _extract_from_trajectory(path: Path) -> TrialTraceSignals:
    """Extract trace signals from a structured trajectory JSONL file."""
    from aec_bench.contracts.trajectory import read_trajectory

    all_entries = read_trajectory(path)
    if not all_entries:
        return _empty_trace_summary(has_transcript=0)

    # Exclude warmup entries from analysis — they are cache priming, not reasoning
    entries = [e for e in all_entries if e.call_type != "warmup"]

    assistant_messages = 0
    tool_call_count = 0
    bash_tool_call_count = 0
    tool_errors = 0
    used_calc_tool = False
    wrote_output = False
    first_error: str | None = None

    for entry in entries:
        if entry.role == "assistant":
            assistant_messages += 1
        elif entry.role == "tool_call":
            tool_call_count += 1
            if entry.tool_name == "bash":
                bash_tool_call_count += 1
            if entry.tool_name is not None and "calc" in entry.tool_name:
                used_calc_tool = True
            if entry.command is not None and _writes_output(entry.command):
                wrote_output = True
        elif entry.role == "tool_result":
            if entry.exit_code is not None and entry.exit_code != 0:
                tool_errors += 1
                if first_error is None:
                    error_text = entry.stderr or entry.stdout or ""
                    first_error = error_text[:200] if error_text else None

    return {
        "has_transcript": 1,
        "total_messages": len(entries),
        "assistant_messages": assistant_messages,
        "tool_result_messages": sum(1 for e in entries if e.role == "tool_result"),
        "tool_call_count": tool_call_count,
        "bash_tool_call_count": bash_tool_call_count,
        "tool_errors": tool_errors,
        "used_calc_tool": used_calc_tool,
        "wrote_output": wrote_output,
        "first_error": first_error,
    }


def _empty_trace_summary(*, has_transcript: int) -> TrialTraceSignals:
    return {
        "has_transcript": has_transcript,
        "total_messages": 0,
        "assistant_messages": 0,
        "tool_result_messages": 0,
        "tool_call_count": 0,
        "bash_tool_call_count": 0,
        "tool_errors": 0,
        "used_calc_tool": False,
        "wrote_output": False,
        "first_error": None,
    }
