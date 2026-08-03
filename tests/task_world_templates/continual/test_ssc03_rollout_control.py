# ABOUTME: Tests shared rollout orchestration through the real SSC-03 lifecycle branch port.
# ABOUTME: Proves chosen-point branching, exact retry, isolation, and ordered lineage.

from __future__ import annotations

import hashlib
import json
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import ValidationError

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualRolloutGroupState,
    ContinualRolloutLineage,
    ContinualWorldDefinitionSpec,
)
from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    read_evidence_lifecycle_branch_snapshot,
    read_evidence_lifecycle_state,
    run_evidence_lifecycle,
    submit_evidence_checkpoint,
)
from aec_bench.task_world_templates.continual.definition import ContinualWorldDefinition
from aec_bench.task_world_templates.continual.rollout_control import (
    ContinualRolloutControl,
    ContinualRolloutError,
)
from aec_bench.task_world_templates.continual.rollout_repository import ContinualRolloutRepository
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_continual_definition import (
    Ssc03HydraulicContinualProfile,
    ssc03_hydraulic_continual_world_definition,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_rollout_adapter import (
    Ssc03HydraulicRolloutBranchReceipt,
    ssc03_hydraulic_rollout_origin,
)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_shared_control_rejects_all_unsafe_storage_identities_before_origin_or_writes(
    tmp_path: Path,
) -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    profile_ref = definition.profile_ref("major_idf_revision", "1")
    loaded = definition.load_profile(profile_ref)
    assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)
    compiled = loaded.value.compile(tmp_path / "package")
    environment = loaded.value.build_smoke_environment(compiled.package_dir)
    assert environment is not None
    parent_run = tmp_path / "parent-run"
    run_evidence_lifecycle(compiled.package_dir, parent_run, episode_environment=environment)
    origin = ssc03_hydraulic_rollout_origin(
        compiled.package_dir,
        parent_run,
        checkpoint_id="revision_analysis",
    )
    child = ContinualRolloutChildRequest(
        child_id="valid-child",
        run_id="storage-preflight-child-run",
        episode_id="storage-preflight-child-episode",
        world_branch_id="storage-preflight-child-branch",
    )
    base_request = ContinualRolloutGroupRequest(
        request_id="storage-preflight-request",
        group_id="storage-preflight-group",
        task_world_id=definition.ref.task_world_id,
        authority_id="host-control",
        definition_ref=definition.ref,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=origin.parent_manifest_content_sha256,
        parent_snapshot=origin.parent_snapshot,
        origin_verification_content_sha256=origin.origin_verification_content_sha256,
        reason="Reject unsafe storage identities before any durable work.",
        children=(child,),
    )
    rollout_root = tmp_path / "rollouts"
    control = ContinualRolloutControl(
        definition,
        parent_run_root=parent_run,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("host-control",),
        package_root=compiled.package_dir,
    )
    parent_before = _tree_bytes(parent_run)
    foreign_snapshot_payload = origin.parent_snapshot.model_dump(mode="python", exclude={"content_sha256"})
    foreign_snapshot_payload["run_id"] = "foreign-parent-run"
    foreign_snapshot = type(origin.parent_snapshot)(**foreign_snapshot_payload)

    unsafe_group_payload = base_request.model_dump(mode="python", exclude={"content_sha256"})
    unsafe_group_payload.update(
        request_id="unsafe-group-request",
        group_id="../unsafe-group",
        parent_snapshot=foreign_snapshot,
    )
    with pytest.raises(ContinualRolloutError, match="unsafe-identity: invalid group id"):
        control.create_group(ContinualRolloutGroupRequest(**unsafe_group_payload))

    unsafe_child = ContinualRolloutChildRequest(
        child_id="../unsafe-child",
        run_id="unsafe-storage-child-run",
        episode_id="unsafe-storage-child-episode",
        world_branch_id="unsafe-storage-child-branch",
    )
    unsafe_child_payload = base_request.model_dump(mode="python", exclude={"content_sha256"})
    unsafe_child_payload.update(
        request_id="unsafe-child-before-origin-request",
        group_id="unsafe-child-before-origin-group",
        parent_snapshot=foreign_snapshot,
        children=(unsafe_child,),
    )
    with pytest.raises(ContinualRolloutError, match="unsafe-identity: invalid child id"):
        control.create_group(ContinualRolloutGroupRequest(**unsafe_child_payload))

    unsafe_child_payload.update(
        request_id="unsafe-child-no-write-request",
        group_id="unsafe-child-no-write-group",
        parent_snapshot=origin.parent_snapshot,
    )
    with pytest.raises(ContinualRolloutError, match="unsafe-identity: invalid child id"):
        control.create_group(ContinualRolloutGroupRequest(**unsafe_child_payload))

    assert _tree_bytes(parent_run) == parent_before
    assert tuple(rollout_root.iterdir()) == ()


