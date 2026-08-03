# ABOUTME: Tests the strict task-neutral actor and host-control interface contracts.
# ABOUTME: Covers opaque actor decisions, strict payloads, and closed control operations.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.world_interface import (
    WorldActorActionCapability,
    WorldActorActionRequest,
    WorldActorCapabilityCatalogue,
    WorldControlRequest,
)
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)

_TASK_WORLD_ID = "wastewater-pump-station-stewardship.v1"


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


def test_actor_contract_uses_only_an_opaque_decision_and_task_action() -> None:
    capability = WorldActorActionCapability(
        name="continue_operation",
        description="Continue to the next declared decision point.",
        input_schema={"type": "object", "required": ["reason"]},
    )
    catalogue = WorldActorCapabilityCatalogue(
        task_world_id=_TASK_WORLD_ID,
        actions=(capability,),
    )
    request = WorldActorActionRequest(
        request_id="request-1",
        decision_id="opaque-decision",
        action_name=capability.name,
        arguments={"reason": "Continue operation."},
    )

    assert request.decision_id == "opaque-decision"
    assert "schema_version" not in type(request).model_fields
    assert "content_sha256" not in type(request).model_fields
    assert "binding" not in type(request).model_fields
    assert "interface_version" not in type(catalogue).model_fields
    with pytest.raises(TypeError, match="immutable"):
        request.arguments["reason"] = "Changed"


def test_actor_contract_rejects_duplicate_actions_and_old_binding_payloads() -> None:
    capability = WorldActorActionCapability(
        name="continue_operation",
        description="Continue to the next declared decision point.",
        input_schema={"type": "object"},
    )
    with pytest.raises(ValidationError, match="actor action names must be distinct"):
        WorldActorCapabilityCatalogue(
            task_world_id=_TASK_WORLD_ID,
            actions=(capability, capability),
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorldActorActionRequest.model_validate(
            {
                "schema_version": "aecbench.world-actor-interface.v1",
                "request_id": "old-request",
                "action_name": capability.name,
                "arguments": {},
                "binding": {"run_id": "old-run"},
            }
        )


def test_control_request_requires_the_session_mode_for_each_open_operation() -> None:
    with pytest.raises(ValidationError, match="create_session requires start mode"):
        WorldControlRequest(
            request_id="control-1",
            operation="create_session",
            task_world_id=_TASK_WORLD_ID,
            authority_id="host-1",
            session_request=_session_request(WorldSessionOpenMode.RESUME),
        )
    with pytest.raises(ValidationError, match="resume_session requires resume mode"):
        WorldControlRequest(
            request_id="control-2",
            operation="resume_session",
            task_world_id=_TASK_WORLD_ID,
            authority_id="host-1",
            session_request=_session_request(WorldSessionOpenMode.START),
        )
    with pytest.raises(ValidationError, match="does not accept raw state"):
        WorldControlRequest.model_validate(
            {
                "request_id": "control-3",
                "operation": "snapshot",
                "task_world_id": _TASK_WORLD_ID,
                "authority_id": "host-1",
                "raw_state": {"sequence": 99},
            }
        )
