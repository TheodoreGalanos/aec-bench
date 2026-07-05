# ABOUTME: Tests runnable SSC-06 product templates beyond the pump station duty baseline.
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

SSC06_PRODUCT_CASES = [
    {
        "name": "blower-process-energy-acoustic-package",
        "discipline": "mechanical",
        "category": "blower-process-acoustic",
        "product_id": "SSC-06-LH-02",
        "source_ids": [
            "PROCESS-06-BLOWER-02",
            "BLOWER-06-DATA-02",
            "MOTOR-06-SCHED-02",
            "RECEIVER-06-PLAN-02",
            "ACOUSTIC-06-CRIT-02",
            "MEMO-06-PROCESS-02",
        ],
        "expected": {
            "oxygen_demand_kg_d": 1775.808,
            "required_airflow_m3_min": 46.862,
            "blower_shaft_power_kw": 73.764,
            "motor_input_power_kw": 78.472,
            "motor_size_margin_kw": 11.528,
            "distance_attenuation_db": 32.465,
            "receiver_spl_dba": 49.535,
            "criterion_margin_db": 5.465,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "compressor-pneumatic-system-package",
        "discipline": "mechanical",
        "category": "compressor-pneumatic",
        "product_id": "SSC-06-LH-03",
        "source_ids": [
            "AIR-06-DEMAND-03",
            "COMP-06-DATA-03",
            "RECEIVER-06-STORAGE-03",
            "MOTOR-06-SCHED-03",
            "FEEDER-06-480V-03",
            "MEMO-06-AIR-03",
        ],
        "expected": {
            "adjusted_air_demand_m3_min": 14.515,
            "compressor_capacity_margin_m3_min": 3.985,
            "receiver_storage_runtime_min": 0.51,
            "compressor_shaft_power_kw": 89.994,
            "motor_input_power_kw": 94.731,
            "motor_size_margin_kw": 15.269,
            "feeder_current_a": 129.481,
            "feeder_voltage_drop_percent": 2.699,
            "voltage_drop_margin_percent": 1.301,
            "pressure_drop_margin_kpa": 13.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "equipment-support-foundation-vibration-package",
        "discipline": "structural",
        "category": "equipment-support-vibration",
        "product_id": "SSC-06-LH-04",
        "source_ids": [
            "LAYOUT-06-SKID-04",
            "MASS-06-SCHED-04",
            "FOUNDATION-06-BASE-04",
            "ISO-06-VIB-04",
            "LOAD-06-COMB-04",
            "MEMO-06-INSTALL-04",
        ],
        "expected": {
            "support_service_reaction_kn": 17.069,
            "factored_support_reaction_kn": 23.044,
            "bearing_pressure_kpa": 15.316,
            "bearing_utilization": 0.096,
            "frequency_ratio": 0.69,
            "vibration_transmissibility": 1.865,
            "transmitted_dynamic_force_kn": 31.842,
            "fatigue_damage_ratio": 0.006,
            "load_combination_margin_kn": 36.956,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "pump-affinity-retrofit-energy-package",
        "discipline": "mechanical",
        "category": "pump-affinity-retrofit",
        "product_id": "SSC-06-LH-05",
        "source_ids": [
            "CURVE-06-RETRO-05",
            "SCENARIO-06-LOAD-05",
            "AFFINITY-06-WS-05",
            "DRIVE-06-VFD-05",
            "TARIFF-06-ENERGY-05",
            "MEMO-06-RETRO-05",
        ],
        "expected": {
            "retrofit_flow_l_s": 70.52,
            "retrofit_head_m": 22.928,
            "retrofit_shaft_power_kw": 27.986,
            "retrofit_motor_input_kw": 29.773,
            "annual_energy_savings_kwh": 72354.097,
            "annual_cost_savings": 13023.737,
            "new_npsh_required_m": 4.586,
            "npsh_margin_m": 3.514,
            "motor_margin_kw": 4.816,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "heat-exchanger-thermal-plant-equipment-package",
        "discipline": "mechanical",
        "category": "thermal-plant-equipment",
        "product_id": "SSC-06-LH-06",
        "source_ids": [
            "PROCESS-06-THERMAL-06",
            "HX-06-DATA-06",
            "PUMP-06-CURVE-06",
            "MOTOR-06-SCHED-06",
            "SUPPORT-06-LAYOUT-06",
            "MEMO-06-THERMAL-06",
        ],
        "expected": {
            "heat_load_kw": 434.72,
            "lmtd_c": 40.0,
            "required_ua_kw_per_c": 10.868,
            "ua_margin_kw_per_c": 2.332,
            "process_flow_m3_h": 18.776,
            "pump_hydraulic_power_kw": 0.816,
            "pump_shaft_power_kw": 1.166,
            "motor_input_power_kw": 1.24,
            "motor_margin_kw": 0.96,
            "support_service_reaction_kn": 5.494,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "marine-coastal-pumping-equipment-package",
        "discipline": "mechanical",
        "category": "marine-coastal-pumping",
        "product_id": "SSC-06-LH-07",
        "source_ids": [
            "TIDE-06-TAILWATER-07",
            "SECTION-06-PUMP-07",
            "PIPE-06-SCHED-07",
            "MOTOR-06-SCHED-07",
            "MATERIAL-06-CORROSION-07",
            "MEMO-06-COASTAL-07",
        ],
        "expected": {
            "total_pumping_head_m": 12.55,
            "pump_hydraulic_power_kw": 6.057,
            "pump_input_power_kw": 9.046,
            "backup_generator_load_kw": 11.846,
            "generator_capacity_margin_kw": 23.154,
            "backup_runtime_hr": 16.546,
            "equipment_freeboard_m": 0.5,
            "equipment_freeboard_margin_m": 0.2,
            "corrosion_allowance_margin_mm": 1.5,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "equipment-datasheet-commissioning-review-package",
        "discipline": "mechanical",
        "category": "equipment-review-commissioning",
        "product_id": "SSC-06-LH-08",
        "source_ids": [
            "EQUIP-06-SCHED-08",
            "DATASHEET-06-MFR-08",
            "CURVE-06-EXPORT-08",
            "COMM-06-CHECK-08",
            "REVIEW-06-COMMENTS-08",
            "MEMO-06-REVIEW-08",
        ],
        "expected": {
            "flow_capacity_margin_pct": 8.974,
            "head_capacity_margin_pct": 12.245,
            "por_position_pct": 95.122,
            "por_margin_pct": 14.878,
            "npsh_margin_m": 2.8,
            "motor_service_margin_kw": 0.1,
            "evidence_completeness_score": 0.875,
            "open_commissioning_items": 2.0,
            "critical_review_comments_open": 0.0,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC06_PRODUCT_CASES, ids=[case["name"] for case in SSC06_PRODUCT_CASES])
def test_ssc06_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC06_PRODUCT_CASES, ids=[case["name"] for case in SSC06_PRODUCT_CASES])
def test_ssc06_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=75, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC06_PRODUCT_CASES, ids=[case["name"] for case in SSC06_PRODUCT_CASES])
def test_ssc06_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=75, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC06_PRODUCT_CASES, ids=[case["name"] for case in SSC06_PRODUCT_CASES])
def test_ssc06_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=75, instance_index=0)
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
