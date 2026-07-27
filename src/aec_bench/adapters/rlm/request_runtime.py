# ABOUTME: Resolves per-request RLM limits against the configured execution envelope.
# ABOUTME: Produces one immutable request view before any provider or REPL effect occurs.

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.rlm.config import ExecutionConfig, GuardrailConfig
from aec_bench.adapters.runtime_limits import configured_positive_int


@dataclass(frozen=True, slots=True)
class ResolvedRlmRequest:
    """Request and effective limits used by one RLM execution."""

    request: AdapterRequest
    max_iterations: int
    token_budget: int
    context_limit: int
    max_budget_usd: float


def configured_positive_float(
    configuration: dict[str, Any],
    field_name: str,
) -> float | None:
    """Return one configured positive finite number, preserving absence."""
    if field_name not in configuration:
        return None
    raw_value = configuration[field_name]
    if isinstance(raw_value, bool) or not isinstance(raw_value, int | float | str):
        raise ValueError(f"{field_name} must be a positive finite number")
    try:
        value = float(raw_value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{field_name} must be a positive finite number") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be a positive finite number")
    return value


def resolve_rlm_request(
    request: AdapterRequest,
    *,
    guardrails: GuardrailConfig,
    execution: ExecutionConfig,
) -> ResolvedRlmRequest:
    """Tighten configured limits with request-local bounds."""
    request_max_turns = configured_positive_int(request.configuration, "max_turns")
    request_token_budget = configured_positive_int(request.configuration, "token_budget")
    request_context_limit = configured_positive_int(request.configuration, "context_budget_tokens")
    request_max_cost_usd = configured_positive_float(request.configuration, "max_cost_usd")

    max_iterations = _tightened_int(guardrails.max_iterations, request_max_turns)
    token_budget = _tightened_int(guardrails.token_budget, request_token_budget)
    context_limit = _tightened_int(execution.context_limit, request_context_limit)
    max_budget_usd = _tightened_cost(guardrails.max_budget_usd, request_max_cost_usd)

    effective_configuration = dict(request.configuration)
    for field_name, requested_value, effective_value in (
        ("max_turns", request_max_turns, max_iterations),
        ("token_budget", request_token_budget, token_budget),
        ("max_cost_usd", request_max_cost_usd, max_budget_usd),
        ("context_budget_tokens", request_context_limit, context_limit),
    ):
        if requested_value is not None:
            effective_configuration[field_name] = effective_value
    return ResolvedRlmRequest(
        request=replace(request, configuration=effective_configuration),
        max_iterations=max_iterations,
        token_budget=token_budget,
        context_limit=context_limit,
        max_budget_usd=max_budget_usd,
    )


def _tightened_int(configured: int, requested: int | None) -> int:
    return min(configured, requested) if requested is not None else configured


def _tightened_cost(configured: float, requested: float | None) -> float:
    if requested is None:
        return configured
    return min(configured, requested) if configured > 0 else requested
