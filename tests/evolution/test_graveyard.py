# ABOUTME: Tests for the graveyard archive that stores failed mutations for potential rescue.
# ABOUTME: Verifies insert, query, persistence, and size limits.

from __future__ import annotations

from pathlib import Path

from aec_bench.evolution.graveyard import GraveyardEntry, MutationGraveyard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    cycle: int = 1,
    strategy: str = "add_skill",
    mutation_description: str = "Added a cable-sizing skill",
    score_before: float = 0.5,
    score_after: float = 0.3,
    workspace_version: str = "v1",
    failure_reason: str = "Score regressed",
) -> GraveyardEntry:
    return GraveyardEntry(
        cycle=cycle,
        strategy=strategy,
        mutation_description=mutation_description,
        score_before=score_before,
        score_after=score_after,
        workspace_version=workspace_version,
        failure_reason=failure_reason,
    )


# ---------------------------------------------------------------------------
# Empty graveyard
# ---------------------------------------------------------------------------


def test_empty_graveyard() -> None:
    graveyard = MutationGraveyard()
    assert graveyard.size == 0
    assert graveyard.browse() == []


# ---------------------------------------------------------------------------
# Insert and browse
# ---------------------------------------------------------------------------


def test_insert_and_browse() -> None:
    graveyard = MutationGraveyard()
    entry = _make_entry(cycle=1, workspace_version="v1")
    graveyard.insert(entry)

    results = graveyard.browse()
    assert len(results) == 1
    assert results[0] == entry


# ---------------------------------------------------------------------------
# Max size eviction
# ---------------------------------------------------------------------------


def test_max_size_evicts_oldest() -> None:
    graveyard = MutationGraveyard(max_size=3)
    for i in range(1, 6):
        graveyard.insert(_make_entry(cycle=i, workspace_version=f"v{i}"))

    # Only the 3 most recent entries should remain.
    assert graveyard.size == 3

    # browse() returns most-recent-first, so versions should be v5, v4, v3.
    results = graveyard.browse(limit=10)
    versions = [e.workspace_version for e in results]
    assert versions == ["v5", "v4", "v3"]


# ---------------------------------------------------------------------------
# Browse by strategy
# ---------------------------------------------------------------------------


def test_browse_by_strategy() -> None:
    graveyard = MutationGraveyard()
    graveyard.insert(_make_entry(cycle=1, strategy="add_skill", workspace_version="v1"))
    graveyard.insert(_make_entry(cycle=2, strategy="modify_prompt", workspace_version="v2"))
    graveyard.insert(_make_entry(cycle=3, strategy="add_skill", workspace_version="v3"))

    results = graveyard.browse(strategy="add_skill")
    assert len(results) == 2
    versions = [e.workspace_version for e in results]
    # Most recent first: v3, v1
    assert versions == ["v3", "v1"]

    prompt_results = graveyard.browse(strategy="modify_prompt")
    assert len(prompt_results) == 1
    assert prompt_results[0].workspace_version == "v2"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    graveyard = MutationGraveyard()
    graveyard.insert(_make_entry(cycle=1, workspace_version="v1", failure_reason="Score drop"))
    graveyard.insert(_make_entry(cycle=2, workspace_version="v2", failure_reason="Syntax error"))

    save_path = tmp_path / "graveyard.json"
    graveyard.save(save_path)
    assert save_path.exists()

    loaded = MutationGraveyard.load(save_path)
    assert loaded.size == graveyard.size

    # browse() is most-recent-first; compare full contents by reversing.
    original_entries = graveyard.browse(limit=100)
    loaded_entries = loaded.browse(limit=100)
    assert original_entries == loaded_entries


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    graveyard = MutationGraveyard.load(tmp_path / "nonexistent.json")
    assert graveyard.size == 0
    assert graveyard.browse() == []


# ---------------------------------------------------------------------------
# Enrichment fields
# ---------------------------------------------------------------------------


def test_enriched_entry_roundtrip(tmp_path: Path) -> None:
    """Enriched fields survive save/load."""
    graveyard = MutationGraveyard()
    graveyard.insert(
        GraveyardEntry(
            cycle=1,
            strategy="conservative",
            mutation_description="Added cable-sizing skill",
            score_before=0.5,
            score_after=0.3,
            workspace_version="v1",
            failure_reason="Score delta: -0.20",
            field_failures={"vc_mv_per_a_m": "too_high", "voltage_drop_v": "too_high"},
            detected_patterns=["no_verification"],
            mutation_actions=[
                {"action_type": "write_skill", "skill_name": "cable-ref"},
                {"action_type": "modify_prompt"},
            ],
            investigation_summary="Agent used wrong Vc table values for aluminium.",
        )
    )

    path = tmp_path / "graveyard.json"
    graveyard.save(path)
    loaded = MutationGraveyard.load(path)

    entry = loaded.browse()[0]
    assert entry.field_failures == {"vc_mv_per_a_m": "too_high", "voltage_drop_v": "too_high"}
    assert entry.detected_patterns == ["no_verification"]
    assert len(entry.mutation_actions) == 2
    assert entry.investigation_summary == "Agent used wrong Vc table values for aluminium."


def test_load_legacy_graveyard_without_enrichment(tmp_path: Path) -> None:
    """Old graveyard.json files without new fields load with None defaults."""
    import json

    legacy = [
        {
            "cycle": 1,
            "strategy": "add_skill",
            "mutation_description": "old entry",
            "score_before": 0.5,
            "score_after": 0.4,
            "workspace_version": "v1",
            "failure_reason": "Score delta: -0.10",
        }
    ]
    path = tmp_path / "graveyard.json"
    path.write_text(json.dumps(legacy))

    loaded = MutationGraveyard.load(path)
    entry = loaded.browse()[0]
    assert entry.field_failures is None
    assert entry.detected_patterns is None
    assert entry.mutation_actions is None
    assert entry.investigation_summary is None
