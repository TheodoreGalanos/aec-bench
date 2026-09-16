# ABOUTME: Records one delegated RLM-client call without changing its request, result, or accounting.
# ABOUTME: Shares explicit parent links and child request/response capture across local harnesses.

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from aec_bench.contracts.trajectory import TrajectoryModelResponse, TrajectoryUsage
from aec_bench.trajectory.writer import TrajectoryWriter

if TYPE_CHECKING:
    from aec_bench.adapters.rlm.client import RlmCompletionResponse, RlmMessage


def record_subagent_call(
    call: Callable[[], RlmCompletionResponse],
    *,
    writer: TrajectoryWriter | None,
    parent_tool_call_id: str | None,
    agent_name: str,
    model: str,
    messages: list[RlmMessage],
    system_prompt: str | None,
) -> RlmCompletionResponse:
    """Capture only admitted child calls, with a separate trace for each invocation."""
    if writer is None or parent_tool_call_id is None:
        return call()
    child = writer.subagent(parent_tool_call_id=parent_tool_call_id, agent_name=agent_name, model_name=model)
    try:
        if system_prompt:
            child.system(system_prompt)
        for message in messages:
            if message.role == "system":
                child.system(message.content)
            elif message.role == "user":
                child.user(message.content)
            elif message.role == "assistant":
                child.new_step()
                child.assistant(message.content)
            else:
                raise ValueError(f"unsupported delegated request role: {message.role!r}")
        child.new_step()
        try:
            response = call()
        except Exception as exc:
            # Provider exceptions can contain credentials or transport details.
            child.error(type(exc).__name__)
            raise
        usage = TrajectoryUsage(
            input_tokens=response.input_tokens or None,
            output_tokens=response.output_tokens or None,
            cache_read_tokens=response.cache_read_tokens or None,
            cache_write_tokens=response.cache_write_tokens or None,
        )
        child.model_response(
            TrajectoryModelResponse(
                source="rlm_client",
                model_name=model,
                usage=usage if any(usage.model_dump(exclude={"details"}).values()) else None,
            ).model_dump(mode="json", exclude_none=True)
        )
        if response.output_text:
            child.assistant(response.output_text)
        if response.tool_call is not None:
            child.tool_call(response.tool_call.name, response.tool_call.code, tool_call_id=response.tool_call.call_id)
        if response.error_message:
            child.error(response.error_message)
        return response
    finally:
        child.close()
