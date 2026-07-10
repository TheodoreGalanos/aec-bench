# ABOUTME: Tests the SSC-01 review-first driveway access safety issue review template.
# ABOUTME: Covers variant gold states, generated source packs, and the stage-gated review verifier.

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
    / "civil"
    / "driveway_access_safety_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "driveway_grade_percent",
    "driveway_grade_margin_percent",
    "culvert_capacity_m3_s",
    "culvert_capacity_margin_m3_s",
    "headwater_level_m",
    "freeboard_m",
    "freeboard_margin_m",
    "roadway_spread_m",
    "spread_margin_m",
    "sight_distance_required_m",
    "sight_distance_margin_m",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_road_edge_level": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_access_profile_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "culvert_chainage_mismatch": {
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
    "access_freeboard_deficient": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/access-profile.md",
    "sources/culvert-drainage-schedule.md",
    "sources/surface-tailwater-table.md",
    "sources/roadway-spread-note.md",
    "sources/sight-distance-note.md",
    "sources/owner-access-criterion.md",
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

    assert "driveway-access-safety-issue-review-package" in templates
    config = templates["driveway-access-safety-issue-review-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "road-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    grades = set()
    for seed in range(60):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        grades.add(round(instance.ground_truth["driveway_grade_percent"], 3))

    assert len(variants) >= 4, "Variant distribution collapsed"
    assert len(grades) >= 10, "Numeric parameters do not vary across seeds"


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

    assert gold["driveway_grade_margin_percent"] > 0.0
    assert gold["culvert_capacity_margin_m3_s"] > 0.0
    assert gold["freeboard_margin_m"] > 0.0
    assert gold["spread_margin_m"] > 0.0
    assert gold["sight_distance_margin_m"] > 0.0


def test_access_freeboard_deficient_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("access_freeboard_deficient")

    assert instance.ground_truth["freeboard_margin_m"] < 0.0


def test_missing_road_edge_level_variant_omits_freeboard_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_road_edge_level")

    assert "headwater_level_m" in instance.ground_truth
    assert "freeboard_m" not in instance.ground_truth
    assert "freeboard_margin_m" not in instance.ground_truth


def test_build_sources_produces_eight_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in [
        "ACCESS-SSC01-006",
        "ROAD-SSC01-006",
        "CULV-SSC01-006",
        "TAIL-SSC01-006",
        "SIGHT-SSC01-006",
        "OPS-SSC01-006",
        "MEMO-SSC01-006",
        "CRIT-SSC01-006",
    ]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["ACCESS-SSC01-006", "CULV-SSC01-006", "ROAD-SSC01-006", "MEMO-SSC01-006"]:
        assert doc_id in register


def test_missing_road_edge_sources_do_not_print_review_answer() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_road_edge_level")
    sources = engine.build_sources(instance.all_params)

    access = sources["sources/access-profile.md"].lower()
    criteria = sources["sources/criteria-comments.md"].lower()

    assert "pending road edge survey confirmation" in access
    assert "grade-adjusted braking" in criteria
    assert "missing-data boundary" not in criteria
    assert "insufficient_data" not in criteria
    assert "not_ready_to_issue" not in criteria
    assert "not ready_with_carried_actions" not in criteria
    assert "do not carry" not in criteria


def test_criteria_define_source_owned_methods() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    criteria = sources["sources/criteria-comments.md"].lower()

    assert "manning" in criteria
    assert "full circular pipe" in criteria
    assert "ratio-squared" in criteria
    assert "triangular-gutter" in criteria
    assert "0.376" in criteria
    assert "km/h to m/s" in criteria
    assert "3.6" in criteria
    assert "grade-adjusted braking" in criteria


def test_scenario_copy_forward_sources_bound_other_checks_to_current_packet() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("scenario_copy_forward")
    sources = engine.build_sources(instance.all_params)

    access = sources["sources/access-profile.md"]
    criteria = sources["sources/criteria-comments.md"].lower()
    culvert = sources["sources/culvert-drainage-schedule.md"]
    sight = sources["sources/sight-distance-note.md"]

    assert "copied from access case ACCESS-SSC01-099" in access
    assert "primary/collateral boundary" not in criteria
    assert "do not cascade" not in criteria
    assert "Culvert diameter" in culvert
    assert "Available sight distance" in sight


def test_sources_print_quantized_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    access = sources["sources/access-profile.md"]
    culvert = sources["sources/culvert-drainage-schedule.md"]
    spread = sources["sources/roadway-spread-note.md"]

    assert re.search(r"Driveway low level \| \d+\.\d{2} m", access)
    assert re.search(r"Driveway length \| \d+\.\d m", access)
    assert re.search(r"Culvert diameter \| \d+\.\d{2} m", culvert)
    assert re.search(r"Longitudinal slope \| \d+\.\d %", spread)


def _assert_driveway_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    access = sources["sources/access-profile.md"]
    culvert = sources["sources/culvert-drainage-schedule.md"]
    tailwater = sources["sources/surface-tailwater-table.md"]
    spread = sources["sources/roadway-spread-note.md"]
    sight = sources["sources/sight-distance-note.md"]
    owner = sources["sources/owner-access-criterion.md"]

    low = _grab(r"Driveway low level \| ([\d.]+) m", access)
    high = _grab(r"Driveway high level \| ([\d.]+) m", access)
    length = _grab(r"Driveway length \| ([\d.]+) m", access)
    allowable_grade = _grab(r"Maximum driveway grade \| ([\d.]+) %", owner)
    driveway_grade = (high - low) / length * 100.0
    assert driveway_grade == pytest.approx(gold["driveway_grade_percent"], rel=0.01, abs=0.02)
    assert allowable_grade - abs(driveway_grade) == pytest.approx(
        gold["driveway_grade_margin_percent"], rel=0.01, abs=0.02
    )

    diameter = _grab(r"Culvert diameter \| ([\d.]+) m", culvert)
    mannings_n = _grab(r"Culvert Manning n \| ([\d.]+)", culvert)
    slope_pct = _grab(r"Culvert slope \| ([\d.]+) %", culvert)
    design_flow = _grab(r"Design flow \| ([\d.]+) m3/s", culvert)
    area = math.pi * diameter**2 / 4.0
    hydraulic_radius = diameter / 4.0
    culvert_capacity = area * hydraulic_radius ** (2.0 / 3.0) * math.sqrt(slope_pct / 100.0) / mannings_n
    assert culvert_capacity == pytest.approx(gold["culvert_capacity_m3_s"], rel=0.01, abs=0.02)
    assert culvert_capacity - design_flow == pytest.approx(gold["culvert_capacity_margin_m3_s"], rel=0.01, abs=0.02)

    tailwater_level = _grab(r"Tailwater level \| ([\d.]+) m", tailwater)
    base_depth = _grab(r"Base headwater depth \| ([\d.]+) m", tailwater)
    loss_factor = _grab(r"Headwater loss factor \| ([\d.]+) m", tailwater)
    headwater_level = tailwater_level + base_depth + loss_factor * (design_flow / culvert_capacity) ** 2
    assert headwater_level == pytest.approx(gold["headwater_level_m"], rel=0.01, abs=0.02)

    road_edge_match = re.search(r"Road edge level \| ([\d.]+) m", access)
    if "freeboard_m" in gold:
        assert road_edge_match
        road_edge = float(road_edge_match.group(1))
        minimum_freeboard = _grab(r"Minimum road-edge freeboard \| ([\d.]+) m", owner)
        freeboard = road_edge - headwater_level
        assert freeboard == pytest.approx(gold["freeboard_m"], rel=0.01, abs=0.02)
        assert freeboard - minimum_freeboard == pytest.approx(gold["freeboard_margin_m"], rel=0.01, abs=0.02)
    else:
        assert not road_edge_match
        assert "pending road edge survey confirmation" in access

    gutter_flow = _grab(r"Gutter flow \| ([\d.]+) m3/s", spread)
    cross_slope = _grab(r"Cross slope \| ([\d.]+) %", spread)
    longitudinal_slope = _grab(r"Longitudinal slope \| ([\d.]+) %", spread)
    gutter_n = _grab(r"Gutter Manning n \| ([\d.]+)", spread)
    allowable_spread = _grab(r"Maximum spread across access path \| ([\d.]+) m", owner)
    roadway_spread = (
        gutter_flow * gutter_n / (0.376 * (cross_slope / 100.0) ** (5.0 / 3.0) * math.sqrt(longitudinal_slope / 100.0))
    ) ** (3.0 / 8.0)
    assert roadway_spread == pytest.approx(gold["roadway_spread_m"], rel=0.01, abs=0.02)
    assert allowable_spread - roadway_spread == pytest.approx(gold["spread_margin_m"], rel=0.01, abs=0.02)

    speed = _grab(r"Access speed \| ([\d.]+) km/h", sight)
    reaction = _grab(r"Sight reaction time \| ([\d.]+) s", sight)
    friction = _grab(r"Braking friction coefficient \| ([\d.]+)", sight)
    access_grade = _grab(r"Access grade \| ([\d.-]+) %", sight)
    available_sight = _grab(r"Available sight distance \| ([\d.]+) m", sight)
    speed_m_s = speed / 3.6
    required_sight = speed_m_s * reaction + speed_m_s**2 / (2.0 * 9.81 * (friction + access_grade / 100.0))
    assert required_sight == pytest.approx(gold["sight_distance_required_m"], rel=0.01, abs=0.02)
    assert available_sight - required_sight == pytest.approx(gold["sight_distance_margin_m"], rel=0.01, abs=0.02)


@pytest.mark.parametrize("variant", ["clean", "access_freeboard_deficient"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_driveway_evidence_recomputable_from_sources(variant)


def test_missing_road_edge_level_packet_recomputes_available_evidence() -> None:
    _assert_driveway_evidence_recomputable_from_sources("missing_road_edge_level")


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
    assert "missing road edge level" not in system_prompt

    assert not list(instance_dir.glob("environment/*_calc.py")), "no-tool template must not ship a calc script"

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
    assert "single RLR item" in instruction
    assert "Do not rename computed_evidence keys" in instruction
    assert "freeboard_margin_m" in instruction
    assert "sight_distance_margin_m" in instruction
    assert "missing road edge level" not in instruction
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
    instance_dir, _gold = _scaffold_variant(tmp_path, "access_freeboard_deficient")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
