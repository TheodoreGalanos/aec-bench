# ABOUTME: Exercises the ASW-8 rollout-control v2 contract through direct, Harbor, and installed routes.
# ABOUTME: Proves child evidence is usable while parent-private retrieval records remain isolated.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    verify_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_rollout import (
    PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION,
    PumpStationCoupledRolloutControl,
    coupled_run_snapshot,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_rollout_interface import (
    PumpStationCoupledRolloutChildRecord,
    PumpStationCoupledRolloutControlRequest,
    PumpStationCoupledRolloutGroupRecord,
    PumpStationCoupledSnapshotRecord,
    execute_coupled_harbor_rollout_request,
    execute_coupled_rollout_request,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_temporal import (
    create_coupled_root_with_temporal_repository,
)


def _installed(arguments: list[str], *, cwd: Path) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    completed = subprocess.run(
        [str(executable), "--json", "task", "pump-station-world", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout)["data"])


def _group(parent_root: Path) -> PumpStationCoupledRolloutGroupRecord:
    parent = PumpStationCoupledRunRepository(parent_root).open()
    snapshot = coupled_run_snapshot(parent)
    children = (
        PumpStationCoupledRolloutChildRecord(
            request_version=PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION,
            child_id="control",
            run_id="interface-child-control",
            world_branch_id="branch-interface-child-control",
            agent_condition_id="condition-control",
            agent_seed=101,
        ),
        PumpStationCoupledRolloutChildRecord(
            request_version=PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION,
            child_id="candidate",
            run_id="interface-child-candidate",
            world_branch_id="branch-interface-child-candidate",
            agent_condition_id="condition-candidate",
            agent_seed=202,
        ),
    )
    return PumpStationCoupledRolloutGroupRecord(
        request_version=PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION,
        request_id="interface-rollout-group-request-001",
        group_id="interface-rollout-group-001",
        task_world_id="wastewater-pump-station-stewardship.v1",
        authority_id="rollout-host",
        parent_snapshot=PumpStationCoupledSnapshotRecord(
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            sequence=snapshot.sequence,
            state_id=snapshot.state_id,
            commit_id=snapshot.commit_id,
        ),
        parent_manifest_content_id=parent.manifest.content_id,
        origin_verification_content_id=verify_coupled_run(parent).content_id,
        reference_system_content_id=parent.manifest.reference_system_content_id,
        event_schedule_sha256=parent.manifest.event_schedule_sha256,
        information_boundary_id="pump-station-actor-view.v4",
        temporal_bundle_content_id=parent.manifest.temporal_bundle_content_id,
        child_request_content_ids=tuple(child.content_id for child in children),
        children=children,
    )


def test_rollout_control_v2_uses_same_direct_harbor_and_installed_contract(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    rollout_root = tmp_path / "rollouts"
    create_coupled_root_with_temporal_repository(
        parent_root,
        run_id="interface-parent",
        world_branch_id="branch-interface-parent",
    )
    control = PumpStationCoupledRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("rollout-host",),
    )
    group = _group(parent_root)
    created = execute_coupled_rollout_request(
        control,
        PumpStationCoupledRolloutControlRequest(
            request_id=group.request_id,
            operation="create_rollout_group",
            task_world_id=group.task_world_id,
            authority_id=group.authority_id,
            group_request=group,
        ),
    )
    assert created.payload["lineage_version"] == "pump-station.rollout-lineage.v2"

    searched = execute_coupled_rollout_request(
        control,
        PumpStationCoupledRolloutControlRequest(
            request_id="candidate-search-001",
            operation="apply_child_actor",
            task_world_id=group.task_world_id,
            authority_id=group.authority_id,
            group_id=group.group_id,
            child_id="candidate",
            action_name="search_evidence",
            arguments={
                "query": "controlled test permit",
                "scope": "operations",
                "limit": 1,
            },
            agent_tenure_id="candidate-tenure-001",
            session_id="candidate-session-001",
        ),
    )
    assert searched.payload["public_status"] == "OK"
    assert not (parent_root / "temporal-evidence" / "private").exists()
    assert (
        rollout_root
        / "groups"
        / group.group_id
        / "children"
        / "candidate"
        / "world-run"
        / "temporal-evidence"
        / "private"
    ).is_dir()

    inspect = PumpStationCoupledRolloutControlRequest(
        request_id="inspect-interface-rollout-001",
        operation="inspect_rollout_group",
        task_world_id=group.task_world_id,
        authority_id=group.authority_id,
        group_id=group.group_id,
    )
    direct = execute_coupled_rollout_request(control, inspect)
    harbor = execute_coupled_harbor_rollout_request(
        parent_repository_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_id="rollout-host",
        request=inspect,
    )
    assert direct == harbor

    request_path = tmp_path / "inspect-rollout.json"
    request_path.write_text(inspect.model_dump_json(), encoding="utf-8")
    installed = _installed(
        [
            "asw-8-rollout-interface",
            "--parent-run-dir",
            str(parent_root),
            "--rollout-dir",
            str(rollout_root),
            "--request-path",
            str(request_path),
            "--host-authority-id",
            "rollout-host",
        ],
        cwd=tmp_path,
    )
    assert installed == direct.model_dump(mode="json")


def test_rollout_control_v2_rejects_v1_nested_records(tmp_path: Path) -> None:
    parent_root = tmp_path / "parent"
    create_coupled_root_with_temporal_repository(
        parent_root,
        run_id="interface-parent",
        world_branch_id="branch-interface-parent",
    )
    value = _group(parent_root).model_dump(mode="json")
    value["children"][0]["request_version"] = "pump-station.rollout-request.v1"

    with pytest.raises(ValidationError, match="rollout child version"):
        PumpStationCoupledRolloutGroupRecord.model_validate(value)


def test_child_created_at_peak_end_gets_parent_corpus_but_fresh_access_state(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    rollout_root = tmp_path / "rollouts"
    create_coupled_root_with_temporal_repository(
        parent_root,
        run_id="interface-parent",
        world_branch_id="branch-interface-parent",
    )
    repository = PumpStationCoupledRunRepository(parent_root)
    parent = repository.open()
    while parent.state.calendar_seconds < 93_600:
        parent = parent.apply_actor(
            request_id=f"parent-continue-{parent.state.sequence + 1}",
            action_name="continue_operation",
            arguments={"reason": "Continue the parent to the declared peak-end snapshot."},
        )
    repository.append(parent)
    control = PumpStationCoupledRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("rollout-host",),
    )
    group = _group(parent_root)
    control.create_group(group.to_runtime())
    before = execute_coupled_rollout_request(
        control,
        PumpStationCoupledRolloutControlRequest(
            request_id="child-ccr28h-before",
            operation="apply_child_actor",
            task_world_id=group.task_world_id,
            authority_id=group.authority_id,
            group_id=group.group_id,
            child_id="candidate",
            action_name="search_evidence",
            arguments={"query": "CCR28H", "scope": "operations", "limit": 1},
            agent_tenure_id="child-tenure-001",
            session_id="child-session-001",
        ),
    )
    assert before.payload["references"] == []

    child = control.open_child(group.group_id, "candidate")
    while child.state.calendar_seconds < 100_800:
        child = control.apply_child_actor(
            group.group_id,
            "candidate",
            request_id=f"child-continue-{child.state.sequence + 1}",
            action_name="continue_operation",
            arguments={"reason": "Continue the child to its documentary review point."},
        )
    after = execute_coupled_rollout_request(
        control,
        PumpStationCoupledRolloutControlRequest(
            request_id="child-ccr28h-after",
            operation="apply_child_actor",
            task_world_id=group.task_world_id,
            authority_id=group.authority_id,
            group_id=group.group_id,
            child_id="candidate",
            action_name="search_evidence",
            arguments={"query": "CCR28H", "scope": "operations", "limit": 1},
            agent_tenure_id="child-tenure-001",
            session_id="child-session-001",
        ),
    )
    assert tuple(item["version_id"] for item in after.payload["references"]) == (
        "pump-c-collateral-inspection-note.v1",
    )
    assert not (parent_root / "temporal-evidence" / "private").exists()
