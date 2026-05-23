# ABOUTME: Tests for RLM client data models and replay implementations.
# ABOUTME: Validates RlmCompletionResponse tool_call handling and replay client.

from aec_bench.adapters.rlm.client import (
    ReplayRlmClient,
    RlmCompletionResponse,
    ToolCall,
)


def test_replay_client_returns_scripted_responses() -> None:
    responses = [
        RlmCompletionResponse(output_text="hello", input_tokens=10, output_tokens=5),
    ]
    client = ReplayRlmClient(responses=responses)
    result = client.generate(model="test", messages=[], system_prompt=None)
    assert result.output_text == "hello"


def test_tool_call_dataclass() -> None:
    tc = ToolCall(name="repl", code="x = 1", call_id="call_123")
    assert tc.name == "repl"
    assert tc.code == "x = 1"
    assert tc.call_id == "call_123"


def test_completion_response_with_tool_call() -> None:
    tc = ToolCall(name="repl", code="print(HELP())", call_id="call_456")
    resp = RlmCompletionResponse(
        output_text="Let me check.",
        input_tokens=500,
        output_tokens=100,
        tool_call=tc,
    )
    assert resp.tool_call is not None
    assert resp.tool_call.code == "print(HELP())"
    assert resp.output_text == "Let me check."


def test_completion_response_defaults_no_tool_call() -> None:
    resp = RlmCompletionResponse(output_text="hello", input_tokens=10, output_tokens=5)
    assert resp.tool_call is None
    assert resp.done is False


def test_completion_response_cache_tokens_default_zero() -> None:
    resp = RlmCompletionResponse(output_text="hi", input_tokens=100, output_tokens=50)
    assert resp.cache_read_tokens == 0
    assert resp.cache_write_tokens == 0


def test_completion_response_with_cache_tokens() -> None:
    resp = RlmCompletionResponse(
        output_text="cached",
        input_tokens=1000,
        output_tokens=200,
        cache_read_tokens=800,
        cache_write_tokens=150,
    )
    assert resp.cache_read_tokens == 800
    assert resp.cache_write_tokens == 150
