# ABOUTME: Unit-tests task-local wastewater pump-station proposals and authority decisions.
# ABOUTME: Proves invalid or incomplete proposals cannot mutate physical stewardship state.

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ProposalContext,
    PumpStationAuthorityOutcome,
    PumpStationEnvironment,
    PumpStationExecutionOutcome,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationProposalError,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    RequestConditionalDeferral,
    RequestObstructionClearance,
    apply_stewardship_proposal,
    create_stewardship_state,
    initial_pump_station_state,
    load_reference_package,
    pump_station_model_from_package,
)


def _environment() -> PumpStationEnvironment:
    return PumpStationEnvironment(
        inflow_m3_s=Decimal("0.0155"),
        wet_well_level_m=Decimal("1.65"),
        isolated=False,
    )


def _state():
    model = pump_station_model_from_package(load_reference_package())
    state = create_stewardship_state(
        model,
        initial_pump_station_state(model),
        _environment(),
    )
    return model, state


def _context(sequence: int, proposal_id: str) -> ProposalContext:
    return ProposalContext(
        proposal_id=proposal_id,
        agent_tenure_id="tenure-1",
        based_on_sequence=sequence,
        reason="Typed test proposal.",
    )


def test_conditional_deferral_creates_policy_records_without_physical_effect() -> None:
    model, state = _state()
    proposal = RequestConditionalDeferral(
        context=_context(state.sequence, "proposal-deferral"),
        pump_id="pump-a",
    )

    transition = apply_stewardship_proposal(model, state, proposal)

    assert transition.receipt.authority.outcome is PumpStationAuthorityOutcome.PERMITTED_WITH_CONDITIONS
    assert transition.receipt.execution is PumpStationExecutionOutcome.COMPLETED
    assert transition.state.physical == state.physical
    restriction = transition.state.restriction(
        PumpStationRestrictionKind.DEFERRED_PUMP_NOT_DUTY,
        "pump-a",
    )
    obligation = transition.state.obligation(
        PumpStationObligationKind.DEFERRED_FOLLOW_UP,
        "pump-a",
    )
    assert restriction.status is PumpStationRestrictionStatus.ACTIVE
    assert obligation.status is PumpStationObligationStatus.ACTIVE
    assert obligation.due_calendar_seconds == (
        state.physical.calendar_seconds + model.resources.repair_kit_lead_seconds
    )
    assert obligation.due_runtime_seconds == (
        state.physical.pump("pump-a").exposure.runtime_seconds + model.inflow.diagnostic_period_seconds
    )
    assert not hasattr(proposal, "parameters")


def test_stale_proposal_is_invalid_and_cannot_change_physical_state() -> None:
    model, state = _state()
    stale = RequestConditionalDeferral(
        context=_context(state.sequence + 1, "proposal-stale"),
        pump_id="pump-a",
    )

    transition = apply_stewardship_proposal(model, state, stale)

    assert transition.receipt.authority.outcome is PumpStationAuthorityOutcome.INVALID
    assert transition.receipt.execution is PumpStationExecutionOutcome.CANCELLED
    assert transition.state.physical == state.physical
    assert transition.state.restrictions == ()
    assert transition.state.obligations == ()


def test_obstruction_clearance_waits_for_named_inspection_evidence() -> None:
    model, state = _state()
    proposal = RequestObstructionClearance(
        context=_context(state.sequence, "proposal-clear"),
        pump_id="pump-a",
        inspection_evidence_id="missing-inspection",
    )

    transition = apply_stewardship_proposal(model, state, proposal)

    assert transition.receipt.authority.outcome is (PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES)
    assert transition.receipt.execution is PumpStationExecutionOutcome.CANCELLED
    assert transition.state.physical == state.physical
    assert transition.state.processes == ()


def test_proposals_are_immutable() -> None:
    proposal = RequestConditionalDeferral(
        context=_context(0, "proposal-immutable"),
        pump_id="pump-a",
    )

    with pytest.raises(FrozenInstanceError):
        proposal.__setattr__("pump_id", "pump-b")


def test_fixed_deferral_policy_rejects_the_standby_pump() -> None:
    model, state = _state()
    proposal = RequestConditionalDeferral(
        context=_context(state.sequence, "proposal-standby-deferral"),
        pump_id="pump-b",
    )

    transition = apply_stewardship_proposal(model, state, proposal)

    assert transition.receipt.authority.outcome is PumpStationAuthorityOutcome.DENIED
    assert transition.state.restrictions == ()
    assert transition.state.obligations == ()


def test_unknown_proposal_fails_before_authority_dispatch() -> None:
    model, state = _state()

    with pytest.raises(PumpStationProposalError, match="proposal-type"):
        apply_stewardship_proposal(model, state, object())
