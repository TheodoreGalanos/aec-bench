# ABOUTME: Derives exact provider-neutral usage from independently imported TrialRecords.
# ABOUTME: Rejects missing call, token, cost, advisor, or identity evidence rather than estimating it.

from __future__ import annotations

import math

from aec_bench.contracts.trial_record import CostRecord, TrialRecord

from .contracts import GovernedAttemptUsage


class GovernedTrialUsageError(ValueError):
    """Raised when scored TrialRecords cannot prove exact governed usage."""


def aggregate_governed_trial_usage(
    records: tuple[TrialRecord, ...],
    *,
    wall_time_seconds: float,
) -> GovernedAttemptUsage:
    """Aggregate exact usage while preserving the candidate wall-time boundary."""

    if not records:
        raise GovernedTrialUsageError(
            "governed usage requires at least one TrialRecord",
        )
    if not math.isfinite(wall_time_seconds) or wall_time_seconds < 0:
        raise GovernedTrialUsageError(
            "governed usage wall time must be finite and non-negative",
        )
    identities = tuple((record.experiment_id, record.trial_id) for record in records)
    if len(identities) != len(set(identities)):
        raise GovernedTrialUsageError(
            "governed usage requires unique TrialRecord identities",
        )

    model_calls = 0
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    estimated_costs: list[float] = []
    for record in records:
        cost = _complete_cost(record)
        calls = _model_calls(record)
        advisor_calls, advisor_input, advisor_output = _advisor_usage(
            record=record,
            cost=cost,
        )
        model_calls += calls + advisor_calls
        input_tokens += _required_token(cost.tokens_in) + advisor_input
        output_tokens += _required_token(cost.tokens_out) + advisor_output
        cache_read_tokens += _required_token(cost.cache_read_tokens)
        cache_write_tokens += _required_token(cost.cache_write_tokens)
        assert cost.estimated_cost_usd is not None
        estimated_costs.append(float(cost.estimated_cost_usd))

    return GovernedAttemptUsage(
        model_calls=model_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        estimated_cost_usd=math.fsum(estimated_costs),
        wall_time_seconds=wall_time_seconds,
    )


def _model_calls(record: TrialRecord) -> int:
    value = None if record.cost is None else record.cost.model_calls
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise GovernedTrialUsageError(
            f"TrialRecord {record.trial_id!r} lacks exact model-call evidence",
        )
    return value


def _complete_cost(record: TrialRecord) -> CostRecord:
    cost = record.cost
    if cost is None or cost.estimated_cost_usd is None:
        raise GovernedTrialUsageError(
            f"TrialRecord {record.trial_id!r} lacks complete cost evidence",
        )
    if any(
        value is None
        for value in (
            cost.tokens_in,
            cost.tokens_out,
            cost.cache_read_tokens,
            cost.cache_write_tokens,
        )
    ):
        raise GovernedTrialUsageError(
            f"TrialRecord {record.trial_id!r} lacks complete token evidence",
        )
    return cost


def _advisor_usage(
    *,
    record: TrialRecord,
    cost: CostRecord,
) -> tuple[int, int, int]:
    cost_values = (
        cost.advisor_calls,
        cost.advisor_input_tokens,
        cost.advisor_output_tokens,
    )
    if all(value is None for value in cost_values):
        return 0, 0, 0
    if any(value is None for value in cost_values):
        raise GovernedTrialUsageError(
            f"TrialRecord {record.trial_id!r} lacks complete advisor usage evidence",
        )
    return (
        _required_token(cost.advisor_calls),
        _required_token(cost.advisor_input_tokens),
        _required_token(cost.advisor_output_tokens),
    )


def _required_token(value: int | None) -> int:
    assert value is not None
    return value


__all__ = (
    "GovernedTrialUsageError",
    "aggregate_governed_trial_usage",
)
