# ABOUTME: Tests for tool-loop prompt builders.
# ABOUTME: Verifies domain hint injection and mandatory-content invariants.

from __future__ import annotations

from aec_bench.contracts.synthesis import SynthesisConfig
from aec_bench.synthesis.prompts import (
    build_tool_loop_system_prompt,
    build_tool_loop_user_message,
)


class TestToolLoopSystemPrompt:
    def test_contains_procedure_and_pitfalls(self) -> None:
        prompt = build_tool_loop_system_prompt(
            SynthesisConfig(domain_hint="public-works scope of works"),
        )
        # Essential sections from amendment §4.
        for header in ("REQUIRED PROCEDURE", "OPERATIONAL GUIDELINES", "COMMON PITFALLS"):
            assert header in prompt
        assert "public-works scope of works" in prompt

    def test_mentions_every_tool_by_name(self) -> None:
        prompt = build_tool_loop_system_prompt(SynthesisConfig())
        for tool in (
            "get_candidate",
            "get_source",
            "search_source",
            "search_across_candidates",
            "get_criteria_bundle",
            "finish",
        ):
            assert tool in prompt, f"missing tool mention: {tool}"

    def test_tells_agent_to_call_finish(self) -> None:
        prompt = build_tool_loop_system_prompt(SynthesisConfig())
        # The termination tool is what the agent is instructed to call last.
        assert "finish" in prompt.lower()
        # Source-verification stance is load-bearing — without this the agent
        # regresses into candidate-averaging.
        assert "ground truth" in prompt.lower()


class TestToolLoopUserMessage:
    def test_announces_k_and_section_title(self) -> None:
        message = build_tool_loop_user_message(
            section_title="Scope of Works",
            k_candidates=4,
        )
        assert "4" in message
        assert "Scope of Works" in message

    def test_no_candidate_content_inline(self) -> None:
        """The tool-loop flow retrieves candidates via get_candidate, not the
        opening message. The user message must stay compact so the early
        turns don't blow past context limits before the agent even uses a
        tool."""
        message = build_tool_loop_user_message(
            section_title="X",
            k_candidates=2,
        )
        # Keep it tight — long prompts here are a regression.
        assert len(message) < 500
