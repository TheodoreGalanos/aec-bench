# ABOUTME: Tests for the PydanticAI-compatible advisor tool helper.
# ABOUTME: Covers call interception, max_uses budget, stats tracking, and fallback.

from __future__ import annotations

import json

from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.contracts.advisor import AdvisorConfig


def _advisor_json() -> str:
    return json.dumps(
        {
            "advice": "Check clause 4.3",
            "suggested_action": "re-read the standards doc",
            "confidence": 0.8,
            "reasoning": "The formula is in the referenced standard",
        }
    )


class TestPydanticAiAdvisorTool:
    def test_initial_usage_is_zero(self) -> None:
        from aec_bench.adapters.tool_loop_local import PydanticAiAdvisorTool

        tool = PydanticAiAdvisorTool(
            client=ReplayRlmClient([]),
            config=AdvisorConfig(model="advisor-model", max_uses=3),
        )
        assert tool.usage() == (0, 0, 0)

    def test_call_returns_advice_json_and_increments_stats(self) -> None:
        from aec_bench.adapters.tool_loop_local import PydanticAiAdvisorTool

        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=500,
                    output_tokens=200,
                ),
            ]
        )
        tool = PydanticAiAdvisorTool(
            client=advisor_client,
            config=AdvisorConfig(model="advisor-model", max_uses=3),
        )

        result = tool("calculate voltage drop", "unsure which formula to use")
        parsed = json.loads(result)

        assert parsed["advice"] == "Check clause 4.3"
        assert parsed["confidence"] == 0.8
        assert tool.usage() == (1, 500, 200)

    def test_multiple_calls_accumulate(self) -> None:
        from aec_bench.adapters.tool_loop_local import PydanticAiAdvisorTool

        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=300,
                    output_tokens=100,
                ),
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=400,
                    output_tokens=150,
                ),
            ]
        )
        tool = PydanticAiAdvisorTool(
            client=advisor_client,
            config=AdvisorConfig(model="advisor-model", max_uses=5),
        )

        tool("g1", "p1")
        tool("g2", "p2")

        assert tool.usage() == (2, 700, 250)

    def test_exhausted_budget_returns_exhaustion_message(self) -> None:
        from aec_bench.adapters.tool_loop_local import PydanticAiAdvisorTool

        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=100,
                    output_tokens=50,
                ),
            ]
        )
        tool = PydanticAiAdvisorTool(
            client=advisor_client,
            config=AdvisorConfig(model="advisor-model", max_uses=1),
        )

        first = json.loads(tool("g1", "p1"))
        assert first["advice"] == "Check clause 4.3"

        second = json.loads(tool("g2", "p2"))
        assert "exhausted" in second["advice"].lower()
        assert second["confidence"] == 0.0
        assert tool.usage() == (1, 100, 50)


class TestPydanticAiAdvisorToolCallWithMessages:
    def test_call_with_messages_increments_stats(self) -> None:
        from aec_bench.adapters.tool_loop_local import PydanticAiAdvisorTool

        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=700,
                    output_tokens=300,
                ),
            ]
        )
        tool = PydanticAiAdvisorTool(
            client=advisor_client,
            config=AdvisorConfig(model="advisor-model", max_uses=3),
        )

        transcript = [
            {"role": "user", "content": "Size a cable for 60 A over 20 m."},
            {"role": "assistant", "content": "I'll check the tables first."},
            {"role": "tool", "content": "[bash] 25mm2 Cu: 0.9 mV/A/m"},
        ]
        result = tool.call_with_messages(transcript)
        parsed = json.loads(result)

        assert parsed["advice"] == "Check clause 4.3"
        assert tool.usage() == (1, 700, 300)

    def test_call_with_messages_respects_budget(self) -> None:
        from aec_bench.adapters.tool_loop_local import PydanticAiAdvisorTool

        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=100,
                    output_tokens=50,
                ),
            ]
        )
        tool = PydanticAiAdvisorTool(
            client=advisor_client,
            config=AdvisorConfig(model="advisor-model", max_uses=1),
        )

        first = json.loads(tool.call_with_messages([{"role": "user", "content": "x"}]))
        assert first["advice"] == "Check clause 4.3"
        second = json.loads(tool.call_with_messages([{"role": "user", "content": "y"}]))
        assert "exhausted" in second["advice"].lower()


class TestPydanticAiMessagesToAdvisorContext:
    def test_converts_system_user_assistant_tool_parts(self) -> None:
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            SystemPromptPart,
            TextPart,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        from aec_bench.adapters.tool_loop_local import (
            pydantic_ai_messages_to_advisor_context,
        )

        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="You are an expert engineer."),
                    UserPromptPart(content="Size a cable for 60 A."),
                ]
            ),
            ModelResponse(
                parts=[
                    TextPart(content="I'll check the tables."),
                    ToolCallPart(
                        tool_name="bash",
                        args={"command": "cat cable.csv"},
                        tool_call_id="c1",
                    ),
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="bash",
                        content="25mm2: 0.9 mV/A/m",
                        tool_call_id="c1",
                    )
                ]
            ),
        ]

        ctx = pydantic_ai_messages_to_advisor_context(messages)
        roles = [m["role"] for m in ctx]
        # System prompt is intentionally skipped — advisor has its own.
        assert "system" not in roles
        assert roles[0] == "user"
        assert "Size a cable" in ctx[0]["content"]
        assistant_entries = [m for m in ctx if m["role"] == "assistant"]
        assert any("I'll check" in m["content"] for m in assistant_entries)
        tool_entries = [m for m in ctx if m["role"] == "tool"]
        assert any("0.9 mV/A/m" in m["content"] for m in tool_entries)
