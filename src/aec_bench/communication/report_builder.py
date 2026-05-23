# ABOUTME: Public-safe communication report builders for leaderboard-style experiment summaries.
# ABOUTME: Aggregates filtered TrialRecords into stable JSON-friendly report structures.

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from aec_bench.communication.metrics import (
    mean_reward,
    perfect_trial_rate,
    resolve_agent_name,
    total_cost_usd,
)
from aec_bench.contracts.trial_record import TrialRecord


@dataclass(frozen=True)
class LeaderboardEntry:
    experiment_id: str
    agent_name: str
    model_name: str
    n_trials: int
    mean_reward: float
    perfect_trial_rate: float
    total_cost_usd: float


@dataclass(frozen=True)
class LeaderboardReport:
    entries: list[LeaderboardEntry]


def build_leaderboard(records: Sequence[TrialRecord]) -> LeaderboardReport:
    grouped: dict[str, list[TrialRecord]] = defaultdict(list)
    for record in records:
        grouped[record.experiment_id].append(record)

    entries = [
        _build_entry(experiment_id, experiment_records) for experiment_id, experiment_records in sorted(grouped.items())
    ]
    return LeaderboardReport(entries=entries)


def leaderboard_to_dict(report: LeaderboardReport) -> dict[str, Any]:
    return {
        "entries": [
            {
                **asdict(entry),
                "mean_reward": round(entry.mean_reward, 4),
                "perfect_trial_rate": round(entry.perfect_trial_rate, 4),
                "total_cost_usd": round(entry.total_cost_usd, 4),
            }
            for entry in report.entries
        ]
    }


def _build_entry(experiment_id: str, records: Sequence[TrialRecord]) -> LeaderboardEntry:
    first_record = records[0]
    return LeaderboardEntry(
        experiment_id=experiment_id,
        agent_name=resolve_agent_name(first_record),
        model_name=first_record.agent.model,
        n_trials=len(records),
        mean_reward=mean_reward(records),
        perfect_trial_rate=perfect_trial_rate(records),
        total_cost_usd=total_cost_usd(records),
    )
