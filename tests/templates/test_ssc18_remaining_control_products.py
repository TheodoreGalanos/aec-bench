# ABOUTME: Tests runnable SSC-18 product templates beyond the control-loop baseline.
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

SSC18_PRODUCT_CASES = [
    {
        "name": "stormwater-treatment-telemetry-control-package",
        "discipline": "electrical",
        "category": "telemetry-control",
        "product_id": "SSC-18-LH-02",
        "source_ids": [
            "SENSOR-18-SCHED-02",
            "LEVEL-18-TABLE-02",
            "NARR-18-CTRL-02",
            "COMMS-18-TOPO-02",
            "PWR-18-SCHED-02",
            "MEMO-18-TEL-02",
        ],
        "expected": {
            "level_span_m": 5.0,
            "current_signal_ma": 14.24,
            "high_level_current_ma": 17.44,
            "pump_start_current_ma": 15.2,
            "pump_stop_current_ma": 7.84,
            "sensor_accuracy_m": 0.013,
            "pump_start_margin_m": 0.3,
            "telemetry_load_w": 143.0,
            "backup_energy_required_kwh": 1.907,
            "battery_usable_kwh": 2.304,
            "backup_energy_margin_kwh": 0.397,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "protection-control-sld-bridge-package",
        "discipline": "electrical",
        "category": "protection-control",
        "product_id": "SSC-18-LH-03",
        "source_ids": [
            "SLD-18-FEEDER-03",
            "SET-18-PROT-03",
            "CT-18-DATA-03",
            "LOOP-18-SCHED-03",
            "FAULT-18-TABLE-03",
            "MEMO-18-SET-03",
        ],
        "expected": {
            "ct_secondary_current_a": 3.333,
            "measurement_signal_ma": 14.667,
            "pickup_signal_ma": 17.333,
            "pickup_margin_a": 100.0,
            "fault_pickup_ratio": 17.0,
            "feeder_load_margin_a": 180.0,
            "ct_error_current_a": 2.0,
            "trip_signal_headroom_ma": 2.667,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "commissioning-calibration-review-package",
        "discipline": "electrical",
        "category": "commissioning-calibration",
        "product_id": "SSC-18-LH-04",
        "source_ids": [
            "CHECK-18-COMM-04",
            "CAL-18-SHEET-04",
            "VDS-18-FCV-04",
            "LOOP-18-SCHED-04",
            "CRIT-18-ACCEPT-04",
            "RESPONSE-18-COMM-04",
        ],
        "expected": {
            "ideal_signal_ma": 13.173,
            "calibration_error_ma": -0.073,
            "calibration_error_pct_span": 0.458,
            "calibration_margin_ma": 0.127,
            "loop_check_pass_fraction": 1.0,
            "failed_point_count": 0.0,
            "process_acceptance_margin": 1.8,
            "valve_cv_headroom": 6.536,
            "commissioning_completeness_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "chemical-dosing-flowmeter-control-package",
        "discipline": "electrical",
        "category": "dosing-control",
        "product_id": "SSC-18-LH-05",
        "source_ids": [
            "DOSE-18-BASIS-05",
            "FLOW-18-DATA-05",
            "PUMP-18-SCHED-05",
            "RANGE-18-LOOP-05",
            "ALM-18-DOSE-05",
            "MEMO-18-DOSE-05",
        ],
        "expected": {
            "active_dose_kg_d": 35.7,
            "solution_volume_l_d": 259.636,
            "dosing_pump_flow_l_h": 12.982,
            "pump_capacity_margin_l_h": 3.018,
            "flowmeter_signal_ma": 14.385,
            "high_alarm_current_ma": 16.8,
            "alarm_headroom_ma": 2.415,
            "pump_current_a": 0.992,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "fire-pump-pressure-signal-alarm-package",
        "discipline": "electrical",
        "category": "fire-pump-alarm",
        "product_id": "SSC-18-LH-06",
        "source_ids": [
            "FIRE-18-PUMP-06",
            "PRESS-18-SENSOR-06",
            "ALM-18-THRESH-06",
            "NAC-18-LOAD-06",
            "CRIT-18-FIRE-06",
            "MEMO-18-FIRE-06",
        ],
        "expected": {
            "pressure_signal_ma": 12.32,
            "low_alarm_current_ma": 10.72,
            "pump_start_current_ma": 11.2,
            "low_alarm_margin_kpa": 100.0,
            "pump_start_margin_kpa": 70.0,
            "nac_load_a": 1.8,
            "nac_panel_margin_a": 1.2,
            "battery_required_kwh": 2.708,
            "battery_margin_kwh": 0.292,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "valve-failure-safe-state-repair-package",
        "discipline": "electrical",
        "category": "safe-state-repair",
        "product_id": "SSC-18-LH-07",
        "source_ids": [
            "PID-18-FAIL-07",
            "VDS-18-FAIL-07",
            "LOOP-18-FAIL-07",
            "MODE-18-FAIL-07",
            "NARR-18-SAFE-07",
            "RESPONSE-18-FAIL-07",
        ],
        "expected": {
            "failed_signal_margin_ma": 0.2,
            "fail_closed_cv_margin": 1.0,
            "bypass_cv_margin": 2.0,
            "safe_flow_margin_m3_h": 3.0,
            "safe_runtime_h": 6.667,
            "safe_runtime_margin_h": 0.667,
            "source_resolution_fraction": 1.0,
            "unresolved_conflict_count": 0.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "instrumentation-source-policy-extension-package",
        "discipline": "electrical",
        "category": "instrumentation-source-policy",
        "product_id": "SSC-18-LH-08",
        "source_ids": [
            "INDEX-18-SOURCE-08",
            "PID-18-LOOP-08",
            "LINK-18-TABLE-08",
            "CASE-18-VERIFY-08",
            "GAP-18-REGISTER-08",
            "MEMO-18-EXT-08",
        ],
        "expected": {
            "source_traceability_fraction": 1.0,
            "linked_table_update_fraction": 1.0,
            "gap_documentation_fraction": 1.0,
            "verification_case_pass_fraction": 1.0,
            "min_cross_domain_margin": 0.8,
            "authority_partition_fraction": 1.0,
            "unresolved_conflict_count": 0.0,
            "extension_memo_completeness_fraction": 0.95,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC18_PRODUCT_CASES, ids=[case["name"] for case in SSC18_PRODUCT_CASES])
def test_ssc18_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC18_PRODUCT_CASES, ids=[case["name"] for case in SSC18_PRODUCT_CASES])
def test_ssc18_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=90, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC18_PRODUCT_CASES, ids=[case["name"] for case in SSC18_PRODUCT_CASES])
def test_ssc18_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=90, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC18_PRODUCT_CASES, ids=[case["name"] for case in SSC18_PRODUCT_CASES])
def test_ssc18_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=90, instance_index=0)
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
