# ABOUTME: Validates Prime Agent JSON v3 event ingestion at the external protocol boundary.
# ABOUTME: Covers framing failures, unknown events, transcript normalization, and exact usage deduplication.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.contracts.adapter_execution import TranscriptEvent, TranscriptRole
from aec_bench.prime_agent.events import (
    PrimeIncompleteEventStreamError,
    PrimeMalformedEventStreamError,
    PrimeUnsupportedEventStreamError,
    parse_prime_events,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "prime_agent"


def test_parses_supported_v3_stream_without_counting_updates() -> None:
    events = parse_prime_events((FIXTURES / "minimal-v3.jsonl").read_bytes())

    assert events.stream_version == 3
    assert events.session_id == "session-123"
    assert events.terminal_event == "agent_end"
    assert events.final_assistant_text == "Final answer"
    assert events.turn_count == 1
    assert events.compaction_count == 1
    assert events.provider == "anthropic"
    assert events.resolved_model == "anthropic/claude-sonnet-4-20260701"
    assert events.usage_model_calls == 1
    assert events.usage_input_tokens == 120
    assert events.usage_output_tokens == 30
    assert events.usage_cache_read_tokens == 10
    assert events.usage_cache_write_tokens == 5

    assistant_messages = [entry for entry in events.transcript if entry.role is TranscriptRole.ASSISTANT]
    assert [entry.content for entry in assistant_messages if entry.event is TranscriptEvent.MESSAGE] == ["Final answer"]
    assert any(entry.event is TranscriptEvent.TOOL_CALL for entry in events.transcript)
    assert any(entry.event is TranscriptEvent.TOOL_RESULT for entry in events.transcript)


def test_preserves_unknown_events_and_all_original_ordered_objects() -> None:
    events = parse_prime_events((FIXTURES / "minimal-v3.jsonl").read_bytes())

    unknown = next(event for event in events.events if event["type"] == "future_event")
    assert unknown == {"type": "future_event", "payload": {"kept": True}}
    assert events.events[0]["type"] == "session"
    assert events.events[-1]["type"] == "agent_end"
    assert events.events[0]["futureHeaderField"] == "preserved"


def test_rejects_malformed_json() -> None:
    with pytest.raises(PrimeMalformedEventStreamError, match="line 2"):
        parse_prime_events((FIXTURES / "malformed-v3.jsonl").read_bytes())


@pytest.mark.parametrize(
    "payload, message",
    [
        (b'{"type":"agent_start"}\n{"type":"agent_end","messages":[]}\n', "session header"),
        (
            b'{"type":"session","version":3,"id":"session-1"}\n{"type":"session","version":3,"id":"again"}\n',
            "second session header",
        ),
        (b'{"type":"session","version":3,"id":"session-1"}\n[]\n', "JSON object"),
        (b"\xff\n", "UTF-8"),
    ],
)
def test_rejects_invalid_stream_framing(payload: bytes, message: str) -> None:
    with pytest.raises(PrimeMalformedEventStreamError, match=message):
        parse_prime_events(payload)


def test_rejects_unsupported_stream_version() -> None:
    with pytest.raises(PrimeUnsupportedEventStreamError, match="version 4"):
        parse_prime_events((FIXTURES / "unsupported-v4.jsonl").read_bytes())


def test_rejects_stream_without_terminal_event() -> None:
    payload = b'{"type":"session","version":3,"id":"session-1"}\n{"type":"agent_start"}\n'

    with pytest.raises(PrimeIncompleteEventStreamError, match="agent_end"):
        parse_prime_events(payload)


def test_deduplicates_repeated_completed_message_usage_by_identity() -> None:
    message = {
        "role": "assistant",
        "content": [{"type": "text", "text": "Only once"}],
        "provider": "anthropic",
        "model": "anthropic/test",
        "responseId": "same-response",
        "usage": {"input": 11, "output": 7, "cacheRead": 3, "cacheWrite": 2},
        "stopReason": "stop",
        "timestamp": 1786064524000,
    }
    rows = [
        {"type": "session", "version": 3, "id": "session-1"},
        {"type": "message_end", "message": message},
        {"type": "message_end", "message": message},
        {"type": "turn_end", "message": message, "toolResults": []},
        {"type": "agent_end", "messages": [message]},
    ]
    payload = "\n".join(json.dumps(row) for row in rows).encode()

    events = parse_prime_events(payload)

    assert events.usage_model_calls == 1
    assert events.usage_input_tokens == 11
    assert events.usage_output_tokens == 7
    assert [entry.content for entry in events.transcript if entry.event is TranscriptEvent.MESSAGE] == ["Only once"]


def test_leaves_all_usage_unknown_when_completed_message_usage_is_incomplete() -> None:
    message = {
        "role": "assistant",
        "content": [{"type": "text", "text": "Answer"}],
        "provider": "anthropic",
        "model": "anthropic/test",
        "responseId": "response-without-usage",
        "stopReason": "stop",
        "timestamp": 1786064524000,
    }
    rows = [
        {"type": "session", "version": 3, "id": "session-1"},
        {"type": "message_end", "message": message},
        {"type": "agent_end", "messages": [message]},
    ]

    events = parse_prime_events("\n".join(json.dumps(row) for row in rows).encode())

    assert events.usage_model_calls is None
    assert events.usage_input_tokens is None
    assert events.usage_output_tokens is None


def test_does_not_reuse_older_text_when_the_final_assistant_message_has_no_text() -> None:
    first = {
        "role": "assistant",
        "content": [{"type": "text", "text": "Intermediate note"}],
        "provider": "anthropic",
        "model": "anthropic/test",
        "responseId": "response-1",
        "usage": {"input": 3, "output": 2, "cacheRead": 0, "cacheWrite": 0},
        "stopReason": "stop",
        "timestamp": 1786064524000,
    }
    final = {
        **first,
        "content": [{"type": "toolCall", "id": "tool-1", "name": "ipython", "arguments": {}}],
        "responseId": "response-2",
        "stopReason": "toolUse",
        "timestamp": 1786064525000,
    }
    rows = [
        {"type": "session", "version": 3, "id": "session-1"},
        {"type": "message_end", "message": first},
        {"type": "message_end", "message": final},
        {"type": "agent_end", "messages": [first, final]},
    ]

    events = parse_prime_events("\n".join(json.dumps(row) for row in rows).encode())

    assert events.final_assistant_text is None
