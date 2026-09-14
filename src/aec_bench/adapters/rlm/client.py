# ABOUTME: LLM client protocol and replay implementation for the RLM adapter.
# ABOUTME: Defines the interface for main-loop and sub-call model invocations.

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from _thread import LockType

    from aec_bench.adapters.rlm.guardrails import GuardrailState
    from aec_bench.adapters.rlm.tokens import TokenTracker


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
        max_output_tokens: int | None = None,
    ) -> RlmCompletionResponse: ...


@runtime_checkable
class ToolCapableRlmClient(Protocol):
    """Structural client surface for providers supporting native tool calls."""

    def generate_with_tools(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        tool_name: str,
        tool_description: str,
        tool_parameters_schema: dict[str, Any],
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
        max_output_tokens: int | None = None,
    ) -> RlmCompletionResponse:
        with self._lock:
            response = self._responses[self._index]
            self._index += 1
        return response


class AuxiliaryRlmClient:
    """Admit secondary calls against the active run and preserve its task policy."""

    def __init__(
        self,
        inner: RlmClient,
        *,
        guardrails: GuardrailState,
        instruction: str,
        system_prompt: str,
        token_tracker: TokenTracker,
        category: Literal["subcall", "compaction", "advisor"],
        lock: LockType,
    ) -> None:
        self.inner = inner
        self.guardrails = guardrails
        self.instruction = instruction
        self.system_prompt = system_prompt
        self.token_tracker = token_tracker
        self.category = category
        self.lock = lock

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> RlmCompletionResponse:
        from aec_bench.adapters.base import AdapterStopReason
        from aec_bench.adapters.runtime_limits import AdapterRuntimeLimitError
        from aec_bench.contracts.pricing import estimate_cost_usd

        with self.lock:
            verdict = self.guardrails.check()
            # max_turns counts main iterations; the current iteration may use tools.
            if not verdict.can_continue and verdict.stop_code != AdapterStopReason.ITERATION_CAP:
                raise AdapterRuntimeLimitError(verdict.stop_reason)
            if self.guardrails.provider_error:
                raise RuntimeError(self.guardrails.provider_error)
            if self.category == "subcall":
                self.guardrails.reserve_subcall()
        try:
            settings = {"max_output_tokens": max_output_tokens} if max_output_tokens is not None else {}
            response = self.inner.generate(
                model=model,
                messages=[RlmMessage(role="user", content=self.instruction), *messages],
                system_prompt="\n\n".join(p for p in (self.system_prompt, system_prompt) if p),
                temperature=temperature,
                **settings,
            )
        except Exception as exc:
            self.guardrails.provider_error = str(exc)
            self.guardrails.usage_known = False
            raise
        with self.lock:
            cost = (
                estimate_cost_usd(
                    model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cache_read_tokens=response.cache_read_tokens,
                    cache_write_tokens=response.cache_write_tokens,
                )
                or 0.0
            )
            self.guardrails.record_auxiliary_tokens(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=cost,
                cache_read_tokens=response.cache_read_tokens,
            )
            if self.category == "subcall":
                self.token_tracker.record_subcall(
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost_usd=cost,
                    cache_read_tokens=response.cache_read_tokens,
                    cache_write_tokens=response.cache_write_tokens,
                )
            if response.error_message:
                self.guardrails.provider_error = response.error_message
                self.guardrails.usage_known = False
        return response
