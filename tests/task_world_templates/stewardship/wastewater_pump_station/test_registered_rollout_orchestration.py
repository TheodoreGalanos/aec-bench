# ABOUTME: Tests registered V4 rollout branches through the existing pump rollout control.
# ABOUTME: Proves one selected snapshot creates isolated children with complete ancestry.

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualWorldSnapshotRef,
)
from aec_bench.contracts.world_interface import WorldActorActionRequest, WorldInterfaceError
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.world_interface import invoke_world_actor, observe_world_actor
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    project_coupled_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_control import (
    PumpStationRolloutControl,
    PumpStationRolloutError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_BOUND_CONTROL_VERSION,
    PUMP_STATION_COUPLED_TREATMENT_VERSION,
    PumpStationBoundControlRequest,
    PumpStationCoupledStewardshipState,
    PumpStationCoupledTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    TemporalEvidenceRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PumpStationRootControlResult,
    PumpStationWorldControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationStateSnapshotRef,
    PumpStationWorldRunError,
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
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)

type RegisteredRun = PumpStationWorldRun[
    PumpStationCoupledModel,
    PumpStationCoupledStewardshipState,
]


def _shared_snapshot(snapshot: PumpStationStateSnapshotRef) -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _continual_snapshot(snapshot: PumpStationStateSnapshotRef) -> ContinualWorldSnapshotRef:
    return ContinualWorldSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _start_registered_parent(root: Path) -> RegisteredRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="registered-rollout-parent",
        episode_id="registered-rollout-episode",
        world_branch_id="registered-rollout-parent-branch",
    )


def _open_registered_session(
    root: Path,
    run: RegisteredRun,
    *,
    session_id: str,
    agent_tenure_id: str,
) -> PumpStationWorldSession:
    manifest = run.manifest
    assert isinstance(manifest, PumpStationWorldRunManifestV2)
    return PumpStationWorldSessionFactory(root).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=session_id,
            task_world_id=manifest.task_world_id,
            agent_tenure_id=agent_tenure_id,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            start_snapshot=_shared_snapshot(run.snapshot()),
        )
    )


def _group_request(
    parent: RegisteredRun,
    *,
    group_id: str,
    child_prefix: str,
) -> ContinualRolloutGroupRequest:
    manifest = parent.manifest
    assert isinstance(manifest, PumpStationWorldRunManifestV2)
    origin = parent.snapshot()
    definition = pump_station_continual_world_definition()
    children = tuple(
        ContinualRolloutChildRequest(
            child_id=child_id,
            run_id=f"{child_prefix}-{child_id}-run",
            episode_id=f"{child_prefix}-{child_id}-episode",
            world_branch_id=f"{child_prefix}-{child_id}-branch",
        )
        for child_id in ("control", "candidate")
    )
    return ContinualRolloutGroupRequest(
        request_id=f"{group_id}-request",
        group_id=group_id,
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="rollout-host",
        definition_ref=definition.ref,
        profile_ref=definition.spec.profiles[0],
        reason="Create isolated registered branches from this verified world position.",
        parent_snapshot=_continual_snapshot(origin),
        parent_manifest_content_sha256=pump_station_artifact_id(
            manifest,
            record_profile="manifest-v2",
        ),
        origin_verification_content_sha256=pump_station_artifact_id(
            parent.verify_v4(),
            record_profile="v4",
        ),
        children=children,
    )


def _child_session(
    control: PumpStationRolloutControl,
    *,
    group_id: str,
    child_id: str,
) -> PumpStationWorldSession:
    return control.open_actor_session(
        group_id=group_id,
        child_id=child_id,
        session_id=f"{group_id}-{child_id}-session",
        agent_tenure_id=f"{group_id}-{child_id}-tenure",
    )


