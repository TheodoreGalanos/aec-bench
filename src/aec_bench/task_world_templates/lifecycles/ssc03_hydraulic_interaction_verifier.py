# ABOUTME: Verifies the SSC-03 hydraulic interaction chain from immutable host-owned evidence.
# ABOUTME: Scores reporting and lineage correctness independently of whether physical criteria pass.

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError, field_validator

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
from aec_bench.task_world_templates.hydraulics import verify_hydraulic_world

ScenarioId = Literal["design-10yr", "major-100yr"]
ReadinessDecision = Literal["screening_ready", "not_screening_ready"]

SCENARIO_IDS: tuple[ScenarioId, ...] = ("design-10yr", "major-100yr")
SOURCE_REVISION_OPERATION_ID = "source-revision.current"
CALCULATION_OPERATION_IDS = tuple(
    operation_id
    for scenario_id in SCENARIO_IDS
    for operation_id in (
        f"hydrology.{scenario_id}",
        f"detention-outlet.{scenario_id}.declared-outlet",
        f"network-hgl.{scenario_id}.declared-tailwater",
    )
)
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
_AFFECTED_SCENARIOS: dict[str, set[str]] = {
    "administrative_no_op": set(),
    "major_idf_revision": {"major-100yr"},
    "outlet_geometry_revision": set(SCENARIO_IDS),
    "tailwater_revision": set(SCENARIO_IDS),
}
_REUSED_OPERATION_IDS: dict[str, set[str]] = {
    "administrative_no_op": set(CALCULATION_OPERATION_IDS),
    "major_idf_revision": {
        "hydrology.design-10yr",
        "detention-outlet.design-10yr.declared-outlet",
        "network-hgl.design-10yr.declared-tailwater",
    },
    "outlet_geometry_revision": {"hydrology.design-10yr", "hydrology.major-100yr"},
    "tailwater_revision": {"hydrology.design-10yr", "hydrology.major-100yr"},
}


class ClaimBoundary(StrictModel):
    evidence_class: Literal["benchmark_owned_synthetic_screening"]
    solver_fidelity: Literal["not_swmm_equivalent"]
    authority_status: Literal["no_authority_approval"]
    standards_status: Literal["no_standards_compliance_claim"]
    project_evidence_status: Literal["not_project_design_evidence"]
    model_evidence_status: Literal["no_model_performance_holdout_or_transfer_result"]
    learning_status: Literal["no_post_training_or_continual_learning_result"]


