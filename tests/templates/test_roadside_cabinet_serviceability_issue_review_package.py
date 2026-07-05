# ABOUTME: Tests the SSC-01 roadside cabinet serviceability issue review template.
# ABOUTME: Covers source-pack variants, recomputed evidence, and stage-gated review grading.

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
    / "roadside_cabinet_serviceability_issue_review_package"
)

FORMULA_BASELINE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "electrical"
    / "roadside_cabinet_flood_heat_backup_energy_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "cabinet_freeboard_m",
    "flood_freeboard_margin_m",
    "thermal_derated_capacity_w",
    "thermal_margin_w",
    "thermal_utilization",
    "battery_runtime_h",
    "battery_margin_h",
    "bess_power_margin_kw",
    "bess_energy_margin_kwh",
    "feeder_voltage_drop_percent",
    "voltage_drop_margin_percent",
    "road_lighting_aeci_kwh_m2_y",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_derating_rate": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_enclosure_derating_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "cabinet_event_mismatch": {
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
    "thermal_capacity_deficient": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/cabinet-setout-elevation.md",
    "sources/flood-inundation-table.md",
    "sources/enclosure-derating-note.md",
    "sources/critical-load-backup-schedule.md",
    "sources/feeder-access-note.md",
    "sources/owner-serviceability-criterion.md",
    "sources/criteria-comments.md",
]


def _load() -> tuple:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    return config, template_dir, engine


