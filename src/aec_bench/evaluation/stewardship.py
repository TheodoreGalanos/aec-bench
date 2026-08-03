# ABOUTME: Evaluates pump-station stewardship trajectories from immutable run evidence.
# ABOUTME: Owns ordered integrity gates, diagnostic metrics, and terminal liabilities.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

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
    PumpStationCoupledModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationAuthorityOutcome,
    PumpStationCoupledStewardshipState,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationProcessStatus,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationConservationReport,
    PumpStationRunStep,
    PumpStationRunStepV4,
    verify_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationActorView,
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
STEWARDSHIP_EVALUATION_SCHEMA_VERSION_V2 = "stewardship-evaluation.v2"

type PumpStationReferenceRun = PumpStationWorldRun[
    PumpStationCoupledModel,
    PumpStationCoupledStewardshipState,
]

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


@dataclass(frozen=True, slots=True)
class PumpStationSemanticActionOutcome:
    """Transport-neutral meaning of one actor or host-control step."""

    kind: str
    target_id: str | None
    backlog_semantic_key: tuple[str, str, str, int] | None
    authority_outcome: str
    execution_status: str


@dataclass(frozen=True, slots=True)
class PumpStationSemanticTerminalState:
    """Transport-neutral terminal coupled-world meaning."""

    calendar_seconds: int
    pump_exposure: tuple[tuple[str, int, int], ...]
    pump_modes: tuple[tuple[str, str], ...]
    assignment_pump_ids: tuple[str, ...]
    service_running_pump_ids: tuple[str, ...]
    test_running_pump_ids: tuple[str, ...]
    resource_quantities: tuple[tuple[str, int, int], ...]
    work_meanings: tuple[tuple[tuple[str, str, str, int], str], ...]
    active_liability_meanings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PumpStationSemanticEvaluation:
    """Transport-neutral projection of the shared stewardship evaluation."""

    reward: float
    trial_valid: bool
    artifact_valid: bool
    policy_valid: bool
    evaluation_valid: bool
    integrity_gates: tuple[tuple[str, bool], ...]
    metrics: tuple[tuple[str, int], ...]
    terminal_liabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PumpStationSemanticOutcome:
    """Run meanings that must be equal across execution transports."""

    ordered_actions: tuple[PumpStationSemanticActionOutcome, ...]
    terminal_state: PumpStationSemanticTerminalState
    conservation: PumpStationConservationReport
    evaluation: PumpStationSemanticEvaluation
    temporal_access: tuple[tuple[str, str, tuple[str, ...]], ...] = ()


def _v4_handover_count(steps: tuple[PumpStationRunStepV4, ...]) -> int:
    """Count verified actor-tenure changes without inventing a world transition."""
    tenure_ids = tuple(
        step.proposal.context.agent_tenure_id
        for step in steps
        if step.command.kind == "actor" and step.proposal is not None
    )
    return sum(previous != current for previous, current in zip(tenure_ids, tenure_ids[1:], strict=False))


