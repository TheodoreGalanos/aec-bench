# ABOUTME: Integration-tests immutable proposal binding and independent task replay.
# ABOUTME: Proves stale context and altered receipts fail without favourable reinterpretation.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ProposalContext,
    PumpStationAuthorityOutcome,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEnvironment,
    PumpStationObservationHistory,
    PumpStationProjectionContext,
    PumpStationRunStep,
    RequestConditionalDeferral,
    TransferDuty,
    apply_stewardship_proposal,
    bind_information_set,
    create_stewardship_state,
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


def _world():
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = create_stewardship_state(
        model,
        initial_pump_station_state(model),
        _environment(),
    )
    projection = PumpStationProjectionContext(
        episode_id="episode-1",
        world_branch_id="branch-1",
        actor_id="station-steward",
        agent_tenure_id="tenure-1",
        episode_started_at_seconds=state.physical.calendar_seconds,
        tenure_started_at_seconds=state.physical.calendar_seconds,
        projection_policy_id="pump-station-current-state-v1",
        source_artifact_ids=(
            package.package_content_id,
            package.manifest_content_id,
        ),
    )
    return model, state, projection


def _bound_context(model, state, projection, proposal_id: str):
    view = project_actor_view(model, state, projection)
    information_set = bind_information_set(
        view,
        PumpStationObservationHistory(
            agent_tenure_id=projection.agent_tenure_id,
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
        agent_tenure_id=projection.agent_tenure_id,
        based_on_sequence=state.sequence,
        base_view_id=view.view_id,
        information_set_id=information_set.information_set_id,
        reason="Bound verifier test action.",
    )
    return context, information_set


def test_verifier_replays_a_bound_transition_without_mutating_the_run() -> None:
    model, initial_state, projection = _world()
    context, information_set = _bound_context(
        model,
        initial_state,
        projection,
        "proposal-deferral",
    )
    proposal = RequestConditionalDeferral(context=context, pump_id="pump-a")
    transition = apply_stewardship_proposal(
        model,
        initial_state,
        proposal,
        information_set=information_set,
    )
    step = PumpStationRunStep(
        proposal=proposal,
        information_set=information_set,
        transition=transition,
    )

    report = verify_stewardship_run(model, initial_state, (step,))

    assert report.valid is True
    assert report.issues == ()
    assert report.replayed_transition_ids == (transition.receipt.transition_id,)
    assert report.final_state_id == transition.receipt.post_state_id
    assert initial_state.sequence == 0


def test_verifier_rejects_an_altered_receipt() -> None:
    model, initial_state, projection = _world()
    context, information_set = _bound_context(
        model,
        initial_state,
        projection,
        "proposal-deferral",
    )
    proposal = RequestConditionalDeferral(context=context, pump_id="pump-a")
    transition = apply_stewardship_proposal(
        model,
        initial_state,
        proposal,
        information_set=information_set,
    )
    altered = replace(
        transition,
        receipt=replace(transition.receipt, post_state_id="altered-state"),
    )

    report = verify_stewardship_run(
        model,
        initial_state,
        (
            PumpStationRunStep(
                proposal=proposal,
                information_set=information_set,
                transition=altered,
            ),
        ),
    )

    assert report.valid is False
    assert "transition-replay-mismatch:transition-0001" in report.issues


def test_stale_view_and_information_set_are_invalid_before_execution() -> None:
    model, state, projection = _world()
    first_context, first_information_set = _bound_context(
        model,
        state,
        projection,
        "proposal-deferral",
    )
    first_proposal = RequestConditionalDeferral(
        context=first_context,
        pump_id="pump-a",
    )
    state = apply_stewardship_proposal(
        model,
        state,
        first_proposal,
        information_set=first_information_set,
    ).state
    stale_proposal = TransferDuty(
        context=replace(
            first_context,
            proposal_id="proposal-stale-transfer",
            reason="This proposal uses an old view.",
        ),
    )

    invalid = apply_stewardship_proposal(
        model,
        state,
        stale_proposal,
        information_set=first_information_set,
    )

    assert invalid.receipt.authority is not None
    assert invalid.receipt.authority.outcome is PumpStationAuthorityOutcome.INVALID
    assert invalid.state.physical == state.physical
    assert invalid.state.restrictions == state.restrictions
    assert invalid.state.obligations == state.obligations
    assert "stale" in invalid.receipt.authority.detail
