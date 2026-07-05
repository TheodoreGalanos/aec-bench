# ABOUTME: Tests the SSC-14 pipe transient support and foundation built-in template.
# ABOUTME: Covers discovery, deterministic support/foundation metrics, and verifier output.

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
    / "structural"
    / "pipe_transient_support_foundation_package"
)


EXPECTED_METRICS = {
    "pipe_internal_area_m2": 0.196,
    "pressure_force_kn": 186.532,
    "transient_thrust_kn": 142.765,
    "operating_line_load_kn_m": 4.59,
    "support_vertical_service_kn": 50.247,
    "foundation_self_weight_kn": 299.52,
    "terzaghi_allowable_bearing_kpa": 228.866,
    "factored_vertical_load_kn": 419.721,
    "factored_horizontal_load_kn": 199.872,
    "overturning_moment_knm": 169.891,
    "bearing_eccentricity_m": 0.405,
    "middle_third_limit_m": 0.867,
    "maximum_bearing_kpa": 49.339,
    "bearing_utilization": 0.216,
    "anchor_shear_per_bolt_kn": 24.984,
    "anchor_shear_utilization": 0.657,
    "sliding_margin_kn": 30.975,
    "overall_pass_score": 1.0,
}


def _sample_ssc14_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=51, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "pipe-transient-support-foundation-package" in templates
    config = templates["pipe-transient-support-foundation-package"]
    assert config.meta.discipline == "structural"
    assert config.meta.category == "pipe-support-foundation"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=51, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc14_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "PIPE-SSC14-001",
        "TRANS-14-001",
        "SUP-14-ANCH-01",
        "FDN-14-BASE-01",
        "SOIL-14-BEAR-01",
        "ANCH-14-001",
        "MEMO-14-SUPPORT-01",
        "Nc = 37.162",
        "Nq = 22.456",
        "Ngamma = 19.7",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc14_instance(tmp_path)
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
