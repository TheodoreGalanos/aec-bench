# ABOUTME: Independently verifies ASW-8 replay, four conservation sections, and semantic outcomes.
# ABOUTME: Recomputes evaluation from immutable run evidence without trusting stored pass claims.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.contracts.evaluation_result import (
    StewardshipEvaluation,
    StewardshipEvaluationEvidence,
    StewardshipIntegrityGates,
    StewardshipMetricVector,
    StewardshipTerminalLiability,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRun,
    PumpStationCoupledRunError,
    replay_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogStatus,
    resource_conservation,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
)

PUMP_STATION_VERIFICATION_REPORT_VERSION_V2 = "pump-station-verification-report.v2"
STEWARDSHIP_EVALUATION_VERSION_V2 = "stewardship-evaluation.v2"


@dataclass(frozen=True, slots=True)
class PumpStationDutyConservationReport:
    """Derived service, runtime, start, and collateral balances."""

    required_capacity_seconds: int
    served_capacity_seconds: int
    unserved_capacity_seconds: int
    assigned_capacity_seconds: int
    surplus_capacity_seconds: int
    service_runtime_seconds: int
    test_runtime_seconds: int
    total_pump_runtime_delta_seconds: int
    collateral_runtime_seconds: int
    required_residual_seconds: int
    assigned_residual_seconds: int
    runtime_residual_seconds: int
    collateral_residual_seconds: int
    valid: bool


@dataclass(frozen=True, slots=True)
class PumpStationResourceConservationReport:
    """Derived current resource-pool balance."""

    reusable_pool_count: int
    consumable_pool_count: int
    failed_pool_ids: tuple[str, ...]
    valid: bool


@dataclass(frozen=True, slots=True)
class PumpStationWorkConservationReport:
    """Derived durable work-identity balance."""

    opening_ids: tuple[str, ...]
    generated_ids: tuple[str, ...]
    terminal_ids: tuple[str, ...]
    closing_ids: tuple[str, ...]
    residual_ids: tuple[str, ...]
    valid: bool


@dataclass(frozen=True, slots=True)
class PumpStationLiabilityConservationReport:
    """Derived canonical liability-owner identity balance."""

    opening_ids: tuple[str, ...]
    created_ids: tuple[str, ...]
    discharged_ids: tuple[str, ...]
    transferred_ids: tuple[str, ...]
    closing_ids: tuple[str, ...]
    residual_ids: tuple[str, ...]
    valid: bool


@dataclass(frozen=True, slots=True)
class PumpStationConservationReport:
    """All four independently checked ASW-8 conservation sections."""

    duty: PumpStationDutyConservationReport
    resources: PumpStationResourceConservationReport
    work: PumpStationWorkConservationReport
    liabilities: PumpStationLiabilityConservationReport

    @property
    def valid(self) -> bool:
        """Return whether every conservation section is valid."""
        return self.duty.valid and self.resources.valid and self.work.valid and self.liabilities.valid

    @property
    def content_id(self) -> str:
        """Return the exact derived report identity."""
        return stewardship_content_id(self, record_profile="v4")


