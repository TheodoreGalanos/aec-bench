# ABOUTME: Verifies the hydraulic interaction chain from immutable host-owned evidence.
# ABOUTME: Scores reporting and lineage correctness independently of whether physical criteria pass.

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.lifecycles.runtime.lifecycle import (
    load_validated_lifecycle_submissions,
    read_lifecycle,
)
from aec_bench.lifecycles.runtime.state import (
    LifecycleOperationActionRecord,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
)
from aec_bench.lifecycles.stormwater_design.hydraulic_evidence import (
    CALCULATION_OPERATION_IDS,
    SCENARIO_IDS,
    ClaimBoundary,
    DecisionSupersession,
    ReadinessDecision,
    ReportReference,
    RunReference,
    ScenarioDecision,
    ScenarioEvidence,
    expected_readiness,
    file_sha256,
    load_scenario_evidence,
    mapping_failures,
    operation_transaction_failures,
    select_operation_actions,
    verification_gate,
)

SOURCE_REVISION_OPERATION_ID = "source-revision.current"
GATE_IDS = (
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
)


class BaselineSubmission(StrictModel):
    checkpoint_id: Literal["baseline_analysis"]
    visible_source_state_sha256: NonEmptyStr
    selected_operations: dict[NonEmptyStr, NonEmptyStr]
    accepted_decisions: tuple[ScenarioDecision, ...]
    readiness_decision: ReadinessDecision
    claim_boundary: ClaimBoundary


class RevisionSubmission(StrictModel):
    checkpoint_id: Literal["revision_analysis"]
    revision_id: NonEmptyStr
    visible_source_state_sha256: NonEmptyStr
    selected_operations: dict[NonEmptyStr, NonEmptyStr]
    accepted_decisions: tuple[ScenarioDecision, ...]
    supersession_lineage: tuple[DecisionSupersession, ...]
    readiness_decision: ReadinessDecision
    claim_boundary: ClaimBoundary


class CloseoutMemo(StrictModel):
    visible_source_state_sha256: NonEmptyStr
    run_reference: dict[NonEmptyStr, RunReference]
    report_reference: dict[NonEmptyStr, ReportReference]
    decision_ids: dict[NonEmptyStr, NonEmptyStr]
    supersession_lineage: tuple[DecisionSupersession, ...]
    readiness_decision: ReadinessDecision
    claim_boundary: ClaimBoundary


class CloseoutSubmission(StrictModel):
    checkpoint_id: Literal["closeout_review"]
    visible_source_state_sha256: NonEmptyStr
    selected_operations: dict[NonEmptyStr, NonEmptyStr]
    run_reference: dict[NonEmptyStr, RunReference]
    report_reference: dict[NonEmptyStr, ReportReference]
    memo: CloseoutMemo
    accepted_decisions: tuple[ScenarioDecision, ...]
    supersession_lineage: tuple[DecisionSupersession, ...]
    readiness_decision: ReadinessDecision
    claim_boundary: ClaimBoundary


