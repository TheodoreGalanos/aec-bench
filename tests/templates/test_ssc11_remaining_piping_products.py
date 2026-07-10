# ABOUTME: Tests runnable SSC-11 product templates beyond the first pump transient package.
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

SSC11_PRODUCT_CASES = [
    {
        "name": "fire-main-hydraulic-seismic-support-package",
        "discipline": "mechanical",
        "category": "fire-protection",
        "product_id": "SSC-11-LH-02",
        "source_ids": [
            "FIRE-SSC11-002",
            "FLOW-SSC11-002",
            "SUP-SSC11-002",
            "PUMP-SSC11-002",
            "MEMO-SSC11-002",
        ],
        "expected": {
            "hazen_williams_loss_m": 2.512,
            "friction_loss_kpa": 24.644,
            "remote_flow_demand_l_s": 12.667,
            "fire_flow_margin_l_s": 19.333,
            "remote_pressure_kpa": 491.971,
            "remote_pressure_margin_kpa": 351.971,
            "support_line_load_kn_m": 0.46,
            "support_vertical_reaction_kn": 1.931,
            "seismic_horizontal_reaction_kn": 0.579,
            "support_vertical_utilization": 0.227,
            "support_horizontal_utilization": 0.193,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "process-piping-valve-control-package",
        "discipline": "mechanical",
        "category": "process-piping",
        "product_id": "SSC-11-LH-03",
        "source_ids": [
            "PID-SSC11-003",
            "LINE-SSC11-003",
            "VALVE-SSC11-003",
            "LOOP-SSC11-003",
            "MEMO-SSC11-003",
        ],
        "expected": {
            "required_valve_cv": 132.372,
            "valve_cv_margin": 17.628,
            "pipe_velocity_m_s": 0.752,
            "velocity_margin_m_s": 2.248,
            "pressure_loss_margin_kpa": 15.0,
            "control_signal_ma": 14.24,
            "bend_thrust_kn": 15.629,
            "thrust_utilization": 0.313,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "stormwater-outlet-flap-gate-hgl-package",
        "discipline": "civil",
        "category": "stormwater-outlet",
        "product_id": "SSC-11-LH-04",
        "source_ids": [
            "DRAIN-SSC11-004",
            "FLAP-SSC11-004",
            "TAIL-SSC11-004",
            "PIPE-SSC11-004",
            "MEMO-SSC11-004",
        ],
        "expected": {
            "pipe_velocity_m_s": 1.289,
            "friction_loss_m": 0.127,
            "flap_gate_headloss_m": 0.152,
            "minor_loss_m": 0.059,
            "upstream_hgl_m": 5.189,
            "hgl_clearance_to_surface_m": 1.011,
            "pipe_crown_margin_to_surface_m": 1.1,
            "outfall_support_reaction_kn": 21.7,
            "support_utilization": 0.678,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "buried-pipeline-groundwater-uplift-package",
        "discipline": "ground",
        "category": "pipeline-ground",
        "product_id": "SSC-11-LH-05",
        "source_ids": [
            "PROFILE-SSC11-005",
            "GEO-SSC11-005",
            "PRESS-SSC11-005",
            "BED-SSC11-005",
            "MEMO-SSC11-005",
        ],
        "expected": {
            "buoyant_uplift_kn_m": 11.095,
            "pipe_self_weight_kn_m": 6.756,
            "contents_weight_kn_m": 8.333,
            "soil_overburden_kn_m": 35.64,
            "downward_resistance_kn_m": 58.729,
            "uplift_factor_of_safety": 5.293,
            "exit_gradient": 0.162,
            "exit_gradient_factor_of_safety": 5.687,
            "pressure_class_margin_kpa": 250.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "pump-station-rising-main-energy-surge-package",
        "discipline": "mechanical",
        "category": "pump-energy",
        "product_id": "SSC-11-LH-06",
        "source_ids": [
            "PUMP-SSC11-006",
            "PROFILE-SSC11-006",
            "PIPE-SSC11-006",
            "FEED-SSC11-006",
            "MEMO-SSC11-006",
        ],
        "expected": {
            "hazen_williams_loss_m": 6.991,
            "total_dynamic_head_m": 37.991,
            "hydraulic_power_kw": 25.343,
            "motor_input_power_kw": 34.565,
            "steady_velocity_m_s": 1.385,
            "surge_pressure_rise_kpa": 1090.912,
            "peak_transient_pressure_kpa": 1610.912,
            "pressure_trip_margin_kpa": 139.088,
            "pipe_pressure_margin_kpa": 239.088,
            "feeder_current_a": 56.694,
            "feeder_voltage_drop_percent": 1.414,
            "voltage_drop_margin_percent": 3.586,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "pipe-material-velocity-compliance-package",
        "discipline": "mechanical",
        "category": "pipe-product-compliance",
        "product_id": "SSC-11-LH-07",
        "source_ids": [
            "LINE-SSC11-007",
            "MAT-SSC11-007",
            "CRIT-SSC11-007",
            "SUP-SSC11-007",
            "MEMO-SSC11-007",
        ],
        "expected": {
            "pipe_velocity_m_s": 1.337,
            "velocity_margin_m_s": 1.163,
            "pressure_loss_kpa": 11.886,
            "pressure_loss_margin_kpa": 78.114,
            "pressure_class_margin_kpa": 720.0,
            "lining_velocity_margin_m_s": 1.663,
            "carbon_equivalent": 0.447,
            "carbon_equivalent_margin": 0.053,
            "certificate_match_percent": 100.0,
            "support_vertical_reaction_kn": 3.266,
            "support_margin_kn": 6.234,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "piping-network-repair-negative-case-package",
        "discipline": "mechanical",
        "category": "piping-review",
        "product_id": "SSC-11-LH-08",
        "source_ids": [
            "BASE-SSC11-008",
            "VAR-SSC11-008",
            "SUP-SSC11-008",
            "VERIFY-SSC11-008",
            "MEMO-SSC11-008",
        ],
        "expected": {
            "baseline_velocity_m_s": 1.12,
            "variant_velocity_m_s": 1.385,
            "velocity_delta_m_s": 0.265,
            "baseline_headloss_m": 0.691,
            "variant_headloss_m": 1.174,
            "headloss_delta_m": 0.483,
            "bend_thrust_kn": 19.819,
            "thrust_utilization": 0.165,
            "support_shift_margin_m": 0.07,
            "negative_case_capture_percent": 100.0,
            "unresolved_repair_count": 0.0,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC11_PRODUCT_CASES, ids=[case["name"] for case in SSC11_PRODUCT_CASES])
def test_ssc11_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC11_PRODUCT_CASES, ids=[case["name"] for case in SSC11_PRODUCT_CASES])
def test_ssc11_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=73, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC11_PRODUCT_CASES, ids=[case["name"] for case in SSC11_PRODUCT_CASES])
def test_ssc11_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=73, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC11_PRODUCT_CASES, ids=[case["name"] for case in SSC11_PRODUCT_CASES])
def test_ssc11_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=73, instance_index=0)
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
