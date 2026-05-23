# ABOUTME: Tests for the task loader in the aec-bench Python implementation.
# ABOUTME: Covers real task-instance shapes from the repository plus malformed synthetic cases.

from pathlib import Path

import pytest

from aec_bench.tasks.loader import LoadError, _load_tools, derive_task_id, load_task_definition

TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"


def test_loader_reads_real_mechanical_instance() -> None:
    instance_dir = TASKS_ROOT / "mechanical" / "heat-load" / "single-room-office-L2" / "adelaide-library-150m2"

    task = load_task_definition(instance_dir, TASKS_ROOT)

    assert task.task_id == "mechanical/heat-load/single-room-office-L2/adelaide-library-150m2"
    assert task.task_type == "heat-load"
    assert task.domain == "mechanical"
    assert task.category == "reasoning"
    assert task.timeout_seconds == 600


def test_loader_reads_real_top_level_electrical_task() -> None:
    task_dir = TASKS_ROOT / "electrical" / "voltage-drop"

    task = load_task_definition(task_dir, TASKS_ROOT)

    assert task.task_id == "electrical/voltage-drop"
    assert task.task_type == "voltage-drop"
    assert task.domain == "electrical"
    assert task.category == "reasoning"
    assert task.timeout_seconds == 600
    assert task.verifier.script == "tests/test.sh"
    assert task.verifier.expected_output_path == "/workspace/output.md"


def test_loader_reads_mechanical_single_room_office_instance() -> None:
    instance_dir = TASKS_ROOT / "mechanical" / "heat-load" / "single-room-office" / "brisbane-office-85m2"

    task = load_task_definition(instance_dir, TASKS_ROOT)

    assert task.task_id == "mechanical/heat-load/single-room-office/brisbane-office-85m2"
    assert task.task_type == "heat-load"
    assert task.domain == "mechanical"
    assert task.category == "reasoning"
    assert task.timeout_seconds == 600
    assert task.verifier.expected_output_path == "/workspace/output.md"


def test_derive_task_id_uses_relative_directory_path() -> None:
    instance_dir = TASKS_ROOT / "mechanical" / "heat-load" / "single-room-office" / "brisbane-office-85m2"

    expected = "mechanical/heat-load/single-room-office/brisbane-office-85m2"

    assert derive_task_id(instance_dir, TASKS_ROOT) == expected


def test_loader_rejects_missing_instruction_file(tmp_path: Path) -> None:
    instance_dir = tmp_path / "mechanical" / "demo-task" / "demo-instance"
    instance_dir.mkdir(parents=True)
    (instance_dir / "task.toml").write_text(
        'version = "1.0"\n\n[metadata]\ndifficulty = "easy"\ncategory = "drawing"\n',
        encoding="utf-8",
    )

    with pytest.raises(LoadError):
        load_task_definition(instance_dir, tmp_path)


def test_loader_reads_holdout_visibility_from_metadata(tmp_path: Path) -> None:
    instance_dir = tmp_path / "mechanical" / "heat-load" / "demo"
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text(
        "Write findings to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        '[agent]\ntimeout_sec = 600\n\n[metadata]\nvisibility = "holdout"\n',
        encoding="utf-8",
    )

    task = load_task_definition(instance_dir, tmp_path)

    assert task.visibility.value == "holdout"


def test_loader_uses_metadata_domain_for_generated_task_roots(tmp_path: Path) -> None:
    instance_dir = tmp_path / "generated" / "suite" / "structural" / "load-analysis" / "demo"
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text(
        "Write findings to /workspace/output.md.\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        "[agent]\n"
        "timeout_sec = 600\n\n"
        "[metadata]\n"
        'domain = "structural"\n'
        'category = "load-analysis"\n'
        'difficulty = "easy"\n',
        encoding="utf-8",
    )

    task = load_task_definition(instance_dir, tmp_path)

    assert task.domain == "structural"
    assert task.category == "load-analysis"


def test_loader_rejects_missing_task_toml(tmp_path: Path) -> None:
    instance_dir = tmp_path / "mechanical" / "heat-load" / "demo"
    instance_dir.mkdir(parents=True)
    (instance_dir / "instruction.md").write_text("Solve the task.\n", encoding="utf-8")

    with pytest.raises(LoadError, match="missing task.toml"):
        load_task_definition(instance_dir, tmp_path)


def test_loader_accepts_verify_py_as_verifier_script(tmp_path: Path) -> None:
    instance_dir = tmp_path / "electrical" / "voltage-drop" / "demo"
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text(
        "Write findings to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "verify.py").write_text("# verifier\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        "[agent]\ntimeout_sec = 600\n\n[metadata]\n",
        encoding="utf-8",
    )

    task = load_task_definition(instance_dir, tmp_path)

    assert task.verifier.script == "tests/verify.py"


def test_loader_prefers_test_sh_over_verify_py(tmp_path: Path) -> None:
    instance_dir = tmp_path / "electrical" / "voltage-drop" / "demo"
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text(
        "Write findings to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "tests" / "verify.py").write_text("# verifier\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        "[agent]\ntimeout_sec = 600\n\n[metadata]\n",
        encoding="utf-8",
    )

    task = load_task_definition(instance_dir, tmp_path)

    assert task.verifier.script == "tests/test.sh"


