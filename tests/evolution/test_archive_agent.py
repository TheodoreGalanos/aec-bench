# ABOUTME: Tests for the archive-explorer agent tools and selection pipeline.
# ABOUTME: Verifies browse, compare, inspect, and graveyard tools.

from __future__ import annotations

from aec_bench.contracts.evolution import BehaviourDescriptor, SkillEntry, WorkspaceSnapshot
from aec_bench.evolution.archive import QDArchive
from aec_bench.evolution.archive_agent import _parse_selection, build_archive_tools
from aec_bench.evolution.graveyard import GraveyardEntry, MutationGraveyard

# ---------------------------------------------------------------------------
# Helpers for building test fixtures
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


def _make_snapshot(
    version: str = "v1",
    prompt: str = "You are a helpful engineering assistant.",
    skills: list[SkillEntry] | None = None,
) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        system_prompt=prompt,
        skills=skills or [],
        workspace_version=version,
    )


def _make_skill(name: str = "cable-sizing", body: str = "def size_cable(): pass") -> SkillEntry:
    return SkillEntry(
        name=name,
        description=f"Skill for {name}",
        body=body,
    )


def _populated_archive() -> QDArchive:
    """Return an archive with 3 diverse entries in different BD cells."""
    archive = QDArchive(n_centroids=200, seed=42)
    archive.insert(
        _make_bd(token_cost=0.0, reward=0.9),
        _make_snapshot("v_high", "High reward prompt with lots of detail."),
        discipline="electrical",
    )
    archive.insert(
        _make_bd(token_cost=250_000.0, reward=0.5),
        _make_snapshot("v_mid", "Mid reward prompt."),
        discipline="civil",
    )
    archive.insert(
        _make_bd(token_cost=500_000.0, reward=0.2),
        _make_snapshot("v_low", "Low reward prompt."),
        discipline="structural",
    )
    return archive


def _populated_graveyard() -> MutationGraveyard:
    """Return a graveyard with 2 failed mutation entries."""
    graveyard = MutationGraveyard()
    graveyard.insert(
        GraveyardEntry(
            cycle=1,
            strategy="add_skill",
            mutation_description="Added a cable-sizing skill",
            score_before=0.5,
            score_after=0.3,
            workspace_version="v1",
            failure_reason="Score regressed by 0.2",
        )
    )
    graveyard.insert(
        GraveyardEntry(
            cycle=2,
            strategy="modify_prompt",
            mutation_description="Rewrote system prompt",
            score_before=0.6,
            score_after=0.4,
            workspace_version="v2",
            failure_reason="Agent started hallucinating units",
        )
    )
    return graveyard


# ---------------------------------------------------------------------------
# browse_archive
# ---------------------------------------------------------------------------


def test_browse_archive_returns_entries() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["browse_archive"](sort_by="reward", limit=3)

    assert "v_high" in result
    assert "v_mid" in result
    assert "0.900" in result  # reward for v_high
    assert "| Version | Reward |" in result


def test_browse_archive_frontier_sort() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["browse_archive"](sort_by="frontier", limit=3)

    # Should return a table with at least one version
    assert "| Version | Reward |" in result
    assert "v_high" in result


def test_browse_archive_empty_returns_message() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["browse_archive"]()

    assert "empty" in result.lower()


# ---------------------------------------------------------------------------
# compare_cells
# ---------------------------------------------------------------------------


def test_compare_cells_shows_diff() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["compare_cells"]("v_high", "v_mid")

    # Should show prompt text from both entries
    assert "High reward prompt" in result
    assert "Mid reward prompt" in result
    # Should show BD comparison table
    assert "reward" in result
    assert "Delta" in result


def test_compare_cells_not_found() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["compare_cells"]("v_missing", "v_high")

    assert "not found" in result.lower()
    assert "v_missing" in result


