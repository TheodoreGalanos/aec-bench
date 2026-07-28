# ABOUTME: Exercises one timed pump-station episode across a fresh actor tenure.
# ABOUTME: Proves handover carries duties while the station and episode continue.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ContinueOperation,
    ProposalContext,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEnvironment,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationObservationHistory,
    PumpStationProjectionContext,
    PumpStationRunStep,
    RequestConditionalDeferral,
    RequestInspection,
    TransferDuty,
    actor_history_entry,
    apply_stewardship_proposal,
    bind_information_set,
    create_stewardship_state,
    create_structured_handover,
    initial_pump_station_state,
    load_reference_package,
    project_actor_view,
    pump_station_model_from_package,
    verify_stewardship_run,
)


def _environment() -> PumpStationEnvironment:
    return PumpStationEnvironment(
        inflow_m3_s=Decimal("0.0155"),
        wet_well_level_m=Decimal("1.65"),
        isolated=False,
    )


def _projection(package, state, tenure_id: str, *, episode_start: int):
    return PumpStationProjectionContext(
        episode_id="episode-live-1",
        world_branch_id="branch-live-1",
        actor_id="station-steward",
        agent_tenure_id=tenure_id,
        episode_started_at_seconds=episode_start,
        tenure_started_at_seconds=state.physical.calendar_seconds,
        projection_policy_id="pump-station-current-state-v1",
        source_artifact_ids=(
            package.package_content_id,
            package.manifest_content_id,
        ),
    )


def _bound_proposal(
    model,
    state,
    projection,
    proposal_id: str,
    reason: str,
    history_ids: tuple[str, ...],
    current_context,
):
    view = project_actor_view(model, state, projection)
    information_set = bind_information_set(
        view,
        PumpStationObservationHistory(
            agent_tenure_id=projection.agent_tenure_id,
            view_ids=(*history_ids, view.view_id),
        ),
        current_context,
    )
    context = ProposalContext(
        proposal_id=proposal_id,
        agent_tenure_id=projection.agent_tenure_id,
        based_on_sequence=state.sequence,
        base_view_id=view.view_id,
        information_set_id=information_set.information_set_id,
        reason=reason,
    )
    return context, information_set, (*history_ids, view.view_id)


def test_timed_episode_continues_through_fresh_tenure_handover_and_replay() -> None:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    initial_state = create_stewardship_state(
        model,
        initial_pump_station_state(model),
        _environment(),
    )
    episode_start = initial_state.physical.calendar_seconds
    first_projection = _projection(
        package,
        initial_state,
        "tenure-1",
        episode_start=episode_start,
    )
    current_context = PumpStationCurrentContext(
        continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
        conversation_prefix_id=None,
        workspace_tool_ids=("propose-pump-station-action",),
        visible_material_ids=(),
    )
    context, information_set, _ = _bound_proposal(
        model,
        initial_state,
        first_projection,
        "proposal-01-deferral",
        "Transfer duty and retain an inspection obligation.",
        (),
        current_context,
    )
    deferral = RequestConditionalDeferral(context=context, pump_id="pump-a")
    first_transition = apply_stewardship_proposal(
        model,
        initial_state,
        deferral,
        information_set=information_set,
    )
    steps = [
        PumpStationRunStep(
            proposal=deferral,
            information_set=information_set,
            transition=first_transition,
        )
    ]
    state = first_transition.state
    history_entry = actor_history_entry(first_transition, deferral)

    second_projection = _projection(
        package,
        state,
        "tenure-2",
        episode_start=episode_start,
    )
    recipient_view = project_actor_view(model, state, second_projection)
    handover = create_structured_handover(
        recipient_view,
        from_tenure_id="tenure-1",
        history=(history_entry,),
        maximum_history_entries=8,
    )
    assert handover.current_actor_view.current_state == recipient_view.current_state
    assert handover.created_at_seconds == state.physical.calendar_seconds
    assert handover.current_actor_view.episode_elapsed_seconds == 0

    handover_context = replace(
        current_context,
        continuity_carrier=PumpStationContinuityCarrier.STRUCTURED_HANDOVER,
        visible_material_ids=(handover.handover_id,),
    )
    tenure_history: tuple[str, ...] = ()

    context, info, tenure_history = _bound_proposal(
        model,
        state,
        second_projection,
        "proposal-02-transfer",
        "Comply with the carried restriction.",
        tenure_history,
        handover_context,
    )
    transfer = TransferDuty(context=context)
    transition = apply_stewardship_proposal(
        model,
        state,
        transfer,
        information_set=info,
    )
    steps.append(
        PumpStationRunStep(
            proposal=transfer,
            information_set=info,
            transition=transition,
        )
    )
    state = transition.state

    context, info, tenure_history = _bound_proposal(
        model,
        state,
        second_projection,
        "proposal-03-inspection",
        "Discharge the carried follow-up obligation.",
        tenure_history,
        handover_context,
    )
    inspection = RequestInspection(context=context, pump_id="pump-a")
    transition = apply_stewardship_proposal(
        model,
        state,
        inspection,
        information_set=info,
    )
    steps.append(
        PumpStationRunStep(
            proposal=inspection,
            information_set=info,
            transition=transition,
        )
    )
    state = transition.state

    context, info, tenure_history = _bound_proposal(
        model,
        state,
        second_projection,
        "proposal-04-complete-inspection",
        "Continue until the next declared decision point.",
        tenure_history,
        handover_context,
    )
    continuation = ContinueOperation(context=context)
    transition = apply_stewardship_proposal(
        model,
        state,
        continuation,
        information_set=info,
    )
    steps.append(
        PumpStationRunStep(
            proposal=continuation,
            information_set=info,
            transition=transition,
        )
    )
    state = transition.state

    final_view = project_actor_view(model, state, second_projection)
    verification = verify_stewardship_run(
        model,
        initial_state,
        tuple(steps),
    )

    assert final_view.episode_elapsed_seconds == model.inflow.diagnostic_period_seconds
    assert final_view.tenure_elapsed_seconds == model.inflow.diagnostic_period_seconds
    assert (
        state.obligation(
            PumpStationObligationKind.DEFERRED_FOLLOW_UP,
            "pump-a",
        ).status
        is PumpStationObligationStatus.FULFILLED
    )
    assert verification.valid is True
    assert verification.final_state_id == transition.receipt.post_state_id
    assert tuple(step.transition.receipt.sequence for step in steps) == (1, 2, 3, 4)