def verify_hydraulic_interaction_lifecycle(
    package_dir: Path,
    run_dir: Path,
    *,
    variant_id: str,
) -> dict[str, Any]:
    """Verify the complete interaction from source identity through closeout propagation."""
    package = Path(package_dir)
    run = Path(run_dir)
    from aec_bench.lifecycles.stormwater_design.hydraulic_review import build_hydraulic_operation_resolver

    operation_resolver = build_hydraulic_operation_resolver(package, run)
    raw = load_validated_lifecycle_submissions(package, run, operation_resolver=operation_resolver)
    try:
        baseline = BaselineSubmission.model_validate(raw["baseline_analysis"])
        revision = RevisionSubmission.model_validate(raw["revision_analysis"])
        closeout = CloseoutSubmission.model_validate(raw["closeout_review"])
    except (KeyError, ValidationError) as exc:
        return _invalid_contract_result(str(exc))

    state = read_lifecycle(package, run, operation_resolver=operation_resolver)
    actions = {
        action.action_id: action
        for checkpoint in state["checkpoint_runs"]
        for action in (LifecycleOperationActionRecord.model_validate(item) for item in checkpoint["operation_actions"])
    }
    baseline_selected, baseline_selection_failures = select_operation_actions(
        baseline.selected_operations,
        actions,
        checkpoint_id="baseline_analysis",
        expected_operation_ids=set(CALCULATION_OPERATION_IDS),
    )
    revision_selected, revision_selection_failures = select_operation_actions(
        revision.selected_operations,
        actions,
        checkpoint_id="revision_analysis",
        expected_operation_ids=set(CALCULATION_OPERATION_IDS) | {SOURCE_REVISION_OPERATION_ID},
    )

    checkpoint_failures = _checkpoint_failures(baseline, revision, closeout)
    source_failures = _source_failures(package, baseline, revision, closeout, revision_selected, variant_id)
    operation_failures = baseline_selection_failures + revision_selection_failures
    operation_failures.extend(operation_transaction_failures(run, actions.values()))
    source_action = revision_selected.get(SOURCE_REVISION_OPERATION_ID)
    reused = (
        operation_resolver.retained_calculation_ids(tuple(baseline_selected.values()), source_action)
        if source_action is not None
        else set()
    )
    selective_failures = _selective_recomputation_failures(
        baseline_selected,
        revision_selected,
        reused,
    )

    baseline_evidence, baseline_evidence_failures = load_scenario_evidence(
        package,
        run,
        baseline_selected,
    )
    revision_evidence, revision_evidence_failures = load_scenario_evidence(
        package,
        run,
        revision_selected,
    )
    operation_failures.extend(baseline_evidence_failures)
    operation_failures.extend(revision_evidence_failures)

    expected_baseline_decisions = _expected_decisions(baseline_evidence, revision=False)
    affected: set[str] = {
        scenario_id
        for scenario_id in SCENARIO_IDS
        if any(scenario_id in operation_id and operation_id not in reused for operation_id in CALCULATION_OPERATION_IDS)
    }
    expected_revision_decisions: dict[str, ScenarioDecision] = {
        scenario_id: (
            _expected_decision(revision_evidence[scenario_id], revision=True)
            if scenario_id in affected
            else expected_baseline_decisions[scenario_id]
        )
        for scenario_id in SCENARIO_IDS
        if scenario_id in baseline_evidence and scenario_id in revision_evidence
    }
    expected_lineage = tuple(
        DecisionSupersession(
            scenario_id=scenario_id,
            superseded_decision_id=f"decision.{scenario_id}.baseline",
            replacement_decision_id=f"decision.{scenario_id}.revision",
        )
        for scenario_id in SCENARIO_IDS
        if scenario_id in affected
    )
    actual_baseline_decisions: dict[str, ScenarioDecision] = {
        item.scenario_id: item for item in baseline.accepted_decisions
    }
    actual_revision_decisions: dict[str, ScenarioDecision] = {
        item.scenario_id: item for item in revision.accepted_decisions
    }

    affected_failures = _affected_decision_failures(
        actual_baseline_decisions,
        actual_revision_decisions,
        expected_baseline_decisions,
        expected_revision_decisions,
        revision.supersession_lineage,
        expected_lineage,
        affected,
    )
    unaffected_failures = _unaffected_decision_failures(
        actual_baseline_decisions,
        actual_revision_decisions,
        expected_baseline_decisions,
        affected,
    )
    expected_runs: dict[str, RunReference] = {
        scenario_id: evidence.run_reference for scenario_id, evidence in revision_evidence.items()
    }
    expected_reports: dict[str, ReportReference] = {
        scenario_id: evidence.report_reference for scenario_id, evidence in revision_evidence.items()
    }
    run_failures = mapping_failures("run_reference", closeout.run_reference, expected_runs)
    report_failures = mapping_failures("report_reference", closeout.report_reference, expected_reports)
    readiness = expected_readiness(expected_revision_decisions)
    memo_failures = _memo_failures(
        closeout,
        expected_runs,
        expected_reports,
        expected_revision_decisions,
        expected_lineage,
        readiness,
    )
    readiness_failures = _readiness_failures(
        baseline,
        revision,
        closeout,
        expected_baseline_decisions,
        expected_revision_decisions,
    )
    claim_failures = _claim_failures(baseline, revision, closeout)

    gates = {
        "checkpoint_contract": verification_gate(checkpoint_failures),
        "source_revision_grounding": verification_gate(source_failures),
        "operation_evidence_integrity": verification_gate(operation_failures),
        "selective_recomputation": verification_gate(selective_failures),
        "affected_decision_update": verification_gate(affected_failures),
        "unaffected_decision_retention": verification_gate(unaffected_failures),
        "run_propagation": verification_gate(run_failures),
        "report_propagation": verification_gate(report_failures),
        "memo_propagation": verification_gate(memo_failures),
        "final_readiness": verification_gate(readiness_failures),
        "claim_boundary": verification_gate(claim_failures),
    }
    passed = all(gate["passed"] for gate in gates.values())
    reward = round(sum(float(gate["score"]) for gate in gates.values()) / len(gates), 4)
    return {
        "template_id": "hydraulic-interaction-lifecycle-review",
        "lifecycle_id": "hydraulic-interaction-review",
        "overall": "pass" if passed else "fail",
        "passed": passed,
        "reward": reward,
        "gates": gates,
    }


