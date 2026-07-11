# ABOUTME: Tests the SSC-03 drainage model-run provenance issue-review package.
# ABOUTME: Covers source-only closure, temporal transitions, variants, and stage-gated verification.

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.task_world_templates.catalogue import get_template as get_composite_template
from aec_bench.templates.registry import discover_templates, load_engine_module, load_template

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "civil"
    / "drainage_model_run_provenance_issue_review_package"
)

STATUS_KEYS = [f"prv_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "all_input_revisions_match_score",
    "scenario_match_score",
    "report_run_match_score",
    "continuity_error_percent",
    "continuity_margin_percent",
    "report_peak_flow_m3_s",
    "memo_peak_flow_m3_s",
    "peak_flow_propagation_delta_m3_s",
    "report_max_hgl_m_ahd",
    "memo_max_hgl_m_ahd",
    "hgl_propagation_delta_m",
]

VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {
        "flips": {},
        "run": 0.0,
        "report": 0.0,
        "claim": 0.0,
        "readiness": 0.0,
        "findings": 0.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "missing_manifest_catchment_revision": {
        "flips": {"prv_03_status": 3.0},
        "run": 2.0,
        "report": 2.0,
        "claim": 2.0,
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_catchment_revision": {
        "flips": {"prv_03_status": 1.0},
        "run": 1.0,
        "report": 1.0,
        "claim": 1.0,
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "report_run_id_mismatch": {
        "flips": {"prv_04_status": 1.0},
        "run": 0.0,
        "report": 1.0,
        "claim": 1.0,
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "continuity_limit_exceeded": {
        "flips": {"prv_04_status": 1.0},
        "run": 1.0,
        "report": 1.0,
        "claim": 1.0,
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "scenario_copy_forward": {
        "flips": {"prv_05_status": 1.0},
        "run": 1.0,
        "report": 1.0,
        "claim": 1.0,
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "downstream_memo_stale_report": {
        "flips": {"prv_06_status": 1.0},
        "run": 0.0,
        "report": 0.0,
        "claim": 1.0,
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "open_critical_comment": {
        "flips": {"prv_07_status": 1.0},
        "run": 0.0,
        "report": 0.0,
        "claim": 0.0,
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "minor_open_comment_carried": {
        "flips": {},
        "run": 0.0,
        "report": 0.0,
        "claim": 0.0,
        "readiness": 1.0,
        "findings": 0.0,
        "requests": 0.0,
        "carried": 1.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/catchment-basis.md",
    "sources/rainfall-basis.md",
    "sources/network-model-config.md",
    "sources/model-input-manifest.md",
    "sources/run-register.md",
    "sources/hydraulic-model-report.md",
    "sources/drainage-design-memo.md",
    "sources/criteria-comments.md",
]


def _load() -> tuple:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    return config, template_dir, engine


def _instance_for_variant(variant: str, max_seeds: int = 2000):
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
    reward_dir = tmp_path / input_file.stem
    reward_file = reward_dir / "reward.json"
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
    details = json.loads((reward_dir / "details.json").read_text(encoding="utf-8"))
    return reward, details


def _extract_json_block(text: str) -> dict:
    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    assert matches, "No fenced JSON block found"
    return json.loads(matches[-1])


def _replace_json_block(text: str, payload: dict) -> str:
    block = "```json\n" + json.dumps(payload, indent=2) + "\n```"
    return re.sub(r"```json\s*\n.*?\n\s*```", lambda _match: block, text, count=1, flags=re.DOTALL)


def _grab(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    assert match, f"Pattern not found: {pattern}"
    return float(match.group(1))


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "drainage-model-run-provenance-issue-review-package" in templates
    config = templates["drainage-model-run-provenance-issue-review-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "drainage-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_composite_catalogue_models_the_temporal_provenance_chain() -> None:
    template = get_composite_template("drainage-model-run-provenance-issue-review-package")

    assert [stage.id for stage in template.stages] == [
        "source_inventory",
        "input_authority",
        "run_provenance",
        "claim_propagation",
        "closure_decision",
    ]
    template_refs = {ref for stage in template.stages for ref in stage.template_refs}
    assert "swmm-hec-report-source-policy-package" in template_refs
    assert "detention-outlet-hgl-package" in template_refs
    assert {handoff.id for handoff in template.handoffs}.issuperset(
        {
            "governing_input_set",
            "run_applicability",
            "report_applicability",
            "design_claim_support",
            "readiness_decision",
        }
    )


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    peak_flows = set()
    for seed in range(60):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        peak_flows.add(instance.ground_truth["report_peak_flow_m3_s"])

    assert len(variants) >= 5, "Variant distribution collapsed"
    assert len(peak_flows) >= 10, "Numeric parameters do not vary across seeds"


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    first = sample_instance(config, engine.compute, "medium", seed=23, instance_index=0)
    second = sample_instance(config, engine.compute, "medium", seed=23, instance_index=0)

    assert first.all_params == second.all_params
    assert first.ground_truth == second.ground_truth


@pytest.mark.parametrize("variant", sorted(VARIANT_EXPECTATIONS))
def test_variant_gold_statuses_and_transitions(variant: str) -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    expected = VARIANT_EXPECTATIONS[variant]

    for key in STATUS_KEYS:
        assert gold[key] == expected["flips"].get(key, 0.0)

    assert gold["run_applicability_code"] == expected["run"]
    assert gold["report_applicability_code"] == expected["report"]
    assert gold["design_claim_support_code"] == expected["claim"]
    assert gold["readiness_code"] == expected["readiness"]
    assert gold["required_findings_count"] == expected["findings"]
    assert gold["required_information_requests_count"] == expected["requests"]
    assert gold["required_carried_actions_count"] == expected["carried"]


def test_missing_manifest_revision_omits_only_revision_match_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_manifest_catchment_revision")

    assert "all_input_revisions_match_score" not in instance.ground_truth
    for key in set(EVIDENCE_KEYS) - {"all_input_revisions_match_score"}:
        assert key in instance.ground_truth


def test_each_defect_variant_flips_one_matrix_item() -> None:
    for variant, expected in VARIANT_EXPECTATIONS.items():
        if variant in {"clean", "minor_open_comment_carried"}:
            continue
        assert len(expected["flips"]) == 1, f"{variant} is not a one-item matrix defect"


def test_build_sources_produces_temporal_packet() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)
    joined = "\n".join(sources.values())
    for token in [
        "SITE-03",
        "CATCH-03-A",
        "STORM-03-A",
        "MANIFEST-03-042",
        "RUN-03-042",
        "RUN-03-041",
        "REPORT-03-042",
        "MEMO-03-DESIGN-01",
        "CRIT-SSC03-001",
    ]:
        assert token in joined

    run_register = sources["sources/run-register.md"]
    assert "governing candidate" in run_register
    assert "superseded" in run_register


def test_source_owned_contract_defines_binary_revision_identity() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    criteria = " ".join(engine.build_sources(instance.all_params)["sources/criteria-comments.md"].lower().split())

    assert "all_input_revisions_match_score" in criteria
    assert "all four governing input revisions" in criteria
    assert "1 only when" in criteria
    assert "0 when any" in criteria


def test_matrix_separates_integrity_checks_from_transition_applicability() -> None:
    instruction = (TEMPLATE_DIR / "instruction.md").read_text(encoding="utf-8").lower()

    assert "intrinsic report acceptance" in instruction
    assert "upstream input-governance state is recorded in the transition decision" in instruction
    assert "citation and value-propagation integrity" in instruction
    assert "whether the cited evidence governs is recorded in the transition decision" in instruction


def test_variant_sources_change_only_the_intended_condition() -> None:
    _config, _template_dir, engine, clean_instance = _instance_for_variant("clean")
    clean_sources = engine.build_sources(clean_instance.all_params)

    cases = {
        "stale_catchment_revision": ("sources/model-input-manifest.md", "Rev C"),
        "missing_manifest_catchment_revision": ("sources/model-input-manifest.md", "pending confirmation"),
        "report_run_id_mismatch": ("sources/hydraulic-model-report.md", "RUN-03-041"),
        "scenario_copy_forward": ("sources/model-input-manifest.md", "STORM-03-B"),
        "downstream_memo_stale_report": ("sources/drainage-design-memo.md", "REPORT-03-041"),
        "open_critical_comment": ("sources/criteria-comments.md", "remains open"),
    }
    for variant, (path, marker) in cases.items():
        variant_params = dict(clean_instance.all_params)
        variant_params["packet_variant"] = variant
        sources = engine.build_sources(variant_params)
        assert marker in sources[path]
        changed = {name for name in SOURCE_FILES if sources[name] != clean_sources[name]}
        assert changed == {path}, f"{variant} changed unexpected files: {changed}"


def test_continuity_variant_changes_only_report_and_exceeds_limit() -> None:
    _config, _template_dir, engine, clean_instance = _instance_for_variant("clean")
    clean_sources = engine.build_sources(clean_instance.all_params)
    failed_params = dict(clean_instance.all_params)
    failed_params["packet_variant"] = "continuity_limit_exceeded"
    failed_sources = engine.build_sources(failed_params)
    failed_gold = engine.compute(**failed_params)

    changed = {name for name in SOURCE_FILES if failed_sources[name] != clean_sources[name]}
    assert changed == {"sources/hydraulic-model-report.md"}
    assert failed_gold["continuity_margin_percent"] < 0.0


@pytest.mark.parametrize("variant", sorted(VARIANT_EXPECTATIONS))
def test_evidence_recomputable_from_rendered_sources(variant: str) -> None:
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    register = sources["sources/document-register.md"]
    manifest = sources["sources/model-input-manifest.md"]
    report = sources["sources/hydraulic-model-report.md"]
    memo = sources["sources/drainage-design-memo.md"]
    criteria = sources["sources/criteria-comments.md"]

    current_catchment_rev = re.search(r"CATCH-03-BASIS-01[^\n]*\| (Rev [A-Z]) \| current", register)
    manifest_catchment_rev = re.search(r"Catchment basis revision \| (Rev [A-Z])", manifest)
    if variant == "missing_manifest_catchment_revision":
        assert manifest_catchment_rev is None
        assert "pending confirmation" in manifest
        assert "all_input_revisions_match_score" not in gold
    else:
        assert current_catchment_rev and manifest_catchment_rev
        revision_match = float(current_catchment_rev.group(1) == manifest_catchment_rev.group(1))
        assert revision_match == gold["all_input_revisions_match_score"]

    governing_storm = re.search(r"Governing design storm \| ([A-Z0-9-]+)", criteria)
    manifest_storm = re.search(r"Design storm \| ([A-Z0-9-]+)", manifest)
    assert governing_storm and manifest_storm
    assert float(governing_storm.group(1) == manifest_storm.group(1)) == gold["scenario_match_score"]

    registered_run = re.search(
        r"\| (RUN-[0-9-]+) \| MANIFEST-03-042 \| REPORT-03-042 \|",
        sources["sources/run-register.md"],
    )
    report_run = re.search(r"Run ID: (RUN-[0-9-]+)", report)
    assert registered_run and report_run
    assert float(registered_run.group(1) == report_run.group(1)) == gold["report_run_match_score"]

    continuity = _grab(r"Continuity error \| ([\d.]+) percent", report)
    maximum = _grab(r"Maximum continuity error \| ([\d.]+) percent", criteria)
    assert continuity == pytest.approx(gold["continuity_error_percent"], abs=0.01)
    assert maximum - continuity == pytest.approx(gold["continuity_margin_percent"], abs=0.01)

    report_peak = _grab(r"Peak flow \| ([\d.]+) m3/s", report)
    memo_peak = _grab(r"Adopted peak flow \| ([\d.]+) m3/s", memo)
    report_hgl = _grab(r"Maximum HGL \| ([\d.]+) m AHD", report)
    memo_hgl = _grab(r"Adopted maximum HGL \| ([\d.]+) m AHD", memo)
    assert report_peak == pytest.approx(gold["report_peak_flow_m3_s"], abs=0.01)
    assert memo_peak == pytest.approx(gold["memo_peak_flow_m3_s"], abs=0.01)
    assert abs(memo_peak - report_peak) == pytest.approx(gold["peak_flow_propagation_delta_m3_s"], abs=0.01)
    assert report_hgl == pytest.approx(gold["report_max_hgl_m_ahd"], abs=0.01)
    assert memo_hgl == pytest.approx(gold["memo_max_hgl_m_ahd"], abs=0.01)
    assert abs(memo_hgl - report_hgl) == pytest.approx(gold["hgl_propagation_delta_m"], abs=0.01)


def test_instruction_and_system_prompt_are_variant_blind() -> None:
    instruction = (TEMPLATE_DIR / "instruction.md").read_text(encoding="utf-8")
    system_prompt = (TEMPLATE_DIR / "system_prompt.md").read_text(encoding="utf-8")
    combined = f"{instruction}\n{system_prompt}".lower()

    for variant in VARIANT_EXPECTATIONS:
        assert variant.replace("_", " ") not in combined
        assert variant not in combined
    assert not re.search(r"\b\d+\.\d+\b", combined), "Prompt contains an engineering numeric value"
    assert "do not invent missing values" in combined


def test_scaffolded_instance_layout(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")

    for rel in SOURCE_FILES:
        assert (instance_dir / "environment" / rel).exists()
    dockerfile = (instance_dir / "environment" / "Dockerfile").read_text(encoding="utf-8")
    for rel in SOURCE_FILES:
        assert f"COPY {rel} /workspace/{rel}" in dockerfile
    assert not list(instance_dir.glob("environment/*_calc.py"))

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
    for item in [f"PRV-0{i}" for i in range(1, 10)]:
        assert item in instruction


@pytest.mark.parametrize("variant", sorted(VARIANT_EXPECTATIONS))
def test_golden_pass_scores_one(tmp_path: Path, variant: str) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, variant)
    reward, _details = _run_verifier(instance_dir, instance_dir / "tests" / "fixtures" / "golden_pass.md", tmp_path)
    assert reward == 1.0


@pytest.mark.parametrize("variant", ["clean", "stale_catchment_revision", "downstream_memo_stale_report"])
def test_fluent_unsafe_memo_scores_low(tmp_path: Path, variant: str) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, variant)
    reward, _details = _run_verifier(instance_dir, instance_dir / "tests" / "fixtures" / "golden_fail.md", tmp_path)
    assert reward <= 0.5


def test_verifier_localizes_broken_provenance_evidence(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")
    golden = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    text = golden.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["computed_evidence"]["report_run_match_score"] = 0.0
    mutated = tmp_path / "broken-provenance.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["matrix"]["items"]["PRV-04"] == 0.0
    assert details["gates"]["evidence"]["keys"]["report_run_match_score"] == 0.0


def test_verifier_localizes_broken_transition(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "stale_catchment_revision")
    golden = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    text = golden.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["transition_decision"]["model_run"] = "governing"
    mutated = tmp_path / "broken-transition.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["transition"]["states"]["model_run"] == 0.0


def test_verifier_rejects_ready_decision_for_unsupported_claim(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "downstream_memo_stale_report")
    golden = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    text = golden.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "broken-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0


def test_verifier_rejects_finding_linked_to_passing_item(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")
    golden = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    text = golden.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["findings"].append(
        {
            "item": "PRV-03",
            "severity": "critical",
            "source_id": "MANIFEST-03-042",
            "object_id": "RUN-03-042",
            "consequence": "Contradicts the passing matrix status.",
            "action": "Resolve the contradictory review record.",
        }
    )
    mutated = tmp_path / "contradictory-finding.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["linkage"]["checks"]["fail_findings_linked"] == 0.0


@pytest.mark.parametrize(
    "statement",
    [
        (
            "This review is conducted against a task-owned synthetic source packet assembled for independent "
            "provenance checking purposes only. It does not constitute or imply authority approval of any design "
            "or model output, acceptance of any project evidence into a formal project register, demonstration of "
            "compliance with any standard or regulatory requirement, hardening or certification of the source "
            "packet, readiness of any executable verifier or automated checking tool, or benchmark readiness of "
            "any kind."
        ),
        (
            "This review pertains to a task-owned synthetic source packet prepared for evaluation of the provenance "
            "review framework. This review does not claim or imply authority approval by regulatory, design, or "
            "project bodies; that this packet represents accepted project evidence or baseline documentation; full "
            "compliance with drainage engineering standards or hydraulic design codes; that the source pack is "
            "hardened for persistent reuse; that the hydraulic model or outputs are verified as executable or "
            "independently reproducible; or that this packet establishes a benchmark standard for other model-run "
            "reviews."
        ),
    ],
)
def test_verifier_accepts_equivalent_complete_claim_boundaries(tmp_path: Path, statement: str) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")
    golden = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    text = golden.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["claim_boundary_statement"] = statement
    mutated = tmp_path / f"equivalent-claim-{len(statement)}.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)

    assert reward == 1.0
    assert details["gates"]["identity_claims"]["checks"]["claim_boundary"] == 1.0


def test_verifier_writes_details_next_to_reward(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")
    golden = instance_dir / "tests" / "fixtures" / "golden_pass.md"
    reward, details = _run_verifier(instance_dir, golden, tmp_path)

    assert reward == 1.0
    assert set(details["gates"]) == {
        "matrix",
        "evidence",
        "provenance",
        "transition",
        "linkage",
        "readiness",
        "identity_claims",
    }
