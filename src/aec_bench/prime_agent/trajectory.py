# ABOUTME: Converts preserved Prime sessions into the shared AEC-Bench trajectory format.
# ABOUTME: Uses explicit session ancestry and keeps unknown parent tool-call relationships absent.

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from aec_bench.contracts.trajectory import (
    TrajectoryEntry,
    TrajectoryModelResponse,
    TrajectoryReasoning,
    TrajectoryUsage,
)
from aec_bench.prime_agent.session_evidence import PrimeSessionEvidenceError, _session_events
from aec_bench.trajectory.writer import TrajectoryWriter

logger = logging.getLogger(__name__)


def write_prime_trajectory(session_directory: Path, destination: Path) -> None:
    """Publish a derived trace after redaction, without changing the Prime run outcome."""
    try:
        entries = prime_session_trajectory(session_directory)
        if not entries:
            return
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".jsonl", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            writer = TrajectoryWriter(str(temporary_path))
            try:
                for entry in entries:
                    writer.append_entry(entry.model_dump(mode="json", exclude_none=True))
            finally:
                writer.close()
            os.replace(temporary_path, destination)
        finally:
            temporary_path.unlink(missing_ok=True)
    except (OSError, ValueError, RecursionError) as exc:
        logger.warning("Prime trajectory export failed (%s); raw session evidence is retained", type(exc).__name__)


def prime_session_trajectory(session_directory: Path) -> list[TrajectoryEntry]:
    """Read one session tree. Never follow parent paths outside the supplied files."""
    directory = session_directory.resolve()
    sessions: dict[Path, tuple[dict[str, Any], list[TrajectoryEntry]]] = {}
    identities: set[str] = set()
    for path in sorted(directory.rglob("*.jsonl")):
        if not path.is_file() or not path.resolve().is_relative_to(directory):
            raise PrimeSessionEvidenceError("Prime session artifact is outside its session directory")
        events = _session_events(path, allow_partial=False)
        header = events[0]
        identity = header.get("id")
        if (
            header.get("type") != "session"
            or header.get("version") != 3
            or not isinstance(identity, str)
            or not identity
        ):
            raise PrimeSessionEvidenceError("Prime trajectory requires a version 3 session header with an id")
        if identity in identities:
            raise PrimeSessionEvidenceError("Prime trajectory has duplicate session ids")
        depth = header.get("rlmDepth", 0)
        if type(depth) is not int or depth < 0 or (not header.get("parentSession") and depth != 0):
            raise PrimeSessionEvidenceError("Prime trajectory has invalid recursion depth")
        identities.add(identity)
        sessions[path.resolve()] = (header, _message_entries(events))
    if not sessions:
        return []
    roots = [path for path, (header, _) in sessions.items() if not header.get("parentSession")]
    if len(roots) != 1:
        raise PrimeSessionEvidenceError("Prime trajectory requires exactly one root session")
    children: dict[Path, list[Path]] = {path: [] for path in sessions}
    parent_calls: dict[Path, str] = {}
    for path, (header, _) in sessions.items():
        parent_value = header.get("parentSession")
        if not parent_value:
            continue
        if not isinstance(parent_value, str) or not Path(parent_value).is_absolute():
            raise PrimeSessionEvidenceError("Prime child session requires an absolute parent session reference")
        parent = Path(parent_value).resolve()
        if parent not in sessions:
            raise PrimeSessionEvidenceError("Prime child references an absent parent session")
        depth = header.get("rlmDepth")
        parent_depth = sessions[parent][0].get("rlmDepth", 0)
        if type(depth) is not int or type(parent_depth) is not int or depth != parent_depth + 1:
            raise PrimeSessionEvidenceError("Prime session ancestry is not an RLM child relationship")
        call_id = _spawn_call(path, sessions[parent][0], sessions[parent][1])
        if call_id is not None:
            parent_calls[path] = call_id
        children[parent].append(path)

    visited: set[Path] = set()

    def collect(path: Path) -> list[TrajectoryEntry]:
        if path in visited:
            raise PrimeSessionEvidenceError("Prime session ancestry contains a cycle")
        visited.add(path)
        header, messages = sessions[path]
        entries = [
            TrajectoryEntry(
                step=0,
                role="session",
                timestamp=header.get("timestamp"),
                metadata={
                    "source": "prime_session",
                    "session_id": header["id"],
                    "rlm_depth": header.get("rlmDepth", 0),
                },
            ),
            *messages,
        ]
        for child_path in children[path]:
            child_header, child_messages = sessions[child_path]
            model = next((e.model_response.model_name for e in child_messages if e.model_response is not None), None)
            for child_entry in collect(child_path):
                entries.append(
                    TrajectoryEntry.model_validate(
                        {
                            "step": 0,
                            "role": "subagent",
                            "timestamp": child_entry.timestamp,
                            "subagent": {
                                "trajectory_id": child_header["id"],
                                "agent_name": "prime-agent",
                                "model_name": model,
                                "parent_tool_call_id": parent_calls.get(child_path),
                                "entry": child_entry,
                            },
                        }
                    )
                )
        return entries

    entries = collect(roots[0])
    if len(visited) != len(sessions):
        raise PrimeSessionEvidenceError("Prime session ancestry contains disconnected sessions")
    return entries


