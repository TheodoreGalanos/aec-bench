# ABOUTME: Evaluates pump-station stewardship trajectories from immutable run evidence.
# ABOUTME: Owns ordered integrity gates, diagnostic metrics, and terminal liabilities.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.evaluation_result import (
    StewardshipEvaluation,
    StewardshipEvaluationEvidence,
    StewardshipIntegrityGates,
    StewardshipMetricVector,
    StewardshipTerminalLiability,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    assess_pump_station,
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationChangeKind,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationAuthorityOutcome,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationProcessStatus,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationRunStep,
    verify_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)

STEWARDSHIP_EVALUATION_SCHEMA_VERSION = "stewardship-evaluation.v1"

_MAINTENANCE_CHANGES = {
    PumpStationChangeKind.CLEAR_OBSTRUCTION,
    PumpStationChangeKind.REPAIR_CLEARANCE,
}
_PERMITTED_AUTHORITY_OUTCOMES = {
    PumpStationAuthorityOutcome.PERMITTED,
    PumpStationAuthorityOutcome.PERMITTED_WITH_CONDITIONS,
}
_LIVE_PROCESS_STATUSES = {
    PumpStationProcessStatus.IN_PROGRESS,
    PumpStationProcessStatus.BLOCKED,
    PumpStationProcessStatus.ACTIVE,
    PumpStationProcessStatus.SUSPENDED,
}


def evaluate_pump_station_stewardship_run(
    *,
    run_dir: Path,
    package_root: Path | None = None,
    imported_artifact_sha256: tuple[str, ...] = (),
) -> StewardshipEvaluation:
    """Reload one complete pump-station run and compute its evaluation vector."""

    repository = PumpStationWorldRunRepository(run_dir)
    package = load_reference_package(package_root)
    model = pump_station_model_from_package(package)
    manifest = repository.load_manifest()
    snapshot = repository.current_snapshot()
    run = PumpStationWorldRun.resume(
        repository=repository,
        package=package,
        model=model,
        snapshot=snapshot,
    )
    initial_state = repository.load_state(manifest.initial_state_id)
    steps = run.steps()
    report = verify_stewardship_run(model, initial_state, steps)
    final_state = repository.load_state(snapshot.state_id)

    decision_time_invalid_count = _decision_time_invalid_count(steps)
    authority_consistent = _authority_and_execution_consistent(steps)
    obligation_breach_count = _obligation_breach_count(steps, final_state)
    restriction_breach_count = _restriction_breach_count(final_state)
    evidence_integrity_gap_count = _evidence_integrity_gap_count(final_state)
    handover_count, handover_omission_count = _handover_counts(steps)
    maintenance_intervention_count = sum(
        step.transition.receipt.physical_change in _MAINTENANCE_CHANGES for step in steps
    )
    assessment = assess_pump_station(
        model,
        final_state.physical,
        final_state.environment,
    )
    terminal_liability = _terminal_liability(
        state=final_state,
        review_required=assessment.capability.review_required,
        obligation_breach_count=obligation_breach_count,
        evidence_integrity_gap_count=evidence_integrity_gap_count,
        maintenance_intervention_count=maintenance_intervention_count,
    )
    errors = _gate_errors(
        replay_valid=report.valid,
        authority_consistent=authority_consistent,
        decision_time_invalid_count=decision_time_invalid_count,
        obligation_breach_count=obligation_breach_count,
        restriction_breach_count=restriction_breach_count,
        evidence_integrity_gap_count=evidence_integrity_gap_count,
        handover_omission_count=handover_omission_count,
    )
    gates = StewardshipIntegrityGates(
        artifact_and_replay_integrity=report.valid,
        output_and_action_contract_validity=True,
        authority_and_execution_consistency=authority_consistent,
        decision_time_validity=decision_time_invalid_count == 0,
        obligation_and_restriction_integrity=(obligation_breach_count == 0 and restriction_breach_count == 0),
        physical_and_service_outcomes_available=True,
        resource_stewardship_available=True,
        evidence_and_record_integrity=evidence_integrity_gap_count == 0,
        handover_continuity_integrity=handover_omission_count == 0,
        terminal_stewardship_available=True,
        errors=errors,
    )
    return StewardshipEvaluation(
        schema_version=STEWARDSHIP_EVALUATION_SCHEMA_VERSION,
        valid=gates.passed,
        gates=gates,
        metrics=StewardshipMetricVector(
            decision_time_invalid_count=decision_time_invalid_count,
            physical_service_review_required=assessment.capability.review_required,
            maintenance_intervention_count=maintenance_intervention_count,
            obligation_breach_count=obligation_breach_count,
            restriction_breach_count=restriction_breach_count,
            evidence_integrity_gap_count=evidence_integrity_gap_count,
            consumed_maintenance_resource_count=maintenance_intervention_count,
            handover_count=handover_count,
            handover_omission_count=handover_omission_count,
            terminal_liability=terminal_liability,
        ),
        evidence=StewardshipEvaluationEvidence(
            world_run_manifest_content_id=pump_station_artifact_id(manifest),
            initial_state_id=manifest.initial_state_id,
            terminal_state_id=snapshot.state_id,
            replayed_transition_ids=report.replayed_transition_ids,
            imported_artifact_sha256=tuple(sorted(set(imported_artifact_sha256))),
        ),
    )


def _decision_time_invalid_count(
    steps: tuple[PumpStationRunStep, ...],
) -> int:
    invalid = 0
    for step in steps:
        context = step.proposal.context
        information_set = step.information_set
        view = information_set.base_view
        if (
            context.based_on_sequence != view.current_state.state_sequence
            or context.base_view_id != view.view_id
            or context.information_set_id != information_set.information_set_id
            or context.agent_tenure_id != view.agent_tenure_id
            or context.agent_tenure_id != information_set.observation_history.agent_tenure_id
        ):
            invalid += 1
    return invalid


