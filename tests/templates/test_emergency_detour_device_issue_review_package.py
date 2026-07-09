# ABOUTME: Tests the SSC-01 review-first emergency detour device issue review template.
# ABOUTME: Covers variant gold states, generated source packs, and the stage-gated review verifier.

from __future__ import annotations

import json
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
    / "emergency_detour_device_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "vms_reading_time_s",
    "vms_message_margin_chars",
    "required_network_mbps",
    "network_headroom_mbps",
    "rf_received_power_dbm",
    "rf_link_margin_db",
    "battery_runtime_h",
    "battery_margin_h",
    "feeder_voltage_drop_percent",
    "voltage_drop_margin_percent",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_closure_duration": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_detour_plan_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "device_inventory_mismatch": {
        "flips": {"rlr_02_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "scenario_copy_forward": {
        "flips": {"rlr_05_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "open_critical_comment": {
        "flips": {"rlr_07_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "minor_open_comment_carried": {
        "flips": {},
        "readiness": 1.0,
        "findings": 0.0,
        "requests": 0.0,
        "carried": 1.0,
    },
    "battery_runtime_deficient": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/detour-plan.md",
    "sources/message-library.md",
    "sources/device-inventory.md",
    "sources/communications-topology.md",
    "sources/power-continuity-schedule.md",
    "sources/criteria-comments.md",
]


def _load() -> tuple:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    return config, template_dir, engine


def _instance_for_variant(variant: str, max_seeds: int = 1000):
    config, template_dir, engine = _load()
    for seed in range(max_seeds):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        if instance.all_params["packet_variant"] == variant:
            return config, template_dir, engine, instance
    pytest.fail(f"No instance with variant {variant!r} found in {max_seeds} seeds")


def _scaffold_variant(tmp_path: Path, variant: str) -> tuple[Path, dict]:
    config, template_dir, engine, instance = _instance_for_variant(variant)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    return instance_dir, instance.ground_truth


def _run_verifier(instance_dir: Path, input_file: Path, tmp_path: Path) -> tuple[float, dict]:
    reward_file = tmp_path / f"reward-{input_file.stem}.json"
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
    assert matches, "No fenced JSON block found"
    return json.loads(matches[-1])


def _replace_json_block(text: str, payload: dict) -> str:
    block = "```json\n" + json.dumps(payload, indent=2) + "\n```"
    return re.sub(r"```json\s*\n.*?\n\s*```", lambda _m: block, text, count=1, flags=re.DOTALL)


def _grab(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    assert match, f"Pattern not found: {pattern}"
    return float(match.group(1))


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "emergency-detour-device-issue-review-package" in templates
    config = templates["emergency-detour-device-issue-review-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "road-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    reading_times = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        reading_times.add(round(instance.ground_truth["vms_reading_time_s"], 3))

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(reading_times) >= 10, "Numeric parameters do not vary across seeds"


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    a = sample_instance(config, engine.compute, "medium", seed=33, instance_index=0)
    b = sample_instance(config, engine.compute, "medium", seed=33, instance_index=0)

    assert a.all_params == b.all_params
    assert a.ground_truth == b.ground_truth


@pytest.mark.parametrize("variant", sorted(VARIANT_EXPECTATIONS))
def test_variant_gold_statuses_and_readiness(variant: str) -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    expected = VARIANT_EXPECTATIONS[variant]

    for key in STATUS_KEYS:
        expected_code = expected["flips"].get(key, 0.0)
        assert gold[key] == expected_code, f"{variant}: {key} expected {expected_code}, got {gold[key]}"

    assert gold["readiness_code"] == expected["readiness"]
    assert gold["required_findings_count"] == expected["findings"]
    assert gold["required_information_requests_count"] == expected["requests"]
    assert gold["required_carried_actions_count"] == expected["carried"]


def test_clean_variant_evidence_is_consistent() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("clean")
    gold = instance.ground_truth

    for key in EVIDENCE_KEYS:
        assert key in gold, f"Missing evidence key {key}"

    assert gold["vms_message_margin_chars"] > 0.0
    assert gold["network_headroom_mbps"] > 0.0
    assert gold["rf_link_margin_db"] > 0.0
    assert gold["battery_margin_h"] > 0.0
    assert gold["voltage_drop_margin_percent"] > 0.0


def test_battery_runtime_deficient_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("battery_runtime_deficient")

    assert instance.ground_truth["battery_margin_h"] < 0.0


def test_missing_closure_duration_variant_omits_battery_margin() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_closure_duration")

    assert "battery_runtime_h" in instance.ground_truth
    assert "battery_margin_h" not in instance.ground_truth


def test_build_sources_produces_seven_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in [
        "OPS-SSC01-004",
        "DETOUR-SSC01-004",
        "TMP-SSC01-004",
        "VMS-SSC01-004",
        "CCTV-SSC01-004",
        "RF-SSC01-004",
        "NET-SSC01-004",
        "PWR-SSC01-004",
        "MSG-SSC01-004",
    ]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["DETOUR-SSC01-004", "MSG-SSC01-004", "RF-SSC01-004", "PWR-SSC01-004", "CRIT-SSC01-004"]:
        assert doc_id in register


def test_missing_closure_duration_sources_do_not_print_review_answer() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_closure_duration")
    sources = engine.build_sources(instance.all_params)

    detour = sources["sources/detour-plan.md"].lower()
    criteria = sources["sources/criteria-comments.md"].lower()

    assert "pending traffic operations confirmation" in detour
    assert "kwh x efficiency divided by load kw" in criteria
    assert "missing-data boundary" not in criteria
    assert "insufficient_data" not in criteria
    assert "not_ready_to_issue" not in criteria
    assert "not ready_with_carried_actions" not in criteria
    assert "do not carry" not in criteria


def test_criteria_define_unit_conversions() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    criteria = sources["sources/criteria-comments.md"].lower()

    assert "feet per inch" in criteria
    assert "0.3048" in criteria
    assert "kwh x efficiency divided by load kw" in criteria
    assert "dbm arithmetic" in criteria
    assert "2 x feeder length" in criteria


def test_scenario_copy_forward_sources_bound_other_checks_to_current_packet() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("scenario_copy_forward")
    sources = engine.build_sources(instance.all_params)

    detour = sources["sources/detour-plan.md"]
    criteria = sources["sources/criteria-comments.md"].lower()
    power = sources["sources/power-continuity-schedule.md"]
    communications = sources["sources/communications-topology.md"]

    assert "copied from closure OPS-SSC01-099" in detour
    assert "primary/collateral boundary" not in criteria
    assert "do not cascade" not in criteria
    assert "Critical device load" in power
    assert "Uplink capacity" in communications


def test_sources_print_quantized_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    message = sources["sources/message-library.md"]
    communications = sources["sources/communications-topology.md"]
    power = sources["sources/power-continuity-schedule.md"]

    assert re.search(r"VMS character height \| \d+ in", message)
    assert re.search(r"Network overhead \| \d+ %", communications)
    assert re.search(r"Battery capacity \| \d+\.\d kWh", power)


def _assert_detour_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    detour = sources["sources/detour-plan.md"]
    message = sources["sources/message-library.md"]
    communications = sources["sources/communications-topology.md"]
    power = sources["sources/power-continuity-schedule.md"]

    character_height = _grab(r"VMS character height \| ([\d.]+) in", message)
    speed = _grab(r"Detour approach speed \| ([\d.]+) km/h", detour)
    reading_rate = _grab(r"Reading rate \| ([\d.]+) chars/s", message)
    message_length = _grab(r"Message length \| ([\d.]+) chars", message)

    reading_time = character_height * 40.0 * 0.3048 / (speed / 3.6)
    message_margin = reading_time * reading_rate - message_length
    assert reading_time == pytest.approx(gold["vms_reading_time_s"], rel=0.01)
    assert message_margin == pytest.approx(gold["vms_message_margin_chars"], rel=0.01, abs=0.02)

    cctv_count = int(_grab(r"Active CCTV cameras \| (\d+)", communications))
    cctv_load = _grab(r"CCTV network load per camera \| ([\d.]+) Mbps", communications)
    vms_count = int(_grab(r"Active VMS boards \| (\d+)", communications))
    vms_load = _grab(r"VMS network load per board \| ([\d.]+) Mbps", communications)
    radio_load = _grab(r"Radio telemetry load \| ([\d.]+) Mbps", communications)
    controller_load = _grab(r"Controller network load \| ([\d.]+) Mbps", communications)
    overhead = _grab(r"Network overhead \| ([\d.]+) %", communications)
    uplink = _grab(r"Uplink capacity \| ([\d.]+) Mbps", communications)
    base_load = cctv_count * cctv_load + vms_count * vms_load + radio_load + controller_load
    required_network = base_load * (1 + overhead / 100.0)
    assert required_network == pytest.approx(gold["required_network_mbps"], rel=0.01)
    assert uplink - required_network == pytest.approx(gold["network_headroom_mbps"], rel=0.01, abs=0.02)

    tx_power = _grab(r"RF transmit power \| ([\d.-]+) dBm", communications)
    tx_gain = _grab(r"RF transmit antenna gain \| ([\d.-]+) dB", communications)
    rx_gain = _grab(r"RF receive antenna gain \| ([\d.-]+) dB", communications)
    path_loss = _grab(r"RF path loss \| ([\d.-]+) dB", communications)
    misc_loss = _grab(r"RF miscellaneous loss \| ([\d.-]+) dB", communications)
    fade_margin = _grab(r"RF fade margin \| ([\d.-]+) dB", communications)
    sensitivity = _grab(r"RF receiver sensitivity \| ([\d.-]+) dBm", communications)
    received = tx_power + tx_gain + rx_gain - path_loss - misc_loss - fade_margin
    assert received == pytest.approx(gold["rf_received_power_dbm"], rel=0.01, abs=0.02)
    assert received - sensitivity == pytest.approx(gold["rf_link_margin_db"], rel=0.01, abs=0.02)

    battery_capacity = _grab(r"Battery capacity \| ([\d.]+) kWh", power)
    battery_efficiency = _grab(r"Battery efficiency \| ([\d.]+)", power)
    critical_load = _grab(r"Critical device load \| ([\d.]+) W", power)
    runtime = battery_capacity * battery_efficiency / (critical_load / 1000.0)
    assert runtime == pytest.approx(gold["battery_runtime_h"], rel=0.01)
    if "battery_margin_h" in gold:
        duration = _grab(r"Required closure duration \| ([\d.]+) h", detour)
        assert runtime - duration == pytest.approx(gold["battery_margin_h"], rel=0.01, abs=0.02)
    else:
        assert "pending traffic operations confirmation" in detour

    feeder_length = _grab(r"Feeder length \| ([\d.]+) km", power)
    resistance = _grab(r"Conductor resistance \| ([\d.]+) ohm/km", power)
    voltage = _grab(r"Feeder voltage \| ([\d.]+) V", power)
    power_factor = _grab(r"Power factor \| ([\d.]+)", power)
    allowable_drop = _grab(r"Allowable voltage drop \| ([\d.]+) %", power)
    current = critical_load / (voltage * power_factor)
    voltage_drop = 2.0 * feeder_length * resistance * current / voltage * 100.0
    assert voltage_drop == pytest.approx(gold["feeder_voltage_drop_percent"], rel=0.01, abs=0.02)
    assert allowable_drop - voltage_drop == pytest.approx(gold["voltage_drop_margin_percent"], rel=0.01, abs=0.02)


@pytest.mark.parametrize("variant", ["clean", "battery_runtime_deficient"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_detour_evidence_recomputable_from_sources(variant)


def test_missing_closure_duration_packet_recomputes_available_evidence() -> None:
    _assert_detour_evidence_recomputable_from_sources("missing_closure_duration")


def test_scaffolded_instance_layout(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")

    for rel in SOURCE_FILES:
        assert (instance_dir / "environment" / rel).exists(), f"Missing {rel}"

    dockerfile = (instance_dir / "environment" / "Dockerfile").read_text(encoding="utf-8")
    for rel in SOURCE_FILES:
        assert f"COPY {rel} /workspace/{rel}" in dockerfile

    instance_json = json.loads((instance_dir / "tests" / "instance.json").read_text(encoding="utf-8"))
    assert instance_json["all_params"]["packet_variant"] == "clean"
    assert "rlr_01_status" in instance_json["ground_truth"]

    verify_source = (instance_dir / "tests" / "verify.py").read_text(encoding="utf-8")
    assert "instance.json" in verify_source

    system_prompt = (instance_dir / "environment" / "system_prompt.md").read_text(encoding="utf-8")
    assert "review" in system_prompt.lower()
    assert "single RLR item" in system_prompt
    assert "missing required closure duration" not in system_prompt

    assert not list(instance_dir.glob("environment/*_calc.py")), "no-tool template must not ship a calc script"

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
    assert "single RLR item" in instruction
    assert "Do not rename computed_evidence keys" in instruction
    assert "battery_margin_h" in instruction
    assert "rf_link_margin_db" in instruction
    assert "missing required closure duration" not in instruction
    assert "Do not cascade" not in instruction
    for item in [f"RLR-0{i}" for i in range(1, 10)]:
        assert item in instruction


@pytest.mark.parametrize("variant", sorted(VARIANT_EXPECTATIONS))
def test_golden_pass_scores_one(tmp_path: Path, variant: str) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, variant)
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    reward, _details = _run_verifier(instance_dir, golden_pass, tmp_path)
    assert reward == 1.0


@pytest.mark.parametrize("variant", ["clean", "open_critical_comment"])
def test_golden_fail_fluent_unsafe_memo_scores_low(tmp_path: Path, variant: str) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, variant)
    golden_fail = instance_dir / "tests" / "fixtures" / "golden_fail.md"

    reward, _details = _run_verifier(instance_dir, golden_fail, tmp_path)
    assert reward <= 0.5


def test_verifier_localizes_flipped_status(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["review_matrix"]["RLR-03"]["status"] = "fail"
    mutated = tmp_path / "mutated-status.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["matrix"]["items"]["RLR-03"] < 1.0


def test_verifier_gates_status_credit_on_evidence(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["computed_evidence"] = {}
    mutated = tmp_path / "mutated-evidence.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward <= 0.6
    assert details["gates"]["readiness"]["score"] == 0.0


def test_verifier_zeroes_readiness_on_unsupported_ready_decision(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "battery_runtime_deficient")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
