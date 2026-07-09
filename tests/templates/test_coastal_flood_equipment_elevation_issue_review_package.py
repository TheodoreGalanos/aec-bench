# ABOUTME: Tests the SSC-04 review-first coastal flood equipment elevation package.
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
    / "civil"
    / "coastal_flood_equipment_elevation_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "design_flood_level_m_ahd",
    "wave_runup_m",
    "switchboard_freeboard_m",
    "switchboard_freeboard_margin_m",
    "generator_freeboard_margin_m",
    "outfall_submergence_margin_m",
    "pump_duty_margin",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_switchboard_survey_level": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_water_level_basis_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "asset_survey_chart_datum_labelled_ahd": {
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
    "switchboard_below_design_level": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/tide-water-level-basis.md",
    "sources/slr-planning-horizon.md",
    "sources/wave-runup-basis.md",
    "sources/asset-survey.md",
    "sources/pump-outfall-schedule.md",
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


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "coastal-flood-equipment-elevation-issue-review-package" in templates
    config = templates["coastal-flood-equipment-elevation-issue-review-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "coastal-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    flood_levels = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        flood_levels.add(instance.ground_truth["design_flood_level_m_ahd"])

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(flood_levels) >= 10, "Numeric parameters do not vary across seeds (min==max regression)"


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    a = sample_instance(config, engine.compute, "medium", seed=19, instance_index=0)
    b = sample_instance(config, engine.compute, "medium", seed=19, instance_index=0)

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

    assert gold["switchboard_freeboard_margin_m"] > 0.0
    assert gold["generator_freeboard_margin_m"] > 0.0
    assert gold["outfall_submergence_margin_m"] > 0.0
    assert gold["pump_duty_margin"] > 0.0


def test_switchboard_deficient_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("switchboard_below_design_level")
    gold = instance.ground_truth

    assert gold["switchboard_freeboard_margin_m"] < 0.0
    assert gold["generator_freeboard_margin_m"] > 0.0
    assert gold["pump_duty_margin"] > 0.0


def test_missing_switchboard_omits_switchboard_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_switchboard_survey_level")

    assert "switchboard_freeboard_m" not in instance.ground_truth
    assert "switchboard_freeboard_margin_m" not in instance.ground_truth
    assert instance.ground_truth["design_flood_level_m_ahd"] > 0.0
    assert instance.ground_truth["generator_freeboard_margin_m"] > 0.0


def test_build_sources_produces_seven_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in ["SITE-04", "DATUM-04", "TIDE-04", "SLR-04", "RUNUP-04", "SWBD-04", "GEN-04", "OUTFALL-04"]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["TIDE-04-BASIS-01", "SLR-04-SCEN-01", "SURV-04-ASSET-01", "CRIT-SSC04-001"]:
        assert doc_id in register


def test_missing_switchboard_sources_mark_pending_record() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_switchboard_survey_level")
    sources = engine.build_sources(instance.all_params)

    survey = sources["sources/asset-survey.md"]
    assert "survey to follow" in survey.lower()

    clean_params = dict(instance.all_params)
    clean_params["packet_variant"] = "clean"
    clean_survey = engine.build_sources(clean_params)["sources/asset-survey.md"]
    assert clean_survey != survey


def test_datum_variant_sources_have_chart_datum_conflict() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("asset_survey_chart_datum_labelled_ahd")
    sources = engine.build_sources(instance.all_params)

    survey = sources["sources/asset-survey.md"]
    assert "chart datum" in survey.lower()
    assert "labelled AHD" in survey


def test_stale_water_level_sources_have_revision_mismatch() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("stale_water_level_basis_revision")
    sources = engine.build_sources(instance.all_params)

    register = sources["sources/document-register.md"]
    water = sources["sources/tide-water-level-basis.md"]

    assert "TIDE-04-BASIS-01 | Tide and water-level basis | Rev D" in register
    assert "TIDE-04-BASIS-01 (Rev C)" in water


def test_sources_print_exact_engine_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)
    criteria = sources["sources/criteria-comments.md"]

    assert re.search(r"Required equipment freeboard: \d+\.\d{2} m", criteria)
    assert re.search(r"Outfall allowable tailwater: \d+\.\d{2} m AHD", criteria)


def _grab(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    assert match, f"Pattern not found: {pattern}"
    return float(match.group(1))


def _assert_coastal_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    water = sources["sources/tide-water-level-basis.md"]
    slr = sources["sources/slr-planning-horizon.md"]
    runup = sources["sources/wave-runup-basis.md"]
    survey = sources["sources/asset-survey.md"]
    pump = sources["sources/pump-outfall-schedule.md"]
    criteria = sources["sources/criteria-comments.md"]

    msl = _grab(r"Present mean sea level[^|]*\| ([\d.]+) m AHD", water)
    tide = _grab(r"Tide amplitude[^|]*\| ([\d.]+) m", water)
    surge = _grab(r"Storm surge[^|]*\| ([\d.]+) m", water)
    slr_allowance = _grab(r"SLR allowance[^|]*\| ([\d.]+) m", slr)
    wave_runup = _grab(r"Wave runup[^|]*\| ([\d.]+) m", runup)
    freeboard = _grab(r"Required equipment freeboard: ([\d.]+) m", criteria)
    outfall_allowable = _grab(r"Outfall allowable tailwater: ([\d.]+) m AHD", criteria)
    design_tailwater = _grab(r"Design tailwater[^|]*\| ([\d.]+) m AHD", pump)
    required_pump = _grab(r"Required pump duty[^|]*\| ([\d.]+) m3/s", pump)
    selected_pump = _grab(r"Selected pump duty[^|]*\| ([\d.]+) m3/s", pump)

    design_flood = msl + tide + slr_allowance + surge + wave_runup

    assert wave_runup == pytest.approx(gold["wave_runup_m"], rel=0.01)
    assert design_flood == pytest.approx(gold["design_flood_level_m_ahd"], rel=0.01)
    assert outfall_allowable - design_tailwater == pytest.approx(
        gold["outfall_submergence_margin_m"],
        rel=0.01,
        abs=0.01,
    )
    assert selected_pump - required_pump == pytest.approx(gold["pump_duty_margin"], rel=0.01, abs=0.01)

    generator = _grab(r"Generator surveyed elevation[^|]*\| ([\d.]+) m AHD", survey)
    assert generator - design_flood - freeboard == pytest.approx(
        gold["generator_freeboard_margin_m"],
        rel=0.01,
        abs=0.01,
    )

    if "switchboard_freeboard_m" not in gold:
        assert "survey to follow" in survey
        return

    switchboard = _grab(r"Switchboard surveyed elevation[^|]*\| ([\d.]+) m AHD", survey)
    assert switchboard - design_flood == pytest.approx(gold["switchboard_freeboard_m"], rel=0.01, abs=0.01)
    assert switchboard - design_flood - freeboard == pytest.approx(
        gold["switchboard_freeboard_margin_m"],
        rel=0.01,
        abs=0.01,
    )


@pytest.mark.parametrize("variant", ["clean", "switchboard_below_design_level"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_coastal_evidence_recomputable_from_sources(variant)


def test_missing_switchboard_packet_recomputes_no_switchboard_evidence() -> None:
    _assert_coastal_evidence_recomputable_from_sources("missing_switchboard_survey_level")


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
    instance_dir, _gold = _scaffold_variant(tmp_path, "switchboard_below_design_level")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
