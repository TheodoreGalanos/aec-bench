# ABOUTME: Tests the SSC-09 facade wind, bracket, anchor, and tolerance template.
# ABOUTME: Covers discovery, deterministic facade fixing metrics, and verifier output.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.templates.registry import discover_templates, load_engine_module, load_template

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "structural"
    / "facade_wind_bracket_anchor_package"
)


EXPECTED_METRICS = {
    "velocity_pressure_kpa": 1.2,
    "body_pressure_kpa": 1.2,
    "edge_pressure_kpa": 1.8,
    "corner_pressure_kpa": 2.4,
    "tributary_area_m2": 0.9,
    "body_wind_load_kn": 1.08,
    "edge_wind_load_kn": 1.62,
    "corner_wind_load_kn": 2.16,
    "dead_load_per_bracket_kn": 0.315,
    "corner_bracket_horizontal_utilization": 0.771,
    "corner_bracket_vertical_utilization": 0.262,
    "body_anchor_combined_utilization": 0.445,
    "edge_anchor_combined_utilization": 0.656,
    "corner_anchor_combined_utilization": 0.87,
    "governing_utilization": 0.87,
    "anchor_embedment_margin_mm": 0.0,
    "anchor_edge_margin_mm": 10.0,
    "anchor_spacing_margin_mm": 60.0,
    "required_projection_mm": 208.0,
    "projection_margin_mm": 22.0,
    "fixed_point_vertical_margin_kn": 0.885,
    "governing_row_is_corner_score": 1.0,
    "overall_pass_score": 1.0,
}


def _sample_ssc09_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=61, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "facade-wind-bracket-anchor-package" in templates
    config = templates["facade-wind-bracket-anchor-package"]
    assert config.meta.discipline == "structural"
    assert config.meta.category == "facade-structural"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=61, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc09_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CASE-SSC09-FACADE-001",
        "ELEV-09-REDRAWN-01",
        "WIND-09-CRIT-01",
        "PRESS-09-ZONES-01",
        "SUP-09-BRACKET-01",
        "ANCH-09-CONC-01",
        "TOL-09-SETOUT-01",
        "MEMO-09-FIXING-01",
        "fixed and sliding points",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc09_instance(tmp_path)
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    reward_file = tmp_path / "reward.json"

    result = subprocess.run(
        [
            sys.executable,
            str(instance_dir / "tests" / "verify.py"),
            "--input",
            str(golden_pass),
            "--output",
            str(reward_file),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(reward_file.read_text(encoding="utf-8"))["reward"] == 1.0
