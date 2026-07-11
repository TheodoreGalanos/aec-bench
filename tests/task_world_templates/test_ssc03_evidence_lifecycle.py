# ABOUTME: Tests the runnable SSC-03 staged evidence-lifecycle companion.
# ABOUTME: Covers package materialisation, continuity verification, disclosure, and task-run integration.

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    branch_evidence_lifecycle,
    build_evidence_lifecycle_task_run_resolver,
    prepare_evidence_checkpoint,
    run_evidence_lifecycle,
    submit_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_lifecycle_local import run_local_evidence_lifecycle_session
from aec_bench.meta_harness.logic_profile import evaluate_logic_profile
from aec_bench.task_world_templates.catalogue import get_template, list_templates
from aec_bench.task_world_templates.lifecycles import registered_lifecycle_template_ids
from aec_bench.task_world_templates.lifecycles.ssc03_drainage_model import (
    GATE_IDS,
    materialize_ssc03_evidence_lifecycle,
    verify_ssc03_evidence_lifecycle,
)
from aec_bench.task_world_templates.materializer import materialize_template_lifecycle


def test_ssc03_lifecycle_is_additive_to_single_episode_template() -> None:
    single_episode = get_template("drainage-model-run-provenance-issue-review-package")
    lifecycle = get_template("drainage-model-evidence-lifecycle-review")

    assert single_episode.evidence_lifecycle is None
    assert lifecycle.evidence_lifecycle is not None
    assert [checkpoint.checkpoint_id for checkpoint in lifecycle.evidence_lifecycle.checkpoints] == [
        "initial_review",
        "response_review",
        "closeout_review",
    ]
    assert lifecycle.world_id != single_episode.world_id


def test_every_lifecycle_template_has_one_executable_registration() -> None:
    declared = {template.template_id for template in list_templates() if template.evidence_lifecycle is not None}

    assert registered_lifecycle_template_ids() == declared


def test_ssc03_declared_verifier_gates_match_executable_gates() -> None:
    template = get_template("drainage-model-evidence-lifecycle-review")

    assert tuple(gate.id for gate in template.verifier_gates) == GATE_IDS


def test_generic_materializer_uses_the_supplied_template_contract(tmp_path: Path) -> None:
    template = get_template("drainage-model-evidence-lifecycle-review").model_copy(
        update={"summary": "Caller-owned lifecycle summary."}
    )

    package = materialize_template_lifecycle(template, tmp_path / "package")

    assert _load_json(package / "template.json")["summary"] == "Caller-owned lifecycle summary."


def test_repeated_lifecycle_materialization_is_byte_identical(tmp_path: Path) -> None:
    first = materialize_ssc03_evidence_lifecycle(tmp_path / "first")
    second = materialize_ssc03_evidence_lifecycle(tmp_path / "second")

    first_files = {
        str(path.relative_to(first)): path.read_bytes() for path in sorted(first.rglob("*")) if path.is_file()
    }
    second_files = {
        str(path.relative_to(second)): path.read_bytes() for path in sorted(second.rglob("*")) if path.is_file()
    }
    assert first_files == second_files


def test_generic_materializer_revalidates_unchecked_template_copies(tmp_path: Path) -> None:
    template = get_template("drainage-model-evidence-lifecycle-review")
    assert template.evidence_lifecycle is not None
    unchecked = template.model_copy(
        update={
            "evidence_lifecycle": template.evidence_lifecycle.model_copy(
                update={"world_id": "aec.task_world.composite.wrong-world"}
            )
        }
    )

    with pytest.raises(ValueError, match="world_id must match"):
        materialize_template_lifecycle(unchecked, tmp_path / "package")


