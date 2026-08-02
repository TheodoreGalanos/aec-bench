# ABOUTME: Tests isolated rollout groups, immutable lineage, recovery, and actor privacy.
# ABOUTME: Proves one verified world snapshot can start repeatable child continuations.

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_control import (
    PumpStationRolloutControl,
    PumpStationRolloutError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_models import (
    PUMP_STATION_ROLLOUT_LINEAGE_VERSION,
    PumpStationRolloutChildRequest,
    PumpStationRolloutGroupRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_bytes,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)


def _start_parent(root: Path) -> PumpStationWorldSession:
    return PumpStationWorldSessionFactory(root, evidence_health=True).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.START,
            session_id="session.parent",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="tenure.parent",
            run_id="run.parent",
            episode_id="episode.parent",
            world_branch_id="branch.parent",
        )
    )


def _group_request(parent: PumpStationWorldSession) -> PumpStationRolloutGroupRequest:
    return PumpStationRolloutGroupRequest(
        request_id="rollout-request-01",
        group_id="rollout-group-01",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="rollout-host",
        parent_snapshot=parent.run.snapshot(),
        origin_verification_id="verified-current-world-state",
        information_boundary_id="pump-station-actor-view.v3",
        event_schedule_id="reference-future-schedule.v1",
        fixed_future_condition_id="reference-future.v1",
        future_condition_seed=7,
        split_group_id="split-group-01",
        children=(
            PumpStationRolloutChildRequest(
                child_id="control",
                run_id="run.child.control",
                world_branch_id="branch.child.control",
                agent_condition_id="agent-condition.control",
                agent_seed=101,
            ),
            PumpStationRolloutChildRequest(
                child_id="candidate",
                run_id="run.child.candidate",
                world_branch_id="branch.child.candidate",
                agent_condition_id="agent-condition.candidate",
                agent_seed=202,
            ),
        ),
    )


def _continue(session: PumpStationWorldSession, request_id: str) -> None:
    session.invoke_actor_action(
        WorldActorActionRequest(
            request_id=request_id,
            action_name="continue_operation",
            binding=session.current_actor_binding,
            arguments={"reason": "Continue this child to its next scheduled event."},
        )
    )


def test_rollout_group_preserves_origin_and_isolates_actor_sessions(tmp_path: Path) -> None:
    parent = _start_parent(tmp_path / "parent")
    parent_snapshot = parent.run.snapshot()
    parent_state = parent.run.state
    control = PumpStationRolloutControl(
        parent_repository_root=tmp_path / "parent",
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
        evidence_health=True,
    )

    lineage = control.create_group(_group_request(parent))

    assert lineage.lineage_version == PUMP_STATION_ROLLOUT_LINEAGE_VERSION
    assert lineage.parent_snapshot == parent_snapshot
    assert lineage.split_group_id == "split-group-01"
    assert len(lineage.children) == 2
    assert parent.run.snapshot() == parent_snapshot
    assert parent.run.state == parent_state
    assert {child.initial_snapshot.state_id for child in lineage.children} == {parent_snapshot.state_id}
    assert {child.event_schedule_id for child in lineage.children} == {"reference-future-schedule.v1"}
    expected_schedule_sha256 = hashlib.sha256(
        pump_station_artifact_bytes(parent_state.scheduled_events, record_profile="v3")
    ).hexdigest()
    assert {child.event_schedule_sha256 for child in lineage.children} == {expected_schedule_sha256}

    child = control.open_actor_session(
        group_id=lineage.group_id,
        child_id="candidate",
        session_id="session.child.candidate",
        agent_tenure_id="tenure.child.candidate",
    )
    public_text = json.dumps(
        json.loads(child.observe_pump_station()),
        sort_keys=True,
    )
    assert "rollout-group-01" not in public_text
    assert "branch.child.control" not in public_text
    assert "split-group-01" not in public_text

    _continue(child, "proposal-child-candidate-01")
    sibling = control.open_actor_session(
        group_id=lineage.group_id,
        child_id="control",
        session_id="session.child.control",
        agent_tenure_id="tenure.child.control",
    )
    assert child.run.snapshot().sequence > lineage.children[1].initial_snapshot.sequence
    assert sibling.run.snapshot() == lineage.children[0].initial_snapshot
    assert parent.run.snapshot() == parent_snapshot
    assert child.verify().valid is True
    assert sibling.verify().valid is True


def test_origin_validation_and_single_child_creation_are_host_operations(
    tmp_path: Path,
) -> None:
    parent = _start_parent(tmp_path / "parent")
    request = _group_request(parent)
    control = PumpStationRolloutControl(
        parent_repository_root=tmp_path / "parent",
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
        evidence_health=True,
    )

    verification = control.validate_origin(request)
    child = control.create_child(request, "control")
    status = control.group_status(request.group_id)

    assert verification.valid is True
    assert child.child_id == "control"
    assert status.state.value == "preparing"
    assert status.created_child_ids == ("control",)
    assert control.create_group(request).children[0] == child


def test_rollout_group_retry_recovers_missing_children_without_duplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _start_parent(tmp_path / "parent")
    request = _group_request(parent)
    first = PumpStationRolloutControl(
        parent_repository_root=tmp_path / "parent",
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
        evidence_health=True,
    )
    original = first._create_child
    calls = 0

    def interrupt_once(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated process interruption")
        return original(*args, **kwargs)

    monkeypatch.setattr(first, "_create_child", interrupt_once)
    with pytest.raises(RuntimeError, match="simulated process interruption"):
        first.create_group(request)

    interrupted = first.group_status(request.group_id)
    assert interrupted.state.value == "preparing"
    assert interrupted.requested_child_ids == ("control", "candidate")
    assert interrupted.created_child_ids == ("control",)

    restarted = PumpStationRolloutControl(
        parent_repository_root=tmp_path / "parent",
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
        evidence_health=True,
    )
    recovered = restarted.create_group(request)
    repeated = restarted.create_group(request)

    assert recovered == repeated
    assert tuple(child.child_id for child in recovered.children) == (
        "control",
        "candidate",
    )
    assert restarted.group_status(request.group_id).state.value == "ready"
    group_root = tmp_path / "rollouts" / "groups" / request.group_id
    assert len(tuple((group_root / "children").iterdir())) == 2

    conflict = replace(request, split_group_id="later-outcome-selected")
    with pytest.raises(PumpStationRolloutError, match="request-id-conflict"):
        restarted.create_group(conflict)

    stale = replace(
        request,
        request_id="rollout-request-stale",
        group_id="rollout-group-stale",
        parent_snapshot=replace(request.parent_snapshot, sequence=999),
    )
    with pytest.raises(PumpStationRolloutError, match="origin-snapshot"):
        restarted.create_group(stale)


def test_rollout_child_native_tool_removes_transport_only_evidence_fields(
    tmp_path: Path,
) -> None:
    parent = _start_parent(tmp_path / "parent")
    control = PumpStationRolloutControl(
        parent_repository_root=tmp_path / "parent",
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
        evidence_health=True,
    )
    control.create_group(_group_request(parent))
    child = control.open_actor_session(
        group_id="rollout-group-01",
        child_id="candidate",
        session_id="session.native-tool",
        agent_tenure_id="tenure.native-tool",
    )

    result = json.loads(
        child.continue_operation(
            "proposal-native-tool-01",
            "Continue through the native agent tool.",
        )
    )

    assert result["status"] == "completed"
    assert child.verify().valid is True
