# ABOUTME: Tests for QDArchive.project_2d_with_centroids() returning all CVT centroids.
# ABOUTME: Validates that both occupied and empty centroids are projected to 2D.

import pytest

from aec_bench.contracts.evolution import BehaviourDescriptor, WorkspaceSnapshot
from aec_bench.evolution.archive import QDArchive


def _make_bd(**overrides) -> BehaviourDescriptor:
    defaults = dict(
        token_cost=0.5,
        verification_depth=0.5,
        tool_density=0.5,
        exploration_ratio=0.5,
        deliberation_ratio=0.5,
        reward=0.8,
    )
    defaults.update(overrides)
    return BehaviourDescriptor(**defaults)


def _make_snapshot(version: str) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        workspace_version=version,
        system_prompt="test",
        skills=[],
    )


def test_project_2d_with_centroids_empty_archive():
    archive = QDArchive(n_centroids=50)
    result = archive.project_2d_with_centroids()
    assert len(result) == 50
    assert all(c["occupied"] is False for c in result)
    assert all("x" in c and "y" in c for c in result)


def test_project_2d_with_centroids_with_entries():
    archive = QDArchive(n_centroids=50)
    bd = _make_bd(reward=0.9)
    snapshot = _make_snapshot("evo-1")
    archive.insert(bd=bd, snapshot=snapshot)

    result = archive.project_2d_with_centroids()
    assert len(result) == 50

    occupied = [c for c in result if c["occupied"]]
    empty = [c for c in result if not c["occupied"]]

    assert len(occupied) == 1
    assert occupied[0]["reward"] == pytest.approx(0.9)
    assert occupied[0]["version"] == "evo-1"
    assert len(empty) == 49


def test_project_2d_with_centroids_agent_mapping():
    archive = QDArchive(n_centroids=50)
    bd = _make_bd()
    snapshot = _make_snapshot("evo-1")
    archive.insert(bd=bd, snapshot=snapshot)

    agent_map = {"evo-1": "agent-0"}
    result = archive.project_2d_with_centroids(agent_map=agent_map)

    occupied = [c for c in result if c["occupied"]]
    assert occupied[0]["agent_id"] == "agent-0"
