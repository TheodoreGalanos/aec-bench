# ABOUTME: Tests for the shared note store — SwarmNote CRUD and BD-indexed queries.
# ABOUTME: Verifies insert, browse, region filtering, tag filtering, and persistence.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.evolution import BehaviourDescriptor, SwarmNote
from aec_bench.evolution.swarm.notes import NoteStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bd(**overrides) -> BehaviourDescriptor:
    defaults = dict(
        token_cost=5000.0,
        verification_depth=0.5,
        tool_density=1.0,
        exploration_ratio=0.3,
        deliberation_ratio=0.2,
        reward=0.7,
    )
    defaults.update(overrides)
    return BehaviourDescriptor(**defaults)


def _make_note(
    agent_id: str = "agent-1",
    title: str = "Observation",
    content: str = "Found something interesting.",
    bd_region: BehaviourDescriptor | None = None,
    tags: tuple[str, ...] = (),
    note_id: str | None = None,
) -> SwarmNote:
    return SwarmNote(
        note_id=note_id or f"note-{id(title)}",
        agent_id=agent_id,
        timestamp="2026-04-08T10:00:00Z",
        bd_region=bd_region,
        title=title,
        content=content,
        tags=tags,
    )


# ---------------------------------------------------------------------------
# Empty store
# ---------------------------------------------------------------------------


def test_empty_store() -> None:
    store = NoteStore()
    assert store.size == 0
    assert store.browse_all() == []


# ---------------------------------------------------------------------------
# Insert and browse
# ---------------------------------------------------------------------------


def test_insert_and_browse_all() -> None:
    store = NoteStore()
    store.insert(_make_note(title="First", note_id="n1"))
    store.insert(_make_note(title="Second", note_id="n2"))
    assert store.size == 2
    notes = store.browse_all()
    assert len(notes) == 2
    # Most recent first
    assert notes[0].title == "Second"
    assert notes[1].title == "First"


def test_browse_by_agent() -> None:
    store = NoteStore()
    store.insert(_make_note(agent_id="agent-1", title="A1", note_id="n1"))
    store.insert(_make_note(agent_id="agent-2", title="A2", note_id="n2"))
    store.insert(_make_note(agent_id="agent-1", title="A1b", note_id="n3"))

    results = store.browse_by_agent("agent-1")
    assert len(results) == 2
    assert all(n.agent_id == "agent-1" for n in results)


# ---------------------------------------------------------------------------
# Region-based queries
# ---------------------------------------------------------------------------


def test_browse_for_region_returns_nearest() -> None:
    store = NoteStore()
    bd_low = _make_bd(token_cost=1000.0, reward=0.2)
    bd_high = _make_bd(token_cost=400_000.0, reward=0.9)

    store.insert(_make_note(title="Low region", bd_region=bd_low, note_id="n1"))
    store.insert(_make_note(title="High region", bd_region=bd_high, note_id="n2"))

    query_bd = _make_bd(token_cost=2000.0, reward=0.25)
    results = store.browse_for_region(query_bd, k=1)
    assert len(results) == 1
    assert results[0].title == "Low region"


def test_browse_for_region_untagged_notes_last() -> None:
    store = NoteStore()
    bd = _make_bd(token_cost=5000.0)
    store.insert(_make_note(title="Tagged", bd_region=bd, note_id="n1"))
    store.insert(_make_note(title="Untagged", bd_region=None, note_id="n2"))

    results = store.browse_for_region(_make_bd(), k=10)
    assert len(results) == 2
    assert results[0].title == "Tagged"
    assert results[1].title == "Untagged"


# ---------------------------------------------------------------------------
# Tag filtering
# ---------------------------------------------------------------------------


def test_browse_by_tag() -> None:
    store = NoteStore()
    store.insert(_make_note(title="Tagged", tags=("insight", "mutation"), note_id="n1"))
    store.insert(_make_note(title="Untagged", tags=(), note_id="n2"))
    store.insert(_make_note(title="Also tagged", tags=("insight",), note_id="n3"))

    results = store.browse_by_tag("insight")
    assert len(results) == 2
    titles = {n.title for n in results}
    assert titles == {"Tagged", "Also tagged"}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = NoteStore()
    bd = _make_bd(token_cost=10_000.0)
    store.insert(_make_note(title="Persisted", bd_region=bd, tags=("test",), note_id="n1"))
    store.insert(_make_note(title="Also persisted", note_id="n2"))

    path = tmp_path / "notes.json"
    store.save(path)
    assert path.exists()

    loaded = NoteStore.load(path)
    assert loaded.size == 2
    assert loaded.browse_all()[0].title == "Also persisted"


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    loaded = NoteStore.load(tmp_path / "nonexistent.json")
    assert loaded.size == 0


# ---------------------------------------------------------------------------
# Bounded size
# ---------------------------------------------------------------------------


def test_max_size() -> None:
    store = NoteStore(max_size=3)
    for i in range(5):
        store.insert(_make_note(title=f"Note {i}", note_id=f"n{i}"))
    assert store.size == 3
