# ABOUTME: Selects exact pump-station host controls and classifies journey completion.
# ABOUTME: Keeps Operations authority and terminal-state rules outside agents and evaluation.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogItem,
    PumpStationBacklogStatus,
    PumpStationCoupledProcessStatus,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpStationPumpMode,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationBoundControlRequest,
    PumpStationEvidenceKind,
    PumpStationObligationStatus,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationRestriction,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)

PUMP_STATION_OPERATIONS_AUTHORITY_ID = "operations-controller"

_TERMINAL_BACKLOG_STATUSES = {
    PumpStationBacklogStatus.CLOSED,
    PumpStationBacklogStatus.CANCELLED,
    PumpStationBacklogStatus.SUPERSEDED,
}
_TERMINAL_PROCESS_STATUSES = {
    PumpStationCoupledProcessStatus.COMPLETED,
    PumpStationCoupledProcessStatus.FAILED,
    PumpStationCoupledProcessStatus.CANCELLED,
}


class PumpStationJourneyStatus(StrEnum):
    """Task-owned runtime status independent of any model session or evaluator."""

    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class PumpStationHostContinuation:
    """One current host decision without exposing raw state to the actor."""

    status: PumpStationJourneyStatus
    control_request: PumpStationBoundControlRequest | None
    reason: str


def pump_station_journey_status(state: PumpStationStewardshipState) -> PumpStationJourneyStatus:
    """Return completed only when no current task work or authority boundary remains."""
    if state.active_restriction_ids:
        return PumpStationJourneyStatus.ACTIVE
    if any(process.status not in _TERMINAL_PROCESS_STATUSES for process in state.processes):
        return PumpStationJourneyStatus.ACTIVE
    if any(obligation.status is not PumpStationObligationStatus.FULFILLED for obligation in state.obligations):
        return PumpStationJourneyStatus.ACTIVE
    if any(episode.status == "open" for episode in state.outage_episodes):
        return PumpStationJourneyStatus.ACTIVE
    if any(_is_current_unfinished_work(state, item) for item in state.backlog):
        return PumpStationJourneyStatus.ACTIVE
    return PumpStationJourneyStatus.COMPLETED


def resolve_pump_station_host_continuation(
    run: PumpStationWorldRun,
    *,
    authority_id: str = PUMP_STATION_OPERATIONS_AUTHORITY_ID,
) -> PumpStationHostContinuation:
    """Select one deterministic Operations review from the canonical current state."""
    status = pump_station_journey_status(run.state)
    if status is PumpStationJourneyStatus.COMPLETED:
        return PumpStationHostContinuation(status=status, control_request=None, reason="declared-terminal-state")
    for restriction in sorted(
        run.state.restrictions,
        key=lambda item: (item.created_sequence, item.restriction_id),
    ):
        control = _eligible_review(run, restriction, authority_id=authority_id)
        if control is not None:
            return PumpStationHostContinuation(
                status=status,
                control_request=control,
                reason="eligible-operations-review",
            )
    return PumpStationHostContinuation(
        status=status,
        control_request=None,
        reason="actor-or-external-progress-required",
    )


def _is_current_unfinished_work(state: PumpStationStewardshipState, item: PumpStationBacklogItem) -> bool:
    if item.status in _TERMINAL_BACKLOG_STATUSES:
        return False
    return not (
        item.generation_rule_id == "WG-06"
        and item.due_calendar_seconds is not None
        and item.due_calendar_seconds > state.disclosed_through_calendar_seconds
    )


def _eligible_review(
    run: PumpStationWorldRun,
    restriction: PumpStationRestriction,
    *,
    authority_id: str,
) -> PumpStationBoundControlRequest | None:
    state = run.state
    if restriction.status is not PumpStationRestrictionStatus.ACTIVE:
        return None
    if restriction.kind is PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN:
        review_kind = "post_verification_restriction"
        evidence_id = f"evidence-{restriction.pump_id}-verification-pass-001"
        evidence_kind = PumpStationEvidenceKind.POST_MAINTENANCE_VERIFICATION
        expected_mode = PumpStationPumpMode.RUN_IN_SERVICE
        work_types = {"post_maintenance_verification"}
        work_status = PumpStationBacklogStatus.COMPLETED
    elif restriction.kind is PumpStationRestrictionKind.NO_INTERVENTION and restriction.restriction_id.startswith(
        f"isolation-{restriction.pump_id}-"
    ):
        review_kind = "post_inspection_isolation"
        evidence_id = f"evidence-{restriction.pump_id.removeprefix('pump-')}-inspection-no-finding-001"
        evidence_kind = PumpStationEvidenceKind.INSPECTION
        expected_mode = PumpStationPumpMode.ISOLATED_FOR_WORK
        work_types = {"inspection", "collateral_duty_inspection"}
        work_status = PumpStationBacklogStatus.CLOSED
    else:
        return None
    if state.physical.boundary(restriction.pump_id).mode is not expected_mode:
        return None
    evidence = tuple(
        item
        for item in state.evidence
        if item.evidence_id == evidence_id
        and item.kind is evidence_kind
        and item.pump_id == restriction.pump_id
        and item.accepted_by is not None
        and item.passed is True
        and (item.health is None or item.health.accepted)
    )
    matching_work = tuple(
        item
        for item in state.backlog
        if item.target_id == restriction.pump_id
        and item.work_type in work_types
        and item.status is work_status
        and evidence_id in item.closure_evidence_ids
    )
    if len(evidence) != 1 or len(matching_work) != 1:
        return None
    snapshot = run.snapshot()
    review_id = (
        "operations-review-"
        + stewardship_content_id((review_kind, restriction.pump_id, restriction.restriction_id, evidence_id))[:16]
    )
    review = PumpStationOperationsBoundaryReviewRequest(
        review_id=review_id,
        review_kind=review_kind,
        pump_id=restriction.pump_id,
        restriction_or_isolation_permit_id=restriction.restriction_id,
        accepted_evidence_id=evidence_id,
        requested_outcome="release",
        base_state_id=snapshot.state_id,
        operations_authority_id=authority_id,
        reason="Release only the matched boundary after the accepted evidence.",
    )
    return PumpStationBoundControlRequest(
        request_id=review_id,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        control=review,
    )
