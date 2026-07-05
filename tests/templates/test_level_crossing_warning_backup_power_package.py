# ABOUTME: Tests the SSC-02 level-crossing warning and backup-power package template.
# ABOUTME: Covers discovery, deterministic rail-crossing metrics, and generated verifier output.

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
    / "level_crossing_warning_backup_power_package"
)


EXPECTED_METRICS = {
    "maximum_train_speed_m_s": 22.222,
    "total_warning_time_s": 40.0,
    "strike_in_distance_m": 888.889,
    "minimum_warning_margin_s": 20.0,
    "gate_horizontal_margin_s": 21.0,
    "connected_signal_load_w": 655.0,
    "design_signal_load_w": 720.5,
    "required_energy_kwh": 5.764,
    "required_battery_capacity_ah": 191.949,
    "battery_capacity_margin_ah": 8.051,
    "required_ups_rating_va": 800.556,
    "ups_rating_margin_va": 99.444,
    "battery_block_count": 4.0,
    "dc_feeder_current_a": 15.01,
    "dc_feeder_voltage_drop_v": 1.648,
    "dc_feeder_voltage_drop_percent": 3.434,
    "dc_voltage_drop_margin_percent": 1.566,
    "fiber_total_loss_db": 3.13,
    "fiber_receive_power_dbm": -6.13,
    "fiber_link_margin_db": 17.87,
    "fiber_excess_margin_db": 14.87,
    "overall_pass_score": 1.0,
}


def _sample_ssc02_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=59, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "level-crossing-warning-backup-power-package" in templates
    config = templates["level-crossing-warning-backup-power-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "rail-signalling"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=59, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc02_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CASE-SSC02-LX-001",
        "ROUTE-02-PROFILE-01",
        "LX-02-LAYOUT-01",
        "WT-02-WARN-01",
        "CTRL-02-XING-01",
        "LOAD-02-SIG-01",
        "BATT-02-UPS-01",
        "FEEDER-02-DC-01",
        "FIBER-02-COMMS-01",
        "OPS-02-DEGRADED-01",
        "MEMO-02-LX-OPS-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc02_instance(tmp_path)
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
