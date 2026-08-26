# ABOUTME: Tests for the archive-explorer agent tools and selection pipeline.
# ABOUTME: Verifies browse, compare, inspect, and graveyard tools.

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aec_bench.contracts.evolution import BehaviourDescriptor, MutationStrategy, SkillEntry, WorkspaceSnapshot
from aec_bench.evolution.archive import ArchiveView, QDArchive
from aec_bench.evolution.archive_agent import _parse_selection, build_archive_tools, run_archive_selection
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
        candidate_id=version,
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
            candidate_id="v1",
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
            candidate_id="v2",
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
    tools = build_archive_tools(archive.view(), graveyard)

    result = tools["browse_archive"](sort_by="reward", limit=3)

    assert "v_high" in result
    assert "v_mid" in result
    assert "0.900" in result  # reward for v_high
    assert "| Candidate | Reward |" in result


def test_browse_archive_frontier_sort() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive.view(), graveyard)

    result = tools["browse_archive"](sort_by="frontier", limit=3)

    # Should return a table with at least one version
    assert "| Candidate | Reward |" in result
    assert "v_high" in result


def test_browse_archive_empty_returns_message() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive.view(), graveyard)

    result = tools["browse_archive"]()

    assert "empty" in result.lower()


# ---------------------------------------------------------------------------
# compare_cells
# ---------------------------------------------------------------------------


def test_compare_cells_shows_diff() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive.view(), graveyard)

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
    tools = build_archive_tools(archive.view(), graveyard)

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
    tools = build_archive_tools(archive.view(), graveyard)

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
    tools = build_archive_tools(archive.view(), graveyard)

    result = tools["inspect_cell"]("v_high")

    # Should show reward and token cost
    assert "0.9000" in result
    assert "0.0" in result  # token_cost
    assert "High reward prompt" in result
    assert "electrical" in result


def test_inspect_cell_not_found() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive.view(), graveyard)

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
    tools = build_archive_tools(archive.view(), graveyard)

    result = tools["inspect_cell"]("v_skilled")

    assert "pipe-sizing" in result
    assert "Skill for pipe-sizing" in result


# ---------------------------------------------------------------------------
# coverage_gaps
# ---------------------------------------------------------------------------


def test_coverage_gaps_shows_empty_regions() -> None:
    archive = _populated_archive()
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive.view(), graveyard)

    result = tools["coverage_gaps"]()

    assert "Coverage" in result
    assert "Occupied" in result
    assert "Empty" in result


def test_coverage_gaps_empty_archive() -> None:
    archive = QDArchive(n_centroids=100, seed=0)
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive.view(), graveyard)

    result = tools["coverage_gaps"]()

    assert "empty" in result.lower()
    assert "100" in result  # total_centroids


# ---------------------------------------------------------------------------
# read_graveyard
# ---------------------------------------------------------------------------


def test_read_graveyard_empty() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = MutationGraveyard()
    tools = build_archive_tools(archive.view(), graveyard)

    result = tools["read_graveyard"]()

    assert "empty" in result.lower()


def test_read_graveyard_with_entries() -> None:
    archive = QDArchive(n_centroids=50, seed=0)
    graveyard = _populated_graveyard()
    tools = build_archive_tools(archive.view(), graveyard)

    result = tools["read_graveyard"](limit=5)

    assert "add_skill" in result
    assert "modify_prompt" in result
    assert "cable-sizing" in result
    assert "Score regressed" in result
    assert "0.500" in result


def test_run_archive_selection_passes_host_context_and_real_graveyard(monkeypatch: pytest.MonkeyPatch) -> None:
    archive = _populated_archive()
    archive_view = archive.view()
    graveyard = _populated_graveyard()
    captured: dict[str, object] = {}

    def fake_build_tools(actual_archive: ArchiveView, actual_graveyard: MutationGraveyard) -> dict[str, object]:
        captured["archive"] = actual_archive
        captured["graveyard"] = actual_graveyard
        return {}

    class FakeAgent:
        def __init__(self, *_args: object, **kwargs: object) -> None:
            captured["system_prompt"] = kwargs["system_prompt"]

        def run_sync(self, brief: str, **_kwargs: object) -> SimpleNamespace:
            captured["brief"] = brief
            return SimpleNamespace(
                output=("SELECTED: v_high\nINSPIRATION: v_mid\nREASON: The mid candidate supplies a useful comparison.")
            )

    monkeypatch.setattr("aec_bench.evolution.archive_agent.build_archive_tools", fake_build_tools)
    monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)
    monkeypatch.setattr("aec_bench.evolution.model_provider.build_pydantic_model", lambda _name: object())

    result = run_archive_selection(
        "test-model",
        archive_view,
        graveyard,
        ["v_high", "v_mid"],
        0.8,
        MutationStrategy.CONSERVATIVE,
        1,
    )

    assert result.parent_candidate_id == "v_high"
    assert result.strategy is MutationStrategy.CONSERVATIVE
    assert captured["archive"] is archive_view
    assert captured["graveyard"] is graveyard
    assert "Host-selected mutation strategy: conservative" in captured["brief"]
    assert "Maximum inspirations: 1" in captured["brief"]
    assert "Do not return a strategy" in captured["system_prompt"]


