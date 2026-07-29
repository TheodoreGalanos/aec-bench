# ABOUTME: Defines the strict shared request, result, and dynamic snapshot expectations for world sessions.
# ABOUTME: Keeps asset actions and physical state outside the promoted host-execution contract.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
)


def _snapshot() -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
        run_id="run-1",
        episode_id="episode-1",
        world_branch_id="branch-1",
        sequence=3,
        state_id="state-3",
        commit_id="commit-3",
    )


def test_world_session_request_requires_exact_resume_snapshot() -> None:
    request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id="session-2",
        task_world_id="wastewater-pump-station-stewardship.v1",
        agent_tenure_id="tenure-2",
        run_id="run-1",
        episode_id="episode-1",
        world_branch_id="branch-1",
        start_snapshot=_snapshot(),
    )

    assert request.start_snapshot == _snapshot()
    with pytest.raises(ValidationError, match="resume request requires"):
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="session-2",
            task_world_id="wastewater-pump-station-stewardship.v1",
            agent_tenure_id="tenure-2",
            run_id="run-1",
            episode_id="episode-1",
            world_branch_id="branch-1",
        )


def test_world_session_contract_rejects_unused_fields_and_duplicate_tools() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorldSessionRequest.model_validate(
            {
                "execution_kind": "stewardship_world_session",
                "open_mode": "start",
                "session_id": "session-1",
                "task_world_id": "wastewater-pump-station-stewardship.v1",
                "agent_tenure_id": "tenure-1",
                "run_id": "run-1",
                "episode_id": "episode-1",
                "world_branch_id": "branch-1",
                "future_options": {},
            }
        )

    with pytest.raises(ValidationError, match="tool names must be distinct"):
        WorldSessionResult(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.START,
            session_id="session-1",
            task_world_id="wastewater-pump-station-stewardship.v1",
            agent_tenure_id="tenure-1",
            snapshot=_snapshot(),
            actor_view_id="view-1",
            information_set_id="information-1",
            tool_names=("observe_pump_station", "observe_pump_station"),
        )
