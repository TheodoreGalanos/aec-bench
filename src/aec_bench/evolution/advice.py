# ABOUTME: Defines bounded, read-only contracts for conditional AVO advice.
# ABOUTME: Computes deterministic intervention triggers and projects existing AVO budget only.

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from enum import StrEnum
from importlib import import_module
from typing import Any, Protocol

from pydantic import model_validator

from aec_bench.contracts.evolution import MutationStrategy, ProposalUsage
from aec_bench.contracts.validators import FrozenStrictModel
from aec_bench.evolution.core import AVOBudget, AVOState
from aec_bench.evolution.memory import AVO_MEMORY_LIMIT, AVOMemoryEntry, validate_memory_entries

_VALID_STAGNATION_THRESHOLD = 3
_INVALID_OR_FAILED_THRESHOLD = 2


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_non_negative_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_finite_non_negative(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{field_name} must be a finite non-negative number")


class AVOAdviceTrigger(StrEnum):
    """Stable reasons that can admit one bounded supervisor intervention."""

    VALID_DEVELOPMENT_STAGNATION = "three_valid_development_evaluations_without_progress"
    CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS = "two_consecutive_invalid_or_failed_development_evaluations"
    EXHAUSTED_DIRECTION_REQUEST = "main_agent_exhausted_direction_request"


@dataclass(frozen=True)
class AVORemainingBudget:
    """Read-only remaining allowance projected from one AVO call's budget.

    ``cost_limit_usd`` distinguishes an unbounded cost plane from a bounded
    plane whose remaining cost is unknown. ``None`` for ``remaining_cost_usd``
    does not mean that the supervisor may spend without a limit. This value is
    a projection for supervisor context; it cannot grant authority to use a
    resource that the AVO budget does not permit.
    """

    remaining_model_requests: int
    remaining_tool_calls: int
    remaining_development_evaluations: int
    remaining_elapsed_seconds: float
    remaining_supervisor_interventions: int
    cost_limit_usd: float | None
    remaining_cost_usd: float | None
    remaining_input_tokens: int | None = None
    remaining_output_tokens: int | None = None
    input_token_limit: int | None = None
    output_token_limit: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "model_requests",
            "tool_calls",
            "development_evaluations",
            "supervisor_interventions",
        ):
            _require_non_negative_integer(getattr(self, f"remaining_{field_name}"), f"remaining_{field_name}")
        _require_finite_non_negative(self.remaining_elapsed_seconds, "remaining_elapsed_seconds")
        for field_name in ("remaining_input_tokens", "remaining_output_tokens"):
            tokens = getattr(self, field_name)
            if tokens is not None:
                _require_non_negative_integer(tokens, field_name)
        for field_name, remaining_name in (
            ("input_token_limit", "remaining_input_tokens"),
            ("output_token_limit", "remaining_output_tokens"),
        ):
            limit = getattr(self, field_name)
            if limit is not None:
                _require_non_negative_integer(limit, field_name)
                remaining = getattr(self, remaining_name)
                if remaining is not None and remaining > limit:
                    raise ValueError(f"{remaining_name} cannot exceed {field_name}")
        if self.cost_limit_usd is not None:
            _require_finite_non_negative(self.cost_limit_usd, "cost_limit_usd")
        if self.remaining_cost_usd is not None:
            _require_finite_non_negative(self.remaining_cost_usd, "remaining_cost_usd")
            if self.cost_limit_usd is None:
                raise ValueError("remaining_cost_usd requires a bounded cost_limit_usd")
            if self.remaining_cost_usd > self.cost_limit_usd:
                raise ValueError("remaining_cost_usd cannot exceed cost_limit_usd")


@dataclass(frozen=True)
class AVOAdviceRequest:
    """Structured, read-only input supplied to one supervisor invocation."""

    goal: str
    selected_parent_id: str
    strategy: MutationStrategy
    attempt_summaries: tuple[AVOMemoryEntry, ...]
    remaining_budget: AVORemainingBudget
    trigger_reason: AVOAdviceTrigger

    def __post_init__(self) -> None:
        _require_text(self.goal, "goal")
        _require_text(self.selected_parent_id, "selected_parent_id")
        try:
            strategy = MutationStrategy(self.strategy)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unsupported mutation strategy: {self.strategy!r}") from exc
        object.__setattr__(self, "strategy", strategy)

        summaries = validate_memory_entries(self.attempt_summaries)
        if len(summaries) > AVO_MEMORY_LIMIT:
            raise ValueError(f"attempt_summaries must contain at most {AVO_MEMORY_LIMIT} entries")
        object.__setattr__(self, "attempt_summaries", summaries)

        if not isinstance(self.remaining_budget, AVORemainingBudget):
            raise TypeError("remaining_budget must be an AVORemainingBudget")
        try:
            trigger_reason = AVOAdviceTrigger(self.trigger_reason)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unsupported advice trigger reason: {self.trigger_reason!r}") from exc
        object.__setattr__(self, "trigger_reason", trigger_reason)


