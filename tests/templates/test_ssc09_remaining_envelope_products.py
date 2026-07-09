# ABOUTME: Tests runnable SSC-09 product templates beyond the facade fixing baseline.
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

SSC09_PRODUCT_CASES = [
    {
        "name": "roof-drainage-pv-uplift-package",
        "discipline": "civil",
        "category": "roof-pv-drainage-uplift",
        "product_id": "SSC-09-LH-02",
        "source_ids": [
            "ROOF-09-CATCH-02",
            "PV-09-LAYOUT-02",
            "GUTTER-09-SCHED-02",
            "WIND-09-UPLIFT-02",
            "FIX-09-PV-02",
            "MEMO-09-ROOF-PV-02",
        ],
        "expected": {
            "roof_runoff_l_s": 57.396,
            "gutter_capacity_margin_l_s": 14.604,
            "downpipe_total_capacity_l_s": 75.0,
            "downpipe_capacity_margin_l_s": 17.604,
            "pv_uplift_force_kn": 198.0,
            "pv_dead_load_kn": 63.0,
            "pv_fixing_margin_kn": 42.0,
            "drainage_obstruction_margin_m2": 6.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "envelope-access-maintenance-safety-package",
        "discipline": "structural",
        "category": "envelope-access-safety",
        "product_id": "SSC-09-LH-03",
        "source_ids": [
            "ACCESS-09-PLAN-03",
            "LOAD-09-MAINT-03",
            "WIND-09-WEATHER-03",
            "ANCH-09-ACCESS-03",
            "OPS-09-MAINT-03",
            "MEMO-09-SAFETY-03",
        ],
        "expected": {
            "maintenance_live_load_kn": 40.0,
            "maintenance_load_margin_kn": 15.0,
            "wind_screen_load_kn": 14.4,
            "wind_anchor_margin_kn": 5.6,
            "fall_arrest_demand_kn": 12.0,
            "fall_arrest_margin_kn": 4.0,
            "access_width_margin_m": 0.1,
            "tolerance_margin_mm": 7.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "canopy-signage-lighting-fixing-package",
        "discipline": "electrical",
        "category": "canopy-signage-lighting-fixing",
        "product_id": "SSC-09-LH-04",
        "source_ids": [
            "CANOPY-09-ELEV-04",
            "SIGN-09-GEOM-04",
            "LIGHT-09-LOAD-04",
            "ANCH-09-CANOPY-04",
            "FEEDER-09-LIGHT-04",
            "MEMO-09-FACADE-04",
        ],
        "expected": {
            "wind_load_kn": 36.4,
            "dead_load_kn": 9.7,
            "combined_fixing_demand_kn": 37.67,
            "fixing_capacity_margin_kn": 17.33,
            "anchor_group_margin_kn": 18.33,
            "lighting_connected_load_w": 520.0,
            "lighting_current_a": 21.667,
            "voltage_drop_percent": 5.688,
            "voltage_drop_margin_percent": 2.312,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "rainscreen-drainage-cavity-fire-material-review-package",
        "discipline": "structural",
        "category": "rainscreen-cavity-fire-review",
        "product_id": "SSC-09-LH-05",
        "source_ids": [
            "RAINSCREEN-09-DETAIL-05",
            "CAVITY-09-DRAIN-05",
            "MAT-09-DATA-05",
            "FIRESTOP-09-SCHED-05",
            "REVIEW-09-MAT-05",
            "MEMO-09-ENVELOPE-05",
        ],
        "expected": {
            "cavity_depth_margin_mm": 13.0,
            "vent_area_margin_cm2_m": 25.0,
            "drainage_slot_margin_cm2": 20.0,
            "material_evidence_score": 0.9,
            "fire_stop_spacing_margin_m": 0.2,
            "thermal_break_coverage_fraction": 0.96,
            "review_resolution_fraction": 1.0,
            "critical_open_comments": 0.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "facade-zone-reentrant-geometry-package",
        "discipline": "structural",
        "category": "facade-zone-geometry",
        "product_id": "SSC-09-LH-06",
        "source_ids": [
            "ELEV-09-BASE-06",
            "ELEV-09-VARIANT-06",
            "ZONE-09-SCHED-06",
            "SUPPORT-09-POINTS-06",
            "CAP-09-ANCHOR-06",
            "MEMO-09-VARIANT-06",
        ],
        "expected": {
            "corner_zone_area_delta_m2": 16.0,
            "corner_zone_area_delta_percent": 38.095,
            "pressure_delta_kpa": 0.6,
            "baseline_corner_load_kn": 1.512,
            "variant_corner_load_kn": 2.016,
            "corner_load_delta_kn": 0.504,
            "baseline_utilization": 0.548,
            "variant_utilization": 0.726,
            "utilization_delta": 0.178,
            "utilization_margin": 0.224,
            "support_reassignment_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "roof-drainage-gutter-downpipe-facade-interface-package",
        "discipline": "civil",
        "category": "roof-drainage",
        "product_id": "SSC-09-LH-07",
        "source_ids": [
            "ROOF-09-FALL-07",
            "GUTTER-09-REPAIR-07",
            "DOWNPIPE-09-SCHED-07",
            "OVERFLOW-09-SKETCH-07",
            "FACADE-09-EXPOSE-07",
            "MEMO-09-REPAIR-07",
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
        "name": "facade-submittal-source-policy-package",
        "discipline": "structural",
        "category": "facade-submittal-policy",
        "product_id": "SSC-09-LH-08",
        "source_ids": [
            "SOURCE-09-INDEX-08",
            "ELEV-09-REDRAWN-08",
            "CALC-09-REPORT-08",
            "MAT-09-SCHEDULE-08",
            "COMMENT-09-REVIEW-08",
            "RESPONSE-09-SUBMITTAL-08",
        ],
        "expected": {
            "source_trace_score": 0.889,
            "calculator_check_fraction": 1.0,
            "material_match_fraction": 0.9,
            "utilization_pass_fraction": 1.0,
            "comment_resolution_fraction": 0.833,
            "boundary_exception_resolution_fraction": 1.0,
            "unapproved_substitution_count": 0.0,
            "response_completeness_score": 0.9,
            "evidence_boundary_score": 0.932,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC09_PRODUCT_CASES, ids=[case["name"] for case in SSC09_PRODUCT_CASES])
def test_ssc09_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC09_PRODUCT_CASES, ids=[case["name"] for case in SSC09_PRODUCT_CASES])
def test_ssc09_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=83, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC09_PRODUCT_CASES, ids=[case["name"] for case in SSC09_PRODUCT_CASES])
def test_ssc09_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=83, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC09_PRODUCT_CASES, ids=[case["name"] for case in SSC09_PRODUCT_CASES])
def test_ssc09_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=83, instance_index=0)
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
