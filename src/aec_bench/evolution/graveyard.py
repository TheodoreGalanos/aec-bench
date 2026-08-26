# ABOUTME: Graveyard archive for failed mutations — stores rejected changes for later rescue.
# ABOUTME: Failed mutations are kept instead of discarded, enabling the evolver to learn from them.

from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from aec_bench.contracts.evolution import CandidateAssessment, MutationSummary, WorkspaceSnapshot


class GraveyardMutationAction(TypedDict):
    """Mutation action retained with a rejected evolution attempt."""

    action_type: str
    skill_name: NotRequired[str]


@dataclass(frozen=True)
class GraveyardEntry:
    """A single failed mutation stored for potential future rescue."""

    cycle: int
    strategy: str
    mutation_description: str
    score_before: float
    score_after: float
    candidate_id: str
    failure_reason: str

    # Enrichment fields — populated from engine data when available.
    # None for backwards compatibility with pre-enrichment graveyard files.
    field_failures: dict[str, str] | None = None
    detected_patterns: list[str] | None = None
    mutation_actions: list[GraveyardMutationAction] | None = None
    investigation_summary: str | None = None
    parent_candidate_id: str | None = None
    rejected_snapshot: WorkspaceSnapshot | None = None
    parent_assessment: CandidateAssessment | None = None
    child_assessment: CandidateAssessment | None = None
    mutation: MutationSummary | None = None
    run_id: str | None = None
    timestamp: datetime | None = None


class MutationGraveyard:
    """Bounded archive of failed mutation attempts.

    Stores GraveyardEntry items in a deque with a fixed maximum size.
    When full, the oldest entry is evicted to make room for the newest.
    Entries can be browsed by strategy or retrieved in reverse-insertion order.
    """

    def __init__(self, max_size: int = 50) -> None:
        self._entries: deque[GraveyardEntry] = deque(maxlen=max_size)

    @property
    def size(self) -> int:
        """Number of entries currently in the graveyard."""
        return len(self._entries)

    def insert(self, entry: GraveyardEntry) -> None:
        """Append an entry to the graveyard.

        When the graveyard is full, the oldest entry is evicted automatically
        by the underlying bounded deque.
        """
        self._entries.append(entry)

    def browse(self, strategy: str | None = None, limit: int = 10) -> list[GraveyardEntry]:
        """Return recent entries, optionally filtered by strategy name.

        Results are returned most-recent-first. At most `limit` entries are
        returned. Pass strategy=None to browse all strategies.
        """
        entries = list(self._entries)
        if strategy is not None:
            entries = [e for e in entries if e.strategy == strategy]
        # Reverse so most recent entries come first, then apply limit.
        return list(reversed(entries))[:limit]

    def save(self, path: Path) -> None:
        """Serialise the graveyard to JSON at the given path.

        Entries are written in insertion order (oldest first) so that load()
        restores the original sequence faithfully.
        """
        payload = [_serialise_entry(entry) for entry in self._entries]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> MutationGraveyard:
        """Load a graveyard from a JSON file previously written by save().

        Returns a fresh empty graveyard when the file does not exist so callers
        do not need to guard against missing files on first run.
        """
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        graveyard = cls()
        for item in data:
            graveyard.insert(_deserialise_entry(item))
        return graveyard


def _serialise_entry(entry: GraveyardEntry) -> dict[str, Any]:
    """Serialise exact rejected material without duplicating trial payloads."""
    payload = asdict(entry)
    for field in ("rejected_snapshot", "parent_assessment", "child_assessment", "mutation"):
        value = getattr(entry, field)
        if value is not None and hasattr(value, "model_dump"):
            payload[field] = value.model_dump(mode="json")
    if entry.timestamp is not None:
        payload["timestamp"] = entry.timestamp.isoformat()
    return payload


def _deserialise_entry(item: dict[str, Any]) -> GraveyardEntry:
    """Restore current exact fields while accepting older optional entries."""
    data = dict(item)
    if data.get("rejected_snapshot") is not None:
        data["rejected_snapshot"] = WorkspaceSnapshot.model_validate(data["rejected_snapshot"])
    if data.get("parent_assessment") is not None:
        data["parent_assessment"] = CandidateAssessment.model_validate(data["parent_assessment"])
    if data.get("child_assessment") is not None:
        data["child_assessment"] = CandidateAssessment.model_validate(data["child_assessment"])
    if data.get("mutation") is not None:
        data["mutation"] = MutationSummary.model_validate(data["mutation"])
    if data.get("timestamp") is not None:
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
    return GraveyardEntry(**data)
