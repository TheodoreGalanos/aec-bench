# ABOUTME: Verifies the SSC-03 intervention choice from archived selection through hydraulic closeout.
# ABOUTME: Scores honest evidence handling separately from whether the chosen intervention solves the problem.

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle import (
    load_validated_lifecycle_submissions,
    read_evidence_lifecycle_state,
)
from aec_bench.meta_harness.evidence_lifecycle_state import (
    LifecycleOperationActionRecord,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
)
from aec_bench.task_world_templates.hydraulics.interventions import (
    HydraulicInterventionId,
    list_hydraulic_intervention_ids,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_verifier import (
    CALCULATION_OPERATION_IDS,
    SCENARIO_IDS,
    ClaimBoundary,
    DecisionSupersession,
    ReadinessDecision,
    ReportReference,
    RunReference,
    ScenarioDecision,
    ScenarioEvidence,
    _expected_readiness,
    _gate,
    _mapping_failures,
    _read_json,
    _scenario_evidence,
    _selected_actions,
    _sha256,
    _transaction_failures,
)

SOURCE_INTERVENTION_OPERATION_ID = "source-intervention.selected"
GATE_IDS = (
    "checkpoint_contract",
    "selection_grounding",
    "operation_evidence_integrity",
    "selective_recomputation",
    "decision_update",
    "intervention_effectiveness",
    "run_propagation",
    "report_propagation",
    "memo_propagation",
    "final_readiness",
    "claim_boundary",
)


class ProblemSubmission(StrictModel):
    checkpoint_id: Literal["problem_analysis"]
    visible_source_state_sha256: NonEmptyStr
    selected_operations: dict[NonEmptyStr, NonEmptyStr]
    accepted_decisions: tuple[ScenarioDecision, ...]
    readiness_decision: ReadinessDecision
    claim_boundary: ClaimBoundary


class SelectionSubmission(StrictModel):
    checkpoint_id: Literal["intervention_selection"]
    visible_source_state_sha256: NonEmptyStr
    selected_intervention_id: HydraulicInterventionId
    selection_basis: NonEmptyStr
    claim_boundary: ClaimBoundary


class InterventionSubmission(StrictModel):
    checkpoint_id: Literal["intervention_analysis"]
    selected_intervention_id: HydraulicInterventionId
    visible_source_state_sha256: NonEmptyStr
    selected_operations: dict[NonEmptyStr, NonEmptyStr]
    accepted_decisions: tuple[ScenarioDecision, ...]
    supersession_lineage: tuple[DecisionSupersession, ...]
    readiness_decision: ReadinessDecision
    claim_boundary: ClaimBoundary


class InterventionCloseoutMemo(StrictModel):
    selected_intervention_id: HydraulicInterventionId
    visible_source_state_sha256: NonEmptyStr
    run_reference: dict[NonEmptyStr, RunReference]
    report_reference: dict[NonEmptyStr, ReportReference]
    decision_ids: dict[NonEmptyStr, NonEmptyStr]
    supersession_lineage: tuple[DecisionSupersession, ...]
    readiness_decision: ReadinessDecision
    claim_boundary: ClaimBoundary


class InterventionCloseoutSubmission(StrictModel):
    checkpoint_id: Literal["closeout_review"]
    selected_intervention_id: HydraulicInterventionId
    visible_source_state_sha256: NonEmptyStr
    selected_operations: dict[NonEmptyStr, NonEmptyStr]
    run_reference: dict[NonEmptyStr, RunReference]
    report_reference: dict[NonEmptyStr, ReportReference]
    memo: InterventionCloseoutMemo
    accepted_decisions: tuple[ScenarioDecision, ...]
    supersession_lineage: tuple[DecisionSupersession, ...]
    readiness_decision: ReadinessDecision
    claim_boundary: ClaimBoundary


def verify_hydraulic_intervention_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Verify the complete design response from problem diagnosis through closeout."""
    package = Path(package_dir)
    run = Path(run_dir)
    raw = load_validated_lifecycle_submissions(package, run)
    try:
        problem = ProblemSubmission.model_validate(raw["problem_analysis"])
        selection = SelectionSubmission.model_validate(raw["intervention_selection"])
        intervention = InterventionSubmission.model_validate(raw["intervention_analysis"])
        closeout = InterventionCloseoutSubmission.model_validate(raw["closeout_review"])
    except (KeyError, ValidationError) as exc:
        return _invalid_contract_result(str(exc))

    state = read_evidence_lifecycle_state(package, run)
    actions = {
        action.action_id: action
        for checkpoint in state["checkpoint_runs"]
        for action in (LifecycleOperationActionRecord.model_validate(item) for item in checkpoint["operation_actions"])
    }
    problem_selected, problem_selection_failures = _selected_actions(
        problem.selected_operations,
        actions,
        checkpoint_id="problem_analysis",
        expected_operation_ids=set(CALCULATION_OPERATION_IDS),
    )
    intervention_selected, intervention_selection_failures = _selected_actions(
        intervention.selected_operations,
        actions,
        checkpoint_id="intervention_analysis",
        expected_operation_ids=set(CALCULATION_OPERATION_IDS) | {SOURCE_INTERVENTION_OPERATION_ID},
    )

    checkpoint_failures = _checkpoint_failures(problem, selection, intervention, closeout)
    selection_failures = _selection_failures(
        package,
        run,
        problem,
        selection,
        intervention,
        closeout,
        intervention_selected,
    )
    operation_failures = problem_selection_failures + intervention_selection_failures
    operation_failures.extend(_transaction_failures(run, actions.values()))
    selective_failures = _selective_recomputation_failures(problem_selected, intervention_selected)

    problem_evidence, problem_evidence_failures = _scenario_evidence(package, run, problem_selected)
    intervention_evidence, intervention_evidence_failures = _scenario_evidence(
        package,
        run,
        intervention_selected,
    )
    operation_failures.extend(problem_evidence_failures)
    operation_failures.extend(intervention_evidence_failures)

    expected_problem_decisions = _expected_phase_decisions(problem_evidence, phase="problem")
    expected_intervention_decisions = _expected_phase_decisions(
        intervention_evidence,
        phase="intervention",
    )
    expected_lineage = tuple(
        DecisionSupersession(
            scenario_id=scenario_id,
            superseded_decision_id=f"decision.{scenario_id}.problem",
            replacement_decision_id=f"decision.{scenario_id}.intervention",
        )
        for scenario_id in SCENARIO_IDS
    )
    decision_failures = _decision_failures(
        problem,
        intervention,
        expected_problem_decisions,
        expected_intervention_decisions,
        expected_lineage,
    )
    effectiveness_failures = _effectiveness_failures(
        selection.selected_intervention_id,
        intervention_evidence,
    )

    expected_runs = {scenario_id: evidence.run_reference for scenario_id, evidence in intervention_evidence.items()}
    expected_reports = {
        scenario_id: evidence.report_reference for scenario_id, evidence in intervention_evidence.items()
    }
    run_failures = _scenario_mapping_failures("run_reference", closeout.run_reference, expected_runs)
    report_failures = _scenario_mapping_failures("report_reference", closeout.report_reference, expected_reports)
    readiness = _expected_readiness(expected_intervention_decisions)
    memo_failures = _memo_failures(
        closeout,
        expected_runs,
        expected_reports,
        expected_intervention_decisions,
        expected_lineage,
        readiness,
    )
    readiness_failures = _readiness_failures(
        problem,
        intervention,
        closeout,
        expected_problem_decisions,
        expected_intervention_decisions,
    )
    claim_failures = _claim_failures(problem, selection, intervention, closeout)

    gates = {
        "checkpoint_contract": _gate(checkpoint_failures),
        "selection_grounding": _gate(selection_failures),
        "operation_evidence_integrity": _gate(operation_failures),
        "selective_recomputation": _gate(selective_failures),
        "decision_update": _gate(decision_failures),
        "intervention_effectiveness": _gate(effectiveness_failures),
        "run_propagation": _gate(run_failures),
        "report_propagation": _gate(report_failures),
        "memo_propagation": _gate(memo_failures),
        "final_readiness": _gate(readiness_failures),
        "claim_boundary": _gate(claim_failures),
    }
    passed = all(gate["passed"] for gate in gates.values())
    reward = _reward(gates)
    return {
        "template_id": "hydraulic-design-response-lifecycle-review",
        "lifecycle_id": "ssc03.hydraulic-design-response-lifecycle",
        "overall": "pass" if passed else "fail",
        "passed": passed,
        "reward": reward,
        "gates": gates,
    }


def _invalid_contract_result(message: str) -> dict[str, Any]:
    gates = {
        gate_id: _gate([message if gate_id == "checkpoint_contract" else "checkpoint contract unavailable"])
        for gate_id in GATE_IDS
    }
    return {
        "template_id": "hydraulic-design-response-lifecycle-review",
        "lifecycle_id": "ssc03.hydraulic-design-response-lifecycle",
        "overall": "fail",
        "passed": False,
        "reward": 0.0,
        "gates": gates,
    }


def _reward(gates: dict[str, dict[str, Any]]) -> float:
    mean_gate_score = sum(float(gate["score"]) for gate in gates.values()) / len(gates)
    if not gates["intervention_effectiveness"]["passed"]:
        mean_gate_score = min(mean_gate_score, 0.5)
    return round(mean_gate_score, 4)


def _checkpoint_failures(
    problem: ProblemSubmission,
    selection: SelectionSubmission,
    intervention: InterventionSubmission,
    closeout: InterventionCloseoutSubmission,
) -> list[str]:
    failures: list[str] = []
    for checkpoint_id, decisions in (
        ("problem_analysis", problem.accepted_decisions),
        ("intervention_analysis", intervention.accepted_decisions),
        ("closeout_review", closeout.accepted_decisions),
    ):
        if len(decisions) != len(SCENARIO_IDS) or {item.scenario_id for item in decisions} != set(SCENARIO_IDS):
            failures.append(f"{checkpoint_id}.accepted_decisions.scenarios")
    if not selection.selection_basis.strip():
        failures.append("intervention_selection.selection_basis")
    if closeout.selected_operations != intervention.selected_operations:
        failures.append("closeout_review.selected_operations")
    if closeout.accepted_decisions != intervention.accepted_decisions:
        failures.append("closeout_review.accepted_decisions")
    if closeout.supersession_lineage != intervention.supersession_lineage:
        failures.append("closeout_review.supersession_lineage")
    return failures


def _selection_failures(
    package: Path,
    run: Path,
    problem: ProblemSubmission,
    selection: SelectionSubmission,
    intervention: InterventionSubmission,
    closeout: InterventionCloseoutSubmission,
    selected_actions: dict[str, LifecycleOperationActionRecord],
) -> list[str]:
    failures: list[str] = []
    source_action = selected_actions.get(SOURCE_INTERVENTION_OPERATION_ID)
    if source_action is None:
        return ["intervention_analysis.source_intervention_action"]
    intervention_id = selection.selected_intervention_id
    if intervention_id not in set(list_hydraulic_intervention_ids()):
        failures.append("intervention_selection.selected_intervention_id")
    if intervention.selected_intervention_id != intervention_id:
        failures.append("intervention_analysis.selected_intervention_id")
    if closeout.selected_intervention_id != intervention_id:
        failures.append("closeout_review.selected_intervention_id")
    if problem.visible_source_state_sha256 != source_action.visible_source_state_before_sha256:
        failures.append("problem_analysis.visible_source_state_sha256")
    if selection.visible_source_state_sha256 != problem.visible_source_state_sha256:
        failures.append("intervention_selection.visible_source_state_sha256")
    if intervention.visible_source_state_sha256 != source_action.visible_source_state_after_sha256:
        failures.append("intervention_analysis.visible_source_state_sha256")
    if closeout.visible_source_state_sha256 != intervention.visible_source_state_sha256:
        failures.append("closeout_review.visible_source_state_sha256")

    problem_source = package / "hidden" / "hydraulic" / "packages" / "problem" / "source" / "source-state.json"
    option_source = (
        package
        / "hidden"
        / "hydraulic"
        / "packages"
        / "interventions"
        / intervention_id
        / "source"
        / "source-state.json"
    )
    if source_action.physical_source_state_before_sha256 != _sha256(problem_source):
        failures.append("intervention_analysis.physical_source_before")
    if source_action.physical_source_state_after_sha256 != _sha256(option_source):
        failures.append("intervention_analysis.physical_source_after")
    if (
        source_action.outcome != LifecycleOperationOutcome.COMPLETED
        or source_action.disposition != LifecycleOperationDisposition.ACTIVATED
        or source_action.budget_consumed != 1
    ):
        failures.append("intervention_analysis.source_intervention_activation")
    identity = _read_json(run / "lifecycle_operations" / source_action.action_id / "artifacts" / "source-identity.json")
    selection_path = run / "episodes" / "intervention_selection" / "submission.json"
    if identity.get("selected_intervention_id") != intervention_id:
        failures.append("intervention_analysis.source_identity.intervention")
    if identity.get("selection_submission_sha256") != _sha256(selection_path):
        failures.append("intervention_analysis.source_identity.selection")
    return failures


def _selective_recomputation_failures(
    problem: dict[str, LifecycleOperationActionRecord],
    intervention: dict[str, LifecycleOperationActionRecord],
) -> list[str]:
    failures: list[str] = []
    for operation_id in CALCULATION_OPERATION_IDS:
        problem_action = problem.get(operation_id)
        current_action = intervention.get(operation_id)
        if problem_action is None or current_action is None:
            failures.append(f"intervention_analysis.{operation_id}.missing")
            continue
        if operation_id.startswith("hydrology."):
            if (
                current_action.outcome != LifecycleOperationOutcome.ALREADY_CURRENT
                or current_action.disposition != LifecycleOperationDisposition.REUSED
                or current_action.retained_from_action_id != problem_action.action_id
                or current_action.input_projection_sha256 != problem_action.input_projection_sha256
                or current_action.budget_consumed != 0
            ):
                failures.append(f"intervention_analysis.{operation_id}.reuse")
        elif (
            current_action.outcome != LifecycleOperationOutcome.COMPLETED
            or current_action.disposition != LifecycleOperationDisposition.COMPUTED
            or current_action.retained_from_action_id is not None
            or current_action.input_projection_sha256 == problem_action.input_projection_sha256
            or current_action.budget_consumed != 1
        ):
            failures.append(f"intervention_analysis.{operation_id}.recompute")
    return failures


def _expected_phase_decisions(
    evidence: dict[str, ScenarioEvidence],
    *,
    phase: str,
) -> dict[str, ScenarioDecision]:
    return {
        scenario_id: ScenarioDecision(
            decision_id=f"decision.{scenario_id}.{phase}",
            scenario_id=evidence_item.scenario_id,
            hydrology_action_id=evidence_item.hydrology_action_id,
            detention_action_id=evidence_item.detention_action_id,
            hgl_action_id=evidence_item.hgl_action_id,
            hydraulic_run_id=evidence_item.hydraulic_run_id,
            screening_outcome=("criteria_not_met" if evidence_item.failed_criteria else "criteria_met"),
            failed_criteria=evidence_item.failed_criteria,
        )
        for scenario_id, evidence_item in evidence.items()
    }


def _decision_failures(
    problem: ProblemSubmission,
    intervention: InterventionSubmission,
    expected_problem: dict[str, ScenarioDecision],
    expected_intervention: dict[str, ScenarioDecision],
    expected_lineage: tuple[DecisionSupersession, ...],
) -> list[str]:
    actual_problem = {item.scenario_id: item for item in problem.accepted_decisions}
    actual_intervention = {item.scenario_id: item for item in intervention.accepted_decisions}
    failures = [
        f"problem_analysis.accepted_decisions.{scenario_id}"
        for scenario_id in SCENARIO_IDS
        if actual_problem.get(scenario_id) != expected_problem.get(scenario_id)
    ]
    failures.extend(
        f"intervention_analysis.accepted_decisions.{scenario_id}"
        for scenario_id in SCENARIO_IDS
        if actual_intervention.get(scenario_id) != expected_intervention.get(scenario_id)
    )
    if intervention.supersession_lineage != expected_lineage:
        failures.append("intervention_analysis.supersession_lineage")
    return failures


def _effectiveness_failures(
    intervention_id: HydraulicInterventionId,
    evidence: dict[str, ScenarioEvidence],
) -> list[str]:
    failures: list[str] = []
    for scenario_id in SCENARIO_IDS:
        scenario = evidence.get(scenario_id)
        if scenario is None:
            failures.append(f"{intervention_id}.{scenario_id}.evidence_missing")
            continue
        failures.extend(f"{intervention_id}.{scenario_id}.{criterion_id}" for criterion_id in scenario.failed_criteria)
    return failures


def _scenario_mapping_failures(
    label: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if set(actual) != set(SCENARIO_IDS):
        failures.append(f"closeout_review.{label}.scenarios")
    failures.extend(_mapping_failures(label, actual, expected))
    return failures


def _memo_failures(
    closeout: InterventionCloseoutSubmission,
    runs: dict[str, RunReference],
    reports: dict[str, ReportReference],
    decisions: dict[str, ScenarioDecision],
    lineage: tuple[DecisionSupersession, ...],
    readiness: ReadinessDecision,
) -> list[str]:
    failures: list[str] = []
    for label, mapping in (
        ("run_reference", closeout.memo.run_reference),
        ("report_reference", closeout.memo.report_reference),
        ("decision_ids", closeout.memo.decision_ids),
    ):
        if set(mapping) != set(SCENARIO_IDS):
            failures.append(f"closeout_review.memo.{label}.scenarios")
    expected = InterventionCloseoutMemo(
        selected_intervention_id=closeout.selected_intervention_id,
        visible_source_state_sha256=closeout.visible_source_state_sha256,
        run_reference=runs,
        report_reference=reports,
        decision_ids={scenario_id: decision.decision_id for scenario_id, decision in decisions.items()},
        supersession_lineage=lineage,
        readiness_decision=readiness,
        claim_boundary=closeout.claim_boundary,
    )
    if closeout.memo != expected:
        failures.append("closeout_review.memo")
    return failures


def _readiness_failures(
    problem: ProblemSubmission,
    intervention: InterventionSubmission,
    closeout: InterventionCloseoutSubmission,
    problem_decisions: dict[str, ScenarioDecision],
    intervention_decisions: dict[str, ScenarioDecision],
) -> list[str]:
    failures: list[str] = []
    if set(problem_decisions) != set(SCENARIO_IDS):
        failures.append("problem_analysis.readiness_evidence.scenarios")
    if set(intervention_decisions) != set(SCENARIO_IDS):
        failures.append("intervention_analysis.readiness_evidence.scenarios")
    if problem.readiness_decision != _expected_readiness(problem_decisions):
        failures.append("problem_analysis.readiness_decision")
    expected_intervention = _expected_readiness(intervention_decisions)
    if intervention.readiness_decision != expected_intervention:
        failures.append("intervention_analysis.readiness_decision")
    if closeout.readiness_decision != expected_intervention:
        failures.append("closeout_review.readiness_decision")
    return failures


def _claim_failures(
    problem: ProblemSubmission,
    selection: SelectionSubmission,
    intervention: InterventionSubmission,
    closeout: InterventionCloseoutSubmission,
) -> list[str]:
    claims = (
        problem.claim_boundary,
        selection.claim_boundary,
        intervention.claim_boundary,
        closeout.claim_boundary,
    )
    return [] if len(set(claim.model_dump_json() for claim in claims)) == 1 else ["claim_boundary"]
