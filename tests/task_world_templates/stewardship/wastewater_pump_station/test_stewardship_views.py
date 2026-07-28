# ABOUTME: Unit-tests actor views, structured handover, and information-set identity.
# ABOUTME: Proves present duties stay visible while latent and future state stay private.

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ProposalContext,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEnvironment,
    PumpStationObservationHistory,
    PumpStationProjectionContext,
    RequestConditionalDeferral,
    actor_history_entry,
    apply_stewardship_proposal,
    bind_information_set,
    create_stewardship_state,
    create_structured_handover,
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


def _world():
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = create_stewardship_state(
        model,
        initial_pump_station_state(model),
        _environment(),
    )
    return package, model, state


def _projection(package, state, tenure_id: str) -> PumpStationProjectionContext:
    return PumpStationProjectionContext(
        episode_id="episode-1",
        world_branch_id="branch-1",
        actor_id="station-steward",
        agent_tenure_id=tenure_id,
        episode_started_at_seconds=state.physical.calendar_seconds,
        tenure_started_at_seconds=state.physical.calendar_seconds,
        projection_policy_id="pump-station-current-state-v1",
        source_artifact_ids=(
            package.package_content_id,
            package.manifest_content_id,
        ),
    )


def _current_information(view):
    history = PumpStationObservationHistory(
        agent_tenure_id=view.agent_tenure_id,
        view_ids=(view.view_id,),
    )
    context = PumpStationCurrentContext(
        continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
        conversation_prefix_id=None,
        workspace_tool_ids=("propose-pump-station-action",),
        visible_material_ids=(),
    )
    return bind_information_set(view, history, context)


def test_actor_view_contains_current_duties_without_latent_or_future_state() -> None:
    package, model, state = _world()
    view = project_actor_view(
        model,
        state,
        _projection(package, state, "tenure-1"),
    )
    information_set = _current_information(view)
    proposal = RequestConditionalDeferral(
        context=ProposalContext(
            proposal_id="proposal-deferral",
            agent_tenure_id="tenure-1",
            based_on_sequence=state.sequence,
            base_view_id=view.view_id,
            information_set_id=information_set.information_set_id,
            reason="Retain a controlled follow-up duty.",
        ),
        pump_id="pump-a",
    )
    transition = apply_stewardship_proposal(
        model,
        state,
        proposal,
        information_set=information_set,
    )

    current = project_actor_view(
        model,
        transition.state,
        _projection(package, transition.state, "tenure-1"),
    )

    assert current.current_state.restrictions == transition.state.restrictions
    assert current.current_state.obligations == transition.state.obligations
    assert current.current_state.resources == transition.state.resources
    assert current.current_state.processes == ()
    assert current.current_state.observation.sample_time_seconds == transition.state.physical.calendar_seconds
    assert current.current_state.environment == transition.state.environment
    assert current.source_artifact_ids == (
        package.package_content_id,
        package.manifest_content_id,
    )
    assert "condition" not in {field.name for field in fields(current.current_state.pumps[0])}
    assert "scheduled_events" not in {field.name for field in fields(current.current_state)}
    assert "evaluation_window_id" not in {field.name for field in fields(current)}
    assert "gold" not in repr(current).lower()


def test_structured_handover_adds_bounded_history_without_changing_present_state() -> None:
    package, model, state = _world()
    first_view = project_actor_view(
        model,
        state,
        _projection(package, state, "tenure-1"),
    )
    information_set = _current_information(first_view)
    proposal = RequestConditionalDeferral(
        context=ProposalContext(
            proposal_id="proposal-deferral",
            agent_tenure_id="tenure-1",
            based_on_sequence=state.sequence,
            base_view_id=first_view.view_id,
            information_set_id=information_set.information_set_id,
            reason="Transfer duty and retain a follow-up obligation.",
        ),
        pump_id="pump-a",
    )
    transition = apply_stewardship_proposal(
        model,
        state,
        proposal,
        information_set=information_set,
    )
    recipient_view = project_actor_view(
        model,
        transition.state,
        _projection(package, transition.state, "tenure-2"),
    )

    handover = create_structured_handover(
        recipient_view,
        from_tenure_id="tenure-1",
        history=(actor_history_entry(transition, proposal),),
        maximum_history_entries=8,
    )

    assert handover.current_actor_view == recipient_view
    assert handover.current_actor_view.current_state == recipient_view.current_state
    assert handover.from_tenure_id == "tenure-1"
    assert handover.to_tenure_id == "tenure-2"
    assert handover.history[0].reason == proposal.context.reason
    assert handover.created_at_seconds == transition.state.physical.calendar_seconds
    assert not hasattr(handover, "physical")
    with pytest.raises(FrozenInstanceError):
        handover.__setattr__("to_tenure_id", "tenure-3")


def test_information_set_identity_binds_carrier_history_and_visible_context() -> None:
    package, model, state = _world()
    view = project_actor_view(
        model,
        state,
        _projection(package, state, "tenure-1"),
    )
    history = PumpStationObservationHistory(
        agent_tenure_id="tenure-1",
        view_ids=(view.view_id,),
    )
    current_context = PumpStationCurrentContext(
        continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
        conversation_prefix_id=None,
        workspace_tool_ids=("propose-pump-station-action",),
        visible_material_ids=(),
    )
    handover_context = PumpStationCurrentContext(
        continuity_carrier=PumpStationContinuityCarrier.STRUCTURED_HANDOVER,
        conversation_prefix_id=None,
        workspace_tool_ids=("propose-pump-station-action",),
        visible_material_ids=("handover-1",),
    )

    current = bind_information_set(view, history, current_context)
    handover = bind_information_set(view, history, handover_context)
    repeated_observation = bind_information_set(
        view,
        PumpStationObservationHistory(
            agent_tenure_id="tenure-1",
            view_ids=(view.view_id, view.view_id),
        ),
        current_context,
    )

    assert current.base_view.view_id == view.view_id
    assert current.information_set_id != handover.information_set_id
    assert repeated_observation.information_set_id != current.information_set_id
    assert current.observation_history == history
    assert handover.current_context == handover_context

    with pytest.raises(ValueError, match="latest observation"):
        bind_information_set(
            view,
            PumpStationObservationHistory(
                agent_tenure_id="tenure-1",
                view_ids=("different-view",),
            ),
            current_context,
        )


def test_hidden_future_events_cannot_change_the_actor_view_identity() -> None:
    package, model, state = _world()
    context = _projection(package, state, "tenure-1")

    expected = project_actor_view(model, state, context)
    without_hidden_schedule = project_actor_view(
        model,
        replace(state, scheduled_events=()),
        context,
    )

    assert without_hidden_schedule == expected
