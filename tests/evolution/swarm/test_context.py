# ABOUTME: Tests for archive context message builder used in swarm agent conversations.
# ABOUTME: Verifies header, coverage, agent performance, graveyard, and top performers.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.contracts.evolution import (
    BehaviourDescriptor,
    SwarmNote,
    WorkspaceSnapshot,
)
from aec_bench.evolution.graveyard import GraveyardEntry
from aec_bench.evolution.swarm.context import build_archive_context
from aec_bench.evolution.swarm.notes import NoteStore
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bd(
    token_cost: float = 10_000,
    reward: float = 0.5,
    verification_depth: float = 0.3,
    tool_density: float = 0.5,
    exploration_ratio: float = 0.2,
    deliberation_ratio: float = 0.3,
) -> BehaviourDescriptor:
    return BehaviourDescriptor(
        token_cost=token_cost,
        verification_depth=verification_depth,
        tool_density=tool_density,
        exploration_ratio=exploration_ratio,
        deliberation_ratio=deliberation_ratio,
        reward=reward,
    )


def _make_snapshot(version: str = "v1") -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        system_prompt="Test prompt",
        skills=[],
        workspace_version=version,
    )


def _make_graveyard_entry(
    cycle: int = 1,
    score_before: float = 0.5,
    score_after: float = 0.3,
    failure_reason: str = "score dropped",
) -> GraveyardEntry:
    return GraveyardEntry(
        cycle=cycle,
        strategy="tweak",
        mutation_description=f"cycle-{cycle} mutation",
        score_before=score_before,
        score_after=score_after,
        workspace_version="v1",
        failure_reason=failure_reason,
    )


@dataclass
class _FakeArchiveEntry:
    """Mimics ArchiveEntry for test purposes without pyribs dependency."""

    snapshot: WorkspaceSnapshot
    bd: BehaviourDescriptor
    run_id: str = ""
    discipline: str = ""


class _FakeArchive:
    """Minimal archive stub implementing the protocol expected by build_archive_context."""

    def __init__(self) -> None:
        self._entries: list[_FakeArchiveEntry] = []

    def coverage_report(self) -> dict:
        total = max(len(self._entries), 50)
        return {
            "occupied": len(self._entries),
            "empty": total - len(self._entries),
            "coverage": len(self._entries) / total if total else 0.0,
            "total_centroids": total,
        }

    def top_k(self, k: int = 5) -> list[_FakeArchiveEntry]:
        sorted_entries = sorted(self._entries, key=lambda e: e.bd.reward, reverse=True)
        return sorted_entries[:k]

    def to_summary(self) -> dict:
        rewards = [e.bd.reward for e in self._entries]
        return {
            "size": len(self._entries),
            "n_centroids": 50,
            "coverage": len(self._entries) / 50.0,
            "best_reward": max(rewards) if rewards else 0.0,
            "mean_reward": sum(rewards) / len(rewards) if rewards else 0.0,
        }

    def add(self, bd: BehaviourDescriptor, snapshot: WorkspaceSnapshot, **kwargs: object) -> None:
        """Test helper to populate the fake archive."""
        self._entries.append(
            _FakeArchiveEntry(
                snapshot=snapshot,
                bd=bd,
                run_id=kwargs.get("run_id", ""),
                discipline=kwargs.get("discipline", ""),
            )
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_archive_produces_valid_header() -> None:
    """Empty archive should still produce a valid markdown with generation header."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=3,
        agent_recent_scores=[],
        agent_best_score=0.0,
    )

    assert "## Current Archive State (Generation 3)" in result
    assert isinstance(result, str)


def test_includes_coverage_info() -> None:
    """Coverage line should reflect archive occupancy."""
    archive = _FakeArchive()
    archive.add(_make_bd(reward=0.7), _make_snapshot("v1"))
    archive.add(_make_bd(reward=0.8), _make_snapshot("v2"))
    graveyard = SharedGraveyard()

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=5,
        agent_recent_scores=[0.6, 0.7],
        agent_best_score=0.7,
    )

    assert "Coverage" in result or "coverage" in result
    # Should contain the occupied count
    assert "2" in result


def test_includes_agent_performance() -> None:
    """Output should contain the agent's recent scores and best score."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-2",
        agent_bd_focus=None,
        generation=1,
        agent_recent_scores=[0.45, 0.52, 0.61],
        agent_best_score=0.61,
    )

    assert "### Your Recent Performance" in result
    assert "0.45" in result
    assert "0.52" in result
    assert "0.61" in result
    assert "Best" in result or "best" in result


