# ABOUTME: Builds bound proposals and deterministic schedules for ASW-5 tests.
# ABOUTME: Uses real pump-station projections, evidence binding, and state transitions.

from __future__ import annotations

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ProposalContext,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationInformationSet,
    PumpStationModel,
    PumpStationObservationHistory,
    PumpStationProcess,
    PumpStationProcessKind,
    PumpStationProjectionContext,
    PumpStationSchedule,
    PumpStationStewardshipState,
    PumpStationTransition,
    apply_stewardship_proposal,
    bind_information_set,
    load_reference_package,
    project_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationProposal,
)


def rich_work_schedule(model: PumpStationModel) -> PumpStationSchedule:
    """Return a short deterministic schedule with one access interruption."""
    return PumpStationSchedule(
        access_available_after_seconds=0,
        repair_kit_available_after_seconds=0,
        access_withdrawal_after_seconds=1,
        access_restored_after_seconds=2,
    )


def bind_proposal(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal_type: type[PumpStationProposal],
    proposal_id: str,
    *,
    tenure_id: str = "tenure-rich-1",
    **parameters: str,
) -> tuple[PumpStationProposal, PumpStationInformationSet]:
    """Bind one proposal to an exact live rich-work actor view."""
    package = load_reference_package()
    view = project_actor_view(
        model,
        state,
        PumpStationProjectionContext(
            episode_id="episode-rich-work",
            world_branch_id="branch-rich-work",
            actor_id="station-steward",
            agent_tenure_id=tenure_id,
            episode_started_at_seconds=state.physical.calendar_seconds,
            tenure_started_at_seconds=state.physical.calendar_seconds,
            projection_policy_id="pump-station-current-state.v2",
            source_artifact_ids=(
                package.package_content_id,
                package.manifest_content_id,
            ),
        ),
    )
    information_set = bind_information_set(
        view,
        PumpStationObservationHistory(
            agent_tenure_id=tenure_id,
            view_ids=(view.view_id,),
        ),
        PumpStationCurrentContext(
            continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
            conversation_prefix_id=None,
            workspace_tool_ids=("propose-pump-station-action",),
            visible_material_ids=(),
        ),
    )
    proposal = proposal_type(
        context=ProposalContext(
            proposal_id=proposal_id,
            agent_tenure_id=tenure_id,
            based_on_sequence=state.sequence,
            base_view_id=view.view_id,
            information_set_id=information_set.information_set_id,
            reason="Exercise the frozen rich-work rule.",
        ),
        **parameters,
    )
    return proposal, information_set


def apply_bound(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal_type: type[PumpStationProposal],
    proposal_id: str,
    *,
    tenure_id: str = "tenure-rich-1",
    **parameters: str,
) -> PumpStationTransition:
    """Apply one exactly bound proposal through the production state machine."""
    proposal, information_set = bind_proposal(
        model,
        state,
        proposal_type,
        proposal_id,
        tenure_id=tenure_id,
        **parameters,
    )
    return apply_stewardship_proposal(
        model,
        state,
        proposal,
        information_set=information_set,
    )


def latest_process(
    state: PumpStationStewardshipState,
    kind: PumpStationProcessKind,
    pump_id: str,
) -> PumpStationProcess:
    """Return the latest process of one kind for one pump."""
    for process in reversed(state.processes):
        if process.kind is kind and process.pump_id == pump_id:
            return process
    raise LookupError(f"missing {kind.value} process for {pump_id}")
