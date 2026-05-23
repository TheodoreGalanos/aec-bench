# ABOUTME: Tests for canonical adapter transcript records in aec-bench Python.
# ABOUTME: Covers stable role, content, tool events, and token-usage capture.

from aec_bench.adapters.transcript import (
    TokenUsage,
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
)


def test_transcript_entry_captures_role_content_and_usage() -> None:
    entry = TranscriptEntry(
        role=TranscriptRole.ASSISTANT,
        content="Computed answer.",
        usage=TokenUsage(input_tokens=120, output_tokens=42),
    )

    assert entry.role is TranscriptRole.ASSISTANT
    assert entry.content == "Computed answer."
    assert entry.usage is not None
    assert entry.usage.output_tokens == 42


def test_transcript_entry_captures_tool_call_and_result_metadata() -> None:
    tool_call = TranscriptEntry(
        role=TranscriptRole.ASSISTANT,
        content="Calling codes_search.",
        event=TranscriptEvent.TOOL_CALL,
        tool_name="codes_search",
        tool_call_id="call-1",
    )
    tool_result = TranscriptEntry(
        role=TranscriptRole.TOOL,
        content='{"matches": []}',
        event=TranscriptEvent.TOOL_RESULT,
        tool_name="codes_search",
        tool_call_id="call-1",
    )

    assert tool_call.event is TranscriptEvent.TOOL_CALL
    assert tool_call.tool_name == "codes_search"
    assert tool_result.event is TranscriptEvent.TOOL_RESULT
    assert tool_result.tool_call_id == "call-1"
