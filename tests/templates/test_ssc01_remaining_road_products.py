# ABOUTME: Tests runnable SSC-01 product templates beyond the first low-point package.
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

SSC01_PRODUCT_CASES = [
    {
        "name": "intersection-timing-grade-sight-distance-package",
        "discipline": "civil",
        "category": "traffic-safety",
        "product_id": "SSC-01-LH-02",
        "source_ids": [
            "INT-SSC01-002",
            "PROF-SSC01-002",
            "SIG-SSC01-002",
            "PED-SSC01-002",
            "MEMO-SSC01-002",
        ],
        "expected": {
            "stopping_distance_m": 85.91,
            "sight_distance_margin_m": 59.09,
            "yellow_interval_s": 4.08,
            "all_red_interval_s": 2.448,
            "ped_clearance_required_s": 14.667,
            "ped_clearance_margin_s": 1.333,
            "grade_adjusted_braking_distance_m": 44.243,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "road-lighting-its-drainage-operations-package",
        "discipline": "electrical",
        "category": "road-operations",
        "product_id": "SSC-01-LH-03",
        "source_ids": [
            "RD-SSC01-003",
            "LGT-SSC01-003",
            "CCTV-SSC01-003",
            "NET-SSC01-003",
            "PWR-SSC01-003",
        ],
        "expected": {
            "average_illuminance_lux": 17.883,
            "minimum_illuminance_lux": 16.5,
            "uniformity_ratio": 0.923,
            "glare_variation_ratio": 1.062,
            "total_network_load_mbps": 19.0,
            "network_headroom_mbps": 26.0,
            "total_cctv_storage_tb": 1.83,
            "poe_load_w": 54.0,
            "poe_headroom_w": 36.0,
            "water_level_margin_m": 0.3,
            "ups_energy_kwh": 1.022,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "emergency-detour-roadside-device-continuity-package",
        "discipline": "electrical",
        "category": "road-operations",
        "product_id": "SSC-01-LH-04",
        "source_ids": [
            "DETOUR-SSC01-004",
            "DEV-SSC01-004",
            "RF-SSC01-004",
            "PWR-SSC01-004",
            "MEMO-SSC01-004",
        ],
        "expected": {
            "vms_reading_time_s": 5.486,
            "vms_message_margin_chars": 1.946,
            "required_network_mbps": 21.6,
            "network_headroom_mbps": 13.4,
            "rf_received_power_dbm": -77.0,
            "rf_link_margin_db": 13.0,
            "battery_runtime_h": 11.077,
            "battery_margin_h": 3.077,
            "feeder_voltage_drop_percent": 0.248,
            "voltage_drop_margin_percent": 4.752,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "bus-priority-signal-cabinet-load-package",
        "discipline": "electrical",
        "category": "road-operations",
        "product_id": "SSC-01-LH-05",
        "source_ids": [
            "BUS-SSC01-005",
            "SIG-SSC01-005",
            "DET-SSC01-005",
            "CAB-SSC01-005",
            "FEED-SSC01-005",
        ],
        "expected": {
            "yellow_interval_s": 3.242,
            "all_red_interval_s": 2.88,
            "bus_handling_capacity_pax_h": 1170.0,
            "bus_capacity_margin_pax_h": 230.0,
            "cabinet_load_w": 891.0,
            "cabinet_load_margin_w": 509.0,
            "feeder_current_a": 4.211,
            "feeder_voltage_drop_percent": 0.422,
            "voltage_drop_margin_percent": 4.578,
            "battery_runtime_h": 4.741,
            "battery_margin_h": 1.741,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "culvert-driveway-access-safety-continuity-package",
        "discipline": "civil",
        "category": "road-resilience",
        "product_id": "SSC-01-LH-06",
        "source_ids": [
            "ACCESS-SSC01-006",
            "CULV-SSC01-006",
            "TAIL-SSC01-006",
            "SIGHT-SSC01-006",
            "MEMO-SSC01-006",
        ],
        "expected": {
            "driveway_grade_percent": 3.333,
            "driveway_grade_margin_percent": 4.667,
            "culvert_capacity_m3_s": 1.113,
            "culvert_capacity_margin_m3_s": 0.293,
            "headwater_level_m": 42.506,
            "freeboard_m": 0.144,
            "freeboard_margin_m": 0.044,
            "roadway_spread_m": 3.652,
            "spread_margin_m": 0.348,
            "sight_distance_required_m": 43.912,
            "sight_distance_margin_m": 76.088,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "roadside-cabinet-flood-heat-backup-energy-package",
        "discipline": "electrical",
        "category": "road-resilience",
        "product_id": "SSC-01-LH-07",
        "source_ids": [
            "CAB-SSC01-007",
            "HGL-SSC01-007",
            "HEAT-SSC01-007",
            "LOAD-SSC01-007",
            "BATT-SSC01-007",
        ],
        "expected": {
            "cabinet_freeboard_m": 0.36,
            "flood_freeboard_margin_m": 0.11,
            "thermal_derated_capacity_w": 630.0,
            "thermal_margin_w": 110.0,
            "thermal_utilization": 0.825,
            "battery_runtime_h": 11.25,
            "battery_margin_h": 5.25,
            "bess_power_margin_kw": 0.68,
            "bess_energy_margin_kwh": 2.73,
            "feeder_voltage_drop_percent": 0.205,
            "voltage_drop_margin_percent": 4.795,
            "road_lighting_aeci_kwh_m2_y": 1.378,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "multimodal-corridor-review-response-package",
        "discipline": "civil",
        "category": "road-resilience",
        "product_id": "SSC-01-LH-08",
        "source_ids": [
            "REV-SSC01-008",
            "MARKUP-SSC01-008",
            "DRAIN-SSC01-008",
            "SIG-SSC01-008",
            "FEED-SSC01-008",
        ],
        "expected": {
            "changed_chainage_delta_m": 12.5,
            "hgl_clearance_mm": 330.0,
            "hgl_clearance_margin_mm": 180.0,
            "ped_clearance_required_s": 16.333,
            "ped_clearance_margin_s": 3.667,
            "vms_reading_time_s": 8.778,
            "vms_message_margin_chars": 10.113,
            "feeder_voltage_drop_percent": 0.351,
            "voltage_drop_margin_percent": 4.649,
            "comment_closeout_percent": 100.0,
            "impacted_calculation_count": 5.0,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC01_PRODUCT_CASES, ids=[case["name"] for case in SSC01_PRODUCT_CASES])
def test_ssc01_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC01_PRODUCT_CASES, ids=[case["name"] for case in SSC01_PRODUCT_CASES])
def test_ssc01_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=71, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC01_PRODUCT_CASES, ids=[case["name"] for case in SSC01_PRODUCT_CASES])
def test_ssc01_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=71, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC01_PRODUCT_CASES, ids=[case["name"] for case in SSC01_PRODUCT_CASES])
def test_ssc01_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=71, instance_index=0)
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
