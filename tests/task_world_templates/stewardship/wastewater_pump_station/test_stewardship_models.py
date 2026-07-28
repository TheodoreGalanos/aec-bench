# ABOUTME: Unit-tests task-local wastewater pump-station proposals and authority decisions.
# ABOUTME: Proves invalid or incomplete proposals cannot mutate physical stewardship state.

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ProposalContext,
    PumpStationAuthorityOutcome,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEnvironment,
    PumpStationExecutionOutcome,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationObservationHistory,
    PumpStationProjectionContext,
    PumpStationProposalError,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    RequestConditionalDeferral,
    RequestObstructionClearance,
    apply_stewardship_proposal,
    bind_information_set,
    create_stewardship_state,
    initial_pump_station_state,
    load_reference_package,
    project_actor_view,
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


def _bound_context(
    model,
    state,
    proposal_id: str,
    *,
    based_on_sequence: int | None = None,
):
    package = load_reference_package()
    view = project_actor_view(
        model,
        state,
        PumpStationProjectionContext(
            episode_id="episode-test",
            world_branch_id="branch-test",
            actor_id="station-steward",
            agent_tenure_id="tenure-1",
            episode_started_at_seconds=0,
            tenure_started_at_seconds=0,
            projection_policy_id="pump-station-current-state-v1",
            source_artifact_ids=(
                package.package_content_id,
                package.manifest_content_id,
            ),
        ),
    )
    information_set = bind_information_set(
        view,
        PumpStationObservationHistory(
            agent_tenure_id="tenure-1",
            view_ids=(view.view_id,),
        ),
        PumpStationCurrentContext(
            continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
            conversation_prefix_id=None,
            workspace_tool_ids=("propose-pump-station-action",),
            visible_material_ids=(),
        ),
    )
    context = ProposalContext(
        proposal_id=proposal_id,
        agent_tenure_id="tenure-1",
        based_on_sequence=(state.sequence if based_on_sequence is None else based_on_sequence),
        base_view_id=view.view_id,
        information_set_id=information_set.information_set_id,
        reason="Typed test proposal.",
    )
    return context, information_set


def test_conditional_deferral_creates_policy_records_without_physical_effect() -> None:
    model, state = _state()
    context, information_set = _bound_context(
        model,
        state,
        "proposal-deferral",
    )
    proposal = RequestConditionalDeferral(
        context=context,
        pump_id="pump-a",
    )

    transition = apply_stewardship_proposal(
        model,
        state,
        proposal,
        information_set=information_set,
    )

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
    context, information_set = _bound_context(
        model,
        state,
        "proposal-stale",
        based_on_sequence=state.sequence + 1,
    )
    stale = RequestConditionalDeferral(
        context=context,
        pump_id="pump-a",
    )

    transition = apply_stewardship_proposal(
        model,
        state,
        stale,
        information_set=information_set,
    )

    assert transition.receipt.authority.outcome is PumpStationAuthorityOutcome.INVALID
    assert transition.receipt.execution is PumpStationExecutionOutcome.CANCELLED
    assert transition.state.physical == state.physical
    assert transition.state.restrictions == ()
    assert transition.state.obligations == ()


def test_obstruction_clearance_waits_for_named_inspection_evidence() -> None:
    model, state = _state()
    context, information_set = _bound_context(model, state, "proposal-clear")
    proposal = RequestObstructionClearance(
        context=context,
        pump_id="pump-a",
        inspection_evidence_id="missing-inspection",
    )

    transition = apply_stewardship_proposal(
        model,
        state,
        proposal,
        information_set=information_set,
    )

    assert transition.receipt.authority.outcome is (PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES)
    assert transition.receipt.execution is PumpStationExecutionOutcome.CANCELLED
    assert transition.state.physical == state.physical
    assert transition.state.processes == ()


def test_proposals_are_immutable() -> None:
    model, state = _state()
    context, _ = _bound_context(model, state, "proposal-immutable")
    proposal = RequestConditionalDeferral(
        context=context,
        pump_id="pump-a",
    )

    with pytest.raises(FrozenInstanceError):
        proposal.__setattr__("pump_id", "pump-b")


def test_fixed_deferral_policy_rejects_the_standby_pump() -> None:
    model, state = _state()
    context, information_set = _bound_context(
        model,
        state,
        "proposal-standby-deferral",
    )
    proposal = RequestConditionalDeferral(
        context=context,
        pump_id="pump-b",
    )

    transition = apply_stewardship_proposal(
        model,
        state,
        proposal,
        information_set=information_set,
    )

    assert transition.receipt.authority.outcome is PumpStationAuthorityOutcome.DENIED
    assert transition.state.restrictions == ()
    assert transition.state.obligations == ()


def test_unknown_proposal_fails_before_authority_dispatch() -> None:
    model, state = _state()
    _, information_set = _bound_context(model, state, "proposal-unknown")

    with pytest.raises(PumpStationProposalError, match="proposal-type"):
        apply_stewardship_proposal(
            model,
            state,
            object(),
            information_set=information_set,
        )
