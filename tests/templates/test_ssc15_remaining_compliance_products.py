# ABOUTME: Tests runnable SSC-15 product templates beyond the submittal baseline.
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

SSC15_PRODUCT_CASES = [
    {
        "name": "steel-certificate-structural-fire-carbon-package",
        "discipline": "structural",
        "category": "material-compliance",
        "product_id": "SSC-15-LH-01",
        "source_ids": [
            "CERT-15-STEEL-01",
            "MAT-15-SCHED-01",
            "WELD-15-CRIT-01",
            "FIRE-15-NOTE-01",
            "CALC-15-STRUCT-01",
            "MEMO-15-STEEL-01",
        ],
        "expected": {
            "carbon_equivalent": 0.482,
            "carbon_equivalent_margin": 0.038,
            "structural_capacity_margin_kn": 33.0,
            "structural_utilization": 0.742,
            "critical_steel_temperature_c": 477.2,
            "fire_temperature_margin_c": 47.2,
            "certificate_field_match_fraction": 1.0,
            "material_memo_completeness_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "cable-component-datasheet-ampacity-voltage-package",
        "discipline": "electrical",
        "category": "component-compliance",
        "product_id": "SSC-15-LH-02",
        "source_ids": [
            "DAT-15-CABLE-02",
            "SCHED-15-CABLE-02",
            "TEMP-15-INSTALL-02",
            "SLD-15-FEEDER-02",
            "LIMIT-15-MFR-02",
            "MEMO-15-CABLE-02",
        ],
        "expected": {
            "derated_ampacity_a": 129.038,
            "ampacity_margin_a": 11.038,
            "ampacity_utilization": 0.914,
            "ac_resistance_ohm_km": 0.19,
            "voltage_drop_percent": 0.859,
            "voltage_drop_margin_percent": 3.141,
            "temperature_rating_margin_c": 15.0,
            "product_identity_match_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "concrete-mix-drainage-retaining-compliance-package",
        "discipline": "civil",
        "category": "mix-compliance",
        "product_id": "SSC-15-LH-03",
        "source_ids": [
            "MIX-15-DESIGN-03",
            "SCM-15-PRODUCT-03",
            "STRENGTH-15-CRIT-03",
            "FOUND-15-DETAIL-03",
            "EXP-15-NOTE-03",
            "MEMO-15-MIX-03",
        ],
        "expected": {
            "target_mean_strength_mpa": 46.6,
            "strength_margin_mpa": 1.4,
            "scm_replacement_margin_percent": 10.0,
            "bearing_capacity_margin_kpa": 80.0,
            "bearing_utilization": 0.765,
            "exposure_cover_margin_mm": 10.0,
            "drainage_freeboard_margin_m": 0.1,
            "mix_evidence_match_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "pipe-product-velocity-slope-certificate-package",
        "discipline": "civil",
        "category": "pipe-product-compliance",
        "product_id": "SSC-15-LH-05",
        "source_ids": [
            "PIPE-15-DATA-05",
            "PIPE-15-SCHED-05",
            "LONG-15-SECTION-05",
            "CRIT-15-HYD-05",
            "CERT-15-PIPE-05",
            "MEMO-15-PIPE-05",
        ],
        "expected": {
            "flow_velocity_m_s": 0.573,
            "velocity_low_margin_m_s": 0.073,
            "velocity_high_margin_m_s": 2.427,
            "manning_capacity_l_s": 29.336,
            "capacity_margin_l_s": 11.336,
            "slope_margin": 0.002,
            "pressure_certificate_margin_kpa": 370.0,
            "lining_temperature_margin_c": 15.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "facade-fixing-certificate-capacity-package",
        "discipline": "structural",
        "category": "fixing-compliance",
        "product_id": "SSC-15-LH-06",
        "source_ids": [
            "CERT-15-FIX-06",
            "CAP-15-TABLE-06",
            "ELEV-15-FACADE-06",
            "WIND-15-CALC-06",
            "MAT-15-FACADE-06",
            "MEMO-15-FIX-06",
        ],
        "expected": {
            "design_bracket_load_kn": 4.32,
            "bracket_capacity_margin_kn": 1.88,
            "bracket_utilization": 0.697,
            "anchor_shear_margin_kn": 1.3,
            "certificate_field_match_fraction": 1.0,
            "carbon_equivalent_margin": 0.06,
            "tolerance_adjustment_margin_mm": 13.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "occupancy-fire-product-class-compliance-package",
        "discipline": "mechanical",
        "category": "code-compliance",
        "product_id": "SSC-15-LH-07",
        "source_ids": [
            "OCC-15-SCHED-07",
            "DAT-15-PRODUCT-07",
            "FIRE-15-CLASS-07",
            "AUTH-15-REF-07",
            "CALC-15-APP-07",
            "MEMO-15-CODE-07",
        ],
        "expected": {
            "occupant_load_persons": 96.0,
            "product_class_capacity_margin_persons": 24.0,
            "flame_spread_margin": 50.0,
            "smoke_developed_margin": 370.0,
            "fire_resistance_margin_min": 15.0,
            "nac_current_margin_a": 3.2,
            "smoke_exhaust_ach_margin": 1.0,
            "authority_evidence_fraction": 1.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "certificate-conflict-repair-portfolio-package",
        "discipline": "mechanical",
        "category": "certificate-repair",
        "product_id": "SSC-15-LH-08",
        "source_ids": [
            "DAT-15-A-08",
            "DAT-15-B-08",
            "CERT-15-REC-08",
            "INDEX-15-SRC-08",
            "TRACE-15-CALC-08",
            "RESPONSE-15-REPAIR-08",
        ],
        "expected": {
            "source_authority_score": 1.0,
            "affected_calculation_update_fraction": 1.0,
            "certificate_capacity_delta_kn": 15.0,
            "replacement_capacity_margin_kn": 12.0,
            "source_conflict_closure_fraction": 1.0,
            "unresolved_conflict_count": 0.0,
            "expired_source_count": 0.0,
            "repair_memo_completeness_fraction": 0.9,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC15_PRODUCT_CASES, ids=[case["name"] for case in SSC15_PRODUCT_CASES])
def test_ssc15_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC15_PRODUCT_CASES, ids=[case["name"] for case in SSC15_PRODUCT_CASES])
def test_ssc15_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=86, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC15_PRODUCT_CASES, ids=[case["name"] for case in SSC15_PRODUCT_CASES])
def test_ssc15_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=86, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC15_PRODUCT_CASES, ids=[case["name"] for case in SSC15_PRODUCT_CASES])
def test_ssc15_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=86, instance_index=0)
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
