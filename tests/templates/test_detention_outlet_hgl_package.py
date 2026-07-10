# ABOUTME: Tests the SSC-03 detention outlet HGL built-in task template.
# ABOUTME: Covers discovery, deterministic stormwater metrics, and generated verifier output.

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
    / "civil"
    / "detention_outlet_hgl_package"
)


EXPECTED_METRICS = {
    "adjusted_rainfall_intensity_mm_h": 85.8,
    "post_development_peak_flow_m3_s": 1.098,
    "required_storage_volume_m3": 929.664,
    "available_storage_volume_m3": 1008.0,
    "storage_volume_margin_m3": 78.336,
    "orifice_area_m2": 0.139,
    "controlled_orifice_release_m3_s": 0.384,
    "outlet_release_margin_m3_s": 0.036,
    "emergency_weir_release_m3_s": 0.977,
    "major_event_excess_flow_m3_s": 0.896,
    "emergency_weir_margin_m3_s": 0.08,
    "design_water_surface_elevation_m": 42.25,
    "basin_freeboard_m": 0.3,
    "freeboard_margin_m": 0.05,
    "downstream_hgl_m": 41.38,
    "hgl_clearance_m": 0.27,
    "overall_pass_score": 1.0,
}


def _sample_ssc03_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=54, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "detention-outlet-hgl-package" in templates
    config = templates["detention-outlet-hgl-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "stormwater-detention"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=54, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc03_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CATCH-03-DET-01",
        "RAIN-03-IDF-10YR",
        "DET-03-BASIN-01",
        "OUT-03-ORIFICE-01",
        "OUT-03-WEIR-01",
        "HGL-03-OUTLET-01",
        "REPORT-03-SWMMTRACE-01",
        "MEMO-03-DRAINAGE-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc03_instance(tmp_path)
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
