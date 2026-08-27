# ABOUTME: Defines the typed command protocol and provider adapter for AVO.
# ABOUTME: Keeps model composition separate from guarded scratch-tool orchestration.

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from enum import StrEnum
from importlib import import_module
from typing import Any, Literal, Protocol

from pydantic import ConfigDict, Field, field_validator, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.evolution.advice import (
    AVOAdvice,
    AVOAdviceFailure,
    AVOAdviceRecord,
)
from aec_bench.evolution.cancellation import AVOCancellationSignal
from aec_bench.evolution.core import AVOState, CandidateProposalRequest, EvaluatedCandidate
from aec_bench.evolution.memory import AVOMemoryEntry
from aec_bench.evolution.mutation import MutationAction


class AVOTool(StrEnum):
    """Names of the only tools exposed to AVO."""

    INSPECT_PARENT_RESULTS = "inspect_parent_results"
    INSPECT_CURRENT_CANDIDATE = "inspect_current_candidate"
    INSPECT_INSPIRATIONS = "inspect_inspirations"
    INSPECT_PREVIOUS_CYCLES = "inspect_previous_cycles"
    INSPECT_REJECTED_CANDIDATES = "inspect_rejected_candidates"
    READ_PROGRAM_GUIDANCE = "read_program_guidance"
    EDIT_CANDIDATE = "edit_candidate"
    TEST_CANDIDATE = "test_candidate"
    RESTORE_CANDIDATE = "restore_candidate"
    SUBMIT_CANDIDATE = "submit_candidate"
    ABSTAIN = "abstain"
    REQUEST_ADVICE = "request_advice"


class MutationInput(StrictModel):
    """Validated prompt or skill mutation accepted by ``edit_candidate``."""

    model_config = ConfigDict(populate_by_name=True)

    action_type: Literal["write_skill", "modify_skill", "delete_skill", "modify_prompt"] = Field(alias="type")
    skill_name: NonEmptyStr | None = Field(default=None, alias="name")
    skill_description: NonEmptyStr | None = Field(default=None, alias="description")
    skill_discipline: str | None = Field(default=None, alias="discipline")
    skill_body: NonEmptyStr | None = Field(default=None, alias="body")
    prompt_content: NonEmptyStr | None = Field(default=None, alias="content")

    @model_validator(mode="after")
    def validate_action_fields(self) -> MutationInput:
        if self.action_type == "modify_prompt":
            if self.prompt_content is None:
                raise ValueError("modify_prompt requires content")
            return self
        if self.skill_name is None:
            raise ValueError(f"{self.action_type} requires name")
        if self.action_type == "delete_skill":
            return self
        if self.skill_body is None:
            raise ValueError(f"{self.action_type} requires body")
        return self

    def to_action(self) -> MutationAction:
        """Convert the validated command payload to the mutation boundary type."""
        return MutationAction(
            action_type=self.action_type,
            skill_name=self.skill_name,
            skill_description=self.skill_description,
            skill_discipline=self.skill_discipline,
            skill_body=self.skill_body,
            prompt_content=self.prompt_content,
        )


class AVOCommand(StrictModel):
    """One typed tool selection returned by an injected agent runner."""

    tool: AVOTool
    arguments: dict[str, Any] = Field(default_factory=dict)


class AVOResponse(StrictModel):
    """Optional usage-bearing response from an injected model runner."""

    command: AVOCommand
    model_cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    @model_validator(mode="after")
    def validate_cost(self) -> AVOResponse:
        if self.model_cost_usd is not None and (not math.isfinite(self.model_cost_usd) or self.model_cost_usd < 0):
            raise ValueError("model_cost_usd must be finite and non-negative")
        return self

    @field_validator("input_tokens", "output_tokens")
    @classmethod
    def validate_tokens(cls, value: int | None) -> int | None:
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError("token counts must be non-negative integers")
        return value


class AVOContext:
    """Context passed to one injected runner request.

    The context contains no canonical workspace handle. The runner can inspect
    or change scratch only through ``tools``.
    """

    def __init__(
        self,
        *,
        request: CandidateProposalRequest,
        parent_evidence: EvaluatedCandidate,
        state: AVOState,
        tools: Mapping[str, Callable[..., object]],
        previous_tool_result: object | None,
        previous_tool_error: str | None,
        cancellation_signal: AVOCancellationSignal | None = None,
    ) -> None:
        self.request = request
        self.parent_evidence = parent_evidence
        self.state = state
        self.tools = tools
        self.previous_tool_result = previous_tool_result
        self.previous_tool_error = previous_tool_error
        self.cancellation_signal = cancellation_signal
        self.memory: tuple[AVOMemoryEntry, ...] = state.memory
        self.supervision_records: tuple[AVOAdviceRecord, ...] = state.supervision_records

    @property
    def latest_advice(self) -> AVOAdvice | None:
        """Return the latest advice, without treating it as an instruction."""
        if not self.supervision_records:
            return None
        return self.supervision_records[-1].advice

    @property
    def latest_advice_failure(self) -> AVOAdviceFailure | None:
        """Return the latest confirmed supervisor failure, when present."""
        if not self.supervision_records:
            return None
        return self.supervision_records[-1].failure


