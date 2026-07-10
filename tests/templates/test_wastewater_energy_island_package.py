# ABOUTME: Tests the SSC-10 wastewater energy island built-in template.
# ABOUTME: Covers discovery, deterministic process-energy metrics, and generated verifier output.

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
    / "mechanical"
    / "wastewater_energy_island_package"
)


EXPECTED_METRICS = {
    "bod_removed_kg_d": 1392.0,
    "carbonaceous_oxygen_kg_d": 227.6,
    "nitrogenous_oxygen_kg_d": 954.216,
    "denitrification_credit_kg_d": 298.584,
    "total_oxygen_kg_d": 883.232,
    "required_airflow_nm3_h": 740.768,
    "blower_capacity_oxygen_kg_d": 1013.472,
    "oxygen_capacity_margin_kg_d": 130.24,
    "blower_shaft_power_kw": 18.761,
    "blower_input_power_kw": 19.959,
    "blower_motor_margin_kw": 10.041,
    "volatile_solids_destroyed_kg_d": 456.0,
    "biogas_m3_d": 410.4,
    "methane_m3_d": 254.448,
    "methane_energy_kwh_d": 2536.847,
    "biogas_electric_energy_kwh_d": 862.528,
    "critical_process_load_kw": 56.659,
    "daily_process_energy_kwh": 1359.811,
    "usable_bess_energy_kwh": 249.12,
    "onsite_energy_available_kwh": 1501.648,
    "island_energy_margin_kwh": 141.837,
    "process_energy_intensity_kwh_m3": 0.234,
    "onsite_energy_fraction": 1.0,
    "feeder_current_a": 79.244,
    "feeder_voltage_drop_percent": 3.795,
    "voltage_drop_margin_percent": 1.205,
    "overall_pass_score": 1.0,
}


def _sample_ssc10_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=57, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "wastewater-energy-island-package" in templates
    config = templates["wastewater-energy-island-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "wastewater-energy"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=57, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc10_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CASE-SSC10-ENERGY-001",
        "PROCESS-10-BASIS-01",
        "PFD-10-AERATION-01",
        "AER-10-BASIN-01",
        "BLOWER-10-01",
        "DIG-10-BIOGAS-01",
        "PV-10-ARRAY-01",
        "BESS-10-ISLAND-01",
        "FEEDER-10-480V-01",
        "MEMO-10-ENERGY-ISLAND-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc10_instance(tmp_path)
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
