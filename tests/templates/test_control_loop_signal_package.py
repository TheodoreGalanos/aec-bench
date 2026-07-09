# ABOUTME: Tests the SSC-18 control-loop signal built-in task template.
# ABOUTME: Covers discovery, deterministic loop metrics, and generated verifier output.

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
    / "electrical"
    / "control_loop_signal_package"
)


EXPECTED_METRICS = {
    "pressure_drop_bar": 3.1,
    "choked_pressure_drop_bar": 4.998,
    "cv_required": 56.464,
    "selected_cv_headroom": 6.536,
    "valve_travel_pct": 89.626,
    "span_pct": 57.333,
    "current_signal_ma": 13.173,
    "reconstructed_process_value": 68.8,
    "high_alarm_current_ma": 16.667,
    "high_high_trip_current_ma": 18.4,
    "alarm_current_headroom_ma": 3.493,
    "trip_flow_headroom_m3_h": 39.2,
    "overall_pass_score": 1.0,
}


def _sample_ssc18_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=48, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "control-loop-signal-package" in templates
    config = templates["control-loop-signal-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "instrumentation-control"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=48, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc18_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "OP-SSC18-LOOP-001",
        "PID-18-101",
        "FIC-18-101",
        "FCV-18-101",
        "FIT-18-101",
        "ALM-18-FLOW-101",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc18_instance(tmp_path)
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
