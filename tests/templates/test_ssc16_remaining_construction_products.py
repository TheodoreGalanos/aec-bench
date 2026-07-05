# ABOUTME: Tests runnable SSC-16 product templates beyond the construction controls baseline.
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

SSC16_PRODUCT_CASES = [
    {
        "name": "temporary-works-wind-structural-staging-package",
        "discipline": "structural",
        "category": "temporary-works",
        "product_id": "SSC-16-LH-02",
        "source_ids": [
            "STAGE-16-WIND-02",
            "TEMP-16-STRUCT-02",
            "WIND-16-CRIT-02",
            "SUPPORT-16-SCHED-02",
            "TOL-16-CHECK-02",
            "MEMO-16-TEMPWORKS-02",
        ],
        "expected": {
            "site_wind_speed_m_s": 29.07,
            "wind_pressure_kpa": 0.507,
            "temporary_panel_wind_force_kn": 21.093,
            "anchor_demand_kn": 6.592,
            "anchor_capacity_margin_kn": 5.408,
            "overturning_moment_knm": 50.623,
            "stability_ratio": 1.391,
            "stability_margin": 0.191,
            "slot_length_margin_mm": 13.0,
            "inspection_tolerance_margin_mm": 3.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "dewatering-settlement-temporary-power-package",
        "discipline": "civil",
        "category": "dewatering-temporary-power",
        "product_id": "SSC-16-LH-03",
        "source_ids": [
            "EXC-16-PLAN-03",
            "GW-16-REC-03",
            "SETTLE-16-MON-03",
            "PUMP-16-SCHED-03",
            "POWER-16-LAYOUT-03",
            "MEMO-16-DEWATER-03",
        ],
        "expected": {
            "dewatering_flow_l_s": 14.976,
            "pump_hydraulic_power_kw": 2.644,
            "pump_input_power_kw": 4.739,
            "generator_headroom_kw": 7.261,
            "predicted_settlement_mm": 16.8,
            "settlement_margin_mm": 8.2,
            "battery_required_kwh": 30.535,
            "battery_margin_kwh": 5.465,
            "feeder_current_a": 23.415,
            "voltage_drop_percent": 0.358,
            "voltage_drop_margin_percent": 4.642,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "staged-road-its-relocation-package",
        "discipline": "electrical",
        "category": "road-its-relocation",
        "product_id": "SSC-16-LH-04",
        "source_ids": [
            "TTC-16-PLAN-04",
            "DEVICE-16-RELOC-04",
            "SIGNAL-16-TIMING-04",
            "NET-16-TOPO-04",
            "POWER-16-SCHED-04",
            "MEMO-16-STAGEOPS-04",
        ],
        "expected": {
            "pedestrian_clearance_time_s": 18.0,
            "pedestrian_clearance_margin_s": 4.0,
            "required_vms_legibility_distance_m": 192.0,
            "vms_legibility_margin_m": 33.0,
            "network_load_mbps": 8.4,
            "network_headroom_mbps": 11.6,
            "poe_load_w": 47.0,
            "poe_headroom_w": 43.0,
            "battery_required_kwh": 4.216,
            "battery_margin_kwh": 1.284,
            "detour_delay_margin_s": 13.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "sediment-basin-storm-readiness-package",
        "discipline": "civil",
        "category": "storm-event-readiness",
        "product_id": "SSC-16-LH-05",
        "source_ids": [
            "CATCH-16-STAGE-05",
            "STORM-16-EVENT-05",
            "BASIN-16-DETAIL-05",
            "INSP-16-CHECK-05",
            "DISCH-16-CRIT-05",
            "MEMO-16-READY-05",
        ],
        "expected": {
            "runoff_volume_m3": 1107.0,
            "required_basin_volume_m3": 1287.0,
            "basin_headroom_m3": 163.0,
            "weir_capacity_m3_s": 1.232,
            "weir_capacity_margin_m3_s": 0.282,
            "freeboard_margin_m": 0.2,
            "drawdown_time_h": 19.861,
            "drawdown_margin_h": 4.139,
            "tss_load_kg": 243.54,
            "inspection_window_margin_h": 6.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "temporary-fuel-chemical-bund-fire-interface-package",
        "discipline": "mechanical",
        "category": "site-safety",
        "product_id": "SSC-16-LH-06",
        "source_ids": [
            "STORE-16-LAYOUT-06",
            "INV-16-FUEL-06",
            "BUND-16-DETAIL-06",
            "FIRE-16-NOTE-06",
            "ALARM-16-LOAD-06",
            "MEMO-16-SAFETY-06",
        ],
        "expected": {
            "required_bund_volume_l": 3100.0,
            "bund_volume_margin_l": 500.0,
            "fire_hrr_kw": 2701.44,
            "visibility_margin_m": 4.0,
            "nac_current_a": 1.09,
            "nac_headroom_a": 0.91,
            "alarm_battery_required_kwh": 2.28,
            "alarm_battery_margin_kwh": 0.72,
            "drain_isolation_fraction": 1.0,
            "spill_response_margin_min": 12.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "construction-monitoring-network-continuity-package",
        "discipline": "electrical",
        "category": "monitoring-network",
        "product_id": "SSC-16-LH-07",
        "source_ids": [
            "MON-16-LAYOUT-07",
            "SENSOR-16-SCHED-07",
            "NET-16-TOPO-07",
            "BAT-16-SOLAR-07",
            "REPORT-16-RULE-07",
            "MEMO-16-MONITOR-07",
        ],
        "expected": {
            "sensor_data_load_mbps": 10.0,
            "network_headroom_mbps": 15.0,
            "rf_received_power_dbm": -63.0,
            "rf_fade_margin_db": 19.0,
            "poe_load_w": 68.0,
            "poe_headroom_w": 52.0,
            "battery_required_kwh": 2.448,
            "battery_margin_kwh": 0.272,
            "solar_daily_headroom_wh": 672.0,
            "voltage_drop_percent": 0.496,
            "voltage_drop_margin_percent": 4.504,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "staging-review-response-negative-case-package",
        "discipline": "civil",
        "category": "staging-review",
        "product_id": "SSC-16-LH-08",
        "source_ids": [
            "REVIEW-16-COMMENTS-08",
            "STAGE-16-REV-08",
            "CONTROL-16-SCHED-08",
            "DEVICE-16-INV-08",
            "CRIT-16-MATRIX-08",
            "RESPONSE-16-REPAIR-08",
        ],
        "expected": {
            "review_comment_closure_fraction": 1.0,
            "affected_check_update_fraction": 1.0,
            "stage_source_match_fraction": 1.0,
            "sediment_basin_margin_m3": 85.0,
            "traffic_device_delta_count": 0.0,
            "power_headroom_w": 160.0,
            "tolerance_margin_mm": 6.0,
            "unresolved_conflict_count": 0.0,
            "repair_ledger_completeness_fraction": 0.92,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC16_PRODUCT_CASES, ids=[case["name"] for case in SSC16_PRODUCT_CASES])
def test_ssc16_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC16_PRODUCT_CASES, ids=[case["name"] for case in SSC16_PRODUCT_CASES])
def test_ssc16_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=88, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC16_PRODUCT_CASES, ids=[case["name"] for case in SSC16_PRODUCT_CASES])
def test_ssc16_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=88, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC16_PRODUCT_CASES, ids=[case["name"] for case in SSC16_PRODUCT_CASES])
def test_ssc16_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=88, instance_index=0)
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
