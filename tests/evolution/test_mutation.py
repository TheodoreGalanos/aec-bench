# ABOUTME: Tests typed evolution mutations against an isolated workspace.
# ABOUTME: Covers prompt and skill changes and their exact mutation summaries.

from __future__ import annotations

from pathlib import Path

import yaml

from aec_bench.evolution.mutation import (
    MutationAction,
    apply_mutations,
)
from aec_bench.evolution.workspace import Workspace

# ---------------------------------------------------------------------------
# Helpers shared with workspace tests (inlined to avoid cross-test imports)
# ---------------------------------------------------------------------------


def _scaffold_workspace(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "name": "test-workspace",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    prompts_dir = root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are an engineering agent.")
    return root


class TestApplyMutations:
    def test_write_skill_action(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        actions = [
            MutationAction(
                action_type="write_skill",
                skill_name="voltage-formulas",
                skill_description="Voltage drop reference",
                skill_discipline="electrical",
                skill_body="## Voltage Drop\nV_d = mV/A/m * I * L / 1000",
            )
        ]

        summary = apply_mutations(actions, ws)

        skill_names = [s.name for s in ws.list_skills()]
        assert "voltage-formulas" in skill_names
        assert "voltage-formulas" in summary.skills_added
        assert summary.skills_modified == []
        assert summary.skills_removed == []
        assert summary.prompt_modified is False

    def test_modify_existing_skill(self, tmp_path: Path) -> None:
        from aec_bench.contracts.evolution import SkillEntry

        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        ws.write_skill(
            SkillEntry(
                name="voltage-formulas",
                description="Old description",
                discipline="electrical",
                body="## Old Body",
            )
        )
        actions = [
            MutationAction(
                action_type="modify_skill",
                skill_name="voltage-formulas",
                skill_body="## New Body",
            )
        ]

        summary = apply_mutations(actions, ws)

        updated = ws.read_skill("voltage-formulas")
        assert updated is not None
        assert updated.body == "## New Body"
        assert "voltage-formulas" in summary.skills_modified
        assert summary.skills_added == []

    def test_modify_nonexistent_skill_creates_it(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        actions = [
            MutationAction(
                action_type="modify_skill",
                skill_name="brand-new",
                skill_description="Created via modify",
                skill_body="## Brand New Skill",
            )
        ]

        summary = apply_mutations(actions, ws)

        skill = ws.read_skill("brand-new")
        assert skill is not None
        assert "brand-new" in summary.skills_added
        assert summary.skills_modified == []

    def test_delete_skill_action(self, tmp_path: Path) -> None:
        from aec_bench.contracts.evolution import SkillEntry

        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        ws.write_skill(
            SkillEntry(
                name="to-delete",
                description="Will be removed",
                body="## Goodbye",
            )
        )
        actions = [
            MutationAction(
                action_type="delete_skill",
                skill_name="to-delete",
            )
        ]

        summary = apply_mutations(actions, ws)

        assert ws.read_skill("to-delete") is None
        assert "to-delete" in summary.skills_removed
        assert summary.skills_added == []
        assert summary.skills_modified == []

    def test_delete_nonexistent_skill_no_error(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        actions = [
            MutationAction(
                action_type="delete_skill",
                skill_name="ghost-skill",
            )
        ]

        summary = apply_mutations(actions, ws)

        assert summary.skills_removed == []

    def test_modify_prompt_action(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        new_content = "You are a structural engineering specialist."
        actions = [
            MutationAction(
                action_type="modify_prompt",
                prompt_content=new_content,
            )
        ]

        summary = apply_mutations(actions, ws)

        assert ws.read_prompt() == new_content
        assert summary.prompt_modified is True

    def test_multiple_actions(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        actions = [
            MutationAction(
                action_type="write_skill",
                skill_name="skill-alpha",
                skill_description="First skill",
                skill_body="## Alpha",
            ),
            MutationAction(
                action_type="write_skill",
                skill_name="skill-beta",
                skill_description="Second skill",
                skill_body="## Beta",
            ),
            MutationAction(
                action_type="modify_prompt",
                prompt_content="Updated prompt.",
            ),
        ]

        summary = apply_mutations(actions, ws)

        assert "skill-alpha" in summary.skills_added
        assert "skill-beta" in summary.skills_added
        assert summary.prompt_modified is True
        skill_names = [s.name for s in ws.list_skills()]
        assert "skill-alpha" in skill_names
        assert "skill-beta" in skill_names

    def test_empty_actions(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))

        summary = apply_mutations([], ws)

        assert summary.prompt_modified is False
        assert summary.skills_added == []
        assert summary.skills_modified == []
        assert summary.skills_removed == []
        assert summary.memory_entries_added == 0
