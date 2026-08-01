# ABOUTME: Replays recorded pump-station proposals through the task-owned verifier.
# ABOUTME: Reports integrity facts without mutating the run or exposing private results.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_state_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationObligationStatus,
    PumpStationProposal,
    PumpStationProposalError,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
    PumpStationTransition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    apply_stewardship_proposal,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_RECORD_VERSIONS_V1,
    PUMP_STATION_RECORD_VERSIONS_V2,
    PumpStationRecordVersions,
)


@dataclass(frozen=True, slots=True)
class PumpStationRunStep:
    """One recorded bound proposal and its resulting transition."""

    proposal: PumpStationProposal
    information_set: PumpStationInformationSet
    transition: PumpStationTransition


@dataclass(frozen=True, slots=True)
class PumpStationVerificationReport:
    """Private host result of deterministic task replay and integrity checks."""

    valid: bool
    issues: tuple[str, ...]
    replayed_transition_ids: tuple[str, ...]
    final_state_id: str
    active_restriction_ids: tuple[str, ...]
    open_obligation_ids: tuple[str, ...]


def verify_stewardship_run(
    model: PumpStationModel,
    initial_state: PumpStationStewardshipState,
    steps: tuple[PumpStationRunStep, ...],
    *,
    record_versions: PumpStationRecordVersions | None = None,
) -> PumpStationVerificationReport:
    """Replay immutable run steps from the declared initial state."""
    selected_versions = record_versions or (
        PUMP_STATION_RECORD_VERSIONS_V2
        if initial_state.state_version.endswith(".v2")
        else PUMP_STATION_RECORD_VERSIONS_V1
    )
    expected_state_version = (
        "pump-station-stewardship-state.v2"
        if selected_versions == PUMP_STATION_RECORD_VERSIONS_V2
        else "pump-station-stewardship-state.v1"
    )
    state = initial_state
    issues: list[str] = []
    if initial_state.state_version != expected_state_version:
        issues.append("initial-state-version-mismatch")
    replayed_transition_ids: list[str] = []
    for step in steps:
        transition_id = step.transition.receipt.transition_id
        try:
            replayed = apply_stewardship_proposal(
                model,
                state,
                step.proposal,
                information_set=step.information_set,
            )
        except PumpStationProposalError as error:
            issues.append(f"transition-replay-error:{transition_id}:{error.code}")
            break
        replayed_transition_ids.append(replayed.receipt.transition_id)
        if replayed != step.transition:
            issues.append(f"transition-replay-mismatch:{transition_id}")
            break
        state = replayed.state
    return PumpStationVerificationReport(
        valid=not issues and len(replayed_transition_ids) == len(steps),
        issues=tuple(issues),
        replayed_transition_ids=tuple(replayed_transition_ids),
        final_state_id=stewardship_state_id(state),
        active_restriction_ids=tuple(
            restriction.restriction_id
            for restriction in state.restrictions
            if restriction.status is PumpStationRestrictionStatus.ACTIVE
        ),
        open_obligation_ids=tuple(
            obligation.obligation_id
            for obligation in state.obligations
            if obligation.status is not PumpStationObligationStatus.FULFILLED
        ),
    )
