# ABOUTME: Tests the SSC-01 road low-point resilience built-in task template.
# ABOUTME: Covers discovery, deterministic drainage/ITS metrics, and generated verifier output.

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
    / "civil"
    / "road_low_point_resilience_package"
)


EXPECTED_METRICS = {
    "peak_runoff_m3_s": 0.292,
    "gutter_approach_flow_m3_s": 0.352,
    "spread_width_m": 5.132,
    "spread_margin_m": 0.868,
    "curb_depth_m": 0.128,
    "inlet_intercepted_flow_m3_s": 0.289,
    "residual_ponding_flow_m3_s": 0.063,
    "hgl_upstream_m": 41.693,
    "hgl_clearance_mm": 506.645,
    "cabinet_freeboard_m": 0.252,
    "cabinet_flood_depth_m": 0.0,
    "vms_reading_time_s": 8.778,
    "vms_message_margin_chars": 7.113,
    "network_headroom_mbps": 24.8,
    "battery_runtime_h": 10.169,
    "battery_margin_h": 4.169,
    "overall_pass_score": 1.0,
}


def _sample_ssc01_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=50, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "road-low-point-resilience-package" in templates
    config = templates["road-low-point-resilience-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "road-resilience"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=50, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc01_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "RD-SSC01-001",
        "LP-01",
        "DRN-PIT-01",
        "HGL-01",
        "CAB-01",
        "VMS-01",
        "BATT-01",
        "gutter Manning `n = 0.016` exactly",
        "pipe Manning `n = 0.013` exactly",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc01_instance(tmp_path)
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
