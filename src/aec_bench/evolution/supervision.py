# ABOUTME: Defines bounded, read-only contracts for conditional AVO supervision.
# ABOUTME: Computes deterministic intervention triggers and projects existing AVO budget only.

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from aec_bench.contracts.evolution import MutationStrategy
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


class AVOSupervisionTrigger(StrEnum):
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

    def __post_init__(self) -> None:
        for field_name in (
            "model_requests",
            "tool_calls",
            "development_evaluations",
            "supervisor_interventions",
        ):
            _require_non_negative_integer(getattr(self, f"remaining_{field_name}"), f"remaining_{field_name}")
        _require_finite_non_negative(self.remaining_elapsed_seconds, "remaining_elapsed_seconds")
        if self.cost_limit_usd is not None:
            _require_finite_non_negative(self.cost_limit_usd, "cost_limit_usd")
        if self.remaining_cost_usd is not None:
            _require_finite_non_negative(self.remaining_cost_usd, "remaining_cost_usd")
            if self.cost_limit_usd is None:
                raise ValueError("remaining_cost_usd requires a bounded cost_limit_usd")
            if self.remaining_cost_usd > self.cost_limit_usd:
                raise ValueError("remaining_cost_usd cannot exceed cost_limit_usd")


@dataclass(frozen=True)
class AVOSupervisionRequest:
    """Structured, read-only input supplied to one supervisor invocation."""

    goal: str
    selected_parent_id: str
    strategy: MutationStrategy
    attempt_summaries: tuple[AVOMemoryEntry, ...]
    remaining_budget: AVORemainingBudget
    trigger_reason: AVOSupervisionTrigger

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
            trigger_reason = AVOSupervisionTrigger(self.trigger_reason)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unsupported supervision trigger reason: {self.trigger_reason!r}") from exc
        object.__setattr__(self, "trigger_reason", trigger_reason)


@dataclass(frozen=True)
class AVOSupervisionAdvice:
    """Validated guidance that cannot mutate AVO or outer evolution state."""

    directions: tuple[str, ...]
    reasoning: str

    def __post_init__(self) -> None:
        directions = tuple(self.directions)
        if not 1 <= len(directions) <= 3:
            raise ValueError("supervision advice must contain one to three directions")
        normalised: list[str] = []
        for direction in directions:
            if not isinstance(direction, str):
                raise TypeError("supervision advice directions must be strings")
            value = direction.strip()
            if not value:
                raise ValueError("supervision advice directions must not be blank")
            normalised.append(value)
        if len(normalised) != len(set(normalised)):
            raise ValueError("supervision advice directions must be unique")
        object.__setattr__(self, "directions", tuple(normalised))
        _require_text(self.reasoning, "reasoning")


def project_remaining_budget(budget: AVOBudget, state: AVOState) -> AVORemainingBudget:
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
    )


def supervision_trigger_reason(
    state: AVOState,
    budget: AVOBudget,
    *,
    exhausted_direction_requested: bool = False,
) -> AVOSupervisionTrigger | None:
    """Return the deterministic trigger reason admitted by explicit AVO state.

    Valid stagnation uses the explicit ``consecutive_without_progress``
    counter, and confirms that its latest three development attempts are valid
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
        return AVOSupervisionTrigger.VALID_DEVELOPMENT_STAGNATION
    if _has_consecutive_invalid_or_failed_evaluations(state):
        return AVOSupervisionTrigger.CONSECUTIVE_INVALID_OR_FAILED_EVALUATIONS
    if exhausted_direction_requested:
        return AVOSupervisionTrigger.EXHAUSTED_DIRECTION_REQUEST
    return None


def should_trigger_supervision(
    state: AVOState,
    budget: AVOBudget,
    *,
    exhausted_direction_requested: bool = False,
) -> bool:
    """Return whether one supervisor intervention is currently admitted."""
    return (
        supervision_trigger_reason(
            state,
            budget,
            exhausted_direction_requested=exhausted_direction_requested,
        )
        is not None
    )


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
    "AVORemainingBudget",
    "AVOSupervisionAdvice",
    "AVOSupervisionRequest",
    "AVOSupervisionTrigger",
    "project_remaining_budget",
    "should_trigger_supervision",
    "supervision_trigger_reason",
)
