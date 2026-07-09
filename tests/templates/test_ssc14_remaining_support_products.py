# ABOUTME: Tests runnable SSC-14 product templates beyond the first pipe support package.
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

SSC14_PRODUCT_CASES = [
    {
        "name": "facade-roof-bracket-connection-package",
        "discipline": "structural",
        "category": "structural-connections",
        "product_id": "SSC-14-LH-02",
        "source_ids": [
            "ELEV-SSC14-002",
            "WIND-SSC14-002",
            "BRKT-SSC14-002",
            "MAT-SSC14-002",
            "MEMO-SSC14-002",
        ],
        "expected": {
            "tributary_area_m2": 1.2,
            "service_wind_load_kn": 1.74,
            "service_dead_load_kn": 0.504,
            "factored_out_of_plane_reaction_kn": 2.61,
            "factored_vertical_reaction_kn": 0.605,
            "bracket_utilization": 0.932,
            "anchor_tension_per_anchor_kn": 1.305,
            "anchor_shear_per_anchor_kn": 0.302,
            "anchor_combined_utilization": 0.391,
            "carbon_equivalent": 0.487,
            "carbon_equivalent_margin": 0.013,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "equipment-skid-support-vibration-package",
        "discipline": "structural",
        "category": "equipment-support",
        "product_id": "SSC-14-LH-03",
        "source_ids": [
            "EQP-SSC14-003",
            "MASS-SSC14-003",
            "FDN-SSC14-003",
            "VIB-SSC14-003",
            "MEMO-SSC14-003",
        ],
        "expected": {
            "support_service_reaction_kn": 11.846,
            "factored_support_reaction_kn": 15.992,
            "bearing_pressure_kpa": 16.019,
            "bearing_utilization": 0.089,
            "frequency_ratio": 0.667,
            "vibration_transmissibility": 1.778,
            "transmitted_dynamic_force_kn": 21.058,
            "fatigue_damage_ratio": 0.008,
            "load_combination_margin_kn": 36.008,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "retaining-foundation-groundwater-stability-package",
        "discipline": "structural",
        "category": "retaining-foundation",
        "product_id": "SSC-14-LH-04",
        "source_ids": [
            "GEO-SSC14-004",
            "WALL-SSC14-004",
            "GW-SSC14-004",
            "SUR-SSC14-004",
            "MEMO-SSC14-004",
        ],
        "expected": {
            "active_earth_force_kn_m": 50.667,
            "surcharge_force_kn_m": 16.0,
            "hydrostatic_force_kn_m": 21.631,
            "total_lateral_force_kn_m": 88.298,
            "overturning_moment_knm_m": 114.697,
            "resisting_moment_knm_m": 345.6,
            "overturning_factor_of_safety": 3.013,
            "sliding_factor_of_safety": 1.373,
            "bearing_pressure_kpa": 75.0,
            "bearing_utilization": 0.341,
            "uplift_margin_kn_m": 178.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "marine-fender-mooring-berthing-structure-package",
        "discipline": "structural",
        "category": "marine-structures",
        "product_id": "SSC-14-LH-05",
        "source_ids": [
            "BERTH-SSC14-005",
            "VESSEL-SSC14-005",
            "FENDER-SSC14-005",
            "WATER-SSC14-005",
            "MEMO-SSC14-005",
        ],
        "expected": {
            "berthing_energy_kj": 334.08,
            "fender_energy_demand_kj": 367.488,
            "fender_energy_utilization": 0.875,
            "fender_reaction_kn": 874.971,
            "mooring_wind_force_kn": 254.15,
            "mooring_line_demand_kn": 70.106,
            "mooring_utilization": 0.738,
            "water_level_margin_m": 0.55,
            "combined_support_load_kn": 449.99,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "wind-solar-foundation-package",
        "discipline": "structural",
        "category": "renewable-foundation",
        "product_id": "SSC-14-LH-06",
        "source_ids": [
            "PV-SSC14-006",
            "WIND-SSC14-006",
            "FDN-SSC14-006",
            "GEO-SSC14-006",
            "MEMO-SSC14-006",
        ],
        "expected": {
            "source_velocity_pressure_kpa": 1.241,
            "array_wind_load_kn": 18.62,
            "array_dead_load_kn": 2.16,
            "foundation_self_weight_kn": 62.208,
            "net_uplift_kn": -45.748,
            "uplift_margin_kn": 165.748,
            "bearing_pressure_kpa": 14.9,
            "bearing_utilization": 0.083,
            "horizontal_shear_kn": 8.379,
            "sliding_margin_kn": 27.023,
            "anchor_tension_per_anchor_kn": 0.0,
            "anchor_tension_utilization": 0.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "construction-tolerance-connection-repair-package",
        "discipline": "structural",
        "category": "field-repair",
        "product_id": "SSC-14-LH-07",
        "source_ids": [
            "SURVEY-SSC14-007",
            "CONN-SSC14-007",
            "TOL-SSC14-007",
            "NCR-SSC14-007",
            "MEMO-SSC14-007",
        ],
        "expected": {
            "tolerance_exceedance_mm": 8.0,
            "required_slot_adjustment_mm": 18.0,
            "remaining_slot_margin_mm": 14.0,
            "repair_shim_margin_mm": 6.0,
            "baseline_moment_knm": 3.84,
            "added_moment_knm": 0.128,
            "bracket_moment_utilization": 0.529,
            "weld_carbon_equivalent": 0.431,
            "carbon_equivalent_margin": 0.019,
            "repair_acceptance_score": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "structural-review-authority-overlay-package",
        "discipline": "structural",
        "category": "structural-review",
        "product_id": "SSC-14-LH-08",
        "source_ids": [
            "INDEX-SSC14-008",
            "LOAD-SSC14-008",
            "MAT-SSC14-008",
            "COMMENTS-SSC14-008",
            "MEMO-SSC14-008",
        ],
        "expected": {
            "governing_uls_load_kn": 253.6,
            "governing_sls_load_kn": 194.6,
            "uls_capacity_margin_kn": 6.4,
            "sls_deflection_margin_mm": 3.8,
            "material_carbon_equivalent": 0.511,
            "carbon_equivalent_margin": 0.039,
            "evidence_complete_percent": 88.889,
            "comment_closeout_percent": 91.667,
            "unresolved_critical_comments": 0.0,
            "authority_override_count": 1.0,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC14_PRODUCT_CASES, ids=[case["name"] for case in SSC14_PRODUCT_CASES])
def test_ssc14_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC14_PRODUCT_CASES, ids=[case["name"] for case in SSC14_PRODUCT_CASES])
def test_ssc14_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=72, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC14_PRODUCT_CASES, ids=[case["name"] for case in SSC14_PRODUCT_CASES])
def test_ssc14_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=72, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC14_PRODUCT_CASES, ids=[case["name"] for case in SSC14_PRODUCT_CASES])
def test_ssc14_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=72, instance_index=0)
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