# ---------------------------------------------------------------------------
# _parse_selection
# ---------------------------------------------------------------------------


def test_parse_selection_valid_format() -> None:
    text = (
        "I have reviewed the archive carefully.\n"
        "SELECTED: v_high\n"
        "INSPIRATION: v_mid, v_low\n"
        "REASON: v_high has the best reward and diverse skills.\n"
    )
    shortlist = ["v_high", "v_mid", "v_low"]
    result = _parse_selection(text, shortlist, MutationStrategy.CROSSOVER, inspiration_limit=2)

    assert result.parent_candidate_id == "v_high"
    assert result.inspiration_candidate_ids == ("v_mid", "v_low")
    assert result.strategy is MutationStrategy.CROSSOVER
    assert result.goal == "Combine material from the selected parent and inspirations."
    assert "best reward" in result.reasoning


def test_parse_selection_invalid_output_is_rejected_without_fallback() -> None:
    with pytest.raises(ValueError, match="SELECTED"):
        _parse_selection(
            "I could not decide.",
            ["v_a", "v_b"],
            MutationStrategy.CONSERVATIVE,
            inspiration_limit=2,
        )


def test_parse_selection_rejects_strategy_change() -> None:
    text = "SELECTED: v_a\nSTRATEGY: exploratory\nREASON: The parent is suitable."
    with pytest.raises(ValueError, match="changed the selected strategy"):
        _parse_selection(text, ["v_a", "v_b"], MutationStrategy.CONSERVATIVE, inspiration_limit=2)


def test_parse_selection_rejects_model_owned_goal() -> None:
    text = "SELECTED: v_a\nGOAL: Change the host intent.\nREASON: The parent is suitable."
    with pytest.raises(ValueError, match="must not return a goal"):
        _parse_selection(text, ["v_a", "v_b"], MutationStrategy.CONSERVATIVE, inspiration_limit=2)


@pytest.mark.parametrize(
    ("text", "message", "inspiration_limit"),
    [
        (
            "SELECTED: v_unknown\nREASON: It is suitable.",
            "outside the allowed candidate set",
            1,
        ),
        (
            "SELECTED: v_a\nINSPIRATION: v_unknown\nREASON: It is suitable.",
            "unknown inspiration",
            1,
        ),
        (
            "SELECTED: v_a\nINSPIRATION: v_a\nREASON: It is suitable.",
            "also be an inspiration",
            1,
        ),
        (
            "SELECTED: v_a\nINSPIRATION: v_b, v_b\nREASON: It is suitable.",
            "unique",
            2,
        ),
        (
            "SELECTED: v_a\nINSPIRATION: v_b, v_c\nREASON: It is suitable.",
            "limit is 1",
            1,
        ),
    ],
)
def test_parse_selection_rejects_invalid_id_contracts(text: str, message: str, inspiration_limit: int) -> None:
    with pytest.raises(ValueError, match=message):
        _parse_selection(
            text,
            ["v_a", "v_b", "v_c"],
            MutationStrategy.CONSERVATIVE,
            inspiration_limit=inspiration_limit,
        )


def test_parse_selection_rejects_graveyard_rescue_without_resolvable_candidate() -> None:
    text = "SELECTED: v_a\nREASON: The archive has no safer option."
    with pytest.raises(ValueError, match="resolvable graveyard candidate"):
        _parse_selection(
            text,
            ["v_a"],
            MutationStrategy.GRAVEYARD_RESCUE,
            graveyard=_populated_graveyard(),
            inspiration_limit=1,
        )


def test_parse_selection_allows_exact_graveyard_inspiration_for_rescue() -> None:
    graveyard = MutationGraveyard()
    graveyard.insert(
        GraveyardEntry(
            cycle=1,
            strategy="conservative",
            mutation_description="Added a useful check",
            score_before=0.5,
            score_after=0.4,
            candidate_id="failed-1",
            failure_reason="The score regressed",
            rejected_snapshot=_make_snapshot("failed-1"),
        )
    )
    text = "SELECTED: v_a\nINSPIRATION: failed-1\nREASON: The rejected snapshot contains a reusable idea."
    result = _parse_selection(
        text,
        ["v_a"],
        MutationStrategy.GRAVEYARD_RESCUE,
        graveyard=graveyard,
        inspiration_limit=1,
    )
    assert result.inspiration_candidate_ids == ("failed-1",)
