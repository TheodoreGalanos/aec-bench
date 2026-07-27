# ABOUTME: Tests runtime budgets passed into the PydanticAI-managed tool loop.
# ABOUTME: Verifies provider requests and native tool calls share the lowered hard limits.

from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import RunUsage

from aec_bench.adapters.base import AdapterFailureKind
from aec_bench.adapters.tool_loop import ToolLoopRequest
from aec_bench.adapters.tool_loop_local import PydanticAiToolLoopClient


def test_pydantic_ai_tool_loop_receives_request_and_tool_call_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _Result:
        def usage(self) -> SimpleNamespace:
            return SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_tokens=0,
                cache_write_tokens=0,
                requests=3,
            )

    def record_run(*args: Any, **kwargs: Any) -> _Result:
        captured.update(kwargs)
        return _Result()

    monkeypatch.setattr(
        "aec_bench.adapters.tool_loop_local.run_agent_sync_with_streaming_fallback",
        record_run,
    )
    monkeypatch.setattr("aec_bench.adapters.tool_loop_local.agent_run_output", lambda _result: "done")

    client = PydanticAiToolLoopClient.__new__(PydanticAiToolLoopClient)
    client.__dict__["_agent"] = SimpleNamespace(_system_prompts=())
    client._stream_mode = "auto"
    client._trajectory_writer = None

    response = client._run_agent(
        ToolLoopRequest(
            model="test-model",
            instruction="Use at most two tools.",
            configuration={"max_turns": 3, "max_tool_calls": 2},
        )
    )

    usage_limits = captured["usage_limits"]
    assert usage_limits.request_limit == 3
    assert usage_limits.tool_calls_limit == 2
    assert response.done is True
    assert response.usage_model_calls == 3


def test_pydantic_ai_usage_limit_failure_does_not_recover_workspace_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "output.md").write_text("partial output must not bypass the limit", encoding="utf-8")
    client = PydanticAiToolLoopClient.__new__(PydanticAiToolLoopClient)
    client._workspace = str(tmp_path)

    def exceed_limit(_request: ToolLoopRequest) -> NoReturn:
        raise UsageLimitExceeded("tool_calls_limit of 1")

    monkeypatch.setattr(client, "_run_agent", exceed_limit)

    response = client.next_turn(
        ToolLoopRequest(
            model="test-model",
            instruction="Stop at the hard limit.",
            configuration={"max_turns": 2, "max_tool_calls": 1},
        )
    )

    assert response.output_text == ""
    assert response.error_message == "tool_calls_limit of 1"
    assert response.failure_kind is AdapterFailureKind.TOOL_CALL_LIMIT_REACHED
    assert response.done is True


def test_pydantic_ai_request_limit_failure_preserves_partial_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def exceed_limit(*args: Any, **kwargs: Any) -> NoReturn:
        usage = kwargs["usage"]
        assert isinstance(usage, RunUsage)
        usage.incr(
            RunUsage(
                requests=3,
                tool_calls=2,
                input_tokens=120,
                output_tokens=30,
                cache_read_tokens=40,
                cache_write_tokens=10,
            )
        )
        raise UsageLimitExceeded("The next request would exceed the request_limit of 3")

    monkeypatch.setattr(
        "aec_bench.adapters.tool_loop_local.run_agent_sync_with_streaming_fallback",
        exceed_limit,
    )

    client = PydanticAiToolLoopClient.__new__(PydanticAiToolLoopClient)
    client.__dict__["_agent"] = SimpleNamespace(_system_prompts=())
    client._stream_mode = "auto"
    client._trajectory_writer = None

    response = client.next_turn(
        ToolLoopRequest(
            model="test-model",
            instruction="Stop at the hard limit.",
            configuration={"max_turns": 3},
        )
    )

    assert response.output_text == ""
    assert response.error_message == "The next request would exceed the request_limit of 3"
    assert response.failure_kind is AdapterFailureKind.TURN_LIMIT_REACHED
    assert response.usage_model_calls == 3
    assert response.usage_input_tokens == 120
    assert response.usage_output_tokens == 30
    assert response.usage_cache_read_tokens == 40
    assert response.usage_cache_write_tokens == 10
    assert response.done is True
