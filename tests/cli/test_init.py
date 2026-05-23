# ABOUTME: Tests for the aec-bench init command: scaffolding, config writing, and skill copying.
# ABOUTME: Validates directory creation, config content, re-run safety, and update-skills behavior.

from __future__ import annotations

from pathlib import Path

from aec_bench.cli.commands.init import init_project
from aec_bench.init.scaffold import (
    copy_agents,
    copy_skills,
    create_scaffold,
    write_gitignore,
    write_project_config,
    write_suite_toml,
)


def test_create_scaffold_creates_directories(tmp_path: Path) -> None:
    result = create_scaffold(tmp_path)

    assert (tmp_path / "tasks").is_dir()
    assert (tmp_path / "seeds").is_dir()
    assert (tmp_path / "artefacts" / "ledger").is_dir()
    assert result.created


def test_create_scaffold_skips_existing_dirs(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "seeds").mkdir()

    result = create_scaffold(tmp_path)
    assert result.created
    assert (tmp_path / "artefacts" / "ledger").is_dir()


def test_write_project_config_creates_toml(tmp_path: Path) -> None:
    write_project_config(tmp_path, project_name="my-bench")

    config_path = tmp_path / "aec-bench.toml"
    assert config_path.exists()
    content = config_path.read_text(encoding="utf-8")
    assert "my-bench" in content
    assert "[paths]" in content
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

    skills_dir = tmp_path / ".claude" / "skills"
    assert skills_dir.is_dir()
    assert (skills_dir / "add-task" / "SKILL.md").exists()
    assert (skills_dir / "create-template" / "SKILL.md").exists()
    assert (skills_dir / "hardening-pass" / "SKILL.md").exists()
    assert (skills_dir / "domain-check" / "SKILL.md").exists()


def test_copy_skills_preserves_user_added_skills(tmp_path: Path) -> None:
    user_skill = tmp_path / ".claude" / "skills" / "my-custom-skill"
    user_skill.mkdir(parents=True)
    (user_skill / "SKILL.md").write_text("custom", encoding="utf-8")

    copy_skills(tmp_path)

    assert (user_skill / "SKILL.md").read_text(encoding="utf-8") == "custom"
    assert (tmp_path / ".claude" / "skills" / "add-task" / "SKILL.md").exists()


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
    # Modify a skill
    skill_path = tmp_path / ".claude" / "skills" / "add-task" / "SKILL.md"
    skill_path.write_text("modified", encoding="utf-8")

    # Update skills
    result = init_project(target=tmp_path, update_skills=True)
    assert result.created
    assert skill_path.read_text(encoding="utf-8") != "modified"


# ---------------------------------------------------------------------------
# copy_agents() tests
# ---------------------------------------------------------------------------


def test_copy_agents_creates_agent_files(tmp_path: Path) -> None:
    copy_agents(tmp_path)

    agents_dir = tmp_path / "agents"
    assert agents_dir.is_dir()
    assert (agents_dir / "tool_loop_anthropic.py").is_file()
    assert (agents_dir / "pydantic_ai_agent.py").is_file()
    assert (agents_dir / "script_anthropic.py").is_file()


def test_copy_agents_writes_init_file(tmp_path: Path) -> None:
    copy_agents(tmp_path)

    init_path = tmp_path / "agents" / "__init__.py"
    assert init_path.is_file()
    content = init_path.read_text(encoding="utf-8")
    assert "ABOUTME" in content


def test_copy_agents_does_not_overwrite_existing_init(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    init_path = agents_dir / "__init__.py"
    init_path.write_text("# custom init\n", encoding="utf-8")

    copy_agents(tmp_path)

    assert init_path.read_text(encoding="utf-8") == "# custom init\n"


def test_copy_agents_preserves_user_added_agents(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    user_agent = agents_dir / "my_custom_agent.py"
    user_agent.write_text("# custom agent\n", encoding="utf-8")

    copy_agents(tmp_path)

    assert user_agent.read_text(encoding="utf-8") == "# custom agent\n"
    assert (agents_dir / "tool_loop_anthropic.py").is_file()