def test_includes_graveyard_failures() -> None:
    """Graveyard entries should appear in the Relevant Failures section."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()
    bd = _make_bd(reward=0.3)
    entry = _make_graveyard_entry(cycle=2, failure_reason="verification failed")
    graveyard.insert(entry, bd, "agent-1")

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=4,
        agent_recent_scores=[0.3],
        agent_best_score=0.3,
    )

    assert "### Relevant Failures" in result
    assert "verification failed" in result


def test_includes_top_performers() -> None:
    """Top performers section should list entries sorted by reward."""
    archive = _FakeArchive()
    archive.add(
        _make_bd(reward=0.9),
        _make_snapshot("v-best"),
        run_id="run-1",
        discipline="electrical",
    )
    archive.add(
        _make_bd(reward=0.6),
        _make_snapshot("v-mid"),
        run_id="run-1",
        discipline="electrical",
    )
    archive.add(
        _make_bd(reward=0.3),
        _make_snapshot("v-low"),
        run_id="run-1",
        discipline="electrical",
    )
    graveyard = SharedGraveyard()

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=2,
        agent_recent_scores=[],
        agent_best_score=0.0,
    )

    assert "### Top Performers" in result
    assert "v-best" in result
    assert "0.9" in result
    # v-best should appear before v-low
    best_pos = result.index("v-best")
    low_pos = result.index("v-low")
    assert best_pos < low_pos


def test_region_filtered_graveyard_with_bd_focus() -> None:
    """When agent has a BD focus, graveyard should use region-based filtering."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()

    # Insert a nearby failure and a distant one
    near_bd = _make_bd(token_cost=5_000, reward=0.3)
    far_bd = _make_bd(token_cost=400_000, reward=0.9)
    near_entry = _make_graveyard_entry(cycle=1, failure_reason="near failure")
    far_entry = _make_graveyard_entry(cycle=2, failure_reason="far failure")
    graveyard.insert(near_entry, near_bd, "agent-2")
    graveyard.insert(far_entry, far_bd, "agent-3")

    focus_bd = _make_bd(token_cost=6_000, reward=0.3)

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=focus_bd,
        generation=1,
        agent_recent_scores=[],
        agent_best_score=0.0,
    )

    assert "### Relevant Failures" in result
    # Near failure should appear (it's the closest to our focus BD)
    assert "near failure" in result


# ---------------------------------------------------------------------------
# Pivot context
# ---------------------------------------------------------------------------


def test_pivot_message_injected_when_pivoting() -> None:
    """When pivoting=True, context should include a pivot section."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=10,
        agent_recent_scores=[0.5, 0.5, 0.5, 0.5, 0.5],
        agent_best_score=0.5,
        pivoting=True,
        consecutive_non_improving=5,
    )

    assert "pivot" in result.lower() or "stuck" in result.lower() or "different" in result.lower()


def test_no_pivot_message_when_not_pivoting() -> None:
    """When pivoting=False, no pivot section should appear."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=5,
        agent_recent_scores=[0.5, 0.6, 0.7],
        agent_best_score=0.7,
        pivoting=False,
    )

    assert "pivot" not in result.lower()
    assert "stuck" not in result.lower()


# ---------------------------------------------------------------------------
# Notes in context
# ---------------------------------------------------------------------------


def test_notes_included_when_present() -> None:
    """Notes from other agents should appear in context."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()
    notes = NoteStore()
    notes.insert(
        SwarmNote(
            note_id="n1",
            agent_id="agent-2",
            timestamp="2026-04-08T10:00:00Z",
            title="Insight from agent-2",
            content="Verification skills help in this region.",
            tags=("reflect",),
        )
    )

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=5,
        agent_recent_scores=[],
        agent_best_score=0.0,
        notes=notes,
    )

    assert "### Shared Notes" in result
    assert "Insight from agent-2" in result
    assert "Verification skills" in result


def test_notes_excluded_from_own_agent() -> None:
    """An agent should not see its own notes in the context."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()
    notes = NoteStore()
    notes.insert(
        SwarmNote(
            note_id="n1",
            agent_id="agent-1",
            timestamp="2026-04-08T10:00:00Z",
            title="My own note",
            content="This is mine.",
        )
    )

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=5,
        agent_recent_scores=[],
        agent_best_score=0.0,
        notes=notes,
    )

    # No notes section when only own notes exist
    assert "My own note" not in result


# ---------------------------------------------------------------------------
# Nudged specialisation
# ---------------------------------------------------------------------------


def test_nudge_injected_when_provided() -> None:
    """When a nudge is provided, context should include an exploration focus section."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=1,
        agent_recent_scores=[],
        agent_best_score=0.0,
        nudge="Focus on token-efficient harnesses with low token_cost.",
    )

    assert "### Exploration Focus" in result
    assert "token-efficient" in result


def test_no_nudge_when_not_provided() -> None:
    """No nudge section when nudge is None."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=1,
        agent_recent_scores=[],
        agent_best_score=0.0,
    )

    assert "Exploration Focus" not in result


def test_no_notes_section_when_empty() -> None:
    """No notes section when NoteStore is empty."""
    archive = _FakeArchive()
    graveyard = SharedGraveyard()
    notes = NoteStore()

    result = build_archive_context(
        archive=archive,
        graveyard=graveyard,
        agent_id="agent-1",
        agent_bd_focus=None,
        generation=5,
        agent_recent_scores=[],
        agent_best_score=0.0,
        notes=notes,
    )

    assert "### Shared Notes" not in result
