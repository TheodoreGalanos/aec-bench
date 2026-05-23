# ABOUTME: TaskProvider for the Command Palette — search tasks and templates.
# ABOUTME: Returns TaskHit objects for fuzzy-matched task entries.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskHit:
    task_id: str
    discipline: str
    description: str = ""


def search_tasks(entries: Sequence[TaskHit], query: str) -> list[TaskHit]:
    q = query.lower().strip()
    if not q:
        return list(entries)
    return [e for e in entries if q in f"{e.task_id} {e.discipline} {e.description}".lower()]
