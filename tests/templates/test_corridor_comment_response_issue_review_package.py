# ABOUTME: Tests the SSC-01 review-first corridor comment-response issue review template.
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
    / "civil"
    / "corridor_comment_response_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "changed_chainage_delta_m",
    "hgl_clearance_mm",
    "hgl_clearance_margin_mm",
    "ped_clearance_required_s",
    "ped_clearance_margin_s",
    "vms_reading_time_s",
    "vms_message_margin_chars",
    "feeder_voltage_drop_percent",
    "voltage_drop_margin_percent",
    "comment_closeout_percent",
    "impacted_calculation_count",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_revised_chainage": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_change_register_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "chainage_identity_mismatch": {
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
    "unsupported_downstream_repair": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/comment-register.md",
    "sources/marked-up-plan.md",
    "sources/drainage-recalc.md",
    "sources/signal-pedestrian-recalc.md",
    "sources/vms-operations-note.md",
    "sources/electrical-feeder-check.md",
    "sources/criteria-comments.md",
]


def _load() -> tuple:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    return config, template_dir, engine


def _instance_for_variant(variant: str, max_seeds: int = 800):
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

    assert "corridor-comment-response-issue-review-package" in templates
    config = templates["corridor-comment-response-issue-review-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "road-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    voltage_margins = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        voltage_margins.add(instance.ground_truth["voltage_drop_margin_percent"])

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(voltage_margins) >= 10, "Numeric parameters do not vary across seeds"


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    a = sample_instance(config, engine.compute, "medium", seed=22, instance_index=0)
    b = sample_instance(config, engine.compute, "medium", seed=22, instance_index=0)

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

    assert gold["hgl_clearance_margin_mm"] > 0.0
    assert gold["ped_clearance_margin_s"] > 0.0
    assert gold["vms_message_margin_chars"] > 0.0
    assert gold["voltage_drop_margin_percent"] > 0.0
    assert gold["comment_closeout_percent"] == 100.0


def test_unsupported_downstream_repair_variant_fails_voltage_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("unsupported_downstream_repair")
    gold = instance.ground_truth

    assert gold["voltage_drop_margin_percent"] < 0.0


def test_missing_revised_chainage_variant_omits_delta_evidence() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_revised_chainage")
    sources = engine.build_sources(instance.all_params)

    assert "changed_chainage_delta_m" not in instance.ground_truth
    assert "pending survey/control confirmation" in sources["sources/marked-up-plan.md"].lower()


def test_build_sources_produces_eight_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in ["RD-SSC01-001", "C-008", "DRN-08", "SG-08", "VMS-08", "FEED-08", "CASE-08", "AHD"]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"
    assert re.search(r"CH \d\+\d{3}\.\d", joined), "Corridor chainage token missing"

    register = sources["sources/document-register.md"]
    for doc_id in ["CMT-SSC01-008", "MARKUP-SSC01-008", "DRAIN-SSC01-008", "SIG-SSC01-008"]:
        assert doc_id in register


def test_stale_change_register_sources_have_revision_mismatch() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("stale_change_register_revision")
    sources = engine.build_sources(instance.all_params)

    register = sources["sources/document-register.md"]
    comment_register = sources["sources/comment-register.md"]

    assert "CMT-SSC01-008 | Comment register and change ledger | Rev C" in register
    assert "# Comment Register - CMT-SSC01-008 (Rev B)" in comment_register


def test_scenario_copy_forward_sources_keep_vms_legibility_numerically_clean() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("scenario_copy_forward")
    sources = engine.build_sources(instance.all_params)
    vms = sources["sources/vms-operations-note.md"]

    assert "copied from corridor RD-SSC01-099 closure case" in vms

    copied_speed = _grab(r"Assessment speed \| ([\d.]+) km/h", vms)
    char_height = _grab(r"VMS character height \| ([\d.]+) in", vms)
    reading_rate = _grab(r"Reading rate \| ([\d.]+) chars/s", vms)
    message_length = _grab(r"Revised message length \| ([\d.]+) chars", vms)
    copied_reading_time = char_height * 40.0 * 0.3048 / (copied_speed / 3.6)

    assert copied_reading_time * reading_rate - message_length > 0.0


def test_scenario_copy_forward_sources_bound_other_checks_to_current_packet() -> None:
    """Scenario-copy variants should not leave unrelated checks plausibly under-evidenced."""
    _config, _template_dir, engine, instance = _instance_for_variant("scenario_copy_forward")
    sources = engine.build_sources(instance.all_params)

    comments = sources["sources/comment-register.md"]
    signal = sources["sources/signal-pedestrian-recalc.md"]
    vms = sources["sources/vms-operations-note.md"]
    feeder = sources["sources/electrical-feeder-check.md"]

    assert "Closure evidence" in comments
    for doc_id in ["DRAIN-SSC01-008", "SIG-SSC01-008", "VMS-SSC01-008", "FEED-SSC01-008"]:
        assert doc_id in comments

    assert "revised C-008 chainage" in signal
    assert "revised C-008 chainage" in vms
    assert "revised C-008 chainage" in feeder
    assert "Load breakdown" in feeder
    assert "DRN-08 telemetry" in feeder
    assert "SG-08 interface" in feeder
    assert "VMS-08" in feeder
    assert "copied from corridor RD-SSC01-099 closure case" in vms


def test_criteria_source_does_not_print_copied_scenario_review_answer() -> None:
    """Copied-scenario sources can show the defect without printing the gold localization."""
    _config, _template_dir, engine, instance = _instance_for_variant("scenario_copy_forward")
    criteria = engine.build_sources(instance.all_params)["sources/criteria-comments.md"].lower()

    assert "copied scenario" in criteria
    assert "reviewer self-consistency" in criteria
    assert "primary/collateral boundary" not in criteria
    assert "do not fail rlr-06" not in criteria
    assert "belongs under rlr-05" not in criteria


def test_missing_chainage_sources_do_not_print_review_answer() -> None:
    """Missing chainage sources expose the gap without prescribing the review status."""
    _config, _template_dir, engine, instance = _instance_for_variant("missing_revised_chainage")
    sources = engine.build_sources(instance.all_params)
    criteria = sources["sources/criteria-comments.md"].lower()
    markup = sources["sources/marked-up-plan.md"].lower()

    assert "pending survey/control confirmation" in markup
    assert "do not include missing or unrecomputable evidence keys" in criteria
    assert "missing-data boundary" not in criteria
    assert "insufficient_data" not in criteria
    assert "missing revised c-008 chainage" not in criteria
    assert "do not reclassify" not in criteria


def test_sources_print_quantized_electrical_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)
    feeder = sources["sources/electrical-feeder-check.md"]

    assert re.search(r"Conductor resistance \| 0\.\d{2} ohm/km", feeder)
    assert re.search(r"Power factor \| 0\.\d{2}", feeder)


