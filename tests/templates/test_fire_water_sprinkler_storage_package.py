# ABOUTME: Tests the SSC-19 fire-water sprinkler storage package template.
# ABOUTME: Covers discovery, deterministic fire-water metrics, and generated verifier output.

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
    / "fire_water_sprinkler_storage_package"
)


EXPECTED_METRICS = {
    "sprinkler_demand_gpm": 300.0,
    "total_fire_demand_gpm": 550.0,
    "sprinkler_head_discharge_gpm": 21.689,
    "required_remote_head_count": 14.0,
    "remote_head_count_margin": 2.0,
    "pressure_drop_test_psi": 22.0,
    "supply_curve_coefficient": 169.564,
    "available_flow_20psi_gpm": 1402.097,
    "water_supply_flow_margin_gpm": 852.097,
    "residual_pressure_at_demand_psi": 61.162,
    "friction_loss_per_ft_psi": 0.0884,
    "equivalent_length_ft": 300.0,
    "total_friction_loss_psi": 26.51,
    "elevation_pressure_loss_psi": 16.454,
    "available_riser_pressure_psi": 18.198,
    "boosted_riser_pressure_psi": 43.198,
    "required_riser_pressure_psi": 35.0,
    "pressure_margin_psi": 8.198,
    "required_storage_gal": 33000.0,
    "storage_margin_gal": 3000.0,
    "overall_pass_score": 1.0,
}


def _sample_ssc19_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=60, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "fire-water-sprinkler-storage-package" in templates
    config = templates["fire-water-sprinkler-storage-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "fire-protection"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=60, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc19_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "CASE-SSC19-FIRE-001",
        "HAZ-19-STORAGE-01",
        "HYD-19-TEST-01",
        "CURVE-19-SUPPLY-01",
        "SPR-19-AREA-01",
        "SPR-19-HEAD-01",
        "PIPE-19-RISER-01",
        "ELEV-19-ZONE-01",
        "PUMP-19-BOOST-01",
        "TANK-19-STORAGE-01",
        "CRIT-19-AHJ-01",
        "MEMO-19-FIRE-WATER-01",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc19_instance(tmp_path)
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
