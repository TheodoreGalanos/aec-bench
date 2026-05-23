# ABOUTME: Shared budget pool for multi-agent swarm runs.
# ABOUTME: Tracks per-agent spend, eval spend, and phase transitions (exploring->winding_down->final->exhausted).

from __future__ import annotations

from collections import defaultdict
from typing import Literal


class BudgetLedger:
    """Shared budget pool with graceful wind-down phases."""

    def __init__(
        self,
        max_cost_usd: float,
        eval_budget_usd: float,
        wind_down_threshold: float = 0.8,
        final_threshold: float = 0.95,
    ) -> None:
        self.max_cost_usd = max_cost_usd
        self.eval_budget_usd = eval_budget_usd
        self.wind_down_threshold = wind_down_threshold
        self.final_threshold = final_threshold
        self.agent_spend: dict[str, float] = defaultdict(float)
        self.eval_spend: float = 0.0

    @property
    def total_agent_spend(self) -> float:
        return sum(self.agent_spend.values())

    @property
    def remaining(self) -> float:
        return max(0.0, self.max_cost_usd - self.total_agent_spend)

    @property
    def spend_percentage(self) -> float:
        if self.max_cost_usd <= 0:
            return 1.0
        return self.total_agent_spend / self.max_cost_usd

    @property
    def eval_budget_remaining(self) -> float:
        return max(0.0, self.eval_budget_usd - self.eval_spend)

    @property
    def eval_budget_exhausted(self) -> bool:
        return self.eval_spend >= self.eval_budget_usd

    @property
    def phase(self) -> Literal["exploring", "winding_down", "final", "exhausted"]:
        pct = self.spend_percentage
        if pct >= 1.0:
            return "exhausted"
        if pct >= self.final_threshold:
            return "final"
        if pct >= self.wind_down_threshold:
            return "winding_down"
        return "exploring"

    def record_agent_spend(self, agent_id: str, amount_usd: float) -> None:
        self.agent_spend[agent_id] += amount_usd

    def record_eval_spend(self, amount_usd: float) -> None:
        self.eval_spend += amount_usd
