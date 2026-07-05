# ABOUTME: Tests the SSC-17 stormwater pumping outage resilience built-in template.
# ABOUTME: Covers discovery, deterministic resilience metrics, and generated verifier output.

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
    / "electrical"
    / "stormwater_pumping_outage_resilience_package"
)


EXPECTED_METRICS = {
    "storm_inflow_volume_m3": 3888.0,
    "pumpable_volume_m3": 2764.8,
    "residual_storage_volume_m3": 1123.2,
    "storage_margin_m3": 126.8,
    "pump_hydraulic_power_kw": 20.012,
    "pump_input_power_kw": 27.795,
    "critical_mixed_load_kw": 30.195,
    "pump_energy_required_kwh": 88.944,
    "controls_energy_required_kwh": 14.4,
    "total_energy_required_kwh": 103.344,
    "usable_bess_energy_kwh": 161.868,
    "generator_energy_kwh": 84.0,
    "backup_energy_available_kwh": 245.868,
    "backup_energy_margin_kwh": 142.524,
    "battery_only_mixed_load_runtime_hr": 5.361,
    "feeder_voltage_drop_percent": 1.457,
    "voltage_drop_margin_percent": 2.543,
    "overall_pass_score": 1.0,
}


def _sample_ssc17_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=55, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "stormwater-pumping-outage-resilience-package" in templates
    config = templates["stormwater-pumping-outage-resilience-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "energy-resilience"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=55, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc17_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CASE-SSC17-PUMP-OUTAGE-001",
        "SCEN-17-STORM-OUTAGE-01",
        "RAIN-17-HYETO-01",
        "PUMP-17-STORM-01",
        "BASIN-17-WETWELL-01",
        "LOAD-17-CRITICAL-01",
        "BESS-17-BACKUP-01",
        "GEN-17-BACKUP-01",
        "FEEDER-17-480V-01",
        "CTRL-17-RTU-01",
        "MEMO-17-RESILIENCE-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc17_instance(tmp_path)
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
