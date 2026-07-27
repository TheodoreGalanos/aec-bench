# ABOUTME: Tests the immutable normalization boundary for one RLM model turn.
# ABOUTME: Covers structured tool calls, text code blocks, and plain text responses.

from dataclasses import FrozenInstanceError

import pytest

from aec_bench.adapters.rlm import TurnExecution, TurnExecutionSurface
from aec_bench.adapters.rlm.client import RlmCompletionResponse, ToolCall


def test_turn_execution_normalizes_a_structured_tool_call() -> None:
    execution = TurnExecution.from_response(
        RlmCompletionResponse(
            output_text="I will calculate this.",
            input_tokens=11,
            output_tokens=7,
            done=False,
            tool_call=ToolCall(
                name="repl",
                code="answer = 6 * 7",
                call_id="call-1",
            ),
        )
    )

    assert execution.surface is TurnExecutionSurface.STRUCTURED_TOOL_CALL
    assert execution.code == "answer = 6 * 7"
    assert execution.effective_response == "I will calculate this."
    assert execution.additional_code_block_count == 0
    assert execution.tool_call_name == "repl"
    assert execution.tool_call_id == "call-1"


def test_turn_execution_normalizes_only_the_first_text_code_block() -> None:
    execution = TurnExecution.from_response(
        RlmCompletionResponse(
            output_text=("First calculation:\n```repl\nx = 1\n```\nSecond calculation:\n```repl\nx = 2\n```"),
            done=True,
        )
    )

    assert execution.surface is TurnExecutionSurface.TEXT_CODE
    assert execution.code == "x = 1"
    assert execution.effective_response == "First calculation:\n```repl\nx = 1\n```"
    assert execution.additional_code_block_count == 1
    assert execution.tool_call_name is None
    assert execution.tool_call_id is None


def test_turn_execution_preserves_plain_text_and_is_immutable() -> None:
    execution = TurnExecution.from_response(
        RlmCompletionResponse(
            output_text="FINAL: complete",
            input_tokens=5,
            output_tokens=2,
            done=True,
        )
    )

    assert execution.surface is TurnExecutionSurface.TEXT
    assert execution.code is None
    assert execution.effective_response == "FINAL: complete"
    assert execution.done is True

    with pytest.raises(FrozenInstanceError):
        execution.code = "changed"  # type: ignore[misc]
