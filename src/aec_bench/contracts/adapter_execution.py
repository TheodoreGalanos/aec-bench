# ABOUTME: Defines provider-neutral transcript values for adapter and Prime execution evidence.
# ABOUTME: Keeps execution records independent from concrete adapter implementations.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


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
