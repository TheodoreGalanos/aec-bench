# ABOUTME: Tests for the task validation engine in aec-bench.
# ABOUTME: Covers structure, schema, instruction, promotion, and verifier fixture checks.

from pathlib import Path

from aec_bench.tasks.validator import (
    Severity,
    ValidationFinding,
    ValidationReport,
    validate_task,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_dir(root: Path, *, difficulty: str = "easy") -> Path:
    """Create a minimal valid task directory."""
    task_dir = root / "electrical" / "my-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n[metadata]\n'
        f'difficulty = "{difficulty}"\n'
        'category = "reasoning"\n'
        'tags = ["electrical"]\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n"
    )
    (task_dir / "instruction.md").write_text(
        "Calculate the voltage drop and write results to `/workspace/output.md`.\n"
    )
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "verify.py").write_text("# verifier\n")
    (tests_dir / "test.sh").write_text("#!/bin/bash\npython3 /tests/verify.py\n")
    env_dir = task_dir / "environment"
    env_dir.mkdir()
    (env_dir / "Dockerfile").write_text("FROM python:3.12\n")
    return task_dir


# ---------------------------------------------------------------------------
# ValidationReport / ValidationFinding data model tests
# ---------------------------------------------------------------------------


def test_report_passes_with_no_findings() -> None:
    report = ValidationReport(task_id="electrical/my-task", findings=[])
    assert report.passed is True
    assert report.error_count == 0
    assert report.warning_count == 0


def test_report_fails_when_error_finding_present() -> None:
    finding = ValidationFinding(
        severity=Severity.ERROR,
        check="structure",
        file="task.toml",
        message="task.toml is missing",
        fix_hint="Create a task.toml file.",
    )
    report = ValidationReport(task_id="electrical/my-task", findings=[finding])
    assert report.passed is False
    assert report.error_count == 1
    assert report.warning_count == 0


def test_report_passes_with_only_warning_findings() -> None:
    finding = ValidationFinding(
        severity=Severity.WARNING,
        check="promotion",
        file="environment/Dockerfile",
        message="Dockerfile missing",
        fix_hint="Add a Dockerfile.",
    )
    report = ValidationReport(task_id="electrical/my-task", findings=[finding])
    assert report.passed is True
    assert report.warning_count == 1
    assert report.error_count == 0


def test_finding_to_dict_contains_all_fields() -> None:
    finding = ValidationFinding(
        severity=Severity.ERROR,
        check="schema",
        file="task.toml",
        message="invalid difficulty",
        fix_hint="Use easy, medium, or hard.",
    )
    d = finding.to_dict()
    assert d["severity"] == "error"
    assert d["check"] == "schema"
    assert d["file"] == "task.toml"
    assert d["message"] == "invalid difficulty"
    assert d["fix_hint"] == "Use easy, medium, or hard."


def test_report_to_dict_structure() -> None:
    report = ValidationReport(task_id="electrical/my-task", findings=[])
    d = report.to_dict()
    assert d["task_id"] == "electrical/my-task"
    assert d["passed"] is True
    assert d["error_count"] == 0
    assert d["warning_count"] == 0
    assert d["findings"] == []


# ---------------------------------------------------------------------------
# validate_task — happy path
# ---------------------------------------------------------------------------


def test_valid_task_directory_produces_no_errors(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)

    report = validate_task(task_dir, tasks_root=tasks_root)

    assert report.passed is True
    assert report.error_count == 0


# ---------------------------------------------------------------------------
# Structure checks
# ---------------------------------------------------------------------------


