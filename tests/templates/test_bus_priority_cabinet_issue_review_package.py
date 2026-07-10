# ABOUTME: Tests the SSC-01 review-first bus-priority cabinet issue review template.
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
    / "bus_priority_cabinet_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "yellow_interval_s",
    "all_red_interval_s",
    "bus_handling_capacity_pax_h",
    "bus_capacity_margin_pax_h",
    "cabinet_load_w",
    "cabinet_load_margin_w",
    "feeder_current_a",
    "feeder_voltage_drop_percent",
    "voltage_drop_margin_percent",
    "battery_runtime_h",
    "battery_margin_h",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_cabinet_capacity": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_signal_timing_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "detector_controller_mismatch": {
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
    "cabinet_load_exceeded": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/bus-priority-operations-plan.md",
    "sources/signal-phasing-timing-sheet.md",
    "sources/detector-controller-schedule.md",
    "sources/cabinet-load-schedule.md",
    "sources/feeder-backup-schedule.md",
    "sources/owner-operations-criterion.md",
    "sources/criteria-comments.md",
]


def _load() -> tuple:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    return config, template_dir, engine


def _instance_for_variant(variant: str, max_seeds: int = 1200):
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

    assert "bus-priority-cabinet-issue-review-package" in templates
    config = templates["bus-priority-cabinet-issue-review-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "road-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    yellow_times = set()
    for seed in range(50):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        yellow_times.add(round(instance.ground_truth["yellow_interval_s"], 3))

    assert len(variants) >= 4, "Variant distribution collapsed"
    assert len(yellow_times) >= 10, "Numeric parameters do not vary across seeds"


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

    assert gold["yellow_interval_s"] > 0.0
    assert gold["all_red_interval_s"] > 0.0
    assert gold["bus_capacity_margin_pax_h"] > 0.0
    assert gold["cabinet_load_margin_w"] > 0.0
    assert gold["voltage_drop_margin_percent"] > 0.0
    assert gold["battery_margin_h"] > 0.0


def test_cabinet_load_exceeded_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("cabinet_load_exceeded")

    assert instance.ground_truth["cabinet_load_margin_w"] < 0.0


def test_missing_cabinet_capacity_variant_omits_cabinet_margin() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_cabinet_capacity")

    assert "cabinet_load_w" in instance.ground_truth
    assert "cabinet_load_margin_w" not in instance.ground_truth


def test_build_sources_produces_eight_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in [
        "BUS-SSC01-005",
        "SIG-SSC01-005",
        "DET-SSC01-005",
        "CTRL-SSC01-005",
        "CAB-SSC01-005",
        "FEED-SSC01-005",
        "BATT-SSC01-005",
        "OPS-SSC01-005",
    ]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["BUS-SSC01-005", "SIG-SSC01-005", "CAB-SSC01-005", "FEED-SSC01-005", "CRIT-SSC01-005"]:
        assert doc_id in register


def test_missing_cabinet_capacity_sources_do_not_print_review_answer() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_cabinet_capacity")
    sources = engine.build_sources(instance.all_params)

    cabinet = sources["sources/cabinet-load-schedule.md"].lower()
    criteria = sources["sources/criteria-comments.md"].lower()

    assert "pending electrical cabinet schedule confirmation" in cabinet
    assert "w to kw" in criteria
    assert "missing-data boundary" not in criteria
    assert "insufficient_data" not in criteria
    assert "not_ready_to_issue" not in criteria
    assert "not ready_with_carried_actions" not in criteria
    assert "do not carry" not in criteria


def test_criteria_define_unit_conversions() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    criteria = sources["sources/criteria-comments.md"].lower()

    assert "km/h to m/s" in criteria
    assert "3.6" in criteria
    assert "signed grade" in criteria
    assert "buses per hour times passengers per bus" in criteria
    assert "w to kw" in criteria
    assert "2 x feeder length" in criteria
    assert "kwh x efficiency divided by load kw" in criteria


def test_scenario_copy_forward_sources_bound_other_checks_to_current_packet() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("scenario_copy_forward")
    sources = engine.build_sources(instance.all_params)

    operations = sources["sources/bus-priority-operations-plan.md"]
    criteria = sources["sources/criteria-comments.md"].lower()
    cabinet = sources["sources/cabinet-load-schedule.md"]
    feeder = sources["sources/feeder-backup-schedule.md"]

    assert "copied from scenario BUS-SSC01-099" in operations
    assert "primary/collateral boundary" not in criteria
    assert "do not cascade" not in criteria
    assert "Controller load" in cabinet
    assert "Battery capacity" in feeder


def test_sources_print_quantized_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    signal = sources["sources/signal-phasing-timing-sheet.md"]
    cabinet = sources["sources/cabinet-load-schedule.md"]
    feeder = sources["sources/feeder-backup-schedule.md"]

    assert re.search(r"Bus approach speed \| \d+ km/h", signal)
    assert re.search(r"Bus approach grade \| -?\d+\.\d %", signal)
    assert re.search(r"Detector count \| \d+", cabinet)
    assert re.search(r"Battery capacity \| \d+\.\d kWh", feeder)


def _assert_bus_priority_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    operations = sources["sources/bus-priority-operations-plan.md"]
    signal = sources["sources/signal-phasing-timing-sheet.md"]
    cabinet = sources["sources/cabinet-load-schedule.md"]
    feeder = sources["sources/feeder-backup-schedule.md"]

    speed = _grab(r"Bus approach speed \| ([\d.]+) km/h", signal)
    grade = _grab(r"Bus approach grade \| ([\d.-]+) %", signal)
    reaction = _grab(r"Yellow reaction time \| ([\d.]+) s", signal)
    deceleration = _grab(r"Yellow deceleration \| ([\d.]+) m/s2", signal)
    width = _grab(r"Intersection width \| ([\d.]+) m", signal)
    bus_length = _grab(r"Design bus length \| ([\d.]+) m", signal)
    all_red_speed = _grab(r"All-red clearance speed \| ([\d.]+) km/h", signal)

    yellow = reaction + (speed / 3.6) / (2.0 * deceleration + 2.0 * 9.81 * grade / 100.0)
    all_red = (width + bus_length) / (all_red_speed / 3.6)
    assert yellow == pytest.approx(gold["yellow_interval_s"], rel=0.01, abs=0.02)
    assert all_red == pytest.approx(gold["all_red_interval_s"], rel=0.01, abs=0.02)

    buses = _grab(r"Scheduled priority buses \| ([\d.]+) buses/h", operations)
    occupancy = _grab(r"Design bus occupancy \| ([\d.]+) passengers/bus", operations)
    demand = _grab(r"Peak passenger demand \| ([\d.]+) passengers/h", operations)
    capacity = buses * occupancy
    assert capacity == pytest.approx(gold["bus_handling_capacity_pax_h"], rel=0.01)
    assert capacity - demand == pytest.approx(gold["bus_capacity_margin_pax_h"], rel=0.01, abs=0.02)

    controller = _grab(r"Controller load \| ([\d.]+) W", cabinet)
    detector_count = int(_grab(r"Detector count \| (\d+)", cabinet))
    detector_load = _grab(r"Detector load per unit \| ([\d.]+) W", cabinet)
    radio = _grab(r"Transit radio load \| ([\d.]+) W", cabinet)
    vms = _grab(r"VMS load \| ([\d.]+) W", cabinet)
    heads = _grab(r"Signal heads load \| ([\d.]+) W", cabinet)
    cabinet_load = controller + detector_count * detector_load + radio + vms + heads
    assert cabinet_load == pytest.approx(gold["cabinet_load_w"], rel=0.01)

    capacity_match = re.search(r"Cabinet capacity \| ([\d.]+) W", cabinet)
    if "cabinet_load_margin_w" in gold:
        assert capacity_match
        cabinet_capacity = float(capacity_match.group(1))
        assert cabinet_capacity - cabinet_load == pytest.approx(gold["cabinet_load_margin_w"], rel=0.01, abs=0.02)
    else:
        assert not capacity_match
        assert "pending electrical cabinet schedule confirmation" in cabinet

    voltage = _grab(r"Feeder voltage \| ([\d.]+) V", feeder)
    power_factor = _grab(r"Power factor \| ([\d.]+)", feeder)
    feeder_length = _grab(r"Feeder length \| ([\d.]+) km", feeder)
    resistance = _grab(r"Conductor resistance \| ([\d.]+) ohm/km", feeder)
    allowable_drop = _grab(r"Allowable voltage drop \| ([\d.]+) %", feeder)
    current = cabinet_load / (voltage * power_factor)
    voltage_drop = 2.0 * feeder_length * resistance * current / voltage * 100.0
    assert current == pytest.approx(gold["feeder_current_a"], rel=0.01, abs=0.02)
    assert voltage_drop == pytest.approx(gold["feeder_voltage_drop_percent"], rel=0.01, abs=0.02)
    assert allowable_drop - voltage_drop == pytest.approx(gold["voltage_drop_margin_percent"], rel=0.01, abs=0.02)

    battery_capacity = _grab(r"Battery capacity \| ([\d.]+) kWh", feeder)
    battery_efficiency = _grab(r"Battery efficiency \| ([\d.]+)", feeder)
    required_backup = _grab(r"Required backup duration \| ([\d.]+) h", feeder)
    runtime = battery_capacity * battery_efficiency / (cabinet_load / 1000.0)
    assert runtime == pytest.approx(gold["battery_runtime_h"], rel=0.01)
    assert runtime - required_backup == pytest.approx(gold["battery_margin_h"], rel=0.01, abs=0.02)


@pytest.mark.parametrize("variant", ["clean", "cabinet_load_exceeded"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_bus_priority_evidence_recomputable_from_sources(variant)


def test_missing_cabinet_capacity_packet_recomputes_available_evidence() -> None:
    _assert_bus_priority_evidence_recomputable_from_sources("missing_cabinet_capacity")


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
    assert "missing cabinet capacity" not in system_prompt

    assert not list(instance_dir.glob("environment/*_calc.py")), "no-tool template must not ship a calc script"

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
    assert "single RLR item" in instruction
    assert "Do not rename computed_evidence keys" in instruction
    assert "cabinet_load_margin_w" in instruction
    assert "battery_margin_h" in instruction
    assert "missing cabinet capacity" not in instruction
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
    instance_dir, _gold = _scaffold_variant(tmp_path, "cabinet_load_exceeded")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