def _invalid_contract_result(message: str) -> dict[str, Any]:
    gates = {
        gate_id: verification_gate([message if gate_id == "checkpoint_contract" else "checkpoint contract unavailable"])
        for gate_id in GATE_IDS
    }
    return {
        "template_id": "hydraulic-interaction-lifecycle-review",
        "lifecycle_id": "hydraulic-interaction-review",
        "overall": "fail",
        "passed": False,
        "reward": 0.0,
        "gates": gates,
    }


def _checkpoint_failures(
    baseline: BaselineSubmission,
    revision: RevisionSubmission,
    closeout: CloseoutSubmission,
) -> list[str]:
    failures: list[str] = []
    if len(baseline.accepted_decisions) != len(SCENARIO_IDS) or {
        item.scenario_id for item in baseline.accepted_decisions
    } != set(SCENARIO_IDS):
        failures.append("baseline_analysis.accepted_decisions.scenarios")
    if len(revision.accepted_decisions) != len(SCENARIO_IDS) or {
        item.scenario_id for item in revision.accepted_decisions
    } != set(SCENARIO_IDS):
        failures.append("revision_analysis.accepted_decisions.scenarios")
    if len(closeout.accepted_decisions) != len(SCENARIO_IDS) or {
        item.scenario_id for item in closeout.accepted_decisions
    } != set(SCENARIO_IDS):
        failures.append("closeout_review.accepted_decisions.scenarios")
    if closeout.selected_operations != revision.selected_operations:
        failures.append("closeout_review.selected_operations")
    if closeout.accepted_decisions != revision.accepted_decisions:
        failures.append("closeout_review.accepted_decisions")
    if closeout.supersession_lineage != revision.supersession_lineage:
        failures.append("closeout_review.supersession_lineage")
    return failures


def _source_failures(
    package: Path,
    baseline: BaselineSubmission,
    revision: RevisionSubmission,
    closeout: CloseoutSubmission,
    revision_selected: dict[str, LifecycleOperationActionRecord],
    variant_id: str,
) -> list[str]:
    failures: list[str] = []
    source_action = revision_selected.get(SOURCE_REVISION_OPERATION_ID)
    if source_action is None:
        return ["revision_analysis.source_revision_action"]
    baseline_source_sha = file_sha256(
        package / "hidden" / "hydraulic" / "packages" / "baseline" / "source" / "source-state.json"
    )
    revision_source_sha = file_sha256(
        package / "hidden" / "hydraulic" / "packages" / "revision" / "source" / "source-state.json"
    )
    if revision.revision_id != variant_id:
        failures.append("revision_analysis.revision_id")
    if baseline.visible_source_state_sha256 != source_action.visible_source_state_before_sha256:
        failures.append("baseline_analysis.visible_source_state_sha256")
    if revision.visible_source_state_sha256 != source_action.visible_source_state_after_sha256:
        failures.append("revision_analysis.visible_source_state_sha256")
    if closeout.visible_source_state_sha256 != revision.visible_source_state_sha256:
        failures.append("closeout_review.visible_source_state_sha256")
    if source_action.physical_source_state_before_sha256 != baseline_source_sha:
        failures.append("revision_analysis.physical_source_before")
    if source_action.physical_source_state_after_sha256 != revision_source_sha:
        failures.append("revision_analysis.physical_source_after")
    if (baseline_source_sha == revision_source_sha) != (variant_id == "administrative_no_op"):
        failures.append("revision_analysis.physical_change_topology")
    return failures


def _selective_recomputation_failures(
    baseline: dict[str, LifecycleOperationActionRecord],
    revision: dict[str, LifecycleOperationActionRecord],
    reused: set[str],
) -> list[str]:
    failures: list[str] = []
    source = revision.get(SOURCE_REVISION_OPERATION_ID)
    if (
        source is None
        or source.outcome != LifecycleOperationOutcome.COMPLETED
        or source.disposition != LifecycleOperationDisposition.ACTIVATED
    ):
        failures.append("revision_analysis.source_revision.currentness")
    for operation_id in CALCULATION_OPERATION_IDS:
        baseline_action = baseline.get(operation_id)
        revision_action = revision.get(operation_id)
        if baseline_action is None or revision_action is None:
            failures.append(f"revision_analysis.{operation_id}.missing")
            continue
        if operation_id in reused:
            if (
                revision_action.outcome != LifecycleOperationOutcome.ALREADY_CURRENT
                or revision_action.disposition != LifecycleOperationDisposition.REUSED
                or revision_action.retained_from_action_id != baseline_action.action_id
                or revision_action.input_projection_sha256 != baseline_action.input_projection_sha256
                or revision_action.budget_consumed != 0
            ):
                failures.append(f"revision_analysis.{operation_id}.reuse")
        elif (
            revision_action.outcome != LifecycleOperationOutcome.COMPLETED
            or revision_action.disposition != LifecycleOperationDisposition.COMPUTED
            or revision_action.retained_from_action_id is not None
            or revision_action.input_projection_sha256 == baseline_action.input_projection_sha256
            or revision_action.budget_consumed != 1
        ):
            failures.append(f"revision_analysis.{operation_id}.recompute")
    return failures


