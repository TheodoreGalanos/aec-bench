# ABOUTME: Tests for the evolution Workspace class.
# ABOUTME: Covers load validation, prompt/skill I/O, snapshots, and git versioning.

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from aec_bench.contracts.evolution import (
    SkillEntry,
    WorkspaceCandidateVersion,
    WorkspaceMigrationCandidate,
    WorkspaceMigrationPlan,
    WorkspaceSnapshot,
)
from aec_bench.evolution.workspace import Workspace, WorkspaceError

# ---------------------------------------------------------------------------
# Helpers
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


def _make_skill(name: str = "voltage-formulas") -> SkillEntry:
    return SkillEntry(
        name=name,
        description="Voltage drop calculation reference",
        discipline="electrical",
        body="## Voltage Drop\nV_d = mV/A/m * I * L / 1000",
    )


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# TestWorkspaceLoad
# ---------------------------------------------------------------------------


class TestWorkspaceLoad:
    def test_load_valid_workspace(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        assert ws.root == root
        assert ws.manifest.name == "test-workspace"
        assert ws.manifest.schema_version == 1
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

    def test_legacy_manifest_has_explicit_reader(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        manifest_path = root / "manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest.pop("schema_version")
        manifest["version"] = "0.1.0"
        manifest_path.write_text(yaml.safe_dump(manifest))

        assert Workspace(root).manifest.schema_version == 1

    def test_unknown_legacy_manifest_version_is_rejected(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        manifest_path = root / "manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest.pop("schema_version")
        manifest["version"] = "9.0.0"
        manifest_path.write_text(yaml.safe_dump(manifest))

        with pytest.raises(WorkspaceError, match="unsupported legacy workspace manifest version"):
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
        snapshot = ws.export_snapshot(candidate_id="baseline")
        assert isinstance(snapshot, WorkspaceSnapshot)
        assert snapshot.system_prompt == "You are an engineering agent."
        assert snapshot.candidate_id == "baseline"
        assert len(snapshot.skills) == 1
        assert snapshot.skills[0].name == "voltage-formulas"

    def test_export_snapshot_no_skills(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        snapshot = ws.export_snapshot(candidate_id="run:1")
        assert snapshot.skills == []
        assert snapshot.candidate_id == "run:1"


# ---------------------------------------------------------------------------
# TestWorkspaceVersioning
# ---------------------------------------------------------------------------


class TestWorkspaceVersioning:
    def test_init_registers_baseline_with_full_sha_and_label(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        candidate = ws.init_versioning()
        assert isinstance(candidate, WorkspaceCandidateVersion)
        assert candidate.candidate_id == "baseline"
        assert candidate.label == "evo-0"
        assert len(candidate.source_revision) == 40
        assert ws.list_candidates() == [candidate]

    def test_commit_candidate_keeps_identity_source_and_lineage_separate(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()
        ws.write_prompt("Updated prompt.")
        candidate = ws.commit_candidate(
            candidate_id="run:1",
            summary="Test mutation",
            score=0.75,
            parent_candidate_id="baseline",
            label="evo-1",
        )
        assert candidate.candidate_id == "run:1"
        assert candidate.parent_candidate_id == "baseline"
        assert candidate.score == 0.75
        assert candidate.label == "evo-1"
        assert len(candidate.source_revision) == 40
        assert {item.candidate_id for item in ws.list_candidates()} == {"baseline", "run:1"}

    def test_rollback_creates_new_commit(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()
        ws.write_prompt("Mutated prompt.")
        ws.commit_candidate(
            candidate_id="run:1",
            summary="Mutation",
            score=0.5,
            parent_candidate_id="baseline",
            label="evo-1",
        )
        ws.rollback_to_candidate("baseline")
        assert ws.read_prompt() == "You are an engineering agent."
        assert {item.label for item in ws.list_candidates()} == {"evo-0", "evo-1"}

    def test_get_diff_between_candidates(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()
        ws.write_prompt("Updated system prompt content.")
        ws.commit_candidate(
            candidate_id="run:1",
            summary="Prompt update",
            parent_candidate_id="baseline",
            label="evo-1",
        )
        diff = ws.get_diff("baseline", "run:1")
        assert "system.md" in diff or "prompts" in diff

    def test_listing_uses_stable_git_commit_time(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        ws.init_versioning()

        first = ws.candidate_commit_time("baseline")
        second = ws.candidate_commit_time("baseline")

        assert first == second

    def test_same_candidate_and_label_is_idempotent(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        ws.init_versioning()
        first = ws.commit_candidate(
            candidate_id="run:1",
            summary="Mutation",
            parent_candidate_id="baseline",
            label="evo-1",
        )

        second = ws.commit_candidate(
            candidate_id="run:1",
            summary="Mutation",
            parent_candidate_id="baseline",
            label="evo-1",
        )

        assert second == first

    def test_existing_label_cannot_be_reused_for_new_candidate(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()
        first = ws.commit_candidate(
            candidate_id="run:1",
            summary="First",
            parent_candidate_id="baseline",
            label="evo-1",
        )

        with pytest.raises(WorkspaceError, match="label 'evo-1' already identifies"):
            ws.commit_candidate(
                candidate_id="run:2",
                summary="Second",
                parent_candidate_id="run:1",
                label="evo-1",
            )

        assert _git(root, "rev-parse", "evo-1^{commit}") == first.source_revision

    def test_moved_label_is_rejected(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()
        ws.write_prompt("Candidate one")
        ws.commit_candidate(
            candidate_id="run:1",
            summary="Mutation",
            parent_candidate_id="baseline",
            label="evo-1",
        )
        ws.write_prompt("Unregistered source")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "unregistered source")
        _git(root, "tag", "-f", "evo-1", "HEAD")

        with pytest.raises(WorkspaceError, match="immutable label.*moved"):
            ws.list_candidates()

    def test_candidate_parent_can_differ_from_git_parent(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()
        first = ws.commit_candidate(
            candidate_id="run:1",
            summary="First",
            parent_candidate_id="baseline",
        )
        second = ws.commit_candidate(
            candidate_id="run:2",
            summary="Second",
            parent_candidate_id="baseline",
        )

        assert second.parent_candidate_id == "baseline"
        assert _git(root, "rev-parse", f"{second.source_revision}^") == first.source_revision

    def test_legacy_migration_requires_expected_source(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        _git(root, "init")
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "test")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "legacy baseline")
        _git(root, "tag", "evo-0")

        report = Workspace(root).migrate_legacy_versions(
            WorkspaceMigrationPlan(candidates=(WorkspaceMigrationCandidate(candidate_id="baseline", label="evo-0"),))
        )

        assert report.complete is False
        assert report.issues[0].code == "source_ambiguous"

    def test_legacy_migration_reports_moved_label(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        _git(root, "init")
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "test")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "legacy baseline")
        _git(root, "tag", "evo-0")

        report = Workspace(root).migrate_legacy_versions(
            WorkspaceMigrationPlan(
                candidates=(
                    WorkspaceMigrationCandidate(
                        candidate_id="baseline",
                        label="evo-0",
                        expected_source_revision="f" * 40,
                    ),
                )
            )
        )

        assert report.complete is False
        assert report.issues[0].code == "label_moved"

    def test_legacy_migration_preserves_explicit_lineage(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        _git(root, "init")
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "test")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "legacy baseline")
        baseline_sha = _git(root, "rev-parse", "HEAD")
        _git(root, "tag", "evo-0")
        (root / "prompts" / "system.md").write_text("Legacy candidate")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "cycle 1: score 0.750")
        candidate_sha = _git(root, "rev-parse", "HEAD")
        _git(root, "tag", "evo-1")
        (root / "archive.json").write_text(
            json.dumps({"n_centroids": 1, "entries": [{"snapshot": {"workspace_version": "evo-1"}}]})
        )
        (root / "graveyard.json").write_text(json.dumps([{"workspace_version": "evo-1"}]))

        report = Workspace(root).migrate_legacy_versions(
            WorkspaceMigrationPlan(
                candidates=(
                    WorkspaceMigrationCandidate(
                        candidate_id="baseline",
                        label="evo-0",
                        expected_source_revision=baseline_sha,
                    ),
                    WorkspaceMigrationCandidate(
                        candidate_id="legacy:1",
                        label="evo-1",
                        parent_candidate_id="baseline",
                        expected_source_revision=candidate_sha,
                    ),
                )
            )
        )

        assert report.complete is True
        migrated = Workspace(root).require_candidate("legacy:1")
        assert migrated.parent_candidate_id == "baseline"
        assert migrated.source_revision == candidate_sha
        assert migrated.score == 0.75
        archive = json.loads((root / "archive.json").read_text())
        graveyard = json.loads((root / "graveyard.json").read_text())
        assert archive["entries"][0]["snapshot"] == {"candidate_id": "legacy:1"}
        assert graveyard[0] == {"candidate_id": "legacy:1"}

    def test_migration_lists_candidate_outside_head_ancestry(self, tmp_path: Path) -> None:
        root = _scaffold_workspace(tmp_path / "ws")
        _git(root, "init")
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "test")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "legacy baseline")
        baseline_sha = _git(root, "rev-parse", "HEAD")
        _git(root, "tag", "evo-0")
        _git(root, "checkout", "-b", "candidate-side")
        (root / "prompts" / "system.md").write_text("Side candidate")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "side candidate")
        side_sha = _git(root, "rev-parse", "HEAD")
        _git(root, "tag", "evo-side")
        _git(root, "checkout", "--detach", baseline_sha)

        report = Workspace(root).migrate_legacy_versions(
            WorkspaceMigrationPlan(
                candidates=(
                    WorkspaceMigrationCandidate(
                        candidate_id="baseline",
                        label="evo-0",
                        expected_source_revision=baseline_sha,
                    ),
                    WorkspaceMigrationCandidate(
                        candidate_id="side:1",
                        label="evo-side",
                        parent_candidate_id="baseline",
                        expected_source_revision=side_sha,
                    ),
                )
            )
        )

        assert report.complete is True
        assert {candidate.candidate_id for candidate in Workspace(root).list_candidates()} == {
            "baseline",
            "side:1",
        }