@dataclass(frozen=True)
class AVOAdvice:
    """Validated guidance that cannot mutate AVO or outer evolution state."""

    directions: tuple[str, ...]
    reasoning: str

    def __post_init__(self) -> None:
        directions = tuple(self.directions)
        if not 1 <= len(directions) <= 3:
            raise ValueError("AVO advice must contain one to three directions")
        normalised: list[str] = []
        for direction in directions:
            if not isinstance(direction, str):
                raise TypeError("AVO advice directions must be strings")
            value = direction.strip()
            if not value:
                raise ValueError("AVO advice directions must not be blank")
            normalised.append(value)
        if len(normalised) != len(set(normalised)):
            raise ValueError("AVO advice directions must be unique")
        object.__setattr__(self, "directions", tuple(normalised))
        _require_text(self.reasoning, "reasoning")


class AVOAdviceFailureCode(StrEnum):
    """Confirmed supervisor failures that do not represent provider failure."""

    OUTPUT_VALIDATION_REJECTED = "output_validation_rejected"


@dataclass(frozen=True)
class AVOAdviceFailure:
    """One confirmed failure produced by supervisor output validation."""

    code: AVOAdviceFailureCode
    detail: str

    def __post_init__(self) -> None:
        try:
            code = AVOAdviceFailureCode(self.code)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unsupported supervisor failure code: {self.code!r}") from exc
        object.__setattr__(self, "code", code)
        _require_text(self.detail, "detail")


class AVOAdviceRecord(FrozenStrictModel):
    """One confirmed intervention outcome retained in AVO state."""

    trigger_reason: AVOAdviceTrigger
    advice: AVOAdvice | None = None
    failure: AVOAdviceFailure | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> AVOAdviceRecord:
        if (self.advice is None) == (self.failure is None):
            raise ValueError("advice record requires advice or confirmed failure, but not both")
        return self


@dataclass(frozen=True)
class AVOAdviceResult:
    """Immutable supervisor output and the usage delta for that one call."""

    output: AVOAdvice | AVOAdviceFailure
    usage: ProposalUsage

    def __post_init__(self) -> None:
        if not isinstance(self.output, AVOAdvice | AVOAdviceFailure):
            raise TypeError("output must be AVOAdvice or AVOAdviceFailure")
        if not isinstance(self.usage, ProposalUsage):
            raise TypeError("usage must be a ProposalUsage")
        if self.usage.model_requests != 1 or self.usage.supervisor_interventions != 1:
            raise ValueError("advisor usage must describe exactly one request and intervention")
        if self.usage.tool_calls or self.usage.development_evaluations:
            raise ValueError("advisor usage must not include tools or revision evaluations")
        if self.usage.development_evaluation_cost_usd is not None:
            raise ValueError("advisor usage must not include revision evaluation cost")


class AVOAdviceBudgetError(ValueError):
    """Raised when a supervisor reservation or reconciliation exceeds AVO authority."""


class AVOAdvisorRunner(Protocol):
    """Narrow provider boundary for one non-recursive supervisor request."""

    def __call__(self, request: AVOAdviceRequest) -> AVOAdviceResult: ...


