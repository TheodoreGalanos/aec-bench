# ABOUTME: Tests the SSC-19 review-first fire-water hazard and storage package.
# ABOUTME: Covers variant gold states, generated source packs, closure, and stage-gated verifier behavior.

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
    / "mechanical"
    / "fire_water_storage_hazard_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "design_density_mm_min",
    "design_area_m2",
    "sprinkler_demand_l_min",
    "hose_allowance_l_min",
    "required_duration_min",
    "required_volume_m3",
    "storage_volume_margin_m3",
    "pump_capacity_margin_l_min",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_commodity_classification": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_hazard_basis_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "tank_volume_mismatch": {
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
    "storage_deficient_under_true_class": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/hazard-storage-arrangement.md",
    "sources/sprinkler-hydrant-demand.md",
    "sources/tank-pump-schedule.md",
    "sources/fire-strategy-operating-case.md",
    "sources/water-supply-basis.md",
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


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "fire-water-storage-hazard-issue-review-package" in templates
    config = templates["fire-water-storage-hazard-issue-review-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "fire-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    volumes = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        volumes.add(instance.ground_truth.get("required_volume_m3", -1.0))

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(volumes) >= 10, "Numeric parameters do not vary across seeds (min==max regression)"


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

    assert gold["storage_volume_margin_m3"] > 0.0
    assert gold["pump_capacity_margin_l_min"] > 0.0
    assert gold["sprinkler_demand_l_min"] == pytest.approx(
        gold["design_density_mm_min"] * gold["design_area_m2"],
        rel=0.01,
    )


def test_storage_deficient_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("storage_deficient_under_true_class")
    gold = instance.ground_truth

    assert gold["storage_volume_margin_m3"] < 0.0
    assert gold["pump_capacity_margin_l_min"] > 0.0


def test_missing_commodity_classification_omits_hazard_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_commodity_classification")

    for key in EVIDENCE_KEYS:
        if key == "hose_allowance_l_min":
            continue
        assert key not in instance.ground_truth
    assert instance.ground_truth["hose_allowance_l_min"] > 0.0


def test_build_sources_produces_seven_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in ["BLDG-19", "HAZ-19", "SPR-19", "TANK-19", "PUMP-19", "AHJ-19"]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["HAZ-19-ARR-01", "SPR-19-DMD-01", "TANK-19-SCH-01", "CRIT-SSC19-001"]:
        assert doc_id in register


def test_missing_commodity_classification_sources_mark_pending_certificate() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_commodity_classification")
    sources = engine.build_sources(instance.all_params)

    hazard = sources["sources/hazard-storage-arrangement.md"]
    assert "commodity classification certificate" in hazard
    assert "pending" in hazard.lower()

    clean_params = dict(instance.all_params)
    clean_params["packet_variant"] = "clean"
    clean_hazard = engine.build_sources(clean_params)["sources/hazard-storage-arrangement.md"]
    assert clean_hazard != hazard


def test_missing_commodity_packet_does_not_close_certificate_indexing_comment() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_commodity_classification")

    criteria = engine.build_sources(instance.all_params)["sources/criteria-comments.md"]

    assert "Confirm commodity certificate has been indexed." not in criteria


def test_stale_hazard_sources_have_revision_mismatch() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("stale_hazard_basis_revision")
    sources = engine.build_sources(instance.all_params)

    register = sources["sources/document-register.md"]
    hazard = sources["sources/hazard-storage-arrangement.md"]

    assert "Rev C" in register
    assert "Rev B" in hazard


def test_sources_print_exact_engine_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)
    hazard = sources["sources/hazard-storage-arrangement.md"]

    assert re.search(r"Storage height[^|]*\| \d+\.\d m", hazard)


def _grab(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    assert match, f"Pattern not found: {pattern}"
    return float(match.group(1))


def _class_from_height(height_m: float, area_adjustment_m2: float) -> tuple[float, float, float, float]:
    if height_m <= 6.5:
        return 12.2, 230.0 + area_adjustment_m2, 1900.0, 90.0
    return 16.3, 280.0 + area_adjustment_m2, 1900.0, 120.0


def _assert_fire_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    hazard = sources["sources/hazard-storage-arrangement.md"]
    tank = sources["sources/tank-pump-schedule.md"]
    criteria = sources["sources/criteria-comments.md"]

    if "design_density_mm_min" not in gold:
        assert "commodity classification certificate pending" in hazard
        return

    height = _grab(r"Storage height[^|]*\| ([\d.]+) m", hazard)
    adjustment = _grab(r"Remote-area adjustment for HAZ-19: (-?[\d.]+) m2", criteria)
    density, area, hose, duration = _class_from_height(height, adjustment)
    sprinkler = density * area
    total = sprinkler + hose
    required_volume = total * duration / 1000.0
    storage = _grab(r"Available fire-water storage[^|]*\| ([\d.]+) m3", tank)
    pump_capacity = _grab(r"Fire pump rated capacity[^|]*\| ([\d.]+) L/min", tank)

    assert density == pytest.approx(gold["design_density_mm_min"], rel=0.01)
    assert area == pytest.approx(gold["design_area_m2"], rel=0.01)
    assert sprinkler == pytest.approx(gold["sprinkler_demand_l_min"], rel=0.01)
    assert hose == pytest.approx(gold["hose_allowance_l_min"], rel=0.01)
    assert duration == pytest.approx(gold["required_duration_min"], rel=0.01)
    assert required_volume == pytest.approx(gold["required_volume_m3"], rel=0.01)
    assert storage - required_volume == pytest.approx(gold["storage_volume_margin_m3"], rel=0.01, abs=0.05)
    assert pump_capacity - total == pytest.approx(gold["pump_capacity_margin_l_min"], rel=0.01, abs=0.05)


@pytest.mark.parametrize("variant", ["clean", "storage_deficient_under_true_class"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_fire_evidence_recomputable_from_sources(variant)


def test_missing_commodity_packet_recomputes_no_hazard_evidence() -> None:
    _assert_fire_evidence_recomputable_from_sources("missing_commodity_classification")


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
    instance_dir, _gold = _scaffold_variant(tmp_path, "storage_deficient_under_true_class")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
