# ABOUTME: Tests runnable SSC-12 product templates beyond the acoustic receiver baseline.
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

SSC12_PRODUCT_CASES = [
    {
        "name": "vibration-isolation-support-package",
        "discipline": "structural",
        "category": "vibration-isolation",
        "product_id": "SSC-12-LH-02",
        "source_ids": [
            "EQ-12-VIB-02",
            "SUPPORT-12-LAYOUT-02",
            "ISO-12-DATA-02",
            "FOUND-12-SCHED-02",
            "CRIT-12-VIB-02",
            "MEMO-12-ISO-02",
        ],
        "expected": {
            "frequency_ratio": 3.333,
            "vibration_transmissibility": 0.109,
            "receiver_vibration_velocity_mm_s": 0.099,
            "vibration_margin_mm_s": 0.251,
            "support_service_reaction_kn": 5.518,
            "support_reaction_margin_kn": 6.482,
            "fatigue_damage_ratio": 0.6,
            "fatigue_margin": 0.4,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "room-acoustic-hvac-operations-package",
        "discipline": "mechanical",
        "category": "room-acoustics",
        "product_id": "SSC-12-LH-03",
        "source_ids": [
            "ROOM-12-PLAN-03",
            "FINISH-12-SCHED-03",
            "HVAC-12-SCHED-03",
            "OCC-12-SCENARIO-03",
            "CRIT-12-ROOM-03",
            "MEMO-12-ROOM-03",
        ],
        "expected": {
            "room_rt60_s": 0.703,
            "rt60_margin_s": 0.497,
            "air_changes_per_h": 5.556,
            "hvac_source_a_level_dba": 32.895,
            "equipment_source_a_level_dba": 35.0,
            "combined_room_level_dba": 37.084,
            "room_noise_margin_db": 7.916,
            "design_occupants": 19.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "construction-noise-vibration-monitoring-package",
        "discipline": "mechanical",
        "category": "construction-monitoring",
        "product_id": "SSC-12-LH-04",
        "source_ids": [
            "STAGE-12-CONST-04",
            "EQUIP-12-SOURCE-04",
            "RCV-12-MAP-04",
            "MON-12-CRIT-04",
            "LOG-12-ACTION-04",
            "MEMO-12-CONST-04",
        ],
        "expected": {
            "receiver_construction_noise_dba": 46.446,
            "combined_construction_noise_dba": 50.918,
            "noise_action_margin_db": 14.082,
            "vibration_transmissibility": 0.152,
            "receiver_vibration_velocity_mm_s": 0.287,
            "vibration_action_margin_mm_s": 1.713,
            "monitoring_data_headroom_mb": 75.0,
            "complaint_response_margin_h": 8.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "rail-road-receiver-impact-package",
        "discipline": "civil",
        "category": "corridor-acoustics",
        "product_id": "SSC-12-LH-05",
        "source_ids": [
            "CORR-12-PLAN-05",
            "TRAFFIC-12-SCENARIO-05",
            "RCV-12-CORR-05",
            "SPEC-12-CORR-05",
            "MIT-12-BARRIER-05",
            "MEMO-12-CORR-05",
        ],
        "expected": {
            "traffic_source_level_dba": 89.369,
            "receiver_noise_level_dba": 38.049,
            "combined_corridor_level_dba": 50.269,
            "corridor_noise_margin_db": 6.731,
            "corridor_vibration_velocity_mm_s": 0.622,
            "corridor_vibration_margin_mm_s": 0.178,
            "mitigation_height_margin_m": 0.7,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "fire-alarm-audibility-occupancy-package",
        "discipline": "electrical",
        "category": "alarm-audibility",
        "product_id": "SSC-12-LH-06",
        "source_ids": [
            "FLOOR-12-PLAN-06",
            "NAC-12-SCHED-06",
            "FINISH-12-ROOM-06",
            "LOAD-12-ALARM-06",
            "CRIT-12-LIFE-06",
            "MEMO-12-AUD-06",
        ],
        "expected": {
            "room_rt60_s": 0.798,
            "rt60_margin_s": 0.702,
            "farthest_nac_level_dba": 58.425,
            "combined_alarm_level_dba": 63.196,
            "audibility_margin_db": 11.804,
            "nac_current_a": 1.51,
            "nac_headroom_a": 0.99,
            "alarm_battery_required_kwh": 2.76,
            "alarm_battery_margin_kwh": 0.64,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "equipment-enclosure-ventilation-noise-package",
        "discipline": "mechanical",
        "category": "enclosure-noise",
        "product_id": "SSC-12-LH-07",
        "source_ids": [
            "ENC-12-PLAN-07",
            "VENT-12-SCHED-07",
            "SPEC-12-EQUIP-07",
            "RCV-12-ENC-07",
            "TREAT-12-ATTEN-07",
            "MEMO-12-ENC-07",
        ],
        "expected": {
            "air_changes_per_h": 15.0,
            "ventilation_margin_ach": 3.0,
            "receiver_enclosure_noise_dba": 26.897,
            "combined_receiver_level_dba": 41.166,
            "noise_criterion_margin_db": 3.834,
            "thermal_capacity_margin_kw": 1.7,
            "treatment_insertion_loss_db": 30.0,
            "overall_pass_score": 1.0,
        },
    },
    {
        "name": "acoustic-review-repair-source-policy-package",
        "discipline": "mechanical",
        "category": "acoustic-review",
        "product_id": "SSC-12-LH-08",
        "source_ids": [
            "INDEX-12-SOURCE-08",
            "SPEC-12-OCTAVE-08",
            "RCV-12-PLAN-08",
            "COMMENT-12-REG-08",
            "CRIT-12-MATRIX-08",
            "RESPONSE-12-REPAIR-08",
        ],
        "expected": {
            "review_comment_closure_fraction": 1.0,
            "affected_calculation_update_fraction": 1.0,
            "source_traceability_fraction": 1.0,
            "mitigation_delta_db": 4.7,
            "corrected_noise_margin_db": 1.1,
            "vibration_margin_mm_s": 0.12,
            "unresolved_conflict_count": 0.0,
            "repair_ledger_completeness_fraction": 0.94,
            "overall_pass_score": 1.0,
        },
    },
]


def _templates_by_name():
    return {config.meta.name: (config, path) for config, path in discover_templates()}


@pytest.mark.parametrize("case", SSC12_PRODUCT_CASES, ids=[case["name"] for case in SSC12_PRODUCT_CASES])
def test_ssc12_remaining_product_template_is_discoverable(case: dict[str, object]) -> None:
    templates = _templates_by_name()

    assert case["name"] in templates
    config, _template_dir = templates[case["name"]]
    assert config.meta.discipline == case["discipline"]
    assert config.meta.category == case["category"]


@pytest.mark.parametrize("case", SSC12_PRODUCT_CASES, ids=[case["name"] for case in SSC12_PRODUCT_CASES])
def test_ssc12_remaining_product_metrics_are_deterministic(case: dict[str, object]) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=89, instance_index=0)

    assert instance.ground_truth == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", SSC12_PRODUCT_CASES, ids=[case["name"] for case in SSC12_PRODUCT_CASES])
def test_ssc12_remaining_product_instruction_is_source_bound(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=89, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    assert case["product_id"] in instruction
    for source_id in case["source_ids"]:
        assert source_id in instruction
    assert "task-owned synthetic source pack" in instruction
    assert "Do not claim authority approval" in instruction


@pytest.mark.parametrize("case", SSC12_PRODUCT_CASES, ids=[case["name"] for case in SSC12_PRODUCT_CASES])
def test_ssc12_remaining_product_golden_pass_scores_one(case: dict[str, object], tmp_path: Path) -> None:
    config, template_dir = _templates_by_name()[case["name"]]
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=89, instance_index=0)
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
