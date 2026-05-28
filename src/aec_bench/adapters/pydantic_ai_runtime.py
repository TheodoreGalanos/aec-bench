# ABOUTME: Shared PydanticAI runtime helpers for provider transport compatibility.
# ABOUTME: Keeps streaming fallback inside adapters while preserving harness result contracts.

from __future__ import annotations

import asyncio
from typing import Any, Literal, cast

StreamMode = Literal["never", "auto", "always"]

_STREAM_MODES: set[str] = {"never", "auto", "always"}


def normalise_stream_mode(value: str | None) -> StreamMode:
    """Return the configured stream mode, defaulting to additive auto fallback."""
    if value is None:
        return "auto"
    normalised = value.strip().lower()
    if normalised not in _STREAM_MODES:
        msg = f"unknown stream mode: {value!r}"
        raise ValueError(msg)
    return cast(StreamMode, normalised)


def should_retry_with_streaming(error: BaseException | str) -> bool:
    """Return True when a provider error says the request must be streamed."""
    text = str(error).lower()
    return (
        "streaming_required" in text
        or "only supports streaming" in text
        or '"stream": true' in text
        or "'stream': true" in text
        or "stream=true" in text
    )


def request_model_response(
    model: Any,
    *,
    messages: list[Any],
    model_settings: Any | None,
    model_request_parameters: Any,
    stream_mode: str | None = "auto",
) -> Any:
    """Call ``Model.request`` with optional streaming fallback.

    Non-streaming requests remain the primary path in ``auto`` mode. Streaming
    is used only when explicitly requested or when the provider reports that the
    model requires streaming.
    """
    mode = normalise_stream_mode(stream_mode)
    return _run_async(
        _request_model_response_async(
            model,
            messages=messages,
            model_settings=model_settings,
            model_request_parameters=model_request_parameters,
            stream_mode=mode,
        )
    )


async def _request_model_response_async(
    model: Any,
    *,
    messages: list[Any],
    model_settings: Any | None,
    model_request_parameters: Any,
    stream_mode: StreamMode,
) -> Any:
    if stream_mode == "always":
        return await _request_stream_response(
            model,
            messages=messages,
            model_settings=model_settings,
            model_request_parameters=model_request_parameters,
        )

    try:
        return await model.request(
            messages,
            model_settings,
            model_request_parameters,
        )
    except Exception as exc:
        if stream_mode == "auto" and should_retry_with_streaming(exc):
            return await _request_stream_response(
                model,
                messages=messages,
                model_settings=model_settings,
                model_request_parameters=model_request_parameters,
            )
        raise


async def _request_stream_response(
    model: Any,
    *,
    messages: list[Any],
    model_settings: Any | None,
    model_request_parameters: Any,
) -> Any:
    async with model.request_stream(
        messages,
        model_settings,
        model_request_parameters,
    ) as streamed_response:
        async for _event in streamed_response:
            pass
        response = streamed_response.get()
    return response


def run_agent_sync_with_streaming_fallback(
    agent: Any,
    user_prompt: Any,
    *,
    stream_mode: str | None = "auto",
    **kwargs: Any,
) -> Any:
    """Run a PydanticAI Agent with optional streaming fallback."""
    mode = normalise_stream_mode(stream_mode)
    if mode == "always":
        return _run_agent_stream_sync(agent, user_prompt, **kwargs)

    try:
        return agent.run_sync(user_prompt, **kwargs)
    except Exception as exc:
        if mode == "auto" and should_retry_with_streaming(exc):
            return _run_agent_stream_sync(agent, user_prompt, **kwargs)
        raise


def agent_run_output(result: Any) -> Any:
    """Return output from either a normal AgentRunResult or streamed result."""
    if hasattr(result, "get_output"):
        return result.get_output()
    return result.output


def _run_agent_stream_sync(agent: Any, user_prompt: Any, **kwargs: Any) -> Any:
    return agent.run_stream_sync(user_prompt, **kwargs)


def _run_async(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
