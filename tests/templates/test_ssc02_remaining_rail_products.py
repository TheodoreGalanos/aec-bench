# ABOUTME: Tests runnable SSC-02 product templates beyond the level-crossing baseline.
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

SSC02_PRODUCT_CASES = [
    {
        "name": "rail-braking-sighting-warning-time-corridor-package",
        "discipline": "electrical",
        "category": "rail-braking-sighting-warning",
        "product_id": "SSC-02-LH-01",
        "source_ids": [
            "ROUTE-02-PROFILE-01",
            "ROLL-02-DATA-01",
            "SIG-02-LAYOUT-01",
            "SIGHT-02-NOTE-01",
            "RULE-02-OPS-01",
            "MEMO-02-BRAKE-01",
        ],
        "expected": {
            "speed_m_s": 25.0,
            "davis_resistance_n_per_t": 48.2,
            "resistance_force_kn": 20.244,
            "effective_braking_deceleration_m_s2": 0.622,
            "braking_distance_m": 602.492,
            "sighting_time_s": 25.6,
            "sighting_margin_s": 18.6,
            "warning_strike_in_distance_m": 950.0,
            "warning_margin_s": 8.0,
            "overlap_margin_m": 167.508,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "ole-sag-thermal-stress-signal-clearance-package",
        "discipline": "electrical",
        "category": "ole-sag-clearance",
        "product_id": "SSC-02-LH-02",
        "source_ids": [
            "OLE-02-SPAN-02",
            "ROUTE-02-CLEAR-02",
            "WEATHER-02-TEMP-02",
            "WIRE-02-DATA-02",
            "CRIT-02-CLEAR-02",
            "MEMO-02-OLE-02",
        ],
        "expected": {
            "thermal_stress_mpa": 65.45,
            "thermal_tension_loss_kn": 9.818,
            "hot_tension_kn": 22.182,
            "sag_m": 0.26,
            "clearance_at_sag_m": 5.34,
            "clearance_margin_m": 0.24,
            "sag_margin_m": 0.19,
            "thermal_stress_margin_mpa": 24.55,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "rail-drainage-flood-clearance-speed-restriction-package",
        "discipline": "civil",
        "category": "rail-drainage-flood-restriction",
        "product_id": "SSC-02-LH-04",
        "source_ids": [
            "TRACK-02-DRAIN-04",
            "CULVERT-02-SCHED-04",
            "FLOOD-02-LEVEL-04",
            "WAYSIDE-02-LAYOUT-04",
            "OPS-02-FLOOD-04",
            "MEMO-02-FLOOD-04",
        ],
        "expected": {
            "peak_flow_m3_s": 1.729,
            "culvert_capacity_margin_m3_s": 0.671,
            "track_freeboard_m": 0.67,
            "freeboard_margin_m": 0.22,
            "equipment_freeboard_m": 0.37,
            "equipment_exposure_margin_m": 0.27,
            "speed_reduction_kmh": 50.0,
            "restriction_pass_score": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "route-profile-cant-rolling-stock-braking-package",
        "discipline": "civil",
        "category": "route-cant-braking",
        "product_id": "SSC-02-LH-05",
        "source_ids": [
            "ALIGN-02-PROFILE-05",
            "CANT-02-TABLE-05",
            "ROLL-02-DATA-05",
            "CRIT-02-COMFORT-05",
            "OPS-02-SCENARIO-05",
            "MEMO-02-ALIGN-05",
        ],
        "expected": {
            "speed_m_s": 23.611,
            "equilibrium_cant_mm": 125.459,
            "cant_deficiency_mm": 30.459,
            "cant_deficiency_margin_mm": 44.541,
            "cant_gradient_mm_per_m": 0.792,
            "cant_gradient_margin_mm_per_m": 0.208,
            "vertical_curve_length_m": 50.4,
            "effective_braking_deceleration_m_s2": 0.672,
            "braking_distance_m": 485.925,
            "davis_resistance_n_per_t": 39.138,
            "resistance_force_kn": 14.872,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "signal-overlap-approach-speed-sighting-photo-package",
        "discipline": "electrical",
        "category": "signal-overlap-sighting",
        "product_id": "SSC-02-LH-06",
        "source_ids": [
            "SIG-02-ARRANGE-06",
            "SPEED-02-APPROACH-06",
            "PHOTO-02-SIGHT-06",
            "GRADE-02-ROUTE-06",
            "CRIT-02-SIGHT-06",
            "MEMO-02-SIGHT-06",
        ],
        "expected": {
            "approach_speed_m_s": 27.778,
            "effective_braking_deceleration_m_s2": 0.731,
            "stopping_distance_m": 611.143,
            "sighting_time_s": 25.92,
            "sighting_time_margin_s": 17.92,
            "stopping_distance_margin_m": 108.857,
            "overlap_margin_m": 80.0,
            "photo_offset_m": 60.0,
            "photo_offset_margin_m": 20.0,
            "warning_distance_m": 972.222,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "wayside-cabinet-load-communications-backup-supply-package",
        "discipline": "electrical",
        "category": "wayside-cabinet-backup",
        "product_id": "SSC-02-LH-07",
        "source_ids": [
            "CAB-02-LAYOUT-07",
            "LOAD-02-DEVICE-07",
            "COMMS-02-TOPO-07",
            "UPS-02-DATA-07",
            "MAINT-02-RESPONSE-07",
            "MEMO-02-RESILIENCE-07",
        ],
        "expected": {
            "connected_load_w": 460.0,
            "design_load_w": 529.0,
            "required_energy_kwh": 5.29,
            "required_battery_capacity_ah": 153.067,
            "battery_capacity_margin_ah": 86.933,
            "feeder_current_a": 11.021,
            "feeder_voltage_drop_v": 1.389,
            "feeder_voltage_drop_percent": 2.893,
            "voltage_drop_margin_percent": 2.107,
            "fiber_total_loss_db": 3.16,
            "fiber_receive_power_dbm": -5.16,
            "fiber_link_margin_db": 18.84,
            "fiber_excess_margin_db": 15.84,
            "required_ups_rating_va": 587.778,
            "ups_rating_margin_va": 612.222,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "rail-standards-conflict-operator-review-package",
        "discipline": "electrical",
        "category": "rail-standards-review",
        "product_id": "SSC-02-LH-08",
        "source_ids": [
            "STD-02-MATRIX-08",
            "COMMENT-02-REGISTER-08",
            "ALIGN-02-SIGNAL-08",
            "CALC-02-EXTRACT-08",
            "EXCEPT-02-APPROVAL-08",
            "RESPONSE-02-AUTH-08",
        ],
        "expected": {
            "standard_selection_fraction": 0.8,
            "comment_resolution_fraction": 1.0,
            "calculation_update_fraction": 0.833,
            "exception_resolution_fraction": 1.0,
            "source_trace_score": 0.9,
            "response_completeness_score": 0.9,
            "operator_review_score": 0.906,
            "open_comments": 0.0,
            "critical_open_comments": 0.0,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC02_PRODUCT_CASES, ids=[case["name"] for case in SSC02_PRODUCT_CASES])
def test_ssc02_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC02_PRODUCT_CASES, ids=[case["name"] for case in SSC02_PRODUCT_CASES])
def test_ssc02_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=78, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC02_PRODUCT_CASES, ids=[case["name"] for case in SSC02_PRODUCT_CASES])
def test_ssc02_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=78, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC02_PRODUCT_CASES, ids=[case["name"] for case in SSC02_PRODUCT_CASES])
def test_ssc02_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=78, instance_index=0)
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
