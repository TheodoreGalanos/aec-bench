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
from aec_bench.evolution.cancellation import AVOCancellationSignal
from aec_bench.evolution.core import AVOState, EvaluatedCandidate, VariationRequest
from aec_bench.evolution.memory import AVOMemoryEntry
from aec_bench.evolution.mutation import MutationAction
from aec_bench.evolution.supervision import (
    AVOSupervisionAdvice,
    AVOSupervisionFailure,
    AVOSupervisionRecord,
)


class AgentToolName(StrEnum):
    """Names of the only tools exposed to the variation agent."""

    READ_PARENT_EVIDENCE = "read_parent_evidence"
    READ_CURRENT_WORKSPACE = "read_current_workspace"
    READ_INSPIRATION = "read_inspiration"
    READ_HISTORY = "read_history"
    READ_GRAVEYARD = "read_graveyard"
    READ_KNOWLEDGE = "read_knowledge"
    APPLY_MUTATION = "apply_mutation"
    EVALUATE_CURRENT_REVISION = "evaluate_current_revision"
    RESTORE_ATTEMPT = "restore_attempt"
    SUBMIT_CURRENT_REVISION = "submit_current_revision"
    ABSTAIN = "abstain"
    REQUEST_SUPERVISION = "request_supervision"


class MutationInput(StrictModel):
    """Validated prompt or skill mutation accepted by ``apply_mutation``."""

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


class AgentCommand(StrictModel):
    """One typed tool selection returned by an injected agent runner."""

    tool: AgentToolName
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(StrictModel):
    """Optional usage-bearing response from an injected model runner."""

    command: AgentCommand
    model_cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    @model_validator(mode="after")
    def validate_cost(self) -> AgentResponse:
        if self.model_cost_usd is not None and (not math.isfinite(self.model_cost_usd) or self.model_cost_usd < 0):
            raise ValueError("model_cost_usd must be finite and non-negative")
        return self

    @field_validator("input_tokens", "output_tokens")
    @classmethod
    def validate_tokens(cls, value: int | None) -> int | None:
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError("token counts must be non-negative integers")
        return value


class AgentContext:
    """Context passed to one injected runner request.

    The context contains no canonical workspace handle. The runner can inspect
    or change scratch only through ``tools``.
    """

    def __init__(
        self,
        *,
        request: VariationRequest,
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
        self.supervision_records: tuple[AVOSupervisionRecord, ...] = state.supervision_records

    @property
    def latest_supervision_advice(self) -> AVOSupervisionAdvice | None:
        """Return the latest advice, without treating it as an instruction."""
        if not self.supervision_records:
            return None
        return self.supervision_records[-1].advice

    @property
    def latest_supervision_failure(self) -> AVOSupervisionFailure | None:
        """Return the latest confirmed supervisor failure, when present."""
        if not self.supervision_records:
            return None
        return self.supervision_records[-1].failure


class AgentRunner(Protocol):
    """Narrow provider boundary used by the bounded variation loop."""

    def __call__(self, context: AgentContext) -> AgentCommand | AgentResponse: ...


ApprovedKnowledgeSource = Callable[[], str] | str


_DEFAULT_AGENT_SYSTEM_PROMPT = (
    "You are a bounded AEC-Bench variation agent. Return exactly one typed tool command. "
    "Use only the approved tool names and arguments. Inspect before editing, evaluate changed "
    "material before submission, and submit only an eligible current revision."
)


class PydanticAIStructuredRunner:
    """Bounded PydanticAI adapter that returns one typed command per request.

    The adapter does not register arbitrary Python tools with the provider.
    It returns the typed command to the loop, which dispatches it through the
    guarded AVO tool map. This keeps provider retries and tool effects inside
    the loop's request and tool budgets.
    """

    def __init__(self, model: Any, *, system_prompt: str = "") -> None:
        self.model = model
        self.system_prompt = system_prompt or _DEFAULT_AGENT_SYSTEM_PROMPT

    def __call__(self, context: AgentContext) -> AgentResponse:
        pydantic_ai = import_module("pydantic_ai")
        usage_module = import_module("pydantic_ai.usage")

        agent = pydantic_ai.Agent(
            self.model,
            system_prompt=self.system_prompt,
            output_type=AgentCommand,
            retries=0,
        )
        result = agent.run_sync(_render_agent_prompt(context), usage_limits=usage_module.UsageLimits(request_limit=1))
        usage = result.usage()
        return AgentResponse(
            command=result.output,
            model_cost_usd=None,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )


def _render_agent_prompt(context: AgentContext) -> str:
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
    supervision = "No confirmed supervisor outcome is available."
    if context.latest_supervision_advice is not None:
        supervision = json.dumps(
            {
                "directions": context.latest_supervision_advice.directions,
                "reasoning": context.latest_supervision_advice.reasoning,
                "authority": (
                    "optional advisory guidance only; it does not itself perform or authorize workspace edits, "
                    "evaluation, or submission, or alter selection, parent, strategy, goal, or budgets; use it only "
                    "through existing bounded tools and authority"
                ),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    elif context.latest_supervision_failure is not None:
        supervision = json.dumps(
            {
                "failure_code": context.latest_supervision_failure.code.value,
                "detail": context.latest_supervision_failure.detail,
                "authority": "confirmed fact only; do not retry supervision",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    host_command = (
        "The host command `request_supervision` takes no arguments and records that the current direction "
        "is exhausted. "
        if "request_supervision" in context.tools
        else ""
    )
    return (
        f"Goal: {request.selection.goal}\n"
        f"Strategy: {request.selection.strategy.value}\n"
        f"Scope: {request.scope.value}\n"
        f"Variation {context.state.variation_id}; current revision {context.state.current_revision}; "
        f"model requests {context.state.usage.model_requests}; tool calls {context.state.usage.tool_calls}; "
        f"development evaluations {context.state.usage.development_evaluations}.\n"
        f"Structured memory (bounded facts only): {memory}\n"
        f"Approved tools: {names}. Each command uses `tool` plus an `arguments` object. "
        f"{host_command}"
        "For apply_mutation, arguments are {mutation: {type, name, description, discipline, body, or content}}. "
        "For evaluate_current_revision, arguments are {hypothesis: string}. For restore_attempt, "
        "arguments are {attempt_id: string} or {revision: integer}. For submit_current_revision and "
        "abstain, arguments are {reasoning: string}.\n"
        f"{previous}\n"
        f"Latest supervisor outcome (advisory guidance or confirmed fact only): {supervision}\n"
        "Return the next AgentCommand."
    )


__all__ = (
    "AgentCommand",
    "AgentContext",
    "AgentResponse",
    "AgentRunner",
    "AgentToolName",
    "ApprovedKnowledgeSource",
    "MutationInput",
    "PydanticAIStructuredRunner",
)
