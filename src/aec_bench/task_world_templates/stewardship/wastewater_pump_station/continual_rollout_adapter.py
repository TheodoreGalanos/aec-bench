# ABOUTME: Adapts registered pump runs to shared chosen-point rollout orchestration.
# ABOUTME: Verifies exact origins, materializes children, and records pump lineage evidence.

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildReceipt,
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualWorldSnapshotRef,
)
from aec_bench.task_world_templates.continual.branch_port import (
    ContinualWorldBranchMaterialization,
    VerifiedContinualWorldBranchOrigin,
)
from aec_bench.task_world_templates.continual.durability import ImmutableByteStore
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    PumpStationContinualProfile,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_models import (
    PUMP_STATION_ROLLOUT_BRANCH_RECEIPT_VERSION_V2,
    PumpStationRolloutBranchReceiptV2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_STATE_VERSION_V4,
    PumpStationCoupledStewardshipState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.models import (
    TemporalEvidenceBundle,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.repository import (
    TemporalEvidenceRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationInitialStateSource,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunManifestV2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
    pump_station_artifact_id,
)


@dataclass(frozen=True, slots=True)
class _PumpStationVerifiedRolloutOrigin:
    """Pump values captured from one prefix-verified selected-history origin."""

    manifest: PumpStationWorldRunManifestV2
    state: PumpStationCoupledStewardshipState
    bundle: TemporalEvidenceBundle
    snapshot: PumpStationStateSnapshotRef
    remaining_schedule_sha256: str


class PumpStationContinualWorldBranchPort:
    """Materialize registered pump children through the durable V4 world run."""

    _TASK_RECEIPT_PATH = "rollout-branch-receipt.json"

    def verify_origin(
        self,
        *,
        profile_value: object,
        package_root: Path | None,
        parent_run_root: Path,
        request: ContinualRolloutGroupRequest,
    ) -> VerifiedContinualWorldBranchOrigin:
        """Capture and prefix-verify one selected pump snapshot under its run lock."""

        del package_root
        profile = self._profile(profile_value)
        repository = PumpStationWorldRunRepository(parent_run_root)
        manifest = repository.load_manifest()
        if not isinstance(manifest, PumpStationWorldRunManifestV2):
            raise ValueError("registered pump rollout requires manifest v2")
        if (
            PumpStationWorldRun._definition_ref(manifest) != request.definition_ref
            or PumpStationWorldRun._profile_ref(manifest) != request.profile_ref
        ):
            raise ValueError("registered pump rollout identity differs")
        manifest_content_id = pump_station_artifact_id(
            manifest,
            record_profile="manifest-v2",
        )
        if manifest_content_id != request.parent_manifest_content_sha256:
            raise ValueError("registered pump parent manifest differs")
        run = PumpStationWorldRun._resume_reference_system_for_historical_prefix(
            repository=repository,
            snapshot=repository.current_snapshot(),
        )
        snapshot = _pump_snapshot(
            request.parent_snapshot,
            snapshot_version=manifest.snapshot_version,
        )
        with repository.locked():
            repository.commits_through(snapshot)
            report = run._verify_v4_under_lock(snapshot)
            if not report.valid or report.final_state_id != snapshot.state_id:
                raise ValueError("registered pump rollout origin replay differs")
            report_content_id = pump_station_artifact_id(
                report,
                record_profile="v4",
            )
            if report_content_id != request.origin_verification_content_sha256:
                raise ValueError("registered pump rollout origin verification differs")
            state = repository.load_state(snapshot.state_id)
            if state.state_version != PUMP_STATION_STATE_VERSION_V4:
                raise ValueError("registered pump rollout selected a non-V4 state")
            selected_state = cast(PumpStationCoupledStewardshipState, state)
            bundle = TemporalEvidenceRepository(
                repository.root / "temporal-evidence",
            ).load_bundle(package=profile.station_package)
            remaining_schedule_sha256 = _remaining_schedule_sha256(selected_state)
        ancestors = (
            *manifest.initial_state_source.ancestor_branch_ids,
            manifest.world_branch_id,
        )
        if len(ancestors) != len(set(ancestors)):
            raise ValueError("registered pump rollout ancestry contains a cycle")
        return VerifiedContinualWorldBranchOrigin(
            parent_snapshot=request.parent_snapshot,
            parent_manifest_content_sha256=manifest_content_id,
            origin_verification_content_sha256=report_content_id,
            ancestor_world_branch_ids=ancestors,
            task_context=_PumpStationVerifiedRolloutOrigin(
                manifest=manifest,
                state=selected_state,
                bundle=bundle,
                snapshot=snapshot,
                remaining_schedule_sha256=remaining_schedule_sha256,
            ),
        )

    def materialize_child(
        self,
        *,
        profile_value: object,
        package_root: Path | None,
        parent_run_root: Path,
        child_run_root: Path,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        origin: VerifiedContinualWorldBranchOrigin,
    ) -> ContinualWorldBranchMaterialization:
        """Create or recover one child with inherited public temporal evidence."""

        del package_root
        profile = self._profile(profile_value)
        context = self._origin_context(origin)
        source = PumpStationInitialStateSource(
            kind="rollout_parent_snapshot",
            opening_specification_id=context.manifest.opening_state_specification_id,
            opening_specification_sha256=context.manifest.opening_state_specification_sha256,
            parent_run_id=context.snapshot.run_id,
            parent_branch_id=context.snapshot.world_branch_id,
            parent_state_id=context.snapshot.state_id,
            parent_commit_id=context.snapshot.commit_id,
            rollout_group_request_id=request.request_id,
            child_request_content_id=child.content_sha256,
            rollout_group_request_content_id=request.content_sha256,
            parent_manifest_content_id=request.parent_manifest_content_sha256,
            origin_verification_content_id=request.origin_verification_content_sha256,
            parent_origin_remaining_schedule_sha256=context.remaining_schedule_sha256,
            ancestor_branch_ids=origin.ancestor_world_branch_ids,
        )
        manifest = replace(
            context.manifest,
            run_id=child.run_id,
            episode_id=child.episode_id,
            world_branch_id=child.world_branch_id,
            initial_sequence=context.snapshot.sequence,
            initial_state_id=context.snapshot.state_id,
            initial_state_source=source,
        )
        repository = PumpStationWorldRunRepository(child_run_root)
        repository.initialize(
            manifest,
            context.state,
            before_select=lambda: PumpStationWorldRun._initialize_reference_temporal_evidence(
                repository=repository,
                package=profile.station_package,
                bundle=context.bundle,
            ),
        )
        PumpStationWorldRun._verify_reference_temporal_evidence(
            repository=repository,
            package=profile.station_package,
            manifest=manifest,
            expected=context.bundle,
        )
        run = PumpStationWorldRun.resume_reference_system(
            repository=repository,
            snapshot=repository.current_snapshot(),
        )
        if not run.verify_v4().valid:
            raise ValueError("registered pump child replay differs")
        initial_snapshot = _initial_snapshot(repository, manifest)
        task_receipt = PumpStationRolloutBranchReceiptV2(
            receipt_version=PUMP_STATION_ROLLOUT_BRANCH_RECEIPT_VERSION_V2,
            group_id=request.group_id,
            child_id=child.child_id,
            shared_group_request_content_sha256=request.content_sha256,
            shared_child_request_content_sha256=child.content_sha256,
            parent_snapshot=context.snapshot,
            initial_snapshot=initial_snapshot,
            child_manifest_content_id=pump_station_artifact_id(
                manifest,
                record_profile="manifest-v2",
            ),
            temporal_bundle_content_id=manifest.temporal_bundle_content_id,
            parent_origin_remaining_schedule_sha256=context.remaining_schedule_sha256,
            ancestor_branch_ids=origin.ancestor_world_branch_ids,
        )
        artifact = _task_store(
            repository.root,
            parent_run_root=parent_run_root,
        ).publish_bytes(
            self._TASK_RECEIPT_PATH,
            pump_station_artifact_bytes(task_receipt, record_profile="v4"),
        )
        return ContinualWorldBranchMaterialization(
            initial_snapshot=_shared_snapshot(initial_snapshot),
            child_manifest_content_sha256=task_receipt.child_manifest_content_id,
            task_branch_receipt_content_sha256=artifact.sha256,
            ancestor_world_branch_ids=task_receipt.ancestor_branch_ids,
        )

    def verify_child(
        self,
        *,
        profile_value: object,
        package_root: Path | None,
        parent_run_root: Path,
        child_run_root: Path,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        receipt: ContinualRolloutChildReceipt,
    ) -> None:
        """Verify the child, complete source provenance, and task receipt."""

        del package_root
        self._profile(profile_value)
        repository = PumpStationWorldRunRepository(child_run_root)
        manifest = repository.load_manifest()
        if not isinstance(manifest, PumpStationWorldRunManifestV2):
            raise ValueError("registered pump child requires manifest v2")
        run = PumpStationWorldRun.resume_reference_system(
            repository=repository,
            snapshot=repository.current_snapshot(),
        )
        if not run.verify_v4().valid:
            raise ValueError("registered pump child replay differs")
        initial_snapshot = _initial_snapshot(repository, manifest)
        manifest_content_id = pump_station_artifact_id(
            manifest,
            record_profile="manifest-v2",
        )
        if (
            receipt.initial_snapshot != _shared_snapshot(initial_snapshot)
            or receipt.child_manifest_content_sha256 != manifest_content_id
        ):
            raise ValueError("registered pump shared child receipt differs")
        payload = _task_store(
            repository.root,
            parent_run_root=parent_run_root,
        ).load_bytes(
            self._TASK_RECEIPT_PATH,
            expected_sha256=receipt.task_branch_receipt_content_sha256,
        )
        task_receipt = load_pump_station_artifact(
            payload,
            PumpStationRolloutBranchReceiptV2,
        )
        parent_snapshot = _pump_snapshot(
            request.parent_snapshot,
            snapshot_version=manifest.snapshot_version,
        )
        initial_state = repository.load_state(manifest.initial_state_id)
        if initial_state.state_version != PUMP_STATION_STATE_VERSION_V4:
            raise ValueError("registered pump child initial state is not V4")
        remaining_schedule_sha256 = _remaining_schedule_sha256(
            cast(PumpStationCoupledStewardshipState, initial_state),
        )
        source = manifest.initial_state_source
        expected_source_scope = (
            "rollout_parent_snapshot",
            request.parent_snapshot.run_id,
            request.parent_snapshot.world_branch_id,
            request.parent_snapshot.state_id,
            request.parent_snapshot.commit_id,
            request.request_id,
            child.content_sha256,
            request.content_sha256,
            request.parent_manifest_content_sha256,
            request.origin_verification_content_sha256,
            remaining_schedule_sha256,
            receipt.ancestor_world_branch_ids,
        )
        observed_source_scope = (
            source.kind,
            source.parent_run_id,
            source.parent_branch_id,
            source.parent_state_id,
            source.parent_commit_id,
            source.rollout_group_request_id,
            source.child_request_content_id,
            source.rollout_group_request_content_id,
            source.parent_manifest_content_id,
            source.origin_verification_content_id,
            source.parent_origin_remaining_schedule_sha256,
            source.ancestor_branch_ids,
        )
        expected_task_scope = (
            PUMP_STATION_ROLLOUT_BRANCH_RECEIPT_VERSION_V2,
            request.group_id,
            child.child_id,
            request.content_sha256,
            child.content_sha256,
            parent_snapshot,
            initial_snapshot,
            manifest_content_id,
            manifest.temporal_bundle_content_id,
            remaining_schedule_sha256,
            receipt.ancestor_world_branch_ids,
        )
        observed_task_scope = (
            task_receipt.receipt_version,
            task_receipt.group_id,
            task_receipt.child_id,
            task_receipt.shared_group_request_content_sha256,
            task_receipt.shared_child_request_content_sha256,
            task_receipt.parent_snapshot,
            task_receipt.initial_snapshot,
            task_receipt.child_manifest_content_id,
            task_receipt.temporal_bundle_content_id,
            task_receipt.parent_origin_remaining_schedule_sha256,
            task_receipt.ancestor_branch_ids,
        )
        if (
            observed_source_scope != expected_source_scope
            or observed_task_scope != expected_task_scope
            or (manifest.initial_sequence, manifest.initial_state_id)
            != (parent_snapshot.sequence, parent_snapshot.state_id)
            or (manifest.run_id, manifest.episode_id, manifest.world_branch_id)
            != (child.run_id, child.episode_id, child.world_branch_id)
        ):
            raise ValueError("registered pump child rollout provenance differs")

    @staticmethod
    def _profile(value: object) -> PumpStationContinualProfile:
        if not isinstance(value, PumpStationContinualProfile):
            raise ValueError("registered pump profile has another task-owned value")
        return value

    @staticmethod
    def _origin_context(
        origin: VerifiedContinualWorldBranchOrigin,
    ) -> _PumpStationVerifiedRolloutOrigin:
        if not isinstance(origin.task_context, _PumpStationVerifiedRolloutOrigin):
            raise ValueError("registered pump rollout origin context differs")
        return origin.task_context


def _remaining_schedule_sha256(
    state: PumpStationCoupledStewardshipState,
) -> str:
    remaining = tuple(
        requirement
        for requirement in state.service_schedule
        if requirement.end_calendar_seconds > state.calendar_seconds
    )
    return stewardship_content_id(
        (
            state.calendar_seconds,
            remaining,
            tuple((pool.pool_id, getattr(pool, "availability", ())) for pool in state.resources.pools),
        ),
        record_profile="v4",
    )


def _pump_snapshot(
    snapshot: ContinualWorldSnapshotRef,
    *,
    snapshot_version: str,
) -> PumpStationStateSnapshotRef:
    return PumpStationStateSnapshotRef(
        snapshot_version=snapshot_version,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _shared_snapshot(
    snapshot: PumpStationStateSnapshotRef,
) -> ContinualWorldSnapshotRef:
    return ContinualWorldSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _initial_snapshot(
    repository: PumpStationWorldRunRepository,
    manifest: PumpStationWorldRunManifestV2,
) -> PumpStationStateSnapshotRef:
    first = repository.commits()[0]
    return PumpStationStateSnapshotRef(
        snapshot_version=manifest.snapshot_version,
        run_id=manifest.run_id,
        episode_id=manifest.episode_id,
        world_branch_id=manifest.world_branch_id,
        sequence=first.sequence,
        state_id=first.state_id,
        commit_id=pump_station_artifact_id(first),
    )


def _task_store(
    child_run_root: Path,
    *,
    parent_run_root: Path,
) -> ImmutableByteStore:
    return ImmutableByteStore(
        child_run_root,
        disjoint_roots=(Path(parent_run_root),),
        host_private=True,
    )


__all__ = ["PumpStationContinualWorldBranchPort"]
