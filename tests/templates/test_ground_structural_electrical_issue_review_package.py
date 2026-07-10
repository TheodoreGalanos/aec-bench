# ABOUTME: Tests the SSC-07 review-first ground structural-electrical issue package.
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
    / "ground"
    / "ground_structural_electrical_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "corrected_spt_n60",
    "design_friction_angle_deg",
    "allowable_bearing_kpa",
    "bearing_margin_kpa",
    "grid_resistance_ohm",
    "grid_resistance_margin_ohm",
    "touch_voltage_margin_v",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_groundwater_level": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_ground_memo_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "resistivity_strength_misuse": {
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
    "bearing_fos_deficient": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/borehole-spt-logs.md",
    "sources/groundwater-record.md",
    "sources/ground-interpretation-memo.md",
    "sources/foundation-load-table.md",
    "sources/resistivity-survey.md",
    "sources/earthing-grid-design.md",
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

    assert "ground-structural-electrical-issue-review-package" in templates
    config = templates["ground-structural-electrical-issue-review-package"]
    assert config.meta.discipline == "ground"
    assert config.meta.category == "ground-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    bearing_values = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        bearing_values.add(instance.ground_truth.get("allowable_bearing_kpa", -1.0))

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(bearing_values) >= 10, "Numeric parameters do not vary across seeds (min==max regression)"


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    a = sample_instance(config, engine.compute, "medium", seed=17, instance_index=0)
    b = sample_instance(config, engine.compute, "medium", seed=17, instance_index=0)

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

    assert gold["corrected_spt_n60"] > 0.0
    assert gold["allowable_bearing_kpa"] > 0.0
    assert gold["bearing_margin_kpa"] > 0.0
    assert gold["grid_resistance_margin_ohm"] > 0.0
    assert gold["touch_voltage_margin_v"] > 0.0


def test_bearing_deficient_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("bearing_fos_deficient")
    gold = instance.ground_truth

    assert gold["bearing_margin_kpa"] < 0.0
    assert gold["grid_resistance_margin_ohm"] > 0.0
    assert gold["touch_voltage_margin_v"] > 0.0


def test_missing_groundwater_omits_bearing_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_groundwater_level")

    assert "allowable_bearing_kpa" not in instance.ground_truth
    assert "bearing_margin_kpa" not in instance.ground_truth
    assert instance.ground_truth["corrected_spt_n60"] > 0.0
    assert instance.ground_truth["grid_resistance_margin_ohm"] > 0.0


def test_build_sources_produces_eight_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in ["SITE-07", "BH-07", "SPT-07", "GW-07", "FDN-07", "RES-07", "GRID-07"]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["BH-07-LOG-01", "GW-07-REC-01", "GIM-07-MEMO-01", "CRIT-SSC07-001"]:
        assert doc_id in register


def test_missing_groundwater_sources_mark_pending_record() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_groundwater_level")
    sources = engine.build_sources(instance.all_params)

    groundwater = sources["sources/groundwater-record.md"]
    assert "standpipe readings pending" in groundwater.lower()

    clean_params = dict(instance.all_params)
    clean_params["packet_variant"] = "clean"
    clean_groundwater = engine.build_sources(clean_params)["sources/groundwater-record.md"]
    assert clean_groundwater != groundwater


def test_partition_variant_sources_misuse_resistivity_as_strength() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("resistivity_strength_misuse")
    sources = engine.build_sources(instance.all_params)

    memo = sources["sources/ground-interpretation-memo.md"]
    assert "RES-07 layer" in memo
    assert "strength stratum" in memo


def test_stale_ground_memo_sources_have_revision_mismatch() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("stale_ground_memo_revision")
    sources = engine.build_sources(instance.all_params)

    register = sources["sources/document-register.md"]
    memo = sources["sources/ground-interpretation-memo.md"]

    assert "GIM-07-MEMO-01 | Ground interpretation memo | Rev C" in register
    assert "GIM-07-MEMO-01 (Rev B)" in memo


def test_sources_print_exact_engine_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)
    criteria = sources["sources/criteria-comments.md"]

    assert re.search(r"Design friction angle: \d+\.\d degrees", criteria)
    assert re.search(r"Grid resistance limit: \d+\.\d{3} ohm", criteria)


