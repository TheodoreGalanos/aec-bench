# ABOUTME: Canonical transcript records for adapter execution traces in aec-bench Python.
# ABOUTME: Preserves stable role and usage metadata without leaking provider SDK objects.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aec_bench.adapters.base import AdapterRequest


class TranscriptEvent(StrEnum):
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class TranscriptRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class TranscriptEntry:
    role: TranscriptRole
    content: str
    event: TranscriptEvent = TranscriptEvent.MESSAGE
    tool_name: str | None = None
    tool_call_id: str | None = None
    usage: TokenUsage | None = None
    occurred_at: datetime | None = None


def initialize_transcript(request: AdapterRequest) -> list[TranscriptEntry]:
    """Build the opening transcript entries from an adapter request."""
    transcript: list[TranscriptEntry] = []
    if request.system_prompt is not None:
        transcript.append(TranscriptEntry(role=TranscriptRole.SYSTEM, content=request.system_prompt))
    transcript.append(TranscriptEntry(role=TranscriptRole.USER, content=request.instruction))
    return transcript
