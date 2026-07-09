# ABOUTME: Tests the SSC-01 review-first road visual operations issue review template.
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
    / "road_visual_operations_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "average_illuminance_lux",
    "minimum_illuminance_lux",
    "uniformity_ratio",
    "minimum_uniformity_ratio",
    "total_network_load_mbps",
    "network_headroom_mbps",
    "total_cctv_storage_tb",
    "poe_load_w",
    "poe_headroom_w",
    "water_level_margin_m",
    "ups_energy_kwh",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_poe_switch_budget": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_lighting_grid_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "device_register_mismatch": {
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
    "poe_budget_exceeded": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/road-segment-and-lighting-grid.md",
    "sources/device-register.md",
    "sources/network-and-storage.md",
    "sources/poe-and-ups-schedule.md",
    "sources/storm-operations-note.md",
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

    assert "road-visual-operations-issue-review-package" in templates
    config = templates["road-visual-operations-issue-review-package"]
    assert config.meta.discipline == "electrical"
    assert config.meta.category == "road-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    averages = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        averages.add(instance.ground_truth["average_illuminance_lux"])

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(averages) >= 10, "Numeric parameters do not vary across seeds"


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

    assert gold["uniformity_ratio"] >= gold["minimum_uniformity_ratio"]
    assert gold["network_headroom_mbps"] > 0.0
    assert gold["poe_headroom_w"] > 0.0
    assert gold["water_level_margin_m"] > 0.0
    assert gold["ups_energy_kwh"] > 0.0


def test_poe_budget_exceeded_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("poe_budget_exceeded")

    assert instance.ground_truth["poe_headroom_w"] < 0.0


def test_missing_poe_switch_budget_variant_omits_poe_headroom() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_poe_switch_budget")

    assert "poe_load_w" in instance.ground_truth
    assert "poe_headroom_w" not in instance.ground_truth


def test_build_sources_produces_seven_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in [
        "RD-SSC01-003",
        "LGT-SSC01-003",
        "LUM-SSC01-003",
        "CCTV-SSC01-003",
        "VMS-SSC01-003",
        "NET-SSC01-003",
        "PWR-SSC01-003",
        "WLS-SSC01-003",
        "OPS-SSC01-003",
    ]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["LGT-SSC01-003", "NET-SSC01-003", "PWR-SSC01-003", "CRIT-SSC01-003"]:
        assert doc_id in register


def test_missing_poe_budget_sources_do_not_print_review_answer() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_poe_switch_budget")
    sources = engine.build_sources(instance.all_params)

    power = sources["sources/poe-and-ups-schedule.md"].lower()
    criteria = sources["sources/criteria-comments.md"].lower()

    assert "pending vendor confirmation" in power
    assert "decimal tb" in criteria
    assert "missing-data boundary" not in criteria
    assert "insufficient_data" not in criteria
    assert "not_ready_to_issue" not in criteria
    assert "not ready_with_carried_actions" not in criteria
    assert "do not carry" not in criteria


def test_criteria_define_decimal_storage_conversion() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    criteria = sources["sources/criteria-comments.md"].lower()

    assert "decimal tb" in criteria
    assert "divide by 8, then by 1000 twice" in criteria
    assert "do not use 1024" in criteria


def test_scenario_copy_forward_sources_bound_other_checks_to_current_packet() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("scenario_copy_forward")
    sources = engine.build_sources(instance.all_params)

    storm = sources["sources/storm-operations-note.md"]
    criteria = sources["sources/criteria-comments.md"].lower()
    power = sources["sources/poe-and-ups-schedule.md"]
    network = sources["sources/network-and-storage.md"]

    assert "copied from corridor RD-SSC01-099" in storm
    assert "primary/collateral boundary" not in criteria
    assert "do not cascade" not in criteria
    assert "PoE load" in power
    assert "Uplink capacity" in network


def test_sources_print_quantized_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    lighting = sources["sources/road-segment-and-lighting-grid.md"]
    network = sources["sources/network-and-storage.md"]
    power = sources["sources/poe-and-ups-schedule.md"]

    assert re.search(r"Grid point LG-01 \| \d+\.\d lux", lighting)
    assert re.search(r"Network overhead \| \d+ %", network)
    assert re.search(r"PoE switch budget \| \d+ W", power)


