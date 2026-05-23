# ABOUTME: Graveyard archive for failed mutations — stores rejected changes for later rescue.
# ABOUTME: Failed mutations are kept instead of discarded, enabling the evolver to learn from them.

from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class GraveyardEntry:
    """A single failed mutation stored for potential future rescue."""

    cycle: int
    strategy: str
    mutation_description: str
    score_before: float
    score_after: float
    workspace_version: str
    failure_reason: str

    # Enrichment fields — populated from engine data when available.
    # None for backwards compatibility with pre-enrichment graveyard files.
    field_failures: dict[str, str] | None = None
    detected_patterns: list[str] | None = None
    mutation_actions: list[dict] | None = None
    investigation_summary: str | None = None


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
        payload = [asdict(entry) for entry in self._entries]
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
            graveyard.insert(GraveyardEntry(**item))
        return graveyard
