# ABOUTME: Projects captured DeepSeek session trees into the shared trajectory contract.
# ABOUTME: Preserves explicit spawn links, observed reasoning and usage, and failed child outcomes.

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from aec_bench.adapters.deepseek_harness.events import (
    _event_datetime,
    _text_content,
    notification_envelope_parts,
)
from aec_bench.contracts.trajectory import (
    MetaHarnessTrajectoryContext,
    TrajectoryEntry,
    TrajectoryModelResponse,
    TrajectoryReasoning,
    TrajectorySubagentEntry,
    TrajectoryUsage,
)

logger = logging.getLogger(__name__)


def write_deepseek_trajectory(
    root_session_id: str,
    notifications: list[dict[str, Any]],
    destination: Path,
    *,
    meta_harness: MetaHarnessTrajectoryContext | None = None,
) -> None:
    """Publish after redaction; a derived export failure does not replace the agent outcome."""
    try:
        entries = deepseek_trajectory(root_session_id, notifications)
        with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent, suffix=".jsonl", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                for entry in entries:
                    entry = entry.model_copy(update={"meta_harness": meta_harness})
                    stream.write(entry.model_dump_json(exclude_none=True) + "\n")
                stream.close()
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
    except (OSError, ValueError, RecursionError) as exc:
        logger.warning("DeepSeek trajectory export failed (%s); raw notifications are retained", type(exc).__name__)


def deepseek_trajectory(root_session_id: str, notifications: list[dict[str, Any]]) -> list[TrajectoryEntry]:
    """Use SDK lineage and hook call IDs; never infer ancestry from timestamps or message text."""
    parents: dict[str, str] = {}
    spawns: dict[str, tuple[str, str]] = {}
    calls: dict[tuple[str, str], tuple[str, int]] = {}
    records: list[tuple[str, TrajectoryEntry]] = [
        (root_session_id, _session_entry(root_session_id)),
    ]
    steps: dict[str, int] = {}
    for notification in notifications:
        envelope = notification_envelope_parts(notification)
        if envelope is None:
            continue
        method, payload = envelope
        if method == "subagent.started":
            child, parent = payload.get("childSessionId"), payload.get("parentSessionId")
            if not isinstance(child, str) or not child or not isinstance(parent, str) or not parent:
                raise ValueError("DeepSeek child lineage requires session IDs")
            if child == root_session_id or child in parents:
                raise ValueError("DeepSeek child session has duplicate or root identity")
            parents[child] = parent
            records.append((child, _session_entry(child)))
        if method != "session.event":
            continue
        session_id, event = payload.get("sessionId"), payload.get("event")
        if not isinstance(session_id, str) or not isinstance(event, dict):
            raise ValueError("DeepSeek session event requires an identity and event object")
        data = event.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("DeepSeek event data must be an object")
        kind = event.get("type")
        if kind == "step/start":
            steps[session_id] = steps.get(session_id, 0) + 1
        step = steps.get(session_id, 0)
        if kind == "aec/subagent-spawn":
            child, call = data.get("child_session_id"), data.get("parent_tool_call_id")
            if not isinstance(child, str) or not child or not isinstance(call, str) or not call or child in spawns:
                raise ValueError("DeepSeek spawn event requires unique child and parent call IDs")
            spawns[child] = session_id, call
        if kind == "tool/call":
            call_id, name = data.get("callId"), data.get("name")
            if not isinstance(call_id, str) or not call_id or not isinstance(name, str) or not name:
                raise ValueError("DeepSeek tool call requires its name and ID")
            if (session_id, call_id) in calls:
                raise ValueError("DeepSeek session has duplicate tool call IDs")
            calls[session_id, call_id] = name, step
        records.extend((session_id, entry) for entry in _event_entries(event, data, step))

    for child, (parent, call) in spawns.items():
        if parents.get(child) != parent or calls.get((parent, call), (None,))[0] != "subagent":
            raise ValueError("DeepSeek spawn event does not match native lineage and a parent subagent call")
    models = {
        session_id: entry.model_response.model_name for session_id, entry in records if entry.model_response is not None
    }
    result: list[TrajectoryEntry] = []
    for session_id, entry in records:
        visited: set[str] = set()
        while session_id != root_session_id:
            if session_id in visited or session_id not in parents:
                raise ValueError("DeepSeek child lineage is disconnected or cyclic")
            visited.add(session_id)
            parent = parents[session_id]
            call_id = spawns[session_id][1] if session_id in spawns else None
            parent_step = calls[parent, call_id][1] if call_id is not None else 0
            entry = TrajectoryEntry(
                role="subagent",
                step=parent_step,
                timestamp=entry.timestamp,
                subagent=TrajectorySubagentEntry(
                    trajectory_id=session_id,
                    parent_tool_call_id=call_id,
                    agent_name="deepseek_harness",
                    model_name=models.get(session_id),
                    entry=entry,
                ),
            )
            session_id = parent
        result.append(entry)
    return result