def test_loader_rejects_missing_verifier_script(tmp_path: Path) -> None:
    instance_dir = tmp_path / "mechanical" / "heat-load" / "demo"
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text(
        "Write findings to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (instance_dir / "task.toml").write_text(
        "[agent]\ntimeout_sec = 600\n\n[metadata]\n",
        encoding="utf-8",
    )

    with pytest.raises(LoadError, match="missing verifier script"):
        load_task_definition(instance_dir, tmp_path)


def test_loader_reads_tools_section_from_task_toml(tmp_path: Path) -> None:
    """Loader must populate environment.tools from the [tools] section in task.toml."""
    instance_dir = tmp_path / "ground" / "terzaghi" / "demo"
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text("Write findings to /workspace/output.md.\n", encoding="utf-8")
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        '[agent]\ntimeout_sec = 600\n\n[metadata]\n\n[tools]\nscripts = ["terzaghi_calc.py"]\n',
        encoding="utf-8",
    )

    task = load_task_definition(instance_dir, tmp_path)

    assert len(task.environment.tools) == 1
    assert task.environment.tools[0].name == "terzaghi-calc"
    assert task.environment.tools[0].source == "terzaghi_calc.py"


def test_loader_returns_empty_tools_when_no_tools_section(tmp_path: Path) -> None:
    """Loader must return empty tools list when task.toml has no [tools] section."""
    instance_dir = tmp_path / "ground" / "terzaghi" / "demo"
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text("Write findings to /workspace/output.md.\n", encoding="utf-8")
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text("[agent]\ntimeout_sec = 600\n\n[metadata]\n", encoding="utf-8")

    task = load_task_definition(instance_dir, tmp_path)

    assert task.environment.tools == []


def test_load_tools_old_scripts_format() -> None:
    """Existing [tools].scripts format still works."""
    raw = {"tools": {"scripts": ["calc.py", "search.py"]}}
    tools = _load_tools(raw)
    assert len(tools) == 2
    assert tools[0].name == "calc"
    assert tools[0].source == "calc.py"
    assert tools[0].returns_image is False


def test_load_tools_new_environment_tools_format() -> None:
    """New [[environment.tools]] format with returns_image."""
    raw = {
        "environment": {
            "tools": [
                {
                    "name": "create_chart",
                    "source": "tools/create_chart.py",
                    "description": "Generate chart",
                    "returns_image": True,
                },
                {
                    "name": "bash",
                    "source": "tools/bash.py",
                    "description": "Run bash",
                },
            ]
        }
    }
    tools = _load_tools(raw)
    assert len(tools) == 2
    assert tools[0].name == "create_chart"
    assert tools[0].returns_image is True
    assert tools[1].returns_image is False


def test_load_tools_new_format_takes_priority() -> None:
    """New format is preferred when both exist."""
    raw = {
        "tools": {"scripts": ["old.py"]},
        "environment": {"tools": [{"name": "new-tool", "source": "tools/new.py", "description": "New tool"}]},
    }
    tools = _load_tools(raw)
    assert len(tools) == 1
    assert tools[0].name == "new-tool"


def test_load_tools_empty_returns_empty() -> None:
    """No tools section returns empty list."""
    assert _load_tools({}) == []


def test_check_dockerfile_status_no_warnings_when_no_extensions(tmp_path: Path) -> None:
    """No warnings when task doesn't declare extensions."""
    from aec_bench.tasks.loader import _check_dockerfile_status

    raw = {"metadata": {"difficulty": "easy"}}
    assert _check_dockerfile_status(tmp_path, raw) == []


def test_check_dockerfile_status_warns_missing_dockerfile(tmp_path: Path) -> None:
    """Warn when extensions declared but no Dockerfile."""
    from aec_bench.tasks.loader import _check_dockerfile_status

    raw = {"environment": {"extensions": ["multimodal"]}}
    warnings = _check_dockerfile_status(tmp_path, raw)
    assert len(warnings) == 1
    assert "aec-bench generate dockerfiles" in warnings[0]


def test_check_dockerfile_status_warns_custom_dockerfile(tmp_path: Path) -> None:
    """Warn when extensions declared but Dockerfile is custom."""
    from aec_bench.tasks.loader import _check_dockerfile_status

    env_dir = tmp_path / "environment"
    env_dir.mkdir()
    (env_dir / "Dockerfile").write_text("FROM ubuntu:24.04\nRUN apt-get update")
    raw = {"environment": {"extensions": ["multimodal"]}}
    warnings = _check_dockerfile_status(tmp_path, raw)
    assert len(warnings) == 1
    assert "custom" in warnings[0]


def test_check_dockerfile_status_no_warning_autogenerated(tmp_path: Path) -> None:
    """No warning when Dockerfile is auto-generated."""
    from aec_bench.tasks.loader import _check_dockerfile_status

    env_dir = tmp_path / "environment"
    env_dir.mkdir()
    (env_dir / "Dockerfile").write_text("# ABOUTME: Auto-generated container\nFROM ubuntu:24.04")
    raw = {"environment": {"extensions": ["multimodal"]}}
    assert _check_dockerfile_status(tmp_path, raw) == []
