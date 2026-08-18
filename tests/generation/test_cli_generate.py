# ABOUTME: Tests for the CLI generate subcommand group.
# ABOUTME: Covers list-templates, validate-template, and generate task commands via CliRunner.

import json
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()

TERZAGHI_DIR = str(
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "ground"
    / "terzaghi_bearing_capacity"
)


def test_list_templates_shows_builtin() -> None:
    """list-templates should include the terzaghi built-in template."""
    result = runner.invoke(app, ["generate", "list-templates"])
    assert result.exit_code == 0, result.output
    assert "terzaghi" in result.output


def test_list_templates_filters_by_discipline() -> None:
    """list-templates --discipline ground should still show terzaghi."""
    result = runner.invoke(app, ["generate", "list-templates", "--discipline", "ground"])
    assert result.exit_code == 0, result.output
    assert "terzaghi" in result.output


def test_list_templates_filters_out_other_discipline() -> None:
    """list-templates --discipline nonexistent should show no templates."""
    result = runner.invoke(app, ["generate", "list-templates", "--discipline", "nonexistent"])
    assert result.exit_code == 0, result.output
    # terzaghi is ground discipline, should not appear
    assert "terzaghi" not in result.output


def test_validate_template_passes_for_valid() -> None:
    """validate-template on the terzaghi template should succeed with exit code 0."""
    result = runner.invoke(app, ["generate", "validate-template", TERZAGHI_DIR])
    assert result.exit_code == 0, result.output
    out = result.output.lower()
    assert "valid" in out or "ok" in out or "0 error" in out


def test_validate_template_fails_for_invalid(tmp_path: Path) -> None:
    """validate-template on an empty dir should fail with non-zero exit code."""
    result = runner.invoke(app, ["generate", "validate-template", str(tmp_path)])
    assert result.exit_code != 0


