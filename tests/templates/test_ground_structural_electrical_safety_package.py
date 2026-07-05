# ABOUTME: Tests the SSC-07 ground structural-electrical safety built-in task template.
# ABOUTME: Covers discovery, deterministic ground metrics, and generated verifier output.

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
    / "ground"
    / "ground_structural_electrical_safety_package"
)


EXPECTED_METRICS = {
    "spt_n60": 22.743,
    "spt_n1_60": 20.342,
    "spt_n1_60_margin": 5.342,
    "cpt_qt_mpa": 12.005,
    "cpt_ic": 1.559,
    "cpt_phi_deg": 41.949,
    "governing_phi_deg": 32.0,
    "allowable_bearing_capacity_kpa": 416.664,
    "bearing_utilization": 0.528,
    "bearing_margin_kpa": 196.664,
    "grid_resistance_ohm": 1.547,
    "ground_potential_rise_v": 4951.196,
    "gpr_margin_v": 48.804,
    "overall_pass_score": 1.0,
}


def _sample_ssc07_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=49, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "ground-structural-electrical-safety-package" in templates
    config = templates["ground-structural-electrical-safety-package"]
    assert config.meta.discipline == "ground"
    assert config.meta.category == "ground-safety"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=49, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc07_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "GND-SSC07-001",
        "BH-07-03",
        "CPT-07-02",
        "SPT-07-03-06M",
        "RES-07-ERT-01",
        "GRID-07-EARTH-01",
        "MEMO-07-SAFETY-01",
        "Nc = 44.0357",
        "Nq = 28.5166",
        "Ngamma = 27.85",
        "gamma_eff = 12.36875",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc07_instance(tmp_path)
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
