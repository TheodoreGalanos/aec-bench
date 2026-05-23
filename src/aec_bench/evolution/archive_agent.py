# ABOUTME: Archive-explorer agent that browses, compares, and selects parent cells.
# ABOUTME: Structured pipeline: bandit shortlist → agent exploration → parent selection.

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from aec_bench.evolution.archive import QDArchive
from aec_bench.evolution.graveyard import MutationGraveyard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Selection result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectionResult:
    """The parent cell chosen by the archive-explorer agent."""

    parent_version: str
    inspiration_versions: list[str]
    strategy: str
    reasoning: str


# ---------------------------------------------------------------------------
# Archive browser tools (closures)
# ---------------------------------------------------------------------------


def build_archive_tools(
    archive: QDArchive,
    graveyard: MutationGraveyard,
) -> dict[str, Callable[..., str]]:
    """Build archive-exploration tool functions as closures over archive and graveyard.

    Returns a dict mapping tool name to callable. Each tool returns a formatted
    string suitable for consumption by the selection agent.
    """

    def browse_archive(sort_by: str = "reward", limit: int = 5) -> str:
        """Return a markdown table of top archive entries sorted by a BD field.

        sort_by can be: reward, token_cost, verification_depth, tool_density,
        exploration_ratio, deliberation_ratio, or frontier (diverse selection).
        """
        if sort_by == "frontier":
            entries = archive.frontier(k=limit)
        else:
            candidates = archive.top_k(k=limit * 2)
            valid_fields = {
                "reward",
                "token_cost",
                "verification_depth",
                "tool_density",
                "exploration_ratio",
                "deliberation_ratio",
            }
            if sort_by in valid_fields:
                candidates.sort(key=lambda e: getattr(e.bd, sort_by), reverse=True)
            entries = candidates[:limit]

        if not entries:
            return "Archive is empty — no entries to browse."

        lines = [
            "| Version | Reward | Tokens | Verif | Tool | Explore | Discipline |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for e in entries:
            lines.append(
                f"| {e.snapshot.workspace_version}"
                f" | {e.bd.reward:.3f}"
                f" | {e.bd.token_cost:.0f}"
                f" | {e.bd.verification_depth:.3f}"
                f" | {e.bd.tool_density:.3f}"
                f" | {e.bd.exploration_ratio:.3f}"
                f" | {e.discipline or '—'} |"
            )
        return "\n".join(lines)

    def compare_cells(version_a: str, version_b: str) -> str:
        """Compare two archive entries: BD deltas, prompt previews, and skill diff."""
        entry_a = archive.get_entry_by_version(version_a)
        entry_b = archive.get_entry_by_version(version_b)

        missing = []
        if entry_a is None:
            missing.append(version_a)
        if entry_b is None:
            missing.append(version_b)
        if missing:
            return f"Version(s) not found in archive: {', '.join(missing)}"

        bd_a = entry_a.bd
        bd_b = entry_b.bd

        lines = [f"## Comparison: {version_a} vs {version_b}", ""]

        # BD comparison table
        lines += [
            "### Behaviour Descriptors",
            "| Dimension | A | B | Delta |",
            "| --- | --- | --- | --- |",
        ]
        dimensions = [
            ("reward", bd_a.reward, bd_b.reward),
            ("token_cost", bd_a.token_cost, bd_b.token_cost),
            ("verification_depth", bd_a.verification_depth, bd_b.verification_depth),
            ("tool_density", bd_a.tool_density, bd_b.tool_density),
            ("exploration_ratio", bd_a.exploration_ratio, bd_b.exploration_ratio),
            ("deliberation_ratio", bd_a.deliberation_ratio, bd_b.deliberation_ratio),
        ]
        for dim, val_a, val_b in dimensions:
            delta = val_b - val_a
            lines.append(f"| {dim} | {val_a:.3f} | {val_b:.3f} | {delta:+.3f} |")

        # Prompt previews
        prompt_a = entry_a.snapshot.system_prompt[:500]
        prompt_b = entry_b.snapshot.system_prompt[:500]
        lines += [
            "",
            f"### Prompt A ({version_a}, first 500 chars)",
            prompt_a,
            "",
            f"### Prompt B ({version_b}, first 500 chars)",
            prompt_b,
        ]

        # Skill diff
        skills_a = {s.name for s in entry_a.snapshot.skills}
        skills_b = {s.name for s in entry_b.snapshot.skills}
        only_a = sorted(skills_a - skills_b)
        only_b = sorted(skills_b - skills_a)
        common = sorted(skills_a & skills_b)

        lines += [
            "",
            "### Skill Diff",
            f"Only in A: {', '.join(only_a) or 'none'}",
            f"Only in B: {', '.join(only_b) or 'none'}",
            f"Common: {', '.join(common) or 'none'}",
        ]

        return "\n".join(lines)

    def inspect_cell(version: str) -> str:
        """Return full detail for an archive entry: all BD values, tasks, prompt, skills."""
        entry = archive.get_entry_by_version(version)
        if entry is None:
            return f"Version not found in archive: {version!r}"

        bd = entry.bd
        snapshot = entry.snapshot

        lines = [f"## Cell: {version}", ""]
        lines += [
            "### Behaviour Descriptors",
            f"- reward: {bd.reward:.4f}",
            f"- token_cost: {bd.token_cost:.1f}",
            f"- verification_depth: {bd.verification_depth:.4f}",
            f"- tool_density: {bd.tool_density:.4f}",
            f"- exploration_ratio: {bd.exploration_ratio:.4f}",
            f"- deliberation_ratio: {bd.deliberation_ratio:.4f}",
        ]

        lines += [
            "",
            "### Provenance",
            f"- discipline: {entry.discipline or '—'}",
            f"- run_id: {entry.run_id or '—'}",
            f"- task_ids: {', '.join(entry.task_ids) or 'none'}",
        ]

        prompt_preview = snapshot.system_prompt[:1000]
        lines += [
            "",
            "### System Prompt (first 1000 chars)",
            prompt_preview,
        ]

        if snapshot.skills:
            lines += ["", "### Skills"]
            for skill in snapshot.skills:
                body_preview = skill.body[:150]
                lines.append(f"- **{skill.name}**: {skill.description}")
                lines.append(f"  `{body_preview}`")
        else:
            lines += ["", "### Skills", "No skills in this workspace."]

        return "\n".join(lines)

    def coverage_gaps() -> str:
        """Return archive coverage statistics: occupied cells, empty cells, coverage ratio."""
        report = archive.coverage_report()
        lines = [
            "## Archive Coverage",
            f"- Total centroids: {report['total_centroids']}",
            f"- Occupied: {report['occupied']}",
            f"- Empty: {report['empty']}",
            f"- Coverage: {report['coverage']:.1%}",
        ]
        if report["occupied"] == 0:
            lines.append("\nArchive is empty — no cells occupied yet.")
        elif report["coverage"] < 0.1:
            lines.append("\nLow coverage — wide unexplored regions remain.")
        return "\n".join(lines)

    def read_graveyard(limit: int = 5) -> str:
        """Return recent failed mutations from the graveyard."""
        entries = graveyard.browse(limit=limit)
        if not entries:
            return "Graveyard is empty — no failed mutations recorded."

        lines = ["## Graveyard (recent failed mutations)", ""]
        for e in entries:
            score_change = e.score_after - e.score_before
            lines += [
                f"### Cycle {e.cycle} — {e.strategy}",
                f"- Description: {e.mutation_description}",
                f"- Score change: {e.score_before:.3f} → {e.score_after:.3f} ({score_change:+.3f})",
                f"- Failure reason: {e.failure_reason}",
                f"- Workspace version: {e.workspace_version}",
                "",
            ]
        return "\n".join(lines)

    return {
        "browse_archive": browse_archive,
        "compare_cells": compare_cells,
        "inspect_cell": inspect_cell,
        "coverage_gaps": coverage_gaps,
        "read_graveyard": read_graveyard,
    }


# ---------------------------------------------------------------------------
# Selection output parser
# ---------------------------------------------------------------------------


def _parse_selection(text: str, shortlist: list[str]) -> SelectionResult:
    """Parse the agent's free-text response for SELECTED/INSPIRATION/STRATEGY/REASON tags.

    Falls back to the first shortlist entry with 'conservative' strategy when the
    expected tags are missing or the selected version is not in the shortlist.
    """
    lines = text.splitlines()

    selected: str | None = None
    inspiration: list[str] = []
    strategy = "conservative"
    reason = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("SELECTED:"):
            selected = stripped[len("SELECTED:") :].strip()
        elif stripped.startswith("INSPIRATION:"):
            raw = stripped[len("INSPIRATION:") :].strip()
            inspiration = [v.strip() for v in raw.split(",") if v.strip()]
        elif stripped.startswith("STRATEGY:"):
            strategy = stripped[len("STRATEGY:") :].strip()
        elif stripped.startswith("REASON:"):
            reason = stripped[len("REASON:") :].strip()

    # Validate: selected must be non-empty and present in the shortlist
    if not selected or selected not in shortlist:
        fallback = shortlist[0] if shortlist else ""
        logger.warning(
            "Archive agent did not produce a valid SELECTED tag — falling back to %r",
            fallback,
        )
        return SelectionResult(
            parent_version=fallback,
            inspiration_versions=[],
            strategy="conservative",
            reasoning="Fallback: agent output did not contain a valid SELECTED tag.",
        )

    return SelectionResult(
        parent_version=selected,
        inspiration_versions=inspiration,
        strategy=strategy,
        reasoning=reason,
    )


# ---------------------------------------------------------------------------
# Selection pipeline
# ---------------------------------------------------------------------------

_SELECTION_SYSTEM = """\
You are an archive-explorer agent choosing the best parent cell for the next \
evolution mutation. You have tools to browse, compare, and inspect cells in \
the quality-diversity archive and to read the graveyard of failed mutations.

Your goal is to select a parent workspace that maximises the chance of \
producing a better offspring. Consider:
- High-reward cells as safe conservative parents
- Frontier (diverse) cells for exploratory mutations
- Cells whose skills or prompts differ from the current best (crossover)
- Graveyard entries with recoverable ideas (graveyard_rescue)

Use the tools as needed, then end your response with EXACTLY:

SELECTED: <version>
INSPIRATION: <v1>, <v2>  (optional additional versions that informed your choice)
STRATEGY: conservative | exploratory | crossover | graveyard_rescue
REASON: <one sentence explaining your choice>
"""


def run_archive_selection(
    model_name: str,
    archive: QDArchive,
    graveyard: MutationGraveyard,
    shortlist: list[str],
    current_score: float,
) -> SelectionResult:
    """Run the archive-explorer agent to select a parent cell for mutation.

    Builds archive tools, runs a PydanticAI agent with a 10-request budget,
    parses the structured tail of the response, and falls back gracefully.
    """
    from pydantic_ai import Agent
    from pydantic_ai.tools import Tool
    from pydantic_ai.usage import UsageLimitExceeded, UsageLimits

    from aec_bench.evolution.structured_evolver import _build_pydantic_model

    if not shortlist:
        logger.warning("Empty shortlist passed to run_archive_selection — returning empty result")
        return SelectionResult(
            parent_version="",
            inspiration_versions=[],
            strategy="conservative",
            reasoning="No shortlist provided.",
        )

    tools_dict = build_archive_tools(archive, graveyard)
    tools = [Tool(fn, name=name) for name, fn in tools_dict.items()]

    model = _build_pydantic_model(model_name)

    agent: Agent[None, str] = Agent(
        model,
        system_prompt=_SELECTION_SYSTEM,
        output_type=str,
        tools=tools,
    )

    shortlist_text = "\n".join(f"- {v}" for v in shortlist)
    brief = (
        f"Current score: {current_score:.4f}\n\n"
        f"Shortlisted candidate versions:\n{shortlist_text}\n\n"
        "Browse the archive, compare candidates, and select the best parent."
    )

    raw_output = ""
    try:
        result = agent.run_sync(brief, usage_limits=UsageLimits(request_limit=10))
        raw_output = result.output
    except UsageLimitExceeded:
        logger.warning("Archive selection agent hit request limit — using fallback")
    except Exception:
        logger.exception("Archive selection agent failed — using fallback")

    return _parse_selection(raw_output, shortlist)
