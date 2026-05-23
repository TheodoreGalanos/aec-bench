# ABOUTME: Shared note store for ad-hoc knowledge sharing between swarm agents.
# ABOUTME: Notes are BD-indexed for region-filtered queries, similar to SharedGraveyard.

from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path

from aec_bench.contracts.evolution import BehaviourDescriptor, SwarmNote

# Normalisation ranges — matches archive.py and shared_graveyard.py.
_BD_RANGES: list[tuple[str, float]] = [
    ("token_cost", 500_000.0),
    ("verification_depth", 1.0),
    ("tool_density", 2.0),
    ("exploration_ratio", 1.0),
    ("deliberation_ratio", 1.0),
    ("reward", 1.0),
]


def _bd_distance(a: BehaviourDescriptor, b: BehaviourDescriptor) -> float:
    """Euclidean distance between two BDs in normalised space."""
    total = 0.0
    for attr, max_val in _BD_RANGES:
        va = getattr(a, attr) / max_val if max_val > 0 else 0.0
        vb = getattr(b, attr) / max_val if max_val > 0 else 0.0
        total += (va - vb) ** 2
    return math.sqrt(total)


class NoteStore:
    """Bounded store for SwarmNote entries with BD-indexed retrieval.

    Notes are shared across all swarm agents. Each note carries an optional
    BD region tag so agents can query for notes relevant to their current
    exploration focus.
    """

    def __init__(self, max_size: int = 200) -> None:
        self._notes: deque[SwarmNote] = deque(maxlen=max_size)

    @property
    def size(self) -> int:
        return len(self._notes)

    def insert(self, note: SwarmNote) -> None:
        """Add a note to the store."""
        self._notes.append(note)

    def browse_all(self, limit: int = 20) -> list[SwarmNote]:
        """Return all notes, most recent first."""
        return list(reversed(self._notes))[:limit]

    def browse_by_agent(self, agent_id: str, limit: int = 10) -> list[SwarmNote]:
        """Return notes from a specific agent, most recent first."""
        return [n for n in reversed(self._notes) if n.agent_id == agent_id][:limit]

    def browse_for_region(
        self,
        bd: BehaviourDescriptor,
        k: int = 10,
    ) -> list[SwarmNote]:
        """Return the k notes nearest to the given BD region.

        Notes without a BD region tag are included at infinite distance
        (they appear last, only if fewer than k region-tagged notes exist).
        """
        if not self._notes:
            return []

        scored: list[tuple[float, SwarmNote]] = []
        for note in self._notes:
            if note.bd_region is not None:
                dist = _bd_distance(note.bd_region, bd)
            else:
                dist = float("inf")
            scored.append((dist, note))

        scored.sort(key=lambda x: x[0])
        return [note for _, note in scored[:k]]

    def browse_by_tag(self, tag: str, limit: int = 10) -> list[SwarmNote]:
        """Return notes with a specific tag, most recent first."""
        return [n for n in reversed(self._notes) if tag in n.tags][:limit]

    def save(self, path: Path) -> None:
        """Persist notes to JSON."""
        payload = [n.model_dump() for n in self._notes]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> NoteStore:
        """Load notes from JSON. Returns empty store if file missing."""
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        store = cls()
        for item in data:
            store.insert(SwarmNote.model_validate(item))
        return store
