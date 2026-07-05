# ABOUTME: Tests the SSC-12 acoustic receiver impact built-in task template.
# ABOUTME: Covers discovery, deterministic acoustic/vibration metrics, and generated verifier output.

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
    / "acoustic_receiver_impact_package"
)


EXPECTED_METRICS = {
    "distance_attenuation_db": 48.501,
    "receiver_linear_level_db": 42.762,
    "receiver_a_weighted_level_dba": 40.583,
    "combined_ambient_level_dba": 44.359,
    "increase_over_background_db": 2.359,
    "criterion_margin_db": 0.641,
    "dominant_octave_hz": 1000.0,
    "frequency_ratio": 3.688,
    "vibration_transmissibility": 0.092,
    "receiver_vibration_velocity_mm_s": 0.242,
    "vibration_margin_mm_s": 0.058,
    "overall_pass_score": 1.0,
}


def _sample_ssc12_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=47, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "acoustic-receiver-impact-package" in templates
    config = templates["acoustic-receiver-impact-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "acoustic-impact"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=47, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc12_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "SRC-SSC12-001",
        "RCV-12-NIGHT-01",
        "MIT-12-BARRIER-01",
        "ISO-12-MOUNT-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc12_instance(tmp_path)
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
