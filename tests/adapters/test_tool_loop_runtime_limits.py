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
    client._last_request_usages = ()

    response = client._run_agent(
        ToolLoopRequest(
            model="test-model",
            instruction="Use at most two tools.",
            configuration={
                "max_turns": 3,
                "max_tool_calls": 2,
                "max_input_tokens": 500_000,
                "max_total_tokens": 500_000,
                "max_output_tokens_per_call": 2_048,
                "count_tokens_before_request": True,
            },
        )
    )

    usage_limits = captured["usage_limits"]
    assert usage_limits.request_limit == 3
    assert usage_limits.tool_calls_limit == 2
    assert usage_limits.input_tokens_limit == 500_000
    assert usage_limits.total_tokens_limit == 500_000
    assert usage_limits.count_tokens_before_request is True
    assert captured["model_settings"] == {"max_tokens": 2_048}
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
    client._last_request_usages = ()

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


def test_pydantic_ai_host_tool_error_preserves_partial_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_after_response(*args: Any, **kwargs: Any) -> NoReturn:
        usage = kwargs["usage"]
        assert isinstance(usage, RunUsage)
        usage.incr(
            RunUsage(
                requests=1,
                input_tokens=12_345,
                output_tokens=678,
                cache_read_tokens=0,
                cache_write_tokens=0,
            )
        )
        raise RuntimeError("artifact-integrity: commit does not extend its parent")

    monkeypatch.setattr(
        "aec_bench.adapters.tool_loop_local.run_agent_sync_with_streaming_fallback",
        fail_after_response,
    )

    client = PydanticAiToolLoopClient.__new__(PydanticAiToolLoopClient)
    client.__dict__["_agent"] = SimpleNamespace(_system_prompts=())
    client._workspace = ""
    client._stream_mode = "auto"
    client._trajectory_writer = None
    client._last_request_usages = ()

    response = client.next_turn(
        ToolLoopRequest(
            model="test-model",
            instruction="Use the closed station tools.",
            configuration={"max_turns": 3},
        )
    )

    assert response.error_message == "artifact-integrity: commit does not extend its parent"
    assert response.failure_kind is AdapterFailureKind.PROVIDER_ERROR
    assert response.usage_model_calls == 1
    assert response.usage_input_tokens == 12_345
    assert response.usage_output_tokens == 678
    assert response.usage_cache_read_tokens == 0
    assert response.usage_cache_write_tokens == 0
    assert response.done is True


def test_pydantic_ai_tool_loop_records_per_request_token_maxima(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.usage import RequestUsage

    class _Result:
        def usage(self) -> RunUsage:
            return RunUsage(
                requests=2,
                input_tokens=1_700,
                output_tokens=350,
            )

        def all_messages(self) -> list[ModelResponse]:
            return [
                ModelResponse(
                    parts=[TextPart(content="first")],
                    usage=RequestUsage(input_tokens=700, output_tokens=150),
                ),
                ModelResponse(
                    parts=[TextPart(content="second")],
                    usage=RequestUsage(input_tokens=1_000, output_tokens=200),
                ),
            ]

    monkeypatch.setattr(
        "aec_bench.adapters.tool_loop_local.run_agent_sync_with_streaming_fallback",
        lambda *args, **kwargs: _Result(),
    )
    monkeypatch.setattr(
        "aec_bench.adapters.tool_loop_local.agent_run_output",
        lambda _result: "done",
    )

    client = PydanticAiToolLoopClient.__new__(PydanticAiToolLoopClient)
    client.__dict__["_agent"] = SimpleNamespace(_system_prompts=())
    client._stream_mode = "auto"
    client._trajectory_writer = None
    client._last_request_usages = ()

    response = client._run_agent(
        ToolLoopRequest(
            model="test-model",
            instruction="Finish.",
            configuration={"max_turns": 2},
        )
    )

    assert response.maximum_input_tokens_in_one_call == 1_000
    assert response.maximum_output_tokens_in_one_call == 200
    assert client.last_request_usages() == ((700, 150), (1_000, 200))
