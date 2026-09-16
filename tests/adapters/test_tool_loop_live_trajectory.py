# ABOUTME: Proves the real PydanticAI tool-loop path publishes completed messages while running.
# ABOUTME: Uses a local FunctionModel to check live tool calls, final deduplication, and failure evidence.

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ThinkingPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from aec_bench.adapters.tool_loop import ToolLoopRequest
from aec_bench.adapters.tool_loop_local import PydanticAiToolLoopClient
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.harness.atif import to_atif
from aec_bench.trajectory.writer import TrajectoryWriter


@pytest.mark.parametrize("fail_second_request", [False, True])
@pytest.mark.parametrize("call_count", [1, 2])
def test_tool_loop_publishes_before_next_model_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_second_request: bool,
    call_count: int,
) -> None:
    source = tmp_path / "trajectory.jsonl"
    requests = 0

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal requests
        requests += 1
        if requests == 1:
            assert read_trajectory(source)[0].content == "Inspect the workspace."
            return ModelResponse(
                parts=[
                    ThinkingPart(content="Inspect the workspace first.", provider_name="test-provider"),
                    TextPart("Check the files."),
                    *[
                        ToolCallPart(tool_name="bash", args='{"command":"pwd"}', tool_call_id=f"call-{index + 1}")
                        for index in range(call_count)
                    ],
                ],
                usage=RequestUsage(
                    input_tokens=120, output_tokens=45, cache_read_tokens=30, details={"reasoning_tokens": 25}
                ),
                model_name="test-model",
                provider_name="test-provider",
                provider_response_id="response-1",
            )
        entries = read_trajectory(source)
        assert any(entry.role == "tool_call" and entry.tool_call_id == "call-1" for entry in entries)
        assert any(entry.role == "tool_result" and entry.tool_call_id == "call-1" for entry in entries)
        reasoning = next(entry for entry in entries if entry.reasoning is not None)
        assert reasoning.reasoning is not None
        assert reasoning.reasoning.content == "Inspect the workspace first."
        model_response = next(entry.model_response for entry in entries if entry.model_response is not None)
        assert model_response.usage is not None
        assert model_response.usage.input_tokens == 120
        if fail_second_request:
            raise RuntimeError("provider unavailable")
        return ModelResponse(parts=[TextPart("Finished.")])

    monkeypatch.setattr("aec_bench.adapters.rlm.providers._build_pydantic_model", lambda *args: FunctionModel(respond))
    monkeypatch.setattr("aec_bench.adapters.rlm.providers._build_model_settings", lambda *args, **kwargs: {})
    writer = TrajectoryWriter(str(source))
    client = PydanticAiToolLoopClient("openai/test", workspace=str(tmp_path), trajectory_writer=writer)
    try:
        response = client.next_turn(ToolLoopRequest(model="openai/test", instruction="Inspect the workspace."))
    finally:
        writer.close()
    assert requests == 2
    entries = read_trajectory(source)
    assert sum(entry.role == "tool_call" for entry in entries) == call_count
    assert sum(entry.role == "tool_result" for entry in entries) == call_count
    assert response.error_message == ("provider unavailable" if fail_second_request else None)
    if not fail_second_request:
        assert entries[-1].content == "Finished."
    trajectory = to_atif(entries, agent_name="tool_loop", agent_version="1")
    assert trajectory.steps[1].observation is not None
    assert trajectory.steps[1].observation.results[0].source_call_id == "call-1"
    assert trajectory.steps[1].reasoning_content == "Inspect the workspace first."
    assert trajectory.steps[1].metrics is not None
    assert trajectory.steps[1].metrics.prompt_tokens == 120
    assert trajectory.steps[1].metrics.completion_tokens == 45
    assert trajectory.steps[1].metrics.cached_tokens == 30
    assert trajectory.steps[1].llm_call_count == 1


def test_trajectory_preserves_malformed_call_without_preventing_model_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "trajectory.jsonl"
    requests = 0

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal requests
        requests += 1
        if requests == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name="bash", args="invalid-json", tool_call_id="bad-call")])
        return ModelResponse(parts=[TextPart("Recovered.")])

    monkeypatch.setattr("aec_bench.adapters.rlm.providers._build_pydantic_model", lambda *args: FunctionModel(respond))
    monkeypatch.setattr("aec_bench.adapters.rlm.providers._build_model_settings", lambda *args, **kwargs: {})
    writer = TrajectoryWriter(str(source))
    client = PydanticAiToolLoopClient("openai/test", workspace=str(tmp_path), trajectory_writer=writer)
    try:
        response = client.next_turn(ToolLoopRequest(model="openai/test", instruction="Inspect the workspace."))
    finally:
        writer.close()
    assert requests == 2
    assert response.output_text == "Recovered."
    entries = read_trajectory(source)
    call = next(entry for entry in entries if entry.role == "tool_call")
    assert call.arguments == {}
    assert call.metadata == {"raw_arguments": "invalid-json"}