def _validate_usage_within_budget(
    usage: ProposalUsage,
    budget: AVOBudget,
    *,
    allow_reserved_unknown_tokens: bool = False,
    allow_reserved_unknown_cost: bool = False,
) -> None:
    """Fail closed when known usage exceeds a configured hard limit."""
    if usage.model_requests > budget.max_model_requests:
        raise AVOAdviceBudgetError("max_model_requests")
    if usage.supervisor_interventions > budget.max_supervisor_interventions:
        raise AVOAdviceBudgetError("max_supervisor_interventions")
    if usage.elapsed_seconds > budget.max_elapsed_seconds:
        raise AVOAdviceBudgetError("max_elapsed_seconds")
    for name, observed, limit in (
        ("max_input_tokens", usage.input_tokens, budget.max_input_tokens),
        ("max_output_tokens", usage.output_tokens, budget.max_output_tokens),
    ):
        if limit is not None:
            if observed is None:
                if allow_reserved_unknown_tokens and usage.model_requests == 1:
                    continue
                raise AVOAdviceBudgetError(f"{name}_unknown")
            if observed > limit:
                raise AVOAdviceBudgetError(name)
    if budget.max_cost_usd is not None:
        total_cost = usage.total_cost_usd
        if total_cost is None:
            if allow_reserved_unknown_cost and usage.model_requests == 1:
                return
            raise AVOAdviceBudgetError("max_cost_usd_unknown")
        if total_cost > budget.max_cost_usd:
            raise AVOAdviceBudgetError("max_cost_usd")


def reserve_advisor_budget(usage: ProposalUsage, budget: AVOBudget) -> ProposalUsage:
    """Reserve one model request and intervention before an advisor call."""
    if not isinstance(usage, ProposalUsage):
        raise TypeError("usage must be a ProposalUsage")
    if not isinstance(budget, AVOBudget):
        raise TypeError("budget must be an AVOBudget")
    if usage.model_requests >= budget.max_model_requests:
        raise AVOAdviceBudgetError("max_model_requests")
    if usage.supervisor_interventions >= budget.max_supervisor_interventions:
        raise AVOAdviceBudgetError("max_supervisor_interventions")
    if usage.elapsed_seconds >= budget.max_elapsed_seconds:
        raise AVOAdviceBudgetError("max_elapsed_seconds")
    reserved = ProposalUsage(
        model_requests=usage.model_requests + 1,
        tool_calls=usage.tool_calls,
        development_evaluations=usage.development_evaluations,
        supervisor_interventions=usage.supervisor_interventions + 1,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        model_cost_usd=usage.model_cost_usd,
        development_evaluation_cost_usd=usage.development_evaluation_cost_usd,
        elapsed_seconds=usage.elapsed_seconds,
    )
    _validate_usage_within_budget(
        reserved,
        budget,
        allow_reserved_unknown_tokens=usage.model_requests == 0,
        allow_reserved_unknown_cost=usage.model_requests == 0 and usage.total_cost_usd is not None,
    )
    return reserved


def complete_advisor_usage(
    usage_before: ProposalUsage,
    budget: AVOBudget,
    advisor_usage: ProposalUsage,
) -> ProposalUsage:
    """Merge one validated advisor usage delta into the shared AVO usage."""
    reserved = reserve_advisor_budget(usage_before, budget)
    if not isinstance(advisor_usage, ProposalUsage):
        raise TypeError("advisor_usage must be a ProposalUsage")
    if (
        advisor_usage.model_requests != 1
        or advisor_usage.supervisor_interventions != 1
        or advisor_usage.tool_calls != 0
        or advisor_usage.development_evaluations != 0
        or advisor_usage.development_evaluation_cost_usd is not None
    ):
        raise ValueError("advisor usage must describe exactly one request and intervention")

    def merge_tokens(previous: int | None, added: int | None) -> int | None:
        if usage_before.model_requests == 0:
            return added
        if previous is None or added is None:
            return None
        return previous + added

    def merge_cost(previous: float | None, added: float | None) -> float | None:
        if usage_before.model_requests == 0:
            return added
        if previous is None or added is None:
            return None
        return previous + added

    reconciled = ProposalUsage(
        model_requests=reserved.model_requests,
        tool_calls=reserved.tool_calls,
        development_evaluations=reserved.development_evaluations,
        supervisor_interventions=reserved.supervisor_interventions,
        input_tokens=merge_tokens(usage_before.input_tokens, advisor_usage.input_tokens),
        output_tokens=merge_tokens(usage_before.output_tokens, advisor_usage.output_tokens),
        model_cost_usd=merge_cost(usage_before.model_cost_usd, advisor_usage.model_cost_usd),
        development_evaluation_cost_usd=usage_before.development_evaluation_cost_usd,
        elapsed_seconds=reserved.elapsed_seconds + advisor_usage.elapsed_seconds,
    )
    return reconciled


