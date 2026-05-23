# ABOUTME: Synthesis engine — dispatches plain (single call) or tool_loop (agent) modes.
# ABOUTME: Adapter-agnostic; vendor coupling lives in the injected client or pydantic-ai model.

from __future__ import annotations

import time
from typing import Any, Protocol

from aec_bench.contracts.synthesis import (
    SynthesisInput,
    SynthesisOutput,
)
from aec_bench.synthesis.prompts import build_full_prompt
from aec_bench.synthesis.tool_loop import synthesise_via_tool_loop

# Rough conservative chars-per-token ratio for English + structured prompts.
# Used only for pre-flight budget checks; actual tokenisation happens at the
# provider. 3.5 chars/token matches what we see across candidates in bootstrap.
_CHARS_PER_TOKEN_ESTIMATE = 3.5


class SynthesisBudgetError(ValueError):
    """Raised when the rendered prompt exceeds max_input_tokens.

    Callers decide whether to fall back to selection or surface the error.
    This is a proper exception (not a SynthesisOutput with fallback_used=True)
    because it fires before any LLM call — the caller can try a smaller set
    of references without paying for a failed synthesis.
    """


class BehavioralLLMClient(Protocol):
    """Minimal protocol the engine depends on — matches providers.behavioral_llm."""

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str: ...


def _estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN_ESTIMATE) + 1


def synthesise(
    input: SynthesisInput,
    *,
    client: BehavioralLLMClient | None = None,
    model: Any | None = None,
    temperature: float = 0.2,
) -> SynthesisOutput:
    """Dispatch to plain or tool-loop synthesis based on config.synthesis_mode.

    Plain mode (default) requires ``client`` — a BehavioralLLMClient that
    makes one LLM call with the rendered prompt. Tool-loop mode requires
    ``model`` — a pydantic-ai compatible model (name string or Model instance).
    """
    mode = input.config.synthesis_mode
    if mode == "tool_loop":
        if model is None:
            raise ValueError(
                "tool_loop synthesis requires `model` (pydantic-ai compatible)",
            )
        return synthesise_via_tool_loop(input, model=model)
    if client is None:
        raise ValueError("plain synthesis requires `client`")
    return _synthesise_plain(input, client=client, temperature=temperature)


def _synthesise_plain(
    input: SynthesisInput,
    *,
    client: BehavioralLLMClient,
    temperature: float = 0.2,
) -> SynthesisOutput:
    """Synthesise one unified draft from K candidate drafts via a single LLM call.

    Returns SynthesisOutput with ``fallback_used=True`` and a ``fallback_reason``
    on model-side failures (LLM raises, empty output). Raises SynthesisBudgetError
    if the rendered prompt exceeds ``config.max_input_tokens`` — that's a caller
    decision, not a synthesis failure.
    """
    config = input.config

    prompt = build_full_prompt(
        criteria=input.criteria,
        references=input.references,
        candidates=input.candidates,
        config=config,
    )

    estimated_input_tokens = _estimate_tokens(prompt)
    if estimated_input_tokens > config.max_input_tokens:
        raise SynthesisBudgetError(
            f"rendered prompt ~{estimated_input_tokens} tokens "
            f"exceeds max_input_tokens {config.max_input_tokens}. "
            "Caller should reduce references or candidate set.",
        )

    start = time.monotonic()
    try:
        raw_output = client.complete(
            prompt,
            temperature=temperature,
            max_tokens=config.max_output_tokens,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return SynthesisOutput(
            content="",
            reason="",
            synthesiser_model=config.synthesiser_model,
            input_tokens=estimated_input_tokens,
            output_tokens=0,
            elapsed_s=elapsed,
            fallback_used=True,
            fallback_reason=f"{type(exc).__name__}: {exc}",
        )

    elapsed = time.monotonic() - start
    content = raw_output.strip() if raw_output else ""

    if not content:
        return SynthesisOutput(
            content="",
            reason="",
            synthesiser_model=config.synthesiser_model,
            input_tokens=estimated_input_tokens,
            output_tokens=0,
            elapsed_s=elapsed,
            fallback_used=True,
            fallback_reason="empty_output",
        )

    # Plain-synthesis doesn't elicit a structured reason; the tool-loop
    # variant fills in meta-reasoning via the FinishResult schema.
    return SynthesisOutput(
        content=content,
        reason="",
        synthesiser_model=config.synthesiser_model,
        input_tokens=estimated_input_tokens,
        output_tokens=_estimate_tokens(content),
        elapsed_s=elapsed,
    )
