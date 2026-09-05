# ABOUTME: Aggregates known trial costs and reports gaps without treating them as free.
# ABOUTME: Supplies one cost definition to evaluation, study, and leaderboard summaries.

from collections.abc import Sequence
from typing import TypedDict

from aec_bench.contracts.trial_record import TrialRecord


class CostSummary(TypedDict):
    total_cost_usd: float | None
    known_cost_usd: float
    n_costed: int
    n_uncosted: int


def summarize_costs(records: Sequence[TrialRecord]) -> CostSummary:
    costs = [
        record.cost.estimated_cost_usd
        for record in records
        if record.cost is not None and record.cost.estimated_cost_usd is not None
    ]
    known_cost = sum(costs, 0.0)
    n_uncosted = len(records) - len(costs)
    return {
        "total_cost_usd": None if n_uncosted else known_cost,
        "known_cost_usd": known_cost,
        "n_costed": len(costs),
        "n_uncosted": n_uncosted,
    }
