# ABOUTME: Archive-explorer agent that browses, compares, and selects parent cells.
# ABOUTME: Structured pipeline: bandit shortlist → agent exploration → parent selection.

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from aec_bench.contracts.evolution import MutationStrategy
from aec_bench.evolution.archive import ArchiveView
from aec_bench.evolution.core import SelectionPlan
from aec_bench.evolution.graveyard import MutationGraveyard

logger = logging.getLogger(__name__)


_STRATEGY_GOALS: dict[MutationStrategy, str] = {
    MutationStrategy.CONSERVATIVE: "Apply a conservative mutation to the selected parent.",
    MutationStrategy.EXPLORATORY: "Explore a less-covered archive region from the selected parent.",
    MutationStrategy.CROSSOVER: "Combine material from the selected parent and inspirations.",
    MutationStrategy.GRAVEYARD_RESCUE: "Recover a useful idea from a rejected graveyard candidate.",
}


# ---------------------------------------------------------------------------
# Archive browser tools (closures)
# ---------------------------------------------------------------------------


def build_archive_tools(
    archive: ArchiveView,
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
            candidates = list(archive.top_k(k=limit * 2))
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
            entries = tuple(candidates[:limit])

        if not entries:
            return "Archive is empty — no entries to browse."

        lines = [
            "| Candidate | Reward | Tokens | Verif | Tool | Explore | Discipline |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for e in entries:
            lines.append(
                f"| {e.snapshot.candidate_id}"
                f" | {e.bd.reward:.3f}"
                f" | {e.bd.token_cost:.0f}"
                f" | {e.bd.verification_depth:.3f}"
                f" | {e.bd.tool_density:.3f}"
                f" | {e.bd.exploration_ratio:.3f}"
                f" | {e.discipline or '—'} |"
            )
        return "\n".join(lines)

    def compare_cells(candidate_a: str, candidate_b: str) -> str:
        """Compare two archive entries: BD deltas, prompt previews, and skill diff."""
        entry_a = archive.get_entry_by_candidate_id(candidate_a)
        entry_b = archive.get_entry_by_candidate_id(candidate_b)

        missing = []
        if entry_a is None:
            missing.append(candidate_a)
        if entry_b is None:
            missing.append(candidate_b)
        if missing:
            return f"Candidate(s) not found in archive: {', '.join(missing)}"
        assert entry_a is not None
        assert entry_b is not None

        bd_a = entry_a.bd
        bd_b = entry_b.bd

        lines = [f"## Comparison: {candidate_a} vs {candidate_b}", ""]

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
            f"### Prompt A ({candidate_a}, first 500 chars)",
            prompt_a,
            "",
            f"### Prompt B ({candidate_b}, first 500 chars)",
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

    def inspect_cell(candidate_id: str) -> str:
        """Return full detail for an archive entry: all BD values, tasks, prompt, skills."""
        entry = archive.get_entry_by_candidate_id(candidate_id)
        if entry is None:
            return f"Candidate not found in archive: {candidate_id!r}"

        bd = entry.bd
        snapshot = entry.snapshot

        lines = [f"## Cell: {candidate_id}", ""]
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
                f"- Candidate ID: {e.candidate_id}",
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


def _resolvable_graveyard_candidate_ids(graveyard: MutationGraveyard) -> set[str]:
    """Return graveyard IDs that have exact, identity-matching snapshots."""
    candidate_ids: set[str] = set()
    for entry in graveyard.browse(limit=graveyard.size):
        snapshot = entry.rejected_snapshot
        if snapshot is not None and snapshot.candidate_id == entry.candidate_id:
            candidate_ids.add(snapshot.candidate_id)
    return candidate_ids


def _require_inspiration_limit(inspiration_limit: int) -> None:
    if isinstance(inspiration_limit, bool) or not isinstance(inspiration_limit, int) or inspiration_limit < 0:
        raise ValueError("inspiration_limit must be a non-negative integer")


def _parse_selection(
    text: str,
    shortlist: Sequence[str],
    strategy: MutationStrategy,
    *,
    graveyard: MutationGraveyard | None = None,
    inspiration_limit: int,
) -> SelectionPlan:
    """Parse and validate the archive-agent response under host-owned intent.

    The model may choose only IDs in the bounded shortlist. During graveyard
    rescue, it may also choose an ID with an exact rejected snapshot. Strategy
    remains host-owned and is never read from the model response.
    """
    _require_inspiration_limit(inspiration_limit)
    try:
        selected_strategy = MutationStrategy(strategy)
    except ValueError as exc:
        raise ValueError(f"unsupported selected mutation strategy: {strategy!r}") from exc

    allowed_parent_ids = tuple(shortlist)
    if not allowed_parent_ids:
        raise ValueError("archive selection requires a non-empty candidate shortlist")
    if len(set(allowed_parent_ids)) != len(allowed_parent_ids):
        raise ValueError("candidate shortlist IDs must be unique")
    if any(not isinstance(candidate_id, str) or not candidate_id.strip() for candidate_id in allowed_parent_ids):
        raise ValueError("candidate shortlist IDs must not be blank")

    resolvable_graveyard_ids = (
        _resolvable_graveyard_candidate_ids(graveyard)
        if graveyard is not None and selected_strategy is MutationStrategy.GRAVEYARD_RESCUE
        else set()
    )
    if selected_strategy is MutationStrategy.GRAVEYARD_RESCUE and not resolvable_graveyard_ids:
        raise ValueError("graveyard_rescue requires a resolvable graveyard candidate")

    lines = text.splitlines()

    selected: str | None = None
    inspiration: list[str] = []
    reason: str | None = None
    reported_strategy: str | None = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("SELECTED:"):
            if selected is not None:
                raise ValueError("archive agent returned repeated SELECTED fields")
            selected = stripped[len("SELECTED:") :].strip()
        elif stripped.startswith("INSPIRATION:"):
            if inspiration:
                raise ValueError("archive agent returned repeated INSPIRATION fields")
            raw = stripped[len("INSPIRATION:") :].strip()
            inspiration = [value.strip() for value in raw.split(",") if value.strip()]
        elif stripped.startswith("GOAL:"):
            raise ValueError("archive agent must not return a goal")
        elif stripped.startswith("STRATEGY:"):
            if reported_strategy is not None:
                raise ValueError("archive agent returned repeated STRATEGY fields")
            reported_strategy = stripped[len("STRATEGY:") :].strip()
        elif stripped.startswith("REASON:"):
            if reason is not None:
                raise ValueError("archive agent returned repeated REASON fields")
            reason = stripped[len("REASON:") :].strip()

    if reported_strategy is not None:
        try:
            returned_strategy = MutationStrategy(reported_strategy)
        except ValueError as exc:
            raise ValueError("archive agent must not return a strategy") from exc
        if returned_strategy is not selected_strategy:
            raise ValueError(
                f"archive agent changed the selected strategy from {selected_strategy.value!r} "
                f"to {returned_strategy.value!r}"
            )
        raise ValueError("archive agent must not return a strategy")

    if not selected:
        raise ValueError("archive agent response must contain a SELECTED candidate ID")
    if selected not in allowed_parent_ids:
        raise ValueError(f"archive agent selected parent outside the allowed candidate set: {selected!r}")
    if len(inspiration) > inspiration_limit:
        raise ValueError(f"archive agent returned {len(inspiration)} inspirations; limit is {inspiration_limit}")

    allowed_inspiration_ids = set(allowed_parent_ids) | resolvable_graveyard_ids
    unknown_inspirations = [candidate_id for candidate_id in inspiration if candidate_id not in allowed_inspiration_ids]
    if unknown_inspirations:
        raise ValueError(f"archive agent returned unknown inspiration IDs: {unknown_inspirations!r}")
    if selected in inspiration:
        raise ValueError("selection parent cannot also be an inspiration")
    if len(inspiration) != len(set(inspiration)):
        raise ValueError("selection inspiration candidate IDs must be unique")
    if not reason:
        raise ValueError("archive agent response must contain a non-empty REASON")

    return SelectionPlan(
        parent_candidate_id=selected,
        inspiration_candidate_ids=tuple(inspiration),
        strategy=selected_strategy,
        goal=_STRATEGY_GOALS[selected_strategy],
        reasoning=reason,
    )


# ---------------------------------------------------------------------------
# Selection pipeline
# ---------------------------------------------------------------------------

_SELECTION_SYSTEM = """\
You are an archive-explorer agent choosing the best parent cell for the next \
evolution mutation. You have tools to browse, compare, and inspect cells in \
the quality-diversity archive and to read the graveyard of failed mutations.

The host supplies the mutation strategy intent. You must choose only the \
parent and inspiration IDs under that fixed intent. Do not return a strategy or \
change it.

Your goal is to select a parent workspace that maximises the chance of \
producing a better offspring. Consider:
- High-reward cells as safe conservative parents
- Frontier (diverse) cells for exploratory mutations
- Cells whose skills or prompts differ from the current best (crossover)
- Graveyard entries with recoverable ideas (graveyard_rescue)

Use the tools as needed, then end your response with EXACTLY:

SELECTED: <candidate_id>
INSPIRATION: <candidate_id>, <candidate_id>  (optional additional candidates that informed your choice)
REASON: <one sentence explaining your choice>
"""


def run_archive_selection(
    model_name: str,
    archive: ArchiveView,
    graveyard: MutationGraveyard,
    shortlist: list[str],
    current_score: float,
    strategy: MutationStrategy,
    inspiration_limit: int,
) -> SelectionPlan:
    """Run the archive-explorer agent to select a parent cell for mutation.

    Builds archive tools over the supplied archive and graveyard, runs a
    PydanticAI agent with a 10-request budget, and validates its response.
    """
    from pydantic_ai import Agent, UsageLimitExceeded, UsageLimits
    from pydantic_ai.tools import Tool

    from aec_bench.evolution.model_provider import build_pydantic_model

    _require_inspiration_limit(inspiration_limit)
    if not shortlist:
        raise ValueError("archive selection requires a non-empty candidate shortlist")

    tools_dict = build_archive_tools(archive, graveyard)
    tools: list[Tool[None]] = [Tool[None](fn, name=name) for name, fn in tools_dict.items()]

    model = build_pydantic_model(model_name)

    agent: Agent[None, str] = Agent(
        model,
        system_prompt=_SELECTION_SYSTEM,
        output_type=str,
        tools=tools,
    )

    shortlist_text = "\n".join(f"- {v}" for v in shortlist)
    brief = (
        f"Current score: {current_score:.4f}\n\n"
        f"Host-selected mutation strategy: {MutationStrategy(strategy).value}\n"
        f"Maximum inspirations: {inspiration_limit}\n\n"
        f"Shortlisted candidate IDs:\n{shortlist_text}\n\n"
        "Browse the archive, compare candidates, and select the best parent. "
        "Do not return a strategy; the host owns that decision."
    )

    try:
        result = agent.run_sync(brief, usage_limits=UsageLimits(request_limit=10))
    except UsageLimitExceeded as exc:
        raise RuntimeError("archive selection agent exceeded its request limit") from exc
    except Exception as exc:
        raise RuntimeError("archive selection agent failed") from exc

    if not isinstance(result.output, str):
        raise ValueError("archive selection agent returned a non-text response")
    return _parse_selection(
        result.output,
        shortlist,
        strategy,
        graveyard=graveyard,
        inspiration_limit=inspiration_limit,
    )