class PydanticAIAdvisor:
    """Provider adapter with one typed, read-only advice request."""

    def __init__(self, model: Any, *, model_identity: str, system_prompt: str = "") -> None:
        if model is None:
            raise ValueError("advisor model must be explicit")
        _require_text(model_identity, "model_identity")
        if system_prompt and not isinstance(system_prompt, str):
            raise TypeError("system_prompt must be a string")
        self.model = model
        self.model_identity = model_identity.strip()
        self.system_prompt = system_prompt.strip() or _DEFAULT_ADVISOR_SYSTEM_PROMPT

    def __call__(self, request: AVOAdviceRequest) -> AVOAdviceResult:
        if not isinstance(request, AVOAdviceRequest):
            raise TypeError("request must be an AVOAdviceRequest")
        pydantic_ai = import_module("pydantic_ai")
        usage_module = import_module("pydantic_ai.usage")
        started_at = time.monotonic()
        agent = pydantic_ai.Agent(
            self.model,
            system_prompt=self.system_prompt,
            output_type=AVOAdvice,
            retries=0,
        )
        result = agent.run_sync(
            _render_advice_prompt(request),
            usage_limits=usage_module.UsageLimits(request_limit=1),
        )

        usage = result.usage()
        if usage.requests != 1:
            raise RuntimeError("advisor provider request count must be exactly one")
        return AVOAdviceResult(
            output=result.output,
            usage=ProposalUsage(
                model_requests=1,
                supervisor_interventions=1,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                elapsed_seconds=max(0.0, time.monotonic() - started_at),
            ),
        )


@dataclass(frozen=True)
class AVOAdvisor:
    """Immutable pairing of an isolated advisor runner and exact identity."""

    runner: PydanticAIAdvisor
    model_identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.runner, PydanticAIAdvisor):
            raise TypeError("runner must be a PydanticAIAdvisor")
        _require_text(self.model_identity, "model_identity")
        identity = self.model_identity.strip()
        if self.runner.model_identity != identity:
            raise ValueError("advisor runner identity must match composition identity")
        object.__setattr__(self, "model_identity", identity)


def build_avo_advisor(
    model: Any,
    *,
    model_identity: str,
    system_prompt: str = "",
) -> AVOAdvisor:
    """Build one explicit advisor runner without composing loop state or tools."""
    runner = PydanticAIAdvisor(model, model_identity=model_identity, system_prompt=system_prompt)
    return AVOAdvisor(runner=runner, model_identity=runner.model_identity)


_DEFAULT_ADVISOR_SYSTEM_PROMPT = (
    "You are a bounded AEC-Bench advisor. Return only validated advice with one to three distinct directions. "
    "You cannot edit workspaces, call tools, evaluate candidates, or change budgets."
)