def _advance_session(
    session: PumpStationWorldSession,
    *,
    request_id: str,
    pump_id: str = "pump-a",
) -> None:
    invoke_world_actor(
        session,
        WorldActorActionRequest(
            request_id=request_id,
            action_name="request_condition_check",
            binding=observe_world_actor(session).binding,
            arguments={
                "pump_id": pump_id,
                "reason": f"Record the visible condition of {pump_id} in this selected branch.",
            },
        ),
    )


def _bound_treatment(
    run: RegisteredRun,
    *,
    request_id: str,
    treatment_label: str,
) -> PumpStationBoundControlRequest:
    snapshot = run.snapshot()
    return PumpStationBoundControlRequest(
        control_envelope_version=PUMP_STATION_BOUND_CONTROL_VERSION,
        request_id=request_id,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        control=PumpStationCoupledTreatmentRequest(
            version=PUMP_STATION_COUPLED_TREATMENT_VERSION,
            request_id=request_id,
            authority_id="rollout-host",
            treatment_label=treatment_label,
            affected_pump_ids=("pump-a", "pump-c"),
            obstruction_delta=Decimal("0.01"),
            clearance_loss_delta=Decimal("0.005"),
            base_state_id=snapshot.state_id,
        ),
    )


def test_registered_rollout_child_treatment_uses_v4_control_and_replays_without_leaking(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    rollout_control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    request = _group_request(
        parent,
        group_id="registered-treatment-group",
        child_prefix="registered-treatment",
    )
    rollout_control.create_group(request)
    candidate = _child_session(
        rollout_control,
        group_id=request.group_id,
        child_id="candidate",
    ).run
    sibling = _child_session(
        rollout_control,
        group_id=request.group_id,
        child_id="control",
    ).run
    candidate_before = candidate.state
    candidate_snapshot_before = candidate.snapshot()
    parent_before = parent.snapshot()
    sibling_before = sibling.snapshot()
    treatment = _bound_treatment(
        candidate,
        request_id="registered-child-treatment-001",
        treatment_label="private-selected-pump-condition",
    )
    assert isinstance(treatment.control, PumpStationCoupledTreatmentRequest)
    control = PumpStationWorldControl(
        candidate.repository.root,
        authorised_principal_ids=("rollout-host",),
    )

    wrong_authority_treatment = replace(
        treatment,
        request_id="registered-child-treatment-wrong-authority",
        control=replace(
            treatment.control,
            request_id="registered-child-treatment-wrong-authority",
            authority_id="operations-controller",
        ),
    )
    wrong_authority_control = PumpStationWorldControl(
        candidate.repository.root,
        authorised_principal_ids=("operations-controller",),
    )
    with pytest.raises(WorldInterfaceError, match="control-capability-unavailable"):
        wrong_authority_control.execute(wrong_authority_treatment)
    assert candidate.snapshot() == candidate_snapshot_before

    assert "coupled_treatment" in {item.operation for item in control.capabilities("rollout-host").operations}
    result = control.execute(treatment)

    assert isinstance(result, PumpStationRootControlResult)
    assert result.receipt.operation == "coupled_treatment"
    treated = candidate.state
    before_by_id = {pump.pump_id: pump for pump in candidate_before.physical.pumps}
    after_by_id = {pump.pump_id: pump for pump in treated.physical.pumps}
    for pump_id in ("pump-a", "pump-c"):
        assert after_by_id[pump_id].condition.obstruction == (
            before_by_id[pump_id].condition.obstruction + Decimal("0.01")
        )
        assert after_by_id[pump_id].condition.clearance_loss == (
            before_by_id[pump_id].condition.clearance_loss + Decimal("0.005")
        )
    assert after_by_id["pump-b"] == before_by_id["pump-b"]
    assert parent.snapshot() == parent_before
    assert sibling.snapshot() == sibling_before
    public_view = json.dumps(
        canonical_stewardship_value(
            project_coupled_actor_view(treated),
            record_profile="v4",
        ),
        sort_keys=True,
    )
    assert treatment.request_id not in public_view
    assert treatment.control.treatment_label not in public_view
    verification = candidate.verify_v4()
    assert verification.valid is True
    assert verification.replayed_transition_ids[-1] == result.transition_receipt["transition_id"]
    selected_after = candidate.snapshot()

    assert control.execute(treatment) == result
    assert candidate.snapshot() == selected_after

    parent_control = PumpStationWorldControl(
        parent_root,
        authorised_principal_ids=("rollout-host",),
    )
    assert "coupled_treatment" not in {
        item.operation for item in parent_control.capabilities("rollout-host").operations
    }
    with pytest.raises(WorldInterfaceError, match="control-capability-unavailable"):
        parent_control.execute(
            _bound_treatment(
                parent,
                request_id="root-treatment-must-fail",
                treatment_label="private-root-condition",
            )
        )


def test_registered_rollout_group_creates_two_isolated_children_from_one_selected_snapshot(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    origin = parent.snapshot()
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    request = _group_request(
        parent,
        group_id="registered-rollout-group",
        child_prefix="registered-rollout",
    )

    lineage = control.create_group(request)

    assert lineage.request_content_sha256 == request.content_sha256
    assert lineage.parent_snapshot == _continual_snapshot(origin)
    assert tuple(child.child_id for child in lineage.children) == (
        "control",
        "candidate",
    )
    assert parent.snapshot() == origin
    for receipt, child_request in zip(lineage.children, request.children, strict=True):
        assert receipt.child_request_content_sha256 == child_request.content_sha256
        assert receipt.parent_snapshot == _continual_snapshot(origin)
        assert receipt.initial_snapshot.sequence == origin.sequence
        assert receipt.initial_snapshot.state_id == origin.state_id
        assert receipt.ancestor_world_branch_ids == (origin.world_branch_id,)

    control_child = _child_session(
        control,
        group_id=request.group_id,
        child_id="control",
    )
    candidate_child = _child_session(
        control,
        group_id=request.group_id,
        child_id="candidate",
    )
    control_initial = control_child.run.snapshot()
    candidate_manifest = candidate_child.run.manifest
    assert isinstance(candidate_manifest, PumpStationWorldRunManifestV2)
    assert candidate_manifest.initial_sequence == origin.sequence
    assert candidate_manifest.initial_state_id == origin.state_id
    assert candidate_manifest.initial_state_source.parent_run_id == origin.run_id
    assert candidate_manifest.initial_state_source.parent_branch_id == origin.world_branch_id
    assert candidate_manifest.initial_state_source.parent_state_id == origin.state_id
    assert candidate_manifest.initial_state_source.parent_commit_id == origin.commit_id
    assert candidate_manifest.initial_state_source.ancestor_branch_ids == (origin.world_branch_id,)

    _advance_session(
        candidate_child,
        request_id="registered-rollout-candidate-condition-check",
    )

    assert candidate_child.run.snapshot().sequence == origin.sequence + 1
    assert control_child.run.snapshot() == control_initial
    assert parent.snapshot() == origin
    assert candidate_child.verify().valid is True
    assert control_child.verify().valid is True


def test_two_registered_rollout_groups_start_independently_from_the_same_selected_snapshot(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    origin = parent.snapshot()
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    first_request = _group_request(
        parent,
        group_id="first-registered-rollout-group",
        child_prefix="first-registered-rollout",
    )
    second_request = _group_request(
        parent,
        group_id="second-registered-rollout-group",
        child_prefix="second-registered-rollout",
    )

    first = control.create_group(first_request)
    second = control.create_group(second_request)

    assert first.group_id != second.group_id
    assert first.parent_snapshot == second.parent_snapshot == _continual_snapshot(origin)
    assert {child.initial_snapshot.state_id for lineage in (first, second) for child in lineage.children} == {
        origin.state_id
    }
    first_candidate = _child_session(
        control,
        group_id=first.group_id,
        child_id="candidate",
    )
    second_candidate = _child_session(
        control,
        group_id=second.group_id,
        child_id="candidate",
    )
    second_initial = second_candidate.run.snapshot()

    _advance_session(
        first_candidate,
        request_id="first-group-candidate-condition-check",
    )

    assert first_candidate.run.snapshot().sequence == origin.sequence + 1
    assert second_candidate.run.snapshot() == second_initial
    assert parent.snapshot() == origin
    assert first_candidate.verify().valid is True
    assert second_candidate.verify().valid is True


def test_registered_rollout_uses_an_older_selected_commit_after_the_parent_advances(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    origin = parent.snapshot()
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    request = _group_request(
        parent,
        group_id="historical-origin-rollout-group",
        child_prefix="historical-origin-rollout",
    )
    parent_session = _open_registered_session(
        parent_root,
        parent,
        session_id="historical-origin-parent-session",
        agent_tenure_id="historical-origin-parent-tenure",
    )
    _advance_session(
        parent_session,
        request_id="parent-condition-check-after-origin",
    )
    selected_after_first_action = parent.snapshot()
    assert selected_after_first_action.sequence == origin.sequence + 1

    lineage = control.create_group(request)

    assert lineage.parent_snapshot == _continual_snapshot(origin)
    assert all(
        (
            child.initial_snapshot.sequence,
            child.initial_snapshot.state_id,
        )
        == (origin.sequence, origin.state_id)
        for child in lineage.children
    )
    child_snapshots = {
        child.child_id: _child_session(
            control,
            group_id=lineage.group_id,
            child_id=child.child_id,
        ).run.snapshot()
        for child in lineage.children
    }

    _advance_session(
        parent_session,
        request_id="parent-second-condition-check-after-origin",
        pump_id="pump-b",
    )
    selected_after_second_action = parent.snapshot()
    repeated = control.create_group(request)

    assert repeated == lineage
    assert selected_after_second_action.sequence == origin.sequence + 2
    assert parent.snapshot() == selected_after_second_action
    assert {
        child_id: _child_session(
            control,
            group_id=lineage.group_id,
            child_id=child_id,
        ).run.snapshot()
        for child_id in child_snapshots
    } == child_snapshots
    assert parent.verify_v4().valid is True


def test_registered_rollout_prefix_ignores_later_private_session_corruption(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    source = _open_registered_session(
        parent_root,
        parent,
        session_id="historical-private-source-session",
        agent_tenure_id="historical-private-source-tenure",
    )
    invoke_world_actor(
        source,
        WorldActorActionRequest(
            request_id="historical-private-search",
            action_name="search_evidence",
            binding=observe_world_actor(source).binding,
            arguments={
                "query": "controlled test permit",
                "scope": "operations",
                "limit": 1,
            },
        ),
    )
    _advance_session(
        source,
        request_id="historical-private-source-condition-check",
    )
    origin = parent.snapshot()
    origin_report = parent.verify_v4(origin)
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    request = _group_request(
        parent,
        group_id="historical-private-corruption-group",
        child_prefix="historical-private-corruption",
    )
    carrier = source.create_retrieval_handover(
        to_tenure_id="historical-private-recipient-tenure",
        to_session_id="historical-private-recipient-session",
        include_fetched_content=True,
    )
    recipient = _open_registered_session(
        parent_root,
        parent,
        session_id="historical-private-recipient-session",
        agent_tenure_id="historical-private-recipient-tenure",
    )
    handover = recipient.create_structured_handover(
        maximum_history_entries=8,
    )
    recipient.install_structured_handover(handover)
    recipient.install_retrieval_handover(carrier)
    _advance_session(
        recipient,
        request_id="historical-private-recipient-condition-check",
    )
    receipt_paths = tuple((parent_root / "temporal-evidence" / "private" / "handover-install-receipts").glob("*.json"))
    assert len(receipt_paths) == 1
    receipt_content = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    receipt_content["next_state_id"] = "corrupted-later-private-state"
    receipt_paths[0].write_text(
        json.dumps(receipt_content),
        encoding="utf-8",
    )

    with pytest.raises(PumpStationWorldRunError, match="temporal-evidence"):
        PumpStationWorldRun.resume_reference_system(
            repository=PumpStationWorldRunRepository(parent_root),
            snapshot=parent.snapshot(),
        )
    current_report = parent.verify_v4()

    assert current_report.valid is False
    assert any(issue.startswith("temporal-evidence-invalid:") for issue in current_report.issues)
    assert parent.verify_v4(origin) == origin_report
    lineage = control.create_group(request)
    assert lineage.parent_snapshot == _continual_snapshot(origin)
    selected_receipts = tuple((parent_root / "temporal-evidence" / "private" / "receipts").glob("*.json"))
    assert len(selected_receipts) == 1
    selected_receipts[0].unlink()
    assert parent.verify_v4(origin).valid is False


@pytest.mark.parametrize(
    ("receipt_directory", "corrupted_field"),
    (
        ("handover-receipts", "source_state_id"),
        ("handover-install-receipts", "next_state_id"),
    ),
)
def test_registered_rollout_prefix_verifies_its_selected_retrieval_handover_receipts(
    tmp_path: Path,
    receipt_directory: str,
    corrupted_field: str,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    source = _open_registered_session(
        parent_root,
        parent,
        session_id="selected-handover-source-session",
        agent_tenure_id="selected-handover-source-tenure",
    )
    invoke_world_actor(
        source,
        WorldActorActionRequest(
            request_id="selected-handover-search",
            action_name="search_evidence",
            binding=observe_world_actor(source).binding,
            arguments={
                "query": "controlled test permit",
                "scope": "operations",
                "limit": 1,
            },
        ),
    )
    _advance_session(
        source,
        request_id="selected-handover-source-condition-check",
    )
    carrier = source.create_retrieval_handover(
        to_tenure_id="selected-handover-recipient-tenure",
        to_session_id="selected-handover-recipient-session",
        include_fetched_content=True,
    )
    recipient = _open_registered_session(
        parent_root,
        parent,
        session_id="selected-handover-recipient-session",
        agent_tenure_id="selected-handover-recipient-tenure",
    )
    handover = recipient.create_structured_handover(maximum_history_entries=8)
    recipient.install_structured_handover(handover)
    recipient.install_retrieval_handover(carrier)
    _advance_session(
        recipient,
        request_id="selected-handover-recipient-condition-check",
    )
    origin = parent.snapshot()
    request = _group_request(
        parent,
        group_id=f"selected-{receipt_directory}-group",
        child_prefix=f"selected-{receipt_directory}",
    )
    receipt_paths = tuple((parent_root / "temporal-evidence" / "private" / receipt_directory).glob("*.json"))
    assert len(receipt_paths) == 1
    receipt_content = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    receipt_content[corrupted_field] = "corrupted-selected-handover-value"
    receipt_paths[0].write_text(json.dumps(receipt_content), encoding="utf-8")

    report = parent.verify_v4(origin)

    assert report.valid is False
    assert any(issue.startswith("temporal-evidence-invalid:") for issue in report.issues)
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    with pytest.raises((PumpStationRolloutError, PumpStationWorldRunError, ValueError)):
        control.create_group(request)


def test_nested_registered_rollout_records_the_complete_ordered_branch_ancestry(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    parent_control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "parent-rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    parent_request = _group_request(
        parent,
        group_id="parent-rollout-group",
        child_prefix="parent-rollout",
    )
    parent_lineage = parent_control.create_group(parent_request)
    candidate = _child_session(
        parent_control,
        group_id=parent_lineage.group_id,
        child_id="candidate",
    )
    sibling = _child_session(
        parent_control,
        group_id=parent_lineage.group_id,
        child_id="control",
    )
    _advance_session(
        candidate,
        request_id="candidate-condition-check-before-nested-rollout",
    )
    candidate_origin = candidate.run.snapshot()
    sibling_before = sibling.run.snapshot()
    parent_before = parent.snapshot()
    candidate_root = candidate.run.repository.root
    nested_control = PumpStationRolloutControl(
        parent_repository_root=candidate_root,
        rollout_repository_root=tmp_path / "nested-rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    nested_request = _group_request(
        candidate.run,
        group_id="nested-rollout-group",
        child_prefix="nested-rollout",
    )

    nested_lineage = nested_control.create_group(nested_request)
    nested_child = _child_session(
        nested_control,
        group_id=nested_lineage.group_id,
        child_id="candidate",
    )
    nested_manifest = nested_child.run.manifest
    assert isinstance(nested_manifest, PumpStationWorldRunManifestV2)
    expected_ancestors = (
        parent_before.world_branch_id,
        candidate_origin.world_branch_id,
    )

    assert nested_lineage.parent_snapshot == _continual_snapshot(candidate_origin)
    assert all(receipt.ancestor_world_branch_ids == expected_ancestors for receipt in nested_lineage.children)
    assert nested_manifest.initial_state_source.ancestor_branch_ids == expected_ancestors
    assert nested_manifest.initial_state_source.parent_commit_id == candidate_origin.commit_id
    assert nested_child.run.snapshot().state_id == candidate_origin.state_id
    assert candidate.run.snapshot() == candidate_origin
    assert sibling.run.snapshot() == sibling_before
    assert parent.snapshot() == parent_before
    assert nested_child.verify().valid is True


@pytest.mark.parametrize("origin_kind", ("foreign", "tampered"))
def test_registered_rollout_rejects_foreign_or_tampered_origin_before_group_publication(
    tmp_path: Path,
    origin_kind: str,
) -> None:
    parent_root = tmp_path / "parent"
    rollout_root = tmp_path / "rollouts"
    parent = _start_registered_parent(parent_root)
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("rollout-host",),
    )
    request = _group_request(
        parent,
        group_id=f"{origin_kind}-origin-rollout-group",
        child_prefix=f"{origin_kind}-origin-rollout",
    )
    if origin_kind == "foreign":
        foreign = PumpStationWorldRun.create_reference_system(
            repository=PumpStationWorldRunRepository(tmp_path / "foreign-parent"),
            run_id="foreign-registered-rollout-parent",
            episode_id="foreign-registered-rollout-episode",
            world_branch_id="foreign-registered-rollout-branch",
        )
        parent_payload = request.parent_snapshot.model_dump(
            mode="python",
            exclude={"content_sha256"},
        )
        parent_payload["commit_id"] = foreign.snapshot().commit_id
        request_payload = request.model_dump(
            mode="python",
            exclude={"content_sha256"},
        )
        request_payload["parent_snapshot"] = ContinualWorldSnapshotRef.model_validate(
            parent_payload,
        )
        request = ContinualRolloutGroupRequest.model_validate(
            request_payload,
        )
    else:
        commit_path = parent_root / "commits" / f"{request.parent_snapshot.commit_id}.json"
        commit_path.write_bytes(commit_path.read_bytes() + b" ")

    with pytest.raises((PumpStationRolloutError, PumpStationWorldRunError)):
        control.create_group(request)

    assert not (rollout_root / "groups" / request.group_id).exists()


def test_registered_rollout_inherits_public_temporal_corpus_without_parent_private_authority(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    rollout_root = tmp_path / "rollouts"
    parent = _start_registered_parent(parent_root)
    parent_session = _open_registered_session(
        parent_root,
        parent,
        session_id="parent-private-session",
        agent_tenure_id="parent-private-tenure",
    )
    invoke_world_actor(
        parent_session,
        WorldActorActionRequest(
            request_id="parent-private-temporal-search",
            action_name="search_evidence",
            binding=observe_world_actor(parent_session).binding,
            arguments={
                "query": "controlled test permit",
                "scope": "operations",
                "limit": 1,
            },
        ),
    )
    parent_binding = parent.repository.load_selected_session_activation()
    parent_bundle = TemporalEvidenceRepository(parent_root / "temporal-evidence").load_bundle(package=parent.package)
    assert (parent_root / "temporal-evidence" / "private").is_dir()
    assert (parent_root / "session-authority").is_dir()
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("rollout-host",),
    )
    request = _group_request(
        parent,
        group_id="temporal-inheritance-rollout-group",
        child_prefix="temporal-inheritance-rollout",
    )

    lineage = control.create_group(request)
    candidate_root = rollout_root / "groups" / lineage.group_id / "children" / "candidate" / "world"

    child_bundle = TemporalEvidenceRepository(candidate_root / "temporal-evidence").load_bundle(package=parent.package)
    assert child_bundle == parent_bundle
    assert not (candidate_root / "temporal-evidence" / "private").exists()
    assert not (candidate_root / "session-authority").exists()

    child = _child_session(
        control,
        group_id=lineage.group_id,
        child_id="candidate",
    )
    child_binding = child.run.repository.load_selected_session_activation()

    assert child_binding.binding_id != parent_binding.binding_id
    assert child_binding.run_id == child.run.manifest.run_id
    assert child_binding.world_branch_id == child.run.manifest.world_branch_id
    assert child_binding.prior_binding_id is None
    assert child_binding.session_event_sequence == 0
    assert parent.repository.load_selected_session_activation() == parent_binding


def test_registered_rollout_rejects_changed_request_for_an_existing_group_id(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    request = _group_request(
        parent,
        group_id="request-conflict-rollout-group",
        child_prefix="request-conflict-rollout",
    )
    lineage = control.create_group(request)
    changed_payload = request.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    changed_payload["reason"] = "Use changed branch intent under the existing rollout group identity."
    changed = ContinualRolloutGroupRequest.model_validate(
        changed_payload,
    )

    with pytest.raises(PumpStationRolloutError) as raised:
        control.create_group(changed)

    assert raised.value.code == "request-id-conflict"
    assert control.inspect_group(request.group_id) == lineage


@pytest.mark.parametrize(
    "field_name",
    ("child_id", "run_id", "episode_id", "world_branch_id"),
)
def test_registered_rollout_rejects_changed_child_identity_for_an_existing_group_id(
    tmp_path: Path,
    field_name: str,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    request = _group_request(
        parent,
        group_id=f"changed-{field_name}-rollout-group",
        child_prefix=f"changed-{field_name}-rollout",
    )
    lineage = control.create_group(request)
    changed_child_payload = request.children[0].model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    changed_child_payload[field_name] = f"changed-{field_name}"
    changed_child = ContinualRolloutChildRequest.model_validate(
        changed_child_payload,
    )
    changed_children = (changed_child, *request.children[1:])
    changed_payload = request.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    changed_payload["children"] = changed_children
    changed = ContinualRolloutGroupRequest.model_validate(
        changed_payload,
    )

    with pytest.raises(PumpStationRolloutError) as raised:
        control.create_group(changed)

    assert raised.value.code == "request-id-conflict"
    assert control.inspect_group(request.group_id) == lineage


def test_registered_rollout_rejects_single_child_creation(
    tmp_path: Path,
) -> None:
    parent_root = tmp_path / "parent"
    parent = _start_registered_parent(parent_root)
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("rollout-host",),
    )
    request = _group_request(
        parent,
        group_id="single-child-operation-rollout-group",
        child_prefix="single-child-operation-rollout",
    )

    with pytest.raises(PumpStationRolloutError) as raised:
        control.create_child(request, "control")

    assert raised.value.code == "rollout-operation"
