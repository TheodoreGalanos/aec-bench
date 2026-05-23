# ABOUTME: Analyst agent that synthesises swarm state into consolidation reports.
# ABOUTME: Reads archive, graveyard, lineage, and notes to extract cross-agent patterns.

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime

from aec_bench.contracts.evolution import ConsolidationReport
from aec_bench.evolution.archive import QDArchive
from aec_bench.evolution.swarm.lineage import LineageTracker
from aec_bench.evolution.swarm.notes import NoteStore
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard


def produce_consolidation_report(
    archive: QDArchive,
    graveyard: SharedGraveyard,
    lineage: LineageTracker,
    notes: NoteStore,
    total_evals: int,
) -> ConsolidationReport:
    """Analyse swarm state and produce a structured consolidation report.

    Extracts patterns from the archive, graveyard, lineage, and notes
    without making LLM calls — pure data analysis. An LLM-powered
    version can be added later for richer insights.
    """
    report_id = f"consolidation-{uuid.uuid4().hex[:8]}"
    coverage = archive.coverage_report()
    coverage_pct = coverage.get("coverage", 0.0) * 100

    cross_agent_patterns = _extract_cross_agent_patterns(lineage)
    strategy_recommendations = _extract_recommendations(archive, graveyard)
    counterintuitive = _extract_counterintuitive(lineage)
    lineage_insights = _summarise_lineage(lineage)

    return ConsolidationReport(
        report_id=report_id,
        timestamp=datetime.now(tz=UTC).isoformat(),
        archive_coverage_pct=coverage_pct,
        total_evals=total_evals,
        cross_agent_patterns=cross_agent_patterns,
        strategy_recommendations=strategy_recommendations,
        counterintuitive_findings=counterintuitive,
        lineage_insights=lineage_insights,
    )


def _extract_cross_agent_patterns(lineage: LineageTracker) -> list[str]:
    """Identify patterns in cross-agent collaboration."""
    patterns: list[str] = []
    records = lineage.all_records()
    if not records:
        return patterns

    # Count contributions per agent
    agent_counts: Counter[str] = Counter()
    for r in records:
        agent_counts[r.source_agent_id] += 1

    if len(agent_counts) > 1:
        top_agent = agent_counts.most_common(1)[0]
        patterns.append(f"Agent {top_agent[0]} has contributed the most archive entries ({top_agent[1]}).")

    # Count cross-agent transfers
    cross = lineage.cross_agent_records()
    if cross:
        patterns.append(f"{len(cross)} entries built on another agent's work (cross-agent transfer).")

    return patterns


def _extract_recommendations(
    archive: QDArchive,
    graveyard: SharedGraveyard,
) -> list[str]:
    """Generate strategy recommendations based on archive and graveyard state."""
    recommendations: list[str] = []
    report = archive.coverage_report()
    coverage = report.get("coverage", 0.0)

    if coverage < 0.1:
        recommendations.append(
            "Archive coverage is very low (<10%). Agents should prioritise exploring "
            "diverse BD regions rather than optimising within known regions."
        )
    elif coverage < 0.3:
        recommendations.append(
            "Archive coverage is moderate. Balance exploration of empty regions with improvement of existing entries."
        )

    # Check graveyard for repeated failure patterns
    failures = graveyard.browse_all(limit=20)
    if len(failures) >= 5:
        strategy_counts: Counter[str] = Counter()
        for f in failures:
            strategy_counts[f.strategy] += 1
        worst = strategy_counts.most_common(1)
        if worst and worst[0][1] >= 3:
            recommendations.append(
                f"Mutation strategy '{worst[0][0]}' has failed {worst[0][1]} times. "
                f"Consider avoiding it or combining with a different approach."
            )

    return recommendations


def _extract_counterintuitive(lineage: LineageTracker) -> list[str]:
    """Find entries flagged as surprising in the lineage."""
    findings: list[str] = []
    for r in lineage.all_records():
        if r.surprise:
            narrative = lineage.get_narrative(r.entry_version)
            explanation = ""
            if narrative and narrative.surprise_explanation:
                explanation = f" — {narrative.surprise_explanation}"
            findings.append(f"Entry {r.entry_version} by {r.source_agent_id} was a surprise{explanation}.")
    return findings


def _summarise_lineage(lineage: LineageTracker) -> str:
    """Produce a one-paragraph summary of lineage state."""
    records = lineage.all_records()
    if not records:
        return "No lineage data yet."

    agents = {r.source_agent_id for r in records}
    cross_count = len(lineage.cross_agent_records())
    surprise_count = sum(1 for r in records if r.surprise)
    narratives = lineage.all_narratives()

    parts = [
        f"{len(records)} archive entries across {len(agents)} agents.",
    ]
    if cross_count:
        parts.append(f"{cross_count} cross-agent transfers.")
    if surprise_count:
        parts.append(f"{surprise_count} surprise findings.")
    if narratives:
        parts.append(f"{len(narratives)} entries have reasoning narratives.")

    return " ".join(parts)
