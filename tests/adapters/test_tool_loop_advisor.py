# ABOUTME: Tests for advisor tool integration in the tool-loop adapter.
# ABOUTME: Verifies advisor tool interception, call handling, max_uses enforcement, and fallback.

import json
from dataclasses import dataclass, field
from typing import Any

from aec_bench.adapters.base import AdapterFailureKind, AdapterRequest
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.tool_loop import (
    ReplayToolLoopClient,
    ToolCall,
    ToolExecutionResult,
    ToolLoopAdapter,
    ToolLoopCompletionResponse,
)
from aec_bench.adapters.transcript import TranscriptEvent, TranscriptRole
from aec_bench.contracts.advisor import AdvisorConfig
from aec_bench.contracts.agent_output import AgentOutputStatus


def _advisor_json() -> str:
    """Return a valid advisor response JSON string."""
    return json.dumps(
        {
            "advice": "Check clause 4.3",
            "suggested_action": "re-read the standards doc",
            "confidence": 0.8,
            "reasoning": "The formula is in the referenced standard",
        }
    )


@dataclass
class RecordingToolExecutor:
    """Captures tool calls for assertion without executing anything real."""

    results: dict[str, ToolExecutionResult]
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        self.calls.append((tool_name, arguments))
        return self.results[tool_name]


class TestToolLoopAdvisorCallHandled:
    """Advisor tool call is intercepted and handled via the advisor client."""

    def test_advisor_tool_call_produces_transcript_and_completes(self) -> None:
        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=500,
                    output_tokens=200,
                ),
            ]
        )
        main_client = ReplayToolLoopClient(
            [
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_1",
                        tool_name="advisor",
                        arguments={
                            "goal": "calculate voltage drop",
                            "problem": "unsure which formula to use",
                        },
                    ),
                ),
                ToolLoopCompletionResponse(
                    output_text="The voltage drop is 3.2%",
                    done=True,
                ),
            ]
        )

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=RecordingToolExecutor(results={}),
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="advisor-model", max_uses=3),
        )
        result = adapter.execute(AdapterRequest(instruction="Calculate voltage drop"))

        assert result.failure_kind is None
        assert result.agent_output.status is AgentOutputStatus.COMPLETED

        # Transcript should include the advisor tool call and its result
        events = [e.event for e in result.transcript]
        assert TranscriptEvent.TOOL_CALL in events
        assert TranscriptEvent.TOOL_RESULT in events

        # The tool result should contain the advisor's advice
        tool_results = [e for e in result.transcript if e.event is TranscriptEvent.TOOL_RESULT]
        assert len(tool_results) == 1
        parsed = json.loads(tool_results[0].content)
        assert parsed["advice"] == "Check clause 4.3"
        assert parsed["confidence"] == 0.8

    def test_advisor_tool_call_does_not_reach_tool_executor(self) -> None:
        """Advisor calls are intercepted before the normal tool dispatch path."""
        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=100,
                    output_tokens=50,
                ),
            ]
        )
        main_client = ReplayToolLoopClient(
            [
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_1",
                        tool_name="advisor",
                        arguments={"goal": "g", "problem": "p"},
                    ),
                ),
                ToolLoopCompletionResponse(output_text="done", done=True),
            ]
        )
        executor = RecordingToolExecutor(results={})

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=executor,
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="advisor-model", max_uses=3),
        )
        adapter.execute(AdapterRequest(instruction="test"))

        assert executor.calls == [], "Advisor tool call should not reach the tool executor"


