# ABOUTME: Tests for the swarm event log — JSONL append writer and replay reader.
# ABOUTME: Verifies serialisation, ordering, and file-based persistence.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.contracts.evolution import SwarmEvent, SwarmEventType
from aec_bench.evolution.swarm.events import SwarmEventReader, SwarmEventWriter


def _make_event(
    event_type: SwarmEventType = SwarmEventType.EVAL_COMPLETED,
    agent_id: str | None = "agent-1",
    payload: dict | None = None,
    seq: int = 0,
) -> SwarmEvent:
    return SwarmEvent(
        event_type=event_type,
        timestamp="2026-04-07T10:00:00Z",
        agent_id=agent_id,
        payload=payload or {},
        sequence_number=seq,
    )


def test_writer_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = SwarmEventWriter(path)
    writer.emit(_make_event(seq=0))
    assert path.exists()


def test_writer_auto_increments_sequence(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = SwarmEventWriter(path)
    writer.emit(_make_event())
    writer.emit(_make_event())
    writer.emit(_make_event())
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 3
    seqs = [json.loads(line)["sequence_number"] for line in lines]
    assert seqs == [0, 1, 2]


def test_writer_appends_not_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = SwarmEventWriter(path)
    writer.emit(_make_event())
    writer2 = SwarmEventWriter(path, start_sequence=1)
    writer2.emit(_make_event())
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2


def test_reader_reads_all_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = SwarmEventWriter(path)
    writer.emit(_make_event(event_type=SwarmEventType.SWARM_STARTED, agent_id=None))
    writer.emit(_make_event(event_type=SwarmEventType.AGENT_SPAWNED, agent_id="agent-1"))
    writer.emit(_make_event(event_type=SwarmEventType.EVAL_COMPLETED, agent_id="agent-1"))
    reader = SwarmEventReader(path)
    events = reader.read_all()
    assert len(events) == 3
    assert events[0].event_type == SwarmEventType.SWARM_STARTED
    assert events[2].event_type == SwarmEventType.EVAL_COMPLETED


def test_reader_reads_after_sequence(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = SwarmEventWriter(path)
    for i in range(5):
        writer.emit(_make_event(seq=i))
    reader = SwarmEventReader(path)
    events = reader.read_after(sequence_number=2)
    assert len(events) == 2
    assert events[0].sequence_number == 3
    assert events[1].sequence_number == 4


def test_reader_empty_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.touch()
    reader = SwarmEventReader(path)
    assert reader.read_all() == []


def test_reader_missing_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent.jsonl"
    reader = SwarmEventReader(path)
    assert reader.read_all() == []


def test_reader_filter_by_agent(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = SwarmEventWriter(path)
    writer.emit(_make_event(agent_id="agent-1"))
    writer.emit(_make_event(agent_id="agent-2"))
    writer.emit(_make_event(agent_id="agent-1"))
    writer.emit(_make_event(agent_id=None))
    reader = SwarmEventReader(path)
    events = reader.read_all(agent_id="agent-1")
    assert len(events) == 2
    assert all(e.agent_id == "agent-1" for e in events)


def test_reader_filter_by_event_type(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = SwarmEventWriter(path)
    writer.emit(_make_event(event_type=SwarmEventType.EVAL_COMPLETED))
    writer.emit(_make_event(event_type=SwarmEventType.ARCHIVE_UPDATED))
    writer.emit(_make_event(event_type=SwarmEventType.EVAL_COMPLETED))
    reader = SwarmEventReader(path)
    events = reader.read_all(event_type=SwarmEventType.EVAL_COMPLETED)
    assert len(events) == 2