def _assert_corridor_evidence_recomputable_from_sources(variant: str) -> None:
    """Recompute the gold evidence available in a rendered source packet."""
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    markup = sources["sources/marked-up-plan.md"]
    drainage = sources["sources/drainage-recalc.md"]
    signal = sources["sources/signal-pedestrian-recalc.md"]
    vms = sources["sources/vms-operations-note.md"]
    feeder = sources["sources/electrical-feeder-check.md"]
    comments = sources["sources/comment-register.md"]

    if variant == "scenario_copy_forward":
        approach_speed = _grab(r"CASE-08 approach speed \| ([\d.]+) km/h", markup)
    else:
        approach_speed = _grab(r"Approach speed \| ([\d.]+) km/h", vms)
    road_level = _grab(r"Revised road level \| ([\d.]+) m AHD", drainage)
    hgl = _grab(r"Revised hydraulic grade line \| ([\d.]+) m AHD", drainage)
    min_clearance = _grab(r"Minimum HGL clearance \| ([\d.]+) mm", drainage)
    ped_startup = _grab(r"Pedestrian startup allowance \| ([\d.]+) s", signal)
    crossing_width = _grab(r"Revised crossing width \| ([\d.]+) m", signal)
    walk_speed = _grab(r"Pedestrian walk speed \| ([\d.]+) m/s", signal)
    available_clearance = _grab(r"Available pedestrian clearance \| ([\d.]+) s", signal)
    char_height = _grab(r"VMS character height \| ([\d.]+) in", vms)
    reading_rate = _grab(r"Reading rate \| ([\d.]+) chars/s", vms)
    message_length = _grab(r"Revised message length \| ([\d.]+) chars", vms)
    device_load = _grab(r"Revised connected device load \| ([\d.]+) W", feeder)
    feeder_length = _grab(r"Feeder length \| ([\d.]+) km", feeder)
    conductor_resistance = _grab(r"Conductor resistance \| ([\d.]+) ohm/km", feeder)
    voltage = _grab(r"Feeder voltage \| ([\d.]+) V", feeder)
    power_factor = _grab(r"Power factor \| ([\d.]+)", feeder)
    allowable_voltage_drop = _grab(r"Allowable voltage drop \| ([\d.]+) %", feeder)
    review_total = _grab(r"Review comments total \| ([\d.]+)", comments)
    review_closed = _grab(r"Review comments closed \| ([\d.]+)", comments)
    impacted_count = _grab(r"Impacted calculation count \| ([\d.]+)", comments)

    hgl_clearance = (road_level - hgl) * 1000.0
    ped_required = ped_startup + crossing_width / walk_speed
    vms_reading_time = char_height * 40.0 * 0.3048 / (approach_speed / 3.6)
    vms_margin = vms_reading_time * reading_rate - message_length
    current = device_load / (voltage * power_factor)
    voltage_drop = 2.0 * feeder_length * conductor_resistance * current / voltage * 100.0
    voltage_margin = allowable_voltage_drop - voltage_drop
    closeout = review_closed / review_total * 100.0

    assert hgl_clearance == pytest.approx(gold["hgl_clearance_mm"], rel=0.01, abs=0.6)
    assert hgl_clearance - min_clearance == pytest.approx(gold["hgl_clearance_margin_mm"], rel=0.01, abs=0.6)
    assert ped_required == pytest.approx(gold["ped_clearance_required_s"], rel=0.01, abs=0.03)
    assert available_clearance - ped_required == pytest.approx(gold["ped_clearance_margin_s"], rel=0.01, abs=0.03)
    assert vms_reading_time == pytest.approx(gold["vms_reading_time_s"], rel=0.01, abs=0.03)
    assert vms_margin == pytest.approx(gold["vms_message_margin_chars"], rel=0.01, abs=0.05)
    assert voltage_drop == pytest.approx(gold["feeder_voltage_drop_percent"], rel=0.01, abs=0.03)
    assert voltage_margin == pytest.approx(gold["voltage_drop_margin_percent"], rel=0.01, abs=0.03)
    assert closeout == pytest.approx(gold["comment_closeout_percent"], rel=0.01, abs=0.03)
    assert impacted_count == pytest.approx(gold["impacted_calculation_count"], rel=0.01, abs=0.01)

    if "changed_chainage_delta_m" in gold:
        original_chainage = _grab(r"Original comment chainage \| CH \d\+([\d.]+)", markup)
        revised_chainage = _grab(r"Revised comment chainage \| CH \d\+([\d.]+)", markup)
        assert revised_chainage - original_chainage == pytest.approx(
            gold["changed_chainage_delta_m"], rel=0.01, abs=0.03
        )
    else:
        assert "pending survey/control confirmation" in markup.lower()


