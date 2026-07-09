# ABOUTME: Tests the SSC-01 review-first intersection signal safety issue review template.
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
    / "intersection_signal_safety_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "stopping_distance_m",
    "sight_distance_margin_m",
    "yellow_interval_s",
    "all_red_interval_s",
    "ped_clearance_required_s",
    "ped_clearance_margin_s",
    "grade_adjusted_braking_distance_m",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_pedestrian_clearance": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_timing_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "approach_datum_mismatch": {
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
    "pedestrian_clearance_deficient": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/intersection-layout.md",
    "sources/approach-profile.md",
    "sources/signal-timing-sheet.md",
    "sources/pedestrian-crossing.md",
    "sources/sight-distance-note.md",
    "sources/controller-handoff.md",
    "sources/criteria-comments.md",
]


def _load() -> tuple:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    return config, template_dir, engine


def _instance_for_variant(variant: str, max_seeds: int = 600):
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

    assert "intersection-signal-safety-issue-review-package" in templates
    config = templates["intersection-signal-safety-issue-review-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "road-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    stopping_distances = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        stopping_distances.add(instance.ground_truth["stopping_distance_m"])

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(stopping_distances) >= 10, "Numeric parameters do not vary across seeds"


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

    assert gold["sight_distance_margin_m"] > 0.0
    assert gold["ped_clearance_margin_s"] > 0.0
    assert gold["yellow_interval_s"] > 0.0
    assert gold["all_red_interval_s"] > 0.0


def test_pedestrian_clearance_deficient_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("pedestrian_clearance_deficient")
    gold = instance.ground_truth

    assert gold["ped_clearance_margin_s"] < 0.0


def test_missing_pedestrian_clearance_variant_omits_margin_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_pedestrian_clearance")

    assert "ped_clearance_margin_s" not in instance.ground_truth


def test_build_sources_produces_eight_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in ["INT-02", "APP-NB-02", "SG-02", "PED-X-02", "CTRL-02", "CASE-AM-02", "AHD"]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["INT-SSC01-002", "PROF-SSC01-002", "SIG-SSC01-002", "PED-SSC01-002", "CRIT-SSC01-002"]:
        assert doc_id in register


def test_missing_pedestrian_clearance_sources_omit_available_clearance() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_pedestrian_clearance")
    sources = engine.build_sources(instance.all_params)

    timing = sources["sources/signal-timing-sheet.md"]
    assert "pending controller export" in timing.lower()

    clean_params = dict(instance.all_params)
    clean_params["packet_variant"] = "clean"
    clean_timing = engine.build_sources(clean_params)["sources/signal-timing-sheet.md"]
    assert clean_timing != timing


def test_stale_timing_sources_have_revision_mismatch() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("stale_timing_revision")
    sources = engine.build_sources(instance.all_params)

    register = sources["sources/document-register.md"]
    timing = sources["sources/signal-timing-sheet.md"]

    assert "Rev C" in register
    assert "Rev B" in timing


def test_sources_print_quantized_profile_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)
    profile = sources["sources/approach-profile.md"]

    assert re.search(r"Braking friction coefficient \| 0\.\d{2}", profile)


def _assert_intersection_evidence_recomputable_from_sources(variant: str) -> None:
    """Recompute the gold evidence available in a rendered source packet."""
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    profile = sources["sources/approach-profile.md"]
    timing = sources["sources/signal-timing-sheet.md"]
    ped = sources["sources/pedestrian-crossing.md"]
    sight = sources["sources/sight-distance-note.md"]

    speed = _grab(r"Approach design speed \| ([\d.]+) km/h", profile)
    grade = _grab(r"Signed approach grade \| (-?[\d.]+) %", profile)
    reaction = _grab(r"Reaction time \| ([\d.]+) s", profile)
    friction = _grab(r"Braking friction coefficient \| ([\d.]+)", profile)
    available_sight = _grab(r"Available sight distance \| ([\d.]+) m", sight)
    yellow_reaction = _grab(r"Yellow perception-reaction term \| ([\d.]+) s", timing)
    yellow_decel = _grab(r"Yellow deceleration rate \| ([\d.]+) m/s2", timing)
    intersection_width = _grab(r"Intersection width \| ([\d.]+) m", timing)
    vehicle_length = _grab(r"Design vehicle length \| ([\d.]+) m", timing)
    all_red_speed = _grab(r"All-red clearance speed \| ([\d.]+) km/h", timing)
    ped_startup = _grab(r"Pedestrian startup allowance \| ([\d.]+) s", ped)
    crossing_width = _grab(r"Crossing width \| ([\d.]+) m", ped)
    walk_speed = _grab(r"Pedestrian walk speed \| ([\d.]+) m/s", ped)

    speed_m_s = speed / 3.6
    grade_fraction = grade / 100.0
    braking = speed_m_s**2 / (2.0 * 9.81 * (friction + grade_fraction))
    stopping = speed_m_s * reaction + braking
    yellow = yellow_reaction + speed_m_s / (2.0 * yellow_decel + 2.0 * 9.81 * grade_fraction)
    all_red = (intersection_width + vehicle_length) / (all_red_speed / 3.6)
    ped_required = ped_startup + crossing_width / walk_speed

    assert stopping == pytest.approx(gold["stopping_distance_m"], rel=0.01, abs=0.02)
    assert available_sight - stopping == pytest.approx(gold["sight_distance_margin_m"], rel=0.01, abs=0.02)
    assert yellow == pytest.approx(gold["yellow_interval_s"], rel=0.01, abs=0.02)
    assert all_red == pytest.approx(gold["all_red_interval_s"], rel=0.01, abs=0.02)
    assert ped_required == pytest.approx(gold["ped_clearance_required_s"], rel=0.01, abs=0.02)
    assert braking == pytest.approx(gold["grade_adjusted_braking_distance_m"], rel=0.01, abs=0.02)

    if "ped_clearance_margin_s" in gold:
        ped_available = _grab(r"Available pedestrian clearance \| ([\d.]+) s", timing)
        assert ped_available - ped_required == pytest.approx(gold["ped_clearance_margin_s"], rel=0.01, abs=0.02)
    else:
        assert "pending controller export" in timing


@pytest.mark.parametrize("variant", ["clean", "pedestrian_clearance_deficient"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    """Clean and genuine-failure packets must be solvable from rendered sources alone."""
    _assert_intersection_evidence_recomputable_from_sources(variant)


def test_missing_pedestrian_clearance_packet_recomputes_available_evidence() -> None:
    """Missing-evidence packets must still expose all non-missing recomputable evidence."""
    _assert_intersection_evidence_recomputable_from_sources("missing_pedestrian_clearance")


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

    assert not list(instance_dir.glob("environment/*_calc.py")), "no-tool template must not ship a calc script"

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
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
    instance_dir, _gold = _scaffold_variant(tmp_path, "pedestrian_clearance_deficient")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
