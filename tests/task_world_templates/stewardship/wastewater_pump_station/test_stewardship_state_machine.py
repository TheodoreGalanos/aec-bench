# ABOUTME: Integration-tests wastewater pump-station stewardship events over the physical kernel.
# ABOUTME: Covers trigger order, duty exposure, and interruption before a physical effect.

from __future__ import annotations

from decimal import Decimal

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ContinueOperation,
    OperatingInterval,
    ProposalContext,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEnvironment,
    PumpStationEventType,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationObservationHistory,
    PumpStationProcessStatus,
    PumpStationProjectionContext,
    PumpStationSchedule,
    RequestConditionalDeferral,
    RequestInspection,
    RequestObstructionClearance,
    TransferDuty,
    advance_pump_station,
    advance_to_next_decision_point,
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


def _degraded_physical_state(model):
    return advance_pump_station(
        model,
        initial_pump_station_state(model),
        OperatingInterval(
            elapsed_seconds=7_200_000,
            duty_runtime_seconds=7_200_000,
            duty_completed_starts=1_000,
            environment=_environment(),
        ),
    ).state


def _bound_context(model, state, proposal_id: str):
    package = load_reference_package()
    view = project_actor_view(
        model,
        state,
        PumpStationProjectionContext(
            episode_id="episode-integration",
            world_branch_id="branch-integration",
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
        based_on_sequence=state.sequence,
        base_view_id=view.view_id,
        information_set_id=information_set.information_set_id,
        reason="Integration journey.",
    )
    return context, information_set


def test_deferral_trigger_and_resource_events_use_canonical_order() -> None:
    model = pump_station_model_from_package(load_reference_package())
    state = create_stewardship_state(
        model,
        _degraded_physical_state(model),
        _environment(),
    )
    pump_a_runtime = state.physical.pump("pump-a").exposure.runtime_seconds

    context, information_set = _bound_context(
        model,
        state,
        "proposal-deferral",
    )
    state = apply_stewardship_proposal(
        model,
        state,
        RequestConditionalDeferral(
            context=context,
            pump_id="pump-a",
        ),
        information_set=information_set,
    ).state
    context, information_set = _bound_context(
        model,
        state,
        "proposal-transfer",
    )
    state = apply_stewardship_proposal(
        model,
        state,
        TransferDuty(context=context),
        information_set=information_set,
    ).state
    context, information_set = _bound_context(
        model,
        state,
        "proposal-continue",
    )
    advanced = apply_stewardship_proposal(
        model,
        state,
        ContinueOperation(context=context),
        information_set=information_set,
    )

    assert advanced.receipt.applied_event_types == (
        PumpStationEventType.OBLIGATION_DUE,
        PumpStationEventType.ACCESS_AVAILABLE,
        PumpStationEventType.REPAIR_KIT_AVAILABLE,
    )
    assert (
        advanced.state.obligation(
            PumpStationObligationKind.DEFERRED_FOLLOW_UP,
            "pump-a",
        ).status
        is PumpStationObligationStatus.DUE
    )
    assert advanced.state.physical.pump("pump-a").exposure.runtime_seconds == pump_a_runtime
    assert advanced.state.physical.pump("pump-b").exposure.runtime_seconds == (model.resources.repair_kit_lead_seconds)
    assert advanced.state.resources.access_window_seconds == model.resources.access_duration_seconds
    assert advanced.state.resources.repair_kit_available is True


def test_access_withdrawal_before_completion_interrupts_without_physical_effect() -> None:
    model = pump_station_model_from_package(load_reference_package())
    diagnostic = model.inflow.diagnostic_period_seconds
    access = model.resources.access_duration_seconds
    state = create_stewardship_state(
        model,
        _degraded_physical_state(model),
        _environment(),
        schedule=PumpStationSchedule(
            access_available_after_seconds=0,
            repair_kit_available_after_seconds=0,
            access_withdrawal_after_seconds=diagnostic + access,
        ),
    )
    state = advance_to_next_decision_point(model, state).state
    context, information_set = _bound_context(
        model,
        state,
        "proposal-inspection",
    )
    state = apply_stewardship_proposal(
        model,
        state,
        RequestInspection(
            context=context,
            pump_id="pump-a",
        ),
        information_set=information_set,
    ).state
    state = advance_to_next_decision_point(model, state).state
    inspection = state.latest_inspection("pump-a")
    context, information_set = _bound_context(
        model,
        state,
        "proposal-transfer",
    )
    state = apply_stewardship_proposal(
        model,
        state,
        TransferDuty(context=context),
        information_set=information_set,
    ).state
    before = state.physical
    context, information_set = _bound_context(
        model,
        state,
        "proposal-clear",
    )
    state = apply_stewardship_proposal(
        model,
        state,
        RequestObstructionClearance(
            context=context,
            pump_id="pump-a",
            inspection_evidence_id=inspection.evidence_id,
        ),
        information_set=information_set,
    ).state

    interrupted = advance_to_next_decision_point(model, state)

    assert interrupted.receipt.applied_event_types == (
        PumpStationEventType.ACCESS_WITHDRAWN,
        PumpStationEventType.PROCESS_COMPLETION,
    )
    assert interrupted.state.physical.pump("pump-a").condition == before.pump("pump-a").condition
    assert interrupted.state.processes[-1].status is PumpStationProcessStatus.INTERRUPTED
    assert interrupted.state.resources.access_window_seconds == 0
