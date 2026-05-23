# ABOUTME: Tests for the post-mutation workspace sanitiser (Phase 4b).
# ABOUTME: Covers budget enforcement, skill truncation, dedup, empty removal, and prompt capping.

from __future__ import annotations

from pathlib import Path

import yaml

from aec_bench.contracts.evolution import SkillEntry
from aec_bench.evolution.sanitiser import sanitise_workspace
from aec_bench.evolution.workspace import Workspace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scaffold_workspace(root: Path, skill_budget: int = 10) -> Workspace:
    """Create minimal workspace directory structure and return a Workspace."""
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "test-workspace",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
        "skill_budget": skill_budget,
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    prompts_dir = root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are an engineering agent.")
    return Workspace(root)


def _add_skill(ws: Workspace, name: str, body: str) -> None:
    """Create a SkillEntry and write it to the workspace."""
    skill = SkillEntry(
        name=name,
        description=f"Description for {name}",
        body=body,
    )
    ws.write_skill(skill)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSanitiseWorkspace:
    def test_no_issues_when_under_budget(self, tmp_path: Path) -> None:
        """2 skills with budget 5 — nothing should be removed or truncated."""
        ws = _scaffold_workspace(tmp_path / "ws", skill_budget=5)
        _add_skill(ws, "alpha", "This is a valid skill body with enough characters.")
        _add_skill(ws, "beta", "Another valid skill body with enough characters too.")

        result = sanitise_workspace(ws)

        assert result.skills_removed == []
        assert result.skills_truncated == []
        assert result.prompt_truncated is False
        assert len(ws.list_skills()) == 2

    def test_removes_excess_skills_over_budget(self, tmp_path: Path) -> None:
        """6 skills with budget 3 — 3 removed (later alphabetically removed first)."""
        ws = _scaffold_workspace(tmp_path / "ws", skill_budget=3)
        # Each body is unique enough to avoid Jaccard dedup
        distinct_bodies = {
            "alpha": "voltage drop calculation using standard cable sizing formulas and tables",
            "bravo": "concrete beam design with reinforcement layout and shear capacity checks",
            "charlie": "hydraulic gradient analysis for stormwater drainage pipe networks",
            "delta": "geotechnical bearing capacity of shallow foundations on clay soils",
            "echo": "fire protection sprinkler system design with flow rate calculations",
            "foxtrot": "structural steel connection design bolt group eccentricity analysis",
        }
        for name, body in distinct_bodies.items():
            _add_skill(ws, name, body)

        result = sanitise_workspace(ws)

        assert len(ws.list_skills()) == 3
        assert len(result.skills_removed) == 3
        remaining_names = {s.name for s in ws.list_skills()}
        assert remaining_names == {"alpha", "bravo", "charlie"}

    def test_truncates_oversized_skill_bodies(self, tmp_path: Path) -> None:
        """A 6000-char skill body should be truncated to 4000 chars (no LLM)."""
        ws = _scaffold_workspace(tmp_path / "ws", skill_budget=5)
        long_body = "x" * 6000
        _add_skill(ws, "oversized", long_body)
        _add_skill(ws, "normal", "This skill body is perfectly fine and under the limit.")

        result = sanitise_workspace(ws)

        assert "oversized" in result.skills_truncated
        assert "normal" not in result.skills_truncated

        # Re-read the skill from disk to verify truncation
        truncated_skill = ws.read_skill("oversized")
        assert truncated_skill is not None
        assert len(truncated_skill.body) == 4000

    def test_removes_empty_skills(self, tmp_path: Path) -> None:
        """A skill with body < 20 chars should be removed, normal skill kept."""
        ws = _scaffold_workspace(tmp_path / "ws", skill_budget=10)
        _add_skill(ws, "normal", "This skill body has more than twenty characters easily.")
        # Write a tiny skill body directly to bypass SkillEntry validation
        tiny_skill = SkillEntry(
            name="tiny",
            description="A tiny skill",
            body="short body here.",  # 16 chars — under the 20-char minimum
        )
        ws.write_skill(tiny_skill)

        result = sanitise_workspace(ws)

        assert "tiny" in result.skills_removed
        assert "normal" not in result.skills_removed
        remaining = {s.name for s in ws.list_skills()}
        assert "tiny" not in remaining
        assert "normal" in remaining

    def test_deduplicates_similar_skills(self, tmp_path: Path) -> None:
        """Two skills with near-identical bodies — the duplicate is removed."""
        ws = _scaffold_workspace(tmp_path / "ws", skill_budget=10)
        shared_words = "voltage drop calculation using the standard formula for cable sizing"
        _add_skill(ws, "alpha", shared_words)
        _add_skill(ws, "beta", shared_words + " extra")

        result = sanitise_workspace(ws)

        assert len(result.skills_removed) == 1
        # First alphabetically kept, second removed
        remaining = {s.name for s in ws.list_skills()}
        assert "alpha" in remaining
        assert "beta" not in remaining

    def test_truncates_oversized_prompt(self, tmp_path: Path) -> None:
        """A 6000-char system prompt should be truncated to 4000 chars."""
        ws = _scaffold_workspace(tmp_path / "ws", skill_budget=5)
        ws.write_prompt("y" * 6000)

        result = sanitise_workspace(ws)

        assert result.prompt_truncated is True
        assert len(ws.read_prompt()) == 4000