def _grab(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    assert match, f"Pattern not found: {pattern}"
    return float(match.group(1))


def _bearing_factors(phi_deg: float) -> tuple[float, float, float]:
    phi_rad = math.radians(phi_deg)
    exponent = 2.0 * (3.0 * math.pi / 4.0 - phi_rad / 2.0) * math.tan(phi_rad)
    denominator = 2.0 * math.cos(math.radians(45.0) + phi_rad / 2.0) ** 2
    nq = math.exp(exponent) / denominator
    nc = (nq - 1.0) / math.tan(phi_rad)
    ngamma = 19.7 + (phi_deg - 30.0) / 4.0 * (36.0 - 19.7)
    return nc, nq, ngamma


def _assert_ground_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    borehole = sources["sources/borehole-spt-logs.md"]
    groundwater = sources["sources/groundwater-record.md"]
    foundation = sources["sources/foundation-load-table.md"]
    resistivity = sources["sources/resistivity-survey.md"]
    grid = sources["sources/earthing-grid-design.md"]
    criteria = sources["sources/criteria-comments.md"]

    raw_n = _grab(r"Raw SPT N[^|]*\| ([\d.]+)", borehole)
    overburden = _grab(r"Effective overburden[^|]*\| ([\d.]+) kPa", borehole)
    n60 = raw_n * 1.33 * 1.0 * 1.0 * 0.95
    design_phi = 27.0 + 0.25 * n60

    assert n60 == pytest.approx(gold["corrected_spt_n60"], rel=0.01)
    assert overburden > 0.0
    assert design_phi == pytest.approx(gold["design_friction_angle_deg"], rel=0.01)

    rho = _grab(r"Apparent resistivity[^|]*\| ([\d.]+) ohm-m", resistivity)
    length = _grab(r"Grid length[^|]*\| ([\d.]+) m", grid)
    width = _grab(r"Grid width[^|]*\| ([\d.]+) m", grid)
    conductor = _grab(r"Total buried conductor[^|]*\| ([\d.]+) m", grid)
    burial = _grab(r"Burial depth[^|]*\| ([\d.]+) m", grid)
    current = _grab(r"Grid current[^|]*\| ([\d.]+) kA", grid)
    grid_limit = _grab(r"Grid resistance limit: ([\d.]+) ohm", criteria)
    touch_limit = _grab(r"Touch voltage limit: ([\d.]+) V", criteria)

    area = length * width
    grid_resistance = rho * (
        1.0 / conductor + 1.0 / math.sqrt(20.0 * area) * (1.0 + 1.0 / (1.0 + burial * math.sqrt(20.0 / area)))
    )
    touch_voltage = current * 1000.0 * grid_resistance * 0.15

    assert grid_resistance == pytest.approx(gold["grid_resistance_ohm"], rel=0.01)
    assert grid_limit - grid_resistance == pytest.approx(gold["grid_resistance_margin_ohm"], rel=0.01, abs=0.002)
    assert touch_limit - touch_voltage == pytest.approx(gold["touch_voltage_margin_v"], rel=0.01, abs=1.0)

    if "allowable_bearing_kpa" not in gold:
        assert "standpipe readings pending" in groundwater
        return

    water_depth = _grab(r"Design groundwater level[^|]*\| ([\d.]+) m", groundwater)
    applied = _grab(r"Applied bearing pressure[^|]*\| ([\d.]+) kPa", foundation)
    cohesion = _grab(r"Effective cohesion: ([\d.]+) kPa", criteria)
    unit_weight = _grab(r"Total unit weight: ([\d.]+) kN/m3", criteria)
    footing_width = _grab(r"Footing width: ([\d.]+) m", criteria)
    embedment = _grab(r"Embedment depth: ([\d.]+) m", criteria)
    factor_of_safety = _grab(r"Bearing factor of safety: ([\d.]+)", criteria)
    nc, nq, ngamma = _bearing_factors(design_phi)
    if water_depth <= embedment:
        q_kpa = unit_weight * water_depth + (unit_weight - 9.81) * (embedment - water_depth)
        gamma_eff = unit_weight - 9.81
    elif water_depth < embedment + footing_width:
        q_kpa = unit_weight * embedment
        gamma_eff = (unit_weight - 9.81) + ((water_depth - embedment) / footing_width) * 9.81
    else:
        q_kpa = unit_weight * embedment
        gamma_eff = unit_weight
    ultimate = cohesion * nc * 1.3 + q_kpa * nq + gamma_eff * footing_width * 0.4 * ngamma
    allowable = ultimate / factor_of_safety

    assert allowable == pytest.approx(gold["allowable_bearing_kpa"], rel=0.01)
    assert allowable - applied == pytest.approx(gold["bearing_margin_kpa"], rel=0.01, abs=0.1)


@pytest.mark.parametrize("variant", ["clean", "bearing_fos_deficient"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_ground_evidence_recomputable_from_sources(variant)


def test_missing_groundwater_packet_recomputes_no_bearing_evidence() -> None:
    _assert_ground_evidence_recomputable_from_sources("missing_groundwater_level")


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
    instance_dir, _gold = _scaffold_variant(tmp_path, "bearing_fos_deficient")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