class AVORunner(Protocol):
    """Narrow provider boundary used by the bounded proposal loop."""

    def __call__(self, context: AVOContext) -> AVOCommand | AVOResponse: ...


ApprovedKnowledgeSource = Callable[[], str] | str


_DEFAULT_AGENT_SYSTEM_PROMPT = (
    "You are a bounded AEC-Bench candidate proposer. Return exactly one typed tool command. "
    "Use only the approved tool names and arguments. Inspect before editing, evaluate changed "
    "material before submission, and submit only an eligible current revision."
)


class PydanticAIAVORunner:
    """Bounded PydanticAI adapter that returns one typed command per request.

    The adapter does not register arbitrary Python tools with the provider.
    It returns the typed command to the loop, which dispatches it through the
    guarded AVO tool map. This keeps provider retries and tool effects inside
    the loop's request and tool budgets.
    """

    def __init__(self, model: Any, *, system_prompt: str = "") -> None:
        self.model = model
        self.system_prompt = system_prompt or _DEFAULT_AGENT_SYSTEM_PROMPT

    def __call__(self, context: AVOContext) -> AVOResponse:
        pydantic_ai = import_module("pydantic_ai")
        usage_module = import_module("pydantic_ai.usage")

        agent = pydantic_ai.Agent(
            self.model,
            system_prompt=self.system_prompt,
            output_type=AVOCommand,
            retries=0,
        )
        result = agent.run_sync(_render_agent_prompt(context), usage_limits=usage_module.UsageLimits(request_limit=1))
        usage = result.usage()
        return AVOResponse(
            command=result.output,
            model_cost_usd=None,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )


def _render_agent_prompt(context: AVOContext) -> str:
    """Render bounded loop state for a structured model request."""
    previous = "No previous tool result."
    if context.previous_tool_error is not None:
        previous = f"Previous tool error: {context.previous_tool_error}"
    elif context.previous_tool_result is not None:
        previous = f"Previous tool result: {context.previous_tool_result!r}"
    names = ", ".join(context.tools)
    request = context.request
    memory = json.dumps(
        [
            {
                "source_variation_id": entry.source_variation_id,
                "source_attempt_id": entry.source_attempt_id,
                "hypothesis": entry.hypothesis,
                "change_summary": entry.change_summary,
                "evidence_summary": entry.evidence_summary,
                "outcome": entry.outcome,
                "failure_category": entry.failure_category,
                "next_direction": entry.next_direction,
            }
            for entry in context.memory
        ],
        ensure_ascii=True,
        sort_keys=True,
    )
    advice = "No confirmed advisor outcome is available."
    if context.latest_advice is not None:
        advice = json.dumps(
            {
                "directions": context.latest_advice.directions,
                "reasoning": context.latest_advice.reasoning,
                "authority": (
                    "optional advisory guidance only; it does not itself perform or authorize workspace edits, "
                    "evaluation, or submission, or alter selection, parent, strategy, goal, or budgets; use it only "
                    "through existing bounded tools and authority"
                ),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    elif context.latest_advice_failure is not None:
        advice = json.dumps(
            {
                "failure_code": context.latest_advice_failure.code.value,
                "detail": context.latest_advice_failure.detail,
                "authority": "confirmed fact only; do not retry the advisor",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    advice_command = (
        "The `request_advice` command takes no arguments and records that the current direction is exhausted. "
        if "request_advice" in context.tools
        else ""
    )
    return (
        f"Goal: {request.selection.goal}\n"
        f"Strategy: {request.selection.strategy.value}\n"
        f"Scope: {request.scope.value}\n"
        f"AVO call {context.state.variation_id}; current revision {context.state.current_revision}; "
        f"model requests {context.state.usage.model_requests}; tool calls {context.state.usage.tool_calls}; "
        f"revision checks {context.state.usage.development_evaluations}.\n"
        f"Structured memory (bounded facts only): {memory}\n"
        f"Approved tools: {names}. Each command uses `tool` plus an `arguments` object. "
        f"{advice_command}"
        "For edit_candidate, arguments are {mutation: {type, name, description, discipline, body, or content}}. "
        "For test_candidate, arguments are {hypothesis: string}. For restore_candidate, "
        "arguments are {attempt_id: string} or {revision: integer}. For submit_candidate and "
        "abstain, arguments are {reasoning: string}.\n"
        f"{previous}\n"
        f"Latest advisor outcome (advisory guidance or confirmed fact only): {advice}\n"
        "Return the next AVOCommand."
    )


__all__ = (
    "AVOCommand",
    "AVOContext",
    "AVOResponse",
    "AVORunner",
    "AVOTool",
    "ApprovedKnowledgeSource",
    "MutationInput",
    "PydanticAIAVORunner",
)