@pytest.mark.parametrize("variant", ["clean", "scenario_copy_forward", "unsupported_downstream_repair"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    """Clean and genuine-failure packets must be solvable from rendered sources alone."""
    _assert_corridor_evidence_recomputable_from_sources(variant)


def test_missing_revised_chainage_packet_recomputes_available_evidence() -> None:
    """Missing-evidence packets must still expose all non-missing recomputable evidence."""
    _assert_corridor_evidence_recomputable_from_sources("missing_revised_chainage")


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
    assert "do not include them with `null`, `0`, or placeholder values" in system_prompt
    assert "single RLR item" in system_prompt
    assert "missing revised chainage" not in system_prompt
    assert "MARKUP-SSC01-008" not in system_prompt

    assert not list(instance_dir.glob("environment/*_calc.py")), "no-tool template must not ship a calc script"

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
    assert "most specific review item" in instruction
    assert "RLR-08 is reviewer self-consistency" in instruction
    assert "Do not rename computed_evidence keys" in instruction
    assert (
        "Do not include missing or unrecomputable evidence keys with `null`, `0`, or placeholder values" in instruction
    )
    assert "single RLR item" in instruction
    assert "vms_reading_time_s" in instruction
    assert "voltage_drop_margin_percent" in instruction
    assert "Primary/collateral boundary rules" not in instruction
    assert "Do not cascade a copied-scenario finding" not in instruction
    assert "scenario-copy variants" not in instruction
    assert "missing revised chainage" not in instruction.lower()
    assert "MARKUP-SSC01-008" not in instruction
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


def test_verifier_penalizes_unavailable_computed_evidence_keys(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "missing_revised_chainage")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    assert "changed_chainage_delta_m" not in payload["computed_evidence"]
    payload["computed_evidence"]["changed_chainage_delta_m"] = None
    mutated = tmp_path / "mutated-unavailable-evidence.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["evidence"]["keys"]["changed_chainage_delta_m"] == 0.0


def test_verifier_accepts_equivalent_claim_boundary_wording(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "missing_revised_chainage")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["claim_boundary_statement"] = (
        "This review record covers a task-owned synthetic source packet only. "
        "It does not constitute authority approval, accepted project evidence, full standards compliance "
        "verification, source-pack hardening, executable-verifier readiness, or benchmark readiness."
    )
    mutated = tmp_path / "mutated-claim-boundary.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward == 1.0
    assert details["gates"]["identity_claims"]["checks"]["claim_boundary"] == 1.0


def test_verifier_zeroes_readiness_on_unsupported_ready_decision(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "unsupported_downstream_repair")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