class TestToolLoopAdvisorMaxUses:
    """Advisor calls are budget-limited via max_uses."""

    def test_advisor_max_uses_enforced(self) -> None:
        """After max_uses calls, further advisor requests return exhaustion message."""
        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=100,
                    output_tokens=50,
                ),
            ]
        )
        main_client = ReplayToolLoopClient(
            [
                # First advisor call — within budget (max_uses=1)
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_1",
                        tool_name="advisor",
                        arguments={"goal": "g1", "problem": "p1"},
                    ),
                ),
                # Second advisor call — over budget
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_2",
                        tool_name="advisor",
                        arguments={"goal": "g2", "problem": "p2"},
                    ),
                ),
                ToolLoopCompletionResponse(output_text="done", done=True),
            ]
        )

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=RecordingToolExecutor(results={}),
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="advisor-model", max_uses=1),
        )
        result = adapter.execute(AdapterRequest(instruction="test"))

        assert result.failure_kind is None

        # Check that the second advisor call returned the exhaustion message
        tool_results = [e for e in result.transcript if e.event is TranscriptEvent.TOOL_RESULT]
        assert len(tool_results) == 2

        # First call: real advisor response
        first_parsed = json.loads(tool_results[0].content)
        assert first_parsed["advice"] == "Check clause 4.3"

        # Second call: budget exhaustion
        second_parsed = json.loads(tool_results[1].content)
        assert "exhausted" in second_parsed["advice"].lower()
        assert second_parsed["confidence"] == 0.0


class TestToolLoopAdvisorWithoutConfig:
    """Without advisor config/client, advisor tool call is treated as undeclared."""

    def test_no_advisor_without_config(self) -> None:
        main_client = ReplayToolLoopClient(
            [
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_1",
                        tool_name="advisor",
                        arguments={"goal": "g", "problem": "p"},
                    ),
                ),
                ToolLoopCompletionResponse(output_text="fallback", done=True),
            ]
        )

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=RecordingToolExecutor(results={}),
        )
        result = adapter.execute(AdapterRequest(instruction="test"))

        # Without advisor config, "advisor" is not in allowed_tools,
        # so it should be treated as an undeclared tool request
        assert result.failure_kind is AdapterFailureKind.UNDECLARED_TOOL_REQUEST

    def test_no_advisor_when_disabled(self) -> None:
        """Even with config, if enabled=False, advisor tool call is undeclared."""
        main_client = ReplayToolLoopClient(
            [
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_1",
                        tool_name="advisor",
                        arguments={"goal": "g", "problem": "p"},
                    ),
                ),
                ToolLoopCompletionResponse(output_text="fallback", done=True),
            ]
        )

        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(output_text=_advisor_json(), input_tokens=100, output_tokens=50),
            ]
        )

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=RecordingToolExecutor(results={}),
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="m", enabled=False),
        )
        result = adapter.execute(AdapterRequest(instruction="test"))

        assert result.failure_kind is AdapterFailureKind.UNDECLARED_TOOL_REQUEST


class TestToolLoopAdvisorTranscriptShape:
    """Advisor tool calls produce the same transcript shape as regular tools."""

    def test_transcript_roles_and_events_match_tool_pattern(self) -> None:
        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=100,
                    output_tokens=50,
                ),
            ]
        )
        main_client = ReplayToolLoopClient(
            [
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_adv",
                        tool_name="advisor",
                        arguments={"goal": "g", "problem": "p"},
                    ),
                ),
                ToolLoopCompletionResponse(output_text="final", done=True),
            ]
        )

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=RecordingToolExecutor(results={}),
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="m"),
        )
        result = adapter.execute(AdapterRequest(instruction="test"))

        roles = [e.role for e in result.transcript]
        events = [e.event for e in result.transcript]

        # Expected: user message, assistant tool_call, tool result, assistant message
        assert roles == [
            TranscriptRole.USER,
            TranscriptRole.ASSISTANT,
            TranscriptRole.TOOL,
            TranscriptRole.ASSISTANT,
        ]
        assert events == [
            TranscriptEvent.MESSAGE,
            TranscriptEvent.TOOL_CALL,
            TranscriptEvent.TOOL_RESULT,
            TranscriptEvent.MESSAGE,
        ]

        # Tool call and result should reference the advisor tool name
        tool_call_entry = result.transcript[1]
        assert tool_call_entry.tool_name == "advisor"
        assert tool_call_entry.tool_call_id == "tc_adv"

        tool_result_entry = result.transcript[2]
        assert tool_result_entry.tool_name == "advisor"
        assert tool_result_entry.tool_call_id == "tc_adv"