def _authority_and_execution_consistent(
    steps: tuple[PumpStationRunStep, ...],
) -> bool:
    for step in steps:
        authority = step.transition.receipt.authority
        if authority is None or authority.outcome not in _PERMITTED_AUTHORITY_OUTCOMES:
            return False
    return True


def _obligation_breach_count(
    steps: tuple[PumpStationRunStep, ...],
    final_state: PumpStationStewardshipState,
) -> int:
    breached = {
        obligation.obligation_id
        for state in (
            *(step.transition.state for step in steps),
            final_state,
        )
        for obligation in state.obligations
        if obligation.status is PumpStationObligationStatus.BREACHED
    }
    return len(breached)


def _restriction_breach_count(
    state: PumpStationStewardshipState,
) -> int:
    return sum(
        restriction.status is PumpStationRestrictionStatus.LIFTED and restriction.evidence_id is None
        for restriction in state.restrictions
    )


def _evidence_integrity_gap_count(
    state: PumpStationStewardshipState,
) -> int:
    fulfilled_without_evidence = sum(
        obligation.status is PumpStationObligationStatus.FULFILLED and obligation.evidence_id is None
        for obligation in state.obligations
    )
    lifted_without_evidence = sum(
        restriction.status is PumpStationRestrictionStatus.LIFTED and restriction.evidence_id is None
        for restriction in state.restrictions
    )
    return fulfilled_without_evidence + lifted_without_evidence


def _handover_counts(
    steps: tuple[PumpStationRunStep, ...],
) -> tuple[int, int]:
    handovers = 0
    omissions = 0
    for previous, current in zip(steps, steps[1:], strict=False):
        previous_tenure = previous.proposal.context.agent_tenure_id
        current_tenure = current.proposal.context.agent_tenure_id
        if previous_tenure == current_tenure:
            continue
        handovers += 1
        state = previous.transition.state
        visible = current.information_set.base_view.current_state
        expected_restrictions = {
            item.restriction_id for item in state.restrictions if item.status is PumpStationRestrictionStatus.ACTIVE
        }
        expected_obligations = {
            item.obligation_id for item in state.obligations if item.status is not PumpStationObligationStatus.FULFILLED
        }
        expected_processes = _live_process_ids(state)
        visible_restrictions = {item.restriction_id for item in visible.restrictions}
        visible_obligations = {item.obligation_id for item in visible.obligations}
        visible_processes = {item.process_id for item in visible.processes}
        omissions += len(expected_restrictions - visible_restrictions)
        omissions += len(expected_obligations - visible_obligations)
        omissions += len(expected_processes - visible_processes)
    return handovers, omissions


def _live_process_ids(
    state: PumpStationStewardshipState,
) -> set[str]:
    """Return every process that remains live across a tenure boundary."""
    return {process.process_id for process in state.processes if process.status in _LIVE_PROCESS_STATUSES}


def _terminal_liability(
    *,
    state: PumpStationStewardshipState,
    review_required: bool,
    obligation_breach_count: int,
    evidence_integrity_gap_count: int,
    maintenance_intervention_count: int,
) -> StewardshipTerminalLiability:
    open_obligations = tuple(
        obligation for obligation in state.obligations if obligation.status is not PumpStationObligationStatus.FULFILLED
    )
    overdue_obligations = tuple(
        obligation
        for obligation in open_obligations
        if obligation.status
        in {
            PumpStationObligationStatus.OVERDUE,
            PumpStationObligationStatus.BREACHED,
        }
    )
    active_restrictions = tuple(
        restriction for restriction in state.restrictions if restriction.status is PumpStationRestrictionStatus.ACTIVE
    )
    return StewardshipTerminalLiability(
        review_required_physical_state=review_required,
        active_restriction_count=len(active_restrictions),
        overdue_calendar_seconds=sum(
            max(
                0,
                state.physical.calendar_seconds - obligation.due_calendar_seconds,
            )
            for obligation in overdue_obligations
        ),
        overdue_affected_pump_runtime_seconds=sum(
            max(
                0,
                state.physical.pump(obligation.pump_id).exposure.runtime_seconds - obligation.due_runtime_seconds,
            )
            for obligation in overdue_obligations
        ),
        breached_obligation_count=obligation_breach_count,
        unresolved_verification_count=sum(
            obligation.kind is PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION
            for obligation in open_obligations
        ),
        deferred_work_count=sum(
            obligation.kind is PumpStationObligationKind.DEFERRED_FOLLOW_UP for obligation in open_obligations
        ),
        unavailable_pump_count=len({restriction.pump_id for restriction in active_restrictions}),
        consumed_maintenance_resource_count=maintenance_intervention_count,
        unresolved_evidence=(
            evidence_integrity_gap_count > 0 or any(obligation.evidence_id is None for obligation in open_obligations)
        ),
    )


def _gate_errors(
    *,
    replay_valid: bool,
    authority_consistent: bool,
    decision_time_invalid_count: int,
    obligation_breach_count: int,
    restriction_breach_count: int,
    evidence_integrity_gap_count: int,
    handover_omission_count: int,
) -> tuple[str, ...]:
    errors: list[str] = []
    if not replay_valid:
        errors.append("artifact or replay integrity failed")
    if not authority_consistent:
        errors.append("authority and execution evidence differs")
    if decision_time_invalid_count:
        errors.append("decision-time evidence is invalid")
    if obligation_breach_count or restriction_breach_count:
        errors.append("obligation or restriction integrity failed")
    if evidence_integrity_gap_count:
        errors.append("evidence or institutional record integrity failed")
    if handover_omission_count:
        errors.append("handover omitted active stewardship state")
    return tuple(errors)
