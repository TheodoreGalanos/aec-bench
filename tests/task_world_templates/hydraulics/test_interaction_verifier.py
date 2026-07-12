# ABOUTME: Tests terminal verification of the SSC-03 interactive hydraulic lifecycle.
# ABOUTME: Distinguishes correct reporting of physical failure from evidence or lineage failure.

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.meta_harness.evidence_lifecycle import (
    execute_lifecycle_operation,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    submit_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_request_protocol import EvidenceLifecycleError
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import (
    materialize_lifecycle_template,
    verify_lifecycle_template,
)

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


def _visible_sha(run: Path) -> str:
    return str(_read_json(run / "workspace" / "hydraulics" / "current-source.json")["visible_source_state_sha256"])


def _execute(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    operation_id: str,
    session_id: str,
) -> dict[str, Any]:
    return execute_lifecycle_operation(
        package,
        run,
        checkpoint_id=checkpoint_id,
        operation_id=operation_id,
        visible_source_state_sha256=_visible_sha(run),
        reason=f"Execute {operation_id} against the declared source.",
        session_id=session_id,
    )


def _execute_calculation_operations(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    session_id: str,
) -> dict[str, dict[str, Any]]:
    actions: dict[str, dict[str, Any]] = {}
    for scenario_id in SCENARIO_IDS:
        for operation_id in (
            f"hydrology.{scenario_id}",
            f"detention-outlet.{scenario_id}.declared-outlet",
            f"network-hgl.{scenario_id}.declared-tailwater",
        ):
            actions[operation_id] = _execute(
                package,
                run,
                checkpoint_id=checkpoint_id,
                operation_id=operation_id,
                session_id=session_id,
            )
    return actions


def _origin_action_id(action: dict[str, Any]) -> str:
    return str(action["retained_from_action_id"] or action["action_id"])


def _decision(
    run: Path,
    actions: dict[str, dict[str, Any]],
    *,
    scenario_id: str,
    revision: bool,
) -> dict[str, Any]:
    hydrology = _origin_action_id(actions[f"hydrology.{scenario_id}"])
    detention = _origin_action_id(actions[f"detention-outlet.{scenario_id}.declared-outlet"])
    hgl = _origin_action_id(actions[f"network-hgl.{scenario_id}.declared-tailwater"])
    detention_result = _read_json(run / "lifecycle_operations" / detention / "artifacts" / "detention-outlet.json")
    hgl_result = _read_json(run / "lifecycle_operations" / hgl / "artifacts" / "network-hgl.json")
    criteria = dict(detention_result["criteria"]) | dict(hgl_result["criteria"])
    failed_criteria = sorted(key for key, passed in criteria.items() if not passed)
    phase = "revision" if revision else "baseline"
    return {
        "decision_id": f"decision.{scenario_id}.{phase}",
        "scenario_id": scenario_id,
        "hydrology_action_id": hydrology,
        "detention_action_id": detention,
        "hgl_action_id": hgl,
        "hydraulic_run_id": detention_result["hydraulic_run_id"],
        "screening_outcome": "criteria_not_met" if failed_criteria else "criteria_met",
        "failed_criteria": failed_criteria,
    }


def _selected_operations(actions: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {operation_id: str(action["action_id"]) for operation_id, action in sorted(actions.items())}


def _readiness(decisions: list[dict[str, Any]]) -> str:
    return (
        "not_screening_ready"
        if any(decision["screening_outcome"] == "criteria_not_met" for decision in decisions)
        else "screening_ready"
    )


def _run_references(
    run: Path,
    actions: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    runs: dict[str, dict[str, str]] = {}
    reports: dict[str, dict[str, str]] = {}
    for scenario_id in SCENARIO_IDS:
        detention_operation = f"detention-outlet.{scenario_id}.declared-outlet"
        hgl_operation = f"network-hgl.{scenario_id}.declared-tailwater"
        selected_detention = actions[detention_operation]
        selected_hgl = actions[hgl_operation]
        detention = _origin_action_id(selected_detention)
        hgl = _origin_action_id(selected_hgl)
        detention_result = _read_json(run / "lifecycle_operations" / detention / "artifacts" / "detention-outlet.json")
        hgl_result = _read_json(run / "lifecycle_operations" / hgl / "artifacts" / "network-hgl.json")
        report = run / "lifecycle_operations" / hgl / "artifacts" / "report.md"
        runs[scenario_id] = {
            "selected_operation_action_id": str(selected_detention["action_id"]),
            "canonical_detention_action_id": detention,
            "hydraulic_run_id": str(detention_result["hydraulic_run_id"]),
            "run_manifest_sha256": str(detention_result["hydraulic_run_manifest_sha256"]),
        }
        reports[scenario_id] = {
            "selected_operation_action_id": str(selected_hgl["action_id"]),
            "canonical_hgl_action_id": hgl,
            "hydraulic_run_id": str(hgl_result["hydraulic_run_id"]),
            "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
        }
    return runs, reports


def _write_and_submit(package: Path, run: Path, checkpoint_id: str, submission: dict[str, Any]) -> None:
    path = run / "workspace" / "submissions" / f"{checkpoint_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    submit_evidence_checkpoint(package, run)


def _complete_lifecycle(
    tmp_path: Path,
    variant_id: str,
    *,
    mutate_submission: Callable[[str, dict[str, Any]], None] | None = None,
    add_rejected_operation: bool = False,
) -> tuple[Path, Path, str]:
    package = materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id=variant_id,
    )
    run = tmp_path / "run"
    prepare_evidence_checkpoint(package, run)
    open_checkpoint_attempt(
        package,
        run,
        session_id="baseline.session-001",
        execution_mode="persistent_context",
    )
    baseline_actions = _execute_calculation_operations(
        package,
        run,
        checkpoint_id="baseline_analysis",
        session_id="baseline.session-001",
    )
    baseline_decisions = [
        _decision(run, baseline_actions, scenario_id=scenario_id, revision=False) for scenario_id in SCENARIO_IDS
    ]
    baseline_submission = {
        "checkpoint_id": "baseline_analysis",
        "visible_source_state_sha256": _visible_sha(run),
        "selected_operations": _selected_operations(baseline_actions),
        "accepted_decisions": baseline_decisions,
        "readiness_decision": _readiness(baseline_decisions),
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
    }
    if mutate_submission is not None:
        mutate_submission("baseline_analysis", baseline_submission)
    _write_and_submit(package, run, "baseline_analysis", baseline_submission)

    prepare_evidence_checkpoint(package, run)
    open_checkpoint_attempt(
        package,
        run,
        session_id="revision.session-001",
        execution_mode="persistent_context",
    )
    revision_action = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id="revision.session-001",
    )
    if add_rejected_operation:
        rejected = _execute(
            package,
            run,
            checkpoint_id="revision_analysis",
            operation_id="network-hgl.major-100yr.declared-tailwater",
            session_id="revision.session-001",
        )
        assert rejected["outcome"] == "rejected"
        assert rejected["budget_consumed"] == 0
    revision_actions = _execute_calculation_operations(
        package,
        run,
        checkpoint_id="revision_analysis",
        session_id="revision.session-001",
    )
    affected = {
        "administrative_no_op": set(),
        "major_idf_revision": {"major-100yr"},
        "outlet_geometry_revision": set(SCENARIO_IDS),
        "tailwater_revision": set(SCENARIO_IDS),
    }[variant_id]
    baseline_by_scenario = {decision["scenario_id"]: decision for decision in baseline_decisions}
    revision_decisions = [
        (
            _decision(run, revision_actions, scenario_id=scenario_id, revision=True)
            if scenario_id in affected
            else baseline_by_scenario[scenario_id]
        )
        for scenario_id in SCENARIO_IDS
    ]
    supersession_lineage = [
        {
            "scenario_id": scenario_id,
            "superseded_decision_id": f"decision.{scenario_id}.baseline",
            "replacement_decision_id": f"decision.{scenario_id}.revision",
        }
        for scenario_id in SCENARIO_IDS
        if scenario_id in affected
    ]
    revision_selected = _selected_operations(revision_actions) | {
        "source-revision.current": str(revision_action["action_id"])
    }
    revision_submission: dict[str, Any] = {
        "checkpoint_id": "revision_analysis",
        "revision_id": variant_id,
        "visible_source_state_sha256": _visible_sha(run),
        "selected_operations": revision_selected,
        "accepted_decisions": revision_decisions,
        "supersession_lineage": supersession_lineage,
        "readiness_decision": _readiness(revision_decisions),
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
    }
    if mutate_submission is not None:
        mutate_submission("revision_analysis", revision_submission)
    _write_and_submit(package, run, "revision_analysis", revision_submission)

    revision_selected = dict(revision_submission["selected_operations"])
    revision_decisions = list(revision_submission["accepted_decisions"])
    supersession_lineage = list(revision_submission["supersession_lineage"])
    revision_visible_sha = str(revision_submission["visible_source_state_sha256"])
    readiness = str(revision_submission["readiness_decision"])

    prepare_evidence_checkpoint(package, run)
    open_checkpoint_attempt(
        package,
        run,
        session_id="closeout.session-001",
        execution_mode="persistent_context",
    )
    run_reference, report_reference = _run_references(run, revision_actions)
    closeout_submission = {
        "checkpoint_id": "closeout_review",
        "visible_source_state_sha256": revision_visible_sha,
        "selected_operations": revision_selected,
        "run_reference": run_reference,
        "report_reference": report_reference,
        "accepted_decisions": revision_decisions,
        "supersession_lineage": supersession_lineage,
        "readiness_decision": readiness,
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
        "memo": {
            "visible_source_state_sha256": revision_visible_sha,
            "run_reference": copy.deepcopy(run_reference),
            "report_reference": copy.deepcopy(report_reference),
            "decision_ids": {
                str(decision["scenario_id"]): str(decision["decision_id"]) for decision in revision_decisions
            },
            "supersession_lineage": supersession_lineage,
            "readiness_decision": readiness,
            "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
        },
    }
    if mutate_submission is not None:
        mutate_submission("closeout_review", closeout_submission)
    _write_and_submit(package, run, "closeout_review", closeout_submission)
    return package, run, readiness


@pytest.mark.parametrize("variant_id", VARIANT_IDS)
def test_complete_interaction_lifecycle_passes_all_evidence_gates(
    tmp_path: Path,
    variant_id: str,
) -> None:
    package, run, readiness = _complete_lifecycle(tmp_path, variant_id)

    result = verify_lifecycle_template(package, run)

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
        ("run", "run_propagation"),
        ("report", "report_propagation"),
        ("memo", "memo_propagation"),
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
            submission["visible_source_state_sha256"] = "0" * 64
        if checkpoint_id != "closeout_review":
            return
        if mutation == "run":
            submission["run_reference"]["design-10yr"]["hydraulic_run_id"] = "stale-run"
        elif mutation == "report":
            submission["report_reference"]["design-10yr"]["report_sha256"] = "0" * 64
        elif mutation == "memo":
            submission["memo"]["readiness_decision"] = "not_screening_ready"
        elif mutation == "readiness":
            submission["readiness_decision"] = "not_screening_ready"

    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "tailwater_revision",
        mutate_submission=mutate,
    )

    result = verify_lifecycle_template(package, run)

    assert result["passed"] is False
    assert result["gates"][failed_gate]["passed"] is False
    for gate_id, gate in result["gates"].items():
        if gate_id != failed_gate:
            assert gate["passed"] is True, (gate_id, gate)


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
        decision["decision_id"] = f"decision.{scenario_id}.{phase}"

    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "major_idf_revision",
        mutate_submission=mutate,
    )

    result = verify_lifecycle_template(package, run)

    assert result["passed"] is False
    assert result["gates"][expected_failed_gate]["passed"] is False


