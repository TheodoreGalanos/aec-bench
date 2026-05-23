# ABOUTME: Tests for unified config resolution across project TOML, global JSON, and defaults.
# ABOUTME: Validates discovery, parsing, key mapping, layering priority, and path resolution.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.cli.commands.config import resolve_path
from aec_bench.config import find_project_config, load_config


def test_find_project_config_in_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "aec-bench.toml").write_text('[project]\nname = "test"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = find_project_config()
    assert result is not None
    assert result == tmp_path / "aec-bench.toml"


def test_find_project_config_in_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "aec-bench.toml").write_text('[project]\nname = "test"\n', encoding="utf-8")
    child = tmp_path / "subdir"
    child.mkdir()
    monkeypatch.chdir(child)

    result = find_project_config()
    assert result is not None
    assert result == tmp_path / "aec-bench.toml"


def test_find_project_config_returns_none_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = find_project_config()
    assert result is None


def test_load_config_reads_project_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    toml_content = """
[project]
name = "my-bench"

[paths]
tasks = "my-tasks"
ledger = "my-ledger"
"""
    (tmp_path / "aec-bench.toml").write_text(toml_content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = load_config()
    assert config.tasks_root == tmp_path / "my-tasks"
    assert config.ledger_root == tmp_path / "my-ledger"


def test_load_config_uses_defaults_without_project_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    config = load_config(project_root=tmp_path)
    assert config.tasks_root == tmp_path / "tasks"
    assert config.ledger_root == tmp_path / "artefacts" / "ledger"


def test_load_config_no_args_falls_back_to_package_root() -> None:
    """Existing behavior: load_config() with no args uses Path(__file__).parents[2] as root."""
    config = load_config()
    # Must resolve to the repo root (where pyproject.toml lives)
    assert (config.project_root / "pyproject.toml").exists()


def test_load_config_project_toml_overrides_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    toml_content = """
[paths]
tasks = "custom-tasks"

[compute]
backend = "docker"
"""
    (tmp_path / "aec-bench.toml").write_text(toml_content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = load_config()
    assert config.tasks_root == tmp_path / "custom-tasks"
    assert config.default_compute_backend == "docker"
    # Defaults still apply for unset values
    assert config.ledger_root == tmp_path / "artefacts" / "ledger"


def test_load_config_resolves_relative_paths_against_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    toml_content = '[paths]\ntasks = "data/tasks"\n'
    (tmp_path / "aec-bench.toml").write_text(toml_content, encoding="utf-8")
    child = tmp_path / "subdir"
    child.mkdir()
    monkeypatch.chdir(child)

    config = load_config()
    # Should resolve relative to project root (where aec-bench.toml is), not cwd
    assert config.tasks_root == tmp_path / "data" / "tasks"


def test_load_config_explicit_project_root_takes_priority(tmp_path: Path) -> None:
    config = load_config(project_root=tmp_path)
    assert config.project_root == tmp_path
    assert config.tasks_root == tmp_path / "tasks"


# ---------------------------------------------------------------------------
# resolve_path integration with unified config
# ---------------------------------------------------------------------------


def test_resolve_path_reads_project_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    toml_content = '[paths]\ntasks = "custom-tasks"\n'
    (tmp_path / "aec-bench.toml").write_text(toml_content, encoding="utf-8")
    (tmp_path / "custom-tasks").mkdir()
    monkeypatch.chdir(tmp_path)

    result = resolve_path("tasks_root")
    assert result == (tmp_path / "custom-tasks").resolve()


def test_resolve_path_cli_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    toml_content = '[paths]\ntasks = "toml-tasks"\n'
    (tmp_path / "aec-bench.toml").write_text(toml_content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = resolve_path("tasks_root", cli_override=str(tmp_path / "cli-tasks"))
    assert result == (tmp_path / "cli-tasks").resolve()