def evaluate_pump_station_reference_run(
    run: PumpStationReferenceRun,
    *,
    imported_artifact_sha256: tuple[str, ...] = (),
    evaluation_scope: Literal["complete_journey", "bounded_continuation"] = "complete_journey",
) -> StewardshipEvaluation:
    """Map one canonical V4 run into the shared stewardship contract."""
    report = run.verify_v4()
    state = run.state
    steps = run.repository.v4_steps()
    receipts = tuple(step.transition.receipt for step in steps)
    closing_work = report.conservation.work.closing_ids
    consumed_resources = sum(int(getattr(pool, "consumed", 0)) for pool in state.resources.pools)
    unavailable_pumps = sum(
        not state.physical.availability(pump.pump_id).run_eligible
        and not state.physical.availability(pump.pump_id).test_eligible
        for pump in state.physical.pumps
    )
    breached_obligations = sum(
        obligation.status is PumpStationObligationStatus.BREACHED for obligation in state.obligations
    )
    restriction_breaches = sum(
        restriction.status is PumpStationRestrictionStatus.LIFTED and restriction.evidence_id is None
        for restriction in state.restrictions
    )
    evidence_gaps = (
        sum(
            obligation.status is PumpStationObligationStatus.FULFILLED and obligation.evidence_id is None
            for obligation in state.obligations
        )
        + restriction_breaches
    )
    terminal_stewardship_available = evaluation_scope == "bounded_continuation" or not state.active_restriction_ids
    errors = list(report.issues)
    if not terminal_stewardship_available:
        errors.append("terminal-stewardship")
    gates = StewardshipIntegrityGates(
        artifact_and_replay_integrity=report.replay_valid,
        output_and_action_contract_validity=report.actor_proposals_valid,
        authority_and_execution_consistency=report.host_controls_valid,
        decision_time_validity=report.actor_proposals_valid,
        obligation_and_restriction_integrity=report.conservation.liabilities.valid,
        physical_and_service_outcomes_available=report.conservation.duty.valid,
        resource_stewardship_available=report.conservation.resources.valid,
        evidence_and_record_integrity=report.valid,
        handover_continuity_integrity=report.replay_valid,
        terminal_stewardship_available=terminal_stewardship_available,
        errors=tuple(dict.fromkeys(errors)),
    )
    terminal = StewardshipTerminalLiability(
        review_required_physical_state=False,
        active_restriction_count=len(state.active_restriction_ids),
        overdue_calendar_seconds=0,
        overdue_affected_pump_runtime_seconds=0,
        breached_obligation_count=breached_obligations,
        unresolved_verification_count=sum(
            "verification" in item.work_type and item.item_id in closing_work for item in state.backlog
        ),
        deferred_work_count=len(closing_work),
        unavailable_pump_count=unavailable_pumps,
        consumed_maintenance_resource_count=consumed_resources,
        unresolved_evidence=evidence_gaps > 0,
    )
    metrics = StewardshipMetricVector(
        decision_time_invalid_count=0 if report.actor_proposals_valid else 1,
        physical_service_review_required=False,
        maintenance_intervention_count=sum(
            receipt.action_or_control_kind
            in {
                "request_inspection",
                "request_obstruction_clearance",
                "request_functional_check",
            }
            for receipt in receipts
        ),
        obligation_breach_count=breached_obligations,
        restriction_breach_count=restriction_breaches,
        evidence_integrity_gap_count=evidence_gaps,
        consumed_maintenance_resource_count=consumed_resources,
        handover_count=_v4_handover_count(steps),
        handover_omission_count=0,
        terminal_liability=terminal,
    )
    return StewardshipEvaluation(
        schema_version=STEWARDSHIP_EVALUATION_SCHEMA_VERSION_V2,
        evaluation_scope=evaluation_scope,
        valid=gates.passed,
        gates=gates,
        metrics=metrics,
        evidence=StewardshipEvaluationEvidence(
            world_run_manifest_content_id=pump_station_artifact_id(run.manifest),
            initial_state_id=run.manifest.initial_state_id,
            terminal_state_id=state.state_id,
            replayed_transition_ids=report.replayed_transition_ids,
            imported_artifact_sha256=tuple(sorted(set(imported_artifact_sha256))),
        ),
    )


