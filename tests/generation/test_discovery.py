# ABOUTME: Tests for template and seed directory scanning in the generation package.
# ABOUTME: Covers discovery of templates (engine.py + params.toml) and seeds (source_task.json).

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.generation.discovery import (
    LibrarySeed,
    LibraryTemplate,
    scan_seeds,
    scan_templates,
)


def test_scan_templates_empty_dir(tmp_path: Path) -> None:
    """Empty directory returns no templates."""
    result = scan_templates(tmp_path)
    assert result == []


def test_scan_templates_nonexistent_dir(tmp_path: Path) -> None:
    """Non-existent directory returns no templates."""
    result = scan_templates(tmp_path / "does-not-exist")
    assert result == []


def test_scan_templates_finds_valid_template(tmp_path: Path) -> None:
    """Directory with params.toml + engine.py is discovered as a template."""
    tmpl_dir = tmp_path / "electrical" / "voltage-drop"
    tmpl_dir.mkdir(parents=True)

    params_content = """\
[meta]
name = "voltage-drop"
discipline = "electrical"
description = "Voltage drop calculation"

[params]
voltage = { type = "float", min = 110, max = 480 }
"""
    (tmpl_dir / "params.toml").write_text(params_content, encoding="utf-8")
    (tmpl_dir / "engine.py").write_text("# engine stub", encoding="utf-8")

    result = scan_templates(tmp_path)

    assert len(result) == 1
    t = result[0]
    assert isinstance(t, LibraryTemplate)
    assert t.discipline == "electrical"
    assert t.task_id == "voltage-drop"
    assert t.path == tmpl_dir
    assert t.params_raw["meta"]["name"] == "voltage-drop"


def test_scan_templates_skips_without_engine(tmp_path: Path) -> None:
    """Directory with params.toml but no engine.py is skipped."""
    tmpl_dir = tmp_path / "civil" / "drainage"
    tmpl_dir.mkdir(parents=True)

    params_content = """\
[meta]
name = "drainage"
discipline = "civil"
"""
    (tmpl_dir / "params.toml").write_text(params_content, encoding="utf-8")

    result = scan_templates(tmp_path)
    assert result == []


def test_scan_seeds_empty_dir(tmp_path: Path) -> None:
    """Empty directory returns no seeds."""
    result = scan_seeds(tmp_path)
    assert result == []


def test_scan_seeds_nonexistent_dir(tmp_path: Path) -> None:
    """Non-existent directory returns no seeds."""
    result = scan_seeds(tmp_path / "does-not-exist")
    assert result == []


def test_scan_seeds_finds_valid_seed(tmp_path: Path) -> None:
    """Directory with source_task.json is discovered as a seed."""
    seed_dir = tmp_path / "electrical" / "cable-sizing"
    seed_dir.mkdir(parents=True)

    seed_data = {
        "source": {
            "discipline": "electrical",
            "category_id": "cable-sizing",
            "task_id": "cable-sizing-001",
            "task_name": "Cable Sizing Basic",
            "description": "Size a cable for a given load",
            "complexity": "easy",
            "standards": ["AS/NZS 3008"],
            "inputs": ["load_kw", "voltage"],
            "outputs": ["cable_size_mm2"],
        }
    }
    (seed_dir / "source_task.json").write_text(json.dumps(seed_data), encoding="utf-8")

    result = scan_seeds(tmp_path)

    assert len(result) == 1
    s = result[0]
    assert isinstance(s, LibrarySeed)
    assert s.discipline == "electrical"
    assert s.category == "cable-sizing"
    assert s.task_id == "cable-sizing-001"
    assert s.task_name == "Cable Sizing Basic"
    assert s.description == "Size a cable for a given load"
    assert s.complexity == "easy"
    assert s.standards == ("AS/NZS 3008",)
    assert s.inputs == ("load_kw", "voltage")
    assert s.outputs == ("cable_size_mm2",)
    assert s.path == seed_dir


def test_scan_seeds_skips_invalid_json(tmp_path: Path) -> None:
    """Malformed source_task.json is skipped without error."""
    seed_dir = tmp_path / "ground" / "broken"
    seed_dir.mkdir(parents=True)
    (seed_dir / "source_task.json").write_text("not valid json", encoding="utf-8")

    result = scan_seeds(tmp_path)
    assert result == []