def _render_advice_prompt(request: AVOAdviceRequest) -> str:
    """Render only immutable request facts for the isolated advisor."""
    summaries = [
        {
            "source_variation_id": entry.source_variation_id,
            "source_attempt_id": entry.source_attempt_id,
            "hypothesis": entry.hypothesis,
            "change_summary": entry.change_summary,
            "evidence_summary": entry.evidence_summary,
            "outcome": entry.outcome.value,
            "failure_category": entry.failure_category,
            "next_direction": entry.next_direction,
        }
        for entry in request.attempt_summaries
    ]
    payload = {
        "goal": request.goal,
        "selected_parent_id": request.selected_parent_id,
        "strategy": request.strategy.value,
        "attempt_summaries": summaries,
        "remaining_budget": asdict(request.remaining_budget),
        "trigger_reason": request.trigger_reason.value,
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def remaining_avo_budget(budget: AVOBudget, state: AVOState) -> AVORemainingBudget:
    """Project non-negative remaining AVO allowances without adding authority."""
    if not isinstance(budget, AVOBudget):
        raise TypeError("budget must be an AVOBudget")
    if not isinstance(state, AVOState):
        raise TypeError("state must be an AVOState")

    usage = state.usage
    total_cost = usage.total_cost_usd
    remaining_cost = None
    if budget.max_cost_usd is not None and total_cost is not None:
        remaining_cost = max(0.0, budget.max_cost_usd - total_cost)
    return AVORemainingBudget(
        remaining_model_requests=max(0, budget.max_model_requests - usage.model_requests),
        remaining_tool_calls=max(0, budget.max_tool_calls - usage.tool_calls),
        remaining_development_evaluations=max(0, budget.max_development_evaluations - usage.development_evaluations),
        remaining_elapsed_seconds=max(0.0, budget.max_elapsed_seconds - usage.elapsed_seconds),
        remaining_supervisor_interventions=max(0, budget.max_supervisor_interventions - usage.supervisor_interventions),
        cost_limit_usd=budget.max_cost_usd,
        remaining_cost_usd=remaining_cost,
        remaining_input_tokens=(
            budget.max_input_tokens
            if budget.max_input_tokens is not None and usage.model_requests == 0 and usage.input_tokens is None
            else (
                None
                if budget.max_input_tokens is None or usage.input_tokens is None
                else max(0, budget.max_input_tokens - usage.input_tokens)
            )
        ),
        remaining_output_tokens=(
            budget.max_output_tokens
            if budget.max_output_tokens is not None and usage.model_requests == 0 and usage.output_tokens is None
            else (
                None
                if budget.max_output_tokens is None or usage.output_tokens is None
                else max(0, budget.max_output_tokens - usage.output_tokens)
            )
        ),
        input_token_limit=budget.max_input_tokens,
        output_token_limit=budget.max_output_tokens,
    )


def advice_trigger(
    state: AVOState,
    budget: AVOBudget,
    *,
    exhausted_direction_requested: bool = False,
) -> AVOAdviceTrigger | None:
    """Return the deterministic trigger reason admitted by explicit AVO state.

    Valid stagnation uses the explicit ``consecutive_without_progress``
    counter, and confirms that its latest three revision attempts are valid
    evidence. Invalid attempts and evaluator failures use their respective
    explicit state counters. Trigger order is stable when more than one
    condition is true. Reaching the hard intervention limit always suppresses
    a trigger, including an explicit main-agent request.
    """
    if not isinstance(state, AVOState):
        raise TypeError("state must be an AVOState")
    if not isinstance(budget, AVOBudget):
        raise TypeError("budget must be an AVOBudget")
    if not isinstance(exhausted_direction_requested, bool):
        raise TypeError("exhausted_direction_requested must be a boolean")
    if state.terminal_status is not None:
        return None
    if state.usage.supervisor_interventions >= budget.max_supervisor_interventions:
        return None

    if _has_valid_stagnation(state):
        return AVOAdviceTrigger.VALID_DEVELOPMENT_STAGNATION
    if _has_consecutive_invalid_or_failed_evaluations(state):
        return AVOAdviceTrigger.CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS
    if exhausted_direction_requested:
        return AVOAdviceTrigger.EXHAUSTED_DIRECTION_REQUEST
    return None


def _has_valid_stagnation(state: AVOState) -> bool:
    """Require the explicit stagnation count and three latest valid attempts."""
    if state.consecutive_without_progress < _VALID_STAGNATION_THRESHOLD:
        return False
    if state.consecutive_evaluation_errors:
        return False
    latest_attempts = state.attempts[-_VALID_STAGNATION_THRESHOLD:]
    return len(latest_attempts) == _VALID_STAGNATION_THRESHOLD and all(
        attempt.evaluated.assessment.valid for attempt in latest_attempts
    )


def _has_consecutive_invalid_or_failed_evaluations(state: AVOState) -> bool:
    """Recognise two evaluator failures or two latest invalid attempts."""
    if state.consecutive_evaluation_errors >= _INVALID_OR_FAILED_THRESHOLD:
        return True
    required_invalid_attempts = _INVALID_OR_FAILED_THRESHOLD - state.consecutive_evaluation_errors
    latest_attempts = state.attempts[-required_invalid_attempts:]
    return len(latest_attempts) == required_invalid_attempts and all(
        not attempt.evaluated.assessment.valid for attempt in latest_attempts
    )


__all__ = (
    "AVOAdviceBudgetError",
    "AVOAdvisor",
    "AVOAdviceFailure",
    "AVOAdviceFailureCode",
    "AVOAdviceRecord",
    "AVOAdviceResult",
    "AVORemainingBudget",
    "AVOAdvice",
    "AVOAdviceRequest",
    "AVOAdviceTrigger",
    "PydanticAIAdvisor",
    "AVOAdvisorRunner",
    "build_avo_advisor",
    "remaining_avo_budget",
    "complete_advisor_usage",
    "reserve_advisor_budget",
    "advice_trigger",
)
