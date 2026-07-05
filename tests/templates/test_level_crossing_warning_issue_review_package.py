# ABOUTME: Tests the SSC-02 review-first level-crossing issue package.
# ABOUTME: Checks source-pack generation, variant localization, and custom verifier behavior.

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

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
    / "level_crossing_warning_issue_review_package"
)


def _base_params(packet_variant: str = "clean") -> dict[str, object]:
    return {
        "maximum_train_speed_kmh": 80.0,
        "minimum_warning_time_s": 25.0,
        "warning_time_margin_s": 6.0,
        "warning_time_deficit_s": 3.0,
        "gate_lowering_time_s": 10.0,
        "gate_start_delay_s": 3.0,
        "required_gate_horizontal_before_arrival_s": 5.0,
        "gate_horizontal_margin_s": 4.0,
        "controller_load_w": 180.0,
        "flashing_light_load_w": 40.0,
        "flashing_light_count": 4,
        "gate_mechanism_load_w": 90.0,
        "gate_mechanism_count": 2,
        "comms_switch_load_w": 45.0,
        "track_circuit_load_w": 65.0,
        "event_recorder_load_w": 25.0,
        "load_future_allowance_pct": 10.0,
        "required_autonomy_h": "8",
        "battery_runtime_margin_h": 1.2,
        "dc_system_voltage_v": 48.0,
        "depth_of_discharge_pct": 80.0,
        "temperature_derating_factor": 0.85,
        "inverter_efficiency_pct": 92.0,
        "battery_block_voltage_v": 12.0,
        "load_power_factor": 0.9,
        "selected_ups_rating_margin_va": 120.0,
        "feeder_length_m": 30.0,
        "feeder_resistance_milliohm_per_m": 1.83,
        "max_voltage_drop_percent": 5.0,
        "fiber_length_km": 1.8,
        "fiber_attenuation_db_per_km": 0.35,
        "fiber_connector_count": 4,
        "connector_loss_db": 0.3,
        "fiber_splice_count": 6,
        "splice_loss_db": 0.05,
        "patch_panel_allowance_db": 1.0,
        "optical_tx_power_dbm": -3.0,
        "receiver_sensitivity_dbm": -24.0,
        "required_fiber_margin_db": 3.0,
        "packet_variant": packet_variant,
    }


def _sample_review_instance(tmp_path: Path, seed: int = 20260706) -> tuple[Path, dict]:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty_name="medium", seed=seed, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    return instance_dir, instance.ground_truth


def test_template_is_discoverable_and_review_native() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    config = templates["level-crossing-warning-issue-review-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "rail-review"
    assert config.meta.tool_mode == "no-tool"


def test_engine_localizes_clean_missing_and_genuine_failure_variants() -> None:
    _config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)

    clean = engine.compute(**_base_params("clean"))
    missing = engine.compute(**_base_params("missing_battery_capacity"))
    deficient = engine.compute(**_base_params("warning_time_deficient"))

    assert clean["rlr_04_status"] == 0.0
    assert clean["readiness_code"] == 0.0
    assert "battery_runtime_h" in clean

    assert missing["rlr_04_status"] == 3.0
    assert missing["readiness_code"] == 2.0
    assert "battery_runtime_h" not in missing
    assert missing["required_information_requests_count"] == 1.0

    assert deficient["rlr_04_status"] == 1.0
    assert deficient["readiness_code"] == 2.0
    assert deficient["warning_time_margin_s"] < 0.0
    assert deficient["required_findings_count"] == 1.0


def test_generated_instance_has_file_backed_sources_and_no_calc_tool(tmp_path: Path) -> None:
    instance_dir, _ground_truth = _sample_review_instance(tmp_path)

    source_dir = instance_dir / "environment" / "sources"
    source_names = {path.name for path in source_dir.iterdir()}
    assert source_names == {
        "backup-power-comms.md",
        "criteria-comments.md",
        "crossing-control-layout.md",
        "degraded-mode-operations.md",
        "document-register.md",
        "route-profile.md",
        "sighting-warning-time.md",
    }
    assert not list((instance_dir / "environment").glob("*_calc.py"))

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "source packet has been placed in `/workspace/sources/`" in instruction
    assert "missing_battery_capacity" not in instruction
    assert "warning_time_deficient" not in instruction
    assert re.search(r"\d+\.\d", instruction) is None


def test_warning_time_evidence_recomputes_from_rendered_sources(tmp_path: Path) -> None:
    instance_dir, ground_truth = _sample_review_instance(tmp_path)
    warning_source = (instance_dir / "environment" / "sources" / "sighting-warning-time.md").read_text(
        encoding="utf-8"
    )

    speed_kmh = float(re.search(r"Maximum train speed \\| ([\\d.]+) km/h", warning_source).group(1))
    strike_in_m = float(re.search(r"Strike-in distance \\| ([\\d.]+) m", warning_source).group(1))
    minimum_warning_s = float(re.search(r"Minimum warning time \\| ([\\d.]+) s", warning_source).group(1))
    gate_start_s = float(re.search(r"Gate start delay \\| ([\\d.]+) s", warning_source).group(1))
    gate_lower_s = float(re.search(r"Gate lowering time \\| ([\\d.]+) s", warning_source).group(1))
    gate_required_s = float(
        re.search(r"Required gates-horizontal time before arrival \\| ([\\d.]+) s", warning_source).group(1)
    )

    provided_warning_s = strike_in_m / (speed_kmh / 3.6)
    warning_margin_s = provided_warning_s - minimum_warning_s
    gate_margin_s = provided_warning_s - gate_start_s - gate_lower_s - gate_required_s

    assert round(provided_warning_s, 3) == round(ground_truth["provided_warning_time_s"], 3)
    assert round(warning_margin_s, 3) == round(ground_truth["warning_time_margin_s"], 3)
    assert round(gate_margin_s, 3) == round(ground_truth["gate_horizontal_margin_s"], 3)


def test_custom_verifier_scores_golden_pass_and_fluent_fail(tmp_path: Path) -> None:
    instance_dir, _ground_truth = _sample_review_instance(tmp_path)
    reward_file = tmp_path / "reward.json"

    for fixture_name, expected_reward in [("golden_pass.md", 1.0), ("golden_fail.md", 0.5)]:
        result = subprocess.run(
            [
                sys.executable,
                str(instance_dir / "tests" / "verify.py"),
                "--input",
                str(instance_dir / "tests" / "fixtures" / fixture_name),
                "--output",
                str(reward_file),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        reward = json.loads(reward_file.read_text(encoding="utf-8"))["reward"]
        if expected_reward == 1.0:
            assert reward == 1.0
        else:
            assert reward <= expected_reward
