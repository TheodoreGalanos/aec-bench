# ABOUTME: Tests for the tool-loop adapter path in aec-bench Python.
# ABOUTME: Covers declared-tool enforcement, transcript completeness, and config recording.

from dataclasses import dataclass, field
from typing import Any

from aec_bench.adapters.base import AdapterFailureKind, AdapterRequest
from aec_bench.adapters.tool_loop import (
    ReplayToolLoopClient,
    ToolCall,
    ToolExecutionResult,
    ToolLoopAdapter,
    ToolLoopCompletionResponse,
    ToolLoopRequest,
)
from aec_bench.adapters.transcript import TranscriptEvent, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.task_definition import ToolSpec


@dataclass
class ScriptedToolLoopClient:
    responses: list[ToolLoopCompletionResponse]
    requests: list[ToolLoopRequest] = field(default_factory=list)

    def next_turn(self, request: ToolLoopRequest) -> ToolLoopCompletionResponse:
        self.requests.append(request)
        return self.responses.pop(0)


@dataclass
class RecordingToolExecutor:
    results: dict[str, ToolExecutionResult]
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        self.calls.append((tool_name, arguments))
        return self.results[tool_name]


def test_tool_loop_adapter_executes_declared_tool_and_records_transcript() -> None:
    client = ScriptedToolLoopClient(
        responses=[
            ToolLoopCompletionResponse(
                tool_call=ToolCall(
                    tool_call_id="call-1",
                    tool_name="codes_search",
                    arguments={"query": "egress width"},
                )
            ),
            ToolLoopCompletionResponse(
                output_text="Final answer in JSONL.",
                usage_input_tokens=210,
                usage_output_tokens=80,
                done=True,
            ),
        ]
    )
    executor = RecordingToolExecutor(
        results={
            "codes_search": ToolExecutionResult(
                output_text='{"matches": []}',
            )
        }
    )
    adapter = ToolLoopAdapter(
        adapter_name="tool-loop-test",
        model_name="fast",
        client=client,
        tool_executor=executor,
        aliases={"fast": "gpt-5.4-mini"},
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Use the declared tools and write /workspace/output.jsonl.",
            system_prompt="Use tools only when needed.",
            tools=[
                ToolSpec(
                    name="codes_search",
                    source="environment/codes_search.py",
                    description="Search code references.",
                )
            ],
            configuration={"max_turns": 4},
        )
    )

    assert executor.calls == [("codes_search", {"query": "egress width"})]
    assert client.requests[0].model == "gpt-5.4-mini"
    assert result.configuration_record == {"model": "gpt-5.4-mini", "max_turns": 4}
    assert result.failure_kind is None
    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert [entry.event for entry in result.transcript] == [
        TranscriptEvent.MESSAGE,
        TranscriptEvent.MESSAGE,
        TranscriptEvent.TOOL_CALL,
        TranscriptEvent.TOOL_RESULT,
        TranscriptEvent.MESSAGE,
    ]
    assert [entry.role for entry in result.transcript] == [
        TranscriptRole.SYSTEM,
        TranscriptRole.USER,
        TranscriptRole.ASSISTANT,
        TranscriptRole.TOOL,
        TranscriptRole.ASSISTANT,
    ]


def test_tool_loop_adapter_rejects_undeclared_tool_request() -> None:
    client = ScriptedToolLoopClient(
        responses=[
            ToolLoopCompletionResponse(
                tool_call=ToolCall(
                    tool_call_id="call-1",
                    tool_name="bash",
                    arguments={"command": "ls"},
                )
            )
        ]
    )
    executor = RecordingToolExecutor(results={})
    adapter = ToolLoopAdapter(
        adapter_name="tool-loop-test",
        model_name="gpt-5.4",
        client=client,
        tool_executor=executor,
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Use tools if necessary and write /workspace/output.jsonl.",
        )
    )

    assert executor.calls == []
    assert result.failure_kind is AdapterFailureKind.UNDECLARED_TOOL_REQUEST
    assert result.agent_output.status is AgentOutputStatus.FAILED
    assert result.agent_output.error_message == "undeclared tool requested: bash"
    assert result.transcript[-1].event is TranscriptEvent.TOOL_RESULT
    assert result.transcript[-1].content == "undeclared tool requested: bash"


