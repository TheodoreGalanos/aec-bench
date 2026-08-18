# ABOUTME: DatasetProvider for the Command Palette searches stable dataset IDs and labels.
# ABOUTME: Returns DatasetHit objects for fuzzy-matched dataset entries.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetHit:
    dataset_id: str
    label: str | None = None
    task_count: int = 0


def search_datasets(entries: Sequence[DatasetHit], query: str) -> list[DatasetHit]:
    q = query.lower().strip()
    if not q:
        return list(entries)
    return [entry for entry in entries if q in f"{entry.dataset_id} {entry.label or ''}".lower()]
