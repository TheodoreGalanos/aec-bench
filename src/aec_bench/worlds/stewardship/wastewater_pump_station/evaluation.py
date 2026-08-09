# ABOUTME: Evaluates pump-station stewardship trajectories from immutable run evidence.
# ABOUTME: Keeps pump-specific scoring, diagnostics, and terminal liabilities with the task owner.

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from aec_bench.contracts.evaluation_result import (
    StewardshipEvaluation,
    StewardshipEvaluationEvidence,
    StewardshipIntegrityGates,
    StewardshipMetricVector,
    StewardshipTerminalLiability,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationAuthorityOutcome,
    PumpStationObligationStatus,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationConservationReport,
    PumpStationCoupledRunStep,
    PumpStationCoupledVerificationReport,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)

type PumpStationReferenceRun = PumpStationWorldRun

_PERMITTED_AUTHORITY_OUTCOMES = {
    PumpStationAuthorityOutcome.PERMITTED,
    PumpStationAuthorityOutcome.PERMITTED_WITH_CONDITIONS,
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


def _handover_count(steps: tuple[PumpStationCoupledRunStep, ...]) -> int:
    """Count verified actor-tenure changes without inventing a world transition."""
    tenure_ids = tuple(
        step.command.agent_tenure_id
        for step in steps
        if step.command.kind == "actor" and step.command.agent_tenure_id is not None
    )
    return sum(previous != current for previous, current in zip(tenure_ids, tenure_ids[1:], strict=False))


def evaluate_pump_station_reference_run(
    run: PumpStationReferenceRun,
    *,
    imported_artifact_sha256: tuple[str, ...] = (),
    evaluation_scope: Literal["complete_journey", "bounded_continuation"] = "complete_journey",
) -> StewardshipEvaluation:
    """Load current run evidence and delegate to the task-owned evaluator."""
    report = run.verify()
    state = run.state
    steps = run.repository.command_steps()
    return evaluate(
        state,
        report,
        steps,
        manifest_content_id=pump_station_artifact_id(run.manifest),
        initial_state_id=run.manifest.initial_state_id,
        imported_artifact_sha256=imported_artifact_sha256,
        evaluation_scope=evaluation_scope,
    )


def evaluate(
    state: PumpStationStewardshipState,
    report: PumpStationCoupledVerificationReport,
    steps: tuple[PumpStationCoupledRunStep, ...],
    *,
    manifest_content_id: str,
    initial_state_id: str,
    imported_artifact_sha256: tuple[str, ...] = (),
    evaluation_scope: Literal["complete_journey", "bounded_continuation"] = "complete_journey",
) -> StewardshipEvaluation:
    """Evaluate canonical state plus explicit verified episode evidence."""
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
        output_and_action_contract_validity=report.actor_actions_valid,
        authority_and_execution_consistency=report.host_controls_valid,
        decision_time_validity=report.actor_actions_valid,
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
        decision_time_invalid_count=0 if report.actor_actions_valid else 1,
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
        handover_count=_handover_count(steps),
        handover_omission_count=0,
        terminal_liability=terminal,
    )
    return StewardshipEvaluation(
        evaluation_scope=evaluation_scope,
        valid=gates.passed,
        gates=gates,
        metrics=metrics,
        evidence=StewardshipEvaluationEvidence(
            world_run_manifest_content_id=manifest_content_id,
            initial_state_id=initial_state_id,
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
    report = run.verify()
    evaluation = evaluate_pump_station_reference_run(run)
    state = run.state
    receipts = tuple(step.transition.receipt for step in run.repository.command_steps())
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
        policy_valid=report.actor_actions_valid and report.host_controls_valid,
        evaluation_valid=evaluation.valid,
        integrity_gates=(
            ("artifact_and_replay_integrity", gate_values.artifact_and_replay_integrity),
            ("actor_action_integrity", report.actor_actions_valid),
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