class ScenarioDecision(StrictModel):
    decision_id: NonEmptyStr
    scenario_id: ScenarioId
    hydrology_action_id: NonEmptyStr
    detention_action_id: NonEmptyStr
    hgl_action_id: NonEmptyStr
    hydraulic_run_id: NonEmptyStr
    screening_outcome: Literal["criteria_met", "criteria_not_met"]
    failed_criteria: tuple[NonEmptyStr, ...] = ()

    @field_validator("failed_criteria")
    @classmethod
    def validate_failed_criteria(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("failed criteria must be unique and sorted")
        return value


class DecisionSupersession(StrictModel):
    scenario_id: ScenarioId
    superseded_decision_id: NonEmptyStr
    replacement_decision_id: NonEmptyStr


class RunReference(StrictModel):
    selected_operation_action_id: NonEmptyStr
    canonical_detention_action_id: NonEmptyStr
    hydraulic_run_id: NonEmptyStr
    run_manifest_sha256: NonEmptyStr


class ReportReference(StrictModel):
    selected_operation_action_id: NonEmptyStr
    canonical_hgl_action_id: NonEmptyStr
    hydraulic_run_id: NonEmptyStr
    report_sha256: NonEmptyStr


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


@dataclass(frozen=True)
class ScenarioEvidence:
    scenario_id: ScenarioId
    hydrology_action_id: str
    detention_action_id: str
    hgl_action_id: str
    hydraulic_run_id: str
    failed_criteria: tuple[str, ...]
    run_reference: RunReference
    report_reference: ReportReference


def verify_hydraulic_interaction_lifecycle(
    package_dir: Path,
    run_dir: Path,
    *,
    variant_id: str,
) -> dict[str, Any]:
    """Verify the complete interaction from source identity through closeout propagation."""
    package = Path(package_dir)
    run = Path(run_dir)
    raw = load_validated_lifecycle_submissions(package, run)
    try:
        baseline = BaselineSubmission.model_validate(raw["baseline_analysis"])
        revision = RevisionSubmission.model_validate(raw["revision_analysis"])
        closeout = CloseoutSubmission.model_validate(raw["closeout_review"])
    except (KeyError, ValidationError) as exc:
        return _invalid_contract_result(str(exc))

    state = read_evidence_lifecycle_state(package, run)
    actions = {
        action.action_id: action
        for checkpoint in state["checkpoint_runs"]
        for action in (LifecycleOperationActionRecord.model_validate(item) for item in checkpoint["operation_actions"])
    }
    baseline_selected, baseline_selection_failures = _selected_actions(
        baseline.selected_operations,
        actions,
        checkpoint_id="baseline_analysis",
        expected_operation_ids=set(CALCULATION_OPERATION_IDS),
    )
    revision_selected, revision_selection_failures = _selected_actions(
        revision.selected_operations,
        actions,
        checkpoint_id="revision_analysis",
        expected_operation_ids=set(CALCULATION_OPERATION_IDS) | {SOURCE_REVISION_OPERATION_ID},
    )

    checkpoint_failures = _checkpoint_failures(baseline, revision, closeout)
    source_failures = _source_failures(package, baseline, revision, closeout, revision_selected, variant_id)
    operation_failures = baseline_selection_failures + revision_selection_failures
    operation_failures.extend(_transaction_failures(run, actions.values()))
    selective_failures = _selective_recomputation_failures(
        baseline_selected,
        revision_selected,
        variant_id,
    )

    baseline_evidence, baseline_evidence_failures = _scenario_evidence(
        package,
        run,
        baseline_selected,
    )
    revision_evidence, revision_evidence_failures = _scenario_evidence(
        package,
        run,
        revision_selected,
    )
    operation_failures.extend(baseline_evidence_failures)
    operation_failures.extend(revision_evidence_failures)

    expected_baseline_decisions = _expected_decisions(baseline_evidence, revision=False)
    affected = _AFFECTED_SCENARIOS[variant_id]
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
    run_failures = _mapping_failures("run_reference", closeout.run_reference, expected_runs)
    report_failures = _mapping_failures("report_reference", closeout.report_reference, expected_reports)
    readiness = _expected_readiness(expected_revision_decisions)
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
        "checkpoint_contract": _gate(checkpoint_failures),
        "source_revision_grounding": _gate(source_failures),
        "operation_evidence_integrity": _gate(operation_failures),
        "selective_recomputation": _gate(selective_failures),
        "affected_decision_update": _gate(affected_failures),
        "unaffected_decision_retention": _gate(unaffected_failures),
        "run_propagation": _gate(run_failures),
        "report_propagation": _gate(report_failures),
        "memo_propagation": _gate(memo_failures),
        "final_readiness": _gate(readiness_failures),
        "claim_boundary": _gate(claim_failures),
    }
    passed = all(gate["passed"] for gate in gates.values())
    reward = round(sum(float(gate["score"]) for gate in gates.values()) / len(gates), 4)
    return {
        "template_id": "hydraulic-interaction-lifecycle-review",
        "lifecycle_id": "ssc03.hydraulic-interaction-lifecycle",
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
        "template_id": "hydraulic-interaction-lifecycle-review",
        "lifecycle_id": "ssc03.hydraulic-interaction-lifecycle",
        "overall": "fail",
        "passed": False,
        "reward": 0.0,
        "gates": gates,
    }


def _selected_actions(
    selected: dict[str, str],
    actions: dict[str, LifecycleOperationActionRecord],
    *,
    checkpoint_id: str,
    expected_operation_ids: set[str],
) -> tuple[dict[str, LifecycleOperationActionRecord], list[str]]:
    failures: list[str] = []
    if set(selected) != expected_operation_ids:
        failures.append(f"{checkpoint_id}.selected_operations.keys")
    resolved: dict[str, LifecycleOperationActionRecord] = {}
    for operation_id, action_id in selected.items():
        action = actions.get(action_id)
        if action is None:
            failures.append(f"{checkpoint_id}.selected_operations.{operation_id}.missing_action")
            continue
        if action.operation_id != operation_id or action.checkpoint_id != checkpoint_id:
            failures.append(f"{checkpoint_id}.selected_operations.{operation_id}.identity")
            continue
        resolved[operation_id] = action
    return resolved, failures