def _assert_visual_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    lighting = sources["sources/road-segment-and-lighting-grid.md"]
    network = sources["sources/network-and-storage.md"]
    power = sources["sources/poe-and-ups-schedule.md"]
    storm = sources["sources/storm-operations-note.md"]
    criteria = sources["sources/criteria-comments.md"]

    lux_values = [_grab(rf"Grid point LG-0{i} \| ([\d.]+) lux", lighting) for i in range(1, 7)]
    average = sum(lux_values) / len(lux_values)
    minimum = min(lux_values)
    uniformity = minimum / average

    assert average == pytest.approx(gold["average_illuminance_lux"], rel=0.01)
    assert minimum == pytest.approx(gold["minimum_illuminance_lux"], rel=0.01)
    assert uniformity == pytest.approx(gold["uniformity_ratio"], rel=0.01)
    assert _grab(r"Minimum uniformity ratio \| ([\d.]+)", criteria) == pytest.approx(
        gold["minimum_uniformity_ratio"], abs=0.01
    )

    cctv_count = int(_grab(r"Active CCTV cameras \| (\d+)", network))
    cctv_load = _grab(r"CCTV network load per camera \| ([\d.]+) Mbps", network)
    vms_load = _grab(r"VMS network load \| ([\d.]+) Mbps", network)
    sensor_load = _grab(r"Storm sensor network load \| ([\d.]+) Mbps", network)
    controller_load = _grab(r"Controller network load \| ([\d.]+) Mbps", network)
    overhead = _grab(r"Network overhead \| ([\d.]+) %", network)
    uplink = _grab(r"Uplink capacity \| ([\d.]+) Mbps", network)
    bitrate = _grab(r"Total CCTV bitrate \| ([\d.]+) Mbps", network)
    retention = _grab(r"Retention period \| ([\d.]+) days", network)
    storage_overhead = _grab(r"Storage overhead factor \| ([\d.]+)", network)

    base_load = cctv_count * cctv_load + vms_load + sensor_load + controller_load
    total_network = base_load * (1 + overhead / 100.0)
    assert total_network == pytest.approx(gold["total_network_load_mbps"], rel=0.01)
    assert uplink - total_network == pytest.approx(gold["network_headroom_mbps"], rel=0.01, abs=0.02)
    storage = bitrate * 24.0 * 3600.0 / 8.0 / 1000.0 * retention * storage_overhead / 1000.0
    assert storage == pytest.approx(gold["total_cctv_storage_tb"], rel=0.01)

    cctv_poe = _grab(r"CCTV PoE load per camera \| ([\d.]+) W", power)
    vms_poe = _grab(r"VMS PoE load \| ([\d.]+) W", power)
    sensor_poe = _grab(r"Storm sensor PoE load \| ([\d.]+) W", power)
    poe_load = cctv_count * cctv_poe + vms_poe + sensor_poe
    assert poe_load == pytest.approx(gold["poe_load_w"], rel=0.01)
    if "poe_headroom_w" in gold:
        poe_budget = _grab(r"PoE switch budget \| ([\d.]+) W", power)
        assert poe_budget - poe_load == pytest.approx(gold["poe_headroom_w"], abs=0.01)
    else:
        assert "pending vendor confirmation" in power

    sensor_level = _grab(r"Storm sensor level \| ([\d.]+) m", storm)
    alarm_threshold = _grab(r"Storm alarm threshold \| ([\d.]+) m", storm)
    assert alarm_threshold - sensor_level == pytest.approx(gold["water_level_margin_m"], abs=0.01)

    luminaire_count = _grab(r"Luminaire count \| ([\d.]+)", power)
    luminaire_power = _grab(r"Luminaire power \| ([\d.]+) W", power)
    device_load = _grab(r"Device UPS load \| ([\d.]+) W", power)
    autonomy = _grab(r"UPS autonomy \| ([\d.]+) h", power)
    efficiency = _grab(r"UPS efficiency \| ([\d.]+)", power)
    ups_energy = (luminaire_count * luminaire_power + device_load) * autonomy / efficiency / 1000.0
    assert ups_energy == pytest.approx(gold["ups_energy_kwh"], rel=0.01)


@pytest.mark.parametrize("variant", ["clean", "poe_budget_exceeded"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_visual_evidence_recomputable_from_sources(variant)


def test_missing_poe_budget_packet_recomputes_available_evidence() -> None:
    _assert_visual_evidence_recomputable_from_sources("missing_poe_switch_budget")


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
    assert "missing PoE switch budget" not in system_prompt
    assert "do not use 1024" not in system_prompt

    assert not list(instance_dir.glob("environment/*_calc.py")), "no-tool template must not ship a calc script"

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
    assert "single RLR item" in instruction
    assert "Do not rename computed_evidence keys" in instruction
    assert "poe_headroom_w" in instruction
    assert "network_headroom_mbps" in instruction
    assert "missing PoE switch budget" not in instruction
    assert "do not use 1024" not in instruction
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
    instance_dir, _gold = _scaffold_variant(tmp_path, "poe_budget_exceeded")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
