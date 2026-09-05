# ABOUTME: Pure communication metrics derived from canonical TrialRecord evaluation fields.
# ABOUTME: Keeps report builders deterministic and independent from rendering or transport layers.

from collections.abc import Sequence
from typing import Any

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.costs import summarize_costs


def mean_reward(records: Sequence[TrialRecord]) -> float:
    rewards = [record.evaluation.reward for record in records if record.evaluation is not None]
    return sum(rewards) / len(rewards) if rewards else 0.0


def perfect_trial_rate(records: Sequence[TrialRecord]) -> float:
    rewards = [record.evaluation.reward for record in records if record.evaluation is not None]
    return sum(reward >= 1.0 for reward in rewards) / len(rewards) if rewards else 0.0


def total_cost_usd(records: Sequence[TrialRecord]) -> float | None:
    return summarize_costs(records)["total_cost_usd"]


def coerce_int(value: Any, fallback: int = 0) -> int:
    """Safely coerce a value to int, returning fallback if None."""
    if value is None:
        return fallback
    return int(value)


def resolve_agent_name(record: TrialRecord) -> str:
    """Extract a display-friendly agent name from a trial record."""
    harbor_name = record.agent.configuration.get("harbor_agent_name")
    if isinstance(harbor_name, str):
        return harbor_name
    return record.agent.adapter


def split_task_id(task_id: str) -> tuple[str, str]:
    """Return (task_type, task_name) from a slash-delimited task_id."""
    parts = task_id.split("/")
    task_name = parts[-1]
    task_type = parts[-2] if len(parts) > 1 else task_id
    return task_type, task_name