def test_affected_scenario_baseline_decision_is_verified(tmp_path: Path) -> None:
    def mutate(checkpoint_id: str, submission: dict[str, Any]) -> None:
        if checkpoint_id != "baseline_analysis":
            return
        decision = next(item for item in submission["accepted_decisions"] if item["scenario_id"] == "major-100yr")
        decision["hydraulic_run_id"] = "stale-baseline-run"

    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "outlet_geometry_revision",
        mutate_submission=mutate,
    )

    result = verify_lifecycle_template(package, run)

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

    result = verify_lifecycle_template(package, run)

    assert result["passed"] is False
    assert result["gates"]["checkpoint_contract"]["passed"] is False


def test_stale_selected_operation_cannot_masquerade_as_current(tmp_path: Path) -> None:
    baseline_selected: dict[str, str] = {}

    def mutate(checkpoint_id: str, submission: dict[str, Any]) -> None:
        if checkpoint_id == "baseline_analysis":
            baseline_selected.update(submission["selected_operations"])
        elif checkpoint_id == "revision_analysis":
            submission["selected_operations"]["hydrology.major-100yr"] = baseline_selected["hydrology.major-100yr"]

    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "major_idf_revision",
        mutate_submission=mutate,
    )

    result = verify_lifecycle_template(package, run)

    assert result["passed"] is False
    assert result["gates"]["operation_evidence_integrity"]["passed"] is False
    assert result["gates"]["selective_recomputation"]["passed"] is False


def test_extra_rejected_action_does_not_change_reward(tmp_path: Path) -> None:
    package, run, _readiness_state = _complete_lifecycle(
        tmp_path,
        "major_idf_revision",
        add_rejected_operation=True,
    )

    result = verify_lifecycle_template(package, run)

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

    result = verify_lifecycle_template(package, run)

    assert result["passed"] is False
    assert result["reward"] == 0.0
    assert result["gates"]["checkpoint_contract"]["passed"] is False
    assert result["gates"]["claim_boundary"]["passed"] is False


def test_canonical_pr18_result_tampering_fails_closed(tmp_path: Path) -> None:
    package, run, _readiness_state = _complete_lifecycle(tmp_path, "tailwater_revision")
    closeout = _read_json(run / "episodes" / "closeout_review" / "submission.json")
    action_id = closeout["run_reference"]["design-10yr"]["canonical_detention_action_id"]
    result_path = run / "lifecycle_operations" / action_id / "artifacts" / "hydraulic-run" / "results.json"
    result = _read_json(result_path)
    result["peak_total_inflow_m3_s"] = 999.0
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(EvidenceLifecycleError, match="operation artifact hash mismatch"):
        verify_lifecycle_template(package, run)
