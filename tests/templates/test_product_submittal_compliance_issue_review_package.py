# ABOUTME: Tests the SSC-15 review-first product submittal compliance package.
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
    / "product_submittal_compliance_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "carbon_equivalent_max",
    "carbon_equivalent_margin",
    "yield_strength_margin_mpa",
    "tensile_strength_margin_mpa",
    "certificate_coverage_count",
    "traceability_match_count",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_heat_number": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_certificate_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "heat_number_mismatch": {
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
    "carbon_equivalent_exceeds": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/submittal-manifest.md",
    "sources/mill-certificates.md",
    "sources/heat-traceability-table.md",
    "sources/product-application-schedule.md",
    "sources/deviation-register.md",
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


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "product-submittal-compliance-issue-review-package" in templates
    config = templates["product-submittal-compliance-issue-review-package"]
    assert config.meta.discipline == "mechanical"
    assert config.meta.category == "product-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    cev_values = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        cev_values.add(instance.ground_truth.get("carbon_equivalent_max", -1.0))

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(cev_values) >= 10, "Numeric parameters do not vary across seeds (min==max regression)"


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    a = sample_instance(config, engine.compute, "medium", seed=15, instance_index=0)
    b = sample_instance(config, engine.compute, "medium", seed=15, instance_index=0)

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

    assert gold["carbon_equivalent_margin"] > 0.0
    assert gold["yield_strength_margin_mpa"] > 0.0
    assert gold["tensile_strength_margin_mpa"] > 0.0
    assert gold["certificate_coverage_count"] >= 2.0
    assert gold["traceability_match_count"] >= 3.0


def test_carbon_equivalent_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("carbon_equivalent_exceeds")
    gold = instance.ground_truth

    assert gold["carbon_equivalent_margin"] < 0.0
    assert gold["yield_strength_margin_mpa"] > 0.0
    assert gold["tensile_strength_margin_mpa"] > 0.0


def test_missing_heat_number_omits_dependent_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_heat_number")

    for key in EVIDENCE_KEYS:
        if key == "certificate_coverage_count":
            continue
        assert key not in instance.ground_truth
    assert instance.ground_truth["certificate_coverage_count"] >= 2.0


def test_build_sources_produces_seven_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in ["SUB-15", "PROD-15", "HEAT-15-A", "HEAT-15-B", "CERT-15", "APP-15"]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["SUB-15-MAN-01", "CERT-15-MILL-01", "TRACE-15-HEAT-01", "CRIT-SSC15-001"]:
        assert doc_id in register


def test_missing_heat_number_sources_mark_pending_traceability() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_heat_number")
    sources = engine.build_sources(instance.all_params)

    schedule = sources["sources/product-application-schedule.md"]
    assert "traceability pending" in schedule.lower()

    clean_params = dict(instance.all_params)
    clean_params["packet_variant"] = "clean"
    clean_schedule = engine.build_sources(clean_params)["sources/product-application-schedule.md"]
    assert clean_schedule != schedule


def test_missing_heat_packet_does_not_close_heat_coverage_or_traceability_comments() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_heat_number")

    criteria = engine.build_sources(instance.all_params)["sources/criteria-comments.md"]

    assert "Confirm mill certificates cover all applied heats." not in criteria
    assert "Confirm heat traceability table matches application rows." not in criteria


def test_stale_certificate_sources_have_revision_mismatch() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("stale_certificate_revision")
    sources = engine.build_sources(instance.all_params)

    register = sources["sources/document-register.md"]
    certificates = sources["sources/mill-certificates.md"]

    assert "CERT-15-MILL-01 | Mill certificates | Rev B" in register
    assert "CERT-15-MILL-01 (Rev A)" in certificates


def test_sources_print_exact_engine_values() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)
    criteria = sources["sources/criteria-comments.md"]

    assert re.search(r"Carbon equivalent limit: \d+\.\d{3}", criteria)
    assert re.search(r"Minimum yield strength: \d+ MPa", criteria)


def _grab(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    assert match, f"Pattern not found: {pattern}"
    return float(match.group(1))


def _certificate_rows(certificates: str) -> dict[str, dict[str, float]]:
    rows: dict[str, dict[str, float]] = {}
    for line in certificates.splitlines():
        if not line.startswith("| HEAT-15-"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows[cells[0]] = {
            "c": float(cells[1]),
            "mn": float(cells[2]),
            "cr": float(cells[3]),
            "mo": float(cells[4]),
            "v": float(cells[5]),
            "ni": float(cells[6]),
            "cu": float(cells[7]),
            "yield": float(cells[8]),
            "tensile": float(cells[9]),
        }
    return rows


def _application_heats(schedule: str) -> list[str]:
    heats = []
    for line in schedule.splitlines():
        if not line.startswith("| APP-15-"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        heat = cells[3]
        if "pending" not in heat.lower():
            heats.append(heat)
    return heats


def _cev(row: dict[str, float]) -> float:
    return row["c"] + row["mn"] / 6.0 + (row["cr"] + row["mo"] + row["v"]) / 5.0 + (row["ni"] + row["cu"]) / 15.0


def _assert_submittal_evidence_recomputable_from_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    certificates = sources["sources/mill-certificates.md"]
    schedule = sources["sources/product-application-schedule.md"]
    criteria = sources["sources/criteria-comments.md"]

    if "carbon_equivalent_max" not in gold:
        assert "traceability pending" in schedule.lower()
        return

    cert_rows = _certificate_rows(certificates)
    heats = _application_heats(schedule)
    selected = [cert_rows[heat] for heat in heats]
    cev_values = [_cev(row) for row in selected]
    yield_values = [row["yield"] for row in selected]
    tensile_values = [row["tensile"] for row in selected]

    cev_limit = _grab(r"Carbon equivalent limit: ([\d.]+)", criteria)
    required_yield = _grab(r"Minimum yield strength: ([\d.]+) MPa", criteria)
    required_tensile = _grab(r"Minimum tensile strength: ([\d.]+) MPa", criteria)

    assert max(cev_values) == pytest.approx(gold["carbon_equivalent_max"], rel=0.01, abs=0.002)
    assert cev_limit - max(cev_values) == pytest.approx(gold["carbon_equivalent_margin"], rel=0.01, abs=0.002)
    assert min(yield_values) - required_yield == pytest.approx(gold["yield_strength_margin_mpa"], rel=0.01)
    assert min(tensile_values) - required_tensile == pytest.approx(gold["tensile_strength_margin_mpa"], rel=0.01)
    assert len(set(cert_rows) & set(heats)) == pytest.approx(gold["certificate_coverage_count"])
    assert len(heats) == pytest.approx(gold["traceability_match_count"])


@pytest.mark.parametrize("variant", ["clean", "carbon_equivalent_exceeds"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    _assert_submittal_evidence_recomputable_from_sources(variant)


def test_missing_heat_packet_recomputes_no_dependent_evidence() -> None:
    _assert_submittal_evidence_recomputable_from_sources("missing_heat_number")


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
    instance_dir, _gold = _scaffold_variant(tmp_path, "carbon_equivalent_exceeds")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
