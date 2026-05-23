# ABOUTME: Tests for the evolution Workspace class.
# ABOUTME: Covers load validation, prompt/skill I/O, snapshots, and git versioning.

from pathlib import Path

import pytest
import yaml

from aec_bench.contracts.evolution import SkillEntry, WorkspaceSnapshot, WorkspaceVersion
from aec_bench.evolution.workspace import Workspace, WorkspaceError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scaffold_workspace(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "test-workspace",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    prompts_dir = root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are an engineering agent.")
    return root


def _make_skill(name: str = "voltage-formulas") -> SkillEntry:
    return SkillEntry(
        name=name,
        description="Voltage drop calculation reference",
        discipline="electrical",
        body="## Voltage Drop\nV_d = mV/A/m * I * L / 1000",
    )


# ---------------------------------------------------------------------------
# TestWorkspaceLoad
# ---------------------------------------------------------------------------


class TestWorkspaceLoad:
    def test_load_valid_workspace(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        assert ws.root == root
        assert ws.manifest.name == "test-workspace"
        assert ws.manifest.agent_adapter == "tool_loop"

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "ws"
        root.mkdir()
        # No manifest.yaml
        with pytest.raises(WorkspaceError, match="manifest.yaml"):
            Workspace(root)

    def test_missing_system_prompt_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "ws"
        root.mkdir()
        manifest = {
            "name": "test-workspace",
            "agent_adapter": "tool_loop",
            "evolvable_layers": ["prompts"],
        }
        (root / "manifest.yaml").write_text(yaml.dump(manifest))
        # No prompts/system.md
        with pytest.raises(WorkspaceError, match="system.md"):
            Workspace(root)


# ---------------------------------------------------------------------------
# TestWorkspacePrompts
# ---------------------------------------------------------------------------


class TestWorkspacePrompts:
    def test_read_prompt(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        assert ws.read_prompt() == "You are an engineering agent."

    def test_write_prompt(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.write_prompt("You are a structural engineer.")
        assert ws.read_prompt() == "You are a structural engineer."
        # Confirm it is persisted on disk
        assert (root / "prompts" / "system.md").read_text() == "You are a structural engineer."


# ---------------------------------------------------------------------------
# TestWorkspaceSkills
# ---------------------------------------------------------------------------


class TestWorkspaceSkills:
    def test_list_empty_skills(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        assert ws.list_skills() == []

    def test_write_and_read_skill(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        skill = _make_skill("voltage-formulas")
        ws.write_skill(skill)
        result = ws.read_skill("voltage-formulas")
        assert result is not None
        assert result.name == "voltage-formulas"
        assert result.description == "Voltage drop calculation reference"
        assert result.discipline == "electrical"
        assert "V_d" in result.body

    def test_list_skills_returns_written(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.write_skill(_make_skill("skill-a"))
        ws.write_skill(_make_skill("skill-b"))
        names = {s.name for s in ws.list_skills()}
        assert names == {"skill-a", "skill-b"}

    def test_delete_skill(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.write_skill(_make_skill("voltage-formulas"))
        ws.delete_skill("voltage-formulas")
        assert ws.list_skills() == []

    def test_read_nonexistent_skill_returns_none(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        assert ws.read_skill("does-not-exist") is None


# ---------------------------------------------------------------------------
# TestWorkspaceSnapshot
# ---------------------------------------------------------------------------


class TestWorkspaceSnapshot:
    def test_export_snapshot_with_skills(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.write_skill(_make_skill("voltage-formulas"))
        snapshot = ws.export_snapshot(workspace_version="evo-0")
        assert isinstance(snapshot, WorkspaceSnapshot)
        assert snapshot.system_prompt == "You are an engineering agent."
        assert snapshot.workspace_version == "evo-0"
        assert len(snapshot.skills) == 1
        assert snapshot.skills[0].name == "voltage-formulas"

    def test_export_snapshot_no_skills(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        snapshot = ws.export_snapshot(workspace_version="evo-1")
        assert snapshot.skills == []
        assert snapshot.workspace_version == "evo-1"


# ---------------------------------------------------------------------------
# TestWorkspaceVersioning
# ---------------------------------------------------------------------------


class TestWorkspaceVersioning:
    def test_init_creates_evo_0_tag(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        version = ws.init_versioning()
        assert isinstance(version, WorkspaceVersion)
        assert version.tag == "evo-0"
        assert version.sha != ""
        versions = ws.list_versions()
        assert len(versions) == 1
        assert versions[0].tag == "evo-0"

    def test_commit_and_tag(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()
        ws.write_prompt("Updated prompt.")
        version = ws.commit_and_tag(
            tag="evo-1",
            summary="Test mutation",
            score=0.75,
            parent_tag="evo-0",
        )
        assert version.tag == "evo-1"
        assert version.parent_tag == "evo-0"
        assert version.score_at_tag == 0.75
        versions = ws.list_versions()
        assert len(versions) == 2
        tags = {v.tag for v in versions}
        assert tags == {"evo-0", "evo-1"}

    def test_rollback_creates_new_commit(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()
        # Mutate and tag evo-1
        ws.write_prompt("Mutated prompt.")
        ws.commit_and_tag(tag="evo-1", summary="Mutation", score=0.5)
        # Rollback to evo-0 (original prompt)
        ws.rollback_to_tag("evo-0")
        # Prompt should be restored
        assert ws.read_prompt() == "You are an engineering agent."
        # Both tags must still exist
        versions = ws.list_versions()
        tags = {v.tag for v in versions}
        assert "evo-0" in tags
        assert "evo-1" in tags

    def test_get_diff_between_tags(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()
        ws.write_prompt("Updated system prompt content.")
        ws.commit_and_tag(tag="evo-1", summary="Prompt update")
        diff = ws.get_diff("evo-0", "evo-1")
        # The diff should mention the changed file
        assert "system.md" in diff or "prompts" in diff