def _spawn_call(path: Path, parent: dict[str, Any], entries: list[TrajectoryEntry]) -> str | None:
    evidence = path.parent / "aec-spawn.json"
    if evidence.is_symlink():
        raise PrimeSessionEvidenceError("Prime spawn evidence must not be a symbolic link")
    if not evidence.exists():
        return None
    data = json.loads(evidence.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or set(data) != {"parent_session_id", "parent_tool_call_id", "rlm_child_id"}
        or any(not isinstance(value, str) or not value for value in data.values())
        or data["parent_session_id"] != parent["id"]
        or data["rlm_child_id"] != path.parent.name
    ):
        raise PrimeSessionEvidenceError("Prime spawn evidence does not match session ancestry")
    calls = [
        entry for entry in entries if entry.role == "tool_call" and entry.tool_call_id == data["parent_tool_call_id"]
    ]
    if len(calls) != 1 or calls[0].tool_name != "ipython":
        raise PrimeSessionEvidenceError("Prime spawn evidence does not identify one parent ipython call")
    return str(data["parent_tool_call_id"])


def _message_entries(events: list[dict[str, Any]]) -> list[TrajectoryEntry]:
    entries: list[TrajectoryEntry] = []
    step = 0
    for event in events[1:]:
        message = event.get("message")
        if event.get("type") != "message" or not isinstance(message, dict):
            continue
        role = message.get("role")
        if role == "assistant":
            step += 1
        context: dict[str, Any] = {"step": step, "timestamp": event.get("timestamp")}
        content = message.get("content", [])
        blocks: list[dict[str, Any]] = [{"type": "text", "text": content}] if isinstance(content, str) else content
        if not isinstance(blocks, list) or any(not isinstance(block, dict) for block in blocks):
            raise PrimeSessionEvidenceError("Prime message content is not a supported block list")
        text = "\n".join(
            block["text"] for block in blocks if block.get("type") == "text" and isinstance(block.get("text"), str)
        )
        if role in {"system", "user"}:
            entries.append(TrajectoryEntry(**context, role=role, content=text))
        elif role == "toolResult":
            entries.append(
                TrajectoryEntry(
                    **context,
                    role="tool_result",
                    tool_name=message.get("toolName"),
                    tool_call_id=message.get("toolCallId"),
                    stdout=text,
                    metadata={"is_error": message.get("isError", False)},
                )
            )
        elif role == "assistant":
            usage = message.get("usage")
            counts: dict[str, int] = {}
            if isinstance(usage, dict):
                for name in ("input", "output", "cacheRead", "cacheWrite"):
                    value = usage.get(name)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        counts[name] = value
            entries.append(
                TrajectoryEntry(
                    **context,
                    role="model_response",
                    model_response=TrajectoryModelResponse(
                        source="prime_session",
                        model_name=message.get("responseModel") or message.get("model"),
                        provider_name=message.get("provider"),
                        response_id=message.get("responseId"),
                        usage=TrajectoryUsage(
                            input_tokens=sum(counts[name] for name in ("input", "cacheRead", "cacheWrite"))
                            if all(name in counts for name in ("input", "cacheRead", "cacheWrite"))
                            else None,
                            output_tokens=counts.get("output"),
                            cache_read_tokens=counts.get("cacheRead"),
                            cache_write_tokens=counts.get("cacheWrite"),
                        )
                        if counts
                        else None,
                    ),
                )
            )
            for block in blocks:
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    entries.append(TrajectoryEntry(**context, role="assistant", content=block["text"]))
                elif block.get("type") == "thinking" and isinstance(block.get("thinking"), str):
                    entries.append(
                        TrajectoryEntry(
                            **context,
                            role="reasoning",
                            reasoning=TrajectoryReasoning(
                                content=block["thinking"],
                                provider_name=message.get("provider"),
                                has_signature=bool(block.get("thinkingSignature")),
                            ),
                        )
                    )
                elif block.get("type") == "toolCall":
                    entries.append(
                        TrajectoryEntry(
                            **context,
                            role="tool_call",
                            tool_name=block.get("name"),
                            tool_call_id=block.get("id"),
                            arguments=block.get("arguments"),
                        )
                    )
            if message.get("stopReason") in {"error", "aborted"}:
                entries.append(
                    TrajectoryEntry(
                        **context, role="error", content=message.get("errorMessage") or message["stopReason"]
                    )
                )
    return entries
