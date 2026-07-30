# ABOUTME: Coordinates deterministic pump-station transitions with durable publication.
# ABOUTME: Provides create, apply, stage, snapshot, resume, and replay over one repository.

from __future__ import annotations

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
    PUMP_STATION_AUTHORITY_POLICY_VERSION,
    PUMP_STATION_RECEIPT_VERSION,
    PUMP_STATION_TRANSITION_RULE_VERSION,
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
    PUMP_STATION_SERIALIZATION_VERSION,
    PUMP_STATION_SNAPSHOT_VERSION,
    PumpStationStagedTransition,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunError,
    PumpStationWorldRunManifest,
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
    ) -> PumpStationWorldRun:
        """Create and atomically select one durable initial state."""
        manifest = PumpStationWorldRunManifest(
            serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
            snapshot_version=PUMP_STATION_SNAPSHOT_VERSION,
            receipt_version=PUMP_STATION_RECEIPT_VERSION,
            authority_policy_version=PUMP_STATION_AUTHORITY_POLICY_VERSION,
            transition_rule_version=PUMP_STATION_TRANSITION_RULE_VERSION,
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