def _expected_decisions(
    evidence: dict[str, ScenarioEvidence],
    *,
    revision: bool,
) -> dict[str, ScenarioDecision]:
    return {scenario_id: _expected_decision(item, revision=revision) for scenario_id, item in evidence.items()}


def _expected_decision(evidence: ScenarioEvidence, *, revision: bool) -> ScenarioDecision:
    phase = "revision" if revision else "baseline"
    return ScenarioDecision(
        decision_id=f"decision.{evidence.scenario_id}.{phase}",
        scenario_id=evidence.scenario_id,
        hydrology_action_id=evidence.hydrology_action_id,
        detention_action_id=evidence.detention_action_id,
        hgl_action_id=evidence.hgl_action_id,
        hydraulic_run_id=evidence.hydraulic_run_id,
        screening_outcome="criteria_not_met" if evidence.failed_criteria else "criteria_met",
        failed_criteria=evidence.failed_criteria,
    )


def _affected_decision_failures(
    baseline: dict[str, ScenarioDecision],
    actual: dict[str, ScenarioDecision],
    expected_baseline: dict[str, ScenarioDecision],
    expected: dict[str, ScenarioDecision],
    lineage: tuple[DecisionSupersession, ...],
    expected_lineage: tuple[DecisionSupersession, ...],
    affected: set[str],
) -> list[str]:
    failures = [
        f"revision_analysis.accepted_decisions.{scenario_id}"
        for scenario_id in affected
        if baseline.get(scenario_id) != expected_baseline.get(scenario_id)
        or actual.get(scenario_id) != expected.get(scenario_id)
    ]
    if lineage != expected_lineage:
        failures.append("revision_analysis.supersession_lineage")
    return failures


def _unaffected_decision_failures(
    baseline: dict[str, ScenarioDecision],
    revision: dict[str, ScenarioDecision],
    expected: dict[str, ScenarioDecision],
    affected: set[str],
) -> list[str]:
    return [
        f"revision_analysis.accepted_decisions.{scenario_id}.retention"
        for scenario_id in SCENARIO_IDS
        if scenario_id not in affected
        and (
            baseline.get(scenario_id) != expected.get(scenario_id)
            or revision.get(scenario_id) != baseline.get(scenario_id)
        )
    ]


def _memo_failures(
    closeout: CloseoutSubmission,
    runs: dict[str, RunReference],
    reports: dict[str, ReportReference],
    decisions: dict[str, ScenarioDecision],
    lineage: tuple[DecisionSupersession, ...],
    readiness: ReadinessDecision,
) -> list[str]:
    expected = CloseoutMemo(
        visible_source_state_sha256=closeout.visible_source_state_sha256,
        run_reference=runs,
        report_reference=reports,
        decision_ids={scenario_id: decision.decision_id for scenario_id, decision in decisions.items()},
        supersession_lineage=lineage,
        readiness_decision=readiness,
        claim_boundary=closeout.claim_boundary,
    )
    return [] if closeout.memo == expected else ["closeout_review.memo"]


def _readiness_failures(
    baseline: BaselineSubmission,
    revision: RevisionSubmission,
    closeout: CloseoutSubmission,
    baseline_decisions: dict[str, ScenarioDecision],
    revision_decisions: dict[str, ScenarioDecision],
) -> list[str]:
    failures: list[str] = []
    if baseline.readiness_decision != expected_readiness(baseline_decisions):
        failures.append("baseline_analysis.readiness_decision")
    expected_revision = expected_readiness(revision_decisions)
    if revision.readiness_decision != expected_revision:
        failures.append("revision_analysis.readiness_decision")
    if closeout.readiness_decision != expected_revision:
        failures.append("closeout_review.readiness_decision")
    return failures


def _claim_failures(
    baseline: BaselineSubmission,
    revision: RevisionSubmission,
    closeout: CloseoutSubmission,
) -> list[str]:
    return [] if baseline.claim_boundary == revision.claim_boundary == closeout.claim_boundary else ["claim_boundary"]