def test_materialized_package_keeps_future_releases_outside_agent_workspace(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")

    assert (package / "lifecycle.json").exists()
    assert (package / "releases" / "initial_review" / "document-register.md").exists()
    assert (package / "releases" / "response_review" / "model-input-manifest-rev-b.md").exists()
    assert (package / "releases" / "closeout_review" / "drainage-design-memo-rev-e.md").exists()
    assert (package / "hidden" / "gold-submissions.json").exists()
    assert not (package / "workspace").exists()


def test_checkpoint_instruction_publishes_review_and_json_contract_without_answers(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    instruction = (package / "instructions" / "initial_review.md").read_text(encoding="utf-8")
    normalized_instruction = " ".join(instruction.split())

    assert "PRV-01 | Packet completeness" in instruction
    assert "PRV-09 | Claim boundary" in instruction
    assert '"evidence_refs": ["DOC-ID Rev X"]' in instruction
    assert '"PRV-01": "pass|fail|not_applicable|insufficient_data"' in instruction
    assert '"finding_id": "F-PRVXX-NNN"' in instruction
    assert '"decision_id": "D-PRVXX-NNN"' in instruction
    assert "Decision-bearing items are PRV-01 through PRV-07" in instruction
    assert "Sequence finding and decision IDs independently within each PRV item" in normalized_instruction
    assert "only the released sources directly necessary" in instruction
    assert "F-PRV03-001" not in instruction
    assert '"PRV-03": "fail"' not in instruction


def test_initial_packet_registers_run_and_comment_action_evidence(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    register = (package / "releases" / "initial_review" / "document-register.md").read_text(encoding="utf-8")
    comments = (package / "releases" / "initial_review" / "comment-action-register.md").read_text(encoding="utf-8")
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    assert "RUN-03-REGISTER-01 | Rev E | current" in register
    assert "COMMENT-03-REGISTER-01 | Rev A | current" in register
    assert "Open critical comments: 0" in comments
    assert "Carried actions: 0" in comments
    assert "COMMENT-03-REGISTER-01 Rev A" in gold["initial_review"]["evidence_refs"]


def test_each_later_release_registers_its_current_document_set(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    response_register = (package / "releases" / "response_review" / "document-register-rev-f.md").read_text(
        encoding="utf-8"
    )
    closeout_register = (package / "releases" / "closeout_review" / "document-register-rev-g.md").read_text(
        encoding="utf-8"
    )
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    assert "MANIFEST-03-042 | Rev B | current submission" in response_register
    assert "RUN-03-REGISTER-01 | Rev F | current" in response_register
    assert "REPORT-03-043 | Rev A | current submission" in response_register
    assert "MEMO-03-DESIGN-01 | Rev E | current submission" in closeout_register
    assert "RESP-03-CLOSEOUT-01 | Rev A | current response" in closeout_register
    assert "REG-03 Rev F" in gold["response_review"]["evidence_refs"]
    assert "REG-03 Rev G" in gold["closeout_review"]["evidence_refs"]


def test_criteria_owns_matrix_localization_and_transition_propagation(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    criteria = (package / "releases" / "initial_review" / "criteria-comments.md").read_text(encoding="utf-8")

    assert "PRV-03 owns manifest input-revision equality" in criteria
    assert "PRV-05 owns rainfall-basis and design-storm identity" in criteria
    assert "Do not duplicate a PRV-03 revision mismatch under PRV-05" in criteria
    assert "A report may govern in the transition only when its parent run governs" in criteria

    instruction = (package / "instructions" / "initial_review.md").read_text(encoding="utf-8")
    normalized_instruction = " ".join(instruction.split())
    assert "PRV-02 owns the stable catchment, rainfall, and criteria identity" in normalized_instruction
    assert "PRV-05 owns scenario propagation into the reviewed manifest" in normalized_instruction


def test_gold_decision_register_preserves_unaffected_and_supersedes_affected(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    initial = {item["decision_id"]: item for item in gold["initial_review"]["accepted_decisions"]}
    response = {item["decision_id"]: item for item in gold["response_review"]["accepted_decisions"]}
    closeout = {item["decision_id"]: item for item in gold["closeout_review"]["accepted_decisions"]}

    for decision_id in ["D-PRV02-001", "D-PRV07-001"]:
        assert response[decision_id] == initial[decision_id]
        assert closeout[decision_id] == initial[decision_id]

    assert response["D-PRV01-001"]["superseded_by"] == "D-PRV01-002"
    assert response["D-PRV01-002"]["status"] == "accepted"
    assert closeout["D-PRV01-002"]["superseded_by"] == "D-PRV01-003"
    assert closeout["D-PRV01-003"]["status"] == "accepted"
    assert "D-PRV03-001" not in initial
    assert response["D-PRV03-001"]["status"] == "accepted"
    assert closeout["D-PRV03-001"] == response["D-PRV03-001"]
    assert response["D-PRV04-001"]["status"] == "superseded"
    assert response["D-PRV04-001"]["superseded_by"] == "D-PRV04-002"
    assert response["D-PRV04-002"]["status"] == "accepted"
    assert response["D-PRV05-001"]["superseded_by"] == "D-PRV05-002"
    assert response["D-PRV05-002"]["status"] == "accepted"
    assert closeout["D-PRV05-002"] == response["D-PRV05-002"]
    assert response["D-PRV06-001"]["status"] == "superseded"
    assert response["D-PRV06-001"]["superseded_by"] is None
    assert closeout["D-PRV06-001"]["superseded_by"] == "D-PRV06-002"
    assert closeout["D-PRV06-002"]["status"] == "accepted"


def test_gold_uses_released_run_register_document_ids_for_run_lineage(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    assert "RUN-03-REGISTER-01 Rev E" in gold["initial_review"]["evidence_refs"]
    assert "RUN-03-042" not in gold["initial_review"]["evidence_refs"]
    assert "RUN-03-REGISTER-01 Rev F" in gold["response_review"]["evidence_refs"]
    response_decisions = {item["decision_id"]: item for item in gold["response_review"]["accepted_decisions"]}
    assert response_decisions["D-PRV04-002"]["basis_refs"] == [
        "RUN-03-REGISTER-01 Rev F",
        "REPORT-03-043 Rev A",
    ]


def test_golden_lifecycle_scores_one_without_bypassing_parent_agentic_review(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    def resolve(context: dict) -> dict:
        _write_json(Path(context["submission_path"]), gold[context["checkpoint_id"]])
        return {"status": "completed", "checkpoint_id": context["checkpoint_id"]}

    resolver = build_evidence_lifecycle_task_run_resolver(
        package_dir=package,
        run_dir=run_dir,
        episode_resolver=resolve,
        verifier=verify_ssc03_evidence_lifecycle,
    )
    task_run = resolver({"process_id": "process.ssc03"})
    world = get_template("drainage-model-evidence-lifecycle-review").compile_task_world_payload()
    evaluation = evaluate_logic_profile(world["logic_profile"], task_run["evidence"])

    assert task_run["evidence"]["score"] == {"reward": 1.0, "passed": True}
    assert task_run["evidence"]["verification"]["overall"] == "pass"
    semantic = task_run["evidence"]["verification"]["semantic_metrics"]
    assert semantic["initial"]["accuracy"] == 1.0
    assert semantic["aggregate"]["acquisition"] == 1.0
    assert semantic["aggregate"]["update_precision"] == 1.0
    assert semantic["aggregate"]["update_recall"] == 1.0
    assert semantic["aggregate"]["retention"] == 1.0
    assert semantic["aggregate"]["interference_count"] == 0
    assert {item["status"] for item in evaluation.closure_results} == {"certified"}
    assert evaluation.overall_status == "review_required"


def test_semantic_metrics_separate_missed_acquisition_from_existing_gate_reward(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["review_matrix"]["PRV-03"] = "fail"

    package, run_dir = _run_with_mutation(tmp_path, "response_review", mutate)

    result = verify_ssc03_evidence_lifecycle(package, run_dir)
    semantic = result["semantic_metrics"]
    initial_to_response = semantic["transitions"][0]

    assert result["gates"]["checkpoint_contract"]["passed"] is False
    assert initial_to_response["from_checkpoint_id"] == "initial_review"
    assert initial_to_response["to_checkpoint_id"] == "response_review"
    assert initial_to_response["acquired_update_count"] < initial_to_response["expected_update_count"]
    assert initial_to_response["acquisition"] < 1.0
    assert semantic["aggregate"]["update_recall"] < 1.0


def test_verifier_localizes_premature_evidence_reference(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["evidence_refs"].append("MEMO-03-DESIGN-01 Rev E")

    package, run_dir = _run_with_mutation(tmp_path, "initial_review", mutate)

    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["reward"] < 1.0
    assert result["gates"]["staged_disclosure"]["passed"] is False
    assert 0.0 < result["gates"]["staged_disclosure"]["score"] < 1.0
    assert result["gates"]["finding_continuity"]["passed"] is True


def test_verifier_localizes_structured_evidence_reference_instead_of_crashing(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["evidence_refs"] = [{"id": "REG-03 Rev E", "source": "document-register.md"}]

    package, run_dir = _run_with_mutation(tmp_path, "initial_review", mutate)

    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["reward"] < 1.0
    assert result["gates"]["staged_disclosure"]["passed"] is False
    assert "initial_review:evidence_refs_shape" in result["gates"]["staged_disclosure"]["failures"]


def test_verifier_requires_evidence_backed_finding_closure(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        finding = next(item for item in payload["findings"] if item["finding_id"] == "F-PRV03-001")
        finding["closure_evidence"].remove("MANIFEST-03-042 Rev B")

    package, run_dir = _run_with_mutation(tmp_path, "response_review", mutate)

    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["reward"] < 1.0
    assert result["gates"]["closure_evidence"]["passed"] is False
    assert 0.0 < result["gates"]["closure_evidence"]["score"] < 1.0
    assert "response_review:F-PRV03-001:closure_evidence" in result["gates"]["closure_evidence"]["failures"]


def test_verifier_requires_closure_request_response_lineage(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        request = next(item for item in payload["closure_evidence_requests"] if item["request_id"] == "CER-001")
        request["response_refs"].remove("MANIFEST-03-042 Rev B")

    package, run_dir = _run_with_mutation(tmp_path, "response_review", mutate)

    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["reward"] < 1.0
    assert result["gates"]["closure_evidence"]["passed"] is False
    assert "response_review:CER-001:response_refs" in result["gates"]["closure_evidence"]["failures"]


def test_semantic_metrics_accept_verifier_valid_closure_reference_supersets(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        finding = next(item for item in payload["findings"] if item["finding_id"] == "F-PRV03-001")
        finding["closure_evidence"].append("RUN-03-REGISTER-01 Rev F")
        request = next(item for item in payload["closure_evidence_requests"] if item["request_id"] == "CER-001")
        request["response_refs"].append("RUN-03-REGISTER-01 Rev F")

    package, run_dir = _run_with_mutation(tmp_path, "response_review", mutate)

    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["overall"] == "pass"
    assert result["gates"]["closure_evidence"]["passed"] is True
    assert result["semantic_metrics"]["aggregate"]["acquisition"] == 1.0
    assert result["semantic_metrics"]["aggregate"]["update_precision"] == 1.0
    assert result["semantic_metrics"]["aggregate"]["retention"] == 1.0


def test_continuity_and_readiness_gates_score_single_errors_fractionally(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    gold["initial_review"]["findings"][0]["opened_at"] = "response_review"
    gold["response_review"]["readiness_decision"] = "ready_to_issue"
    run_dir = tmp_path / "run"

    _run_payloads(package, run_dir, gold)
    gates = verify_ssc03_evidence_lifecycle(package, run_dir)["gates"]

    assert gates["finding_continuity"]["passed"] is False
    assert 0.0 < gates["finding_continuity"]["score"] < 1.0
    assert gates["final_readiness"]["passed"] is False
    assert 0.0 < gates["final_readiness"]["score"] < 1.0


def test_verifier_accepts_equivalent_supersession_reason_prose(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        decision = next(item for item in payload["accepted_decisions"] if item["decision_id"] == "D-PRV04-001")
        decision["supersession_reason"] = "The later registered run and report replace this evidence object."

    package, run_dir = _run_with_mutation(tmp_path, "response_review", mutate)

    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["gates"]["accepted_decision_preservation"]["passed"] is True


def test_verifier_accepts_allowed_decision_evidence_and_preserves_it_across_checkpoints(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    for checkpoint_id in ("initial_review", "response_review", "closeout_review"):
        decision = next(
            item for item in gold[checkpoint_id]["accepted_decisions"] if item["decision_id"] == "D-PRV04-001"
        )
        decision["basis_refs"].append("CRIT-SSC03-001 Rev C")

    _run_payloads(package, run_dir, gold)
    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["gates"]["accepted_decision_preservation"]["passed"] is True


def test_verifier_accepts_stable_prv02_basis_with_one_registered_identity_reference(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    for checkpoint_id in ("initial_review", "response_review", "closeout_review"):
        decision = next(
            item for item in gold[checkpoint_id]["accepted_decisions"] if item["decision_id"] == "D-PRV02-001"
        )
        decision["basis_refs"].append("REG-03 Rev E")

    _run_payloads(package, run_dir, gold)
    gate = verify_ssc03_evidence_lifecycle(package, run_dir)["gates"]["accepted_decision_preservation"]

    assert gate["passed"] is True


def test_verifier_accepts_alternative_complete_prv03_basis(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    alternative = ["MANIFEST-03-042 Rev B", "CATCH-03-BASIS-01 Rev D", "RAIN-03-BASIS-01 Rev C"]

    for checkpoint_id in ("response_review", "closeout_review"):
        decision = next(
            item for item in gold[checkpoint_id]["accepted_decisions"] if item["decision_id"] == "D-PRV03-001"
        )
        decision["basis_refs"] = alternative

    _run_payloads(package, run_dir, gold)
    gate = verify_ssc03_evidence_lifecycle(package, run_dir)["gates"]["accepted_decision_preservation"]

    assert gate["passed"] is True


def test_verifier_rejects_disallowed_or_rewritten_decision_evidence_fractionally(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    initial = next(
        item for item in gold["initial_review"]["accepted_decisions"] if item["decision_id"] == "D-PRV04-001"
    )
    response = next(
        item for item in gold["response_review"]["accepted_decisions"] if item["decision_id"] == "D-PRV04-001"
    )
    initial["basis_refs"].append("MEMO-03-DESIGN-01 Rev D")
    response["basis_refs"].append("CRIT-SSC03-001 Rev C")

    _run_payloads(package, run_dir, gold)
    gate = verify_ssc03_evidence_lifecycle(package, run_dir)["gates"]["accepted_decision_preservation"]

    assert gate["passed"] is False
    assert 0.0 < gate["score"] < 1.0
    assert "initial_review:D-PRV04-001:basis_disallowed" in gate["failures"]
    assert "response_review:D-PRV04-001:basis_changed" in gate["failures"]


def test_prv08_is_graded_against_submitted_transition_consistency(tmp_path: Path) -> None:
    def consistent_self_finding(payload: dict) -> None:
        payload["transition_decision"]["model_report"] = "governing"
        payload["review_matrix"]["PRV-08"] = "fail"

    package, run_dir = _run_with_mutation(tmp_path, "initial_review", consistent_self_finding)
    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["gates"]["checkpoint_contract"]["passed"] is False
    assert result["gates"]["reviewer_self_consistency"]["passed"] is True


def test_prv08_rejects_pass_when_submitted_transition_is_inconsistent(tmp_path: Path) -> None:
    def hidden_inconsistency(payload: dict) -> None:
        payload["transition_decision"]["model_report"] = "governing"

    package, run_dir = _run_with_mutation(tmp_path, "initial_review", hidden_inconsistency)
    gate = verify_ssc03_evidence_lifecycle(package, run_dir)["gates"]["reviewer_self_consistency"]

    assert gate["passed"] is False
    assert 0.0 < gate["score"] < 1.0
    assert "initial_review.PRV-08" in gate["failures"]


def test_prv09_is_graded_against_claim_boundary_statement(tmp_path: Path) -> None:
    def acknowledge_unsafe_claim(payload: dict) -> None:
        payload["claim_boundary_statement"] = "This task-owned synthetic packet is accepted project evidence."
        payload["review_matrix"]["PRV-09"] = "fail"

    package, run_dir = _run_with_mutation(tmp_path, "closeout_review", acknowledge_unsafe_claim)
    gate = verify_ssc03_evidence_lifecycle(package, run_dir)["gates"]["claim_boundary"]

    assert 0.0 < gate["score"] < 1.0
    assert "closeout_review.statement" in gate["failures"]
    assert "closeout_review.PRV-09" not in gate["failures"]


def test_checkpoint_gate_retains_hard_failure_with_fractional_item_score(tmp_path: Path) -> None:
    def one_matrix_error(payload: dict) -> None:
        payload["review_matrix"]["PRV-04"] = "fail"

    package, run_dir = _run_with_mutation(tmp_path, "initial_review", one_matrix_error)
    gate = verify_ssc03_evidence_lifecycle(package, run_dir)["gates"]["checkpoint_contract"]

    assert gate["passed"] is False
    assert 0.0 < gate["score"] < 1.0
    assert "initial_review.review_matrix.PRV-04" in gate["failures"]


def test_closure_request_accepts_equivalent_complete_wording_and_rejects_rewrite(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    equivalent = ["revised current manifest citing catchment basis Rev D"]
    for checkpoint_id in ("initial_review", "response_review", "closeout_review"):
        request = next(
            item for item in gold[checkpoint_id]["closure_evidence_requests"] if item["request_id"] == "CER-001"
        )
        request["required_evidence"] = equivalent

    passing_run = tmp_path / "passing-run"
    _run_payloads(package, passing_run, gold)
    passing_gate = verify_ssc03_evidence_lifecycle(package, passing_run)["gates"]["closure_evidence"]
    assert passing_gate["passed"] is True

    rewritten = json.loads(json.dumps(gold))
    response_request = next(
        item for item in rewritten["response_review"]["closure_evidence_requests"] if item["request_id"] == "CER-001"
    )
    response_request["required_evidence"] = ["manifest only"]
    failing_run = tmp_path / "failing-run"
    _run_payloads(package, failing_run, rewritten)
    failing_gate = verify_ssc03_evidence_lifecycle(package, failing_run)["gates"]["closure_evidence"]
    assert failing_gate["passed"] is False
    assert "response_review:CER-001:requirement_changed" in failing_gate["failures"]


def test_prv06_closure_is_owned_by_the_recorded_memo_requirement(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    equivalent = ["revised design memo citing and propagating the governing report"]
    for checkpoint_id in ("response_review", "closeout_review"):
        request = next(
            item for item in gold[checkpoint_id]["closure_evidence_requests"] if item["request_id"] == "CER-002"
        )
        request["required_evidence"] = equivalent

    run_dir = tmp_path / "run"
    _run_payloads(package, run_dir, gold)
    gate = verify_ssc03_evidence_lifecycle(package, run_dir)["gates"]["closure_evidence"]

    assert gate["passed"] is True


def test_verifier_rejects_unsafe_claim_boundary_statement(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    def resolve(context: dict) -> dict:
        payload = json.loads(json.dumps(gold[context["checkpoint_id"]]))
        if context["checkpoint_id"] == "closeout_review":
            payload["claim_boundary_statement"] = "This is accepted project evidence and benchmark ready."
        _write_json(Path(context["submission_path"]), payload)
        return {"status": "completed"}

    run_evidence_lifecycle(package, run_dir, episode_resolver=resolve)
    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["reward"] < 1.0
    assert result["gates"]["claim_boundary"]["passed"] is False
    assert "closeout_review.statement" in result["gates"]["claim_boundary"]["failures"]


def test_verifier_rejects_disclaimer_followed_by_positive_readiness_claim(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    def resolve(context: dict) -> dict:
        payload = json.loads(json.dumps(gold[context["checkpoint_id"]]))
        if context["checkpoint_id"] == "closeout_review":
            payload["claim_boundary_statement"] += " It is benchmark ready."
        _write_json(Path(context["submission_path"]), payload)
        return {"status": "completed"}

    run_evidence_lifecycle(package, run_dir, episode_resolver=resolve)
    result = verify_ssc03_evidence_lifecycle(package, run_dir)

    assert result["gates"]["claim_boundary"]["passed"] is False


def test_verifier_rejects_rewritten_episode_archive(tmp_path: Path) -> None:
    package, run_dir = _run_gold(tmp_path)
    archive = run_dir / "episodes" / "initial_review" / "submission.json"
    payload = _load_json(archive)
    payload["review_matrix"]["PRV-03"] = "pass"
    _write_json(archive, payload)

    with pytest.raises(EvidenceLifecycleError, match="archived checkpoint submission changed"):
        verify_ssc03_evidence_lifecycle(package, run_dir)


def test_three_episode_runner_preserves_only_released_evidence(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    visibility: list[list[str]] = []

    def resolve(context: dict) -> dict:
        inbox = Path(context["workspace"]) / "inbox"
        visibility.append(sorted(path.name for path in inbox.iterdir()))
        _write_json(Path(context["submission_path"]), gold[context["checkpoint_id"]])
        return {"status": "completed"}

    result = run_evidence_lifecycle(package, run_dir, episode_resolver=resolve)

    assert result["status"] == "complete"
    assert visibility == [
        ["initial_review"],
        ["initial_review", "response_review"],
        ["closeout_review", "initial_review", "response_review"],
    ]


def test_persistent_session_runner_closes_actual_three_checkpoint_contract(tmp_path: Path) -> None:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    registry = _GoldSessionRegistry(package=package, run_dir=run_dir)

    task_run = run_local_evidence_lifecycle_session(
        package_dir=package,
        run_dir=run_dir,
        model="test-model",
        registry=registry,
        verifier=verify_ssc03_evidence_lifecycle,
        process_id="process.ssc03",
    )

    assert registry.build_count == 1
    assert registry.execute_count == 1
    assert task_run["evidence"]["lifecycle"]["status"] == "complete"
    assert task_run["evidence"]["score"] == {"reward": 1.0, "passed": True}
    assert task_run["evidence"]["verification"]["overall"] == "pass"
    metrics = _load_json(run_dir / "metrics.json")
    assert metrics["semantic_transition"]["aggregate"]["acquisition"] == 1.0
    experiment_id = task_run["evidence"]["experiment"]["experiment_id"]
    canonical_metrics = _load_json(run_dir / "experiments" / experiment_id / "metrics.json")
    assert canonical_metrics["semantic_transition"] == metrics["semantic_transition"]


def test_branch_from_response_can_complete_and_verify_independently(tmp_path: Path) -> None:
    package, parent_run = _run_gold(tmp_path)
    branch_run = tmp_path / "branch"
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="response_review",
        branch_id="branch.response-recheck",
        reason="Recheck response closure before accepting closeout.",
    )
    submit_evidence_checkpoint(package, branch_run)
    closeout = prepare_evidence_checkpoint(package, branch_run)
    _write_json(Path(closeout["submission_path"]), gold["closeout_review"])
    submit_evidence_checkpoint(package, branch_run)

    result = verify_ssc03_evidence_lifecycle(package, branch_run)

    assert result["reward"] == 1.0
    assert result["overall"] == "pass"


def _run_gold(tmp_path: Path) -> tuple[Path, Path]:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    def resolve(context: dict) -> dict:
        _write_json(Path(context["submission_path"]), gold[context["checkpoint_id"]])
        return {"status": "completed"}

    run_evidence_lifecycle(package, run_dir, episode_resolver=resolve)
    return package, run_dir


def _run_with_mutation(
    tmp_path: Path,
    checkpoint_id: str,
    mutate: Callable[[dict], None],
) -> tuple[Path, Path]:
    package = materialize_ssc03_evidence_lifecycle(tmp_path / "package")
    run_dir = tmp_path / "run"
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    def resolve(context: dict) -> dict:
        payload = json.loads(json.dumps(gold[context["checkpoint_id"]]))
        if context["checkpoint_id"] == checkpoint_id:
            mutate(payload)
        _write_json(Path(context["submission_path"]), payload)
        return {"status": "completed"}

    run_evidence_lifecycle(package, run_dir, episode_resolver=resolve)
    return package, run_dir


def _run_payloads(package: Path, run_dir: Path, payloads: dict[str, dict]) -> None:
    def resolve(context: dict) -> dict:
        _write_json(Path(context["submission_path"]), payloads[context["checkpoint_id"]])
        return {"status": "completed"}

    run_evidence_lifecycle(package, run_dir, episode_resolver=resolve)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


class _GoldSessionRegistry:
    def __init__(self, *, package: Path, run_dir: Path) -> None:
        self.package = package
        self.run_dir = run_dir
        self.build_count = 0
        self.execute_count = 0

    def build(self, *, native_tools, **_kwargs):
        self.build_count += 1
        submit_checkpoint = next(tool for tool in native_tools if tool.__name__ == "submit_checkpoint")
        gold = _load_json(self.package / "hidden" / "gold-submissions.json")
        registry = self

        class _GoldSessionAdapter:
            def execute(self, _request):
                registry.execute_count += 1
                for checkpoint_id in ("initial_review", "response_review", "closeout_review"):
                    _write_json(
                        registry.run_dir / "workspace" / "submissions" / f"{checkpoint_id}.json",
                        gold[checkpoint_id],
                    )
                    response = json.loads(submit_checkpoint(checkpoint_id))
                    assert response["status"] in {"awaiting_checkpoint_submission", "complete"}
                return SimpleNamespace(
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text="Lifecycle complete.",
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=30,
                    usage_output_tokens=6,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _GoldSessionAdapter()
