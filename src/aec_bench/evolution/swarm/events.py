# ABOUTME: Event log writer and reader for swarm state persistence.
# ABOUTME: Uses JSONL format — one JSON object per line, append-only.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.evolution import SwarmEvent, SwarmEventType


class SwarmEventWriter:
    """Append-only JSONL event writer for swarm state changes."""

    def __init__(self, path: Path, start_sequence: int = 0) -> None:
        self._path = path
        self._next_sequence = start_sequence

    def emit(self, event: SwarmEvent) -> None:
        """Append an event to the log with auto-incremented sequence number."""
        updated = event.model_copy(update={"sequence_number": self._next_sequence})
        line = updated.model_dump_json() + "\n"
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)
        self._next_sequence += 1

    @property
    def next_sequence(self) -> int:
        return self._next_sequence


class SwarmEventReader:
    """Read and filter events from a JSONL event log."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def read_all(
        self,
        agent_id: str | None = None,
        event_type: SwarmEventType | None = None,
    ) -> list[SwarmEvent]:
        """Read all events, optionally filtered by agent_id or event_type."""
        if not self._path.exists():
            return []
        events: list[SwarmEvent] = []
        for line in self._path.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            event = SwarmEvent.model_validate_json(line)
            if agent_id is not None and event.agent_id != agent_id:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            events.append(event)
        return events

    def read_after(self, sequence_number: int) -> list[SwarmEvent]:
        """Read events with sequence_number strictly greater than the given value."""
        all_events = self.read_all()
        return [e for e in all_events if e.sequence_number > sequence_number]
