# ABOUTME: Tests current root controls in the separate task-local host-control envelope.
# ABOUTME: Proves that the installed actor surface cannot accept the root-control payload.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.continual_world import ContinualWorldActorRequest
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    pump_station_actor_capabilities,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
)


def _bound_control() -> PumpStationBoundControlRequest:
    return PumpStationBoundControlRequest(
        request_id="control-power-unavailable",
        run_id="run-v4",
        episode_id="episode-v4",
        world_branch_id="branch-v4",
        base_state_id="state-v4-004",
        base_commit_id="commit-v4-004",
        based_on_sequence=4,
        control=PumpStationCommonBoundaryRequest(
            request_id="control-power-unavailable",
            authority_id="operations-controller",
            boundary_kind="power",
            available=False,
            base_state_id="state-v4-004",
        ),
    )


def test_bound_root_control_uses_only_the_task_local_control_surface() -> None:
    bound_control = _bound_control()
    actor_actions = {
        item.name
        for item in pump_station_actor_capabilities(
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            temporal_repository_verified=True,
        ).actions
    }
    assert actor_actions.isdisjoint({"operations_review", "process_outcome", "common_boundary"})

    with pytest.raises(
        ValidationError,
        match="extra_forbidden",
    ):
        ContinualWorldActorRequest.model_validate(
            {
                "operation": "capabilities",
                "control_request": bound_control,
            }
        )