def test_shared_control_branches_two_real_ssc03_children_from_one_chosen_checkpoint(
    tmp_path: Path,
) -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    profile_ref = definition.profile_ref("major_idf_revision", "1")
    loaded = definition.load_profile(profile_ref)
    assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)
    compiled = loaded.value.compile(tmp_path / "package")
    environment = loaded.value.build_smoke_environment(compiled.package_dir)
    assert environment is not None
    parent_run = tmp_path / "parent-run"
    run_evidence_lifecycle(
        compiled.package_dir,
        parent_run,
        episode_environment=environment,
    )
    lifecycle_before = _tree_bytes(parent_run)
    branch_snapshot = read_evidence_lifecycle_branch_snapshot(
        compiled.package_dir,
        parent_run,
        checkpoint_id="revision_analysis",
    )
    assert branch_snapshot.checkpoint_id == "revision_analysis"
    assert _tree_bytes(parent_run) == lifecycle_before
    parent_before = (parent_run / "state.json").read_bytes()
    origin = ssc03_hydraulic_rollout_origin(
        compiled.package_dir,
        parent_run,
        checkpoint_id="revision_analysis",
    )
    expected_run_id = f"ssc03-run-{hashlib.sha256(str(parent_run.resolve()).encode('utf-8')).hexdigest()}"
    assert origin.parent_snapshot.run_id == expected_run_id
    assert origin.parent_snapshot.episode_id == "ssc03-checkpoint-revision_analysis"
    request = ContinualRolloutGroupRequest(
        request_id="request-ssc03-1",
        group_id="group-ssc03-1",
        task_world_id=definition.ref.task_world_id,
        authority_id="host-control",
        definition_ref=definition.ref,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=origin.parent_manifest_content_sha256,
        parent_snapshot=origin.parent_snapshot,
        origin_verification_content_sha256=origin.origin_verification_content_sha256,
        reason="Recheck the submitted response from two isolated continuations.",
        children=(
            ContinualRolloutChildRequest(
                child_id="child-a",
                run_id="ssc03-child-run-a",
                episode_id="ssc03-child-episode-a",
                world_branch_id="ssc03-branch-a",
            ),
            ContinualRolloutChildRequest(
                child_id="child-b",
                run_id="ssc03-child-run-b",
                episode_id="ssc03-child-episode-b",
                world_branch_id="ssc03-branch-b",
            ),
        ),
    )
    control = ContinualRolloutControl(
        definition,
        parent_run_root=parent_run,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("host-control",),
        package_root=compiled.package_dir,
    )

    foreign_snapshot_payload = origin.parent_snapshot.model_dump(mode="python", exclude={"content_sha256"})
    foreign_snapshot_payload["run_id"] = "caller-selected-parent-run"
    foreign_payload = request.model_dump(mode="python", exclude={"content_sha256"})
    foreign_payload.update(
        request_id="request-ssc03-foreign-parent",
        group_id="group-ssc03-foreign-parent",
        parent_snapshot=type(origin.parent_snapshot)(**foreign_snapshot_payload),
    )
    with pytest.raises(ContinualRolloutError, match="origin-verification"):
        control.create_group(ContinualRolloutGroupRequest(**foreign_payload))
    assert not (tmp_path / "rollouts" / "groups" / "group-ssc03-foreign-parent").exists()

    lineage = control.create_group(request)
    replayed = control.create_group(request)

    assert replayed == lineage
    assert tuple(child.child_id for child in lineage.children) == ("child-a", "child-b")
    assert tuple(child.ancestor_world_branch_ids for child in lineage.children) == (("root",), ("root",))
    assert control.group_status(request.group_id).state is ContinualRolloutGroupState.READY
    assert control.child_run_ref(request.group_id, "child-a").initial_snapshot.world_branch_id == "ssc03-branch-a"
    assert (parent_run / "state.json").read_bytes() == parent_before

    for child_id, branch_id in (("child-a", "ssc03-branch-a"), ("child-b", "ssc03-branch-b")):
        child_run = tmp_path / "rollouts" / "groups" / request.group_id / "children" / child_id / "world"
        state = read_evidence_lifecycle_state(compiled.package_dir, child_run)
        assert state["active_checkpoint_id"] == "revision_analysis"
        assert state["branch"]["branch_id"] == branch_id
        task_receipt_path = child_run / "rollout-branch-receipt.json"
        task_receipt_bytes = task_receipt_path.read_bytes()
        generic_receipt = next(item for item in lineage.children if item.child_id == child_id)
        assert hashlib.sha256(task_receipt_bytes).hexdigest() == generic_receipt.task_branch_receipt_content_sha256
        assert stat.S_IMODE(task_receipt_path.stat().st_mode) == 0o600
        task_receipt = Ssc03HydraulicRolloutBranchReceipt.model_validate_json(task_receipt_bytes)
        assert tuple(item.checkpoint_id for item in task_receipt.submitted_checkpoint_prefix) == (
            "baseline_analysis",
            "revision_analysis",
        )
        if child_id == "child-a":
            foreign_ancestry = task_receipt.model_dump(mode="python", exclude={"content_sha256"})
            foreign_ancestry["ancestor_world_branch_ids"] = ("foreign-branch",)
            with pytest.raises(ValidationError, match="rollout branch ancestry is invalid"):
                Ssc03HydraulicRolloutBranchReceipt(**foreign_ancestry)

    changed_payload = request.model_dump(mode="python", exclude={"content_sha256"})
    changed_payload["reason"] = "Changed request."
    with pytest.raises(ContinualRolloutError, match="request-conflict"):
        control.create_group(ContinualRolloutGroupRequest(**changed_payload))

    stale_spec_payload = definition.spec.model_dump(mode="python", exclude={"content_sha256"})
    stale_spec_payload["implementation_content_sha256"] = "f" * 64
    stale_definition = ContinualWorldDefinition(
        spec=ContinualWorldDefinitionSpec(**stale_spec_payload),
        profile_loader=definition.profile_loader,
        branch_port=definition.branch_port,
    )
    stale_control = ContinualRolloutControl(
        stale_definition,
        parent_run_root=parent_run,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("host-control",),
        package_root=compiled.package_dir,
    )
    with pytest.raises(ContinualRolloutError, match="definition"):
        stale_control.inspect_group(request.group_id)

    receipt_a_path = tmp_path / "rollouts" / "groups" / request.group_id / "children" / "child-a" / "receipt.json"
    receipt_b_path = tmp_path / "rollouts" / "groups" / request.group_id / "children" / "child-b" / "receipt.json"
    receipt_a_bytes = receipt_a_path.read_bytes()
    receipt_a_path.write_bytes(receipt_b_path.read_bytes())
    with pytest.raises(ContinualRolloutError, match="child-receipt-integrity"):
        control.inspect_group(request.group_id)
    receipt_a_path.write_bytes(receipt_a_bytes)
    assert control.inspect_group(request.group_id) == lineage

    child_state_path = (
        tmp_path / "rollouts" / "groups" / request.group_id / "children" / "child-a" / "world" / "state.json"
    )
    child_state = json.loads(child_state_path.read_text(encoding="utf-8"))
    child_state["branch"]["branch_id"] = "tampered-branch"
    child_state_path.write_text(json.dumps(child_state, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ContinualRolloutError, match="child-verification"):
        control.child_run_ref(request.group_id, "child-a")

    parent_state_path = parent_run / "state.json"
    parent_state = json.loads(parent_state_path.read_text(encoding="utf-8"))
    baseline = next(
        checkpoint
        for checkpoint in parent_state["checkpoint_runs"]
        if checkpoint["checkpoint_id"] == "baseline_analysis"
    )
    baseline_archive = parent_run / "episodes" / "baseline_analysis" / "submission.json"
    baseline_workspace = parent_run / "workspace" / baseline["submission_path"]
    changed_baseline = baseline_archive.read_bytes() + b"\n"
    baseline_archive.write_bytes(changed_baseline)
    baseline_workspace.write_bytes(changed_baseline)
    baseline["submission_sha256"] = hashlib.sha256(changed_baseline).hexdigest()
    parent_state_path.write_text(json.dumps(parent_state, indent=2) + "\n", encoding="utf-8")

    changed_origin = ssc03_hydraulic_rollout_origin(
        compiled.package_dir,
        parent_run,
        checkpoint_id="revision_analysis",
    )
    assert changed_origin.parent_snapshot == origin.parent_snapshot
    assert changed_origin.origin_verification_content_sha256 != origin.origin_verification_content_sha256
    with pytest.raises(ContinualRolloutError, match="origin-verification"):
        control.create_group(request)
    assert control.inspect_group(request.group_id) == lineage
    assert control.group_status(request.group_id).state is ContinualRolloutGroupState.READY
    assert control.child_run_ref(request.group_id, "child-b").world_branch_id == "ssc03-branch-b"


def test_nested_ssc03_rollout_keeps_declared_parent_run_identity_and_lineage(
    tmp_path: Path,
) -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    profile_ref = definition.profile_ref("major_idf_revision", "1")
    loaded = definition.load_profile(profile_ref)
    assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)
    compiled = loaded.value.compile(tmp_path / "package")
    environment = loaded.value.build_smoke_environment(compiled.package_dir)
    assert environment is not None
    parent_run = tmp_path / "parent-run"
    run_evidence_lifecycle(compiled.package_dir, parent_run, episode_environment=environment)
    parent_origin = ssc03_hydraulic_rollout_origin(
        compiled.package_dir,
        parent_run,
        checkpoint_id="revision_analysis",
    )
    parent_child = ContinualRolloutChildRequest(
        child_id="nested-parent-child",
        run_id="declared-nested-parent-run",
        episode_id="declared-nested-parent-episode",
        world_branch_id="declared-nested-parent-branch",
    )
    parent_request = ContinualRolloutGroupRequest(
        request_id="nested-parent-request",
        group_id="nested-parent-group",
        task_world_id=definition.ref.task_world_id,
        authority_id="host-control",
        definition_ref=definition.ref,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=parent_origin.parent_manifest_content_sha256,
        parent_snapshot=parent_origin.parent_snapshot,
        origin_verification_content_sha256=parent_origin.origin_verification_content_sha256,
        reason="Create the durable parent for a nested continuation.",
        children=(parent_child,),
    )
    parent_control = ContinualRolloutControl(
        definition,
        parent_run_root=parent_run,
        rollout_repository_root=tmp_path / "parent-rollouts",
        authorised_principal_ids=("host-control",),
        package_root=compiled.package_dir,
    )
    parent_control.create_group(parent_request)
    nested_parent_root = (
        tmp_path / "parent-rollouts" / "groups" / parent_request.group_id / "children" / parent_child.child_id / "world"
    )
    submit_evidence_checkpoint(compiled.package_dir, nested_parent_root)

    nested_origin = ssc03_hydraulic_rollout_origin(
        compiled.package_dir,
        nested_parent_root,
        checkpoint_id="revision_analysis",
    )

    assert nested_origin.parent_snapshot.run_id == parent_child.run_id
    assert nested_origin.parent_snapshot.world_branch_id == parent_child.world_branch_id
    nested_child = ContinualRolloutChildRequest(
        child_id="nested-child",
        run_id="declared-nested-child-run",
        episode_id="declared-nested-child-episode",
        world_branch_id="declared-nested-child-branch",
    )
    nested_request = ContinualRolloutGroupRequest(
        request_id="nested-request",
        group_id="nested-group",
        task_world_id=definition.ref.task_world_id,
        authority_id="host-control",
        definition_ref=definition.ref,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=nested_origin.parent_manifest_content_sha256,
        parent_snapshot=nested_origin.parent_snapshot,
        origin_verification_content_sha256=nested_origin.origin_verification_content_sha256,
        reason="Continue from the declared child run without changing its identity.",
        children=(nested_child,),
    )
    nested_control = ContinualRolloutControl(
        definition,
        parent_run_root=nested_parent_root,
        rollout_repository_root=tmp_path / "nested-rollouts",
        authorised_principal_ids=("host-control",),
        package_root=compiled.package_dir,
    )

    nested_lineage = nested_control.create_group(nested_request)

    assert nested_lineage.parent_snapshot.run_id == parent_child.run_id
    assert nested_lineage.children[0].ancestor_world_branch_ids == (
        "root",
        parent_child.world_branch_id,
    )
    nested_receipt_path = (
        tmp_path
        / "nested-rollouts"
        / "groups"
        / nested_request.group_id
        / "children"
        / nested_child.child_id
        / "world"
        / "rollout-branch-receipt.json"
    )
    nested_receipt = Ssc03HydraulicRolloutBranchReceipt.model_validate_json(nested_receipt_path.read_bytes())
    assert nested_receipt.parent_snapshot.run_id == parent_child.run_id
    assert nested_receipt.ancestor_world_branch_ids == ("root", parent_child.world_branch_id)

    parent_receipt_path = nested_parent_root / "rollout-branch-receipt.json"
    parent_receipt_payload = json.loads(parent_receipt_path.read_text(encoding="utf-8"))
    parent_receipt_payload["initial_snapshot"]["run_id"] = "tampered-parent-run"
    parent_receipt_path.write_text(json.dumps(parent_receipt_payload, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValidationError, match="content_sha256"):
        ssc03_hydraulic_rollout_origin(
            compiled.package_dir,
            nested_parent_root,
            checkpoint_id="revision_analysis",
        )


def test_shared_control_recovers_real_ssc03_child_created_before_its_receipt(
    tmp_path: Path,
) -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    profile_ref = definition.profile_ref("major_idf_revision", "1")
    loaded = definition.load_profile(profile_ref)
    assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)
    compiled = loaded.value.compile(tmp_path / "package")
    environment = loaded.value.build_smoke_environment(compiled.package_dir)
    assert environment is not None
    parent_run = tmp_path / "parent-run"
    run_evidence_lifecycle(compiled.package_dir, parent_run, episode_environment=environment)
    origin_fields = ssc03_hydraulic_rollout_origin(
        compiled.package_dir,
        parent_run,
        checkpoint_id="revision_analysis",
    )
    child = ContinualRolloutChildRequest(
        child_id="interrupted-child",
        run_id="ssc03-interrupted-run",
        episode_id="ssc03-interrupted-episode",
        world_branch_id="ssc03-interrupted-branch",
    )
    request = ContinualRolloutGroupRequest(
        request_id="interrupted-request",
        group_id="interrupted-group",
        task_world_id=definition.ref.task_world_id,
        authority_id="host-control",
        definition_ref=definition.ref,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=origin_fields.parent_manifest_content_sha256,
        parent_snapshot=origin_fields.parent_snapshot,
        origin_verification_content_sha256=origin_fields.origin_verification_content_sha256,
        reason="Recover an interrupted child publication.",
        children=(child,),
    )
    repository = ContinualRolloutRepository(
        tmp_path / "rollouts",
        disjoint_roots=(parent_run, compiled.package_dir),
    )
    control = ContinualRolloutControl(
        definition,
        parent_run_root=parent_run,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("host-control",),
        package_root=compiled.package_dir,
    )
    assert definition.branch_port is not None
    verified_origin = definition.branch_port.verify_origin(
        profile_value=loaded.value,
        package_root=compiled.package_dir,
        parent_run_root=parent_run,
        request=request,
    )
    with repository.locked(request.group_id):
        repository.publish_group_request(request)
    assert control.group_status(request.group_id).state is ContinualRolloutGroupState.PREPARING
    with repository.locked(request.group_id):
        repository.publish_child_request(request.group_id, child)
    definition.branch_port.materialize_child(
        profile_value=loaded.value,
        package_root=compiled.package_dir,
        parent_run_root=parent_run,
        child_run_root=repository.child_world_root(request.group_id, child.child_id),
        request=request,
        child=child,
        origin=verified_origin,
    )

    interrupted_request_path = (
        repository.root / "groups" / request.group_id / "children" / child.child_id / "request.json"
    )
    interrupted_request_bytes = interrupted_request_path.read_bytes()
    different_child = ContinualRolloutChildRequest(
        child_id=child.child_id,
        run_id="different-interrupted-run",
        episode_id="different-interrupted-episode",
        world_branch_id="different-interrupted-branch",
    )
    interrupted_request_path.write_bytes(
        json.dumps(
            different_child.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    with pytest.raises(ContinualRolloutError, match="child-request-integrity"):
        control.group_status(request.group_id)
    interrupted_request_path.write_bytes(interrupted_request_bytes)
    assert control.group_status(request.group_id).state is ContinualRolloutGroupState.PREPARING
    with pytest.raises(ContinualRolloutError, match="group-not-ready"):
        control.child_run_ref(request.group_id, child.child_id)

    lineage = control.create_group(request)

    assert tuple(receipt.child_id for receipt in lineage.children) == ("interrupted-child",)
    assert control.group_status(request.group_id).state is ContinualRolloutGroupState.READY
    child_receipt_path = repository.root / "groups" / request.group_id / "children" / child.child_id / "receipt.json"
    moved_child_receipt_path = child_receipt_path.with_suffix(".missing")
    child_receipt_path.rename(moved_child_receipt_path)
    with pytest.raises(ContinualRolloutError, match="child-receipt-integrity"):
        control.group_status(request.group_id)
    moved_child_receipt_path.rename(child_receipt_path)

    concurrent_child = ContinualRolloutChildRequest(
        child_id="concurrent-child",
        run_id="ssc03-concurrent-run",
        episode_id="ssc03-concurrent-episode",
        world_branch_id="ssc03-concurrent-branch",
    )
    concurrent_payload = request.model_dump(mode="python", exclude={"content_sha256"})
    concurrent_payload.update(
        request_id="concurrent-request",
        group_id="concurrent-group",
        reason="Create one exact child through two concurrent retries.",
        children=(concurrent_child,),
    )
    concurrent_request = ContinualRolloutGroupRequest(**concurrent_payload)
    barrier = Barrier(2)

    def create_concurrently() -> ContinualRolloutLineage:
        barrier.wait()
        return control.create_group(concurrent_request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(executor.submit(create_concurrently) for _ in range(2))
        concurrent_lineages = tuple(future.result() for future in futures)

    assert concurrent_lineages[0] == concurrent_lineages[1]
    assert tuple(receipt.child_id for receipt in concurrent_lineages[0].children) == ("concurrent-child",)

    unsafe_child = ContinualRolloutChildRequest(
        child_id="unsafe-child",
        run_id="ssc03-unsafe-run",
        episode_id="ssc03-unsafe-episode",
        world_branch_id="ssc03-unsafe-branch",
    )
    unsafe_payload = request.model_dump(mode="python", exclude={"content_sha256"})
    unsafe_payload.update(
        request_id="unsafe-request",
        group_id="unsafe-group",
        reason="Reject a child destination that escapes the rollout repository.",
        children=(unsafe_child,),
    )
    unsafe_request = ContinualRolloutGroupRequest(**unsafe_payload)
    with repository.locked(unsafe_request.group_id):
        repository.publish_group_request(unsafe_request)
        repository.publish_child_request(unsafe_request.group_id, unsafe_child)
    outside = tmp_path / "outside-child"
    outside.mkdir()
    unsafe_world = repository.root / "groups" / unsafe_request.group_id / "children" / unsafe_child.child_id / "world"
    unsafe_world.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ContinualRolloutError, match="artifact-confinement"):
        control.create_group(unsafe_request)
    assert tuple(outside.iterdir()) == ()


def test_ssc03_historical_rollout_validates_only_the_selected_submission_prefix(
    tmp_path: Path,
) -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    profile_ref = definition.profile_ref("major_idf_revision", "1")
    loaded = definition.load_profile(profile_ref)
    assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)
    compiled = loaded.value.compile(tmp_path / "package")
    environment = loaded.value.build_smoke_environment(compiled.package_dir)
    assert environment is not None
    parent_run = tmp_path / "parent-run"
    run_evidence_lifecycle(compiled.package_dir, parent_run, episode_environment=environment)

    later_archive = parent_run / "episodes" / "closeout_review" / "submission.json"
    later_archive_bytes = later_archive.read_bytes()
    later_archive.write_bytes(later_archive_bytes + b"\n")

    with pytest.raises(EvidenceLifecycleError, match="archived checkpoint submission changed: closeout_review"):
        read_evidence_lifecycle_state(compiled.package_dir, parent_run)

    origin = ssc03_hydraulic_rollout_origin(
        compiled.package_dir,
        parent_run,
        checkpoint_id="revision_analysis",
    )
    child = ContinualRolloutChildRequest(
        child_id="historical-prefix-child",
        run_id="historical-prefix-child-run",
        episode_id="historical-prefix-child-episode",
        world_branch_id="historical-prefix-child-branch",
    )
    request = ContinualRolloutGroupRequest(
        request_id="historical-prefix-request",
        group_id="historical-prefix-group",
        task_world_id=definition.ref.task_world_id,
        authority_id="host-control",
        definition_ref=definition.ref,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=origin.parent_manifest_content_sha256,
        parent_snapshot=origin.parent_snapshot,
        origin_verification_content_sha256=origin.origin_verification_content_sha256,
        reason="Continue from revision analysis without depending on later closeout evidence.",
        children=(child,),
    )
    control = ContinualRolloutControl(
        definition,
        parent_run_root=parent_run,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("host-control",),
        package_root=compiled.package_dir,
    )

    lineage = control.create_group(request)

    assert lineage.parent_snapshot == origin.parent_snapshot
    assert lineage.children[0].child_id == child.child_id

    later_archive.write_bytes(later_archive_bytes)
    selected_archive = parent_run / "episodes" / "revision_analysis" / "submission.json"
    selected_archive.write_bytes(selected_archive.read_bytes() + b"\n")

    with pytest.raises(EvidenceLifecycleError, match="archived checkpoint submission changed: revision_analysis"):
        ssc03_hydraulic_rollout_origin(
            compiled.package_dir,
            parent_run,
            checkpoint_id="revision_analysis",
        )
