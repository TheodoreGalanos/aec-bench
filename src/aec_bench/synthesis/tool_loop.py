# ABOUTME: Tool-loop synthesis driver — pydantic-ai Agent with AggAgent §4 tools.
# ABOUTME: Alternative to plain synthesis; dispatched via SynthesisConfig.synthesis_mode.

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from aec_bench.contracts.synthesis import SynthesisInput, SynthesisOutput
from aec_bench.synthesis import tools as _tools
from aec_bench.synthesis.prompts import (
    build_tool_loop_system_prompt,
    build_tool_loop_user_message,
)


class FinishResult(BaseModel):
    """Structured output for the synthesiser's termination tool.

    pydantic-ai exposes the output_type schema as a final-result tool the
    agent must call to terminate, so FinishResult plays the role of the
    spec's `finish` tool — synthesised draft plus meta-reasoning.
    """

    synthesised_section: str = Field(
        description="The final synthesised draft — self-contained, no references to candidates.",
    )
    reason: str = Field(
        description="Concise account of how the candidates were combined and conflicts resolved.",
    )


def synthesise_via_tool_loop(
    input: SynthesisInput,
    *,
    model: Any,
) -> SynthesisOutput:
    """Run AggAgent-style tool-loop synthesis via pydantic-ai.

    ``model`` accepts any pydantic-ai Model or model-name string
    (e.g. ``"anthropic:claude-sonnet-4-6"``, a pre-built
    ``BedrockConverseModel``, or a ``TestModel`` for tests).

    On any model-side failure (turn cap, exception, empty output) returns
    ``SynthesisOutput`` with ``fallback_used=True`` — the caller decides
    whether to fall back to plain synthesis or the best pointwise candidate.
    """
    cfg = input.config
    tool_call_trace: list[dict[str, Any]] = []

    agent = Agent(
        model,
        output_type=FinishResult,
        system_prompt=build_tool_loop_system_prompt(cfg),
    )

    @agent.tool_plain
    def get_candidate(i: int | None = None) -> list[dict[str, Any]]:
        """Return all K candidates (i omitted) or a single candidate by index."""
        tool_call_trace.append({"tool": "get_candidate", "args": {"i": i}})
        try:
            return _tools.get_candidate(input, i=i)
        except IndexError as exc:
            return [{"error": str(exc)}]

    @agent.tool_plain
    def get_source(source_label: str) -> str:
        """Return the extracted content for a given source label."""
        tool_call_trace.append(
            {"tool": "get_source", "args": {"source_label": source_label}},
        )
        try:
            return _tools.get_source(input, source_label)
        except KeyError as exc:
            return f"error: {exc}"

    @agent.tool_plain
    def search_source(
        source_label: str | None,
        query: str,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search extracted data; pass source_label=None to search all sources."""
        tool_call_trace.append(
            {
                "tool": "search_source",
                "args": {"source_label": source_label, "query": query, "k": k},
            },
        )
        return _tools.search_source(input, source_label, query, k)

    @agent.tool_plain
    def search_across_candidates(query: str, k: int = 5) -> list[dict[str, Any]]:
        """Locate divergences by searching the K candidates for a query term."""
        tool_call_trace.append(
            {"tool": "search_across_candidates", "args": {"query": query, "k": k}},
        )
        return _tools.search_across_candidates(input, query, k)

    @agent.tool_plain
    def get_criteria_bundle() -> dict[str, Any]:
        """Return writing rules, rubric criteria, and expert personas."""
        tool_call_trace.append({"tool": "get_criteria_bundle", "args": {}})
        return _tools.get_criteria_bundle(input)

    user_msg = build_tool_loop_user_message(
        section_title=input.criteria.section_title,
        k_candidates=len(input.candidates),
    )

    start = time.monotonic()
    try:
        result = agent.run_sync(
            user_msg,
            usage_limits=UsageLimits(
                request_limit=cfg.tool_loop_max_turns,
                output_tokens_limit=cfg.max_output_tokens,
            ),
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        # On UsageLimitExceeded the agent hit the request cap, so turns ==
        # configured cap. For other exceptions we don't know — report 0.
        exc_name = type(exc).__name__
        turns_on_failure = cfg.tool_loop_max_turns if exc_name == "UsageLimitExceeded" else 0
        return SynthesisOutput(
            content="",
            reason="",
            synthesiser_model=cfg.synthesiser_model,
            input_tokens=0,
            output_tokens=0,
            elapsed_s=elapsed,
            fallback_used=True,
            fallback_reason=f"{exc_name}: {exc}",
            synthesiser_turns=turns_on_failure,
            tool_calls=tuple(tool_call_trace),
        )

    elapsed = time.monotonic() - start
    usage = result.usage()
    output = result.output

    content = (output.synthesised_section or "").strip()
    if not content:
        return SynthesisOutput(
            content="",
            reason=output.reason or "",
            synthesiser_model=cfg.synthesiser_model,
            input_tokens=int(usage.input_tokens or 0),
            output_tokens=int(usage.output_tokens or 0),
            elapsed_s=elapsed,
            fallback_used=True,
            fallback_reason="empty_output",
            synthesiser_turns=int(usage.requests or 0),
            tool_calls=tuple(tool_call_trace),
        )

    return SynthesisOutput(
        content=content,
        reason=output.reason or "",
        synthesiser_model=cfg.synthesiser_model,
        input_tokens=int(usage.input_tokens or 0),
        output_tokens=int(usage.output_tokens or 0),
        elapsed_s=elapsed,
        synthesiser_turns=int(usage.requests or 0),
        tool_calls=tuple(tool_call_trace),
    )


__all__ = ["FinishResult", "synthesise_via_tool_loop"]
