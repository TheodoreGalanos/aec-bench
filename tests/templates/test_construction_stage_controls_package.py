# ABOUTME: Tests the SSC-16 construction stage controls built-in task template.
# ABOUTME: Covers discovery, deterministic source-pack calculations, and generated verifier output.

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
    / "construction_stage_controls_package"
)


EXPECTED_METRICS = {
    "runoff_volume_ft3": 26345.088,
    "required_basin_volume_ft3": 26345.088,
    "basin_storage_headroom_ft3": 5154.912,
    "freeboard_margin_ft": 0.4,
    "tss_load_lb": 304.264,
    "taper_length_ft": 224.583,
    "taper_headroom_ft": 25.417,
    "minimum_channelizer_count": 10.0,
    "channelizer_headroom_count": 2.0,
    "total_monitoring_data_mbps": 4.2,
    "monitoring_load_w": 40.0,
    "battery_autonomy_h": 48.0,
    "solar_daily_headroom_wh": 120.0,
    "inspection_days_remaining": 1.0,
}


def _sample_ssc16_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=42, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "construction-stage-controls-package" in templates
    config = templates["construction-stage-controls-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "construction-staging"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=42, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc16_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "STG-SSC16-001",
        "WZ-16-A",
        "SB-01",
        "TTC-01",
        "MON-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc16_instance(tmp_path)
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
