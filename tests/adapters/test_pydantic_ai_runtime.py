# ABOUTME: Tests additive streaming fallbacks for PydanticAI-backed adapters.
# ABOUTME: Ensures provider streaming is an internal transport detail, not a harness contract.

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.usage import RequestUsage

from aec_bench.adapters.pydantic_ai_runtime import (
    request_model_response,
    should_retry_with_streaming,
)


class _StreamedResponse:
    def __init__(self, response: ModelResponse) -> None:
        self._response = response
        self.iterated = False

    def __aiter__(self) -> AsyncIterator[object]:
        async def _events() -> AsyncIterator[object]:
            self.iterated = True
            if False:  # pragma: no cover - keeps this as an async generator.
                yield object()

        return _events()

    def get(self) -> ModelResponse:
        return self._response


class _FakeModel:
    def __init__(self, *, request_response: ModelResponse | BaseException, stream_response: ModelResponse) -> None:
        self.request_response = request_response
        self.stream_response = stream_response
        self.request_calls = 0
        self.stream_calls = 0
        self.last_streamed: _StreamedResponse | None = None

    async def request(self, messages: list[Any], model_settings: Any, model_request_parameters: Any) -> ModelResponse:
        del messages, model_settings, model_request_parameters
        self.request_calls += 1
        if isinstance(self.request_response, BaseException):
            raise self.request_response
        return self.request_response

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[Any],
        model_settings: Any,
        model_request_parameters: Any,
    ) -> AsyncIterator[_StreamedResponse]:
        del messages, model_settings, model_request_parameters
        self.stream_calls += 1
        streamed = _StreamedResponse(self.stream_response)
        self.last_streamed = streamed
        yield streamed


def _response(text: str, *, input_tokens: int = 0, output_tokens: int = 0) -> ModelResponse:
    return ModelResponse(
        parts=[TextPart(content=text)],
        usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_streaming_required_detection_matches_together_error() -> None:
    assert should_retry_with_streaming(
        "status_code: 400, body: {'message': 'This model only supports streaming. Set \"stream\": true.', "
        "'code': 'streaming_required'}"
    )


def test_request_model_response_uses_non_streaming_first() -> None:
    model = _FakeModel(
        request_response=_response("non-stream", input_tokens=3, output_tokens=2),
        stream_response=_response("stream"),
    )

    result = request_model_response(
        model,
        messages=[],
        model_settings=None,
        model_request_parameters=None,
        stream_mode="auto",
    )

    assert result.parts == [TextPart(content="non-stream")]
    assert result.usage.input_tokens == 3
    assert model.request_calls == 1
    assert model.stream_calls == 0


def test_request_model_response_retries_streaming_when_provider_requires_it() -> None:
    model = _FakeModel(
        request_response=RuntimeError("streaming_required: set stream=true"),
        stream_response=_response("streamed", input_tokens=5, output_tokens=4),
    )

    result = request_model_response(
        model,
        messages=[],
        model_settings=None,
        model_request_parameters=None,
        stream_mode="auto",
    )

    assert result.parts == [TextPart(content="streamed")]
    assert result.usage.output_tokens == 4
    assert model.request_calls == 1
    assert model.stream_calls == 1
    assert model.last_streamed is not None
    assert model.last_streamed.iterated is True


def test_request_model_response_never_streaming_preserves_provider_error() -> None:
    model = _FakeModel(
        request_response=RuntimeError("streaming_required: set stream=true"),
        stream_response=_response("streamed"),
    )

    with pytest.raises(RuntimeError, match="streaming_required"):
        request_model_response(
            model,
            messages=[],
            model_settings=None,
            model_request_parameters=None,
            stream_mode="never",
        )

    assert model.request_calls == 1
    assert model.stream_calls == 0


def test_request_model_response_always_streaming_skips_non_streaming_call() -> None:
    model = _FakeModel(
        request_response=_response("non-stream"),
        stream_response=_response("streamed"),
    )

    result = request_model_response(
        model,
        messages=[],
        model_settings=None,
        model_request_parameters=None,
        stream_mode="always",
    )

    assert result.parts == [TextPart(content="streamed")]
    assert model.request_calls == 0
    assert model.stream_calls == 1
