# ABOUTME: Tests the SSC-13 road visual operations built-in task template.
# ABOUTME: Covers discovery, deterministic source-pack calculations, and generated verifier output.

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
    / "road_visual_operations_package"
)


EXPECTED_METRICS = {
    "average_illuminance_lux": 18.875,
    "minimum_illuminance_lux": 16.8,
    "uniformity_ratio": 0.89,
    "cctv_01_pixels_per_meter": 80.0,
    "cctv_02_pixels_per_meter": 60.0,
    "cctv_01_storage_tb": 0.99792,
    "cctv_02_storage_tb": 0.99792,
    "total_cctv_storage_tb": 1.99584,
    "total_network_load_mbps": 16.7,
    "poe_load_w": 44.0,
    "poe_headroom_w": 76.0,
    "fibre_loss_db": 2.347,
    "fibre_margin_db": 12.653,
    "ups_energy_kwh": 1.271,
}


def _sample_ssc13_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=42, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "road-visual-operations-package" in templates
    config = templates["road-visual-operations-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "road-visual-operations"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=42, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc13_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "RD-SSC13-001",
        "NIGHT-INCIDENT-01",
        "CCTV-01",
        "CCTV-02",
        "MSG-POL-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc13_instance(tmp_path)
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
