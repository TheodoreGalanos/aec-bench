# ABOUTME: Tests the SSC-06 review-first pump duty, NPSH, motor, and feeder package.
# ABOUTME: Covers variant gold states, generated source packs, closure, and stage-gated verifier behavior.

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
    / "mechanical"
    / "pump_station_duty_npsh_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "total_dynamic_head_m",
    "pump_head_margin_m",
    "npsh_available_m",
    "npsh_margin_m",
    "motor_input_kw",
    "motor_margin_kw",
    "feeder_voltage_drop_percent",
    "voltage_drop_margin_percent",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_wetwell_min_level": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_pump_curve_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "impeller_diameter_mismatch": {
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
    "npsh_margin_deficient": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/wet-well-suction-geometry.md",
    "sources/rising-main-schedule.md",
    "sources/pump-curve-datasheet.md",
    "sources/motor-feeder-schedule.md",
    "sources/duty-operating-case.md",
    "sources/criteria-comments.md",
]


def _load() -> tuple:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    return config, template_dir, engine


def _instance_for_variant(variant: str, max_seeds: int = 500):
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


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "pump-station-duty-npsh-issue-review-package" in templates
    config = templates["pump-station-duty-npsh-issue-review-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "equipment-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    heads = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        heads.add(instance.ground_truth["total_dynamic_head_m"])

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(heads) >= 10, "Numeric parameters do not vary across seeds (min==max regression)"


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    a = sample_instance(config, engine.compute, "medium", seed=11, instance_index=0)
    b = sample_instance(config, engine.compute, "medium", seed=11, instance_index=0)

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

    assert gold["pump_head_margin_m"] > 0.0
    assert gold["npsh_margin_m"] >= float(instance.all_params["minimum_npsh_margin_m"])
    assert gold["motor_margin_kw"] > 0.0
    assert gold["voltage_drop_margin_percent"] > 0.0


def test_npsh_margin_deficient_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("npsh_margin_deficient")
    gold = instance.ground_truth

    assert gold["npsh_margin_m"] < float(instance.all_params["minimum_npsh_margin_m"])


def test_missing_wetwell_level_variant_omits_npsh_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_wetwell_min_level")

    assert "npsh_available_m" not in instance.ground_truth
    assert "npsh_margin_m" not in instance.ground_truth


def test_build_sources_produces_seven_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in ["WW-06", "PMP-06", "RM-06", "MOT-06", "FDR-06", "DUTY-06"]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["WW-06-GEO-01", "RM-06-SCH-01", "PMP-06-CURVE-01", "CRIT-SSC06-001"]:
        assert doc_id in register


def test_missing_wetwell_level_sources_mark_pending_minimum_level() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_wetwell_min_level")
    sources = engine.build_sources(instance.all_params)

    wet_well = sources["sources/wet-well-suction-geometry.md"]
    assert "pending" in wet_well.lower()
    assert "minimum wet-well operating level" in wet_well

    clean_params = dict(instance.all_params)
    clean_params["packet_variant"] = "clean"
    clean_wet_well = engine.build_sources(clean_params)["sources/wet-well-suction-geometry.md"]
    assert clean_wet_well != wet_well


def test_stale_pump_curve_sources_have_revision_mismatch() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("stale_pump_curve_revision")
    sources = engine.build_sources(instance.all_params)

    register = sources["sources/document-register.md"]
    pump_curve = sources["sources/pump-curve-datasheet.md"]

    assert "Rev C" in register
    assert "Rev B" in pump_curve


def test_sources_print_exact_engine_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)
    main = sources["sources/rising-main-schedule.md"]

    assert re.search(r"Hazen-Williams C[^|]*\| \d+\.0", main)