def _transaction_failures(
    run: Path,
    actions: Iterable[LifecycleOperationActionRecord],
) -> list[str]:
    failures: list[str] = []
    for action in actions:
        transaction = run / "lifecycle_operations" / action.action_id
        expected_entries = {"request.json", "action.json", "committed.json"}
        if action.outcome == LifecycleOperationOutcome.COMPLETED:
            expected_entries.update({"result-manifest.json", "artifacts"})
        actual_entries = {path.name for path in transaction.iterdir()}
        if actual_entries != expected_entries:
            failures.append(f"{action.action_id}.transaction_inventory")
            continue
        expected_request = {
            "schema_version": "1",
            "action_id": action.action_id,
            "checkpoint_id": action.requested_checkpoint_id,
            "operation_id": action.operation_id,
            "reason": action.reason,
        }
        actual_request = _read_json(transaction / "request.json")
        supplied_source = actual_request.pop("visible_source_state_sha256", None)
        if actual_request != expected_request or not isinstance(supplied_source, str):
            failures.append(f"{action.action_id}.request")
        elif action.outcome != LifecycleOperationOutcome.REJECTED:
            if supplied_source != action.visible_source_state_before_sha256:
                failures.append(f"{action.action_id}.request_source")
        elif _rejection_projection_sha256(action.operation_id, supplied_source) != action.input_projection_sha256:
            failures.append(f"{action.action_id}.rejection_projection")
        if _read_json(transaction / "action.json") != action.model_dump(mode="json"):
            failures.append(f"{action.action_id}.action")
        if _read_json(transaction / "committed.json") != {
            "action_id": action.action_id,
            "status": "committed",
        }:
            failures.append(f"{action.action_id}.commit")
        if action.outcome != LifecycleOperationOutcome.COMPLETED:
            continue
        artifact_prefix = f"lifecycle_operations/{action.action_id}/artifacts/"
        artifact_sha256 = {
            artifact.path.removeprefix(artifact_prefix): artifact.sha256 for artifact in action.artifacts
        }
        if any(artifact.path == artifact.path.removeprefix(artifact_prefix) for artifact in action.artifacts):
            failures.append(f"{action.action_id}.artifact_path")
            continue
        expected_result = {
            "schema_version": "1",
            "action_id": action.action_id,
            "operation_id": action.operation_id,
            "input_projection_sha256": action.input_projection_sha256,
            "physical_source_state_sha256": action.physical_source_state_after_sha256,
            "visible_source_state_sha256": action.visible_source_state_after_sha256,
            "prerequisite_action_ids": list(action.prerequisite_action_ids),
            "artifact_sha256": artifact_sha256,
        }
        if _read_json(transaction / "result-manifest.json") != expected_result:
            failures.append(f"{action.action_id}.result_manifest")
    return failures


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
    baseline_source_sha = _sha256(
        package / "hidden" / "hydraulic" / "packages" / "baseline" / "source" / "source-state.json"
    )
    revision_source_sha = _sha256(
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
    variant_id: str,
) -> list[str]:
    failures: list[str] = []
    source = revision.get(SOURCE_REVISION_OPERATION_ID)
    if (
        source is None
        or source.outcome != LifecycleOperationOutcome.COMPLETED
        or source.disposition != LifecycleOperationDisposition.ACTIVATED
    ):
        failures.append("revision_analysis.source_revision.currentness")
    reused = _REUSED_OPERATION_IDS[variant_id]
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


