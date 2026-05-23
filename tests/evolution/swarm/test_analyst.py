# ABOUTME: Tests for the analyst agent — consolidation report production.
# ABOUTME: Verifies pattern extraction, recommendations, and counterintuitive findings.

from __future__ import annotations

from aec_bench.contracts.evolution import (
    BehaviourDescriptor,
    LineageNarrative,
    LineageRecord,
    WorkspaceSnapshot,
)
from aec_bench.evolution.archive import QDArchive
from aec_bench.evolution.graveyard import GraveyardEntry
from aec_bench.evolution.swarm.analyst import produce_consolidation_report
from aec_bench.evolution.swarm.lineage import LineageTracker
from aec_bench.evolution.swarm.notes import NoteStore
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard

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


def _make_snapshot(version: str = "v1") -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        system_prompt="Test prompt.",
        skills=[],
        workspace_version=version,
    )


def _make_record(version: str, agent: str = "agent-0", **overrides) -> LineageRecord:
    defaults = dict(
        entry_version=version,
        parent_version=None,
        source_agent_id=agent,
        cross_agent=False,
        mutation_type="evolution_cycle",
        surprise=False,
        timestamp="2026-04-08T10:00:00Z",
    )
    defaults.update(overrides)
    return LineageRecord(**defaults)


# ---------------------------------------------------------------------------
# Basic report
# ---------------------------------------------------------------------------


def test_empty_state_produces_report() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = SharedGraveyard()
    lineage = LineageTracker()
    notes = NoteStore()

    report = produce_consolidation_report(archive, graveyard, lineage, notes, total_evals=0)

    assert report.report_id.startswith("consolidation-")
    assert report.archive_coverage_pct == 0.0
    assert report.total_evals == 0
    assert report.lineage_insights == "No lineage data yet."


def test_report_reflects_coverage() -> None:
    archive = QDArchive(n_centroids=100, seed=0)
    archive.insert(bd=_make_bd(reward=0.8), snapshot=_make_snapshot("v1"))
    graveyard = SharedGraveyard()
    lineage = LineageTracker()
    notes = NoteStore()

    report = produce_consolidation_report(archive, graveyard, lineage, notes, total_evals=5)

    assert report.archive_coverage_pct == 1.0  # 1/100 = 1%
    assert report.total_evals == 5


# ---------------------------------------------------------------------------
# Cross-agent patterns
# ---------------------------------------------------------------------------


def test_cross_agent_patterns_detected() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = SharedGraveyard()
    lineage = LineageTracker()
    notes = NoteStore()

    lineage.record(_make_record("v1", agent="agent-0"))
    lineage.record(_make_record("v2", agent="agent-0"))
    lineage.record(_make_record("v3", agent="agent-1"))

    report = produce_consolidation_report(archive, graveyard, lineage, notes, total_evals=3)

    assert len(report.cross_agent_patterns) > 0
    assert any("agent-0" in p for p in report.cross_agent_patterns)


def test_cross_agent_transfer_noted() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = SharedGraveyard()
    lineage = LineageTracker()
    notes = NoteStore()

    lineage.record(_make_record("v1", agent="agent-0"))
    lineage.record(_make_record("v2", agent="agent-1", cross_agent=True, cross_agent_source="agent-0"))

    report = produce_consolidation_report(archive, graveyard, lineage, notes, total_evals=2)

    assert any("cross-agent" in p.lower() for p in report.cross_agent_patterns)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def test_low_coverage_recommendation() -> None:
    archive = QDArchive(n_centroids=200, seed=0)  # 0% coverage
    graveyard = SharedGraveyard()
    lineage = LineageTracker()
    notes = NoteStore()

    report = produce_consolidation_report(archive, graveyard, lineage, notes, total_evals=10)

    assert any("coverage" in r.lower() for r in report.strategy_recommendations)


def test_repeated_failure_recommendation() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = SharedGraveyard()
    lineage = LineageTracker()
    notes = NoteStore()

    bd = _make_bd()
    for i in range(5):
        graveyard.insert(
            GraveyardEntry(
                cycle=i,
                strategy="add_skill",
                mutation_description=f"Added skill {i}",
                score_before=0.5,
                score_after=0.3,
                workspace_version=f"v{i}",
                failure_reason="Score dropped",
            ),
            bd=bd,
            agent_id="agent-0",
        )

    report = produce_consolidation_report(archive, graveyard, lineage, notes, total_evals=5)

    assert any("add_skill" in r for r in report.strategy_recommendations)


# ---------------------------------------------------------------------------
# Counterintuitive findings
# ---------------------------------------------------------------------------


def test_surprise_findings_extracted() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = SharedGraveyard()
    lineage = LineageTracker()
    notes = NoteStore()

    lineage.record(_make_record("v1", agent="agent-0", surprise=True))
    lineage.attach_narrative(
        LineageNarrative(
            entry_version="v1",
            agent_reasoning="Tried unusual approach.",
            surprise_explanation="Token efficiency improved despite adding more verification.",
        )
    )

    report = produce_consolidation_report(archive, graveyard, lineage, notes, total_evals=1)

    assert len(report.counterintuitive_findings) == 1
    assert "Token efficiency" in report.counterintuitive_findings[0]


# ---------------------------------------------------------------------------
# Lineage insights
# ---------------------------------------------------------------------------


def test_lineage_insights_summary() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = SharedGraveyard()
    lineage = LineageTracker()
    notes = NoteStore()

    lineage.record(_make_record("v1", agent="agent-0"))
    lineage.record(_make_record("v2", agent="agent-1"))
    lineage.attach_narrative(
        LineageNarrative(
            entry_version="v1",
            agent_reasoning="First attempt.",
        )
    )

    report = produce_consolidation_report(archive, graveyard, lineage, notes, total_evals=2)

    assert "2 archive entries" in report.lineage_insights
    assert "2 agents" in report.lineage_insights
    assert "1 entries have reasoning narratives" in report.lineage_insights
