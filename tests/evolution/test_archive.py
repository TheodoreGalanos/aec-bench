# ABOUTME: Tests for the QDArchive — CVT-MAP-Elites archive for harness evolution.
# ABOUTME: Verifies insert, query, projection, and summary operations.

import pytest

from aec_bench.contracts.evolution import BehaviourDescriptor, WorkspaceSnapshot
from aec_bench.evolution.archive import QDArchive

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bd(
    token_cost: float = 1000.0,
    verification_depth: float = 0.5,
    tool_density: float = 1.0,
    exploration_ratio: float = 0.3,
    deliberation_ratio: float = 0.2,
    reward: float = 0.8,
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
        system_prompt="You are a helpful assistant.",
        skills=[],
        workspace_version=version,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_archive_starts_empty() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    assert archive.size == 0


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------


def test_insert_increases_size() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    accepted = archive.insert(bd=_make_bd(), snapshot=_make_snapshot("v1"))
    assert accepted is True
    assert archive.size == 1


def test_insert_better_replaces_worse_at_same_cell() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    bd_weak = _make_bd(reward=0.3)
    bd_strong = _make_bd(reward=0.9)

    archive.insert(bd=bd_weak, snapshot=_make_snapshot("v_weak"))
    size_after_first = archive.size

    # Insert with the exact same measures but higher reward — must replace.
    accepted = archive.insert(bd=bd_strong, snapshot=_make_snapshot("v_strong"))
    assert accepted is True
    assert archive.size == size_after_first  # same cell, no growth


def test_insert_worse_does_not_replace() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    bd_strong = _make_bd(reward=0.9)
    bd_weak = _make_bd(reward=0.3)

    archive.insert(bd=bd_strong, snapshot=_make_snapshot("v_strong"))
    accepted = archive.insert(bd=bd_weak, snapshot=_make_snapshot("v_weak"))
    assert accepted is False


# ---------------------------------------------------------------------------
# Diverse entries fill different cells
# ---------------------------------------------------------------------------


def test_diverse_bds_fill_different_cells() -> None:
    archive = QDArchive(n_centroids=200, seed=42)

    # Two BDs at extreme opposite corners of the space.
    bd_a = _make_bd(
        token_cost=0.0,
        verification_depth=0.0,
        tool_density=0.0,
        exploration_ratio=0.0,
        deliberation_ratio=0.0,
        reward=0.1,
    )
    bd_b = _make_bd(
        token_cost=500_000.0,
        verification_depth=1.0,
        tool_density=2.0,
        exploration_ratio=1.0,
        deliberation_ratio=1.0,
        reward=0.9,
    )

    archive.insert(bd=bd_a, snapshot=_make_snapshot("va"))
    archive.insert(bd=bd_b, snapshot=_make_snapshot("vb"))

    assert archive.size == 2


# ---------------------------------------------------------------------------
# Query nearest
# ---------------------------------------------------------------------------


def test_query_nearest_empty_returns_none() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    result = archive.query_nearest(bd=_make_bd())
    assert result is None


def test_query_nearest_returns_snapshot() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    snapshot = _make_snapshot("v_query")
    archive.insert(bd=_make_bd(), snapshot=snapshot)

    result = archive.query_nearest(bd=_make_bd())
    assert result is not None
    assert result.workspace_version == "v_query"


# ---------------------------------------------------------------------------
# project_2d
# ---------------------------------------------------------------------------


def test_project_2d_empty_returns_empty_list() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    assert archive.project_2d() == []


def test_project_2d_single_entry_returns_origin_point() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    archive.insert(bd=_make_bd(reward=0.7), snapshot=_make_snapshot("v_single"))
    points = archive.project_2d()
    assert len(points) == 1
    assert points[0]["x"] == 0.0
    assert points[0]["y"] == 0.0
    assert points[0]["reward"] == pytest.approx(0.7)
    assert "version" in points[0]


def test_project_2d_multiple_entries_have_required_keys() -> None:
    archive = QDArchive(n_centroids=200, seed=42)
    bds = [_make_bd(token_cost=float(i * 10_000), reward=float(i) * 0.1) for i in range(1, 6)]
    for i, bd in enumerate(bds):
        archive.insert(bd=bd, snapshot=_make_snapshot(f"v{i}"))

    points = archive.project_2d()
    assert len(points) > 0
    for point in points:
        assert "x" in point
        assert "y" in point
        assert "reward" in point
        assert "version" in point


# ---------------------------------------------------------------------------
# to_summary
# ---------------------------------------------------------------------------


def test_to_summary_keys_present() -> None:
    archive = QDArchive(n_centroids=100, seed=0)
    summary = archive.to_summary()
    assert "size" in summary
    assert "n_centroids" in summary
    assert "coverage" in summary
    assert "best_reward" in summary
    assert "mean_reward" in summary


def test_to_summary_values_after_insert() -> None:
    archive = QDArchive(n_centroids=100, seed=0)
    archive.insert(bd=_make_bd(reward=0.75), snapshot=_make_snapshot("vs"))
    summary = archive.to_summary()
    assert summary["size"] == 1
    assert summary["n_centroids"] == 100
    assert summary["coverage"] == pytest.approx(0.01)
    assert summary["best_reward"] == pytest.approx(0.75)
    assert summary["mean_reward"] == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Persistence: save / load
# ---------------------------------------------------------------------------


class TestQDArchivePersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        archive = QDArchive(n_centroids=50, seed=42)
        archive.insert(_make_bd(reward=0.8), _make_snapshot("evo-1"))
        archive.insert(
            _make_bd(token_cost=200_000, reward=0.4),
            _make_snapshot("evo-2"),
        )

        save_path = tmp_path / "archive.json"
        archive.save(save_path)
        assert save_path.exists()

        loaded = QDArchive.load(save_path)
        assert loaded.size == archive.size

    def test_load_nonexistent_returns_fresh(self, tmp_path):
        loaded = QDArchive.load(tmp_path / "missing.json")
        assert loaded.size == 0


# ---------------------------------------------------------------------------
# Query methods: top_k, frontier, coverage_report, get_entry_by_version
# ---------------------------------------------------------------------------


class TestQDArchiveQueries:
    def test_top_k_returns_sorted(self):
        archive = QDArchive(n_centroids=200, seed=42)
        # Insert 3 entries spread across BD space to guarantee different cells.
        archive.insert(_make_bd(token_cost=0.0, reward=0.5), _make_snapshot("v_mid"))
        archive.insert(_make_bd(token_cost=250_000.0, reward=0.9), _make_snapshot("v_high"))
        archive.insert(_make_bd(token_cost=500_000.0, reward=0.2), _make_snapshot("v_low"))

        result = archive.top_k(2)
        assert len(result) == 2
        assert result[0].bd.reward >= result[1].bd.reward
        assert result[0].bd.reward == pytest.approx(0.9)
        assert result[1].bd.reward == pytest.approx(0.5)

    def test_top_k_empty(self):
        archive = QDArchive(n_centroids=50, seed=0)
        assert archive.top_k(5) == []

    def test_top_k_k_larger_than_archive(self):
        archive = QDArchive(n_centroids=50, seed=0)
        archive.insert(_make_bd(reward=0.7), _make_snapshot("v1"))
        result = archive.top_k(10)
        assert len(result) == 1

    def test_frontier_returns_diverse_high_performers(self):
        archive = QDArchive(n_centroids=200, seed=42)
        # Insert 10 entries spread across BD space.
        for i in range(10):
            tc = float(i) * 50_000.0
            reward = 0.1 + float(i) * 0.08
            archive.insert(
                _make_bd(token_cost=tc, reward=reward),
                _make_snapshot(f"v{i}"),
            )

        result = archive.frontier(3)
        assert len(result) == 3
        # All returned entries should be valid ArchiveEntry objects.
        for entry in result:
            assert entry.snapshot is not None
            assert entry.bd is not None

    def test_frontier_empty(self):
        archive = QDArchive(n_centroids=50, seed=0)
        assert archive.frontier(3) == []

    def test_frontier_k_larger_than_archive(self):
        archive = QDArchive(n_centroids=50, seed=0)
        archive.insert(_make_bd(reward=0.7), _make_snapshot("v1"))
        result = archive.frontier(10)
        assert len(result) == 1

    def test_coverage_report(self):
        archive = QDArchive(n_centroids=100, seed=0)
        archive.insert(_make_bd(reward=0.8), _make_snapshot("v1"))
        report = archive.coverage_report()
        assert report["occupied"] == 1
        assert report["total_centroids"] == 100
        assert report["empty"] == 99
        assert report["coverage"] == pytest.approx(0.01)

    def test_coverage_report_empty_archive(self):
        archive = QDArchive(n_centroids=50, seed=0)
        report = archive.coverage_report()
        assert report["occupied"] == 0
        assert report["empty"] == 50
        assert report["total_centroids"] == 50
        assert report["coverage"] == pytest.approx(0.0)

    def test_get_entry_by_version(self):
        archive = QDArchive(n_centroids=50, seed=0)
        snapshot = _make_snapshot("evo-abc-123")
        archive.insert(_make_bd(reward=0.6), snapshot)
        result = archive.get_entry_by_version("evo-abc-123")
        assert result is not None
        assert result.snapshot.workspace_version == "evo-abc-123"

    def test_get_entry_by_version_missing(self):
        archive = QDArchive(n_centroids=50, seed=0)
        archive.insert(_make_bd(reward=0.6), _make_snapshot("existing"))
        result = archive.get_entry_by_version("nonexistent-version")
        assert result is None
