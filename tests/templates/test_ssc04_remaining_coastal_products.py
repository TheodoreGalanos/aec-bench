# ABOUTME: Tests runnable SSC-04 product templates beyond the coastal pump baseline.
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

SSC04_PRODUCT_CASES = [
    {
        "name": "wave-runup-freeboard-asset-protection-package",
        "discipline": "civil",
        "category": "coastal-wave-protection",
        "product_id": "SSC-04-LH-02",
        "source_ids": [
            "WAVE-04-CLIMATE-02",
            "PROFILE-04-SHORE-02",
            "ASSET-04-LEVEL-02",
            "ARMOR-04-SCHED-02",
            "CRIT-04-HORIZON-02",
            "MEMO-04-PROTECT-02",
        ],
        "expected": {
            "deepwater_wavelength_m": 99.924,
            "shoaling_coefficient": 1.12,
            "nearshore_wave_height_m": 2.016,
            "breaking_height_limit_m": 2.496,
            "breaking_margin_m": 0.48,
            "runup_2_percent_m": 2.419,
            "total_water_level_m": 4.469,
            "freeboard_margin_m": 0.331,
            "armor_stability_margin_t": 0.7,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "marine-berthing-fender-storm-operations-package",
        "discipline": "structural",
        "category": "marine-berthing-operations",
        "product_id": "SSC-04-LH-03",
        "source_ids": [
            "VESSEL-04-DATA-03",
            "BERTH-04-LAYOUT-03",
            "FENDER-04-SCHED-03",
            "MOORING-04-SCHED-03",
            "TIDE-04-WEATHER-03",
            "MEMO-04-MARINE-03",
        ],
        "expected": {
            "berthing_energy_knm": 47.52,
            "fender_energy_margin_knm": 17.48,
            "environmental_mooring_load_kn": 45.3,
            "mooring_capacity_kn": 64.0,
            "mooring_margin_kn": 18.7,
            "storm_tide_operating_level_m": 3.1,
            "deck_clearance_margin_m": 0.6,
            "allowable_operating_window_margin_h": 3.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "flap-gate-tide-drainage-resilience-package",
        "discipline": "civil",
        "category": "coastal-drainage-resilience",
        "product_id": "SSC-04-LH-04",
        "source_ids": [
            "OUTFALL-04-SECTION-04",
            "FLAP-04-DATA-04",
            "TIDE-04-TAILWATER-04",
            "DRAIN-04-UPSTREAM-04",
            "PUMP-04-CONTROL-04",
            "MEMO-04-DRAINAGE-04",
        ],
        "expected": {
            "pipe_area_m2": 0.442,
            "outlet_velocity_m_s": 0.951,
            "tailwater_level_m": 2.8,
            "outfall_submergence_depth_m": 1.6,
            "flap_gate_headloss_m": 0.115,
            "upstream_hgl_m": 3.165,
            "road_low_point_hgl_margin_m": 0.285,
            "storage_margin_m3": 170.0,
            "pump_input_power_kw": 5.045,
            "control_battery_margin_kwh": 6.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "coastal-erosion-longshore-temporary-works-package",
        "discipline": "civil",
        "category": "coastal-erosion-temporary-works",
        "product_id": "SSC-04-LH-05",
        "source_ids": [
            "BEACH-04-PROFILE-05",
            "SEDIMENT-04-GRADING-05",
            "WAVE-04-CLIMATE-05",
            "TEMP-04-WORKS-05",
            "MONITOR-04-PERMIT-05",
            "MEMO-04-EROSION-05",
        ],
        "expected": {
            "longshore_transport_m3_day": 189.855,
            "temporary_protection_volume_m3": 626.52,
            "protection_volume_margin_m3": 93.48,
            "sediment_basin_required_m3": 643.5,
            "sediment_basin_margin_m3": 56.5,
            "discharge_capacity_margin_m3_s": 0.04,
            "monitoring_coverage_fraction": 1.0,
            "construction_tolerance_margin_m": 0.07,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "sea-level-rise-asset-review-package",
        "discipline": "civil",
        "category": "coastal-asset-slr-review",
        "product_id": "SSC-04-LH-06",
        "source_ids": [
            "ASSET-04-REGISTER-06",
            "SLR-04-SCENARIO-06",
            "STORM-04-TIDE-06",
            "SERVICE-04-CRITERION-06",
            "ADAPT-04-OPTION-06",
            "MEMO-04-REVIEW-06",
        ],
        "expected": {
            "future_stillwater_level_m": 2.9,
            "future_design_level_m": 3.25,
            "asset_freeboard_margin_m": 0.2,
            "service_threshold_exceedance_m": 0.2,
            "adaptation_raise_required_m": 0.0,
            "adaptation_cost_margin_usd": 70000.0,
            "benefit_cost_ratio": 1.778,
            "scenario_trace_score": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "coastal-pumpout-generator-autonomy-package",
        "discipline": "electrical",
        "category": "coastal-pumpout-autonomy",
        "product_id": "SSC-04-LH-07",
        "source_ids": [
            "PUMPSTA-04-SECTION-07",
            "FLOOD-04-EVENT-07",
            "PUMP-04-DUTY-07",
            "LOAD-04-ELEC-07",
            "BACKUP-04-FUEL-07",
            "MEMO-04-CONTINUITY-07",
        ],
        "expected": {
            "inflow_volume_m3": 4032.0,
            "pumped_volume_m3": 3456.0,
            "storage_margin_m3": 124.0,
            "pump_total_dynamic_head_m": 5.2,
            "pump_input_power_kw": 17.983,
            "emergency_load_kw": 40.666,
            "generator_capacity_margin_kw": 10.334,
            "fuel_runtime_margin_h": 8.0,
            "bess_runtime_h": 1.771,
            "access_freeboard_margin_m": 0.25,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "marine-asset-source-policy-review-package",
        "discipline": "civil",
        "category": "marine-source-policy-review",
        "product_id": "SSC-04-LH-08",
        "source_ids": [
            "DATUM-04-STATEMENT-08",
            "CRITERIA-04-MATRIX-08",
            "ASSET-04-MARINE-08",
            "CALC-04-APPENDIX-08",
            "COMMENT-04-REGISTER-08",
            "MEMO-04-SOURCE-08",
        ],
        "expected": {
            "datum_trace_score": 1.0,
            "criteria_resolution_fraction": 1.0,
            "asset_schedule_match_fraction": 0.933,
            "calculation_trace_fraction": 0.9,
            "comment_resolution_fraction": 0.875,
            "authority_partition_score": 1.0,
            "unsupported_source_value_count": 0.0,
            "response_completeness_score": 0.9,
            "evidence_boundary_score": 0.944,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC04_PRODUCT_CASES, ids=[case["name"] for case in SSC04_PRODUCT_CASES])
def test_ssc04_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC04_PRODUCT_CASES, ids=[case["name"] for case in SSC04_PRODUCT_CASES])
def test_ssc04_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=84, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC04_PRODUCT_CASES, ids=[case["name"] for case in SSC04_PRODUCT_CASES])
def test_ssc04_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=84, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC04_PRODUCT_CASES, ids=[case["name"] for case in SSC04_PRODUCT_CASES])
def test_ssc04_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=84, instance_index=0)
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