def test_generate_task_creates_instances(tmp_path: Path) -> None:
    """generate task should create the requested number of instance directories."""
    result = runner.invoke(
        app,
        [
            "generate",
            "task",
            "terzaghi-bearing-capacity",
            "--instances",
            "2",
            "--seed",
            "42",
            "--output",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    # Find all task.toml files — each signals a fully scaffolded instance
    task_tomls = list(tmp_path.rglob("task.toml"))
    assert len(task_tomls) == 2


def test_generate_task_deterministic(tmp_path: Path) -> None:
    """The same template source and seed produce identical task content."""
    kwargs = [
        "generate",
        "task",
        "terzaghi-bearing-capacity",
        "--instances",
        "1",
        "--seed",
        "99",
        "--output",
    ]
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"

    result_a = runner.invoke(app, [*kwargs, str(out_a)])
    result_b = runner.invoke(app, [*kwargs, str(out_b)])

    assert result_a.exit_code == 0, result_a.output
    assert result_b.exit_code == 0, result_b.output

    # instruction.md is deterministic (derived from seed/params only)
    instr_a = next(out_a.rglob("instruction.md"))
    instr_b = next(out_b.rglob("instruction.md"))
    assert instr_a.read_text() == instr_b.read_text()

    toml_a = next(out_a.rglob("task.toml"))
    toml_b = next(out_b.rglob("task.toml"))
    assert toml_a.read_bytes() == toml_b.read_bytes()
    task_config = tomllib.loads(toml_a.read_text(encoding="utf-8"))
    assert "version" not in task_config
    assert "generation" not in task_config
    manifest = (out_a / "generation-manifest.json").read_text(encoding="utf-8")
    assert "template_source_sha256" not in manifest


def test_generate_task_dry_run_creates_nothing(tmp_path: Path) -> None:
    """--dry-run should print a summary but write no files."""
    result = runner.invoke(
        app,
        [
            "generate",
            "task",
            "terzaghi-bearing-capacity",
            "--instances",
            "2",
            "--seed",
            "42",
            "--output",
            str(tmp_path),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert list(tmp_path.iterdir()) == []


def test_generate_task_requires_name_or_template() -> None:
    """generate task with no name and no --template should exit with error."""
    result = runner.invoke(app, ["generate", "task"])
    assert result.exit_code != 0


def test_generate_task_name_not_found() -> None:
    """generate task with an unknown template name should exit with error."""
    result = runner.invoke(
        app,
        ["generate", "task", "nonexistent-template", "--output", "/tmp/nowhere"],
    )
    assert result.exit_code == 1


def test_generate_task_with_difficulty_filter(tmp_path: Path) -> None:
    """generate task --difficulty easy should produce instances with easy difficulty."""
    result = runner.invoke(
        app,
        [
            "generate",
            "task",
            "terzaghi-bearing-capacity",
            "--instances",
            "2",
            "--seed",
            "42",
            "--difficulty",
            "easy",
            "--output",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    task_tomls = list(tmp_path.rglob("task.toml"))
    assert len(task_tomls) == 2
    for toml in task_tomls:
        content = toml.read_text()
        assert 'difficulty = "easy"' in content


def test_generate_task_from_local_template(tmp_path: Path) -> None:
    """generate task --template <path> should work without a named template."""
    result = runner.invoke(
        app,
        [
            "generate",
            "task",
            "--template",
            TERZAGHI_DIR,
            "--instances",
            "1",
            "--seed",
            "10",
            "--output",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    task_tomls = list(tmp_path.rglob("task.toml"))
    assert len(task_tomls) == 1


def test_generate_task_keeps_unexpected_template_import_errors_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_import_template(_template_dir: Path) -> None:
        raise ModuleNotFoundError("missing_template_dependency")

    monkeypatch.setattr("aec_bench.cli.commands.generate.load_template", fail_to_import_template)

    result = runner.invoke(app, ["generate", "task", "--template", str(tmp_path)])

    assert isinstance(result.exception, ModuleNotFoundError)
    assert str(result.exception) == "missing_template_dependency"


def test_generate_task_supports_explicit_visibility_and_start_index(tmp_path: Path) -> None:
    """The CLI must generate auditable split packages without reusing low task indices."""
    result = runner.invoke(
        app,
        [
            "generate",
            "task",
            "terzaghi-bearing-capacity",
            "--instances",
            "2",
            "--difficulty",
            "easy",
            "--seed",
            "901",
            "--start-index",
            "10",
            "--visibility",
            "holdout",
            "--output",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payloads = []
    for task_toml in sorted(tmp_path.rglob("task.toml")):
        with open(task_toml, "rb") as fh:
            payloads.append(tomllib.load(fh))
    assert {payload["metadata"]["visibility"] for payload in payloads} == {"holdout"}
    manifest = json.loads((tmp_path / "generation-manifest.json").read_text(encoding="utf-8"))
    assert [instance["instance_index"] for instance in manifest["instances"]] == [10, 11]


def test_generate_task_rejects_a_negative_start_index(tmp_path: Path) -> None:
    """Negative task indices cannot participate in a frozen generation identity."""
    result = runner.invoke(
        app,
        [
            "generate",
            "task",
            "terzaghi-bearing-capacity",
            "--instances",
            "1",
            "--start-index",
            "-1",
            "--output",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert list(tmp_path.rglob("task.toml")) == []


def test_generate_task_refuses_to_overwrite_an_existing_instance(tmp_path: Path) -> None:
    """Repeated CLI generation must preserve the first frozen task package."""
    arguments = [
        "generate",
        "task",
        "terzaghi-bearing-capacity",
        "--instances",
        "1",
        "--difficulty",
        "easy",
        "--seed",
        "901",
        "--start-index",
        "10",
        "--output",
        str(tmp_path),
    ]
    first_result = runner.invoke(app, arguments)
    assert first_result.exit_code == 0, first_result.output
    task_toml = next(tmp_path.rglob("task.toml"))
    original = task_toml.read_bytes()

    second_result = runner.invoke(app, arguments)

    assert second_result.exit_code != 0
    assert task_toml.read_bytes() == original