@dataclass(frozen=True, slots=True)
class PumpStationCoupledVerificationReport:
    """V2 replay report with its complete conservation artifact."""

    report_version: str
    valid: bool
    replay_valid: bool
    actor_proposals_valid: bool
    host_controls_valid: bool
    terminal_state_id: str
    replayed_transition_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    conservation: PumpStationConservationReport
    conservation_content_id: str

    @property
    def content_id(self) -> str:
        """Return the exact verification-report identity."""
        return stewardship_content_id(self, record_profile="v4")


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
    """Transport-neutral v2 evaluation projection."""

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
    """Only the direct-versus-Harbor meanings that must be equal."""

    ordered_actions: tuple[PumpStationSemanticActionOutcome, ...]
    terminal_state: PumpStationSemanticTerminalState
    conservation: PumpStationConservationReport
    evaluation: PumpStationSemanticEvaluation
    temporal_access: tuple[tuple[str, str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class PumpStationCoupledEvaluationResult:
    """Evaluation v2 result derived from verified immutable run evidence."""

    schema_version: str
    valid: bool
    reward: float
    integrity_gates: tuple[tuple[str, bool], ...]
    metrics: tuple[tuple[str, int], ...]
    terminal_liabilities: tuple[str, ...]
    verification_report_id: str


def derive_conservation_report(run: PumpStationCoupledRun) -> PumpStationConservationReport:
    """Derive all balances from the opening state, intervals, receipts, and terminal state."""
    required = served = unserved = assigned = surplus = 0
    service_runtime = test_runtime = total_delta = collateral = 0
    for interval in run.state.operating_intervals:
        elapsed = interval.elapsed_seconds
        assigned_scu = len(interval.service_running_pump_ids)
        served_scu = min(interval.required_service_scu, assigned_scu)
        required += interval.required_service_scu * elapsed
        served += served_scu * elapsed
        unserved += (interval.required_service_scu - served_scu) * elapsed
        assigned += assigned_scu * elapsed
        surplus += max(0, assigned_scu - interval.required_service_scu) * elapsed
        for delta in interval.pump_deltas:
            service_runtime += delta.service_runtime_seconds
            test_runtime += delta.test_runtime_seconds
            if delta.opening_exposure is not None and delta.closing_exposure is not None:
                total_delta += delta.closing_exposure.runtime_seconds - delta.opening_exposure.runtime_seconds
            collateral += delta.collateral_runtime_seconds
    recorded_collateral = sum(row[2] for row in run.state.collateral_runtime)
    duty = PumpStationDutyConservationReport(
        required_capacity_seconds=required,
        served_capacity_seconds=served,
        unserved_capacity_seconds=unserved,
        assigned_capacity_seconds=assigned,
        surplus_capacity_seconds=surplus,
        service_runtime_seconds=service_runtime,
        test_runtime_seconds=test_runtime,
        total_pump_runtime_delta_seconds=total_delta,
        collateral_runtime_seconds=collateral,
        required_residual_seconds=required - served - unserved,
        assigned_residual_seconds=assigned - served - surplus,
        runtime_residual_seconds=total_delta - service_runtime - test_runtime,
        collateral_residual_seconds=recorded_collateral - collateral,
        valid=(
            required == served + unserved
            and assigned == served + surplus
            and total_delta == service_runtime + test_runtime
            and recorded_collateral == collateral
        ),
    )
    resource_result = resource_conservation(
        run.state.resources,
        run.state.resource_reservations,
    )
    reusable_count = sum(hasattr(pool, "capacity") for pool in run.state.resources.pools)
    resources = PumpStationResourceConservationReport(
        reusable_pool_count=reusable_count,
        consumable_pool_count=len(run.state.resources.pools) - reusable_count,
        failed_pool_ids=resource_result.failure_pool_ids,
        valid=resource_result.valid,
    )
    opening_ids = {"backlog-a-verification-001", "backlog-b-clearance-001"}
    generated_ids = {record.backlog_item_id for record in run.state.generation_records}
    terminal_ids = set(run.state.terminal_work_item_ids)
    closing_ids = {
        item.item_id
        for item in run.state.backlog
        if item.status
        in {
            PumpStationBacklogStatus.OPEN,
            PumpStationBacklogStatus.PLANNED,
            PumpStationBacklogStatus.IN_PROGRESS,
            PumpStationBacklogStatus.BLOCKED,
            PumpStationBacklogStatus.COMPLETED,
        }
    }
    work_left = opening_ids | generated_ids
    work_right = terminal_ids | closing_ids
    work = PumpStationWorkConservationReport(
        opening_ids=tuple(sorted(opening_ids)),
        generated_ids=tuple(sorted(generated_ids)),
        terminal_ids=tuple(sorted(terminal_ids)),
        closing_ids=tuple(sorted(closing_ids)),
        residual_ids=tuple(sorted(work_left ^ work_right)),
        valid=work_left == work_right and not (terminal_ids & closing_ids),
    )
    liability_opening = {"obligation-a-verification-001", "outage-b-001"}
    liability_created = set(run.state.created_liability_ids)
    liability_discharged = set(run.state.discharged_liability_ids)
    liability_transferred: set[str] = set()
    liability_closing = set(run.state.active_liability_ids)
    liability_left = liability_opening | liability_created
    liability_right = liability_discharged | liability_transferred | liability_closing
    liabilities = PumpStationLiabilityConservationReport(
        opening_ids=tuple(sorted(liability_opening)),
        created_ids=tuple(sorted(liability_created)),
        discharged_ids=tuple(sorted(liability_discharged)),
        transferred_ids=(),
        closing_ids=tuple(sorted(liability_closing)),
        residual_ids=tuple(sorted(liability_left ^ liability_right)),
        valid=liability_left == liability_right,
    )
    return PumpStationConservationReport(
        duty=duty,
        resources=resources,
        work=work,
        liabilities=liabilities,
    )


def verify_coupled_run(run: PumpStationCoupledRun) -> PumpStationCoupledVerificationReport:
    """Replay the run and derive conservation without trusting its terminal state."""
    issue_codes: list[str] = []
    actor_command_ids = tuple(command.request_id for command in run.commands if command.kind == "actor")
    proposal_ids = tuple(proposal.context.proposal_id for proposal in run.proposals)
    paired_steps = tuple(zip(run.commands, run.receipts, strict=False))
    all_steps_paired = len(run.commands) == len(run.receipts)
    actor_proposals_valid = (
        actor_command_ids == proposal_ids
        and all_steps_paired
        and all(
            receipt.actor_action and receipt.request_id == command.request_id
            for command, receipt in paired_steps
            if command.kind == "actor"
        )
    )
    host_controls_valid = all_steps_paired and all(
        not receipt.actor_action and receipt.request_id == command.request_id
        for command, receipt in paired_steps
        if command.kind != "actor"
    )
    if not actor_proposals_valid:
        issue_codes.append("actor-proposal-integrity")
    if not host_controls_valid:
        issue_codes.append("host-control-integrity")
    replay_valid = False
    try:
        replay = replay_coupled_run(
            run.manifest,
            run.commands,
            proposals=run.proposals,
            origin_manifest=run.origin_manifest,
            origin_commands=run.origin_commands,
            origin_proposals=run.origin_proposals,
        )
        replay_valid = (
            replay.state == run.state and replay.receipts == run.receipts and replay.proposals == run.proposals
        )
        if not replay_valid:
            issue_codes.append("replay-mismatch")
    except (ValueError, PumpStationCoupledRunError):
        replay = run
        issue_codes.append("replay-error")
    conservation = derive_conservation_report(replay)
    if not conservation.duty.valid:
        issue_codes.append("duty-conservation")
    if not conservation.resources.valid:
        issue_codes.append("resource-conservation")
    if not conservation.work.valid:
        issue_codes.append("work-conservation")
    if not conservation.liabilities.valid:
        issue_codes.append("liability-conservation")
    return PumpStationCoupledVerificationReport(
        report_version=PUMP_STATION_VERIFICATION_REPORT_VERSION_V2,
        valid=(replay_valid and actor_proposals_valid and host_controls_valid and conservation.valid),
        replay_valid=replay_valid,
        actor_proposals_valid=actor_proposals_valid,
        host_controls_valid=host_controls_valid,
        terminal_state_id=replay.state.state_id,
        replayed_transition_ids=tuple(receipt.transition_id for receipt in replay.receipts),
        issue_codes=tuple(issue_codes),
        conservation=conservation,
        conservation_content_id=conservation.content_id,
    )


def evaluate_coupled_run(run: PumpStationCoupledRun) -> PumpStationCoupledEvaluationResult:
    """Compute task evaluation v2 from the independent verification report."""
    report = verify_coupled_run(run)
    gates = (
        ("artifact_and_replay_integrity", report.replay_valid),
        ("actor_proposal_integrity", report.actor_proposals_valid),
        ("host_control_integrity", report.host_controls_valid),
        ("duty_conservation", report.conservation.duty.valid),
        ("resource_conservation", report.conservation.resources.valid),
        ("work_conservation", report.conservation.work.valid),
        ("liability_conservation", report.conservation.liabilities.valid),
        ("terminal_stewardship", not run.state.active_restriction_ids),
    )
    valid = report.valid and all(value for _, value in gates)
    metrics = (
        ("operating_interval_count", len(run.state.operating_intervals)),
        ("generated_work_count", len(run.state.generation_records)),
        ("terminal_work_count", len(run.state.terminal_work_item_ids)),
        ("closing_work_count", len(report.conservation.work.closing_ids)),
        ("handover_count", sum(receipt.action_or_control_kind == "structured_handover" for receipt in run.receipts)),
        ("unserved_capacity_seconds", report.conservation.duty.unserved_capacity_seconds),
    )
    return PumpStationCoupledEvaluationResult(
        schema_version=STEWARDSHIP_EVALUATION_VERSION_V2,
        valid=valid,
        reward=1.0 if valid else 0.0,
        integrity_gates=gates,
        metrics=metrics,
        terminal_liabilities=tuple(sorted(run.state.active_liability_ids)),
        verification_report_id=report.content_id,
    )


def shared_stewardship_evaluation(
    run: PumpStationCoupledRun,
    *,
    imported_artifact_sha256: tuple[str, ...] = (),
) -> StewardshipEvaluation:
    """Project verified ASW-8 evidence into the shared TrialRecord contract."""
    report = verify_coupled_run(run)
    evaluation = evaluate_coupled_run(run)
    closing_work = report.conservation.work.closing_ids
    consumed_resources = sum(int(getattr(pool, "consumed", 0)) for pool in run.state.resources.pools)
    unavailable_pumps = sum(
        not run.state.physical.availability(pump.pump_id).run_eligible
        and not run.state.physical.availability(pump.pump_id).test_eligible
        for pump in run.state.physical.pumps
    )
    gates = StewardshipIntegrityGates(
        artifact_and_replay_integrity=report.replay_valid,
        output_and_action_contract_validity=report.replay_valid,
        authority_and_execution_consistency=report.host_controls_valid,
        decision_time_validity=report.actor_proposals_valid,
        obligation_and_restriction_integrity=report.conservation.liabilities.valid,
        physical_and_service_outcomes_available=report.conservation.duty.valid,
        resource_stewardship_available=report.conservation.resources.valid,
        evidence_and_record_integrity=report.valid,
        handover_continuity_integrity=report.replay_valid,
        terminal_stewardship_available=evaluation.valid,
        errors=() if evaluation.valid else tuple(report.issue_codes or ("asw-8-evaluation-invalid",)),
    )
    terminal = StewardshipTerminalLiability(
        review_required_physical_state=False,
        active_restriction_count=len(run.state.active_restriction_ids),
        overdue_calendar_seconds=0,
        overdue_affected_pump_runtime_seconds=0,
        breached_obligation_count=0,
        unresolved_verification_count=0,
        deferred_work_count=len(closing_work),
        unavailable_pump_count=unavailable_pumps,
        consumed_maintenance_resource_count=consumed_resources,
        unresolved_evidence=False,
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
            for receipt in run.receipts
        ),
        obligation_breach_count=0,
        restriction_breach_count=0,
        evidence_integrity_gap_count=0,
        consumed_maintenance_resource_count=consumed_resources,
        handover_count=sum(receipt.action_or_control_kind == "structured_handover" for receipt in run.receipts),
        handover_omission_count=0,
        terminal_liability=terminal,
    )
    return StewardshipEvaluation(
        schema_version=STEWARDSHIP_EVALUATION_VERSION_V2,
        valid=evaluation.valid,
        gates=gates,
        metrics=metrics,
        evidence=StewardshipEvaluationEvidence(
            world_run_manifest_content_id=run.manifest.content_id,
            initial_state_id=run.manifest.initial_state_id,
            terminal_state_id=run.state.state_id,
            replayed_transition_ids=report.replayed_transition_ids,
            imported_artifact_sha256=tuple(sorted(set(imported_artifact_sha256))),
        ),
    )


def semantic_outcome(
    run: PumpStationCoupledRun,
    *,
    temporal_access: tuple[tuple[str, str, tuple[str, ...]], ...] = (),
) -> PumpStationSemanticOutcome:
    """Project only meanings that must match between direct and Harbor runs."""
    report = verify_coupled_run(run)
    evaluation = evaluate_coupled_run(run)
    items = {item.item_id: item for item in run.state.backlog}
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
        for receipt in run.receipts
    )
    resource_quantities = tuple(
        (
            pool.pool_id,
            int(pool.free),
            int(pool.reserved),
        )
        for pool in run.state.resources.pools
    )
    terminal = PumpStationSemanticTerminalState(
        calendar_seconds=run.state.calendar_seconds,
        pump_exposure=tuple(
            (pump.pump_id, pump.exposure.runtime_seconds, pump.exposure.completed_starts)
            for pump in run.state.physical.pumps
        ),
        pump_modes=tuple(
            (pump.pump_id, run.state.physical.boundary(pump.pump_id).mode.value) for pump in run.state.physical.pumps
        ),
        assignment_pump_ids=run.state.assignment.ordered_pump_ids,
        service_running_pump_ids=run.state.physical.service_running_pump_ids,
        test_running_pump_ids=run.state.physical.test_running_pump_ids,
        resource_quantities=resource_quantities,
        work_meanings=tuple(sorted((item.semantic_key, item.status.value) for item in run.state.backlog)),
        active_liability_meanings=tuple(sorted(run.state.active_liability_ids)),
    )
    semantic_evaluation = PumpStationSemanticEvaluation(
        reward=evaluation.reward,
        trial_valid=report.replay_valid,
        artifact_valid=report.replay_valid,
        policy_valid=True,
        evaluation_valid=evaluation.valid,
        integrity_gates=evaluation.integrity_gates,
        metrics=evaluation.metrics,
        terminal_liabilities=evaluation.terminal_liabilities,
    )
    return PumpStationSemanticOutcome(
        ordered_actions=actions,
        terminal_state=terminal,
        conservation=report.conservation,
        evaluation=semantic_evaluation,
        temporal_access=temporal_access,
    )
