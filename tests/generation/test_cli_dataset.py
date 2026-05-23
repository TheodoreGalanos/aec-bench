# ABOUTME: Integration tests for the 'generate suite' CLI command.
# ABOUTME: Tests dry-run, validate-only, full generation, seed override, and error handling.

import json
import textwrap
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()

MINIMAL_SUITE_TOML = textwrap.dedent("""\
    name = "cli-test-suite"
    seed = 42

    [coverage]
    difficulties = {easy = 0.5, medium = 0.5}
    min_tasks_per_discipline = 1

    [templates]
    include = ["ground/*"]

    [visibility]
    mix = {all_given = 1.0}

    [tool_mode]
    mix = {with_tool = 1.0}

    [instances]
    per_task = 2
    total_max = 100

    [output]
    dir = "./tasks/"
""")


def _write_suite_toml(tmp_path: Path, content: str = MINIMAL_SUITE_TOML) -> Path:
    """Write a suite.toml and return its path."""
    config_file = tmp_path / "suite.toml"
    config_file.write_text(content)
    return config_file


def test_suite_dry_run_creates_no_files(tmp_path: Path) -> None:
    """--dry-run should print a plan but write nothing."""
    config_file = _write_suite_toml(tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    toml_content = MINIMAL_SUITE_TOML.replace('dir = "./tasks/"', f'dir = "{output_dir}"')
    config_file.write_text(toml_content)

    result = runner.invoke(app, ["generate", "suite", "--config", str(config_file), "--dry-run"])
    assert result.exit_code == 0, result.output
    # No dataset.json should exist
    assert not (output_dir / "dataset.json").exists()


def test_suite_validate_only(tmp_path: Path) -> None:
    """--validate-only should check templates and exit without generating."""
    config_file = _write_suite_toml(tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    toml_content = MINIMAL_SUITE_TOML.replace('dir = "./tasks/"', f'dir = "{output_dir}"')
    config_file.write_text(toml_content)

    result = runner.invoke(app, ["generate", "suite", "--config", str(config_file), "--validate-only"])
    assert result.exit_code == 0, result.output
    assert not (output_dir / "dataset.json").exists()


def test_suite_full_run(tmp_path: Path) -> None:
    """Full dataset generation should create instance dirs and dataset.json."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    toml_content = MINIMAL_SUITE_TOML.replace('dir = "./tasks/"', f'dir = "{output_dir}"')
    config_file = _write_suite_toml(tmp_path, toml_content)

    result = runner.invoke(app, ["generate", "suite", "--config", str(config_file)])
    assert result.exit_code == 0, result.output

    # dataset.json should exist
    dataset_json = output_dir / "dataset.json"
    assert dataset_json.exists()

    data = json.loads(dataset_json.read_text())
    assert data["name"] == "cli-test-suite"
    assert len(data["instances"]) >= 2  # per_task = 2 × number of matched templates


def test_suite_seed_override(tmp_path: Path) -> None:
    """--seed should override the config seed, producing different instances."""
    output_a = tmp_path / "run_a"
    output_b = tmp_path / "run_b"
    output_a.mkdir()
    output_b.mkdir()

    dir_a = tmp_path / "a"
    dir_a.mkdir()
    toml_a = MINIMAL_SUITE_TOML.replace('dir = "./tasks/"', f'dir = "{output_a}"')
    config_a = dir_a / "suite.toml"
    config_a.write_text(toml_a)

    dir_b = tmp_path / "b"
    dir_b.mkdir()
    toml_b = MINIMAL_SUITE_TOML.replace('dir = "./tasks/"', f'dir = "{output_b}"')
    config_b = dir_b / "suite.toml"
    config_b.write_text(toml_b)

    result_a = runner.invoke(app, ["generate", "suite", "--config", str(config_a)])
    result_b = runner.invoke(app, ["generate", "suite", "--config", str(config_b), "--seed", "999"])

    assert result_a.exit_code == 0, result_a.output
    assert result_b.exit_code == 0, result_b.output

    data_a = json.loads((output_a / "dataset.json").read_text())
    data_b = json.loads((output_b / "dataset.json").read_text())

    assert data_a["seed"] != data_b["seed"]


def test_suite_invalid_config(tmp_path: Path) -> None:
    """Invalid config path should produce an error."""
    result = runner.invoke(app, ["generate", "suite", "--config", str(tmp_path / "nonexistent.toml")])
    assert result.exit_code != 0


def test_generate_dataset_alias_still_works(tmp_path: Path) -> None:
    """Deprecated generate dataset alias should remain available during transition."""
    config_file = _write_suite_toml(tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    toml_content = MINIMAL_SUITE_TOML.replace('dir = "./tasks/"', f'dir = "{output_dir}"')
    config_file.write_text(toml_content)

    result = runner.invoke(app, ["generate", "dataset", "--config", str(config_file), "--dry-run"])

    assert result.exit_code == 0, result.output
