# ABOUTME: Reduces the DeepSeek adapter's raw notifications into provider-neutral execution evidence.
# ABOUTME: Counts root model steps, retains native counters, and keeps child sessions out of the root transcript.

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aec_bench.contracts.adapter_execution import (
    TokenUsage,
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
)

_KNOWN_EVENT_TYPES = {
    "agent/inbox/spliced",
    "assistant/chunk",
    "assistant/message",
    "request/context",
    "request/header",
    "session/title",
    "step/end",
    "step/start",
    "tool/call",
    "tool/result",
    "turn/end",
    "turn/start",
    "user/message",
}


@dataclass(frozen=True)
class DeepSeekRunProjection:
    session_id: str
    root_model_calls: int
    root_steps: int
    root_turns: int
    tool_calls_started: int
    tool_calls_completed: int
    transcript: list[TranscriptEntry]
    final_response: str
    last_turn_end_reason: str | None
    usage_input_tokens: int
    usage_output_tokens: int
    usage_cache_read_tokens: int
    maximum_input_tokens_in_one_call: int
    maximum_output_tokens_in_one_call: int
    child_session_ids: tuple[str, ...]
    unknown_event_types: tuple[str, ...]
    idle_seen: bool


def reduce_deepseek_notifications(
    root_session_id: str,
    notifications: list[dict[str, Any]],
) -> DeepSeekRunProjection:
    """Build one deterministic root-session projection from captured wire notifications."""
    root_steps = 0
    root_turns = 0
    tool_calls_started = 0
    tool_calls_completed = 0
    transcript: list[TranscriptEntry] = []
    final_response = ""
    last_turn_end_reason: str | None = None
    usage_input_tokens = 0
    usage_output_tokens = 0
    usage_cache_read_tokens = 0
    maximum_input_tokens_in_one_call = 0
    maximum_output_tokens_in_one_call = 0
    child_session_ids: set[str] = set()
    unknown_event_types: set[str] = set()
    idle_seen = False

    for notification in notifications:
        envelope = notification_envelope_parts(notification)
        if envelope is None:
            continue
        method, params = envelope
        session_id = params.get("sessionId")
        if not isinstance(session_id, str):
            continue
        if session_id != root_session_id:
            child_session_ids.add(session_id)
            continue
        if method == "session.status":
            idle_seen = idle_seen or params.get("status") == "idle"
            continue
        if method != "session.event":
            continue
        event = params.get("event")
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if not isinstance(event_type, str):
            continue
        if event_type not in _KNOWN_EVENT_TYPES:
            unknown_event_types.add(event_type)
        data = event.get("data")
        data = data if isinstance(data, dict) else {}

        if event_type == "turn/start":
            root_turns += 1
        elif event_type == "step/start":
            root_steps += 1
        elif event_type == "turn/end":
            last_turn_end_reason = _turn_end_reason(data)
        elif event_type == "assistant/message":
            entry, usage = _assistant_entry(data, event)
            if entry is not None:
                transcript.append(entry)
                final_response = entry.content
            usage_input_tokens += usage.input_tokens or 0
            usage_output_tokens += usage.output_tokens or 0
            usage_cache_read_tokens += _usage_value(data, "cacheReadTokens")
            maximum_input_tokens_in_one_call = max(maximum_input_tokens_in_one_call, usage.input_tokens or 0)
            maximum_output_tokens_in_one_call = max(maximum_output_tokens_in_one_call, usage.output_tokens or 0)
        elif event_type == "tool/call":
            tool_calls_started += 1
            transcript.append(_tool_call_entry(data, event))
        elif event_type == "tool/result":
            tool_calls_completed += 1
            transcript.append(_tool_result_entry(data, event))

    return DeepSeekRunProjection(
        session_id=root_session_id,
        root_model_calls=root_steps,
        root_steps=root_steps,
        root_turns=root_turns,
        tool_calls_started=tool_calls_started,
        tool_calls_completed=tool_calls_completed,
        transcript=transcript,
        final_response=final_response,
        last_turn_end_reason=last_turn_end_reason,
        usage_input_tokens=usage_input_tokens,
        usage_output_tokens=usage_output_tokens,
        usage_cache_read_tokens=usage_cache_read_tokens,
        maximum_input_tokens_in_one_call=maximum_input_tokens_in_one_call,
        maximum_output_tokens_in_one_call=maximum_output_tokens_in_one_call,
        child_session_ids=tuple(sorted(child_session_ids)),
        unknown_event_types=tuple(sorted(unknown_event_types)),
        idle_seen=idle_seen,
    )


def notification_envelope_parts(notification: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Read either captured AEC evidence or the SDK's direct notification shape."""
    method = notification.get("notification_method", notification.get("method"))
    params = notification.get("payload", notification.get("params"))
    if not isinstance(method, str) or not isinstance(params, dict):
        return None
    return method, params


def _turn_end_reason(data: dict[str, Any]) -> str | None:
    reason = data.get("reason")
    kind = reason.get("kind") if isinstance(reason, dict) else None
    return kind if isinstance(kind, str) else None


def _assistant_entry(
    data: dict[str, Any],
    event: dict[str, Any],
) -> tuple[TranscriptEntry | None, TokenUsage]:
    message = data.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    text = _text_content(content)
    usage = TokenUsage(
        input_tokens=_usage_value(data, "inputTokens"),
        output_tokens=_usage_value(data, "outputTokens"),
    )
    if not text:
        return None, usage
    return (
        TranscriptEntry(
            role=TranscriptRole.ASSISTANT,
            content=text,
            usage=usage,
            occurred_at=_event_datetime(event),
        ),
        usage,
    )


def _tool_call_entry(data: dict[str, Any], event: dict[str, Any]) -> TranscriptEntry:
    arguments = data.get("arguments")
    return TranscriptEntry(
        role=TranscriptRole.ASSISTANT,
        content=arguments if isinstance(arguments, str) else json.dumps(arguments, sort_keys=True),
        event=TranscriptEvent.TOOL_CALL,
        tool_name=_optional_string(data.get("name")),
        tool_call_id=_optional_string(data.get("callId")),
        occurred_at=_event_datetime(event),
    )


def _tool_result_entry(data: dict[str, Any], event: dict[str, Any]) -> TranscriptEntry:
    message = data.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    tool_result = content[0] if isinstance(content, list) and content and isinstance(content[0], dict) else {}
    return TranscriptEntry(
        role=TranscriptRole.TOOL,
        content=_text_content(tool_result.get("content")),
        event=TranscriptEvent.TOOL_RESULT,
        tool_call_id=_optional_string(tool_result.get("toolCallId")),
        occurred_at=_event_datetime(event),
    )


def _text_content(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    return "".join(
        str(block.get("text") or "") for block in content if isinstance(block, dict) and block.get("type") == "text"
    )


def _usage_value(data: dict[str, Any], field_name: str) -> int:
    usage = data.get("usage")
    value = usage.get(field_name) if isinstance(usage, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _event_datetime(event: dict[str, Any]) -> datetime | None:
    timestamp = event.get("time")
    if not isinstance(timestamp, int | float) or isinstance(timestamp, bool):
        return None
    return datetime.fromtimestamp(timestamp / 1000, tz=UTC)
