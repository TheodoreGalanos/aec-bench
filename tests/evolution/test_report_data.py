# ABOUTME: Tests for the evolution report data layer — git-based diff extraction.
# ABOUTME: Uses real git repos in tmp_path to validate tag parsing and diff collection.

from __future__ import annotations

import subprocess
from pathlib import Path

from aec_bench.evolution.report_data import (
    EvolutionReportData,
    _aggregate_status,
    _previous_version,
    _status_char_to_label,
    build_evolution_report_data,
    discover_workspaces,
    get_file_at_version,
    get_file_diff_at_version,
    get_file_tree_at_version,
    list_runs,
)


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_workspace(root: Path) -> None:
    """Set up a minimal evolution workspace with git history."""
    root.mkdir(exist_ok=True)
    (root / "manifest.yaml").write_text("name: test-evo\nadapter: rlm\n")
    (root / "prompts").mkdir()
    (root / "prompts" / "system.md").write_text("You are a helpful agent.")
    (root / "skills").mkdir()

    _git(root, "init")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "initial")
    _git(root, "tag", "-a", "evo-0", "-m", "evo-0: initial workspace")


def _add_cycle(root: Path, cycle: int, score: float) -> None:
    """Simulate one evolution cycle with prompt and skill changes."""
    # Modify system prompt
    prompt_path = root / "prompts" / "system.md"
    current = prompt_path.read_text()
    prompt_path.write_text(current + f"\n## Cycle {cycle} addition\nNew instructions here.")

    # Add a skill
    skill_dir = root / "skills" / f"skill-{cycle}"
    skill_dir.mkdir(exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: skill-{cycle}\ndescription: Added in cycle {cycle}\n---\nContent.")

    _git(root, "add", ".")
    _git(root, "commit", "-m", f"evo-{cycle}: cycle {cycle}: score {score:.3f}")
    _git(root, "tag", "-a", f"evo-{cycle}", "-m", f"evo-{cycle}: cycle {cycle}: score {score:.3f}")


class TestBuildEvolutionReportData:
    """Tests for building report data from git history."""

    def test_single_cycle(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.45)

        data = build_evolution_report_data(ws)
        assert isinstance(data, EvolutionReportData)
        assert data.workspace_name == "test-evo"
        assert data.total_cycles == 1
        assert len(data.cycles) == 1

    def test_cycle_score_parsed(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.45)

        data = build_evolution_report_data(ws)
        assert abs(data.cycles[0].score - 0.45) < 0.001

    def test_multiple_cycles(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.3)
        _add_cycle(ws, 2, 0.65)

        data = build_evolution_report_data(ws)
        assert data.total_cycles == 2
        assert len(data.cycles) == 2
        assert data.best_score == 0.65
        assert data.final_score == 0.65

    def test_prompt_diff_captured(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.5)

        data = build_evolution_report_data(ws)
        assert "Cycle 1 addition" in data.cycles[0].prompt_diff

    def test_skills_added_detected(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.5)

        data = build_evolution_report_data(ws)
        assert "skill-1" in data.cycles[0].skills_added

    def test_skills_modified_detected(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.5)

        # Modify the skill in cycle 2
        skill_path = ws / "skills" / "skill-1" / "SKILL.md"
        skill_path.write_text("---\nname: skill-1\n---\nUpdated content.")
        _git(ws, "add", ".")
        _git(ws, "commit", "-m", "evo-2: cycle 2: score 0.7")
        _git(ws, "tag", "-a", "evo-2", "-m", "evo-2: cycle 2: score 0.700")

        data = build_evolution_report_data(ws)
        assert "skill-1" in data.cycles[1].skills_modified

    def test_version_tags(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.3)
        _add_cycle(ws, 2, 0.6)

        data = build_evolution_report_data(ws)
        assert data.cycles[0].version_tag == "evo-1"
        assert data.cycles[1].version_tag == "evo-2"

    def test_empty_workspace_no_cycles(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)

        data = build_evolution_report_data(ws)
        assert data.total_cycles == 0
        assert data.cycles == []


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestPreviousVersion:
    """Tests for _previous_version helper."""

    def test_evo_0_returns_none(self) -> None:
        assert _previous_version("evo-0") is None

    def test_evo_1_returns_evo_0(self) -> None:
        assert _previous_version("evo-1") == "evo-0"

    def test_evo_5_returns_evo_4(self) -> None:
        assert _previous_version("evo-5") == "evo-4"


class TestPreviousVersionRunScoped:
    """Tests for _previous_version with run-scoped evo-{YYYYMMDD}-{HHMM}-N tags."""

    def test_run_scoped_cycle_2(self) -> None:
        assert _previous_version("evo-20260404-1220-2") == "evo-20260404-1220-1"

    def test_run_scoped_cycle_1_falls_back_to_evo_0(self) -> None:
        assert _previous_version("evo-20260404-1220-1") == "evo-0"

    def test_run_scoped_cycle_0_returns_none(self) -> None:
        assert _previous_version("evo-20260404-1220-0") is None

    def test_legacy_still_works(self) -> None:
        assert _previous_version("evo-3") == "evo-2"
        assert _previous_version("evo-1") == "evo-0"
        assert _previous_version("evo-0") is None

    def test_invalid_tag_returns_none(self) -> None:
        assert _previous_version("something-else") is None


class TestStatusCharToLabel:
    """Tests for _status_char_to_label helper."""

    def test_added(self) -> None:
        assert _status_char_to_label("A") == "added"

    def test_modified(self) -> None:
        assert _status_char_to_label("M") == "modified"

    def test_deleted(self) -> None:
        assert _status_char_to_label("D") == "removed"

    def test_unknown_char(self) -> None:
        assert _status_char_to_label("X") == "unchanged"


class TestAggregateStatus:
    """Tests for _aggregate_status helper."""

    def test_all_unchanged(self) -> None:
        children = [
            {"status": "unchanged"},
            {"status": "unchanged"},
        ]
        assert _aggregate_status(children) == "unchanged"

    def test_one_added(self) -> None:
        children = [
            {"status": "unchanged"},
            {"status": "added"},
        ]
        assert _aggregate_status(children) == "added"

    def test_removed_beats_modified(self) -> None:
        children = [
            {"status": "modified"},
            {"status": "removed"},
        ]
        assert _aggregate_status(children) == "removed"

    def test_empty_children(self) -> None:
        assert _aggregate_status([]) == "unchanged"


# ---------------------------------------------------------------------------
# discover_workspaces tests
# ---------------------------------------------------------------------------


def _init_workspace_with_evolution(root: Path) -> None:
    """Set up a workspace with both manifest.yaml and evolution.yaml."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.yaml").write_text("name: test-evo\nadapter: rlm\n")
    (root / "evolution.yaml").write_text("models:\n  evolver: claude-sonnet-4-20250514\n")
    (root / "prompts").mkdir()
    (root / "prompts" / "system.md").write_text("You are a helpful agent.")
    (root / "skills").mkdir()

    _git(root, "init")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "initial")
    _git(root, "tag", "-a", "evo-0", "-m", "evo-0: initial workspace")


class TestDiscoverWorkspaces:
    """Tests for discover_workspaces."""

    def test_finds_valid_workspace(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "my-evo"
        _init_workspace_with_evolution(ws)
        _add_cycle(ws, 1, 0.45)

        results = discover_workspaces(tmp_path / "workspaces")
        assert len(results) == 1
        result = results[0]
        assert result["name"] == "test-evo"
        assert result["path"] == "my-evo"
        assert result["cycles"] == 1
        assert abs(result["best_score"] - 0.45) < 0.001
        assert abs(result["final_score"] - 0.45) < 0.001
        assert result["model"] == "claude-sonnet-4-20250514"

    def test_ignores_incomplete_dirs(self, tmp_path: Path) -> None:
        search = tmp_path / "workspaces"
        search.mkdir()
        # Directory with only manifest.yaml (no evolution.yaml)
        only_manifest = search / "only-manifest"
        only_manifest.mkdir()
        (only_manifest / "manifest.yaml").write_text("name: no-evo\n")

        # Directory with only evolution.yaml (no manifest.yaml)
        only_evo = search / "only-evo"
        only_evo.mkdir()
        (only_evo / "evolution.yaml").write_text("models:\n  evolver: x\n")

        # Empty directory
        (search / "empty").mkdir()

        results = discover_workspaces(search)
        assert results == []

    def test_finds_multiple_workspaces(self, tmp_path: Path) -> None:
        search = tmp_path / "workspaces"
        ws1 = search / "alpha"
        _init_workspace_with_evolution(ws1)
        _add_cycle(ws1, 1, 0.3)

        ws2 = search / "beta"
        ws2.mkdir(parents=True, exist_ok=True)
        (ws2 / "manifest.yaml").write_text("name: beta-evo\nadapter: rlm\n")
        (ws2 / "evolution.yaml").write_text("models:\n  evolver: gpt-4.1-mini\n")
        (ws2 / "prompts").mkdir()
        (ws2 / "prompts" / "system.md").write_text("system prompt")
        (ws2 / "skills").mkdir()
        _git(ws2, "init")
        _git(ws2, "add", ".")
        _git(ws2, "commit", "-m", "initial")
        _git(ws2, "tag", "-a", "evo-0", "-m", "evo-0: initial")
        _add_cycle(ws2, 1, 0.7)

        results = discover_workspaces(search)
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"test-evo", "beta-evo"}


# ---------------------------------------------------------------------------
# get_file_tree_at_version tests
# ---------------------------------------------------------------------------


class TestGetFileTreeAtVersion:
    """Tests for get_file_tree_at_version."""

    def test_file_tree_at_evo0(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)

        tree = get_file_tree_at_version(ws, "evo-0")
        assert isinstance(tree, dict)
        assert tree["name"] == "."
        assert tree["type"] == "directory"
        # All files at evo-0 should be "added"
        assert tree["status"] == "added"

        # Flatten to find files
        all_files = _collect_files(tree)
        file_names = {f["name"] for f in all_files}
        assert "manifest.yaml" in file_names
        assert "system.md" in file_names

        # Every file at evo-0 should be "added"
        for f in all_files:
            assert f["status"] == "added", f"Expected 'added' for {f['name']}"

    def test_file_tree_at_evo1_shows_changes(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.5)

        tree = get_file_tree_at_version(ws, "evo-1")
        all_files = _collect_files(tree)
        file_names = {f["name"] for f in all_files}

        # The newly added skill file should be present
        assert "SKILL.md" in file_names

        # system.md was modified
        system_files = [f for f in all_files if f["name"] == "system.md"]
        assert len(system_files) == 1
        assert system_files[0]["status"] == "modified"

        # The newly added SKILL.md should be "added"
        skill_files = [f for f in all_files if f["name"] == "SKILL.md"]
        assert len(skill_files) == 1
        assert skill_files[0]["status"] == "added"

    def test_directory_nodes_have_children(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)

        tree = get_file_tree_at_version(ws, "evo-0")
        # The root should have children
        assert "children" in tree
        assert len(tree["children"]) > 0

        # Find the "prompts" directory
        prompts_dirs = [c for c in tree["children"] if c["name"] == "prompts"]
        assert len(prompts_dirs) == 1
        assert prompts_dirs[0]["type"] == "directory"
        assert len(prompts_dirs[0]["children"]) > 0


# ---------------------------------------------------------------------------
# get_file_at_version tests
# ---------------------------------------------------------------------------


class TestGetFileAtVersion:
    """Tests for get_file_at_version."""

    def test_get_file_at_evo0(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)

        result = get_file_at_version(ws, "evo-0", "manifest.yaml")
        assert result["path"] == "manifest.yaml"
        assert result["version"] == "evo-0"
        assert "name: test-evo" in result["content"]
        assert result["language"] == "yaml"

    def test_get_file_at_evo1(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.5)

        result = get_file_at_version(ws, "evo-1", "prompts/system.md")
        assert "Cycle 1 addition" in result["content"]
        assert result["language"] == "markdown"

    def test_language_detection(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir(parents=True)
        (ws / "manifest.yaml").write_text("name: lang-test\n")
        (ws / "config.toml").write_text("[section]\nkey = 1\n")
        (ws / "data.json").write_text('{"a": 1}\n')
        (ws / "script.py").write_text("print('hello')\n")
        (ws / "readme.md").write_text("# Hello\n")
        (ws / "notes.txt").write_text("plain text\n")

        _git(ws, "init")
        _git(ws, "add", ".")
        _git(ws, "commit", "-m", "initial")
        _git(ws, "tag", "-a", "evo-0", "-m", "evo-0: initial")

        assert get_file_at_version(ws, "evo-0", "manifest.yaml")["language"] == "yaml"
        assert get_file_at_version(ws, "evo-0", "config.toml")["language"] == "toml"
        assert get_file_at_version(ws, "evo-0", "data.json")["language"] == "json"
        assert get_file_at_version(ws, "evo-0", "script.py")["language"] == "python"
        assert get_file_at_version(ws, "evo-0", "readme.md")["language"] == "markdown"
        assert get_file_at_version(ws, "evo-0", "notes.txt")["language"] == "text"


# ---------------------------------------------------------------------------
# get_file_diff_at_version tests
# ---------------------------------------------------------------------------


class TestGetFileDiffAtVersion:
    """Tests for get_file_diff_at_version."""

    def test_diff_at_evo0_shows_additions(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)

        result = get_file_diff_at_version(ws, "evo-0", "prompts/system.md")
        assert result["path"] == "prompts/system.md"
        assert result["from_version"] is None
        assert result["to_version"] == "evo-0"
        # At evo-0, entire content should appear as additions
        assert "+You are a helpful agent." in result["diff"]

    def test_diff_between_versions(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        _init_workspace(ws)
        _add_cycle(ws, 1, 0.5)

        result = get_file_diff_at_version(ws, "evo-1", "prompts/system.md")
        assert result["from_version"] == "evo-0"
        assert result["to_version"] == "evo-1"
        assert "+## Cycle 1 addition" in result["diff"]
        assert "+New instructions here." in result["diff"]


# ---------------------------------------------------------------------------
# Tree traversal test helper
# ---------------------------------------------------------------------------


def _collect_files(node: dict) -> list[dict]:
    """Recursively collect all file nodes from a tree."""
    files: list[dict] = []
    if node["type"] == "file":
        files.append(node)
    for child in node.get("children", []):
        files.extend(_collect_files(child))
    return files


# ---------------------------------------------------------------------------
# list_runs tests
# ---------------------------------------------------------------------------


class TestListRuns:
    def test_groups_run_scoped_tags(self, tmp_path: Path) -> None:
        """Run-scoped tags are grouped by run_id prefix."""
        root = tmp_path / "ws"
        _init_workspace(root)
        _git(root, "tag", "-a", "evo-20260404-0328-1", "-m", "cycle 1: score 0.250")
        _git(root, "tag", "-a", "evo-20260404-0328-2", "-m", "cycle 2: score 0.500")
        _git(root, "tag", "-a", "evo-20260404-1220-1", "-m", "cycle 1: score 0.125")

        runs = list_runs(root)
        assert len(runs) == 2
        # Most recent first
        assert runs[0]["run_id"] == "20260404-1220"
        assert runs[0]["cycles"] == 1
        assert runs[1]["run_id"] == "20260404-0328"
        assert runs[1]["cycles"] == 2

    def test_legacy_tags_form_single_run(self, tmp_path: Path) -> None:
        """Legacy evo-N tags are grouped as a single 'legacy' run."""
        root = tmp_path / "ws"
        _init_workspace(root)
        _git(root, "tag", "-a", "evo-1", "-m", "cycle 1: score 0.500")
        _git(root, "tag", "-a", "evo-2", "-m", "cycle 2: score 0.750")

        runs = list_runs(root)
        assert len(runs) == 1
        assert runs[0]["run_id"] == "legacy"
        assert runs[0]["cycles"] == 2

    def test_empty_workspace_returns_empty(self, tmp_path: Path) -> None:
        root = tmp_path / "ws"
        _init_workspace(root)
        runs = list_runs(root)
        assert runs == []

    def test_scores_parsed_from_tag_messages(self, tmp_path: Path) -> None:
        root = tmp_path / "ws"
        _init_workspace(root)
        _git(root, "tag", "-a", "evo-20260404-1220-1", "-m", "cycle 1: score 0.250")
        _git(root, "tag", "-a", "evo-20260404-1220-2", "-m", "cycle 2: score 0.750")

        runs = list_runs(root)
        assert runs[0]["best_score"] == 0.75
        assert runs[0]["final_score"] == 0.75