def test_compare_cells_shows_skill_diff() -> None:
    archive = QDArchive(n_centroids=200, seed=42)
    skill_a = _make_skill("cable-sizing", "def size(): pass")
    skill_b = _make_skill("voltage-drop", "def drop(): pass")

    archive.insert(
        _make_bd(token_cost=0.0, reward=0.9),
        _make_snapshot("v_with_a", skills=[skill_a]),
    )
    archive.insert(
        _make_bd(token_cost=500_000.0, reward=0.5),
        _make_snapshot("v_with_b", skills=[skill_b]),
    )
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["compare_cells"]("v_with_a", "v_with_b")

    assert "cable-sizing" in result
    assert "voltage-drop" in result
    assert "Only in A" in result
    assert "Only in B" in result


# ---------------------------------------------------------------------------
# inspect_cell
# ---------------------------------------------------------------------------


def test_inspect_cell_shows_detail() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["inspect_cell"]("v_high")

    # Should show reward and token cost
    assert "0.9000" in result
    assert "0.0" in result  # token_cost
    assert "High reward prompt" in result
    assert "electrical" in result


def test_inspect_cell_not_found() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["inspect_cell"]("v_nonexistent")

    assert "not found" in result.lower()
    assert "v_nonexistent" in result


def test_inspect_cell_shows_skills() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    skill = _make_skill("pipe-sizing", "def size_pipe(): return 42")
    archive.insert(
        _make_bd(reward=0.7),
        _make_snapshot("v_skilled", skills=[skill]),
    )
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["inspect_cell"]("v_skilled")

    assert "pipe-sizing" in result
    assert "Skill for pipe-sizing" in result


# ---------------------------------------------------------------------------
# coverage_gaps
# ---------------------------------------------------------------------------


def test_coverage_gaps_shows_empty_regions() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["coverage_gaps"]()

    assert "Coverage" in result
    assert "Occupied" in result
    assert "Empty" in result


def test_coverage_gaps_empty_archive() -> None:
    archive = QDArchive(n_centroids=100, seed=0)
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["coverage_gaps"]()

    assert "empty" in result.lower()
    assert "100" in result  # total_centroids


# ---------------------------------------------------------------------------
# read_graveyard
# ---------------------------------------------------------------------------


def test_read_graveyard_empty() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["read_graveyard"]()

    assert "empty" in result.lower()


def test_read_graveyard_with_entries() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = _populated_graveyard()
    tools = build_archive_tools(archive, graveyard)

    result = tools["read_graveyard"](limit=5)

    assert "add_skill" in result
    assert "modify_prompt" in result
    assert "cable-sizing" in result
    assert "Score regressed" in result
    assert "0.500" in result


# ---------------------------------------------------------------------------
# _parse_selection
# ---------------------------------------------------------------------------


def test_parse_selection_valid_format() -> None:
    text = (
        "I have reviewed the archive carefully.\n"
        "SELECTED: v_high\n"
        "INSPIRATION: v_mid, v_low\n"
        "STRATEGY: crossover\n"
        "REASON: v_high has the best reward and diverse skills.\n"
    )
    shortlist = ["v_high", "v_mid", "v_low"]
    result = _parse_selection(text, shortlist)

    assert result.parent_version == "v_high"
    assert result.inspiration_versions == ["v_mid", "v_low"]
    assert result.strategy == "crossover"
    assert "best reward" in result.reasoning


def test_parse_selection_fallback() -> None:
    text = "I could not decide."  # missing SELECTED tag
    shortlist = ["v_a", "v_b"]
    result = _parse_selection(text, shortlist)

    assert result.parent_version == "v_a"
    assert result.strategy == "conservative"
    assert "Fallback" in result.reasoning


def test_parse_selection_invalid_version_falls_back() -> None:
    text = "SELECTED: v_unknown\nSTRATEGY: exploratory\nREASON: seemed good"
    shortlist = ["v_a", "v_b"]
    result = _parse_selection(text, shortlist)

    # v_unknown is not in shortlist, so must fall back to first entry
    assert result.parent_version == "v_a"
    assert result.strategy == "conservative"


def test_parse_selection_empty_shortlist_returns_empty() -> None:
    text = "SELECTED: v_high\nSTRATEGY: conservative\nREASON: best"
    shortlist: list[str] = []
    result = _parse_selection(text, shortlist)

    assert result.parent_version == ""
    assert result.strategy == "conservative"
