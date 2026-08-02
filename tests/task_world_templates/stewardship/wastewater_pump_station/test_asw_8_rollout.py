# ABOUTME: Tests ASW-8 rollout v2 lineage, temporal inheritance, isolation, and replay.
# ABOUTME: Proves one child can receive a three-pump treatment without leaking or moving peers.

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    verify_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_rollout import (
    PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION,
    PumpStationCoupledRolloutChildRequest,
    PumpStationCoupledRolloutControl,
    PumpStationCoupledRolloutError,
    PumpStationCoupledRolloutGroupRequest,
    coupled_run_snapshot,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRun,
    PumpStationCoupledRunError,
    PumpStationCoupledRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PUMP_STATION_COUPLED_TREATMENT_VERSION,
    PumpStationCoupledTreatmentRequest,
    project_coupled_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_temporal import (
    copy_coupled_child_temporal_repository,
    create_coupled_root_with_temporal_repository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
)


def _request(parent_root: Path) -> PumpStationCoupledRolloutGroupRequest:
    parent = PumpStationCoupledRunRepository(parent_root).open()
    children = (
        PumpStationCoupledRolloutChildRequest(
            request_version=PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION,
            child_id="control",
            run_id="asw-8-child-control",
            world_branch_id="branch-asw-8-child-control",
            agent_condition_id="condition-control",
            agent_seed=101,
        ),
        PumpStationCoupledRolloutChildRequest(
            request_version=PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION,
            child_id="candidate",
            run_id="asw-8-child-candidate",
            world_branch_id="branch-asw-8-child-candidate",
            agent_condition_id="condition-candidate",
            agent_seed=202,
        ),
    )
    return PumpStationCoupledRolloutGroupRequest(
        request_version=PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION,
        request_id="asw-8-rollout-group-request-001",
        group_id="asw-8-rollout-group-001",
        task_world_id="wastewater-pump-station-stewardship.v1",
        authority_id="rollout-host",
        parent_snapshot=coupled_run_snapshot(parent),
        parent_manifest_content_id=parent.manifest.content_id,
        origin_verification_content_id=verify_coupled_run(parent).content_id,
        reference_system_content_id=parent.manifest.reference_system_content_id,
        event_schedule_sha256=parent.manifest.event_schedule_sha256,
        information_boundary_id="pump-station-actor-view.v4",
        temporal_bundle_content_id=parent.manifest.temporal_bundle_content_id,
        child_request_content_ids=tuple(child.content_id for child in children),
        children=children,
    )


def test_rollout_v2_inherits_public_evidence_and_isolates_children(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    parent = create_coupled_root_with_temporal_repository(
        parent_root,
        run_id="asw-8-parent",
        world_branch_id="branch-asw-8-parent",
    )
    control = PumpStationCoupledRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    request = _request(parent_root)

    lineage = control.create_group(request)

    assert lineage.group_request_content_id == request.content_id
    assert lineage.parent_snapshot == coupled_run_snapshot(parent)
    assert len(lineage.children) == 2
    for receipt in lineage.children:
        child = control.open_child(request.group_id, receipt.child_id)
        temporal = control.load_child_temporal_state(request.group_id, receipt.child_id)
        assert child.manifest.initial_state_source.kind == "rollout_parent_snapshot"
        assert child.manifest.initial_state_source.parent_state_id == parent.state.state_id
        assert child.manifest.temporal_bundle_content_id == parent.manifest.temporal_bundle_content_id
        assert temporal.public_bundle_content_id == parent.manifest.temporal_bundle_content_id
        assert temporal.ancestor_branch_ids == (parent.manifest.world_branch_id,)
        assert temporal.private_access_result_ids == ()
        assert receipt.child_manifest_content_id == child.manifest.content_id
        assert receipt.initial_state_id == parent.state.state_id

    parent_before = coupled_run_snapshot(control.open_parent())
    sibling_before = coupled_run_snapshot(control.open_child(request.group_id, "control"))
    candidate = control.apply_child_actor(
        request.group_id,
        "candidate",
        request_id="candidate-continue-001",
        action_name="continue_operation",
        arguments={"reason": "Continue only the candidate child to its next event."},
    )

    assert candidate.state.sequence > parent.state.sequence
    assert coupled_run_snapshot(control.open_parent()) == parent_before
    assert coupled_run_snapshot(control.open_child(request.group_id, "control")) == sibling_before
    assert verify_coupled_run(candidate).valid is True

    treatment = PumpStationCoupledTreatmentRequest(
        version=PUMP_STATION_COUPLED_TREATMENT_VERSION,
        request_id="candidate-common-treatment-001",
        authority_id="rollout-host",
        treatment_label="private-three-pump-common-condition",
        affected_pump_ids=("pump-a", "pump-b", "pump-c"),
        obstruction_delta=Decimal("0.01"),
        clearance_loss_delta=Decimal("0.005"),
        base_state_id=candidate.state.state_id,
    )
    treated = control.apply_child_treatment(
        request.group_id,
        "candidate",
        treatment,
    )

    for before, after in zip(candidate.state.physical.pumps, treated.state.physical.pumps, strict=True):
        assert after.condition.obstruction == before.condition.obstruction + Decimal("0.01")
        assert after.condition.clearance_loss == before.condition.clearance_loss + Decimal("0.005")
    assert verify_coupled_run(treated).valid is True
    assert coupled_run_snapshot(control.open_parent()) == parent_before
    assert coupled_run_snapshot(control.open_child(request.group_id, "control")) == sibling_before
    public_view = json.dumps(
        canonical_stewardship_value(
            project_coupled_actor_view(treated.state),
            record_profile="v4",
        ),
        sort_keys=True,
    )
    assert treatment.request_id not in public_view
    assert treatment.treatment_label not in public_view


def test_rollout_v2_rejects_cross_version_requests(tmp_path: Path) -> None:
    parent_root = tmp_path / "parent"
    create_coupled_root_with_temporal_repository(
        parent_root,
        run_id="asw-8-parent",
        world_branch_id="branch-asw-8-parent",
    )
    control = PumpStationCoupledRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )

    with pytest.raises(PumpStationCoupledRolloutError, match="rollout-request-version"):
        control.create_group(
            replace(
                _request(parent_root),
                request_version="pump-station.rollout-request.v1",
            )
        )


def test_rollout_child_rejects_changed_inherited_event_schedule(tmp_path: Path) -> None:
    parent_root = tmp_path / "parent"
    create_coupled_root_with_temporal_repository(
        parent_root,
        run_id="asw-8-parent",
        world_branch_id="branch-asw-8-parent",
    )
    control = PumpStationCoupledRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    request = _request(parent_root)
    control.create_group(request)
    manifest_path = (
        tmp_path / "rollouts" / "groups" / request.group_id / "children" / "candidate" / "world-run" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_bytes())
    manifest["event_schedule_sha256"] = "changed-event-schedule"
    manifest_path.write_text(
        json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(PumpStationCoupledRunError, match="rollout-origin-binding"):
        control.open_child(request.group_id, "candidate")


def test_rollout_v2_recovers_child_created_before_temporal_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent_root = tmp_path / "parent"
    rollout_root = tmp_path / "rollouts"
    create_coupled_root_with_temporal_repository(
        parent_root,
        run_id="asw-8-parent",
        world_branch_id="branch-asw-8-parent",
    )
    request = _request(parent_root)
    original_copy = copy_coupled_child_temporal_repository
    interrupted = False

    def interrupt_first_temporal_copy(
        *,
        parent_run_root: Path,
        child_run_root: Path,
        parent: PumpStationCoupledRun,
        child: PumpStationCoupledRun,
    ) -> object:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise OSError("simulated interruption before child temporal publication")
        return original_copy(
            parent_run_root=parent_run_root,
            child_run_root=child_run_root,
            parent=parent,
            child=child,
        )

    monkeypatch.setattr(
        "aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_rollout."
        "copy_coupled_child_temporal_repository",
        interrupt_first_temporal_copy,
    )
    control = PumpStationCoupledRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("rollout-host",),
    )
    with pytest.raises(OSError, match="simulated interruption"):
        control.create_group(request)

    restarted = PumpStationCoupledRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("rollout-host",),
    )
    recovered = restarted.create_group(request)
    repeated = restarted.create_group(request)

    assert recovered == repeated
    assert tuple(receipt.child_id for receipt in recovered.children) == (
        "control",
        "candidate",
    )
    for receipt in recovered.children:
        child = restarted.open_child(request.group_id, receipt.child_id)
        assert verify_coupled_run(child).valid is True
        assert (
            rollout_root
            / "groups"
            / request.group_id
            / "children"
            / receipt.child_id
            / "world-run"
            / "temporal-evidence"
            / "corpus"
        ).is_dir()
