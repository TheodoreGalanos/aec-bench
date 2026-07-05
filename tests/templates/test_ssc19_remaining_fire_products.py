# ABOUTME: Tests runnable SSC-19 product templates beyond the fire-water baseline.
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

SSC19_PRODUCT_CASES = [
    {
        "name": "bess-fire-containment-ventilation-feeder-package",
        "discipline": "electrical",
        "category": "bess-safety-feeder",
        "product_id": "SSC-19-LH-02",
        "source_ids": [
            "BESS-19-DATA-02",
            "FIRE-19-STRAT-02",
            "VENT-19-SCHED-02",
            "CONTAIN-19-DETAIL-02",
            "SLD-19-BESS-02",
            "MEMO-19-SAFETY-02",
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
        "name": "structural-fire-tenability-package",
        "discipline": "structural",
        "category": "structural-fire-tenability",
        "product_id": "SSC-19-LH-03",
        "source_ids": [
            "FIRE-19-STRAT-03",
            "HRR-19-DESIGN-03",
            "STEEL-19-MEMBER-03",
            "TEN-19-CRIT-03",
            "EGRESS-19-ALARM-03",
            "MEMO-19-FIRE-ENG-03",
        ],
        "expected": {
            "design_hrr_kw": 2701.44,
            "fire_energy_mj": 3241.728,
            "steel_critical_temp_c": 474.136,
            "steel_temperature_margin_c": 54.136,
            "visibility_distance_m": 32.0,
            "visibility_margin_m": 22.0,
            "required_egress_width_m": 6.4,
            "egress_width_margin_m": 2.0,
            "nac_current_margin_a": 3.5,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "alarm-smoke-control-emergency-power-package",
        "discipline": "electrical",
        "category": "alarm-smoke-emergency-power",
        "product_id": "SSC-19-LH-04",
        "source_ids": [
            "ALARM-19-ZONE-04",
            "NAC-19-LOAD-04",
            "SMOKE-19-VENT-04",
            "BATT-19-LIFE-04",
            "OPS-19-EMERG-04",
            "MEMO-19-LIFE-04",
        ],
        "expected": {
            "nac_current_a": 7.8,
            "nac_current_margin_a": 2.2,
            "smoke_control_load_kw": 24.9,
            "battery_required_ah": 19.5,
            "battery_capacity_margin_ah": 240.5,
            "generator_required_kw": 31.312,
            "generator_margin_kw": 48.688,
            "smoke_exhaust_ach": 4.024,
            "smoke_exhaust_ach_margin": 0.024,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "warehouse-hazard-storage-fm-ahj-review-package",
        "discipline": "mechanical",
        "category": "warehouse-hazard-review",
        "product_id": "SSC-19-LH-05",
        "source_ids": [
            "STORE-19-LAYOUT-05",
            "HAZ-19-COMMODITY-05",
            "SPR-19-BASIS-05",
            "REVIEW-19-FM-AHJ-05",
            "CALC-19-APPENDIX-05",
            "MEMO-19-HAZARD-05",
        ],
        "expected": {
            "storage_area_ft2": 24000.0,
            "storage_height_ft": 28.0,
            "sprinkler_density_gpm_ft2": 0.338,
            "sprinkler_demand_gpm": 843.75,
            "total_fire_demand_gpm": 1343.75,
            "required_remote_head_count": 24.0,
            "water_supply_margin_gpm": 506.25,
            "pressure_margin_psi": 13.0,
            "aisle_width_margin_ft": 2.0,
            "comment_resolution_fraction": 0.833,
            "authority_response_score": 0.889,
            "critical_open_comments": 0.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "fire-pump-power-control-resilience-package",
        "discipline": "mechanical",
        "category": "fire-pump-resilience",
        "product_id": "SSC-19-LH-06",
        "source_ids": [
            "PUMP-19-CURVE-06",
            "MOTOR-19-FUEL-06",
            "CTRL-19-LOAD-06",
            "SUPPLY-19-CURVE-06",
            "CRIT-19-AUTH-06",
            "MEMO-19-PUMP-06",
        ],
        "expected": {
            "water_horsepower_hp": 52.509,
            "brake_horsepower_hp": 72.929,
            "motor_input_hp": 77.584,
            "motor_margin_hp": 47.416,
            "fuel_required_gal": 57.6,
            "fuel_margin_gal": 12.4,
            "control_energy_required_kwh": 16.0,
            "battery_energy_available_kwh": 17.28,
            "battery_energy_margin_kwh": 1.28,
            "feeder_voltage_drop_percent": 1.01,
            "voltage_drop_margin_percent": 1.99,
            "fire_flow_margin_gpm": 350.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "bund-containment-firewater-environmental-isolation-package",
        "discipline": "civil",
        "category": "bund-firewater-isolation",
        "product_id": "SSC-19-LH-07",
        "source_ids": [
            "INV-19-CHEM-07",
            "BUND-19-LAYOUT-07",
            "FIREWATER-19-DEMAND-07",
            "DRAIN-19-ISOLATION-07",
            "ENV-19-CRIT-07",
            "MEMO-19-CONTAIN-07",
        ],
        "expected": {
            "rainfall_allowance_l": 23100.0,
            "required_bund_volume_l": 42400.0,
            "bund_capacity_margin_l": 3600.0,
            "firewater_runoff_volume_l": 45600.0,
            "isolation_required_volume_l": 48600.0,
            "isolation_capacity_margin_l": 16400.0,
            "headloss_margin_m": 0.22,
            "valve_verification_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "fire-review-response-evidence-boundary-package",
        "discipline": "mechanical",
        "category": "fire-review-boundary",
        "product_id": "SSC-19-LH-08",
        "source_ids": [
            "SOURCE-19-INDEX-08",
            "COMMENT-19-REVIEW-08",
            "HAZ-19-TABLE-08",
            "CALC-19-EXTRACT-08",
            "AUTH-19-SOURCE-08",
            "RESPONSE-19-MEMO-08",
        ],
        "expected": {
            "source_trace_score": 0.9,
            "comment_resolution_fraction": 0.857,
            "affected_check_update_fraction": 1.0,
            "unresolved_gap_count": 2.0,
            "allowed_gap_margin": 1.0,
            "authority_role_separation_score": 1.0,
            "conflict_resolution_fraction": 0.667,
            "response_completeness_score": 0.917,
            "review_boundary_score": 0.89,
            "critical_open_comments": 0.0,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC19_PRODUCT_CASES, ids=[case["name"] for case in SSC19_PRODUCT_CASES])
def test_ssc19_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC19_PRODUCT_CASES, ids=[case["name"] for case in SSC19_PRODUCT_CASES])
def test_ssc19_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=79, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC19_PRODUCT_CASES, ids=[case["name"] for case in SSC19_PRODUCT_CASES])
def test_ssc19_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=79, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC19_PRODUCT_CASES, ids=[case["name"] for case in SSC19_PRODUCT_CASES])
def test_ssc19_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=79, instance_index=0)
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
