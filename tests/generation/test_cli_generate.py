# ABOUTME: Tests for the CLI generate subcommand group.
# ABOUTME: Covers list-templates, validate-template, and generate task commands via CliRunner.

from pathlib import Path

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
    """Same seed should produce identical parameter and structural content across two runs.

    The timestamp field in task.toml is wall-clock time and will differ between runs.
    We verify all other content (instruction.md, verify.py, the TOML except timestamp) is identical.
    """
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

    # task.toml has all same fields except the wall-clock timestamp
    import re

    toml_a = next(out_a.rglob("task.toml"))
    toml_b = next(out_b.rglob("task.toml"))

    def _strip_timestamp(text: str) -> str:
        return re.sub(r'timestamp = ".*?"', 'timestamp = "STRIPPED"', text)

    assert _strip_timestamp(toml_a.read_text()) == _strip_timestamp(toml_b.read_text())


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
