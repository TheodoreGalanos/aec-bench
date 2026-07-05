# ABOUTME: Tests runnable SSC-08 product templates beyond the station population baseline.
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

SSC08_PRODUCT_CASES = [
    {
        "name": "room-occupancy-lighting-access-control-package",
        "discipline": "electrical",
        "category": "room-operations",
        "product_id": "SSC-08-LH-02",
        "source_ids": [
            "ROOM-08-PLAN-02",
            "OCC-08-SCHED-02",
            "LGT-08-LAYOUT-02",
            "ACC-08-DEV-02",
            "ENERGY-08-PROFILE-02",
            "MEMO-08-ROOM-02",
        ],
        "expected": {
            "design_occupants": 40.0,
            "average_illuminance_lux": 93.6,
            "illuminance_margin_lux": 3.6,
            "uniformity_ratio": 0.769,
            "lighting_power_density_w_m2": 1.6,
            "leni_kwh_m2_y": 5.12,
            "access_reader_count": 6.0,
            "access_controller_spare_points": 2.0,
            "access_battery_required_wh": 343.529,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "life-safety-vertical-movement-emergency-power-package",
        "discipline": "electrical",
        "category": "life-safety-emergency-power",
        "product_id": "SSC-08-LH-03",
        "source_ids": [
            "EMERG-08-PLAN-03",
            "LIFT-08-SCHED-03",
            "ESC-08-SCHED-03",
            "ALARM-08-LOAD-03",
            "BACKUP-08-POWER-03",
            "MEMO-08-POWER-03",
        ],
        "expected": {
            "critical_connected_load_kw": 42.1,
            "diversified_emergency_load_kw": 35.785,
            "available_generator_capacity_kw": 49.5,
            "generator_capacity_margin_kw": 13.715,
            "battery_bridge_load_kw": 7.1,
            "required_battery_capacity_kwh": 17.75,
            "battery_capacity_margin_kwh": 6.25,
            "emergency_feeder_current_a": 57.39,
            "feeder_voltage_drop_percent": 1.231,
            "voltage_drop_margin_percent": 1.769,
            "load_shed_margin_kw": 4.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "crowd-cctv-communications-operations-package",
        "discipline": "electrical",
        "category": "security-communications-operations",
        "product_id": "SSC-08-LH-04",
        "source_ids": [
            "QUEUE-08-SCHED-04",
            "CCTV-08-LAYOUT-04",
            "NET-08-TOPO-04",
            "POE-08-SWITCH-04",
            "ACCESS-08-STATE-04",
            "MEMO-08-SECURITY-04",
        ],
        "expected": {
            "queue_population_persons": 118.8,
            "cctv_pixels_per_m": 240.0,
            "ppm_margin": 60.0,
            "cctv_storage_tb": 6.26,
            "network_load_mbps": 33.24,
            "network_headroom_mbps": 26.76,
            "poe_load_w": 140.0,
            "poe_headroom_w": 40.0,
            "access_state_match_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "smoke-control-visibility-egress-interaction-package",
        "discipline": "mechanical",
        "category": "smoke-control-egress",
        "product_id": "SSC-08-LH-05",
        "source_ids": [
            "FIRE-08-STRATEGY-05",
            "POP-08-SCHED-05",
            "VENT-08-SCHED-05",
            "EGRESS-08-PLAN-05",
            "VIS-08-CRIT-05",
            "MEMO-08-TENABILITY-05",
        ],
        "expected": {
            "smoke_exhaust_air_changes_per_h": 7.5,
            "ach_margin": 1.5,
            "smoke_layer_height_margin_m": 0.3,
            "visibility_margin_m": 4.0,
            "required_egress_width_mm": 2600.0,
            "egress_width_margin_mm": 600.0,
            "egress_flow_time_s": 130.0,
            "egress_time_margin_s": 50.0,
            "life_safety_battery_margin_kwh": 1.2,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "lift-shaft-car-accessibility-service-package",
        "discipline": "mechanical",
        "category": "vertical-transport-accessibility",
        "product_id": "SSC-08-LH-06",
        "source_ids": [
            "SHAFT-08-PLAN-06",
            "CAR-08-DATA-06",
            "ACCESS-08-SCHED-06",
            "LIFT-08-RULE-06",
            "POWER-08-SCHED-06",
            "MEMO-08-VT-06",
        ],
        "expected": {
            "car_width_margin_m": 0.2,
            "car_depth_margin_m": 0.1,
            "shaft_width_margin_m": 0.15,
            "shaft_depth_margin_m": 0.15,
            "accessible_lift_capacity_persons_per_5min": 80.842,
            "accessible_capacity_margin_persons_per_5min": 38.842,
            "emergency_power_load_kw": 25.5,
            "generator_allocation_margin_kw": 6.5,
            "lift_feeder_current_a": 41.825,
            "feeder_voltage_drop_margin_percent": 2.379,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "pedestrian-clearance-forecourt-signal-interface-package",
        "discipline": "civil",
        "category": "pedestrian-forecourt-interface",
        "product_id": "SSC-08-LH-07",
        "source_ids": [
            "FORECOURT-08-PLAN-07",
            "PED-08-DEMAND-07",
            "SIGNAL-08-TIMING-07",
            "LIGHT-08-LAYOUT-07",
            "AUTH-08-ROAD-07",
            "MEMO-08-INTERFACE-07",
        ],
        "expected": {
            "pedestrian_clearance_time_s": 18.0,
            "pedestrian_phase_margin_s": 6.0,
            "all_red_time_s": 1.72,
            "all_red_margin_s": 1.28,
            "forecourt_density_person_m2": 1.5,
            "forecourt_density_margin_person_m2": 0.5,
            "required_discharge_width_mm": 1950.0,
            "discharge_width_margin_mm": 450.0,
            "forecourt_average_illuminance_lux": 66.462,
            "illuminance_margin_lux": 16.462,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "building-operations-scenario-repair-package",
        "discipline": "mechanical",
        "category": "building-operations-review",
        "product_id": "SSC-08-LH-08",
        "source_ids": [
            "PLAN-08-FLOOR-08",
            "OCC-08-SOURCE-08",
            "SYSTEM-08-SCHED-08",
            "CRIT-08-MATRIX-08",
            "COMMENT-08-REG-08",
            "MEMO-08-REPAIR-08",
        ],
        "expected": {
            "source_trace_score": 1.0,
            "occupancy_update_fraction": 1.0,
            "affected_system_check_fraction": 0.917,
            "comment_resolution_fraction": 0.9,
            "open_critical_comment_count": 0.0,
            "authority_partition_score": 1.0,
            "repair_action_closure_fraction": 0.875,
            "unsupported_value_count": 0.0,
            "evidence_boundary_score": 0.949,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC08_PRODUCT_CASES, ids=[case["name"] for case in SSC08_PRODUCT_CASES])
def test_ssc08_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC08_PRODUCT_CASES, ids=[case["name"] for case in SSC08_PRODUCT_CASES])
def test_ssc08_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=85, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC08_PRODUCT_CASES, ids=[case["name"] for case in SSC08_PRODUCT_CASES])
def test_ssc08_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=85, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC08_PRODUCT_CASES, ids=[case["name"] for case in SSC08_PRODUCT_CASES])
def test_ssc08_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=85, instance_index=0)
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
