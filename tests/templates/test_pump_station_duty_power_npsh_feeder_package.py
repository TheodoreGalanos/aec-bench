# ABOUTME: Tests the SSC-06 pump station duty, power, NPSH, and feeder template.
# ABOUTME: Covers discovery, deterministic pump-duty metrics, and generated verifier output.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aec_bench.contracts.task_definition import Lifecycle, Visibility
from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.templates.registry import discover_templates, load_template

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "mechanical"
    / "pump_station_duty_power_npsh_feeder_package"
)


EXPECTED_METRICS = {
    "hazen_williams_headloss_m": 4.585,
    "flow_velocity_m_s": 1.467,
    "minor_loss_m": 0.57,
    "total_dynamic_head_m": 23.555,
    "pump_curve_head_margin_m": 2.045,
    "hydraulic_power_kw": 16.604,
    "shaft_power_kw": 22.438,
    "motor_input_power_kw": 23.87,
    "required_motor_power_kw": 25.804,
    "motor_size_margin_kw": 4.196,
    "npsh_available_m": 11.792,
    "npsh_margin_m": 4.392,
    "npsh_margin_ratio": 1.594,
    "load_reactive_power_kvar": 14.164,
    "feeder_current_a": 33.386,
    "feeder_voltage_drop_percent": 1.623,
    "voltage_drop_margin_percent": 2.377,
    "overall_pass_score": 1.0,
}


def _sample_ssc06_instance(tmp_path: Path) -> Path:
    loaded_template = load_template(TEMPLATE_DIR)
    template_dir = loaded_template.path
    instance = sample_instance(loaded_template, difficulty_name="easy", seed=56, instance_index=0)
    (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(
        loaded_template,
        instance,
        tmp_path,
        task_lifecycle=Lifecycle.PROPOSED,
        task_visibility=Visibility.PUBLIC,
    )


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {template.config.meta.name: template.config for template in discover_templates()[0]}

    assert "pump-station-duty-power-npsh-feeder-package" in templates
    config = templates["pump-station-duty-power-npsh-feeder-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "pump-station-duty"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    loaded_template = load_template(TEMPLATE_DIR)
    instance = sample_instance(loaded_template, difficulty_name="easy", seed=56, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc06_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CASE-SSC06-PUMP-DUTY-001",
        "EQUIP-06-PUMP-01",
        "WW-06-WETWELL-01",
        "RM-06-RISING-MAIN-01",
        "CURVE-06-PUMP-01",
        "MOTOR-06-SCHED-01",
        "NPSH-06-SUCTION-01",
        "FEEDER-06-480V-01",
        "MEMO-06-SELECTION-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc06_instance(tmp_path)
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
