# ABOUTME: Tests the strict task-neutral actor and host-control interface contracts.
# ABOUTME: Covers exact bindings, immutable content identity, and closed control operations.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.world_interface import (
    WorldActorActionCapability,
    WorldActorActionRequest,
    WorldActorBinding,
    WorldActorCapabilityCatalogue,
    WorldControlRequest,
)
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)


def _binding() -> WorldActorBinding:
    return WorldActorBinding(
        task_world_id="wastewater-pump-station-stewardship.v1",
        session_id="session-1",
        run_id="run-1",
        episode_id="episode-1",
        world_branch_id="branch-1",
        sequence=3,
        state_id="state-3",
        commit_id="commit-3",
        agent_tenure_id="tenure-1",
        actor_view_id="view-3",
        information_set_id="information-3",
    )


def _session_request(open_mode: WorldSessionOpenMode) -> WorldSessionRequest:
    start_snapshot = (
        StewardshipStateSnapshotRef(
            run_id="run-1",
            episode_id="episode-1",
            world_branch_id="branch-1",
            sequence=3,
            state_id="state-3",
            commit_id="commit-3",
        )
        if open_mode is WorldSessionOpenMode.RESUME
        else None
    )
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=open_mode,
        session_id="session-1",
        task_world_id="wastewater-pump-station-stewardship.v1",
        agent_tenure_id="tenure-1",
        run_id="run-1",
        episode_id="episode-1",
        world_branch_id="branch-1",
        start_snapshot=start_snapshot,
    )


def test_actor_contract_is_exact_bound_content_addressed_and_deeply_immutable() -> None:
    capability = WorldActorActionCapability(
        name="continue_operation",
        description="Continue to the next declared decision point.",
        input_schema={"type": "object", "required": ["reason"]},
    )
    catalogue = WorldActorCapabilityCatalogue(
        task_world_id=_binding().task_world_id,
        interface_version="pump-station.actor.v1",
        observation_schema_ref="pump-station.actor-view.v2",
        actions=(capability,),
    )
    request = WorldActorActionRequest(
        request_id="request-1",
        action_name=capability.name,
        binding=_binding(),
        arguments={"reason": "Continue operation."},
    )

    assert len(catalogue.content_sha256) == 64
    assert len(request.content_sha256) == 64
    assert request.binding.world_branch_id == "branch-1"
    with pytest.raises(TypeError, match="immutable"):
        request.arguments["reason"] = "Changed"


def test_actor_contract_rejects_duplicate_actions_and_invalid_sequence() -> None:
    capability = WorldActorActionCapability(
        name="continue_operation",
        description="Continue to the next declared decision point.",
        input_schema={"type": "object"},
    )
    with pytest.raises(ValidationError, match="actor action names must be distinct"):
        WorldActorCapabilityCatalogue(
            task_world_id=_binding().task_world_id,
            interface_version="pump-station.actor.v1",
            observation_schema_ref="pump-station.actor-view.v2",
            actions=(capability, capability),
        )
    with pytest.raises(ValidationError, match="actor binding sequence must be non-negative"):
        WorldActorBinding(**{**_binding().model_dump(), "sequence": -1})


def test_control_request_requires_the_session_mode_for_each_open_operation() -> None:
    with pytest.raises(ValidationError, match="create_session requires start mode"):
        WorldControlRequest(
            request_id="control-1",
            operation="create_session",
            task_world_id=_binding().task_world_id,
            authority_id="host-1",
            session_request=_session_request(WorldSessionOpenMode.RESUME),
        )
    with pytest.raises(ValidationError, match="resume_session requires resume mode"):
        WorldControlRequest(
            request_id="control-2",
            operation="resume_session",
            task_world_id=_binding().task_world_id,
            authority_id="host-1",
            session_request=_session_request(WorldSessionOpenMode.START),
        )
    with pytest.raises(ValidationError, match="does not accept raw state"):
        WorldControlRequest.model_validate(
            {
                "request_id": "control-3",
                "operation": "snapshot",
                "task_world_id": _binding().task_world_id,
                "authority_id": "host-1",
                "raw_state": {"sequence": 99},
            }
        )
