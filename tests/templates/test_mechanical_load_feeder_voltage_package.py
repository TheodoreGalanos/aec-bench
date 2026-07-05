# ABOUTME: Tests the SSC-05 mechanical-load feeder and voltage package template.
# ABOUTME: Covers discovery, deterministic feeder metrics, and generated verifier output.

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
    / "mechanical_load_feeder_voltage_package"
)


EXPECTED_METRICS = {
    "connected_load_kw": 59.8,
    "demand_load_kw": 43.44,
    "future_allowance_kw": 6.516,
    "design_load_kw": 49.956,
    "initial_reactive_power_kvar": 34.87,
    "required_capacitor_kvar": 15.126,
    "selected_capacitor_margin_kvar": 4.874,
    "corrected_apparent_power_kva": 53.716,
    "feeder_current_a": 74.73,
    "derated_cable_ampacity_a": 107.386,
    "ampacity_margin_a": 32.655,
    "breaker_allowable_current_a": 80.0,
    "breaker_margin_a": 5.27,
    "voltage_drop_v": 17.337,
    "feeder_voltage_drop_percent": 4.178,
    "voltage_drop_margin_percent": 0.822,
    "overall_pass_score": 1.0,
}


def _sample_ssc05_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=58, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "mechanical-load-feeder-voltage-package" in templates
    config = templates["mechanical-load-feeder-voltage-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "feeder-voltage"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=58, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc05_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CASE-SSC05-FEEDER-001",
        "LOAD-05-MECH-SCHED-01",
        "SLD-05-MCC-01",
        "FEEDER-05-MCC-01",
        "CABLE-05-FDR-01",
        "PROT-05-BKR-01",
        "CRIT-05-VDROP-01",
        "MEMO-05-ELEC-LOAD-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc05_instance(tmp_path)
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
