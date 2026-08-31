# ABOUTME: Tests for the TUI library screen: data loading, tree structure, and detail rendering.
# ABOUTME: Validates seed loading, template discovery, instance detection, and summary statistics.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.app import App

from aec_bench.tasks.library_export import load_seeds
from aec_bench.templates.registry import discover_templates
from aec_bench.tui.screens.library import (
    LibraryScreen,
    build_summary,
    load_library_instances,
    render_bar_chart,
    render_category_detail,
    render_discipline_detail,
    render_instance_detail,
    render_seed_detail,
    render_template_detail,
)


def _load_seeds(tasks_root: Path):
    seeds, diagnostics = load_seeds(tasks_root)
    assert diagnostics == []
    return seeds


def _load_templates(templates_root: Path):
    templates, diagnostics = discover_templates(user_dirs=[templates_root], include_builtin=False)
    assert diagnostics == []
    return templates


def _write_seed(base: Path, discipline: str, category: str, task_id: str, complexity: str = "low") -> Path:
    """Helper to create a seed file on disk."""
    seed_dir = base / discipline / category / task_id
    seed_dir.mkdir(parents=True, exist_ok=True)
    seed = {
        "status": "proposed",
        "seed_origin": "ngnbench",
        "source": {
            "discipline": discipline,
            "category_id": category,
            "task_id": task_id,
            "task_name": task_id.replace("-", " ").title(),
            "description": f"Test seed for {task_id}",
            "complexity": complexity,
            "standards": ["AS1234"],
            "inputs": ["input_a", "input_b"],
            "outputs": ["output_a"],
        },
    }
    path = seed_dir / "source_task.json"
    path.write_text(json.dumps(seed), encoding="utf-8")
    return path


def _write_template(base: Path, discipline: str, task_id: str) -> Path:
    """Helper to create a minimal template directory."""
    template_dir = base / discipline / task_id.replace("-", "_")
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "__init__.py").write_text("# ABOUTME: test\n# ABOUTME: test\n")
    (template_dir / "engine.py").write_text(
        "# ABOUTME: test\n# ABOUTME: test\ndef compute(*, x: float) -> dict[str, float]:\n    return {'y': x}\n"
    )
    (template_dir / "instruction.md").write_text("Compute y.\n")
    lines = [
        "[meta]",
        f'name = "{task_id}"',
        f'discipline = "{discipline}"',
        'description = "test"',
        'category = "test"',
        'tool_mode = "no-tool"',
        "",
        "[params.x]",
        'type = "float"',
        'description = "input"',
        "min = 0",
        "max = 10",
        "",
        "[outputs.y]",
        'description = "result"',
        "tolerance = 0.03",
    ]
    (template_dir / "params.toml").write_text("\n".join(lines), encoding="utf-8")
    return template_dir


def _write_instance(base: Path, discipline: str, category: str, task: str, instance: str) -> Path:
    """Helper to create a minimal task instance."""
    inst_dir = base / discipline / category / task / instance
    inst_dir.mkdir(parents=True, exist_ok=True)
    task_key = inst_dir.relative_to(base).as_posix().lower()
    (inst_dir / "task.toml").write_text(
        '[identity]\nid = "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa"\n'
        f'key = "{task_key}"\nversion = 1\n\n'
        '[metadata]\ndifficulty = "medium"\nlifecycle = "active"\nvisibility = "public"\ntags = ["test"]\n',
        encoding="utf-8",
    )
    (inst_dir / "instruction.md").write_text("Do the task.", encoding="utf-8")
    tests_dir = inst_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return inst_dir


