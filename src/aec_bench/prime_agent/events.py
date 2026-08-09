# ABOUTME: Parses the untrusted Prime Agent JSON-lines event stream without mirroring its full schema.
# ABOUTME: Preserves raw event objects while deriving only adapter transcript, model, usage, and completion evidence.

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import StrictInt, ValidationError, field_validator

from aec_bench.contracts.adapter_execution import (
    TokenUsage,
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
)
from aec_bench.contracts.validators import LenientModel

PRIME_EVENT_STREAM_VERSIONS = frozenset({3})


class PrimeEventStreamError(ValueError):
    """Base error for an unusable Prime Agent JSON event stream."""


class PrimeMalformedEventStreamError(PrimeEventStreamError):
    """Raised when the JSONL framing or required envelope is malformed."""


class PrimeUnsupportedEventStreamError(PrimeEventStreamError):
    """Raised when Prime advertises an event stream version AEC-Bench has not tested."""


class PrimeIncompleteEventStreamError(PrimeEventStreamError):
    """Raised when a well-formed stream has no terminal Prime event."""


class _SessionHeader(LenientModel):
    type: Literal["session"]
    version: StrictInt
    id: str

    @field_validator("id")
    @classmethod
    def require_session_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("session id must not be blank")
        return value


class _EventEnvelope(LenientModel):
    type: str

    @field_validator("type")
    @classmethod
    def require_event_type(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("event type must not be blank")
        return value


@dataclass(frozen=True)
class PrimeEvents:
    """Small normalized view over one preserved Prime JSON event stream."""

    stream_version: int
    session_id: str
    events: tuple[dict[str, Any], ...]
    terminal_event: str
    transcript: tuple[TranscriptEntry, ...]
    final_assistant_text: str | None
    turn_count: int
    compaction_count: int
    provider: str | None
    resolved_model: str | None
    assistant_error: str | None
    usage_model_calls: int | None
    usage_input_tokens: int | None
    usage_output_tokens: int | None
    usage_cache_read_tokens: int | None
    usage_cache_write_tokens: int | None


@dataclass
class _UsageAccumulator:
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    complete: bool = True

    def record(self, message: dict[str, Any]) -> None:
        usage = message.get("usage")
        if not isinstance(usage, dict):
            self.complete = False
            return
        values = tuple(_non_negative_int(usage.get(name)) for name in ("input", "output", "cacheRead", "cacheWrite"))
        if any(value is None for value in values):
            self.complete = False
            return
        input_tokens, output_tokens, cache_read_tokens, cache_write_tokens = values
        assert input_tokens is not None
        assert output_tokens is not None
        assert cache_read_tokens is not None
        assert cache_write_tokens is not None
        self.model_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_read_tokens += cache_read_tokens
        self.cache_write_tokens += cache_write_tokens


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return int(value)


def _event_objects(raw: bytes | str) -> list[dict[str, Any]]:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise PrimeMalformedEventStreamError("Prime event stream is not valid UTF-8") from exc
    else:
        text = raw

    lines = text.splitlines()
    if not lines:
        raise PrimeMalformedEventStreamError("Prime event stream is missing its session header")

    objects: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise PrimeMalformedEventStreamError(f"Prime event stream line {line_number} is blank")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PrimeMalformedEventStreamError(f"Prime event stream line {line_number} is not valid JSON") from exc
        if not isinstance(value, dict):
            raise PrimeMalformedEventStreamError(f"Prime event stream line {line_number} must be a JSON object")
        objects.append(value)
    return objects


def _validated_header(event: dict[str, Any]) -> _SessionHeader:
    try:
        header = _SessionHeader.model_validate(event)
    except ValidationError as exc:
        raise PrimeMalformedEventStreamError("Prime event stream is missing a valid session header") from exc
    if header.version not in PRIME_EVENT_STREAM_VERSIONS:
        raise PrimeUnsupportedEventStreamError(
            f"Prime event stream version {header.version} is unsupported; "
            f"supported versions: {sorted(PRIME_EVENT_STREAM_VERSIONS)}"
        )
    return header


def _message_identity(message: dict[str, Any]) -> str | None:
    response_id = message.get("responseId")
    if isinstance(response_id, str) and response_id:
        return f"response:{response_id}"
    timestamp = message.get("timestamp")
    provider = message.get("provider")
    model = message.get("model")
    if isinstance(timestamp, int | float) and not isinstance(timestamp, bool):
        content = json.dumps(message.get("content"), sort_keys=True, separators=(",", ":"))
        return f"message:{provider}:{model}:{timestamp}:{content}"
    return None


def _message_text(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    text = "".join(parts).strip()
    return text or None


def _occurred_at(message: dict[str, Any]) -> datetime | None:
    timestamp = message.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int | float):
        return None
    try:
        return datetime.fromtimestamp(float(timestamp) / 1000, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return None


def _json_content(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def parse_prime_events(raw: bytes | str) -> PrimeEvents:
    """Validate a Prime JSON v3 stream and derive the existing adapter fields."""
    events = _event_objects(raw)
    header = _validated_header(events[0])

    transcript: list[TranscriptEntry] = []
    usage = _UsageAccumulator()
    seen_messages: set[str] = set()
    final_text: str | None = None
    provider: str | None = None
    resolved_model: str | None = None
    assistant_error: str | None = None
    turn_count = 0
    compaction_count = 0
    terminal_event: str | None = None

    def record_assistant(message: dict[str, Any]) -> None:
        nonlocal assistant_error, final_text, provider, resolved_model
        identity = _message_identity(message)
        if identity is None:
            usage.complete = False
        elif identity in seen_messages:
            return
        else:
            seen_messages.add(identity)
            usage.record(message)

        text = _message_text(message)
        final_text = text
        if text is not None:
            transcript.append(
                TranscriptEntry(
                    role=TranscriptRole.ASSISTANT,
                    content=text,
                    usage=TokenUsage(
                        input_tokens=_non_negative_int(
                            message.get("usage", {}).get("input") if isinstance(message.get("usage"), dict) else None
                        ),
                        output_tokens=_non_negative_int(
                            message.get("usage", {}).get("output") if isinstance(message.get("usage"), dict) else None
                        ),
                    ),
                    occurred_at=_occurred_at(message),
                )
            )
        message_provider = message.get("provider")
        if isinstance(message_provider, str) and message_provider:
            provider = message_provider
        response_model = message.get("responseModel")
        requested_model = message.get("model")
        if isinstance(response_model, str) and response_model:
            resolved_model = response_model
        elif isinstance(requested_model, str) and requested_model:
            resolved_model = requested_model
        stop_reason = message.get("stopReason")
        if stop_reason in {"error", "aborted"}:
            error_message = message.get("errorMessage")
            assistant_error = (
                str(error_message)
                if isinstance(error_message, str) and error_message
                else f"assistant stopped: {stop_reason}"
            )
        else:
            assistant_error = None

    for line_number, event in enumerate(events[1:], start=2):
        try:
            envelope = _EventEnvelope.model_validate(event)
        except ValidationError as exc:
            raise PrimeMalformedEventStreamError(
                f"Prime event stream line {line_number} is missing a valid event type"
            ) from exc
        if envelope.type == "session":
            raise PrimeMalformedEventStreamError(
                f"Prime event stream line {line_number} contains a second session header"
            )
        if envelope.type == "turn_end":
            turn_count += 1
        elif envelope.type == "compaction_end":
            compaction_count += 1
        elif envelope.type == "tool_execution_start":
            tool_name = event.get("toolName")
            tool_call_id = event.get("toolCallId")
            transcript.append(
                TranscriptEntry(
                    role=TranscriptRole.ASSISTANT,
                    content=_json_content(event.get("args")),
                    event=TranscriptEvent.TOOL_CALL,
                    tool_name=tool_name if isinstance(tool_name, str) else None,
                    tool_call_id=tool_call_id if isinstance(tool_call_id, str) else None,
                )
            )
        elif envelope.type == "tool_execution_end":
            tool_name = event.get("toolName")
            tool_call_id = event.get("toolCallId")
            transcript.append(
                TranscriptEntry(
                    role=TranscriptRole.TOOL,
                    content=_json_content(event.get("result")),
                    event=TranscriptEvent.TOOL_RESULT,
                    tool_name=tool_name if isinstance(tool_name, str) else None,
                    tool_call_id=tool_call_id if isinstance(tool_call_id, str) else None,
                )
            )
        elif envelope.type == "message_end":
            message = event.get("message")
            if isinstance(message, dict) and message.get("role") == "assistant":
                record_assistant(message)
        elif envelope.type == "agent_end":
            terminal_event = envelope.type
            messages = event.get("messages")
            if isinstance(messages, list):
                for message in messages:
                    if isinstance(message, dict) and message.get("role") == "assistant":
                        record_assistant(message)

    if terminal_event is None:
        raise PrimeIncompleteEventStreamError("Prime event stream ended without an agent_end terminal event")

    usage_known = bool(seen_messages) and usage.complete
    return PrimeEvents(
        stream_version=header.version,
        session_id=header.id,
        events=tuple(events),
        terminal_event=terminal_event,
        transcript=tuple(transcript),
        final_assistant_text=final_text,
        turn_count=turn_count,
        compaction_count=compaction_count,
        provider=provider,
        resolved_model=resolved_model,
        assistant_error=assistant_error,
        usage_model_calls=usage.model_calls if usage_known else None,
        usage_input_tokens=usage.input_tokens if usage_known else None,
        usage_output_tokens=usage.output_tokens if usage_known else None,
        usage_cache_read_tokens=usage.cache_read_tokens if usage_known else None,
        usage_cache_write_tokens=usage.cache_write_tokens if usage_known else None,
    )
