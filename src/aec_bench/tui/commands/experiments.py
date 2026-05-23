# ABOUTME: ExperimentProvider for the Command Palette — search experiments by ID.
# ABOUTME: Returns ExperimentHit objects for fuzzy-matched experiment entries.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentHit:
    experiment_id: str
    trial_count: int = 0


def search_experiments(entries: Sequence[ExperimentHit], query: str) -> list[ExperimentHit]:
    q = query.lower().strip()
    if not q:
        return list(entries)
    return [e for e in entries if q in e.experiment_id.lower()]