def _session_entry(session_id: str) -> TrajectoryEntry:
    return TrajectoryEntry(
        step=0, role="session", metadata={"source": "deepseek_notifications", "session_id": session_id}
    )


def _event_entries(event: dict[str, Any], data: dict[str, Any], step: int) -> list[TrajectoryEntry]:
    occurred_at = _event_datetime(event)
    context: dict[str, Any] = {"step": step, "timestamp": occurred_at.isoformat() if occurred_at is not None else None}
    kind = event.get("type")
    if kind == "user/message":
        return [TrajectoryEntry(**context, role="user", content=_text_content(data.get("content")))]
    if kind == "assistant/message":
        message = data.get("message", {})
        if not isinstance(message, dict) or not isinstance(message.get("source", {}), dict):
            raise ValueError("DeepSeek assistant message and source must be objects")
        source = message.get("source", {})
        usage = data.get("usage")
        token_fields = {
            "inputTokens": "input_tokens",
            "outputTokens": "output_tokens",
            "cacheReadTokens": "cache_read_tokens",
            "cacheWriteTokens": "cache_write_tokens",
        }
        response = TrajectoryModelResponse(
            source="deepseek_session",
            model_name=source.get("model"),
            provider_name=source.get("provider"),
            usage=TrajectoryUsage.model_validate(
                {
                    **{target: usage[field] for field, target in token_fields.items() if field in usage},
                    "details": {field: value for field, value in usage.items() if field not in token_fields},
                }
            )
            if isinstance(usage, dict)
            else None,
        )
        entries = [
            TrajectoryEntry(
                **context,
                role="model_response",
                model_response=response,
                metadata={"deepseek_message_id": message["id"]} if "id" in message else None,
            )
        ]
        for block in _content_blocks(message):
            text = block.get("text")
            if block.get("type") in {"text", "reasoning"} and not isinstance(text, str):
                raise ValueError("DeepSeek text and reasoning blocks require text")
            if block.get("type") == "text":
                entries.append(TrajectoryEntry(**context, role="assistant", content=text))
            elif block.get("type") == "reasoning":
                assert isinstance(text, str)
                entries.append(
                    TrajectoryEntry(
                        **context,
                        role="reasoning",
                        reasoning=TrajectoryReasoning(content=text, provider_name=response.provider_name),
                    )
                )
        return entries
    if kind == "tool/call":
        arguments = data.get("arguments")
        try:
            parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
        except ValueError:
            parsed = None
        return [
            TrajectoryEntry(
                **context,
                role="tool_call",
                tool_call_id=data["callId"],
                tool_name=data["name"],
                arguments=parsed if isinstance(parsed, dict) else None,
                command=arguments if isinstance(arguments, str) else json.dumps(arguments),
            )
        ]
    if kind == "tool/result":
        results = _content_blocks(data.get("message", {}))
        return [
            TrajectoryEntry(
                **context,
                role="tool_result",
                tool_call_id=result.get("toolCallId"),
                content=_text_content(result.get("content")),
                metadata={"is_error": result.get("isError", False)},
            )
            for result in results
            if result.get("type") == "tool-result"
        ]
    if kind == "turn/end":
        reason_data = data.get("reason", {})
        if not isinstance(reason_data, dict):
            raise ValueError("DeepSeek turn reason must be an object")
        reason = reason_data.get("kind")
        if reason != "completed":
            return [TrajectoryEntry(**context, role="error", content=f"DeepSeek turn ended: {reason}")]
    return []


def _content_blocks(message: Any) -> list[dict[str, Any]]:
    if not isinstance(message, dict):
        raise ValueError("DeepSeek message must be an object")
    blocks = message.get("content", [])
    if not isinstance(blocks, list) or any(not isinstance(block, dict) for block in blocks):
        raise ValueError("DeepSeek message content must be an array of blocks")
    return blocks
