# ABOUTME: Aggregates known trial costs and reports gaps without treating them as free.
# ABOUTME: Supplies one cost definition to evaluation, study, and leaderboard summaries.

from collections import defaultdict
from collections.abc import Sequence
from typing import TypedDict

from aec_bench.contracts.trial_record import ModelUsageRecord, TrialRecord


class CostSummary(TypedDict):
    total_cost_usd: float | None
    known_cost_usd: float
    n_costed: int
    n_uncosted: int


def summarize_costs(records: Sequence[TrialRecord]) -> CostSummary:
    return summarize_cost_values([record.cost.estimated_cost_usd if record.cost else None for record in records])


def summarize_cost_values(values: Sequence[float | None]) -> CostSummary:
    costs = [value for value in values if value is not None]
    known_cost = sum(costs, 0.0)
    n_uncosted = len(values) - len(costs)
    return {
        "total_cost_usd": None if n_uncosted else known_cost,
        "known_cost_usd": known_cost,
        "n_costed": len(costs),
        "n_uncosted": n_uncosted,
    }


class ModelUsageSummary(CostSummary):
    n_trials: int
    tokens_in: int | None
    tokens_out: int | None
    cache_read_tokens: int | None
    n_reported_cost: int
    n_estimated_cost: int


class ModelUsageBreakdown(TypedDict):
    by_model_usage: dict[str, ModelUsageSummary]
    n_trials_without_model_usage: int


def summarize_model_usage(records: Sequence[TrialRecord]) -> ModelUsageBreakdown:
    by_model: dict[str, list[ModelUsageRecord]] = defaultdict(list)
    missing = 0
    for record in records:
        if record.cost is None or not record.cost.model_usage:
            missing += 1
            continue
        for model, usage in record.cost.model_usage.items():
            by_model[model].append(usage)

    summaries: dict[str, ModelUsageSummary] = {}
    for model, items in sorted(by_model.items()):
        summaries[model] = {
            **summarize_cost_values([item.cost_usd for item in items]),
            "n_trials": len(items),
            "tokens_in": _sum_tokens([item.tokens_in for item in items]),
            "tokens_out": _sum_tokens([item.tokens_out for item in items]),
            "cache_read_tokens": _sum_tokens([item.cache_read_tokens for item in items]),
            "n_reported_cost": sum(item.reported_cost_usd is not None for item in items),
            "n_estimated_cost": sum(
                item.reported_cost_usd is None and item.estimated_cost_usd is not None for item in items
            ),
        }
    return {"by_model_usage": summaries, "n_trials_without_model_usage": missing}


def _sum_tokens(values: Sequence[int | None]) -> int | None:
    return None if any(value is None for value in values) else sum(value for value in values if value is not None)