def test_load_seeds_finds_all_seeds(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_seed(tasks_root, "civil", "drainage", "pipe-sizing")
    _write_seed(tasks_root, "civil", "drainage", "culvert-design", complexity="medium")
    _write_seed(tasks_root, "electrical", "cable-sizing", "cable-ampacity")

    seeds = _load_seeds(tasks_root)
    assert len(seeds) == 3
    disciplines = {s.discipline for s in seeds}
    assert disciplines == {"civil", "electrical"}


def test_load_seeds_extracts_fields(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_seed(tasks_root, "ground", "foundations", "terzaghi", complexity="medium")

    seeds = _load_seeds(tasks_root)
    assert len(seeds) == 1
    seed = seeds[0]
    assert seed.discipline == "ground"
    assert seed.category == "foundations"
    assert seed.task_id == "terzaghi"
    assert seed.complexity == "medium"
    assert seed.standards == ("AS1234",)
    assert len(seed.inputs) == 2
    assert len(seed.outputs) == 1


def test_discover_templates_finds_templates(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    _write_template(templates_root, "ground", "terzaghi-bearing")

    templates = _load_templates(templates_root)
    assert len(templates) == 1
    assert templates[0].discipline == "ground"
    assert templates[0].task_id == "terzaghi-bearing"


def test_load_library_instances_finds_instances(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_instance(tasks_root, "mechanical", "heat-load", "audit-office", "brisbane-8rm")
    _write_instance(tasks_root, "mechanical", "heat-load", "audit-office", "sydney-8rm")

    instances = load_library_instances(tasks_root)
    assert len(instances) == 2
    assert all(i.discipline == "mechanical" for i in instances)


def test_load_library_instances_excludes_seed_only_dirs(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    # Seed only — has source_task.json but no task.toml + instruction.md
    _write_seed(tasks_root, "civil", "drainage", "pipe-sizing")
    # Real instance
    _write_instance(tasks_root, "mechanical", "heat-load", "audit-office", "brisbane-8rm")

    instances = load_library_instances(tasks_root)
    assert len(instances) == 1
    assert instances[0].discipline == "mechanical"


def test_build_summary_aggregates(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    templates_root = tmp_path / "templates"
    _write_seed(tasks_root, "civil", "drainage", "pipe-sizing")
    _write_seed(tasks_root, "civil", "drainage", "culvert-design", complexity="medium")
    _write_seed(tasks_root, "electrical", "cable-sizing", "cable-ampacity")
    _write_template(templates_root, "electrical", "voltage-drop")
    _write_instance(tasks_root, "mechanical", "heat-load", "audit", "brisbane")

    seeds = _load_seeds(tasks_root)
    templates = _load_templates(templates_root)
    instances = load_library_instances(tasks_root)
    summary = build_summary(seeds, templates, instances)

    assert summary.total_seeds == 3
    assert summary.total_templates == 1
    assert summary.total_instances == 1
    assert summary.seeds_by_discipline["civil"] == 2
    assert summary.seeds_by_discipline["electrical"] == 1
    assert summary.complexity_counts["low"] == 2
    assert summary.complexity_counts["medium"] == 1
    assert summary.total_categories == 2  # drainage, cable-sizing


def test_load_seeds_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    seeds = _load_seeds(tmp_path / "nonexistent")
    assert seeds == []


def test_load_library_instances_handles_flat_two_level_paths(tmp_path: Path) -> None:
    """Flat instances at tasks/<discipline>/<task>/ with only 2 path parts."""
    tasks_root = tmp_path / "tasks"
    inst_dir = tasks_root / "electrical" / "voltage-drop"
    inst_dir.mkdir(parents=True)
    (inst_dir / "task.toml").write_text(
        '[identity]\nid = "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa"\n'
        'key = "electrical/voltage-drop"\nversion = 1\n\n'
        '[metadata]\ndifficulty = "easy"\nlifecycle = "active"\nvisibility = "public"\n',
        encoding="utf-8",
    )
    (inst_dir / "instruction.md").write_text("Calculate voltage drop.", encoding="utf-8")
    (inst_dir / "tests").mkdir()
    (inst_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    instances = load_library_instances(tasks_root)
    assert len(instances) == 1
    assert instances[0].discipline == "electrical"
    assert instances[0].instance_name == "voltage-drop"


def test_scan_finds_both_seed_and_instance_in_colocated_dir(tmp_path: Path) -> None:
    """A directory can have both source_task.json and task.toml + instruction.md."""
    tasks_root = tmp_path / "tasks"
    colocated = tasks_root / "ground" / "foundations" / "terzaghi"
    colocated.mkdir(parents=True)
    # Seed
    seed = {
        "status": "proposed",
        "seed_origin": "ngnbench",
        "source": {
            "discipline": "ground",
            "category_id": "foundations",
            "task_id": "terzaghi",
            "task_name": "Terzaghi",
            "description": "test",
            "complexity": "low",
            "standards": ["std"],
            "inputs": ["x"],
            "outputs": ["y"],
        },
    }
    (colocated / "source_task.json").write_text(json.dumps(seed), encoding="utf-8")
    # Instance
    (colocated / "task.toml").write_text(
        '[identity]\nid = "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa"\n'
        'key = "ground/foundations/terzaghi"\nversion = 1\n\n'
        '[metadata]\ndifficulty = "easy"\nlifecycle = "active"\nvisibility = "public"\n',
        encoding="utf-8",
    )
    (colocated / "instruction.md").write_text("Do it.", encoding="utf-8")
    (colocated / "tests").mkdir()
    (colocated / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    seeds = _load_seeds(tasks_root)
    instances = load_library_instances(tasks_root)
    assert len(seeds) == 1
    assert len(instances) == 1


def test_discover_templates_reports_dir_without_engine(tmp_path: Path) -> None:
    """A params.toml without sibling engine.py produces a diagnostic."""
    templates_root = tmp_path / "templates"
    orphan = templates_root / "ground" / "broken_template"
    orphan.mkdir(parents=True)
    (orphan / "params.toml").write_text('[meta]\nname = "broken"\n', encoding="utf-8")
    # No engine.py!

    templates, diagnostics = discover_templates(user_dirs=[templates_root], include_builtin=False)
    assert templates == []
    assert len(diagnostics) == 1
    assert diagnostics[0].path == orphan
    assert "engine.py" in diagnostics[0].error


# --- Task 2: Bar chart renderer tests ---


def test_render_bar_chart_produces_bars() -> None:
    data = {"civil": 88, "electrical": 145, "ground": 13}
    result = render_bar_chart(data, max_width=20)
    lines = result.strip().split("\n")
    assert len(lines) == 3
    assert "electrical" in lines[0]
    assert "█" in lines[0]


def test_render_bar_chart_empty_data() -> None:
    result = render_bar_chart({}, max_width=20)
    assert result == ""


# --- Task 3: Detail pane renderer tests ---


def test_render_seed_detail_shows_pipeline(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_seed(tasks_root, "civil", "drainage", "pipe-sizing")
    seeds = _load_seeds(tasks_root)

    result = render_seed_detail(seeds[0], has_template=False, instance_count=0)
    assert "pipe-sizing" in result.lower() or "Pipe Sizing" in result
    assert "seed" in result.lower()
    assert "template" in result.lower()


def test_render_template_detail_shows_params(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    _write_template(templates_root, "ground", "terzaghi-bearing")
    templates = _load_templates(templates_root)

    result = render_template_detail(templates[0])
    assert "terzaghi-bearing" in result
    assert "Parameters" in result or "params" in result.lower()


def test_render_template_detail_shows_archetypes_and_difficulty(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    template_dir = templates_root / "ground" / "full_template"
    template_dir.mkdir(parents=True)
    (template_dir / "__init__.py").write_text("# ABOUTME: test\n# ABOUTME: test\n")
    (template_dir / "engine.py").write_text(
        "# ABOUTME: test\n# ABOUTME: test\ndef compute(*, x: float) -> dict[str, float]:\n    return {'y': x}\n"
    )
    (template_dir / "instruction.md").write_text("Compute y.\n")
    toml_content = """
[meta]
name = "full-template"
discipline = "ground"
description = "test with archetypes"
category = "test"
tool_mode = "no-tool"

[params.x]
type = "float"
description = "input"
min = 0
max = 10

[outputs.y]
description = "result"
tolerance = 0.03

[archetypes.sandy_soil]
description = "Sandy soil profile"
site_contexts = ["test-site"]

[difficulty.easy]
description = "All parameters given"
visibility = "all_given"
archetypes = ["sandy_soil"]
"""
    (template_dir / "params.toml").write_text(toml_content, encoding="utf-8")

    templates = _load_templates(templates_root)
    full = [t for t in templates if t.task_id == "full-template"][0]
    result = render_template_detail(full)
    assert "sandy_soil" in result or "Sandy soil" in result
    assert "easy" in result


def test_render_instance_detail_shows_environment(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_instance(tasks_root, "mechanical", "heat-load", "audit", "brisbane")
    instances = load_library_instances(tasks_root)

    result = render_instance_detail(instances[0])
    assert "brisbane" in result
    assert "medium" in result


def test_render_discipline_detail_shows_counts(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_seed(tasks_root, "civil", "drainage", "pipe-sizing")
    _write_seed(tasks_root, "civil", "drainage", "culvert-design")
    _write_seed(tasks_root, "civil", "pavement", "road-thickness", complexity="medium")
    seeds = [s for s in _load_seeds(tasks_root) if s.discipline == "civil"]

    result = render_discipline_detail("civil", seeds, template_count=0, instance_count=0)
    assert "civil" in result.lower()
    assert "3" in result
    assert "drainage" in result


def test_render_category_detail_shows_seeds(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_seed(tasks_root, "civil", "drainage", "pipe-sizing")
    _write_seed(tasks_root, "civil", "drainage", "culvert-design")
    seeds = [s for s in _load_seeds(tasks_root) if s.category == "drainage"]

    result = render_category_detail("drainage", seeds, template_ids=set())
    assert "drainage" in result
    assert "pipe-sizing" in result
    assert "culvert-design" in result


# --- Task 4: Library screen tests ---


class LibraryTestApp(App[None]):
    def __init__(self, tasks_root: Path, templates_root: Path | None = None) -> None:
        super().__init__()
        self._tasks_root = tasks_root
        self._templates_root = templates_root

    def on_mount(self) -> None:
        self.push_screen(
            LibraryScreen(
                tasks_root=self._tasks_root,
                templates_root=self._templates_root,
            )
        )


def _populate_library(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal library with seeds, a template, and an instance."""
    tasks_root = tmp_path / "tasks"
    templates_root = tmp_path / "templates"
    _write_seed(tasks_root, "civil", "drainage", "pipe-sizing")
    _write_seed(tasks_root, "electrical", "cable-sizing", "cable-ampacity")
    _write_template(templates_root, "electrical", "voltage-drop")
    _write_instance(tasks_root, "mechanical", "heat-load", "audit", "brisbane")
    return tasks_root, templates_root


@pytest.mark.anyio
async def test_library_screen_loads_data(tmp_path: Path) -> None:
    tasks_root, templates_root = _populate_library(tmp_path)
    app = LibraryTestApp(tasks_root=tasks_root, templates_root=templates_root)

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, LibraryScreen)
        assert screen._summary.total_seeds == 2
        assert screen._summary.total_templates == 1


@pytest.mark.anyio
async def test_library_screen_empty_tasks(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    templates_root = tmp_path / "templates"
    app = LibraryTestApp(tasks_root=tasks_root, templates_root=templates_root)

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert screen._summary.total_seeds == 0


@pytest.mark.anyio
async def test_library_has_no_search_input(tmp_path: Path) -> None:
    tasks_root, templates_root = _populate_library(tmp_path)
    app = LibraryTestApp(tasks_root=tasks_root, templates_root=templates_root)

    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Input

        inputs = app.query(Input)
        assert len(inputs) == 0
