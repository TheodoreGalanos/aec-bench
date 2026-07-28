# ABOUTME: Builds real pump-station world-run fixtures for persistence tests.
# ABOUTME: Uses the certified package, task projector, and production state machine without mocks.

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ProposalContext,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEnvironment,
    PumpStationInformationSet,
    PumpStationObservationHistory,
    PumpStationProjectionContext,
    PumpStationWorldRun,
    PumpStationWorldRunRepository,
    bind_information_set,
    create_stewardship_state,
    initial_pump_station_state,
    load_reference_package,
    project_actor_view,
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationProposal,
)


def create_world_run(root: Path) -> PumpStationWorldRun:
    """Create one real durable run from the certified package."""
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    state = create_stewardship_state(
        model,
        initial_pump_station_state(model),
        PumpStationEnvironment(
            inflow_m3_s=Decimal("0.0155"),
            wet_well_level_m=Decimal("1.65"),
            isolated=False,
        ),
    )
    return PumpStationWorldRun.create(
        repository=PumpStationWorldRunRepository(root),
        package=package,
        model=model,
        initial_state=state,
        run_id="run-durable-1",
        episode_id="episode-durable-1",
        world_branch_id="branch-durable-1",
    )


def bind_proposal(
    run: PumpStationWorldRun,
    proposal_type: type[PumpStationProposal],
    proposal_id: str,
    **parameters: str,
) -> tuple[PumpStationProposal, PumpStationInformationSet]:
    """Bind one proposal to the run's exact current actor view."""
    package = load_reference_package()
    state = run.state
    view = project_actor_view(
        run.model,
        state,
        PumpStationProjectionContext(
            episode_id=run.manifest.episode_id,
            world_branch_id=run.manifest.world_branch_id,
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
    proposal = proposal_type(
        context=ProposalContext(
            proposal_id=proposal_id,
            agent_tenure_id="tenure-1",
            based_on_sequence=state.sequence,
            base_view_id=view.view_id,
            information_set_id=information_set.information_set_id,
            reason="Exercise durable world-run publication.",
        ),
        **parameters,
    )
    return proposal, information_set
