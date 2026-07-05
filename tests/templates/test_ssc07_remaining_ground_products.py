# ABOUTME: Tests runnable SSC-07 product templates beyond the first safety package.
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

SSC07_PRODUCT_CASES = [
    {
        "name": "retaining-wall-seepage-uplift-foundation-package",
        "product_id": "SSC-07-LH-02",
        "source_ids": [
            "RET-07-WALL-01",
            "GEO-07-RET-01",
            "GW-07-RET-01",
            "SUR-07-RET-01",
            "MEMO-07-RET-01",
        ],
        "expected": {
            "active_pressure_coefficient": 0.307,
            "active_thrust_kn_m": 64.266,
            "sliding_fs": 1.758,
            "overturning_fs": 2.312,
            "max_bearing_pressure_kpa": 141.396,
            "bearing_margin_kpa": 78.604,
            "exit_gradient": 0.175,
            "exit_gradient_fs": 5.429,
            "uplift_pressure_kpa": 20.601,
            "uplift_margin_kpa": 40.937,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "solar-array-ground-bearing-earthing-package",
        "product_id": "SSC-07-LH-03",
        "source_ids": [
            "PV-07-ARRAY-01",
            "WIND-07-PV-01",
            "RACK-07-FOUND-01",
            "RES-07-PV-01",
            "MEMO-07-PV-01",
        ],
        "expected": {
            "wind_force_total_kn": 78.936,
            "support_reaction_kn": 6.578,
            "uplift_force_kn": 43.415,
            "uplift_margin_kn": 6.585,
            "bearing_pressure_kpa": 7.748,
            "bearing_utilization": 0.091,
            "grid_resistance_ohm": 2.233,
            "ground_potential_rise_v": 3126.831,
            "gpr_margin_v": 1873.169,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "excavation-dewatering-temporary-power-package",
        "product_id": "SSC-07-LH-04",
        "source_ids": [
            "EXC-07-SECTION-01",
            "GW-07-DEWATER-01",
            "PUMP-07-TEMP-01",
            "PWR-07-TEMP-01",
            "MEMO-07-TEMP-01",
        ],
        "expected": {
            "exit_gradient": 0.229,
            "exit_gradient_fs": 3.937,
            "rapid_drawdown_fs": 1.134,
            "pump_power_kw": 4.557,
            "temporary_power_kw": 10.614,
            "generator_margin_kw": 7.386,
            "battery_runtime_h": 8.333,
            "battery_runtime_margin_h": 2.333,
            "uplift_pressure_kpa": 31.392,
            "uplift_margin_kpa": 10.608,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "seismic-slope-service-continuity-package",
        "product_id": "SSC-07-LH-05",
        "source_ids": [
            "SEIS-07-CASE-01",
            "SLOPE-07-SECTION-01",
            "SOIL-07-SEIS-01",
            "UTIL-07-SERVICE-01",
            "MEMO-07-SEIS-01",
        ],
        "expected": {
            "slope_resisting_kpa": 46.328,
            "static_driving_kpa": 24.089,
            "seismic_increment_kpa": 7.53,
            "static_slope_fs": 1.923,
            "seismic_slope_fs": 1.465,
            "seismic_fs_margin": 0.365,
            "service_capacity_margin_kw": 8.0,
            "feeder_voltage_drop_percent": 1.621,
            "voltage_drop_margin_percent": 3.379,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "ground-improvement-foundation-recheck-package",
        "product_id": "SSC-07-LH-06",
        "source_ids": [
            "GI-07-CERT-01",
            "SPT-07-POST-01",
            "FDN-07-RECHECK-01",
            "SETTLE-07-RECHECK-01",
            "MEMO-07-FOUND-01",
        ],
        "expected": {
            "improvement_ratio": 2.444,
            "post_improvement_n_margin": 4.0,
            "allowable_bearing_capacity_kpa": 264.0,
            "bearing_utilization": 0.682,
            "bearing_margin_kpa": 84.0,
            "immediate_settlement_mm": 9.36,
            "primary_settlement_mm": 12.5,
            "total_settlement_mm": 21.86,
            "settlement_margin_mm": 3.14,
            "certificate_match_percent": 100.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "buried-pipe-thrust-soil-resistance-package",
        "product_id": "SSC-07-LH-07",
        "source_ids": [
            "PIPE-07-ALIGN-01",
            "TRANS-07-THRUST-01",
            "SOIL-07-PIPE-01",
            "TBLOCK-07-01",
            "MEMO-07-PIPE-01",
        ],
        "expected": {
            "pipe_internal_area_m2": 0.283,
            "transient_thrust_kn": 183.942,
            "thrust_resistance_margin_kn": 76.058,
            "thrust_utilization": 0.707,
            "bearing_pressure_kpa": 26.667,
            "bearing_margin_kpa": 133.333,
            "uplift_pressure_kpa": 23.544,
            "uplift_margin_kpa": 12.456,
            "hazen_williams_headloss_m": 0.036,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "ground-investigation-parameter-repair-package",
        "product_id": "SSC-07-LH-08",
        "source_ids": [
            "GIR-07-REVIEW-01",
            "CPT-07-REPAIR-01",
            "LAB-07-REPAIR-01",
            "CALC-07-AFFECTED-01",
            "MEMO-07-REPAIR-01",
        ],
        "expected": {
            "phi_source_delta_deg": 3.5,
            "adopted_phi_deg": 31.0,
            "spt_n1_60_margin": 1.2,
            "bearing_utilization": 0.881,
            "bearing_margin_kpa": 25.0,
            "wall_sliding_fs_margin": 0.12,
            "grid_resistance_margin_ohm": 0.1,
            "comment_closeout_percent": 100.0,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC07_PRODUCT_CASES, ids=[case["name"] for case in SSC07_PRODUCT_CASES])
def test_ssc07_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == "ground"
    assert config.meta.category == "ground-investigation"


@pytest.mark.parametrize("case", SSC07_PRODUCT_CASES, ids=[case["name"] for case in SSC07_PRODUCT_CASES])
def test_ssc07_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=70, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC07_PRODUCT_CASES, ids=[case["name"] for case in SSC07_PRODUCT_CASES])
def test_ssc07_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=70, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC07_PRODUCT_CASES, ids=[case["name"] for case in SSC07_PRODUCT_CASES])
def test_ssc07_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=70, instance_index=0)
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
