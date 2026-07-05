# ABOUTME: Tests the SSC-15 product submittal compliance package template.
# ABOUTME: Covers discovery, deterministic submittal metrics, and verifier output.

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
    / "product_submittal_compliance_package"
)


EXPECTED_METRICS = {
    "flow_capacity_margin_l_s": 3.0,
    "flow_capacity_ratio": 1.071,
    "head_capacity_margin_m": 2.0,
    "head_capacity_ratio": 1.053,
    "bep_flow_percent": 105.0,
    "por_min_flow_l_s": 28.0,
    "por_max_flow_l_s": 48.0,
    "por_low_margin_l_s": 14.0,
    "por_high_margin_l_s": 6.0,
    "motor_available_kw": 34.5,
    "motor_margin_kw": 11.5,
    "pressure_certificate_margin_kpa": 140.0,
    "evidence_completeness_percent": 100.0,
    "certificate_match_percent": 100.0,
    "review_closeout_percent": 100.0,
    "review_days_remaining": 4.0,
    "approved_deviation_count": 1.0,
    "unresolved_deviation_count": 0.0,
    "open_critical_comments": 0.0,
    "overall_pass_score": 1.0,
}


def _sample_ssc15_instance(tmp_path: Path) -> Path:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=64, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "product-submittal-compliance-package" in templates
    config = templates["product-submittal-compliance-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "product-compliance"


def test_engine_reproduces_task_owned_source_pack_metrics() -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="easy", seed=64, instance_index=0)

    assert instance.ground_truth == pytest.approx(EXPECTED_METRICS)


def test_generated_instance_contains_source_bound_instruction(tmp_path: Path) -> None:
    instance_dir = _sample_ssc15_instance(tmp_path)
    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")

    for required_text in [
        "SUB-15-PKG-001",
        "REG-15-SUB-001",
        "DAT-15-PUMP-001",
        "CERT-15-PRESS-001",
        "CALC-15-DUTY-001",
        "CMT-15-REVIEW-001",
        "DEV-15-LOG-001",
        "MEMO-15-DISP-001",
        "task-owned synthetic source pack",
        "Do not claim authority approval",
    ]:
        assert required_text in instruction


def test_generated_verifier_scores_golden_pass_at_one(tmp_path: Path) -> None:
    instance_dir = _sample_ssc15_instance(tmp_path)
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
