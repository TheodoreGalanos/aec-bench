# ABOUTME: Tests for LineageTracker with parent-chain traversal and surprise detection.
# ABOUTME: Covers record/retrieve, lineage chains, cross-agent filtering, and persistence.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.evolution import BehaviourDescriptor, LineageRecord
from aec_bench.evolution.swarm.lineage import LineageTracker


def _make_record(
    version: str,
    parent: str | None = None,
    agent: str = "agent-1",
    cross_agent: bool = False,
    cross_source: str | None = None,
    mutation: str = "mutate",
) -> LineageRecord:
    return LineageRecord(
        entry_version=version,
        parent_version=parent,
        source_agent_id=agent,
        cross_agent=cross_agent,
        cross_agent_source=cross_source,
        mutation_type=mutation,
        timestamp="2026-04-07T00:00:00Z",
    )


def _make_bd(
    token_cost: float = 5000.0,
    verification_depth: float = 0.5,
    tool_density: float = 0.8,
    exploration_ratio: float = 0.3,
    deliberation_ratio: float = 0.2,
    reward: float = 0.7,
) -> BehaviourDescriptor:
    return BehaviourDescriptor(
        token_cost=token_cost,
        verification_depth=verification_depth,
        tool_density=tool_density,
        exploration_ratio=exploration_ratio,
        deliberation_ratio=deliberation_ratio,
        reward=reward,
    )


def test_empty_tracker() -> None:
    tracker = LineageTracker()
    assert tracker.all_records() == []


def test_record_and_retrieve() -> None:
    tracker = LineageTracker()
    rec = _make_record("v1")
    tracker.record(rec)
    records = tracker.all_records()
    assert len(records) == 1
    assert records[0].entry_version == "v1"


def test_get_by_version() -> None:
    tracker = LineageTracker()
    tracker.record(_make_record("v1"))
    tracker.record(_make_record("v2", parent="v1"))
    result = tracker.get_by_version("v2")
    assert result is not None
    assert result.entry_version == "v2"
    assert result.parent_version == "v1"


def test_get_by_version_missing() -> None:
    tracker = LineageTracker()
    tracker.record(_make_record("v1"))
    assert tracker.get_by_version("v999") is None


def test_lineage_chain_three_entries() -> None:
    tracker = LineageTracker()
    tracker.record(_make_record("v1"))
    tracker.record(_make_record("v2", parent="v1"))
    tracker.record(_make_record("v3", parent="v2"))
    chain = tracker.get_lineage_chain("v3")
    assert [r.entry_version for r in chain] == ["v3", "v2", "v1"]


def test_lineage_chain_single() -> None:
    tracker = LineageTracker()
    tracker.record(_make_record("v1"))
    chain = tracker.get_lineage_chain("v1")
    assert len(chain) == 1
    assert chain[0].entry_version == "v1"


def test_cross_agent_records() -> None:
    tracker = LineageTracker()
    tracker.record(_make_record("v1"))
    tracker.record(_make_record("v2", cross_agent=True, cross_source="agent-2"))
    tracker.record(_make_record("v3"))
    cross = tracker.cross_agent_records()
    assert len(cross) == 1
    assert cross[0].entry_version == "v2"
    assert cross[0].cross_agent_source == "agent-2"


def test_surprise_by_bd_distance() -> None:
    """Token cost jumps 1000->400000, reward 0.3->0.9 => surprise."""
    tracker = LineageTracker()
    parent_bd = _make_bd(token_cost=1000.0, reward=0.3)
    child_bd = _make_bd(token_cost=400000.0, reward=0.9)
    assert tracker.is_surprise(parent_bd, child_bd) is True


def test_no_surprise_for_nearby_bds() -> None:
    """Token cost 5000->5500, reward 0.7->0.72 => not a surprise."""
    tracker = LineageTracker()
    parent_bd = _make_bd(token_cost=5000.0, reward=0.7)
    child_bd = _make_bd(token_cost=5500.0, reward=0.72)
    assert tracker.is_surprise(parent_bd, child_bd) is False


def test_save_load_roundtrip(tmp_path: Path) -> None:
    tracker = LineageTracker()
    tracker.record(_make_record("v1"))
    tracker.record(_make_record("v2", parent="v1"))
    filepath = tmp_path / "lineage.json"
    tracker.save(filepath)

    loaded = LineageTracker.load(filepath)
    assert len(loaded.all_records()) == 2
    chain = loaded.get_lineage_chain("v2")
    assert [r.entry_version for r in chain] == ["v2", "v1"]


def test_load_missing_file(tmp_path: Path) -> None:
    filepath = tmp_path / "does_not_exist.json"
    tracker = LineageTracker.load(filepath)
    assert tracker.all_records() == []


# ---------------------------------------------------------------------------
# Lineage narratives
# ---------------------------------------------------------------------------


def test_attach_and_retrieve_narrative() -> None:
    from aec_bench.contracts.evolution import LineageNarrative

    tracker = LineageTracker()
    tracker.record(_make_record("v1"))

    narrative = LineageNarrative(
        entry_version="v1",
        agent_reasoning="Tried adding verification skill to improve accuracy.",
        investigation_context="Archive coverage was 5%. Targeted low-token region.",
    )
    tracker.attach_narrative(narrative)

    result = tracker.get_narrative("v1")
    assert result is not None
    assert "verification skill" in result.agent_reasoning


def test_narrative_missing_returns_none() -> None:
    tracker = LineageTracker()
    tracker.record(_make_record("v1"))
    assert tracker.get_narrative("v1") is None


def test_all_narratives() -> None:
    from aec_bench.contracts.evolution import LineageNarrative

    tracker = LineageTracker()
    tracker.record(_make_record("v1"))
    tracker.record(_make_record("v2", parent="v1"))

    tracker.attach_narrative(
        LineageNarrative(
            entry_version="v1",
            agent_reasoning="First attempt.",
        )
    )
    tracker.attach_narrative(
        LineageNarrative(
            entry_version="v2",
            agent_reasoning="Improved on v1.",
        )
    )

    narratives = tracker.all_narratives()
    assert len(narratives) == 2
    assert narratives[0].entry_version == "v1"


def test_narrative_roundtrip(tmp_path: Path) -> None:
    from aec_bench.contracts.evolution import LineageNarrative

    tracker = LineageTracker()
    tracker.record(_make_record("v1"))
    tracker.attach_narrative(
        LineageNarrative(
            entry_version="v1",
            agent_reasoning="Added cable-sizing skill.",
            investigation_context="Score was 0.5, needed improvement.",
            surprise_explanation="Unexpectedly improved token efficiency.",
        )
    )

    filepath = tmp_path / "lineage.json"
    tracker.save(filepath)

    loaded = LineageTracker.load(filepath)
    narrative = loaded.get_narrative("v1")
    assert narrative is not None
    assert narrative.agent_reasoning == "Added cable-sizing skill."
    assert narrative.surprise_explanation == "Unexpectedly improved token efficiency."
