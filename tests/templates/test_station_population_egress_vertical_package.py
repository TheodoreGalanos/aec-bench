# ABOUTME: Tests the SSC-08 station population egress vertical movement template.
# ABOUTME: Covers discovery, deterministic building-operations metrics, and verifier output.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.templates.registry import discover_templates, load_engine_module, load_template

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "mechanical"
    / "station_population_egress_vertical_package"
)


EXPECTED_METRICS = {
    "calculated_occupants": 600.0,
    "design_occupants": 600.0,
    "occupant_density_person_m2": 0.4,
    "required_egress_width_mm": 3000.0,
    "egress_width_margin_mm": 600.0,
    "egress_width_utilization": 0.833,
    "egress_flow_time_s": 125.313,
    "egress_time_margin_s": 54.687,
    "escalator_practical_capacity_persons_per_h": 3600.0,
    "escalator_capacity_persons_per_5min": 300.0,
    "lift_passengers_per_5min": 64.0,
    "lift_handling_capacity_percent": 10.667,
    "lift_handling_margin_percent": 0.667,
    "vertical_capacity_persons_per_5min": 364.0,
    "vertical_capacity_margin_persons_per_5min": 104.0,
    "ventilation_air_changes_per_h": 6.4,
    "ventilation_ach_margin": 0.4,
    "nac_total_load_a": 2.4,
    "nac_spare_capacity_a": 0.6,
    "nac_utilization_percent": 80.0,
    "overall_pass_score": 1.0,
}


def _sample_ssc08_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=63, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "station-population-egress-vertical-package" in templates
    config = templates["station-population-egress-vertical-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "building-operations"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=63, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc08_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CASE-SSC08-STATION-001",
        "ZONE-08-CONCOURSE-L1",
        "POP-08-PEAK-001",
        "EGRESS-08-ROUTE-A",
        "ESC-08-UP-01",
        "LIFT-08-GROUP-01",
        "VENT-08-SMOKE-01",
        "NAC-08-ALARM-01",
        "MEMO-08-OPS-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc08_instance(tmp_path)
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    reward_file = tmp_path / "reward.json"

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
