# ABOUTME: Normalizes one model response into the RLM turn execution surface.
# ABOUTME: Keeps structured tool calls and text-parsed REPL turns immutable and explicit.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from aec_bench.adapters.rlm.client import RlmCompletionResponse
from aec_bench.adapters.rlm.engine import parse_code_blocks, truncate_after_first_block


class TurnExecutionSurface(StrEnum):
    """The response surface that supplied a turn's executable instruction."""

    STRUCTURED_TOOL_CALL = "structured_tool_call"
    TEXT_CODE = "text_code"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class TurnExecution:
    """Immutable execution-facing projection of one model response."""

    surface: TurnExecutionSurface
    output_text: str
    code: str | None
    effective_response: str
    additional_code_block_count: int
    done: bool
    tool_call_name: str | None
    tool_call_id: str | None

    @classmethod
    def from_response(cls, response: RlmCompletionResponse) -> TurnExecution:
        """Normalize structural tool-use and legacy text response surfaces."""
        if response.tool_call is not None:
            return cls(
                surface=TurnExecutionSurface.STRUCTURED_TOOL_CALL,
                output_text=response.output_text,
                code=response.tool_call.code,
                effective_response=response.output_text,
                additional_code_block_count=0,
                done=response.done,
                tool_call_name=response.tool_call.name,
                tool_call_id=response.tool_call.call_id,
            )

        code_blocks = parse_code_blocks(response.output_text)
        if code_blocks:
            return cls(
                surface=TurnExecutionSurface.TEXT_CODE,
                output_text=response.output_text,
                code=code_blocks[0],
                effective_response=truncate_after_first_block(response.output_text),
                additional_code_block_count=len(code_blocks) - 1,
                done=response.done,
                tool_call_name=None,
                tool_call_id=None,
            )

        return cls(
            surface=TurnExecutionSurface.TEXT,
            output_text=response.output_text,
            code=None,
            effective_response=response.output_text,
            additional_code_block_count=0,
            done=response.done,
            tool_call_name=None,
            tool_call_id=None,
        )
