# ABOUTME: Tests strict version and filesystem boundaries around pump rollout control transports.
# ABOUTME: Proves the installed V1 API cannot operate on registered child worlds.

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualRolloutLineage,
    ContinualWorldSnapshotRef,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
    PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
    PumpStationPhysicalTreatmentClass,
    PumpStationPhysicalTreatmentRequest,
    PumpStationTreatmentSeverity,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_control import (
    PumpStationRolloutControl,
    PumpStationRolloutError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_interface import (
    PumpStationRolloutControlRequest,
    execute_pump_station_rollout_request,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_models import (
    PUMP_STATION_TREATMENT_RECEIPT_VERSION,
    PumpStationPhysicalTreatmentScheduleReceipt,
    PumpStationRolloutTreatmentStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_repository import (
    PumpStationRolloutRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunManifestV2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
)


def _created_registered_group(
    tmp_path: Path,
) -> tuple[
    PumpStationRolloutControl,
    Path,
    ContinualRolloutGroupRequest,
    ContinualRolloutLineage,
]:
    parent_root = tmp_path / "parent"
    rollout_root = tmp_path / "rollouts"
    parent = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(parent_root),
        run_id="transport-boundary-parent",
        episode_id="transport-boundary-episode",
        world_branch_id="transport-boundary-parent-branch",
    )
    manifest = parent.manifest
    assert isinstance(manifest, PumpStationWorldRunManifestV2)
    definition = pump_station_continual_world_definition()
    children = tuple(
        ContinualRolloutChildRequest(
            child_id=child_id,
            run_id=f"transport-boundary-{child_id}-run",
            episode_id=f"transport-boundary-{child_id}-episode",
            world_branch_id=f"transport-boundary-{child_id}-branch",
        )
        for child_id in ("control", "candidate")
    )
    parent_snapshot = parent.snapshot()
    request = ContinualRolloutGroupRequest(
        request_id="transport-boundary-group-request",
        group_id="transport-boundary-group",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="rollout-host",
        definition_ref=definition.ref,
        profile_ref=definition.spec.profiles[0],
        parent_snapshot=ContinualWorldSnapshotRef(
            run_id=parent_snapshot.run_id,
            episode_id=parent_snapshot.episode_id,
            world_branch_id=parent_snapshot.world_branch_id,
            sequence=parent_snapshot.sequence,
            state_id=parent_snapshot.state_id,
            commit_id=parent_snapshot.commit_id,
        ),
        parent_manifest_content_sha256=pump_station_artifact_id(
            manifest,
            record_profile="manifest-v2",
        ),
        origin_verification_content_sha256=pump_station_artifact_id(
            parent.verify_v4(),
            record_profile="v4",
        ),
        children=children,
        reason="Test the strict transport boundary around one registered rollout group.",
    )
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("rollout-host",),
    )
    lineage = control.create_group(request)
    assert isinstance(lineage, ContinualRolloutLineage)
    return control, rollout_root, request, lineage


def _legacy_treatment_request(
    lineage: ContinualRolloutLineage,
    *,
    request_id: str,
) -> PumpStationPhysicalTreatmentRequest:
    child = next(item for item in lineage.children if item.child_id == "candidate")
    return PumpStationPhysicalTreatmentRequest(
        request_id=request_id,
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="rollout-host",
        group_id=lineage.group_id,
        child_id=child.child_id,
        child_run_id=child.initial_snapshot.run_id,
        child_episode_id=child.initial_snapshot.episode_id,
        child_world_branch_id=child.initial_snapshot.world_branch_id,
        base_state_id=child.initial_snapshot.state_id,
        base_commit_id=child.initial_snapshot.commit_id,
        based_on_sequence=child.initial_snapshot.sequence,
        parent_state_id=lineage.parent_snapshot.state_id,
        treatment_class=PumpStationPhysicalTreatmentClass.RECURRENT_OBSTRUCTION,
        treatment_version=PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
        affected_pump_ids=("pump-a",),
        activation_calendar_seconds=0,
        severity=PumpStationTreatmentSeverity.MODERATE,
        random_stream_id="transport-boundary-treatment-stream",
        random_seed=37,
        visibility_policy=PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
        decision_right_id=PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    )


@pytest.mark.parametrize("operation", ("inspect_rollout_group", "open_rollout_actor_session"))
def test_installed_v1_transport_rejects_a_registered_group(
    tmp_path: Path,
    operation: str,
) -> None:
    control, _, request, _ = _created_registered_group(tmp_path)
    payload = {
        "request_id": f"v1-{operation}-v2-group",
        "operation": operation,
        "task_world_id": PUMP_STATION_TASK_WORLD_ID,
        "authority_id": "rollout-host",
        "group_id": request.group_id,
    }
    if operation == "open_rollout_actor_session":
        payload.update(
            child_id="candidate",
            session_id="v1-transport-v2-child-session",
            agent_tenure_id="v1-transport-v2-child-tenure",
        )
    installed_request = PumpStationRolloutControlRequest.model_validate(payload)

    with pytest.raises(PumpStationRolloutError) as raised:
        execute_pump_station_rollout_request(control, installed_request)

    assert raised.value.code == "rollout-version"


def test_legacy_treatment_controls_reject_a_registered_group_without_legacy_world(
    tmp_path: Path,
) -> None:
    control, rollout_root, _, lineage = _created_registered_group(tmp_path)
    request = _legacy_treatment_request(
        lineage,
        request_id="legacy-schedule-on-v2-child",
    )
    legacy_world_root = rollout_root / "groups" / lineage.group_id / "children" / request.child_id / "world-run"
    assert not legacy_world_root.exists()

    with pytest.raises(PumpStationRolloutError) as schedule_error:
        control.schedule_treatment(request)

    assert schedule_error.value.code == "rollout-operation"
    assert not legacy_world_root.exists()

    recovery_request = replace(
        request,
        request_id="legacy-recovery-on-v2-child",
    )
    PumpStationRolloutRepository(rollout_root).publish_treatment_schedule(
        PumpStationPhysicalTreatmentScheduleReceipt(
            receipt_version=PUMP_STATION_TREATMENT_RECEIPT_VERSION,
            request=recovery_request,
            request_content_sha256=pump_station_artifact_id(recovery_request),
            status=PumpStationRolloutTreatmentStatus.SCHEDULED,
            affected_pump_ids=recovery_request.affected_pump_ids,
            unaffected_pump_ids=("pump-b",),
        )
    )

    with pytest.raises(PumpStationRolloutError) as recovery_error:
        control.recover_treatment(
            group_id=recovery_request.group_id,
            child_id=recovery_request.child_id,
            treatment_request_id=recovery_request.request_id,
        )

    assert recovery_error.value.code == "rollout-operation"
    assert not legacy_world_root.exists()


def test_registered_child_symlink_blocks_open_but_not_durable_lineage_inspection(
    tmp_path: Path,
) -> None:
    control, rollout_root, request, lineage = _created_registered_group(tmp_path)
    child = next(item for item in lineage.children if item.child_id == "candidate")
    child_root = rollout_root / "groups" / request.group_id / "children" / child.child_id
    world_root = child_root / "world"
    relocated_world_root = child_root / "relocated-world"
    world_root.rename(relocated_world_root)
    world_root.symlink_to(relocated_world_root.name, target_is_directory=True)
    assert world_root.is_symlink()
    assert control.inspect_group(request.group_id) == lineage

    with pytest.raises(PumpStationRolloutError) as raised:
        control.open_actor_session(
            group_id=request.group_id,
            child_id=child.child_id,
            session_id="symlinked-child-session",
            agent_tenure_id="symlinked-child-tenure",
        )

    assert raised.value.code == "artifact-confinement"


def test_registered_actor_open_rejects_a_tampered_task_branch_receipt(
    tmp_path: Path,
) -> None:
    control, rollout_root, request, lineage = _created_registered_group(tmp_path)
    child = next(item for item in lineage.children if item.child_id == "candidate")
    receipt_path = (
        rollout_root
        / "groups"
        / request.group_id
        / "children"
        / child.child_id
        / "world"
        / "rollout-branch-receipt.json"
    )
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["shared_group_request_content_sha256"] == request.content_sha256
    assert payload["shared_child_request_content_sha256"] == child.child_request_content_sha256
    assert "group_request_content_id" not in payload
    assert "child_request_content_id" not in payload
    payload["parent_origin_remaining_schedule_sha256"] = "0" * 64
    receipt_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    with pytest.raises(PumpStationRolloutError) as raised:
        control.open_actor_session(
            group_id=request.group_id,
            child_id=child.child_id,
            session_id="tampered-task-receipt-session",
            agent_tenure_id="tampered-task-receipt-tenure",
        )

    assert raised.value.code == "child-verification"