def _instance_for_variant(variant: str, max_seeds: int = 1600):
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

    assert "roadside-cabinet-serviceability-issue-review-package" in templates
    config = templates["roadside-cabinet-serviceability-issue-review-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "road-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_preserves_existing_formula_baseline() -> None:
    assert (FORMULA_BASELINE_DIR / "engine.py").exists()
    assert (FORMULA_BASELINE_DIR / "params.toml").exists()
    assert (FORMULA_BASELINE_DIR / "instruction.md").exists()


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    runtimes = set()
    for seed in range(80):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        runtimes.add(round(instance.ground_truth["battery_runtime_h"], 1))

    assert len(variants) >= 4, "Variant distribution collapsed"
    assert len(runtimes) >= 10, "Numeric parameters do not vary across seeds"


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    a = sample_instance(config, engine.compute, "medium", seed=41, instance_index=0)
    b = sample_instance(config, engine.compute, "medium", seed=41, instance_index=0)

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

    assert gold["flood_freeboard_margin_m"] > 0.0
    assert gold["thermal_margin_w"] > 0.0
    assert 0.0 < gold["thermal_utilization"] < 1.0
    assert gold["battery_margin_h"] > 0.0
    assert gold["bess_power_margin_kw"] > 0.0
    assert gold["bess_energy_margin_kwh"] > 0.0
    assert gold["voltage_drop_margin_percent"] > 0.0
    assert gold["road_lighting_aeci_kwh_m2_y"] > 0.0


def test_thermal_capacity_deficient_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("thermal_capacity_deficient")

    assert instance.ground_truth["thermal_margin_w"] < 0.0
    assert instance.ground_truth["thermal_utilization"] > 1.0
    assert instance.ground_truth["battery_margin_h"] > 0.0


def test_missing_derating_rate_variant_omits_thermal_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_derating_rate")

    assert "cabinet_freeboard_m" in instance.ground_truth
    assert "thermal_derated_capacity_w" not in instance.ground_truth
    assert "thermal_margin_w" not in instance.ground_truth
    assert "thermal_utilization" not in instance.ground_truth


def test_build_sources_produces_eight_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in [
        "CAB-SSC01-007",
        "HGL-SSC01-007",
        "HEAT-SSC01-007",
        "LOAD-SSC01-007",
        "BATT-SSC01-007",
        "FEED-SSC01-007",
        "OPS-SSC01-007",
        "MEMO-SSC01-007",
        "CRIT-SSC01-007",
    ]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"


def test_missing_derating_sources_do_not_print_review_answer() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_derating_rate")
    sources = engine.build_sources(instance.all_params)

    derating = sources["sources/enclosure-derating-note.md"].lower()
    criteria = sources["sources/criteria-comments.md"].lower()

    assert "pending heat derating rate confirmation" in derating
    assert "thermal utilization is a ratio, not a percent" in criteria
    assert "missing-data boundary" not in criteria
    assert "insufficient_data" not in criteria
    assert "not_ready_to_issue" not in criteria
    assert "not ready_with_carried_actions" not in criteria
    assert "do not carry" not in criteria


def test_prompt_is_variant_blind_for_missing_derating_rate() -> None:
    instruction = (TEMPLATE_DIR / "instruction.md").read_text(encoding="utf-8").lower()
    system_prompt = (TEMPLATE_DIR / "system_prompt.md").read_text(encoding="utf-8").lower()

    for text in (instruction, system_prompt):
        assert "missing derating rate" not in text
        assert "belongs under rlr-04 only" not in text
        assert "do not fail rlr-03 for this missing value" not in text
        assert "criteria_memo must mention both memo-ssc01-007 and crit-ssc01-007" not in text
        assert "serviceability_scenario must mention ops-ssc01-007" not in text
        assert "rlr-08 passes when the readiness decision reconciles" in text
        assert "thermal_utilization is a ratio, not a percent" not in text
        assert "118.6" not in text


def test_criteria_define_source_owned_methods() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    criteria = sources["sources/criteria-comments.md"].lower()

    assert "greater of hgl and inundation" in criteria
    assert "pad level minus controlling water level" in criteria
    assert "reference capacity" in criteria
    assert "event-temperature derating factor" in criteria
    assert "thermal utilization is a ratio, not a percent" in criteria
    assert "kwh times efficiency divided by load kw" in criteria
    assert "2 x length x resistance x current" in criteria
    assert "annual lighting energy divided by lit area" in criteria


def test_scenario_copy_forward_sources_bound_other_checks_to_current_packet() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("scenario_copy_forward")
    sources = engine.build_sources(instance.all_params)

    cabinet = sources["sources/cabinet-setout-elevation.md"]
    criteria = sources["sources/criteria-comments.md"].lower()
    backup = sources["sources/critical-load-backup-schedule.md"]
    feeder = sources["sources/feeder-access-note.md"]

    assert "copied from cabinet serviceability case CAB-SSC01-099" in cabinet
    assert "primary/collateral boundary" not in criteria
    assert "do not cascade" not in criteria
    assert "belongs under rlr" not in criteria
    assert "Critical load" in backup
    assert "Feeder length" in feeder


def test_sources_print_quantized_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    cabinet = sources["sources/cabinet-setout-elevation.md"]
    derating = sources["sources/enclosure-derating-note.md"]
    feeder = sources["sources/feeder-access-note.md"]

    assert re.search(r"Cabinet pad level \| \d+\.\d{2} m", cabinet)
    assert re.search(r"Event temperature \| \d+\.\d C", derating)
    assert re.search(r"Derating rate \| \d+\.\d{2} % per C", derating)
    assert re.search(r"Feeder length \| \d+\.\d{2} km", feeder)


def _assert_cabinet_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    cabinet = sources["sources/cabinet-setout-elevation.md"]
    flood = sources["sources/flood-inundation-table.md"]
    derating = sources["sources/enclosure-derating-note.md"]
    backup = sources["sources/critical-load-backup-schedule.md"]
    feeder = sources["sources/feeder-access-note.md"]
    owner = sources["sources/owner-serviceability-criterion.md"]

    pad = _grab(r"Cabinet pad level \| ([\d.]+) m", cabinet)
    hgl = _grab(r"HGL level \| ([\d.]+) m", flood)
    inundation = _grab(r"Inundation level \| ([\d.]+) m", flood)
    minimum_freeboard = _grab(r"Minimum cabinet freeboard \| ([\d.]+) m", owner)
    controlling = max(hgl, inundation)
    freeboard = pad - controlling
    assert freeboard == pytest.approx(gold["cabinet_freeboard_m"], rel=0.01, abs=0.02)
    assert freeboard - minimum_freeboard == pytest.approx(gold["flood_freeboard_margin_m"], rel=0.01, abs=0.02)

    critical_load = _grab(r"Critical load \| ([\d.]+) W", backup)
    derating_match = re.search(r"Derating rate \| ([\d.]+) % per C", derating)
    if "thermal_margin_w" in gold:
        assert derating_match
        capacity = _grab(r"Reference enclosure capacity \| ([\d.]+) W", derating)
        ref_temp = _grab(r"Reference temperature \| ([\d.]+) C", derating)
        event_temp = _grab(r"Event temperature \| ([\d.]+) C", derating)
        derate_pct = float(derating_match.group(1))
        derated_capacity = capacity * (1.0 - derate_pct / 100.0 * (event_temp - ref_temp))
        assert derated_capacity == pytest.approx(gold["thermal_derated_capacity_w"], rel=0.01, abs=2.0)
        assert derated_capacity - critical_load == pytest.approx(gold["thermal_margin_w"], rel=0.01, abs=2.0)
        assert critical_load / derated_capacity == pytest.approx(gold["thermal_utilization"], rel=0.01, abs=0.01)
    else:
        assert not derating_match
        assert "pending heat derating rate confirmation" in derating

    battery_capacity = _grab(r"Battery capacity \| ([\d.]+) kWh", backup)
    battery_efficiency = _grab(r"Battery efficiency \| ([\d.]+)", backup)
    required_backup = _grab(r"Required backup duration \| ([\d.]+) h", owner)
    inverter_capacity = _grab(r"BESS inverter capacity \| ([\d.]+) kW", backup)
    runtime = battery_capacity * battery_efficiency / (critical_load / 1000.0)
    assert runtime == pytest.approx(gold["battery_runtime_h"], rel=0.01, abs=0.05)
    assert runtime - required_backup == pytest.approx(gold["battery_margin_h"], rel=0.01, abs=0.05)
    assert inverter_capacity - critical_load / 1000.0 == pytest.approx(gold["bess_power_margin_kw"], rel=0.01, abs=0.05)
    assert battery_capacity * battery_efficiency - critical_load / 1000.0 * required_backup == pytest.approx(
        gold["bess_energy_margin_kwh"], rel=0.01, abs=0.05
    )

    length = _grab(r"Feeder length \| ([\d.]+) km", feeder)
    resistance = _grab(r"Conductor resistance \| ([\d.]+) ohm/km", feeder)
    voltage = _grab(r"Feeder voltage \| ([\d.]+) V", feeder)
    power_factor = _grab(r"Power factor \| ([\d.]+)", feeder)
    allowable_drop = _grab(r"Allowable voltage drop \| ([\d.]+) %", owner)
    current = critical_load / (voltage * power_factor)
    voltage_drop = 2.0 * length * resistance * current / voltage * 100.0
    assert voltage_drop == pytest.approx(gold["feeder_voltage_drop_percent"], rel=0.01, abs=0.02)
    assert allowable_drop - voltage_drop == pytest.approx(gold["voltage_drop_margin_percent"], rel=0.01, abs=0.02)

    lighting_power = _grab(r"Road lighting power \| ([\d.]+) W", feeder)
    annual_hours = _grab(r"Annual operating hours \| ([\d.]+) h/y", feeder)
    lit_area = _grab(r"Lit area \| ([\d.]+) m2", feeder)
    aeci = lighting_power * annual_hours / 1000.0 / lit_area
    assert aeci == pytest.approx(gold["road_lighting_aeci_kwh_m2_y"], rel=0.01, abs=0.02)


@pytest.mark.parametrize("variant", ["clean", "thermal_capacity_deficient"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_cabinet_evidence_recomputable_from_sources(variant)


def test_missing_derating_rate_packet_recomputes_available_evidence() -> None:
    _assert_cabinet_evidence_recomputable_from_sources("missing_derating_rate")


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
    assert "missing derating rate" not in system_prompt
    assert "118.6" not in system_prompt
    assert "belongs under RLR-04 only" not in system_prompt

    assert not list(instance_dir.glob("environment/*_calc.py")), "no-tool template must not ship a calc script"

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
    assert "single RLR item" in instruction
    assert "Do not rename computed_evidence keys" in instruction
    assert "thermal_margin_w" in instruction
    assert "road_lighting_aeci_kwh_m2_y" in instruction
    assert "missing derating rate" not in instruction
    assert "118.6" not in instruction
    assert "belongs under RLR-04 only" not in instruction
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


def test_verifier_accepts_explicit_nonclaim_boundary_wording(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "thermal_capacity_deficient")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["claim_boundary_statement"] = (
        "This review covers a task-owned synthetic source packet only. It does not constitute authority "
        "approval, accepted project evidence, full standards compliance verification, source-pack hardening, "
        "executable-verifier readiness, or benchmark readiness."
    )
    mutated = tmp_path / "mutated-nonclaim-boundary.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward == 1.0
    assert details["gates"]["identity_claims"]["checks"]["claim_boundary"] == 1.0

    payload["claim_boundary_statement"] = (
        "This review covers a task-owned synthetic source packet only and does not constitute authority approval."
    )
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["identity_claims"]["checks"]["claim_boundary"] == 0.0


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
    instance_dir, _gold = _scaffold_variant(tmp_path, "thermal_capacity_deficient")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
