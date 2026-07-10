# ABOUTME: Tests runnable SSC-03 product templates beyond the detention outlet baseline.
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

SSC03_PRODUCT_CASES = [
    {
        "name": "drainage-long-section-hgl-road-low-point-package",
        "discipline": "civil",
        "category": "drainage-hgl-road-low-point",
        "product_id": "SSC-03-LH-02",
        "source_ids": [
            "ROAD-SSC03-002",
            "DRAIN-SSC03-002",
            "PITPIPE-SSC03-002",
            "HGL-SSC03-002",
            "MEMO-SSC03-002",
        ],
        "expected": {
            "pipe_slope_percent": 0.625,
            "pipe_velocity_m_s": 1.485,
            "manning_capacity_m3_s": 0.485,
            "capacity_margin_m3_s": 0.065,
            "friction_loss_m": 0.374,
            "minor_loss_m": 0.073,
            "upstream_hgl_m": 22.397,
            "low_point_freeboard_m": 0.403,
            "freeboard_margin_m": 0.103,
            "roadway_spread_m": 1.782,
            "spread_margin_m": 0.618,
            "equipment_freeboard_m": 0.653,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "stormwater-pump-station-control-backup-energy-package",
        "discipline": "mechanical",
        "category": "stormwater-pump-control",
        "product_id": "SSC-03-LH-03",
        "source_ids": [
            "WETWELL-SSC03-003",
            "INFLOW-SSC03-003",
            "RMAIN-SSC03-003",
            "CTRL-SSC03-003",
            "ENERGY-SSC03-003",
            "MEMO-SSC03-003",
        ],
        "expected": {
            "total_pump_capacity_l_s": 144.0,
            "pump_capacity_margin_l_s": 26.0,
            "hazen_williams_loss_m": 3.571,
            "total_dynamic_head_m": 12.071,
            "rising_main_velocity_m_s": 1.467,
            "hydraulic_power_kw": 8.509,
            "motor_input_power_kw": 11.858,
            "control_load_kw": 2.2,
            "backup_energy_required_kwh": 13.2,
            "backup_energy_margin_kwh": 10.8,
            "wetwell_freeboard_m": 0.85,
            "wetwell_freeboard_margin_m": 0.4,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "roof-drainage-gutter-downpipe-facade-interface-package",
        "discipline": "civil",
        "category": "roof-drainage",
        "product_id": "SSC-03-LH-04",
        "source_ids": [
            "ROOF-SSC03-004",
            "GUTTER-SSC03-004",
            "FACADE-SSC03-004",
            "RAIN-SSC03-004",
            "MEMO-SSC03-004",
        ],
        "expected": {
            "roof_runoff_l_s": 55.733,
            "gutter_capacity_margin_l_s": 12.267,
            "downpipe_total_capacity_l_s": 81.0,
            "downpipe_capacity_margin_l_s": 25.267,
            "overflow_capacity_l_s": 123.093,
            "overflow_capacity_margin_l_s": 123.093,
            "freeboard_margin_m": 0.1,
            "facade_fixing_pressure_margin_kpa": 0.7,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "outfall-tailwater-flap-gate-coastal-boundary-package",
        "discipline": "civil",
        "category": "outfall-tailwater",
        "product_id": "SSC-03-LH-05",
        "source_ids": [
            "OUTFALL-SSC03-005",
            "TIDE-SSC03-005",
            "FLAP-SSC03-005",
            "HGL-SSC03-005",
            "MEMO-SSC03-005",
        ],
        "expected": {
            "pipe_velocity_m_s": 1.132,
            "friction_loss_m": 0.15,
            "flap_gate_headloss_m": 0.082,
            "minor_loss_m": 0.026,
            "upstream_hgl_m": 3.108,
            "outfall_submergence_m": 0.23,
            "hgl_clearance_m": 0.642,
            "hgl_clearance_margin_m": 0.292,
            "coastal_freeboard_margin_m": 0.25,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "water-quality-pollutant-load-construction-sediment-package",
        "discipline": "civil",
        "category": "water-quality-sediment",
        "product_id": "SSC-03-LH-06",
        "source_ids": [
            "STAGE-SSC03-006",
            "CATCH-SSC03-006",
            "POLLUT-SSC03-006",
            "BASIN-SSC03-006",
            "MEMO-SSC03-006",
        ],
        "expected": {
            "runoff_volume_m3": 912.0,
            "pollutant_load_kg": 164.16,
            "removed_load_kg": 128.045,
            "residual_load_kg": 36.115,
            "required_basin_volume_m3": 768.0,
            "basin_volume_margin_m3": 152.0,
            "temporary_discharge_margin_l_s": 23.0,
            "weir_release_l_s": 315.759,
            "capture_percent": 78.0,
            "capture_margin_percent": 3.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "sewer-storm-pipe-gradient-capacity-repair-package",
        "discipline": "civil",
        "category": "pipe-gradient-repair",
        "product_id": "SSC-03-LH-07",
        "source_ids": [
            "PIPE-SSC03-007",
            "INVERT-SSC03-007",
            "LONG-SSC03-007",
            "CRIT-SSC03-007",
            "MEMO-SSC03-007",
        ],
        "expected": {
            "scheduled_slope_percent": 0.5,
            "long_section_slope_percent": 0.505,
            "invert_conflict_m": 0.005,
            "manning_capacity_m3_s": 0.434,
            "capacity_margin_m3_s": 0.094,
            "flow_velocity_m_s": 1.203,
            "velocity_low_margin_m_s": 0.453,
            "velocity_high_margin_m_s": 1.797,
            "pipe_crown_cover_m": 0.58,
            "cover_margin_m": 0.13,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "swmm-hec-report-source-policy-package",
        "discipline": "civil",
        "category": "model-source-policy",
        "product_id": "SSC-03-LH-08",
        "source_ids": [
            "MODEL-SSC03-008",
            "REPORT-SSC03-008",
            "RESULT-SSC03-008",
            "HASH-SSC03-008",
            "VERIFY-SSC03-008",
            "MEMO-SSC03-008",
        ],
        "expected": {
            "object_match_percent": 100.0,
            "hash_completeness_percent": 100.0,
            "peak_delta_m3_s": 0.028,
            "peak_delta_margin_m3_s": 0.022,
            "continuity_error_percent": 0.37,
            "continuity_margin_percent": 0.63,
            "storage_unit_count": 2.0,
            "outlet_row_count": 5.0,
            "negative_case_capture_percent": 100.0,
            "unresolved_source_conflicts": 0.0,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC03_PRODUCT_CASES, ids=[case["name"] for case in SSC03_PRODUCT_CASES])
def test_ssc03_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC03_PRODUCT_CASES, ids=[case["name"] for case in SSC03_PRODUCT_CASES])
def test_ssc03_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=73, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC03_PRODUCT_CASES, ids=[case["name"] for case in SSC03_PRODUCT_CASES])
def test_ssc03_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
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


@pytest.mark.parametrize("case", SSC03_PRODUCT_CASES, ids=[case["name"] for case in SSC03_PRODUCT_CASES])
def test_ssc03_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
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