def test_missing_task_toml_produces_structure_error(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    (task_dir / "task.toml").unlink()

    report = validate_task(task_dir, tasks_root=tasks_root)

    errors = [f for f in report.findings if f.severity == Severity.ERROR and f.check == "structure"]
    assert len(errors) >= 1
    assert any("task.toml" in f.file for f in errors)


def test_missing_instruction_md_produces_structure_error(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    (task_dir / "instruction.md").unlink()

    report = validate_task(task_dir, tasks_root=tasks_root)

    errors = [f for f in report.findings if f.severity == Severity.ERROR and f.check == "structure"]
    assert any("instruction.md" in f.file for f in errors)


def test_empty_instruction_produces_structure_error(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    (task_dir / "instruction.md").write_text("")

    report = validate_task(task_dir, tasks_root=tasks_root)

    errors = [f for f in report.findings if f.severity == Severity.ERROR and f.check == "structure"]
    assert any("instruction.md" in f.file for f in errors)


def test_missing_verifier_produces_structure_error(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    (task_dir / "tests" / "verify.py").unlink()
    (task_dir / "tests" / "test.sh").unlink()

    report = validate_task(task_dir, tasks_root=tasks_root)

    errors = [f for f in report.findings if f.severity == Severity.ERROR and f.check == "structure"]
    assert len(errors) >= 1


def test_missing_test_sh_with_verify_py_produces_warning(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    (task_dir / "tests" / "test.sh").unlink()

    report = validate_task(task_dir, tasks_root=tasks_root)

    warnings = [f for f in report.findings if f.severity == Severity.WARNING and f.check == "structure"]
    assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------


def test_invalid_difficulty_produces_schema_error(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root, difficulty="extreme")

    report = validate_task(task_dir, tasks_root=tasks_root)

    errors = [f for f in report.findings if f.severity == Severity.ERROR and f.check == "schema"]
    assert any("difficulty" in f.message for f in errors)


def test_valid_difficulty_values_produce_no_schema_error(tmp_path: Path) -> None:
    for difficulty in ("easy", "medium", "hard"):
        tasks_root = tmp_path / f"tasks_{difficulty}"
        tasks_root.mkdir()
        task_dir = _make_task_dir(tasks_root, difficulty=difficulty)

        report = validate_task(task_dir, tasks_root=tasks_root)

        errors = [f for f in report.findings if f.severity == Severity.ERROR and f.check == "schema"]
        assert errors == [], f"Unexpected schema errors for difficulty={difficulty}: {errors}"


def test_missing_tags_produces_schema_warning(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    # Rewrite task.toml without tags
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n[metadata]\n'
        'difficulty = "easy"\n'
        'category = "reasoning"\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n"
    )

    report = validate_task(task_dir, tasks_root=tasks_root)

    warnings = [f for f in report.findings if f.severity == Severity.WARNING and f.check == "schema"]
    assert len(warnings) >= 1


def test_missing_category_produces_schema_info(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    # Rewrite task.toml without category
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n[metadata]\n'
        'difficulty = "easy"\n'
        'tags = ["electrical"]\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n"
    )

    report = validate_task(task_dir, tasks_root=tasks_root)

    infos = [f for f in report.findings if f.severity == Severity.INFO and f.check == "schema"]
    assert len(infos) >= 1


# ---------------------------------------------------------------------------
# Instruction checks
# ---------------------------------------------------------------------------


def test_unresolved_placeholder_produces_instruction_error(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    (task_dir / "instruction.md").write_text(
        "Calculate voltage drop for {{ conductor_material }} and write to /workspace/output.md.\n"
    )

    report = validate_task(task_dir, tasks_root=tasks_root)

    errors = [f for f in report.findings if f.severity == Severity.ERROR and f.check == "instruction"]
    assert len(errors) >= 1


def test_missing_workspace_reference_produces_instruction_warning(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    (task_dir / "instruction.md").write_text("Calculate the voltage drop and report verbally.\n")

    report = validate_task(task_dir, tasks_root=tasks_root)

    warnings = [f for f in report.findings if f.severity == Severity.WARNING and f.check == "instruction"]
    assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# Promotion checks
# ---------------------------------------------------------------------------


def test_missing_dockerfile_produces_promotion_warning(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    task_dir = _make_task_dir(tasks_root)
    (task_dir / "environment" / "Dockerfile").unlink()

    report = validate_task(task_dir, tasks_root=tasks_root)

    warnings = [f for f in report.findings if f.severity == Severity.WARNING and f.check == "promotion"]
    assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# Invariant: every non-INFO finding must have a fix_hint
# ---------------------------------------------------------------------------


def test_all_non_info_findings_have_fix_hints(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    # Create a task with multiple problems to exercise multiple checks
    task_dir = tasks_root / "electrical" / "broken-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n[metadata]\n'
        'difficulty = "extreme"\n'
        "tags = []\n\n"
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n"
    )
    (task_dir / "instruction.md").write_text("Calculate {{ something }} and write to /workspace/output.md.\n")
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "verify.py").write_text("# verifier\n")

    report = validate_task(task_dir, tasks_root=tasks_root)

    non_info = [f for f in report.findings if f.severity != Severity.INFO]
    for finding in non_info:
        assert finding.fix_hint, f"Finding {finding.check}/{finding.message} has empty fix_hint"