def _grab(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    assert match, f"Pattern not found: {pattern}"
    return float(match.group(1))


def _assert_pump_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    wet_well = sources["sources/wet-well-suction-geometry.md"]
    main = sources["sources/rising-main-schedule.md"]
    pump = sources["sources/pump-curve-datasheet.md"]
    motor = sources["sources/motor-feeder-schedule.md"]
    duty = sources["sources/duty-operating-case.md"]
    criteria = sources["sources/criteria-comments.md"]

    flow_l_s = _grab(r"Design flow[^|]*\| ([\d.]+) L/s", duty)
    flow = flow_l_s / 1000.0
    static_lift = _grab(r"Static lift[^|]*\| ([\d.]+) m", duty)
    length = _grab(r"Rising main length[^|]*\| ([\d.]+) m", main)
    diameter = _grab(r"Internal diameter[^|]*\| ([\d.]+) mm", main) / 1000.0
    c_factor = _grab(r"Hazen-Williams C[^|]*\| ([\d.]+)", main)
    k_minor = _grab(r"Aggregate minor-loss coefficient[^|]*\| ([\d.]+)", main)

    headloss = 10.67 * length * flow**1.852 / (c_factor**1.852 * diameter**4.87)
    velocity = flow / (math.pi * diameter**2 / 4.0)
    minor = k_minor * velocity**2 / (2.0 * 9.81)
    total_head = static_lift + headloss + minor
    pump_head = _grab(r"Pump curve head at design duty[^|]*\| ([\d.]+) m", pump)

    assert total_head == pytest.approx(gold["total_dynamic_head_m"], rel=0.01)
    assert pump_head - total_head == pytest.approx(gold["pump_head_margin_m"], rel=0.01, abs=0.02)

    density = _grab(r"Fluid density[^|]*\| ([\d.]+) kg/m3", wet_well)
    pump_eff = _grab(r"Pump efficiency[^|]*\| ([\d.]+) %", pump) / 100.0
    motor_eff = _grab(r"Motor efficiency[^|]*\| ([\d.]+) %", motor) / 100.0
    service_factor = _grab(r"Motor service factor[^|]*\| ([\d.]+)", motor)
    selected_motor = _grab(r"Selected motor size[^|]*\| ([\d.]+) kW", motor)

    hydraulic_kw = density * 9.81 * flow * total_head / 1000.0
    shaft_kw = hydraulic_kw / pump_eff
    motor_input = shaft_kw / motor_eff
    motor_margin = selected_motor - shaft_kw * service_factor

    assert motor_input == pytest.approx(gold["motor_input_kw"], rel=0.01)
    assert motor_margin == pytest.approx(gold["motor_margin_kw"], rel=0.01, abs=0.02)

    if "npsh_available_m" in gold:
        atmosphere = _grab(r"Atmospheric pressure[^|]*\| ([\d.]+) kPa", wet_well)
        vapor = _grab(r"Vapor pressure[^|]*\| ([\d.]+) kPa", wet_well)
        minimum_level = _grab(r"Minimum wet-well operating level[^|]*\| ([\d.]+) m", wet_well)
        suction_loss = _grab(r"Suction-side loss[^|]*\| ([\d.]+) m", wet_well)
        npsh_required = _grab(r"NPSHr at design duty[^|]*\| ([\d.]+) m", pump)
        npsh_available = (atmosphere - vapor) * 1000.0 / (density * 9.81) + minimum_level - suction_loss
        assert npsh_available == pytest.approx(gold["npsh_available_m"], rel=0.01, abs=0.02)
        assert npsh_available - npsh_required == pytest.approx(gold["npsh_margin_m"], rel=0.01, abs=0.02)
    else:
        assert "pending survey of stop/start setpoints" in wet_well

    voltage = _grab(r"Feeder voltage[^|]*\| ([\d.]+) V", motor)
    feeder_length = _grab(r"Feeder length[^|]*\| ([\d.]+) km", motor)
    resistance = _grab(r"Resistance[^|]*\| ([\d.]+) ohm/km", motor)
    reactance = _grab(r"Reactance[^|]*\| ([\d.]+) ohm/km", motor)
    power_factor = _grab(r"Motor power factor[^|]*\| ([\d.]+)", motor)
    max_drop = _grab(r"Maximum feeder voltage drop[^|]*\| ([\d.]+) %", criteria)

    kvar = motor_input * math.tan(math.acos(power_factor))
    kva = math.hypot(motor_input, kvar)
    current = kva * 1000.0 / (math.sqrt(3.0) * voltage)
    reactive_factor = kvar / kva
    drop_v = math.sqrt(3.0) * current * feeder_length * (resistance * power_factor + reactance * reactive_factor)
    drop_pct = drop_v / voltage * 100.0
    assert drop_pct == pytest.approx(gold["feeder_voltage_drop_percent"], rel=0.01, abs=0.02)
    assert max_drop - drop_pct == pytest.approx(gold["voltage_drop_margin_percent"], rel=0.01, abs=0.02)


@pytest.mark.parametrize("variant", ["clean", "npsh_margin_deficient"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_pump_evidence_recomputable_from_sources(variant)


def test_missing_wetwell_level_packet_recomputes_available_evidence() -> None:
    _assert_pump_evidence_recomputable_from_sources("missing_wetwell_min_level")


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
    assert "Do not rename computed_evidence keys" in system_prompt

    assert not list(instance_dir.glob("environment/*_calc.py")), "no-tool template must not ship a calc script"

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
    assert "Do not rename computed_evidence keys" in instruction
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
    instance_dir, _gold = _scaffold_variant(tmp_path, "npsh_margin_deficient")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