def _scenario_evidence(
    package: Path,
    run: Path,
    selected: dict[str, LifecycleOperationActionRecord],
) -> tuple[dict[str, ScenarioEvidence], list[str]]:
    evidence: dict[str, ScenarioEvidence] = {}
    failures: list[str] = []
    for scenario_id in SCENARIO_IDS:
        operation_ids = (
            f"hydrology.{scenario_id}",
            f"detention-outlet.{scenario_id}.declared-outlet",
            f"network-hgl.{scenario_id}.declared-tailwater",
        )
        if any(operation_id not in selected for operation_id in operation_ids):
            failures.append(f"{scenario_id}.selected_operation_chain")
            continue
        hydrology_action = _canonical_action(selected[operation_ids[0]], run)
        detention_action = _canonical_action(selected[operation_ids[1]], run)
        hgl_action = _canonical_action(selected[operation_ids[2]], run)
        try:
            scenario_evidence = _verify_scenario_evidence(
                package,
                run,
                scenario_id,
                selected[operation_ids[1]],
                selected[operation_ids[2]],
                hydrology_action,
                detention_action,
                hgl_action,
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            failures.append(f"{scenario_id}.integrity:{exc}")
            continue
        evidence[scenario_id] = scenario_evidence
    return evidence, failures


def _canonical_action(
    selected: LifecycleOperationActionRecord,
    run: Path,
) -> LifecycleOperationActionRecord:
    action_id = selected.retained_from_action_id or selected.action_id
    return LifecycleOperationActionRecord.model_validate(
        _read_json(run / "lifecycle_operations" / action_id / "action.json")
    )


def _verify_scenario_evidence(
    package: Path,
    run: Path,
    scenario_id: ScenarioId,
    selected_detention: LifecycleOperationActionRecord,
    selected_hgl: LifecycleOperationActionRecord,
    hydrology_action: LifecycleOperationActionRecord,
    detention_action: LifecycleOperationActionRecord,
    hgl_action: LifecycleOperationActionRecord,
) -> ScenarioEvidence:
    detention_root = run / "lifecycle_operations" / detention_action.action_id / "artifacts"
    hgl_root = run / "lifecycle_operations" / hgl_action.action_id / "artifacts"
    hydraulic_run = detention_root / "hydraulic-run"
    hydraulic_package = _package_for_physical_source(package, detention_action.physical_source_state_after_sha256)
    verification = verify_hydraulic_world(hydraulic_package, hydraulic_run)
    result = _read_json(hydraulic_run / "results.json")
    time_series = _read_json(hydraulic_run / "timeseries.json")
    hydrology = _read_json(run / "lifecycle_operations" / hydrology_action.action_id / "artifacts" / "hydrology.json")
    detention = _read_json(detention_root / "detention-outlet.json")
    hgl = _read_json(hgl_root / "network-hgl.json")
    if result["scenario_id"] != scenario_id or hydrology["scenario_id"] != scenario_id:
        raise ValueError("scenario identity mismatch")
    expected_hydrograph = [
        {"time_s": step["time_s"], "inflow_m3_s": step["total_inflow_m3_s"]} for step in time_series["steps"]
    ]
    if (
        hydrology["peak_total_inflow_m3_s"] != result["peak_total_inflow_m3_s"]
        or hydrology["hydrograph"] != expected_hydrograph
    ):
        raise ValueError("hydrology projection mismatch")
    criteria = dict(detention["criteria"]) | dict(hgl["criteria"])
    expected_criteria = {
        criterion: gate.passed for criterion, gate in verification.gates.items() if criterion != "reported_criteria"
    }
    if criteria != expected_criteria:
        raise ValueError("stage criteria do not reconcile with PR18 verification")
    if detention["hydraulic_run_id"] != result["run_id"] or hgl["hydraulic_run_id"] != result["run_id"]:
        raise ValueError("stage run identity mismatch")
    report = hgl_root / "report.md"
    if report.read_bytes() != (hydraulic_run / "report.md").read_bytes():
        raise ValueError("HGL report does not match the coupled run")
    failed = tuple(sorted(criterion for criterion, passed in criteria.items() if not passed))
    return ScenarioEvidence(
        scenario_id=scenario_id,
        hydrology_action_id=hydrology_action.action_id,
        detention_action_id=detention_action.action_id,
        hgl_action_id=hgl_action.action_id,
        hydraulic_run_id=str(result["run_id"]),
        failed_criteria=failed,
        run_reference=RunReference(
            selected_operation_action_id=selected_detention.action_id,
            canonical_detention_action_id=detention_action.action_id,
            hydraulic_run_id=str(result["run_id"]),
            run_manifest_sha256=_sha256(hydraulic_run / "run-manifest.json"),
        ),
        report_reference=ReportReference(
            selected_operation_action_id=selected_hgl.action_id,
            canonical_hgl_action_id=hgl_action.action_id,
            hydraulic_run_id=str(result["run_id"]),
            report_sha256=_sha256(report),
        ),
    )


def _package_for_physical_source(package: Path, source_sha256: str) -> Path:
    candidates = (
        package / "hidden" / "hydraulic" / "packages" / "baseline",
        package / "hidden" / "hydraulic" / "packages" / "revision",
    )
    for candidate in candidates:
        if _sha256(candidate / "source" / "source-state.json") == source_sha256:
            return candidate
    raise ValueError("operation physical source does not match an embedded PR18 package")


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


def _mapping_failures(label: str, actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    return [] if actual == expected else [f"closeout_review.{label}"]


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


def _expected_readiness(decisions: dict[str, ScenarioDecision]) -> ReadinessDecision:
    return (
        "not_screening_ready"
        if any(item.screening_outcome == "criteria_not_met" for item in decisions.values())
        else "screening_ready"
    )


def _readiness_failures(
    baseline: BaselineSubmission,
    revision: RevisionSubmission,
    closeout: CloseoutSubmission,
    baseline_decisions: dict[str, ScenarioDecision],
    revision_decisions: dict[str, ScenarioDecision],
) -> list[str]:
    failures: list[str] = []
    if baseline.readiness_decision != _expected_readiness(baseline_decisions):
        failures.append("baseline_analysis.readiness_decision")
    expected_revision = _expected_readiness(revision_decisions)
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


def _gate(failures: list[str]) -> dict[str, Any]:
    unique = sorted(set(failures))
    return {"passed": not unique, "score": 1.0 if not unique else 0.0, "failures": unique}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rejection_projection_sha256(operation_id: str, supplied_visible_source_sha256: str) -> str:
    payload = json.dumps(
        {
            "schema_version": "1",
            "operation_id": operation_id,
            "supplied_visible_source_sha256": supplied_visible_source_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