class TestToolLoopAdvisorStats:
    """Advisor call count and token usage are surfaced on AdapterResult."""

    def test_single_advisor_call_populates_usage_stats(self) -> None:
        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=500,
                    output_tokens=200,
                ),
            ]
        )
        main_client = ReplayToolLoopClient(
            [
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_1",
                        tool_name="advisor",
                        arguments={"goal": "g", "problem": "p"},
                    ),
                ),
                ToolLoopCompletionResponse(output_text="final", done=True),
            ]
        )

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=RecordingToolExecutor(results={}),
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="advisor-model", max_uses=3),
        )
        result = adapter.execute(AdapterRequest(instruction="test"))

        assert result.usage_advisor_calls == 1
        assert result.usage_advisor_input_tokens == 500
        assert result.usage_advisor_output_tokens == 200

    def test_multiple_advisor_calls_aggregate_stats(self) -> None:
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
        main_client = ReplayToolLoopClient(
            [
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_1",
                        tool_name="advisor",
                        arguments={"goal": "g1", "problem": "p1"},
                    ),
                ),
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_2",
                        tool_name="advisor",
                        arguments={"goal": "g2", "problem": "p2"},
                    ),
                ),
                ToolLoopCompletionResponse(output_text="final", done=True),
            ]
        )

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=RecordingToolExecutor(results={}),
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="advisor-model", max_uses=5),
        )
        result = adapter.execute(AdapterRequest(instruction="test"))

        assert result.usage_advisor_calls == 2
        assert result.usage_advisor_input_tokens == 700
        assert result.usage_advisor_output_tokens == 250

    def test_no_advisor_config_leaves_stats_unset(self) -> None:
        main_client = ReplayToolLoopClient(
            [
                ToolLoopCompletionResponse(output_text="final", done=True),
            ]
        )

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=RecordingToolExecutor(results={}),
        )
        result = adapter.execute(AdapterRequest(instruction="test"))

        assert result.usage_advisor_calls is None
        assert result.usage_advisor_input_tokens is None
        assert result.usage_advisor_output_tokens is None

    def test_client_reported_advisor_usage_overrides_adapter_intercept(self) -> None:
        """Clients that handle advisor internally (PydanticAI) expose
        ``advisor_usage()``; the adapter should prefer those counts over its
        own intercept counters, which stay at zero on that path."""

        class ClientWithAdvisorUsage:
            """Fake client that completes immediately and reports advisor stats."""

            def __init__(self) -> None:
                self._called = False

            def next_turn(self, request):  # type: ignore[no-untyped-def]
                self._called = True
                return ToolLoopCompletionResponse(output_text="done", done=True)

            def advisor_usage(self) -> tuple[int, int, int]:
                return (4, 1200, 350)

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=ClientWithAdvisorUsage(),
            tool_executor=RecordingToolExecutor(results={}),
            advisor_client=ReplayRlmClient([]),
            advisor_config=AdvisorConfig(model="advisor-model", max_uses=5),
        )
        result = adapter.execute(AdapterRequest(instruction="test"))

        assert result.usage_advisor_calls == 4
        assert result.usage_advisor_input_tokens == 1200
        assert result.usage_advisor_output_tokens == 350

    def test_exhausted_calls_not_counted(self) -> None:
        """Calls past max_uses return fallback JSON and should not bump call count."""
        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=100,
                    output_tokens=50,
                ),
            ]
        )
        main_client = ReplayToolLoopClient(
            [
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_1",
                        tool_name="advisor",
                        arguments={"goal": "g1", "problem": "p1"},
                    ),
                ),
                ToolLoopCompletionResponse(
                    tool_call=ToolCall(
                        tool_call_id="tc_2",
                        tool_name="advisor",
                        arguments={"goal": "g2", "problem": "p2"},
                    ),
                ),
                ToolLoopCompletionResponse(output_text="final", done=True),
            ]
        )

        adapter = ToolLoopAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            tool_executor=RecordingToolExecutor(results={}),
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="advisor-model", max_uses=1),
        )
        result = adapter.execute(AdapterRequest(instruction="test"))

        assert result.usage_advisor_calls == 1
        assert result.usage_advisor_input_tokens == 100
        assert result.usage_advisor_output_tokens == 50
