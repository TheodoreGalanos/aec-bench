# ABOUTME: Owns the current registered pump-station durable run and replay boundary.
# ABOUTME: Provides one create, resume, host-control, snapshot, and verification path.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, NoReturn

from aec_bench.contracts.continual_world import (
    ContinualWorldProfileRef,
    WorldBuildRef,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCoupledWorldError,
    apply_control,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    PumpStationEventSchedule,
    PumpStationReferenceSystem,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
    stewardship_state_id,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationActionError,
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledTransition,
    PumpStationCoupledTreatmentRequest,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
    PumpStationStewardshipState,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationCoupledVerificationReport,
    derive_pump_station_conservation_report,
    verify_coupled_stewardship_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationCommand,
    PumpStationInitialStateSource,
    PumpStationRegisteredWorldRunManifest,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunError,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

if TYPE_CHECKING:
    from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
        PumpStationContinualProfile,
    )
    from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.models import (
        TemporalEvidenceBundle,
    )


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationWorldRunError(code, detail)


class PumpStationWorldRun:
    """One current registered branch backed by immutable filesystem evidence."""

    def __init__(
        self,
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        model: PumpStationCoupledModel,
        reference_system: PumpStationReferenceSystem,
        manifest: PumpStationRegisteredWorldRunManifest,
    ) -> None:
        self._repository = repository
        self._package = package
        self._model = model
        self._reference_system = reference_system
        self._manifest = manifest

    @classmethod
    def create_reference_system(
        cls,
        *,
        repository: PumpStationWorldRunRepository,
        run_id: str,
        episode_id: str,
        world_branch_id: str,
        reference_system_id: str = PUMP_STATION_REFERENCE_SYSTEM_ID,
    ) -> PumpStationWorldRun:
        """Create one registered root and its required temporal evidence."""
        world_build, profile_ref, profile = cls._load_registered_reference_profile(reference_system_id)
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
            build_pump_station_temporal_evidence_bundle,
        )

        bundle = build_pump_station_temporal_evidence_bundle(
            profile.station_package,
            profile.reference_system,
            world_branch_id=world_branch_id,
        )
        manifest = cls._reference_system_manifest(
            world_build=world_build,
            profile_ref=profile_ref,
            profile=profile,
            bundle=bundle,
            run_id=run_id,
            episode_id=episode_id,
            world_branch_id=world_branch_id,
        )

        def initialize_temporal_evidence() -> None:
            cls._initialize_reference_temporal_evidence(
                repository=repository,
                package=profile.station_package,
                bundle=bundle,
            )

        repository.initialize(
            manifest,
            profile.opening_state,
            before_select=initialize_temporal_evidence,
        )
        cls._verify_reference_temporal_evidence(
            repository=repository,
            package=profile.station_package,
            manifest=manifest,
            expected=bundle,
        )
        return cls(
            repository=repository,
            package=profile.station_package,
            model=profile.model,
            reference_system=profile.reference_system,
            manifest=manifest,
        )

    @classmethod
    def resume_reference_system(
        cls,
        *,
        repository: PumpStationWorldRunRepository,
        snapshot: PumpStationStateSnapshotRef,
    ) -> PumpStationWorldRun:
        """Resume the selected registered run after identity and replay validation."""
        manifest, profile, bundle = cls._load_reference_system_identity(
            repository=repository,
            snapshot=snapshot,
        )
        cls._verify_reference_temporal_evidence(
            repository=repository,
            package=profile.station_package,
            manifest=manifest,
            expected=bundle,
        )
        return cls(
            repository=repository,
            package=profile.station_package,
            model=profile.model,
            reference_system=profile.reference_system,
            manifest=manifest,
        )

    @classmethod
    def _resume_reference_system_at_snapshot(
        cls,
        *,
        repository: PumpStationWorldRunRepository,
        snapshot: PumpStationStateSnapshotRef,
    ) -> PumpStationWorldRun:
        """Open one selected prefix for rollout-origin verification."""
        manifest, profile, bundle = cls._load_reference_system_identity(
            repository=repository,
            snapshot=snapshot,
        )
        cls._verify_reference_temporal_evidence_identity(
            repository=repository,
            package=profile.station_package,
            manifest=manifest,
            expected=bundle,
        )
        return cls(
            repository=repository,
            package=profile.station_package,
            model=profile.model,
            reference_system=profile.reference_system,
            manifest=manifest,
        )

    @classmethod
    def _load_reference_system_identity(
        cls,
        *,
        repository: PumpStationWorldRunRepository,
        snapshot: PumpStationStateSnapshotRef,
    ) -> tuple[
        PumpStationRegisteredWorldRunManifest,
        PumpStationContinualProfile,
        TemporalEvidenceBundle,
    ]:
        """Load immutable registered identity without checking mutable history."""
        manifest = repository.load_manifest()
        world_build = cls._world_build(manifest)
        profile_ref = cls._profile_ref(manifest)
        from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
            PumpStationContinualProfile,
            pump_station_continual_world_definition,
        )
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
            build_pump_station_temporal_evidence_bundle,
        )
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.repository import (
            TemporalEvidenceRepository,
        )

        try:
            definition = pump_station_continual_world_definition()
            if definition.build != world_build:
                raise ValueError(f"world build does not match: {world_build.task_world_id}")
            loaded = definition.load_profile(profile_ref)
        except (KeyError, ValueError) as error:
            _fail("world-run-identity", f"registered profile differs: {error}")
        if not isinstance(loaded.value, PumpStationContinualProfile):
            _fail("world-run-identity", "registered profile has another task-owned value")
        profile = loaded.value
        if manifest.initial_state_source.kind == "reference_system_specification":
            bundle = build_pump_station_temporal_evidence_bundle(
                profile.station_package,
                profile.reference_system,
                world_branch_id=manifest.world_branch_id,
            )
        else:
            bundle = TemporalEvidenceRepository(
                repository.root / "temporal-evidence",
            ).load_bundle(package=profile.station_package)
        expected_manifest = cls._reference_system_manifest(
            world_build=world_build,
            profile_ref=profile_ref,
            profile=profile,
            bundle=bundle,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
        )
        if manifest.initial_state_source.kind == "rollout_parent_snapshot":
            source = manifest.initial_state_source
            if (
                source.parent_state_id != manifest.initial_state_id
                or source.parent_branch_id != source.ancestor_branch_ids[-1]
                or manifest.world_branch_id in source.ancestor_branch_ids
            ):
                _fail("world-run-identity", "registered rollout-child provenance differs")
            expected_manifest = replace(
                expected_manifest,
                initial_sequence=manifest.initial_sequence,
                initial_state_id=manifest.initial_state_id,
                initial_state_source=source,
            )
        if manifest != expected_manifest:
            _fail("world-run-identity", "registered reference-system manifest differs")
        if repository.current_snapshot() != snapshot:
            _fail("snapshot-drift", "requested snapshot is not the selected world state")
        return manifest, profile, bundle

    @property
    def repository(self) -> PumpStationWorldRunRepository:
        return self._repository

    @property
    def package(self) -> ReferencePackage:
        return self._package

    @property
    def model(self) -> PumpStationCoupledModel:
        return self._model

    @property
    def reference_system(self) -> PumpStationReferenceSystem:
        return self._reference_system

    @property
    def event_schedule(self) -> PumpStationEventSchedule:
        return self._reference_system.event_schedule

    @property
    def manifest(self) -> PumpStationRegisteredWorldRunManifest:
        return self._manifest

    @property
    def world_build(self) -> WorldBuildRef:
        return self._world_build(self._manifest)

    @property
    def continual_profile_ref(self) -> ContinualWorldProfileRef:
        return self._profile_ref(self._manifest)

    @property
    def state(self) -> PumpStationStewardshipState:
        snapshot = self._repository.current_snapshot()
        return self._repository.load_state(snapshot.state_id)

    def snapshot(self) -> PumpStationStateSnapshotRef:
        return self._repository.current_snapshot()

    def apply_control(
        self,
        request: PumpStationBoundControlRequest,
    ) -> PumpStationCoupledTransition:
        """Apply or exactly recover one bound root host-control request."""
        if (
            isinstance(request.control, PumpStationCoupledTreatmentRequest)
            and self._manifest.initial_state_source.kind != "rollout_parent_snapshot"
        ):
            _fail("control-wrong-profile", "coupled treatment requires a registered rollout child")
        command = self._control_command(request)
        with self._repository.locked():
            committed = self._repository.find_committed_command(request.request_id)
            if committed is not None:
                return self._repository.validate_repeated_command(committed, command)
            recovered = self._repository._recover_staged_command_under_lock(command)
            if recovered is not None:
                return recovered
            prior = self._repository.current_snapshot()
            observed = (
                request.run_id,
                request.episode_id,
                request.world_branch_id,
                request.based_on_sequence,
                request.base_state_id,
                request.base_commit_id,
            )
            expected = (
                self._manifest.run_id,
                self._manifest.episode_id,
                self._manifest.world_branch_id,
                prior.sequence,
                prior.state_id,
                prior.commit_id,
            )
            if observed != expected:
                _fail("control-request-scope", "registered control does not bind the selected snapshot")
            state = self._repository.load_state(prior.state_id)
            try:
                transition = apply_control(state, request.control, sequence=request.based_on_sequence + 1)
            except (PumpStationActionError, PumpStationCoupledWorldError) as error:
                _fail(error.code, str(error))
            staged = self._repository.stage_command_transition(
                manifest=self._manifest,
                prior_snapshot=prior,
                command=command,
                transition=transition,
            )
            return self._repository._publish_staged_command_under_lock(staged)

    def verify(
        self,
        snapshot: PumpStationStateSnapshotRef | None = None,
    ) -> PumpStationCoupledVerificationReport:
        """Independently replay the selected history or one exact prefix."""
        with self._repository.locked():
            return self._verify_under_lock(snapshot)

    def _verify_under_lock(
        self,
        snapshot: PumpStationStateSnapshotRef | None = None,
    ) -> PumpStationCoupledVerificationReport:
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence import (
            TemporalEvidenceRepository,
            verify_temporal_evidence_repository,
        )

        initial_state = self._repository.load_state(self._manifest.initial_state_id)
        try:
            selected_snapshot = snapshot or self._repository.current_snapshot()
            steps = (
                self._repository.command_steps_through(selected_snapshot)
                if snapshot is not None
                else self._repository.command_steps()
            )
        except (OSError, PumpStationWorldRunError, TypeError, ValueError) as error:
            return PumpStationCoupledVerificationReport(
                valid=False,
                replay_valid=False,
                actor_actions_valid=False,
                host_controls_valid=False,
                issues=(f"repository-invalid:{error}",),
                replayed_transition_ids=(),
                final_state_id=stewardship_state_id(initial_state),
                conservation=derive_pump_station_conservation_report(initial_state, initial_state),
            )
        replay = verify_coupled_stewardship_run(
            self._model,
            self.event_schedule,
            initial_state,
            steps,
            expected_final_state_id=selected_snapshot.state_id,
            expected_task_world_id=self._manifest.task_world_id,
            expected_run_id=self._manifest.run_id,
            expected_episode_id=self._manifest.episode_id,
            expected_world_branch_id=self._manifest.world_branch_id,
            expected_actor_id="pump-station-actor",
            initial_sequence=self._manifest.initial_sequence,
            expected_source_artifact_ids=(
                self._manifest.reference_system_content_id,
                self._manifest.package_content_id,
                self._manifest.temporal_bundle_content_id,
            ),
        )
        actor_bindings = {
            step.command.request_id: (
                step.command.information_set_id or "",
                step.command.actor_view_id or "",
            )
            for step in steps
            if step.command.kind == "actor"
        }
        temporal_report = verify_temporal_evidence_repository(
            TemporalEvidenceRepository(self._repository.root / "temporal-evidence"),
            package=self._package,
            actor_bindings=actor_bindings,
        )
        temporal_issues = tuple(
            f"temporal-evidence-invalid:{issue.code}:{issue.artifact_id or '-'}" for issue in temporal_report.issues
        )
        issues = (*temporal_issues, *replay.issues)
        return replace(replay, valid=not issues and replay.valid, issues=issues)

    @staticmethod
    def _load_registered_reference_profile(
        reference_system_id: str,
    ) -> tuple[
        WorldBuildRef,
        ContinualWorldProfileRef,
        PumpStationContinualProfile,
    ]:
        from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
            PumpStationContinualProfile,
            pump_station_continual_world_definition,
        )
        from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
            PUMP_STATION_TASK_WORLD_ID,
        )

        try:
            definition = pump_station_continual_world_definition()
            if definition.build.task_world_id != PUMP_STATION_TASK_WORLD_ID:
                raise ValueError("registered pump definition has another task-world identity")
            profile_ref = definition.profile_ref(reference_system_id)
            loaded = definition.load_profile(profile_ref)
        except (KeyError, ValueError) as error:
            _fail("world-run-identity", f"registered profile differs: {error}")
        if not isinstance(loaded.value, PumpStationContinualProfile):
            _fail("world-run-identity", "registered pump profile has another value")
        return definition.ref, profile_ref, loaded.value

    @staticmethod
    def _reference_system_manifest(
        *,
        world_build: WorldBuildRef,
        profile_ref: ContinualWorldProfileRef,
        profile: PumpStationContinualProfile,
        bundle: TemporalEvidenceBundle,
        run_id: str,
        episode_id: str,
        world_branch_id: str,
    ) -> PumpStationRegisteredWorldRunManifest:
        system = profile.reference_system
        package = profile.station_package
        model = profile.model
        opening_id, opening_sha256 = PumpStationWorldRun._descriptor_binding(system.descriptor, "opening_state")
        event_schedule_id, event_schedule_sha256 = PumpStationWorldRun._descriptor_binding(
            system.descriptor,
            "event_schedule",
        )
        temporal_template_id, temporal_template_sha256 = PumpStationWorldRun._descriptor_binding(
            system.descriptor,
            "temporal_template",
        )
        return PumpStationRegisteredWorldRunManifest(
            run_id=run_id,
            episode_id=episode_id,
            world_branch_id=world_branch_id,
            profile_id=package.profile_id,
            generation_id=package.generation_id,
            package_content_id=package.package_content_id,
            manifest_content_id=package.manifest_content_id,
            asset_id=model.asset_id,
            model_id=stewardship_content_id(model),
            initial_sequence=0,
            initial_state_id=stewardship_state_id(profile.opening_state),
            task_world_id=world_build.task_world_id,
            world_build_entry_point=world_build.entry_point,
            world_build_artifact_sha256=world_build.artifact_sha256,
            continual_profile_id=profile_ref.profile_id,
            continual_profile_content_sha256=profile_ref.profile_content_sha256,
            reference_system_id=system.descriptor_id,
            reference_system_content_id=system.descriptor_content_id,
            opening_state_specification_id=opening_id,
            opening_state_specification_sha256=opening_sha256,
            event_schedule_id=event_schedule_id,
            event_schedule_sha256=event_schedule_sha256,
            temporal_template_id=temporal_template_id,
            temporal_template_sha256=temporal_template_sha256,
            temporal_bundle_content_id=bundle.content_sha256,
            temporal_corpus_content_id=bundle.corpus_manifest.content_sha256,
            temporal_capability_content_id=bundle.capability.content_sha256,
            initial_state_source=PumpStationInitialStateSource(
                kind="reference_system_specification",
                opening_specification_id=opening_id,
                opening_specification_sha256=opening_sha256,
            ),
        )

    @staticmethod
    def _descriptor_binding(descriptor: Mapping[str, object], name: str) -> tuple[str, str]:
        value = descriptor.get(name)
        if not isinstance(value, Mapping):
            _fail("world-run-identity", f"descriptor lacks {name}")
        identity = value.get("id")
        content_sha256 = value.get("content_sha256")
        if not isinstance(identity, str) or not identity.strip():
            _fail("world-run-identity", f"descriptor {name} identity differs")
        if not isinstance(content_sha256, str) or not content_sha256.strip():
            _fail("world-run-identity", f"descriptor {name} content differs")
        return identity, content_sha256

    @staticmethod
    def _initialize_reference_temporal_evidence(
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        bundle: TemporalEvidenceBundle,
    ) -> None:
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.models import (
            TemporalEvidenceIntegrityError,
        )
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.repository import (
            TemporalEvidenceRepository,
        )
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.verification import (
            verify_temporal_evidence_repository,
        )

        temporal_repository = TemporalEvidenceRepository(repository.root / "temporal-evidence")
        try:
            loaded = temporal_repository.initialize(bundle, package=package)
            report = verify_temporal_evidence_repository(temporal_repository, package=package)
        except (OSError, ValueError, TemporalEvidenceIntegrityError) as error:
            _fail("temporal-evidence", f"registered temporal initialization failed: {error}")
        if loaded != bundle or not report.valid:
            _fail("temporal-evidence", "registered temporal initialization differs")

    @staticmethod
    def _verify_reference_temporal_evidence(
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        manifest: PumpStationRegisteredWorldRunManifest,
        expected: TemporalEvidenceBundle,
    ) -> None:
        PumpStationWorldRun._verify_reference_temporal_evidence_identity(
            repository=repository,
            package=package,
            manifest=manifest,
            expected=expected,
        )
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.models import (
            TemporalEvidenceIntegrityError,
        )
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.repository import (
            TemporalEvidenceRepository,
        )
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.verification import (
            verify_temporal_evidence_repository,
        )

        temporal_repository = TemporalEvidenceRepository(repository.root / "temporal-evidence")
        try:
            steps = repository.command_steps()
            actor_bindings = {
                step.command.request_id: (
                    step.command.information_set_id or "",
                    step.command.actor_view_id or "",
                )
                for step in steps
                if step.command.kind == "actor"
            }
            report = verify_temporal_evidence_repository(
                temporal_repository,
                package=package,
                actor_bindings=actor_bindings,
            )
        except (OSError, ValueError, PumpStationWorldRunError, TemporalEvidenceIntegrityError) as error:
            _fail("temporal-evidence", f"registered temporal evidence is invalid: {error}")
        if not report.valid:
            _fail("temporal-evidence", "registered temporal evidence differs")

    @staticmethod
    def _verify_reference_temporal_evidence_identity(
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        manifest: PumpStationRegisteredWorldRunManifest,
        expected: TemporalEvidenceBundle,
    ) -> None:
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.models import (
            TemporalEvidenceIntegrityError,
        )
        from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.repository import (
            TemporalEvidenceRepository,
        )

        try:
            loaded = TemporalEvidenceRepository(
                repository.root / "temporal-evidence",
            ).load_bundle(package=package)
        except (OSError, ValueError, TemporalEvidenceIntegrityError) as error:
            _fail("temporal-evidence", f"registered temporal evidence is invalid: {error}")
        observed = (
            loaded.content_sha256,
            loaded.corpus_manifest.content_sha256,
            loaded.capability.content_sha256,
        )
        bound = (
            manifest.temporal_bundle_content_id,
            manifest.temporal_corpus_content_id,
            manifest.temporal_capability_content_id,
        )
        if loaded != expected or observed != bound:
            _fail("temporal-evidence", "registered temporal evidence differs from the manifest")

    @staticmethod
    def _world_build(manifest: PumpStationRegisteredWorldRunManifest) -> WorldBuildRef:
        try:
            return WorldBuildRef(
                task_world_id=manifest.task_world_id,
                entry_point=manifest.world_build_entry_point,
                artifact_sha256=manifest.world_build_artifact_sha256,
            )
        except ValueError as error:
            _fail("world-run-identity", f"definition reference differs: {error}")

    @staticmethod
    def _profile_ref(manifest: PumpStationRegisteredWorldRunManifest) -> ContinualWorldProfileRef:
        try:
            return ContinualWorldProfileRef(
                task_world_id=manifest.task_world_id,
                profile_id=manifest.continual_profile_id,
                profile_content_sha256=manifest.continual_profile_content_sha256,
            )
        except ValueError as error:
            _fail("world-run-identity", f"profile reference differs: {error}")

    def _control_command(self, request: PumpStationBoundControlRequest) -> PumpStationCommand:
        control = request.control
        if isinstance(control, PumpStationOperationsBoundaryReviewRequest):
            kind = "operations_review"
        elif isinstance(control, PumpStationProcessOutcomeRequest):
            kind = "process_outcome"
        elif isinstance(control, PumpStationCommonBoundaryRequest):
            kind = "common_boundary"
        elif isinstance(control, PumpStationCoupledTreatmentRequest):
            kind = "coupled_treatment"
        else:
            _fail("control-type", f"unsupported registered control {type(control).__name__}")
        return PumpStationCommand(
            kind=kind,
            request_id=request.request_id,
            request_content_id=control.content_id,
            action=None,
            control=control,
            task_world_id=self._manifest.task_world_id,
            run_id=request.run_id,
            episode_id=request.episode_id,
            world_branch_id=request.world_branch_id,
            based_on_sequence=request.based_on_sequence,
            base_state_id=request.base_state_id,
            base_commit_id=request.base_commit_id,
            authority_id=request.authority_id,
        )


__all__ = ["PumpStationWorldRun"]
