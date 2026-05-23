# ABOUTME: TrialProvider for the Command Palette — search trials by task, model, or ID.
# ABOUTME: Returns TrialHit objects for fuzzy-matched trial records.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aec_bench.contracts.trial_record import TrialRecord


@dataclass(frozen=True)
class TrialHit:
    trial_id: str
    experiment_id: str
    task_id: str
    model: str
    reward: float


def search_trials(records: Sequence[TrialRecord], query: str) -> list[TrialHit]:
    """Search trial records by task_id, model, or trial_id. Case-insensitive substring match."""
    q = query.lower().strip()
    hits: list[TrialHit] = []
    for record in records:
        if not q:
            hits.append(_to_hit(record))
            continue
        searchable = f"{record.trial_id} {record.task.task_id} {record.agent.model}".lower()
        if q in searchable:
            hits.append(_to_hit(record))
    return hits


def _to_hit(record: TrialRecord) -> TrialHit:
    return TrialHit(
        trial_id=record.trial_id,
        experiment_id=record.experiment_id,
        task_id=record.task.task_id,
        model=record.agent.model,
        reward=record.evaluation.reward,
    )
