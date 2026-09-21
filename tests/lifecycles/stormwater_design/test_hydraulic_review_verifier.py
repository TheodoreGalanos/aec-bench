# ABOUTME: Tests terminal verification of the hydraulic-review lifecycle.
# ABOUTME: Distinguishes correct reporting of physical failure from evidence or lineage failure.

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.lifecycles.catalogue import (
    materialize_lifecycle,
    verify_lifecycle,
)
from aec_bench.lifecycles.runtime.lifecycle import (
    execute_lifecycle_operation,
    open_checkpoint_attempt,
    release_checkpoint,
    submit_checkpoint,
)
from aec_bench.lifecycles.runtime.request_protocol import EvidenceLifecycleError
from aec_bench.lifecycles.stormwater_design.hydraulic_review_smoke import write_hydraulic_review_smoke_submission
from tests.support.lifecycle_operations import resolve_operation_runtime

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
SCENARIO_IDS = ("design-10yr", "major-100yr")
VARIANT_IDS = (
    "administrative_no_op",
    "major_idf_revision",
    "outlet_geometry_revision",
    "tailwater_revision",
)
CLAIM_BOUNDARY = {
    "evidence_class": "benchmark_owned_synthetic_screening",
    "solver_fidelity": "not_swmm_equivalent",
    "authority_status": "no_authority_approval",
    "standards_status": "no_standards_compliance_claim",
    "project_evidence_status": "not_project_design_evidence",
    "model_evidence_status": "no_model_performance_holdout_or_transfer_result",
    "learning_status": "no_post_training_or_continual_learning_result",
}
EXPECTED_GATES = {
    "checkpoint_contract",
    "source_revision_grounding",
    "operation_evidence_integrity",
    "selective_recomputation",
    "affected_decision_update",
    "unaffected_decision_retention",
    "run_propagation",
    "report_propagation",
    "memo_propagation",
    "final_readiness",
    "claim_boundary",
}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _complete_lifecycle(
    tmp_path: Path,
    variant_id: str,
    *,
    mutate_submission: Callable[[str, dict[str, Any]], None] | None = None,
    add_rejected_operation: bool = False,
) -> tuple[Path, Path, str]:
    package = materialize_lifecycle(TEMPLATE_ID, tmp_path / "package", variant_id=variant_id)
    run = tmp_path / "run"
    for checkpoint_id in ("baseline_analysis", "revision_analysis", "closeout_review"):
        release_checkpoint(package, run, operation_resolver=resolve_operation_runtime(package, run))
        session_id = f"{checkpoint_id}.session-001"
        open_checkpoint_attempt(
            package,
            run,
            operation_resolver=resolve_operation_runtime(package, run),
            session_id=session_id,
            execution_mode="persistent_context",
        )
        if add_rejected_operation and checkpoint_id == "revision_analysis":
            rejected = execute_lifecycle_operation(
                package,
                run,
                operation_resolver=resolve_operation_runtime(package, run),
                operation_id="not-declared",
                reason="Check a rejected operation.",
                session_id=session_id,
            )
            assert rejected["outcome"] == "rejected"
            assert rejected["budget_consumed"] == 0
        path = run / "workspace/submissions" / f"{checkpoint_id}.json"
        write_hydraulic_review_smoke_submission(package, run, checkpoint_id, session_id, path)
        submission = _read_json(path)
        if mutate_submission is not None:
            mutate_submission(checkpoint_id, submission)
        path.write_text(json.dumps(submission) + "\n")
        submit_checkpoint(package, run, operation_resolver=resolve_operation_runtime(package, run))
    return package, run, str(submission["readiness_decision"])


@pytest.mark.parametrize("variant_id", VARIANT_IDS)
def test_complete_interaction_lifecycle_passes_all_evidence_gates(
    tmp_path: Path,
    variant_id: str,
) -> None:
    package, run, readiness = _complete_lifecycle(tmp_path, variant_id)

    result = verify_lifecycle(package, run)

    failed_gates = {gate_id: gate for gate_id, gate in result["gates"].items() if not gate["passed"]}
    assert failed_gates == {}
    assert result["passed"] is True
    assert result["overall"] == "pass"
    assert result["reward"] == 1.0
    assert set(result["gates"]) == EXPECTED_GATES
    assert all(gate["passed"] for gate in result["gates"].values())
    assert readiness == (
        "not_screening_ready" if variant_id in {"major_idf_revision", "outlet_geometry_revision"} else "screening_ready"
    )


@pytest.mark.parametrize(
    ("mutation", "failed_gate"),
    [
        ("source", "source_revision_grounding"),
        ("evidence", "run_propagation"),
        ("readiness", "final_readiness"),
    ],
)
def test_closeout_reference_failures_are_isolated(
    tmp_path: Path,
    mutation: str,
    failed_gate: str,
) -> None:
    def mutate(checkpoint_id: str, submission: dict[str, Any]) -> None:
        if mutation == "source" and checkpoint_id == "revision_analysis":
            submission["source_revision"] = "baseline"
        if checkpoint_id != "closeout_review":
            return
        if mutation == "evidence":
            submission["evidence_checkpoint"] = "baseline_analysis"
        elif mutation == "readiness":
            submission["readiness_decision"] = "not_screening_ready"

    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "tailwater_revision",
        mutate_submission=mutate,
    )

    result = verify_lifecycle(package, run)

    assert result["passed"] is False
    assert result["gates"][failed_gate]["passed"] is False


