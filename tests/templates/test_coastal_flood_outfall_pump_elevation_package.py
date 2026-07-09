# ABOUTME: Tests the SSC-04 coastal flood outfall pump elevation template.
# ABOUTME: Covers discovery, deterministic coastal metrics, and generated verifier output.

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
    / "coastal_flood_outfall_pump_elevation_package"
)


EXPECTED_METRICS = {
    "present_submergence_percent": 32.241,
    "future_submergence_percent": 53.754,
    "submergence_increase_percent": 21.512,
    "design_stillwater_level_m": 2.65,
    "design_flood_level_m": 3.1,
    "minimum_equipment_elevation_m": 3.4,
    "inflow_volume_m3": 4536.0,
    "pumped_volume_m3": 3888.0,
    "storage_margin_m3": 102.0,
    "pump_total_dynamic_head_m": 4.7,
    "pump_hydraulic_power_kw": 16.599,
    "pump_motor_input_kw": 24.789,
    "pump_motor_margin_kw": 5.211,
    "switchboard_freeboard_margin_m": 0.22,
    "controls_freeboard_margin_m": 0.15,
    "feeder_current_a": 40.1,
    "feeder_voltage_drop_percent": 0.989,
    "voltage_drop_margin_percent": 4.011,
    "overall_pass_score": 1.0,
}


def _sample_ssc04_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=62, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "coastal-flood-outfall-pump-elevation-package" in templates
    config = templates["coastal-flood-outfall-pump-elevation-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "coastal-resilience"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=62, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc04_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CASE-SSC04-COASTAL-001",
        "DATUM-04-AHD-01",
        "TIDE-04-HORIZON-01",
        "OUTFALL-04-FLAP-01",
        "PUMP-04-FLOOD-01",
        "BASIN-04-WETWELL-01",
        "ELEC-04-SWBD-01",
        "FEEDER-04-PUMP-01",
        "MEMO-04-RESILIENCE-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc04_instance(tmp_path)
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
