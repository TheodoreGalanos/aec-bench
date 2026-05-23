# ABOUTME: LLM client protocol and replay implementation for the RLM adapter.
# ABOUTME: Defines the interface for main-loop and sub-call model invocations.

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RlmMessage:
    """A message in the RLM conversation history."""

    role: str  # "system", "user", "assistant", "tool_call", "tool_result"
    content: str
    tool_call_id: str | None = None
    tool_name: str | None = None


@dataclass(frozen=True)
class ToolCall:
    """A tool call extracted from a model response."""

    name: str
    code: str
    call_id: str


@dataclass(frozen=True)
class RlmCompletionResponse:
    """Response from the LLM for one REPL iteration."""

    output_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    error_message: str | None = None
    done: bool = False
    tool_call: ToolCall | None = None


class RlmClient(Protocol):
    """Protocol for LLM clients used by the RLM adapter."""

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
    ) -> RlmCompletionResponse: ...


class ReplayRlmClient:
    """Deterministic replay client for testing. Returns scripted responses in order.

    Thread-safe: parallel K-candidate generation (see lambda-rlm synthesis mode)
    issues generate() calls from multiple threads. A lock around index increment
    ensures each response is returned exactly once. Completion order under
    concurrency is non-deterministic; tests should be order-agnostic when K>1.
    """

    def __init__(self, responses: list[RlmCompletionResponse]) -> None:
        import threading

        self._responses = list(responses)
        self._index = 0
        self._lock = threading.Lock()

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
    ) -> RlmCompletionResponse:
        with self._lock:
            response = self._responses[self._index]
            self._index += 1
        return response
