# ABOUTME: Tests runnable SSC-10 product templates beyond the wastewater energy island baseline.
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

SSC10_PRODUCT_CASES = [
    {
        "name": "aeration-blower-process-power-acoustic-package",
        "discipline": "mechanical",
        "category": "aeration-blower-acoustic",
        "product_id": "SSC-10-LH-02",
        "source_ids": [
            "SAMPLE-10-AER-02",
            "CRITERIA-10-AER-02",
            "BLOWER-10-DATA-02",
            "MOTOR-10-SCHED-02",
            "RECEIVER-10-PLAN-02",
            "MEMO-10-AER-02",
        ],
        "expected": {
            "bod_removed_kg_d": 1426.0,
            "nitrogen_removed_kg_d": 235.6,
            "oxygen_demand_kg_d": 1139.78,
            "required_airflow_m3_min": 16.869,
            "blower_oxygen_capacity_margin_kg_d": 2778.978,
            "blower_input_power_kw": 29.477,
            "motor_margin_kw": 65.523,
            "combined_source_spl_dba": 84.436,
            "receiver_spl_dba": 45.848,
            "acoustic_margin_db": 9.152,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "chemical-dosing-storage-containment-package",
        "discipline": "mechanical",
        "category": "chemical-dosing-containment",
        "product_id": "SSC-10-LH-03",
        "source_ids": [
            "FLOW-10-CHEM-03",
            "DOSE-10-BASIS-03",
            "TANK-10-STORAGE-03",
            "BUND-10-DETAIL-03",
            "PUMP-10-CONTROL-03",
            "MEMO-10-CHEM-03",
        ],
        "expected": {
            "chemical_mass_kg_d": 182.4,
            "solution_volume_l_d": 380.0,
            "required_storage_m3": 6.84,
            "refill_margin_d": 2.526,
            "bund_required_m3": 6.85,
            "bund_margin_m3": 1.35,
            "dosing_pump_flow_l_h": 19.0,
            "pump_capacity_margin_l_h": 3.0,
            "design_signal_ma": 14.133,
            "signal_headroom_ma": 5.867,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "instrumented-process-control-valve-package",
        "discipline": "mechanical",
        "category": "process-control-valve",
        "product_id": "SSC-10-LH-04",
        "source_ids": [
            "PID-10-VALVE-04",
            "LOOP-10-SCHED-04",
            "VALVE-10-DATA-04",
            "RANGE-10-PV-04",
            "CONTROL-10-NARR-04",
            "MEMO-10-INST-04",
        ],
        "expected": {
            "required_cv": 124.348,
            "cv_margin": 20.652,
            "valve_authority_ratio": 0.688,
            "command_signal_ma": 15.2,
            "signal_error_ma": 0.0,
            "fail_close_margin_s": 5.0,
            "basin_hrt_hr": 5.482,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "clarifier-sludge-hydraulic-constraint-package",
        "discipline": "mechanical",
        "category": "clarifier-sludge-hydraulics",
        "product_id": "SSC-10-LH-05",
        "source_ids": [
            "CLAR-10-SCHED-05",
            "SAMPLE-10-LOAD-05",
            "SLUDGE-10-WASTE-05",
            "HGL-10-PROFILE-05",
            "PERMIT-10-CRIT-05",
            "MEMO-10-CLAR-05",
        ],
        "expected": {
            "surface_overflow_rate_m3_m2_d": 15.915,
            "sor_margin_m3_m2_d": 14.085,
            "solids_loading_kg_m2_d": 50.93,
            "slr_margin_kg_m2_d": 69.07,
            "bod_removed_kg_d": 1476.0,
            "sludge_production_kg_d": 915.12,
            "wasting_capacity_margin_kg_d": 64.88,
            "sludge_blanket_margin_m": 0.28,
            "clarifier_hrt_hr": 5.333,
            "hrt_margin_hr": 2.333,
            "recycle_flow_m3_d": 2520.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "wet-weather-process-bypass-resilience-package",
        "discipline": "mechanical",
        "category": "wet-weather-bypass-resilience",
        "product_id": "SSC-10-LH-06",
        "source_ids": [
            "WET-10-INFLOW-06",
            "UNIT-10-SCHED-06",
            "PUMP-10-STORAGE-06",
            "CONTROL-10-RULES-06",
            "PERMIT-10-BYPASS-06",
            "MEMO-10-WET-06",
        ],
        "expected": {
            "required_storage_m3": 1050.0,
            "storage_margin_m3": 50.0,
            "reactor_hrt_hr": 3.214,
            "hrt_margin_hr": 0.014,
            "clarifier_peak_sor_m3_m2_d": 51.692,
            "sor_margin_m3_m2_d": 6.308,
            "pump_input_power_kw": 63.811,
            "outage_energy_kwh": 159.528,
            "usable_backup_energy_kwh": 220.936,
            "backup_energy_margin_kwh": 61.408,
            "bypass_volume_m3": 0.0,
            "bypass_margin_m3": 0.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "biogas-sludge-generator-dispatch-package",
        "discipline": "mechanical",
        "category": "biogas-generator-dispatch",
        "product_id": "SSC-10-LH-07",
        "source_ids": [
            "SLUDGE-10-PROD-07",
            "DIGESTER-10-GAS-07",
            "GEN-10-DATA-07",
            "LOAD-10-PROFILE-07",
            "POLICY-10-DISPATCH-07",
            "MEMO-10-DISPATCH-07",
        ],
        "expected": {
            "volatile_solids_feed_kg_d": 873.2,
            "volatile_solids_destroyed_kg_d": 454.064,
            "biogas_m3_d": 417.739,
            "methane_m3_d": 263.175,
            "methane_energy_kwh_d": 2623.86,
            "generator_electric_energy_kwh_d": 944.589,
            "average_generator_kw": 39.358,
            "generator_capacity_margin_kw": 82.0,
            "critical_dispatch_energy_kwh": 688.0,
            "dispatch_energy_margin_kwh": 256.589,
            "available_runtime_hr": 9.639,
            "heat_recovery_kwh_d": 1154.498,
            "heat_recovery_margin_kwh_d": 104.498,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "treatment-review-permit-basis-package",
        "discipline": "mechanical",
        "category": "treatment-permit-review",
        "product_id": "SSC-10-LH-08",
        "source_ids": [
            "PERMIT-10-CRIT-08",
            "SAMPLE-10-DATA-08",
            "CALC-10-APPX-08",
            "COMMENT-10-REG-08",
            "AUTH-10-MATRIX-08",
            "MEMO-10-PERMIT-08",
        ],
        "expected": {
            "required_srt_d": 6.753,
            "srt_margin_d": 2.447,
            "bod_permit_margin_mg_l": 7.0,
            "ammonia_permit_margin_mg_l": 1.1,
            "oxygen_capacity_margin_kg_d": 125.0,
            "chemical_capacity_margin_kg_d": 38.0,
            "sludge_capacity_margin_kg_d": 130.0,
            "comments_resolved_fraction": 0.889,
            "source_completeness_fraction": 0.929,
            "response_completeness_score": 0.939,
            "critical_comments_open": 0.0,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC10_PRODUCT_CASES, ids=[case["name"] for case in SSC10_PRODUCT_CASES])
def test_ssc10_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC10_PRODUCT_CASES, ids=[case["name"] for case in SSC10_PRODUCT_CASES])
def test_ssc10_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=76, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC10_PRODUCT_CASES, ids=[case["name"] for case in SSC10_PRODUCT_CASES])
def test_ssc10_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=76, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC10_PRODUCT_CASES, ids=[case["name"] for case in SSC10_PRODUCT_CASES])
def test_ssc10_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=76, instance_index=0)
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
