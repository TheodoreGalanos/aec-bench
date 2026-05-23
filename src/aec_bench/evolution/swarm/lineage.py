# ABOUTME: Lineage tracker for multi-agent QD swarm evolution.
# ABOUTME: Parent-chain traversal, cross-agent queries, and surprise detection.

from __future__ import annotations

import json
import math
from pathlib import Path

from aec_bench.contracts.evolution import BehaviourDescriptor, LineageNarrative, LineageRecord

# Normalisation ranges for each BD dimension used in surprise detection.
_BD_NORM_RANGES: dict[str, float] = {
    "token_cost": 500_000.0,
    "verification_depth": 1.0,
    "tool_density": 2.0,
    "exploration_ratio": 1.0,
    "deliberation_ratio": 1.0,
    "reward": 1.0,
}

_SURPRISE_THRESHOLD: float = 0.5


class LineageTracker:
    """In-memory lineage store with persistence and surprise detection."""

    def __init__(self) -> None:
        self._records: list[LineageRecord] = []
        self._index: dict[str, LineageRecord] = {}
        self._narratives: dict[str, LineageNarrative] = {}

    def record(self, rec: LineageRecord) -> None:
        """Add a lineage record, indexing by entry_version."""
        self._records.append(rec)
        self._index[rec.entry_version] = rec

    def all_records(self) -> list[LineageRecord]:
        """Return all records in insertion order."""
        return list(self._records)

    def get_by_version(self, version: str) -> LineageRecord | None:
        """Lookup a record by its entry_version."""
        return self._index.get(version)

    def get_lineage_chain(self, version: str) -> list[LineageRecord]:
        """Walk the parent chain from *version* back to root."""
        chain: list[LineageRecord] = []
        current = self._index.get(version)
        while current is not None:
            chain.append(current)
            if current.parent_version is None:
                break
            current = self._index.get(current.parent_version)
        return chain

    def attach_narrative(self, narrative: LineageNarrative) -> None:
        """Attach a freeform narrative to a lineage record."""
        self._narratives[narrative.entry_version] = narrative

    def get_narrative(self, version: str) -> LineageNarrative | None:
        """Look up a narrative by entry version."""
        return self._narratives.get(version)

    def all_narratives(self) -> list[LineageNarrative]:
        """Return all narratives in insertion order."""
        return [self._narratives[r.entry_version] for r in self._records if r.entry_version in self._narratives]

    @property
    def size(self) -> int:
        return len(self._records)

    def cross_agent_records(self) -> list[LineageRecord]:
        """Return records where cross_agent is True."""
        return [r for r in self._records if r.cross_agent]

    @staticmethod
    def is_surprise(
        parent_bd: BehaviourDescriptor,
        child_bd: BehaviourDescriptor,
    ) -> bool:
        """True if normalised Euclidean distance between BDs exceeds threshold."""
        squared_sum = 0.0
        for field, norm_range in _BD_NORM_RANGES.items():
            parent_val = getattr(parent_bd, field)
            child_val = getattr(child_bd, field)
            diff = (child_val - parent_val) / norm_range
            squared_sum += diff * diff
        distance = math.sqrt(squared_sum)
        return distance > _SURPRISE_THRESHOLD

    def save(self, path: Path) -> None:
        """Persist all records and narratives to a JSON file."""
        entries = []
        for r in self._records:
            entry: dict = {"record": r.model_dump(mode="json")}
            narrative = self._narratives.get(r.entry_version)
            if narrative is not None:
                entry["narrative"] = narrative.model_dump(mode="json")
            entries.append(entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries, indent=2))

    @classmethod
    def load(cls, path: Path) -> LineageTracker:
        """Load records and narratives from a JSON file. Returns empty tracker if file missing."""
        tracker = cls()
        if not path.exists():
            return tracker
        raw = json.loads(path.read_text())
        for item in raw:
            # Support both old format (flat record) and new format (record + narrative)
            if "record" in item:
                tracker.record(LineageRecord.model_validate(item["record"]))
                if "narrative" in item:
                    tracker.attach_narrative(LineageNarrative.model_validate(item["narrative"]))
            else:
                tracker.record(LineageRecord.model_validate(item))
        return tracker
