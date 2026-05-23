# ABOUTME: Tests for BD-indexed SharedGraveyard with region-based queries.
# ABOUTME: Verifies insert, browse, nearest-neighbour lookup, and persistence.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.evolution import BehaviourDescriptor
from aec_bench.evolution.graveyard import GraveyardEntry
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard


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


def _make_entry(cycle: int = 1, score_before: float = 0.5, score_after: float = 0.3) -> GraveyardEntry:
    return GraveyardEntry(
        cycle=cycle,
        strategy="tweak",
        mutation_description=f"cycle-{cycle} mutation",
        score_before=score_before,
        score_after=score_after,
        workspace_version="v1",
        failure_reason="score dropped",
    )


def test_empty_graveyard() -> None:
    sg = SharedGraveyard()
    assert sg.browse_all() == []
    assert sg.browse_by_agent("agent-1") == []
    assert sg.browse_for_region(_make_bd()) == []


def test_insert_and_browse_all() -> None:
    sg = SharedGraveyard()
    entry = _make_entry(cycle=1)
    bd = _make_bd()
    sg.insert(entry, bd, "agent-1")

    results = sg.browse_all(limit=10)
    assert len(results) == 1
    assert results[0].cycle == 1


def test_browse_by_agent() -> None:
    sg = SharedGraveyard()
    sg.insert(_make_entry(cycle=1), _make_bd(), "agent-1")
    sg.insert(_make_entry(cycle=2), _make_bd(), "agent-2")
    sg.insert(_make_entry(cycle=3), _make_bd(), "agent-1")

    results = sg.browse_by_agent("agent-1", limit=20)
    assert len(results) == 2
    # Most recent first
    assert results[0].cycle == 3
    assert results[1].cycle == 1


def test_browse_for_region_returns_nearest() -> None:
    sg = SharedGraveyard()
    bd_low = _make_bd(token_cost=1000, reward=0.2)
    bd_high = _make_bd(token_cost=400_000, reward=0.9)
    bd_mid = _make_bd(token_cost=50_000, reward=0.5)

    sg.insert(_make_entry(cycle=1), bd_low, "agent-1")
    sg.insert(_make_entry(cycle=2), bd_high, "agent-2")
    sg.insert(_make_entry(cycle=3), bd_mid, "agent-3")

    # Query near bd_low — should return cycle=1 first
    query = _make_bd(token_cost=2000, reward=0.2)
    results = sg.browse_for_region(query, k=2)
    assert len(results) == 2
    assert results[0].cycle == 1


def test_region_k_greater_than_entries() -> None:
    sg = SharedGraveyard()
    sg.insert(_make_entry(cycle=1), _make_bd(), "agent-1")
    sg.insert(_make_entry(cycle=2), _make_bd(), "agent-2")

    results = sg.browse_for_region(_make_bd(), k=10)
    assert len(results) == 2


def test_save_load_roundtrip(tmp_path: Path) -> None:
    sg = SharedGraveyard()
    sg.insert(_make_entry(cycle=1), _make_bd(token_cost=5000), "agent-1")
    sg.insert(_make_entry(cycle=2), _make_bd(token_cost=20000), "agent-2")

    save_path = tmp_path / "graveyard.json"
    sg.save(save_path)

    loaded = SharedGraveyard.load(save_path)
    assert len(loaded.browse_all()) == 2
    # Check persistence preserved BD data — region query should work
    query = _make_bd(token_cost=5000)
    results = loaded.browse_for_region(query, k=1)
    assert results[0].cycle == 1


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.json"
    sg = SharedGraveyard.load(missing)
    assert sg.browse_all() == []


def test_global_max_size() -> None:
    sg = SharedGraveyard(max_size=3)
    for i in range(5):
        sg.insert(_make_entry(cycle=i), _make_bd(), f"agent-{i}")

    results = sg.browse_all(limit=50)
    assert len(results) == 3
    # Most recent first: cycles 4, 3, 2
    assert results[0].cycle == 4
    assert results[1].cycle == 3
    assert results[2].cycle == 2