def test_tool_loop_adapter_classifies_turn_limit_reached() -> None:
    client = ScriptedToolLoopClient(
        responses=[
            ToolLoopCompletionResponse(
                output_text="",
                done=False,
            )
        ]
    )
    executor = RecordingToolExecutor(results={})
    adapter = ToolLoopAdapter(
        adapter_name="tool-loop-test",
        model_name="gpt-5.4",
        client=client,
        tool_executor=executor,
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Use tools if necessary and write /workspace/output.jsonl.",
            configuration={"max_turns": 1},
        )
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.TURN_LIMIT_REACHED


def test_tool_loop_adapter_classifies_provider_timeout() -> None:
    client = ScriptedToolLoopClient(
        responses=[
            ToolLoopCompletionResponse(
                error_message="provider timeout",
                timed_out=True,
            )
        ]
    )
    executor = RecordingToolExecutor(results={})
    adapter = ToolLoopAdapter(
        adapter_name="tool-loop-test",
        model_name="gpt-5.4",
        client=client,
        tool_executor=executor,
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Use tools if necessary and write /workspace/output.jsonl.",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.FAILED
    assert result.failure_kind is AdapterFailureKind.TIMEOUT


def test_tool_loop_adapter_surfaces_tool_error_to_model_and_continues() -> None:
    client = ScriptedToolLoopClient(
        responses=[
            ToolLoopCompletionResponse(
                tool_call=ToolCall(
                    tool_call_id="call-1",
                    tool_name="codes_search",
                    arguments={"query": "egress width"},
                )
            ),
            ToolLoopCompletionResponse(
                output_text="Recovered after tool failure.",
                usage_input_tokens=300,
                usage_output_tokens=100,
                done=True,
            ),
        ]
    )
    executor = RecordingToolExecutor(
        results={
            "codes_search": ToolExecutionResult(
                output_text="",
                error_message="codes_search failed with exit code 1",
            )
        }
    )
    adapter = ToolLoopAdapter(
        adapter_name="tool-loop-test",
        model_name="gpt-5.4",
        client=client,
        tool_executor=executor,
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Use the declared tools and write /workspace/output.jsonl.",
            tools=[
                ToolSpec(
                    name="codes_search",
                    source="environment/codes_search.py",
                    description="Search code references.",
                )
            ],
            configuration={"max_turns": 4},
        )
    )

    assert executor.calls == [("codes_search", {"query": "egress width"})]
    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.failure_kind is None

    tool_result_entry = [e for e in result.transcript if e.event is TranscriptEvent.TOOL_RESULT][0]
    assert "exit code 1" in tool_result_entry.content

    assert result.transcript[-1].role is TranscriptRole.ASSISTANT
    assert "Recovered" in result.transcript[-1].content


def test_tool_loop_adapter_serializes_remote_execution_spec() -> None:
    adapter = ToolLoopAdapter(
        adapter_name="tool-loop-test",
        model_name="fast",
        client=ReplayToolLoopClient(
            responses=[
                ToolLoopCompletionResponse(
                    output_text="Final answer in JSONL.",
                    usage_input_tokens=210,
                    usage_output_tokens=80,
                    done=True,
                )
            ]
        ),
        tool_executor=RecordingToolExecutor(results={}),
        aliases={"fast": "gpt-5.4-mini"},
    )

    execution = adapter.serialize_execution()

    assert execution.adapter_kind == "tool_loop"
    assert execution.adapter_name == "tool-loop-test"
    assert execution.resolved_model == "gpt-5.4-mini"
    assert execution.payload == {
        "client": {
            "client_kind": "replay",
            "payload": {
                "responses": [
                    {
                        "output_text": "Final answer in JSONL.",
                        "tool_call": None,
                        "error_message": None,
                        "usage_input_tokens": 210,
                        "usage_output_tokens": 80,
                        "timed_out": False,
                        "done": True,
                    }
                ]
            },
        }
    }
