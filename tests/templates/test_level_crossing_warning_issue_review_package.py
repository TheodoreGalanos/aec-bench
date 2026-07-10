# ABOUTME: Tests the SSC-02 review-first level-crossing issue package.
# ABOUTME: Checks source-pack generation, variant localization, and custom verifier behavior.

from __future__ import annotations

import json
import math
import re
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
    / "level_crossing_warning_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{index}_status" for index in range(1, 10)]
EVIDENCE_KEYS = [
    "maximum_train_speed_m_s",
    "provided_warning_time_s",
    "strike_in_distance_m",
    "warning_time_margin_s",
    "gate_horizontal_margin_s",
    "design_signal_load_w",
    "required_battery_capacity_ah",
    "installed_battery_capacity_ah",
    "battery_runtime_h",
    "battery_runtime_margin_h",
    "dc_voltage_drop_margin_percent",
    "fiber_link_margin_db",
]
SOURCE_FILES = [
    "sources/document-register.md",
    "sources/route-profile.md",
    "sources/sighting-warning-time.md",
    "sources/crossing-control-layout.md",
    "sources/backup-power-comms.md",
    "sources/degraded-mode-operations.md",
    "sources/criteria-comments.md",
]
VARIANT_EXPECTATIONS = {
    "clean": ({}, 0.0, 0.0, 0.0, 0.0),
    "missing_battery_capacity": ({"rlr_04_status": 3.0}, 2.0, 0.0, 1.0, 0.0),
    "stale_warning_revision": ({"rlr_03_status": 1.0}, 2.0, 1.0, 0.0, 0.0),
    "chainage_sighting_mismatch": ({"rlr_02_status": 1.0}, 2.0, 1.0, 0.0, 0.0),
    "scenario_copy_forward": ({"rlr_05_status": 1.0}, 2.0, 1.0, 0.0, 0.0),
    "open_critical_comment": ({"rlr_07_status": 1.0}, 2.0, 1.0, 0.0, 0.0),
    "minor_open_comment_carried": ({}, 1.0, 0.0, 0.0, 1.0),
    "warning_time_deficient": ({"rlr_04_status": 1.0}, 2.0, 1.0, 0.0, 0.0),
}


