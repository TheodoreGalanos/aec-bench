# ABOUTME: BD-indexed wrapper over GraveyardEntry for multi-agent region queries.
# ABOUTME: Uses Euclidean distance in normalised BD space for nearest-neighbour lookup.

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

from aec_bench.contracts.evolution import BehaviourDescriptor, CandidateAssessment, MutationSummary, WorkspaceSnapshot
from aec_bench.evolution.graveyard import GraveyardEntry

# Normalisation ranges for BD dimensions — maps raw values to [0, 1].
_NORM_RANGES: dict[str, float] = {
    "token_cost": 500_000.0,
    "verification_depth": 1.0,
    "tool_density": 2.0,
    "exploration_ratio": 1.0,
    "deliberation_ratio": 1.0,
    "reward": 1.0,
}


@dataclass(frozen=True)
class _IndexedEntry:
    """Internal pairing of a graveyard entry with its BD and originating agent."""

    entry: GraveyardEntry
    bd: BehaviourDescriptor
    agent_id: str


def _normalise(bd: BehaviourDescriptor) -> tuple[float, ...]:
    """Convert a BehaviourDescriptor to a normalised tuple for distance computation."""
    return (
        bd.token_cost / _NORM_RANGES["token_cost"],
        bd.verification_depth / _NORM_RANGES["verification_depth"],
        bd.tool_density / _NORM_RANGES["tool_density"],
        bd.exploration_ratio / _NORM_RANGES["exploration_ratio"],
        bd.deliberation_ratio / _NORM_RANGES["deliberation_ratio"],
        bd.reward / _NORM_RANGES["reward"],
    )


def _euclidean_distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Euclidean distance between two normalised BD vectors."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


class SharedGraveyard:
    """BD-indexed graveyard shared across swarm agents.

    Wraps GraveyardEntry with BehaviourDescriptor indexing so agents can
    query failures by BD region (nearest neighbours in normalised space),
    by agent identity, or browse all failures globally.
    """

    def __init__(self, max_size: int = 200) -> None:
        self._entries: deque[_IndexedEntry] = deque(maxlen=max_size)

    @property
    def size(self) -> int:
        """Number of entries in the graveyard."""
        return len(self._entries)

    def insert(self, entry: GraveyardEntry, bd: BehaviourDescriptor, agent_id: str) -> None:
        """Add a failure with its BD coordinates and originating agent."""
        self._entries.append(_IndexedEntry(entry=entry, bd=bd, agent_id=agent_id))

    def browse(self, strategy: str | None = None, limit: int = 10) -> list[GraveyardEntry]:
        """Return recent failures, optionally filtered by strategy.

        Compatible with MutationGraveyard.browse() so the evolution engine
        can use SharedGraveyard as a drop-in via duck typing.
        """
        entries = [ie.entry for ie in reversed(self._entries)]
        if strategy is not None:
            entries = [e for e in entries if e.strategy == strategy]
        return entries[:limit]

    def browse_all(self, limit: int = 50) -> list[GraveyardEntry]:
        """Return all failures, most recent first."""
        return [ie.entry for ie in reversed(self._entries)][:limit]

    def browse_by_agent(self, agent_id: str, limit: int = 20) -> list[GraveyardEntry]:
        """Return failures from a specific agent, most recent first."""
        return [ie.entry for ie in reversed(self._entries) if ie.agent_id == agent_id][:limit]

    def browse_for_region(self, bd: BehaviourDescriptor, k: int = 10) -> list[GraveyardEntry]:
        """Return the k nearest failures by BD distance (normalised Euclidean)."""
        if not self._entries:
            return []

        query_vec = _normalise(bd)
        scored: list[tuple[float, _IndexedEntry]] = [
            (_euclidean_distance(query_vec, _normalise(ie.bd)), ie) for ie in self._entries
        ]
        scored.sort(key=lambda pair: pair[0])
        return [ie.entry for _, ie in scored[:k]]

    def save(self, path: Path) -> None:
        """Persist the graveyard to a JSON file.

        Each record stores the entry dict, BD dict, and agent_id so that
        region queries work after reload.
        """
        payload = []
        for indexed in self._entries:
            entry = asdict(indexed.entry)
            for field_name in ("rejected_snapshot", "parent_assessment", "child_assessment", "mutation"):
                value = getattr(indexed.entry, field_name)
                if value is not None and hasattr(value, "model_dump"):
                    entry[field_name] = value.model_dump(mode="json")
            if indexed.entry.timestamp is not None:
                entry["timestamp"] = indexed.entry.timestamp.isoformat()
            payload.append({"entry": entry, "bd": indexed.bd.model_dump(), "agent_id": indexed.agent_id})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SharedGraveyard:
        """Load from a JSON file previously written by save().

        Returns a fresh empty graveyard when the file does not exist.
        """
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        graveyard = cls()
        for item in data:
            raw_entry = dict(item["entry"])
            if raw_entry.get("rejected_snapshot") is not None:
                raw_entry["rejected_snapshot"] = WorkspaceSnapshot.model_validate(raw_entry["rejected_snapshot"])
            if raw_entry.get("parent_assessment") is not None:
                raw_entry["parent_assessment"] = CandidateAssessment.model_validate(raw_entry["parent_assessment"])
            if raw_entry.get("child_assessment") is not None:
                raw_entry["child_assessment"] = CandidateAssessment.model_validate(raw_entry["child_assessment"])
            if raw_entry.get("mutation") is not None:
                raw_entry["mutation"] = MutationSummary.model_validate(raw_entry["mutation"])
            if raw_entry.get("timestamp") is not None:
                from datetime import datetime

                raw_entry["timestamp"] = datetime.fromisoformat(raw_entry["timestamp"])
            entry = GraveyardEntry(**raw_entry)
            bd = BehaviourDescriptor(**item["bd"])
            graveyard.insert(entry, bd, item["agent_id"])
        return graveyard
