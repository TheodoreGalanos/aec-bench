# ABOUTME: Coordinates deterministic pump-station transitions with durable publication.
# ABOUTME: Provides create, apply, stage, snapshot, resume, and replay over one repository.

from __future__ import annotations

from dataclasses import replace

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
    stewardship_state_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_STATE_VERSION_V1,
    PUMP_STATION_STATE_VERSION_V2,
    PumpStationProposal,
    PumpStationStewardshipState,
    PumpStationTransition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    apply_stewardship_proposal,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationRunStep,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_MIGRATION_VERSION,
    PUMP_STATION_RECORD_VERSIONS_V1,
    PUMP_STATION_RECORD_VERSIONS_V2,
    PUMP_STATION_SERIALIZATION_VERSION,
    PumpStationRecordVersions,
    PumpStationStagedTransition,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunError,
    PumpStationWorldRunManifest,
    PumpStationWorldRunMigration,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _fail(code: str, detail: str) -> None:
    raise PumpStationWorldRunError(code, detail)


class PumpStationWorldRun:
    """One continuing pump-station branch backed by immutable filesystem evidence."""

    def __init__(
        self,
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        model: PumpStationModel,
        manifest: PumpStationWorldRunManifest,
    ) -> None:
        self._repository = repository
        self._package = package
        self._model = model
        self._manifest = manifest

    @classmethod
    def create(
        cls,
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        model: PumpStationModel,
        initial_state: PumpStationStewardshipState,
        run_id: str,
        episode_id: str,
        world_branch_id: str,
        record_versions: PumpStationRecordVersions = PUMP_STATION_RECORD_VERSIONS_V1,
    ) -> PumpStationWorldRun:
        """Create and atomically select one durable initial state."""
        expected_state_version = (
            PUMP_STATION_STATE_VERSION_V2
            if record_versions == PUMP_STATION_RECORD_VERSIONS_V2
            else PUMP_STATION_STATE_VERSION_V1
        )
        if initial_state.state_version != expected_state_version:
            _fail(
                "state-version",
                "initial state and durable record versions differ",
            )
        manifest = PumpStationWorldRunManifest(
            serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
            snapshot_version=record_versions.snapshot_version,
            receipt_version=record_versions.receipt_version,
            authority_policy_version=record_versions.authority_policy_version,
            transition_rule_version=record_versions.transition_rule_version,
            run_id=run_id,
            episode_id=episode_id,
            world_branch_id=world_branch_id,
            profile_id=package.profile_id,
            generation_id=package.generation_id,
            package_content_id=package.package_content_id,
            manifest_content_id=package.manifest_content_id,
            asset_id=model.asset_id,
            model_id=stewardship_content_id(model),
            initial_sequence=initial_state.sequence,
            initial_state_id=stewardship_state_id(initial_state),
        )
        repository.initialize(manifest, initial_state)
        return cls(
            repository=repository,
            package=package,
            model=model,
            manifest=manifest,
        )

    def migrate_to_v2(
        self,
        *,
        repository: PumpStationWorldRunRepository,
        run_id: str,
        world_branch_id: str,
    ) -> PumpStationWorldRun:
        """Continue one version-1 state as a new version-2 run with lineage."""
        if self._manifest.record_versions != PUMP_STATION_RECORD_VERSIONS_V1:
            _fail("migration-source-version", str(self._manifest.record_versions))
        source_snapshot = self.snapshot()
        migrated_state = replace(
            self.state,
            state_version=PUMP_STATION_STATE_VERSION_V2,
            dependencies=(),
            dependency_waivers=(),
            resource_reservations=(),
        )
        migrated = PumpStationWorldRun.create(
            repository=repository,
            package=self._package,
            model=self._model,
            initial_state=migrated_state,
            run_id=run_id,
            episode_id=self._manifest.episode_id,
            world_branch_id=world_branch_id,
            record_versions=PUMP_STATION_RECORD_VERSIONS_V2,
        )
        target_snapshot = migrated.snapshot()
        repository.publish_migration(
            PumpStationWorldRunMigration(
                migration_version=PUMP_STATION_MIGRATION_VERSION,
                source_run_id=self._manifest.run_id,
                source_world_branch_id=self._manifest.world_branch_id,
                source_state_id=source_snapshot.state_id,
                source_snapshot_version=self._manifest.snapshot_version,
                source_receipt_version=self._manifest.receipt_version,
                source_authority_policy_version=(self._manifest.authority_policy_version),
                source_transition_rule_version=(self._manifest.transition_rule_version),
                target_run_id=migrated.manifest.run_id,
                target_world_branch_id=migrated.manifest.world_branch_id,
                target_state_id=target_snapshot.state_id,
                target_snapshot_version=migrated.manifest.snapshot_version,
                target_receipt_version=migrated.manifest.receipt_version,
                target_authority_policy_version=(migrated.manifest.authority_policy_version),
                target_transition_rule_version=(migrated.manifest.transition_rule_version),
            )
        )
        return migrated

    @classmethod
    def resume(
        cls,
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        model: PumpStationModel,
        snapshot: PumpStationStateSnapshotRef,
    ) -> PumpStationWorldRun:
        """Resume only the exact state currently selected by the repository."""
        manifest = repository.load_manifest()
        cls._validate_identity(manifest, package=package, model=model)
        current = repository.current_snapshot()
        if current != snapshot:
            _fail("snapshot-drift", "requested snapshot is not the selected world state")
        return cls(
            repository=repository,
            package=package,
            model=model,
            manifest=manifest,
        )

    @property
    def repository(self) -> PumpStationWorldRunRepository:
        """Return the host-supplied repository."""
        return self._repository

    @property
    def package(self) -> ReferencePackage:
        """Return the validated reference package bound to this run."""
        return self._package

    @property
    def model(self) -> PumpStationModel:
        """Return the physical model bound to this run."""
        return self._model

    @property
    def manifest(self) -> PumpStationWorldRunManifest:
        """Return the immutable run identity."""
        return self._manifest

    @property
    def state(self) -> PumpStationStewardshipState:
        """Reload the current complete state through the repository."""
        snapshot = self._repository.current_snapshot()
        return self._repository.load_state(snapshot.state_id)

    def snapshot(self) -> PumpStationStateSnapshotRef:
        """Return the exact currently selected dynamic state."""
        return self._repository.current_snapshot()

    def stage(
        self,
        proposal: PumpStationProposal,
        *,
        information_set: PumpStationInformationSet,
    ) -> PumpStationStagedTransition:
        """Write immutable transition evidence without selecting its state."""
        with self._repository.locked():
            prior = self._repository.current_snapshot()
            committed = self._repository.find_committed_proposal(
                proposal.context.proposal_id,
            )
            if committed is not None:
                _fail(
                    "proposal-already-committed",
                    proposal.context.proposal_id,
                )
            state = self._repository.load_state(prior.state_id)
            transition = apply_stewardship_proposal(
                self._model,
                state,
                proposal,
                information_set=information_set,
            )
            return self._repository.stage_transition(
                manifest=self._manifest,
                prior_snapshot=prior,
                proposal=proposal,
                information_set=information_set,
                transition=transition,
            )

    def apply(
        self,
        proposal: PumpStationProposal,
        *,
        information_set: PumpStationInformationSet,
    ) -> PumpStationTransition:
        """Apply or idempotently replay one exact bound proposal."""
        with self._repository.locked():
            prior = self._repository.current_snapshot()
            committed = self._repository.find_committed_proposal(
                proposal.context.proposal_id,
            )
            if committed is not None:
                return self._repository.validate_repeated_proposal(
                    committed,
                    proposal,
                    information_set,
                )
            state = self._repository.load_state(prior.state_id)
            transition = apply_stewardship_proposal(
                self._model,
                state,
                proposal,
                information_set=information_set,
            )
            staged = self._repository.stage_transition(
                manifest=self._manifest,
                prior_snapshot=prior,
                proposal=proposal,
                information_set=information_set,
                transition=transition,
            )
            return self._repository.publish_staged_transition(staged)

    def steps(self) -> tuple[PumpStationRunStep, ...]:
        """Reload all selected run steps for independent replay."""
        return self._repository.steps()

    @staticmethod
    def _validate_identity(
        manifest: PumpStationWorldRunManifest,
        *,
        package: ReferencePackage,
        model: PumpStationModel,
    ) -> None:
        if manifest.serialization_version != PUMP_STATION_SERIALIZATION_VERSION:
            _fail("serialization-version", manifest.serialization_version)
        expected = (
            package.profile_id,
            package.generation_id,
            package.package_content_id,
            package.manifest_content_id,
            model.asset_id,
            stewardship_content_id(model),
        )
        observed = (
            manifest.profile_id,
            manifest.generation_id,
            manifest.package_content_id,
            manifest.manifest_content_id,
            manifest.asset_id,
            manifest.model_id,
        )
        if observed != expected:
            _fail("world-run-identity", "package or physical model differs")
