# ABOUTME: Tests for the aec-bench init command: scaffolding, config writing, and skill copying.
# ABOUTME: Validates directory creation, config content, re-run safety, and update-skills behavior.

from __future__ import annotations

from pathlib import Path

from aec_bench.cli.commands.init import init_project
from aec_bench.init.scaffold import (
    _PACKAGED_SKILLS,
    copy_skills,
    create_scaffold,
    write_gitignore,
    write_project_config,
    write_suite_toml,
)


def _packaged_skill_tree(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for skill_name in _PACKAGED_SKILLS
        for path in (root / skill_name).rglob("*")
        if path.is_file()
    }


def test_create_scaffold_creates_directories(tmp_path: Path) -> None:
    result = create_scaffold(tmp_path)

    assert (tmp_path / "tasks").is_dir()
    assert (tmp_path / "seeds").is_dir()
    assert (tmp_path / "artefacts" / "ledger").is_dir()
    assert (tmp_path / "artefacts" / "datasets").is_dir()
    assert result.created


def test_create_scaffold_skips_existing_dirs(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "seeds").mkdir()

    result = create_scaffold(tmp_path)
    assert result.created
    assert (tmp_path / "artefacts" / "ledger").is_dir()
    assert (tmp_path / "artefacts" / "datasets").is_dir()


def test_write_project_config_creates_toml(tmp_path: Path) -> None:
    write_project_config(tmp_path, project_name="my-bench")

    config_path = tmp_path / "aec-bench.toml"
    assert config_path.exists()
    content = config_path.read_text(encoding="utf-8")
    assert "my-bench" in content
    assert "[paths]" in content
    assert 'datasets = "artefacts/datasets"' in content
    assert "[compute]" in content


def test_write_project_config_does_not_overwrite(tmp_path: Path) -> None:
    config_path = tmp_path / "aec-bench.toml"
    config_path.write_text("existing", encoding="utf-8")

    write_project_config(tmp_path, project_name="new")
    assert config_path.read_text(encoding="utf-8") == "existing"


def test_write_project_config_overwrites_with_force(tmp_path: Path) -> None:
    config_path = tmp_path / "aec-bench.toml"
    config_path.write_text("existing", encoding="utf-8")

    write_project_config(tmp_path, project_name="new", force=True)
    assert "new" in config_path.read_text(encoding="utf-8")


def test_write_suite_toml_creates_file(tmp_path: Path) -> None:
    write_suite_toml(tmp_path)

    suite_path = tmp_path / "suite.toml"
    assert suite_path.exists()
    content = suite_path.read_text(encoding="utf-8")
    assert "terzaghi-bearing-capacity" in content
    assert "dataset" in content


def test_write_gitignore_creates_file(tmp_path: Path) -> None:
    write_gitignore(tmp_path)

    gitignore_path = tmp_path / ".gitignore"
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")
    assert "artefacts/" in content
    assert "jobs/" in content


def test_copy_skills_creates_skill_dirs(tmp_path: Path) -> None:
    copy_skills(tmp_path)

    source_root = Path(__file__).resolve().parents[2] / "src" / "aec_bench" / "init" / "skill_data"
    expected_tree = _packaged_skill_tree(source_root)
    installed_trees: list[dict[Path, bytes]] = []
    for relative_root in (Path(".claude/skills"), Path(".agents/skills")):
        skills_dir = tmp_path / relative_root
        assert skills_dir.is_dir()
        assert {path.name for path in skills_dir.iterdir() if path.is_dir()} == set(_PACKAGED_SKILLS)
        assert all((skills_dir / skill_name / "SKILL.md").is_file() for skill_name in _PACKAGED_SKILLS)
        assert (skills_dir / "meta-harness" / "references" / "experiment-workflows.md").exists()
        assert (skills_dir / "meta-harness" / "examples" / "lifecycle-ablation.yaml").exists()
        installed_trees.append(_packaged_skill_tree(skills_dir))
    assert installed_trees == [expected_tree, expected_tree]


def test_copy_skills_preserves_skill_directories_with_other_names(tmp_path: Path) -> None:
    user_skills = [
        tmp_path / relative_root / "my-custom-skill"
        for relative_root in (Path(".claude/skills"), Path(".agents/skills"))
    ]
    for user_skill in user_skills:
        user_skill.mkdir(parents=True)
        (user_skill / "SKILL.md").write_text("custom", encoding="utf-8")

    copy_skills(tmp_path)

    for user_skill in user_skills:
        assert (user_skill / "SKILL.md").read_text(encoding="utf-8") == "custom"
        assert (user_skill.parent / "add-task" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# init_project() integration tests
# ---------------------------------------------------------------------------


def test_init_project_creates_full_scaffold(tmp_path: Path) -> None:
    result = init_project(target=tmp_path, generate_example=False)

    assert result.created
    assert (tmp_path / "aec-bench.toml").exists()
    assert (tmp_path / "suite.toml").exists()
    assert (tmp_path / ".gitignore").exists()
    assert (tmp_path / "tasks").is_dir()
    assert (tmp_path / "seeds").is_dir()
    assert (tmp_path / ".claude" / "skills" / "add-task" / "SKILL.md").exists()
    assert (tmp_path / ".agents" / "skills" / "add-task" / "SKILL.md").exists()
    assert "Copied skills to .claude/skills/ and .agents/skills/" in result.messages


def test_init_project_detects_existing(tmp_path: Path) -> None:
    (tmp_path / "aec-bench.toml").write_text("[project]\n", encoding="utf-8")

    result = init_project(target=tmp_path)
    assert not result.created
    assert "already initialised" in result.messages[0].lower()


def test_init_project_force_recreates_config(tmp_path: Path) -> None:
    (tmp_path / "aec-bench.toml").write_text("[project]\n", encoding="utf-8")

    result = init_project(target=tmp_path, force=True, generate_example=False)
    assert result.created


def test_init_project_update_skills_only(tmp_path: Path) -> None:
    # First init
    init_project(target=tmp_path, generate_example=False)
    # Modify both installed copies of one packaged skill.
    skill_paths = [
        tmp_path / relative_root / "add-task" / "SKILL.md"
        for relative_root in (Path(".claude/skills"), Path(".agents/skills"))
    ]
    for skill_path in skill_paths:
        skill_path.write_text("modified", encoding="utf-8")

    # Update skills
    result = init_project(target=tmp_path, update_skills=True)
    assert result.created
    assert all(skill_path.read_text(encoding="utf-8") != "modified" for skill_path in skill_paths)


def test_init_project_update_skills_adds_codex_skills_to_existing_project(tmp_path: Path) -> None:
    (tmp_path / "aec-bench.toml").write_text("[project]\n", encoding="utf-8")
    old_claude_skill = tmp_path / ".claude" / "skills" / "add-task" / "SKILL.md"
    old_claude_skill.parent.mkdir(parents=True)
    old_claude_skill.write_text("old packaged copy", encoding="utf-8")

    result = init_project(target=tmp_path, update_skills=True)

    assert result.created
    assert old_claude_skill.read_text(encoding="utf-8") != "old packaged copy"
    assert (tmp_path / ".agents" / "skills" / "add-task" / "SKILL.md").is_file()
    assert result.messages == ("Skills updated in .claude/skills/ and .agents/skills/.",)
