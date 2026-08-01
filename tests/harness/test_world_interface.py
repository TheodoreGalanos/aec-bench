# ABOUTME: Exercises the shared actor and control seams against the real pump-station world.
# ABOUTME: Proves exact invocation, idempotent retry, negative access, and durable control results.

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorBinding,
    WorldControlRequest,
)
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.world_interface import (
    WorldInterfaceError,
    invoke_world_actor,
    observe_world_actor,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.local_interface import (
    PumpStationLocalInterfaceRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PUMP_STATION_CONTROL_OPERATIONS,
    PumpStationWorldControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSessionFactory,
)


def _session_request(
    *,
    open_mode: WorldSessionOpenMode = WorldSessionOpenMode.START,
) -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=open_mode,
        session_id="session-1",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="tenure-1",
        run_id="run-1",
        episode_id="episode-1",
        world_branch_id="branch-1",
    )


def _action_request(
    binding: WorldActorBinding,
    *,
    request_id: str = "request-1",
    action_name: str = "continue_operation",
    reason: str = "Continue to the next declared event.",
) -> WorldActorActionRequest:
    return WorldActorActionRequest(
        request_id=request_id,
        action_name=action_name,
        binding=binding,
        arguments={"reason": reason},
    )


def test_actor_interface_invokes_one_exact_bound_action_and_retries_without_effect(
    tmp_path: Path,
) -> None:
    session = PumpStationWorldSessionFactory(tmp_path / "world").open(_session_request())
    catalogue = session.actor_capabilities
    observation = observe_world_actor(session)
    request = _action_request(observation.binding)

    first = invoke_world_actor(session, request)
    retried = invoke_world_actor(session, request)

    assert first == retried
    assert first.post_binding.sequence == 1
    assert first.task_receipt["proposal_id"] == request.request_id
    assert session.result.snapshot.sequence == 1
    assert {item.name for item in catalogue.actions}.isdisjoint(PUMP_STATION_CONTROL_OPERATIONS)


def test_actor_interface_fails_closed_for_stale_cross_scope_and_unknown_calls(
    tmp_path: Path,
) -> None:
    session = PumpStationWorldSessionFactory(tmp_path / "world").open(_session_request())
    observation = observe_world_actor(session)
    invoke_world_actor(session, _action_request(observation.binding))

    failures = (
        (
            _action_request(observation.binding, request_id="stale-request"),
            "actor-stale-sequence",
        ),
        (
            _action_request(
                WorldActorBinding(
                    **{
                        **observation.binding.model_dump(),
                        "world_branch_id": "branch-other",
                    }
                ),
                request_id="wrong-branch",
            ),
            "actor-wrong-world",
        ),
        (
            _action_request(
                WorldActorBinding(
                    **{
                        **session.current_actor_binding.model_dump(),
                        "information_set_id": "information-other",
                    }
                ),
                request_id="wrong-information",
            ),
            "actor-wrong-information-set",
        ),
        (
            _action_request(
                WorldActorBinding(
                    **{
                        **session.current_actor_binding.model_dump(),
                        "actor_view_id": "view-stale",
                    }
                ),
                request_id="stale-view",
            ),
            "actor-stale-view",
        ),
        (
            _action_request(
                WorldActorBinding(
                    **{
                        **session.current_actor_binding.model_dump(),
                        "agent_tenure_id": "tenure-other",
                    }
                ),
                request_id="wrong-tenure",
            ),
            "actor-wrong-tenure",
        ),
        (
            _action_request(
                session.current_actor_binding,
                request_id="unknown-action",
                action_name="create_session",
            ),
            "actor-action-unavailable",
        ),
    )
    for request, code in failures:
        with pytest.raises(WorldInterfaceError, match=code):
            invoke_world_actor(session, request)

    with pytest.raises(WorldInterfaceError, match="actor-request-id-conflict"):
        invoke_world_actor(
            session,
            _action_request(
                observation.binding,
                reason="Use different content for the same request identity.",
            ),
        )
    assert session.result.snapshot.sequence == 1


def test_local_actor_interface_cannot_create_a_world_run() -> None:
    with pytest.raises(ValidationError, match="actor local-interface session must resume"):
        PumpStationLocalInterfaceRequest(
            surface="actor",
            operation="observe",
            session_request=_session_request(),
        )


def test_control_interface_is_separate_authorised_and_fail_closed(tmp_path: Path) -> None:
    control = PumpStationWorldControl(
        tmp_path / "world",
        authorised_principal_ids=("host-1",),
    )
    start = _session_request()
    created = control.execute(
        WorldControlRequest(
            request_id="control-create",
            operation="create_session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-1",
            session_request=start,
        )
    )
    repeated = control.execute(
        WorldControlRequest(
            request_id="control-create",
            operation="create_session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-1",
            session_request=start,
        )
    )
    assert created.session_result is not None
    resume_request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id="session-2",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="tenure-2",
        run_id=created.session_result.snapshot.run_id,
        episode_id=created.session_result.snapshot.episode_id,
        world_branch_id=created.session_result.snapshot.world_branch_id,
        start_snapshot=created.session_result.snapshot,
    )
    opened = control.execute(
        WorldControlRequest(
            request_id="control-open",
            operation="open_session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-1",
            session_request=resume_request,
        )
    )
    resumed = control.execute(
        WorldControlRequest(
            request_id="control-resume",
            operation="resume_session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-1",
            session_request=resume_request,
        )
    )
    progress = control.execute(
        WorldControlRequest(
            request_id="control-progress",
            operation="inspect_progress",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-1",
        )
    )
    snapshot = control.execute(
        WorldControlRequest(
            request_id="control-snapshot",
            operation="snapshot",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-1",
        )
    )
    verified = control.execute(
        WorldControlRequest(
            request_id="control-verify",
            operation="verify",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="host-1",
        )
    )

    assert created == repeated
    assert created.receipt.state_changed is True
    assert opened.receipt.state_changed is False
    assert resumed.receipt.state_changed is False
    assert opened.session_result == resumed.session_result
    assert progress.progress is not None
    assert progress.progress.transition_count == 0
    assert snapshot.snapshot == created.session_result.snapshot
    assert verified.verification is not None
    assert verified.verification.valid is True
    assert tuple(item.operation for item in control.capabilities("host-1").operations) == (
        PUMP_STATION_CONTROL_OPERATIONS
    )

    with pytest.raises(WorldInterfaceError, match="control-unauthorised"):
        control.capabilities("actor-1")
    with pytest.raises(WorldInterfaceError, match="control-capability-unavailable"):
        control.execute(
            WorldControlRequest(
                request_id="control-treatment",
                operation="schedule_evidence_treatment",
                task_world_id=PUMP_STATION_TASK_WORLD_ID,
                authority_id="host-1",
            )
        )