def pump_station_semantic_outcome(
    run: PumpStationReferenceRun,
    *,
    temporal_access: tuple[tuple[str, str, tuple[str, ...]], ...] = (),
) -> PumpStationSemanticOutcome:
    """Project only meanings that must match across execution transports."""
    report = run.verify_v4()
    evaluation = evaluate_pump_station_reference_run(run)
    state = run.state
    receipts = tuple(step.transition.receipt for step in run.repository.v4_steps())
    items = {item.item_id: item for item in state.backlog}
    actions = tuple(
        PumpStationSemanticActionOutcome(
            kind=receipt.action_or_control_kind,
            target_id=receipt.target_id,
            backlog_semantic_key=(
                items[receipt.backlog_item_id].semantic_key if receipt.backlog_item_id in items else None
            ),
            authority_outcome=receipt.authority_outcome,
            execution_status=receipt.execution_status,
        )
        for receipt in receipts
    )
    terminal = PumpStationSemanticTerminalState(
        calendar_seconds=state.calendar_seconds,
        pump_exposure=tuple(
            (pump.pump_id, pump.exposure.runtime_seconds, pump.exposure.completed_starts)
            for pump in state.physical.pumps
        ),
        pump_modes=tuple(
            (pump.pump_id, state.physical.boundary(pump.pump_id).mode.value) for pump in state.physical.pumps
        ),
        assignment_pump_ids=state.assignment.ordered_pump_ids,
        service_running_pump_ids=state.physical.service_running_pump_ids,
        test_running_pump_ids=state.physical.test_running_pump_ids,
        resource_quantities=tuple((pool.pool_id, int(pool.free), int(pool.reserved)) for pool in state.resources.pools),
        work_meanings=tuple(sorted((item.semantic_key, item.status.value) for item in state.backlog)),
        active_liability_meanings=tuple(sorted(state.active_liability_ids)),
    )
    gate_values = evaluation.gates
    semantic_evaluation = PumpStationSemanticEvaluation(
        reward=1.0 if evaluation.valid else 0.0,
        trial_valid=report.replay_valid,
        artifact_valid=report.replay_valid,
        policy_valid=report.actor_proposals_valid and report.host_controls_valid,
        evaluation_valid=evaluation.valid,
        integrity_gates=(
            ("artifact_and_replay_integrity", gate_values.artifact_and_replay_integrity),
            ("actor_proposal_integrity", report.actor_proposals_valid),
            ("host_control_integrity", report.host_controls_valid),
            ("duty_conservation", report.conservation.duty.valid),
            ("resource_conservation", report.conservation.resources.valid),
            ("work_conservation", report.conservation.work.valid),
            ("liability_conservation", report.conservation.liabilities.valid),
            ("terminal_stewardship", gate_values.terminal_stewardship_available),
        ),
        metrics=(
            ("operating_interval_count", len(state.operating_intervals)),
            ("generated_work_count", len(state.generation_records)),
            ("terminal_work_count", len(state.terminal_work_item_ids)),
            ("closing_work_count", len(report.conservation.work.closing_ids)),
            ("handover_count", evaluation.metrics.handover_count),
            ("unserved_capacity_seconds", report.conservation.duty.unserved_capacity_seconds),
        ),
        terminal_liabilities=tuple(sorted(state.active_liability_ids)),
    )
    return PumpStationSemanticOutcome(
        ordered_actions=actions,
        terminal_state=terminal,
        conservation=report.conservation,
        evaluation=semantic_evaluation,
        temporal_access=temporal_access,
    )


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
    initial_state = cast(
        PumpStationStewardshipState,
        repository.load_state(manifest.initial_state_id),
    )
    steps = run.steps()
    report = verify_stewardship_run(model, initial_state, steps)
    final_state = cast(
        PumpStationStewardshipState,
        repository.load_state(snapshot.state_id),
    )

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
        proposal = step.proposal
        information_set = step.information_set
        if proposal is None or information_set is None:
            continue
        view = information_set.base_view
        if not isinstance(view, PumpStationActorView):
            invalid += 1
            continue
        context = proposal.context
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
    previous_tenure: str | None = None
    previous_state: PumpStationStewardshipState | None = None
    for step in steps:
        proposal = step.proposal
        information_set = step.information_set
        if proposal is None or information_set is None:
            continue
        view = information_set.base_view
        if not isinstance(view, PumpStationActorView):
            continue
        current_tenure = proposal.context.agent_tenure_id
        if previous_tenure is None or previous_state is None:
            previous_tenure = current_tenure
            previous_state = step.transition.state
            continue
        if previous_tenure == current_tenure:
            previous_state = step.transition.state
            continue
        handovers += 1
        expected_restrictions = {
            item.restriction_id
            for item in previous_state.restrictions
            if item.status is PumpStationRestrictionStatus.ACTIVE
        }
        expected_obligations = {
            item.obligation_id
            for item in previous_state.obligations
            if item.status is not PumpStationObligationStatus.FULFILLED
        }
        expected_processes = _live_process_ids(previous_state)
        visible = view.current_state
        visible_restrictions = {item.restriction_id for item in visible.restrictions}
        visible_obligations = {item.obligation_id for item in visible.obligations}
        visible_processes = {item.process_id for item in visible.processes}
        omissions += len(expected_restrictions - visible_restrictions)
        omissions += len(expected_obligations - visible_obligations)
        omissions += len(expected_processes - visible_processes)
        previous_tenure = current_tenure
        previous_state = step.transition.state
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
