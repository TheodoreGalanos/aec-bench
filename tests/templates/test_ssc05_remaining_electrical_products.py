# ABOUTME: Tests runnable SSC-05 product templates beyond the mechanical-load feeder baseline.
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

SSC05_PRODUCT_CASES = [
    {
        "name": "pv-bess-interconnection-export-control-package",
        "discipline": "electrical",
        "category": "pv-bess-export-control",
        "product_id": "SSC-05-LH-02",
        "source_ids": [
            "PV-05-MOD-02",
            "INV-05-DATA-02",
            "BESS-05-DATA-02",
            "PCC-05-SLD-02",
            "RULE-05-EXPORT-02",
            "MEMO-05-INTERCON-02",
        ],
        "expected": {
            "pv_ac_output_kw": 148.5,
            "export_kw": 86.5,
            "export_excess_kw": 11.5,
            "usable_bess_energy_kwh": 273.972,
            "backup_energy_required_kwh": 270.0,
            "backup_energy_margin_kwh": 3.972,
            "feeder_current_a": 188.019,
            "feeder_voltage_drop_percent": 3.447,
            "voltage_drop_excess_percent": 0.447,
            "breaker_margin_a": 11.981,
            "overall_pass_score": 0.0,
        },
    },
    {
        "name": "switchboard-fault-arcflash-earthing-package",
        "discipline": "electrical",
        "category": "switchboard-fault-arcflash-earthing",
        "product_id": "SSC-05-LH-03",
        "source_ids": [
            "SLD-05-SWBD-03",
            "FAULT-05-STUDY-03",
            "RELAY-05-SET-03",
            "EARTH-05-SOIL-03",
            "LAYOUT-05-SWBD-03",
            "NOTE-05-SAFETY-03",
        ],
        "expected": {
            "utility_fault_current_ka": 34.78,
            "total_fault_current_ka": 45.08,
            "fault_rating_margin_ka": 4.92,
            "incident_energy_cal_cm2": 4.929,
            "incident_energy_margin_cal_cm2": 3.071,
            "touch_voltage_v": 450.801,
            "touch_voltage_margin_v": 49.199,
            "busbar_force_kn": 4.064,
            "busbar_force_margin_kn": 5.936,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "fire-life-safety-communications-load-package",
        "discipline": "electrical",
        "category": "life-safety-comms-load",
        "product_id": "SSC-05-LH-04",
        "source_ids": [
            "FIRE-05-LOAD-04",
            "CCTV-05-DEVICE-04",
            "COMMS-05-TOPO-04",
            "UPS-05-DATA-04",
            "CRIT-05-EMERG-04",
            "MEMO-05-LIFE-04",
        ],
        "expected": {
            "life_safety_load_kw": 1.56,
            "communications_load_kw": 1.98,
            "total_essential_load_kw": 3.54,
            "battery_required_kwh": 19.824,
            "usable_battery_kwh": 21.06,
            "battery_margin_kwh": 1.236,
            "nac_current_a": 9.1,
            "nac_margin_a": 2.9,
            "feeder_current_a": 14.16,
            "feeder_margin_a": 5.84,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "pump-station-mcc-cable-protection-package",
        "discipline": "electrical",
        "category": "pump-station-mcc-protection",
        "product_id": "SSC-05-LH-05",
        "source_ids": [
            "PUMP-05-SCHED-05",
            "MCC-05-SLD-05",
            "CABLE-05-PUMP-05",
            "PROT-05-SET-05",
            "DUTY-05-BASIS-05",
            "MEMO-05-POWER-05",
        ],
        "expected": {
            "running_current_a": 81.697,
            "starting_current_a": 408.485,
            "derated_cable_ampacity_a": 112.056,
            "ampacity_margin_a": 30.359,
            "voltage_drop_percent": 3.057,
            "voltage_drop_margin_percent": 0.943,
            "overload_setting_margin_a": 17.303,
            "short_circuit_margin_ka": 2.8,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "poe-fibre-field-cabinet-power-package",
        "discipline": "electrical",
        "category": "poe-fibre-field-cabinet",
        "product_id": "SSC-05-LH-06",
        "source_ids": [
            "DEVICE-05-SCHED-06",
            "NET-05-TOPO-06",
            "POE-05-SWITCH-06",
            "FIBRE-05-PATH-06",
            "UPS-05-CAB-06",
            "MEMO-05-CABINET-06",
        ],
        "expected": {
            "poe_load_w": 524.0,
            "poe_budget_margin_w": 146.0,
            "usable_ups_energy_kwh": 2.196,
            "ups_runtime_hr": 3.437,
            "runtime_margin_hr": 1.437,
            "cabinet_heat_w": 704.0,
            "cabinet_temp_rise_c": 8.8,
            "temperature_margin_c": 6.2,
            "fibre_loss_db": 5.35,
            "optical_margin_db": 4.65,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "regional-load-flow-voltage-regulation-package",
        "discipline": "electrical",
        "category": "regional-load-flow-voltage",
        "product_id": "SSC-05-LH-07",
        "source_ids": [
            "SLD-05-FEEDER-07",
            "LOAD-05-SCENARIO-07",
            "CABLE-05-FEEDER-07",
            "CRIT-05-VOLT-07",
            "COMMENT-05-REVIEW-07",
            "MEMO-05-RESPONSE-07",
        ],
        "expected": {
            "peak_load_kw": 1225.0,
            "transformer_loading_percent": 93.085,
            "transformer_margin_percent": 6.915,
            "feeder_current_a": 180.865,
            "voltage_drop_percent": 9.974,
            "regulated_voltage_pu": 0.965,
            "minimum_voltage_margin_pu": 0.025,
            "required_pfc_kvar": 195.869,
            "feeder_loss_kw": 29.061,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "electrical-source-policy-product-datasheet-package",
        "discipline": "electrical",
        "category": "electrical-source-policy-datasheet",
        "product_id": "SSC-05-LH-08",
        "source_ids": [
            "DATA-05-PRODUCT-08",
            "CERT-05-LISTING-08",
            "RATING-05-TABLE-08",
            "CALC-05-WORKSHEET-08",
            "SUBMIT-05-REGISTER-08",
            "RESPONSE-05-SUBMITTAL-08",
        ],
        "expected": {
            "datasheet_completeness_fraction": 0.9,
            "source_trace_score": 0.857,
            "derated_product_current_a": 212.16,
            "breaker_rating_margin_a": 52.16,
            "cable_rating_margin_a": 35.0,
            "voltage_drop_margin_percent": 0.9,
            "protection_setting_margin_percent": 8.0,
            "open_comments": 2.0,
            "critical_open_comments": 0.0,
            "response_completeness_score": 0.92,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC05_PRODUCT_CASES, ids=[case["name"] for case in SSC05_PRODUCT_CASES])
def test_ssc05_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC05_PRODUCT_CASES, ids=[case["name"] for case in SSC05_PRODUCT_CASES])
def test_ssc05_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=77, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC05_PRODUCT_CASES, ids=[case["name"] for case in SSC05_PRODUCT_CASES])
def test_ssc05_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=77, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC05_PRODUCT_CASES, ids=[case["name"] for case in SSC05_PRODUCT_CASES])
def test_ssc05_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=77, instance_index=0)
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
