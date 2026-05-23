# ABOUTME: Builds a markdown context message summarising archive state for agent conversations.
# ABOUTME: Injected into swarm agent prompts so each agent sees coverage and failures.

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from aec_bench.contracts.evolution import BehaviourDescriptor, ConsolidationReport
from aec_bench.evolution.swarm.notes import NoteStore
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard

if TYPE_CHECKING:
    from aec_bench.contracts.evolution import WorkspaceSnapshot


@runtime_checkable
class _ArchiveEntryLike(Protocol):
    """Structural type for archive entries — avoids hard dependency on pyribs."""

    @property
    def snapshot(self) -> WorkspaceSnapshot: ...

    @property
    def bd(self) -> BehaviourDescriptor: ...

    @property
    def run_id(self) -> str: ...

    @property
    def discipline(self) -> str: ...


@runtime_checkable
class _ArchiveLike(Protocol):
    """Structural type for the QD archive — avoids hard dependency on pyribs/numpy."""

    def coverage_report(self) -> dict: ...

    def top_k(self, k: int = 5) -> list: ...

    def to_summary(self) -> dict: ...


def _format_coverage_section(archive: _ArchiveLike, generation: int) -> str:
    """Render the header and coverage line."""
    report = archive.coverage_report()
    occupied = report.get("occupied", 0)
    total = report.get("total_centroids", 0)
    coverage_pct = report.get("coverage", 0.0) * 100

    lines = [
        f"## Current Archive State (Generation {generation})",
        "",
        f"Coverage: {occupied}/{total} cells occupied ({coverage_pct:.1f}%)",
        "",
    ]
    return "\n".join(lines)


def _format_top_performers(archive: _ArchiveLike, k: int = 5) -> str:
    """Render the top-k archive entries."""
    entries = archive.top_k(k)
    lines = ["### Top Performers", ""]

    if not entries:
        lines.append("No entries in archive yet.")
        lines.append("")
        return "\n".join(lines)

    for i, entry in enumerate(entries, 1):
        version = entry.snapshot.workspace_version
        reward = entry.bd.reward
        discipline = entry.discipline or "—"
        run_id = entry.run_id or "—"
        lines.append(f"{i}. **{version}** — reward: {reward:.3f}, discipline: {discipline}, run: {run_id}")

    lines.append("")
    return "\n".join(lines)


def _format_agent_performance(
    recent_scores: Sequence[float],
    best_score: float,
) -> str:
    """Render the agent's recent performance section."""
    lines = ["### Your Recent Performance", ""]

    if not recent_scores:
        lines.append("No evaluations yet.")
    else:
        display_scores = list(recent_scores[-5:])
        formatted = ", ".join(f"{s:.2f}" for s in display_scores)
        lines.append(f"Recent scores: {formatted}")
        lines.append(f"Best score: {best_score:.2f}")

    lines.append("")
    return "\n".join(lines)


def _format_graveyard_failures(
    graveyard: SharedGraveyard,
    agent_bd_focus: BehaviourDescriptor | None,
    limit: int = 5,
) -> str:
    """Render relevant failures from the shared graveyard."""
    if agent_bd_focus is not None:
        entries = graveyard.browse_for_region(agent_bd_focus, k=limit)
    else:
        entries = graveyard.browse_all(limit=limit)

    lines = ["### Relevant Failures", ""]

    if not entries:
        lines.append("No recorded failures.")
    else:
        for entry in entries:
            lines.append(
                f"- Cycle {entry.cycle}: {entry.mutation_description} "
                f"({entry.score_before:.2f} -> {entry.score_after:.2f}) — "
                f"{entry.failure_reason}"
            )

    lines.append("")
    return "\n".join(lines)


def _format_consolidation_section(report: ConsolidationReport) -> str:
    """Render the latest consolidation report from the analyst."""
    lines = [
        "### Latest Consolidation",
        "",
        f"Archive coverage: {report.archive_coverage_pct:.0f}% after {report.total_evals} evals.",
        "",
    ]

    if report.cross_agent_patterns:
        lines.append("**Cross-Agent Patterns:**")
        for p in report.cross_agent_patterns:
            lines.append(f"- {p}")
        lines.append("")

    if report.strategy_recommendations:
        lines.append("**Recommendations:**")
        for r in report.strategy_recommendations:
            lines.append(f"- {r}")
        lines.append("")

    if report.counterintuitive_findings:
        lines.append("**Counterintuitive Findings:**")
        for f in report.counterintuitive_findings:
            lines.append(f"- {f}")
        lines.append("")

    if report.lineage_insights:
        lines.append(f"**Lineage:** {report.lineage_insights}")
        lines.append("")

    return "\n".join(lines)