@pytest.mark.parametrize(
    ("scenario_id", "expected_failed_gate"),
    [
        ("major-100yr", "affected_decision_update"),
        ("design-10yr", "unaffected_decision_retention"),
    ],
)
def test_revision_decision_continuity_is_checked_by_topology(
    tmp_path: Path,
    scenario_id: str,
    expected_failed_gate: str,
) -> None:
    def mutate(checkpoint_id: str, submission: dict[str, Any]) -> None:
        if checkpoint_id != "revision_analysis":
            return
        decision = next(item for item in submission["accepted_decisions"] if item["scenario_id"] == scenario_id)
        phase = "baseline" if scenario_id == "major-100yr" else "revision"
        decision["evidence_checkpoint"] = f"{phase}_analysis"

    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "major_idf_revision",
        mutate_submission=mutate,
    )

    result = verify_lifecycle(package, run)

    assert result["passed"] is False
    assert result["gates"][expected_failed_gate]["passed"] is False


def test_affected_scenario_baseline_decision_is_verified(tmp_path: Path) -> None:
    def mutate(checkpoint_id: str, submission: dict[str, Any]) -> None:
        if checkpoint_id != "baseline_analysis":
            return
        decision = next(item for item in submission["accepted_decisions"] if item["scenario_id"] == "major-100yr")
        decision["screening_outcome"] = "criteria_not_met"

    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "outlet_geometry_revision",
        mutate_submission=mutate,
    )

    result = verify_lifecycle(package, run)

    assert result["passed"] is False
    assert result["gates"]["affected_decision_update"]["passed"] is False


def test_checkpoint_contract_rejects_duplicate_scenario_decisions(tmp_path: Path) -> None:
    def mutate(checkpoint_id: str, submission: dict[str, Any]) -> None:
        if checkpoint_id == "baseline_analysis":
            submission["accepted_decisions"].append(copy.deepcopy(submission["accepted_decisions"][0]))

    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "outlet_geometry_revision",
        mutate_submission=mutate,
    )

    result = verify_lifecycle(package, run)

    assert result["passed"] is False
    assert result["gates"]["checkpoint_contract"]["passed"] is False


def test_unknown_evidence_checkpoint_fails_closed(tmp_path: Path) -> None:
    def mutate(checkpoint_id: str, submission: dict[str, Any]) -> None:
        if checkpoint_id == "revision_analysis":
            submission["accepted_decisions"][0]["evidence_checkpoint"] = "missing_analysis"

    package, run, _ = _complete_lifecycle(tmp_path, "major_idf_revision", mutate_submission=mutate)
    result = verify_lifecycle(package, run)
    assert result["passed"] is False
    assert result["reward"] == 0.0
    assert result["gates"]["checkpoint_contract"]["passed"] is False


def test_extra_rejected_action_does_not_change_reward(tmp_path: Path) -> None:
    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "major_idf_revision",
        add_rejected_operation=True,
    )

    result = verify_lifecycle(package, run)

    assert result["passed"] is True
    assert result["reward"] == 1.0


def test_unsafe_claim_boundary_fails_closed(tmp_path: Path) -> None:
    def mutate(checkpoint_id: str, submission: dict[str, Any]) -> None:
        if checkpoint_id == "baseline_analysis":
            submission["claim_boundary"]["authority_status"] = "authority_approved"

    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "tailwater_revision",
        mutate_submission=mutate,
    )

    result = verify_lifecycle(package, run)

    assert result["passed"] is False
    assert result["reward"] == 0.0
    assert result["gates"]["checkpoint_contract"]["passed"] is False
    assert result["gates"]["claim_boundary"]["passed"] is False


def test_canonical_calculation_result_tampering_fails_closed(tmp_path: Path) -> None:
    package, run, _readiness_state = _complete_lifecycle(tmp_path, "tailwater_revision")
    state = _read_json(run / "state.json")
    action_id = next(
        action["retained_from_action_id"] or action["action_id"]
        for checkpoint in state["checkpoint_runs"]
        if checkpoint["checkpoint_id"] == "revision_analysis"
        for action in checkpoint["operation_actions"]
        if action["operation_id"] == "detention-outlet.design-10yr.declared-outlet"
    )
    result_path = run / "lifecycle_operations" / action_id / "artifacts" / "hydraulic-run" / "results.json"
    result = _read_json(result_path)
    result["peak_total_inflow_m3_s"] = 999.0
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(EvidenceLifecycleError, match="operation artifact hash mismatch"):
        verify_lifecycle(package, run)
