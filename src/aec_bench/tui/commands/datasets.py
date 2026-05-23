# ABOUTME: DatasetProvider for the Command Palette — search datasets by name or version.
# ABOUTME: Returns DatasetHit objects for fuzzy-matched dataset entries.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetHit:
    name: str
    version: str
    task_count: int = 0


def search_datasets(entries: Sequence[DatasetHit], query: str) -> list[DatasetHit]:
    q = query.lower().strip()
    if not q:
        return list(entries)
    return [e for e in entries if q in f"{e.name} {e.version}".lower()]
