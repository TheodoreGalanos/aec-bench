# ABOUTME: Tests runnable SSC-13 product templates beyond the road visual baseline.
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

SSC13_PRODUCT_CASES = [
    {
        "name": "station-building-security-lighting-package",
        "discipline": "electrical",
        "category": "security-lighting",
        "product_id": "SSC-13-LH-02",
        "source_ids": [
            "PLAN-13-ROOM-02",
            "LIGHT-13-GRID-02",
            "CCTV-13-CAM-02",
            "ACCESS-13-CTRL-02",
            "NET-13-TOPO-02",
            "MEMO-13-SECURITY-02",
        ],
        "expected": {
            "average_illuminance_lux": 204.333,
            "minimum_illuminance_lux": 196.0,
            "uniformity_ratio": 0.959,
            "illuminance_margin_lux": 44.333,
            "cctv_pixels_per_m": 160.0,
            "cctv_ppm_margin": 40.0,
            "network_load_mbps": 25.3,
            "network_headroom_mbps": 24.7,
            "poe_load_w": 74.0,
            "poe_headroom_w": 46.0,
            "coverage_match_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "sports-field-lighting-power-uniformity-package",
        "discipline": "electrical",
        "category": "field-lighting",
        "product_id": "SSC-13-LH-03",
        "source_ids": [
            "FIELD-13-LAYOUT-03",
            "LUM-13-SCHED-03",
            "GRID-13-CALC-03",
            "POWER-13-SCHED-03",
            "CTRL-13-MODE-03",
            "MEMO-13-FIELD-03",
        ],
        "expected": {
            "average_illuminance_lux": 528.75,
            "minimum_illuminance_lux": 512.0,
            "uniformity_ratio": 0.968,
            "average_illuminance_margin_lux": 28.75,
            "uniformity_margin": 0.268,
            "connected_load_kw": 12.72,
            "event_energy_kwh": 57.24,
            "feeder_current_a": 19.957,
            "feeder_current_margin_a": 12.043,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "remote-its-backup-communications-package",
        "discipline": "electrical",
        "category": "its-communications",
        "product_id": "SSC-13-LH-04",
        "source_ids": [
            "DEV-13-INV-04",
            "RF-13-LINK-04",
            "FIB-13-TOPO-04",
            "BW-13-TABLE-04",
            "PWR-13-BAT-04",
            "MEMO-13-REMOTE-04",
        ],
        "expected": {
            "rf_received_power_dbm": -61.0,
            "rf_fade_margin_db": 21.0,
            "fibre_loss_db": 3.24,
            "fibre_margin_db": 14.76,
            "network_load_mbps": 13.5,
            "network_headroom_mbps": 16.5,
            "poe_load_w": 51.0,
            "poe_headroom_w": 39.0,
            "battery_required_kwh": 2.471,
            "battery_margin_kwh": 0.729,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "vms-message-legibility-power-package",
        "discipline": "electrical",
        "category": "vms-operations",
        "product_id": "SSC-13-LH-05",
        "source_ids": [
            "VMS-13-SCHED-05",
            "MSG-13-LIB-05",
            "ROAD-13-SPEED-05",
            "NET-13-TOPO-05",
            "PWR-13-SCHED-05",
            "MEMO-13-VMS-05",
        ],
        "expected": {
            "required_legibility_distance_m": 192.0,
            "legibility_distance_margin_m": 33.0,
            "available_read_time_s": 10.125,
            "read_time_margin_s": 3.625,
            "vms_power_load_w": 760.0,
            "power_headroom_w": 440.0,
            "network_load_mbps": 3.2,
            "network_headroom_mbps": 6.8,
            "message_policy_match_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "cctv-coverage-pixel-storage-package",
        "discipline": "electrical",
        "category": "cctv-coverage-storage",
        "product_id": "SSC-13-LH-06",
        "source_ids": [
            "CCTV-13-PLAN-06",
            "TARGET-13-LIST-06",
            "CAM-13-DATA-06",
            "REC-13-POL-06",
            "NET-13-PWR-06",
            "MEMO-13-CCTV-06",
        ],
        "expected": {
            "camera_01_pixels_per_m": 149.333,
            "camera_02_pixels_per_m": 122.182,
            "camera_03_pixels_per_m": 168.0,
            "minimum_pixels_per_m": 122.182,
            "ppm_margin": 22.182,
            "coverage_match_fraction": 1.0,
            "storage_required_tb": 6.707,
            "network_load_mbps": 21.6,
            "network_headroom_mbps": 28.4,
            "poe_load_w": 52.0,
            "poe_headroom_w": 38.0,
            "fibre_margin_db": 12.92,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "lighting-energy-emergency-mode-package",
        "discipline": "electrical",
        "category": "lighting-energy",
        "product_id": "SSC-13-LH-07",
        "source_ids": [
            "LIGHT-13-LAYOUT-07",
            "CTRL-13-SCHED-07",
            "LENI-13-PROFILE-07",
            "EMERG-13-LOAD-07",
            "CRIT-13-TABLE-07",
            "MEMO-13-ENERGY-07",
        ],
        "expected": {
            "average_illuminance_lux": 173.5,
            "minimum_illuminance_lux": 168.0,
            "uniformity_ratio": 0.968,
            "illuminance_margin_lux": 23.5,
            "emergency_illuminance_margin_lux": 2.0,
            "annual_lighting_energy_kwh": 1572.48,
            "leni_kwh_m2_year": 3.494,
            "leni_margin_kwh_m2_year": 1.506,
            "emergency_battery_required_kwh": 0.452,
            "emergency_battery_margin_kwh": 0.348,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "visual-systems-review-repair-package",
        "discipline": "electrical",
        "category": "visual-systems-review",
        "product_id": "SSC-13-LH-08",
        "source_ids": [
            "REVIEW-13-COMMENTS-08",
            "LAYOUT-13-REV-08",
            "DEVICE-13-SCHED-08",
            "CALC-13-TRACE-08",
            "CRIT-13-MATRIX-08",
            "RESPONSE-13-REPAIR-08",
        ],
        "expected": {
            "review_comment_closure_fraction": 1.0,
            "affected_check_update_fraction": 1.0,
            "lighting_minimum_margin_lux": 1.1,
            "revised_cctv_pixels_per_m": 80.0,
            "cctv_ppm_margin": 10.0,
            "network_headroom_mbps": 12.0,
            "poe_headroom_w": 28.0,
            "unresolved_conflict_count": 0.0,
            "repair_memo_completeness_fraction": 0.9,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC13_PRODUCT_CASES, ids=[case["name"] for case in SSC13_PRODUCT_CASES])
def test_ssc13_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC13_PRODUCT_CASES, ids=[case["name"] for case in SSC13_PRODUCT_CASES])
def test_ssc13_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=87, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC13_PRODUCT_CASES, ids=[case["name"] for case in SSC13_PRODUCT_CASES])
def test_ssc13_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=87, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC13_PRODUCT_CASES, ids=[case["name"] for case in SSC13_PRODUCT_CASES])
def test_ssc13_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=87, instance_index=0)
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
