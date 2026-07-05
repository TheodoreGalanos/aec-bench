# ABOUTME: Tests the SSC-11 pump transient protection built-in task template.
# ABOUTME: Covers discovery, deterministic transient/support metrics, and verifier output.

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
    / "pump_transient_protection_package"
)


EXPECTED_METRICS = {
    "fluid_only_wave_speed_m_s": 1484.725,
    "pipe_flexibility_ratio": 0.418,
    "wave_speed_m_s": 1246.832,
    "steady_velocity_m_s": 0.547,
    "velocity_change_m_s": 0.465,
    "joukowsky_pressure_rise_kpa": 578.22,
    "joukowsky_pressure_head_m": 59.06,
    "total_dynamic_head_m": 63.581,
    "hydraulic_power_kw": 62.248,
    "peak_transient_pressure_kpa": 1098.22,
    "bend_transient_thrust_kn": 153.753,
    "operating_line_load_kn_m": 3.346,
    "support_vertical_service_kn": 35.573,
    "pressure_trip_margin_kpa": 61.78,
    "pipe_pressure_margin_kpa": 251.78,
    "thrust_utilization": 0.809,
    "support_vertical_utilization": 0.847,
    "overall_pass_score": 1.0,
}


def _sample_ssc11_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=53, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "pump-transient-protection-package" in templates
    config = templates["pump-transient-protection-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "pump-transient"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=53, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc11_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "PID-SSC11-401",
        "PUMP-11-DUTY-01",
        "TRANS-11-TRIP-01",
        "SUP-11-ANCH-01",
        "PROT-11-HHP-01",
        "MEMO-11-SUPPORT-PROTECT-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc11_instance(tmp_path)
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
