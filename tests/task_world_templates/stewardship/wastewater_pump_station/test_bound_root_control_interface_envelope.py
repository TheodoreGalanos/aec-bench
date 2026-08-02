# ABOUTME: Tests V4 root controls in the separate task-local host-control envelope.
# ABOUTME: Proves that the installed actor surface cannot accept the root-control payload.

from __future__ import annotations

from dataclasses import asdict

import pytest
from pydantic import ValidationError

from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    pump_station_actor_capabilities_v2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.local_interface import (
    PumpStationLocalInterfaceRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_BOUND_CONTROL_VERSION,
    PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
)


def _bound_control() -> PumpStationBoundControlRequest:
    return PumpStationBoundControlRequest(
        control_envelope_version=PUMP_STATION_BOUND_CONTROL_VERSION,
        request_id="control-power-unavailable",
        run_id="run-v4",
        episode_id="episode-v4",
        world_branch_id="branch-v4",
        base_state_id="state-v4-004",
        base_commit_id="commit-v4-004",
        based_on_sequence=4,
        control=PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="control-power-unavailable",
            authority_id="operations-controller",
            boundary_kind="power",
            available=False,
            base_state_id="state-v4-004",
        ),
    )


def _resumed_session() -> WorldSessionRequest:
    snapshot = StewardshipStateSnapshotRef(
        run_id="run-v4",
        episode_id="episode-v4",
        world_branch_id="branch-v4",
        sequence=4,
        state_id="state-v4-004",
        commit_id="commit-v4-004",
    )
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id="session-v4",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="tenure-v4",
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        start_snapshot=snapshot,
    )


def test_bound_v4_root_control_uses_only_the_task_local_control_surface() -> None:
    bound_control = _bound_control()

    request = PumpStationLocalInterfaceRequest.model_validate(
        {
            "surface": "control",
            "operation": "execute",
            "control_request": asdict(bound_control),
        }
    )

    assert request.control_request == bound_control
    assert isinstance(request.control_request, PumpStationBoundControlRequest)
    actor_actions = {
        item.name
        for item in pump_station_actor_capabilities_v2(
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            temporal_repository_verified=True,
        ).actions
    }
    assert actor_actions.isdisjoint({"operations_review", "process_outcome", "common_boundary"})

    with pytest.raises(
        ValidationError,
        match="actor local-interface request cannot contain host control",
    ):
        PumpStationLocalInterfaceRequest(
            surface="actor",
            operation="capabilities",
            session_request=_resumed_session(),
            control_request=bound_control,
        )
