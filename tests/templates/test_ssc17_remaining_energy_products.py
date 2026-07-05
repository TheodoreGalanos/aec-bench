# ABOUTME: Tests runnable SSC-17 product templates beyond the stormwater pumping baseline.
# ABOUTME: Covers discovery, deterministic metrics, source IDs, and golden verifier scoring.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.templates.registry import discover_templates, load_engine_module

SSC17_PRODUCT_CASES = [
    {
        "name": "der-resilience-feeder-interconnection-package",
        "discipline": "electrical",
        "category": "der-interconnection-resilience",
        "product_id": "SSC-17-LH-01",
        "source_ids": [
            "PV-SSC17-001",
            "LOAD-SSC17-001",
            "BESS-SSC17-001",
            "SLD-SSC17-001",
            "UTIL-SSC17-001",
            "MEMO-SSC17-001",
        ],
        "expected": {
            "pv_ac_output_kw": 147.6,
            "export_kw": 57.6,
            "export_margin_kw": 62.4,
            "critical_energy_required_kwh": 310.0,
            "usable_bess_energy_kwh": 315.84,
            "generator_energy_kwh": 110.0,
            "resilience_energy_available_kwh": 425.84,
            "autonomy_energy_margin_kwh": 115.84,
            "battery_only_runtime_hr": 5.094,
            "feeder_voltage_drop_percent": 1.848,
            "voltage_drop_margin_percent": 1.152,
            "feeder_ampacity_margin_a": 68.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "wastewater-energy-island-resilience-package",
        "discipline": "mechanical",
        "category": "wastewater-energy-resilience",
        "product_id": "SSC-17-LH-02",
        "source_ids": [
            "WWTP-SSC17-002",
            "PFD-SSC17-002",
            "BLOWER-SSC17-002",
            "BIOGAS-SSC17-002",
            "BESS-SSC17-002",
            "MEMO-SSC17-002",
        ],
        "expected": {
            "oxygen_demand_kg_d": 931.776,
            "blower_energy_kwh_d": 698.832,
            "blower_average_kw": 29.118,
            "biogas_production_m3_d": 353.6,
            "chp_energy_available_kwh": 371.576,
            "bess_usable_energy_kwh": 220.8,
            "critical_process_energy_kwh": 565.416,
            "resilience_energy_available_kwh": 592.376,
            "energy_margin_kwh": 26.96,
            "battery_only_runtime_hr": 4.686,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "bess-fire-containment-ventilation-feeder-package",
        "discipline": "electrical",
        "category": "bess-safety-feeder",
        "product_id": "SSC-17-LH-04",
        "source_ids": [
            "BESS-SSC17-004",
            "SLD-SSC17-004",
            "ROOM-SSC17-004",
            "FIRE-SSC17-004",
            "VENT-SSC17-004",
            "MEMO-SSC17-004",
        ],
        "expected": {
            "usable_bess_energy_kwh": 484.5,
            "ventilation_airflow_m3_s": 0.3,
            "ventilation_fan_power_kw": 0.36,
            "ventilation_energy_kwh": 1.44,
            "design_hrr_kw": 360.0,
            "containment_hrr_margin_kw": 140.0,
            "safety_load_kw": 2.86,
            "safety_energy_required_kwh": 11.44,
            "safety_energy_margin_kwh": 473.06,
            "feeder_voltage_drop_percent": 0.758,
            "voltage_drop_margin_percent": 2.242,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "road-its-field-equipment-energy-resilience-package",
        "discipline": "electrical",
        "category": "road-its-energy-resilience",
        "product_id": "SSC-17-LH-05",
        "source_ids": [
            "ROAD-SSC17-005",
            "DEVICE-SSC17-005",
            "NET-SSC17-005",
            "CAB-SSC17-005",
            "FLOOD-SSC17-005",
            "MEMO-SSC17-005",
        ],
        "expected": {
            "field_device_load_kw": 2.22,
            "outage_energy_required_kwh": 22.2,
            "usable_battery_energy_kwh": 26.496,
            "pv_energy_available_kwh": 2.55,
            "backup_energy_available_kwh": 29.046,
            "backup_energy_margin_kwh": 6.846,
            "battery_only_runtime_hr": 11.935,
            "vms_runtime_margin_hr": 3.935,
            "cabinet_freeboard_m": 0.65,
            "cabinet_freeboard_margin_m": 0.35,
            "poe_load_w": 76.0,
            "poe_margin_w": 4.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "station-emergency-operations-energy-package",
        "discipline": "electrical",
        "category": "station-emergency-energy",
        "product_id": "SSC-17-LH-06",
        "source_ids": [
            "STATION-SSC17-006",
            "POP-SSC17-006",
            "LIFE-SSC17-006",
            "SLD-SSC17-006",
            "SHED-SSC17-006",
            "MEMO-SSC17-006",
        ],
        "expected": {
            "emergency_load_kw": 73.8,
            "required_energy_kwh": 221.4,
            "generator_energy_kwh": 187.5,
            "usable_bess_energy_kwh": 178.56,
            "backup_energy_available_kwh": 366.06,
            "backup_energy_margin_kwh": 144.66,
            "battery_only_runtime_hr": 2.42,
            "generator_capacity_margin_kw": 51.2,
            "load_shed_kw": 55.0,
            "feeder_voltage_drop_percent": 1.689,
            "voltage_drop_margin_percent": 2.311,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "rail-weather-electrical-backup-operations-package",
        "discipline": "electrical",
        "category": "rail-weather-backup-energy",
        "product_id": "SSC-17-LH-07",
        "source_ids": [
            "RAIL-SSC17-007",
            "WEATHER-SSC17-007",
            "SIGNAL-SSC17-007",
            "FEEDER-SSC17-007",
            "RULE-SSC17-007",
            "MEMO-SSC17-007",
        ],
        "expected": {
            "signal_comms_load_kw": 10.0,
            "weather_heating_energy_kwh": 54.0,
            "required_backup_energy_kwh": 134.0,
            "usable_battery_energy_kwh": 186.576,
            "generator_energy_kwh": 60.0,
            "backup_energy_available_kwh": 246.576,
            "backup_energy_margin_kwh": 112.576,
            "battery_only_runtime_hr": 18.658,
            "thermal_rating_margin_a": 55.0,
            "sag_margin_m": 0.13,
            "feeder_voltage_drop_percent": 3.184,
            "voltage_drop_margin_percent": 1.816,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "coastal-marine-flood-energy-resilience-package",
        "discipline": "electrical",
        "category": "coastal-flood-energy-resilience",
        "product_id": "SSC-17-LH-08",
        "source_ids": [
            "COAST-SSC17-008",
            "SECTION-SSC17-008",
            "PUMP-SSC17-008",
            "EQUIP-SSC17-008",
            "BACKUP-SSC17-008",
            "MEMO-SSC17-008",
        ],
        "expected": {
            "design_flood_level_m": 3.6,
            "equipment_freeboard_m": 0.65,
            "equipment_freeboard_margin_m": 0.2,
            "outfall_submergence_m": 0.65,
            "outfall_submergence_margin_m": 0.15,
            "pump_input_power_kw": 16.144,
            "backup_energy_required_kwh": 47.361,
            "usable_bess_energy_kwh": 114.39,
            "generator_energy_kwh": 52.5,
            "backup_energy_available_kwh": 166.89,
            "backup_energy_margin_kwh": 119.529,
            "feeder_voltage_drop_percent": 1.223,
            "voltage_drop_margin_percent": 2.777,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC17_PRODUCT_CASES, ids=[case["name"] for case in SSC17_PRODUCT_CASES])
def test_ssc17_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC17_PRODUCT_CASES, ids=[case["name"] for case in SSC17_PRODUCT_CASES])
def test_ssc17_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=74, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC17_PRODUCT_CASES, ids=[case["name"] for case in SSC17_PRODUCT_CASES])
def test_ssc17_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=74, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC17_PRODUCT_CASES, ids=[case["name"] for case in SSC17_PRODUCT_CASES])
def test_ssc17_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=74, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    reward_file = tmp_path / f"{case['name']}-reward.json"

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