def _base_params(packet_variant: str = "clean") -> dict[str, object]:
    return {
        "maximum_train_speed_kmh": 80.0,
        "minimum_warning_time_s": 25.0,
        "warning_time_margin_s": 6.0,
        "warning_time_deficit_s": 3.0,
        "gate_lowering_time_s": 10.0,
        "gate_start_delay_s": 3.0,
        "required_gate_horizontal_before_arrival_s": 5.0,
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
        "load_power_factor": 0.9,
        "selected_ups_rating_margin_va": 120.0,
        "voltage_drop_margin_target_percent": 1.0,
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


def _load() -> tuple:
    config, template_dir = load_template(TEMPLATE_DIR)
    return config, template_dir, load_engine_module(template_dir)


def _instance_for_variant(variant: str, max_seeds: int = 800):
    config, template_dir, engine = _load()
    for seed in range(max_seeds):
        instance = sample_instance(config, engine.compute, difficulty_name="medium", seed=seed, instance_index=0)
        if instance.all_params["packet_variant"] == variant:
            return config, template_dir, engine, instance
    raise AssertionError(f"Could not sample variant {variant!r}")


def _scaffold_variant(tmp_path: Path, variant: str) -> tuple[Path, dict]:
    config, template_dir, _engine, instance = _instance_for_variant(variant)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    return instance_dir, instance.ground_truth


def _run_verifier(instance_dir: Path, input_file: Path, tmp_path: Path) -> tuple[float, dict]:
    reward_file = tmp_path / "reward.json"
    result = subprocess.run(
        [
            sys.executable,
            str(instance_dir / "tests" / "verify.py"),
            "--input",
            str(input_file),
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
    details = json.loads((reward_file.parent / "details.json").read_text(encoding="utf-8"))
    return reward, details


def _extract_json_block(text: str) -> dict:
    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    assert matches
    return json.loads(matches[-1])


def _replace_json_block(text: str, payload: dict) -> str:
    return re.sub(
        r"```json\s*\n(.*?)\n\s*```",
        "```json\n" + json.dumps(payload, indent=2) + "\n```",
        text,
        count=1,
        flags=re.DOTALL,
    )


def test_template_is_discoverable_and_review_native() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    config = templates["level-crossing-warning-issue-review-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "rail-review"
    assert config.meta.tool_mode == "no-tool"


def test_parameters_vary_across_seeds_and_do_not_include_dead_inputs() -> None:
    config, _template_dir, engine = _load()
    samples = [
        sample_instance(config, engine.compute, difficulty_name="medium", seed=seed, instance_index=0)
        for seed in range(40)
    ]

    assert len({sample.ground_truth["strike_in_distance_m"] for sample in samples}) >= 10
    assert len({sample.all_params["packet_variant"] for sample in samples}) >= 3
    assert "gate_horizontal_margin_s" not in config.params
    assert "battery_block_voltage_v" not in config.params


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    first = sample_instance(config, engine.compute, difficulty_name="medium", seed=20260710, instance_index=0)
    second = sample_instance(config, engine.compute, difficulty_name="medium", seed=20260710, instance_index=0)

    assert first.all_params == second.all_params
    assert first.ground_truth == second.ground_truth


def test_engine_quantizes_before_derivation() -> None:
    _config, _template_dir, engine = _load()
    params = _base_params()
    params["maximum_train_speed_kmh"] = 80.04
    params["temperature_derating_factor"] = 0.854

    quantized = engine._quantize(params)

    assert quantized["maximum_train_speed_kmh"] == 80.0
    assert quantized["temperature_derating_factor"] == 0.85


@pytest.mark.parametrize("variant", VARIANT_EXPECTATIONS)
def test_variant_gold_statuses_and_readiness(variant: str) -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant(variant)
    flips, readiness, findings, requests, carried = VARIANT_EXPECTATIONS[variant]

    for key in STATUS_KEYS:
        assert instance.ground_truth[key] == flips.get(key, 0.0)
    assert instance.ground_truth["readiness_code"] == readiness
    assert instance.ground_truth["required_findings_count"] == findings
    assert instance.ground_truth["required_information_requests_count"] == requests
    assert instance.ground_truth["required_carried_actions_count"] == carried


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


@pytest.mark.parametrize(
    ("variant", "expected_changed"),
    [
        ("missing_battery_capacity", {"sources/backup-power-comms.md"}),
        ("stale_warning_revision", {"sources/sighting-warning-time.md"}),
        ("chainage_sighting_mismatch", {"sources/route-profile.md"}),
        ("scenario_copy_forward", {"sources/degraded-mode-operations.md"}),
        ("open_critical_comment", {"sources/criteria-comments.md"}),
        ("minor_open_comment_carried", {"sources/criteria-comments.md"}),
        ("warning_time_deficient", {"sources/sighting-warning-time.md"}),
    ],
)
def test_each_variant_changes_only_its_intended_source(variant: str, expected_changed: set[str]) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    clean_params = dict(instance.all_params)
    clean_params["packet_variant"] = "clean"
    clean = engine.build_sources(clean_params)
    changed = {path for path, content in engine.build_sources(instance.all_params).items() if content != clean[path]}

    assert changed == expected_changed


def test_stale_warning_variant_has_a_real_register_revision_mismatch() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("stale_warning_revision")
    sources = engine.build_sources(instance.all_params)

    assert "SIGHT-SSC02-LX-01 | Sighting and warning time worksheet | Rev B" in sources["sources/document-register.md"]
    assert "SIGHT-SSC02-LX-01 (Rev A)" in sources["sources/sighting-warning-time.md"]


def test_chainage_variant_requires_cross_file_identity_reconciliation() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("chainage_sighting_mismatch")
    sources = engine.build_sources(instance.all_params)

    assert "Crossing ID | LX-SSC02-041" in sources["sources/route-profile.md"]
    assert "Crossing ID: LX-SSC02-014" in sources["sources/sighting-warning-time.md"]
    assert "Identity note:" not in sources["sources/sighting-warning-time.md"]


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

    system_prompt = (instance_dir / "environment" / "system_prompt.md").read_text(encoding="utf-8")
    assert system_prompt == (TEMPLATE_DIR / "system_prompt.md").read_text(encoding="utf-8")
    assert "8-12 turns" in system_prompt
    assert "Do not rename `computed_evidence` keys" in system_prompt
    for key in EVIDENCE_KEYS:
        assert key in instruction
        assert key in system_prompt

    dockerfile = (instance_dir / "environment" / "Dockerfile").read_text(encoding="utf-8")
    for source_name in source_names:
        assert f"COPY sources/{source_name} /workspace/sources/{source_name}" in dockerfile
    assert (instance_dir / "tests" / "instance.json").exists()
    assert (instance_dir / "tests" / "verify.py").read_text(encoding="utf-8") == (TEMPLATE_DIR / "verify.py").read_text(
        encoding="utf-8"
    )
    assert all(f"RLR-0{index}" in instruction for index in range(1, 10))


def test_warning_time_evidence_recomputes_from_rendered_sources(tmp_path: Path) -> None:
    instance_dir, ground_truth = _sample_review_instance(tmp_path)
    warning_source = (instance_dir / "environment" / "sources" / "sighting-warning-time.md").read_text(encoding="utf-8")

    speed_kmh = float(re.search(r"Maximum train speed \| ([\d.]+) km/h", warning_source).group(1))
    strike_in_m = float(re.search(r"Strike-in distance \| ([\d.]+) m", warning_source).group(1))
    minimum_warning_s = float(re.search(r"Minimum warning time \| ([\d.]+) s", warning_source).group(1))
    gate_start_s = float(re.search(r"Gate start delay \| ([\d.]+) s", warning_source).group(1))
    gate_lower_s = float(re.search(r"Gate lowering time \| ([\d.]+) s", warning_source).group(1))
    gate_required_s = float(
        re.search(r"Required gates-horizontal time before arrival \| ([\d.]+) s", warning_source).group(1)
    )

    provided_warning_s = strike_in_m / (speed_kmh / 3.6)
    warning_margin_s = provided_warning_s - minimum_warning_s
    gate_margin_s = provided_warning_s - gate_start_s - gate_lower_s - gate_required_s

    assert round(provided_warning_s, 3) == round(ground_truth["provided_warning_time_s"], 3)
    assert round(warning_margin_s, 3) == round(ground_truth["warning_time_margin_s"], 3)
    assert round(gate_margin_s, 3) == round(ground_truth["gate_horizontal_margin_s"], 3)


def _row_value(label: str, text: str) -> float:
    match = re.search(rf"\| {re.escape(label)} \| (-?[\d.]+)", text)
    assert match, label
    return float(match.group(1))


@pytest.mark.parametrize("variant", VARIANT_EXPECTATIONS)
def test_all_evidence_recomputes_from_rendered_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    sources = engine.build_sources(instance.all_params)
    route = sources["sources/route-profile.md"]
    warning = sources["sources/sighting-warning-time.md"]
    layout = sources["sources/crossing-control-layout.md"]
    backup = sources["sources/backup-power-comms.md"]

    speed_kmh = _row_value("Maximum train speed", route)
    speed_m_s = speed_kmh / 3.6
    strike_in_m = _row_value("Strike-in distance", warning)
    provided_warning_s = strike_in_m / speed_m_s
    minimum_warning_s = _row_value("Minimum warning time", warning)
    warning_margin_s = provided_warning_s - minimum_warning_s
    gate_margin_s = (
        provided_warning_s
        - _row_value("Gate start delay", warning)
        - _row_value("Gate lowering time", warning)
        - _row_value("Required gates-horizontal time before arrival", warning)
    )

    connected_load_w = (
        _row_value("Controller load", layout)
        + _row_value("Flashing-light load", layout) * _row_value("Flashing-light count", layout)
        + _row_value("Gate mechanism load", layout) * _row_value("Gate mechanism count", layout)
        + _row_value("Communications switch load", backup)
        + _row_value("Track circuit load", layout)
        + _row_value("Event recorder load", layout)
    )
    design_signal_load_w = connected_load_w * (1.0 + _row_value("Load future allowance", backup) / 100.0)
    usable_fraction = (
        _row_value("Depth of discharge", backup)
        / 100.0
        * _row_value("Temperature derating factor", backup)
        * _row_value("Inverter efficiency", backup)
        / 100.0
    )
    required_autonomy_h = _row_value("Required autonomy", backup)
    dc_voltage_v = _row_value("DC system voltage", backup)
    required_capacity_ah = design_signal_load_w * required_autonomy_h / (dc_voltage_v * usable_fraction)

    feeder_current_a = design_signal_load_w / dc_voltage_v
    feeder_drop_v = (
        2.0 * feeder_current_a * _row_value("Feeder length", backup) * _row_value("Feeder resistance", backup) / 1000.0
    )
    voltage_drop_margin = _row_value("Maximum voltage drop", backup) - feeder_drop_v / dc_voltage_v * 100.0

    fiber_loss_db = (
        _row_value("Fiber length", backup) * _row_value("Fiber attenuation", backup)
        + _row_value("Fiber connector count", backup) * _row_value("Connector loss", backup)
        + _row_value("Fiber splice count", backup) * _row_value("Splice loss", backup)
        + _row_value("Patch panel allowance", backup)
    )
    fiber_receive_dbm = _row_value("Optical TX power", backup) - fiber_loss_db
    fiber_link_margin_db = fiber_receive_dbm - _row_value("Receiver sensitivity", backup)

    recomputed = {
        "maximum_train_speed_m_s": speed_m_s,
        "provided_warning_time_s": provided_warning_s,
        "strike_in_distance_m": strike_in_m,
        "warning_time_margin_s": warning_margin_s,
        "gate_horizontal_margin_s": gate_margin_s,
        "design_signal_load_w": design_signal_load_w,
        "required_battery_capacity_ah": required_capacity_ah,
        "dc_voltage_drop_margin_percent": voltage_drop_margin,
        "fiber_link_margin_db": fiber_link_margin_db,
    }
    if variant != "missing_battery_capacity":
        installed_capacity_ah = _row_value("Installed battery capacity", backup)
        battery_runtime_h = installed_capacity_ah * dc_voltage_v * usable_fraction / design_signal_load_w
        recomputed.update(
            {
                "installed_battery_capacity_ah": installed_capacity_ah,
                "battery_runtime_h": battery_runtime_h,
                "battery_runtime_margin_h": battery_runtime_h - required_autonomy_h,
            }
        )

    assert set(recomputed) == {key for key in EVIDENCE_KEYS if key in instance.ground_truth}
    for key, value in recomputed.items():
        assert math.isclose(value, instance.ground_truth[key], rel_tol=0.01, abs_tol=0.02), key


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


@pytest.mark.parametrize("variant", VARIANT_EXPECTATIONS)
def test_golden_pass_scores_one_for_every_variant(tmp_path: Path, variant: str) -> None:
    instance_dir, _ground_truth = _scaffold_variant(tmp_path, variant)

    reward, _details = _run_verifier(
        instance_dir,
        instance_dir / "tests" / "fixtures" / "golden_pass.md",
        tmp_path,
    )

    assert reward == 1.0


@pytest.mark.parametrize("variant", ["clean", "warning_time_deficient"])
def test_fluent_unsafe_memo_scores_at_most_half(tmp_path: Path, variant: str) -> None:
    instance_dir, _ground_truth = _scaffold_variant(tmp_path, variant)

    reward, _details = _run_verifier(
        instance_dir,
        instance_dir / "tests" / "fixtures" / "golden_fail.md",
        tmp_path,
    )

    assert reward <= 0.5


def test_verifier_localizes_flipped_status(tmp_path: Path) -> None:
    instance_dir, _ground_truth = _scaffold_variant(tmp_path, "warning_time_deficient")
    golden_path = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    payload = _extract_json_block(golden_path.read_text(encoding="utf-8"))
    payload["review_matrix"]["RLR-04"]["status"] = "pass"
    mutated = tmp_path / "mutated.md"
    mutated.write_text(_replace_json_block(golden_path.read_text(encoding="utf-8"), payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)

    assert reward < 1.0
    assert details["gates"]["matrix"]["items"]["RLR-04"] == 0.0


def test_verifier_gates_matrix_and_readiness_on_evidence(tmp_path: Path) -> None:
    instance_dir, _ground_truth = _scaffold_variant(tmp_path, "clean")
    golden_path = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    payload = _extract_json_block(golden_path.read_text(encoding="utf-8"))
    payload["computed_evidence"] = {}
    stripped = tmp_path / "stripped.md"
    stripped.write_text(_replace_json_block(golden_path.read_text(encoding="utf-8"), payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, stripped, tmp_path)

    assert reward <= 0.6
    assert details["gates"]["readiness"]["score"] == 0.0
    assert details["gates"]["matrix"]["items"]["RLR-03"] == 0.0
    assert details["gates"]["matrix"]["items"]["RLR-04"] == 0.0
    assert details["gates"]["matrix"]["items"]["RLR-06"] == 0.0


def test_verifier_zeroes_unsupported_ready_decision(tmp_path: Path) -> None:
    instance_dir, _ground_truth = _scaffold_variant(tmp_path, "warning_time_deficient")
    golden_path = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    payload = _extract_json_block(golden_path.read_text(encoding="utf-8"))
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "ready.md"
    mutated.write_text(_replace_json_block(golden_path.read_text(encoding="utf-8"), payload), encoding="utf-8")

    _reward, details = _run_verifier(instance_dir, mutated, tmp_path)

    assert details["gates"]["readiness"]["score"] == 0.0
