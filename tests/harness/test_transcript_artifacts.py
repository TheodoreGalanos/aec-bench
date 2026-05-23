# ABOUTME: Tests for transcript artifact serialization in aec-bench Python.
# ABOUTME: Covers JSONL persistence of canonical transcript entries for harness collection.

from pathlib import Path

from aec_bench.adapters.transcript import TranscriptEntry, TranscriptEvent, TranscriptRole
from aec_bench.harness.transcript_artifacts import write_transcript_artifact


def test_write_transcript_artifact_persists_tool_events_as_jsonl(tmp_path: Path) -> None:
    transcript = [
        TranscriptEntry(role=TranscriptRole.USER, content="Review the task."),
        TranscriptEntry(
            role=TranscriptRole.ASSISTANT,
            content="Calling codes_search.",
            event=TranscriptEvent.TOOL_CALL,
            tool_name="codes_search",
            tool_call_id="call-1",
        ),
        TranscriptEntry(
            role=TranscriptRole.TOOL,
            content='{"matches": []}',
            event=TranscriptEvent.TOOL_RESULT,
            tool_name="codes_search",
            tool_call_id="call-1",
        ),
    ]

    artifact_path = write_transcript_artifact(
        path=tmp_path / "conversation.jsonl",
        transcript=transcript,
    )

    assert artifact_path == tmp_path / "conversation.jsonl"
    lines = artifact_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert '"event": "tool_call"' in lines[1]
    assert '"tool_name": "codes_search"' in lines[1]
    assert '"event": "tool_result"' in lines[2]