def _format_nudge_section(nudge: str) -> str:
    """Render a nudge hint for agents in nudged specialisation mode."""
    lines = [
        "### Exploration Focus",
        "",
        nudge,
        "",
        "This is a suggestion, not a constraint. You are free to explore other regions "
        "if you find promising opportunities, but consider this direction as your starting bias.",
        "",
    ]
    return "\n".join(lines)


def _format_notes_section(
    notes: NoteStore,
    agent_bd_focus: BehaviourDescriptor | None,
    agent_id: str,
    limit: int = 5,
) -> str:
    """Render shared notes from other agents relevant to the current region."""
    if agent_bd_focus is not None:
        entries = notes.browse_for_region(agent_bd_focus, k=limit)
    else:
        entries = notes.browse_all(limit=limit)

    # Filter out the agent's own notes — they already know what they wrote
    entries = [n for n in entries if n.agent_id != agent_id]

    lines = ["### Shared Notes", ""]

    if not entries:
        lines.append("No notes from other agents yet.")
    else:
        for note in entries:
            tags_str = f" [{', '.join(note.tags)}]" if note.tags else ""
            lines.append(f"- **{note.title}** ({note.agent_id}){tags_str}: {note.content}")

    lines.append("")
    return "\n".join(lines)


def _format_pivot_section(consecutive_non_improving: int) -> str:
    """Render a pivot instruction when the agent is stagnating."""
    lines = [
        "### PIVOT — You Are Stuck",
        "",
        f"You have had {consecutive_non_improving} consecutive evaluations without improvement.",
        "Your current approach is not working. You MUST try something fundamentally different:",
        "",
        "- Study what other agents achieved in different archive regions",
        "- Try a mutation strategy you haven't used before",
        "- Target a completely different BD region (token cost, verification depth, etc.)",
        "- Consider combining approaches from multiple archive entries",
        "",
        "Do NOT continue with small variations of your current approach.",
        "",
    ]
    return "\n".join(lines)


def build_archive_context(
    archive: _ArchiveLike,
    graveyard: SharedGraveyard,
    agent_id: str,
    agent_bd_focus: BehaviourDescriptor | None,
    generation: int,
    agent_recent_scores: Sequence[float],
    agent_best_score: float,
    pivoting: bool = False,
    consecutive_non_improving: int = 0,
    notes: NoteStore | None = None,
    nudge: str | None = None,
    consolidation_report: ConsolidationReport | None = None,
) -> str:
    """Build a markdown message summarising archive state for injection into agent conversations.

    Sections:
    1. Current Archive State — header with generation and coverage line.
    2. Exploration Focus (conditional) — nudge hint for specialised agents.
    3. PIVOT (conditional) — injected when agent is stagnating.
    4. Latest Consolidation (conditional) — analyst insights.
    5. Top Performers — top 5 entries sorted by reward.
    6. Your Recent Performance — last 5 scores and best.
    7. Shared Notes (conditional) — notes from other agents, region-filtered.
    8. Relevant Failures — region-filtered if agent has BD focus, otherwise all.
    """
    sections = [
        _format_coverage_section(archive, generation),
    ]

    if nudge is not None:
        sections.append(_format_nudge_section(nudge))

    if pivoting:
        sections.append(_format_pivot_section(consecutive_non_improving))

    if consolidation_report is not None:
        sections.append(_format_consolidation_section(consolidation_report))

    sections.append(_format_top_performers(archive))
    sections.append(_format_agent_performance(agent_recent_scores, agent_best_score))

    if notes is not None and notes.size > 0:
        sections.append(_format_notes_section(notes, agent_bd_focus, agent_id))

    sections.append(_format_graveyard_failures(graveyard, agent_bd_focus))

    return "\n".join(sections)
