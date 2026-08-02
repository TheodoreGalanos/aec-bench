# ABOUTME: Coordinates deterministic pump-station transitions with durable publication.
# ABOUTME: Provides create, apply, stage, snapshot, resume, and replay over one repository.

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Generic, NoReturn, TypeVar, cast

from pydantic import JsonValue

from aec_bench.contracts.continual_world import (
    ContinualWorldDefinitionRef,
    ContinualWorldProfileRef,
)
from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorBinding,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID_V2,
    pump_station_proposal_from_validated_arguments_v2,
    validate_pump_station_actor_arguments_v2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCoupledWorldError,
    project_coupled_information_set,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
    PumpStationModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PumpStationPhysicalTreatmentActivationRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
    stewardship_content_id,
    stewardship_state_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_STATE_VERSION_V1,
    PUMP_STATION_STATE_VERSION_V2,
    PUMP_STATION_STATE_VERSION_V3,
    ProposalContext,
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledStewardshipState,
    PumpStationLegacyStewardshipState,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
    PumpStationProposal,
    PumpStationProposalError,
    PumpStationTransition,
    PumpStationTransitionV4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    apply_evidence_treatment_schedule,
    apply_physical_treatment_activation,
    apply_stewardship_control_v4,
    apply_stewardship_proposal,
    apply_stewardship_proposal_v4,
    materialize_evidence_health_state,
    validate_legacy_proposal_profile,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationRunStep,
    PumpStationVerificationReportV4,
    verify_stewardship_run_v4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_COMMAND_VERSION_V4,
    PUMP_STATION_MIGRATION_VERSION,
    PUMP_STATION_RECORD_VERSIONS_V1,
    PUMP_STATION_RECORD_VERSIONS_V2,
    PUMP_STATION_RECORD_VERSIONS_V3,
    PUMP_STATION_RECORD_VERSIONS_V4,
    PUMP_STATION_SERIALIZATION_VERSION,
    PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
    PumpStationCommandV4,
    PumpStationInitialStateSource,
    PumpStationRecordVersions,
    PumpStationStagedTransition,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunError,
    PumpStationWorldRunManifest,
    PumpStationWorldRunManifestRecord,
    PumpStationWorldRunManifestV2,
    PumpStationWorldRunMigration,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

if TYPE_CHECKING:
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
        PumpStationContinualProfile,
    )
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.models import (
        TemporalEvidenceBundle,
    )

_RunModelT = TypeVar(
    "_RunModelT",
    PumpStationModel,
    PumpStationCoupledModel,
    default=PumpStationModel,
)
_RunStateT = TypeVar(
    "_RunStateT",
    PumpStationLegacyStewardshipState,
    PumpStationCoupledStewardshipState,
    default=PumpStationLegacyStewardshipState,
)


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationWorldRunError(code, detail)


class PumpStationWorldRun(Generic[_RunModelT, _RunStateT]):
    """One continuing pump-station branch backed by immutable filesystem evidence."""

    def __init__(
        self,
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        model: _RunModelT,
        manifest: PumpStationWorldRunManifestRecord,
    ) -> None:
        if isinstance(manifest, PumpStationWorldRunManifestV2):
            if not isinstance(model, PumpStationCoupledModel):
                _fail("world-run-identity", "manifest v2 requires the coupled model")
        elif not isinstance(model, PumpStationModel):
            _fail("world-run-identity", "manifest v1 requires the two-pump model")
        self._repository = repository
        self._package = package
        self._model: _RunModelT = model
        self._manifest: PumpStationWorldRunManifestRecord = manifest

    @classmethod
    def create(
        cls,
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        model: PumpStationModel,
        initial_state: PumpStationLegacyStewardshipState,
        run_id: str,
        episode_id: str,
        world_branch_id: str,
        record_versions: PumpStationRecordVersions = PUMP_STATION_RECORD_VERSIONS_V1,
    ) -> PumpStationWorldRun[PumpStationModel, PumpStationLegacyStewardshipState]:
        """Create and atomically select one durable initial state."""
        expected_state_version = {
            PUMP_STATION_RECORD_VERSIONS_V1: PUMP_STATION_STATE_VERSION_V1,
            PUMP_STATION_RECORD_VERSIONS_V2: PUMP_STATION_STATE_VERSION_V2,
            PUMP_STATION_RECORD_VERSIONS_V3: PUMP_STATION_STATE_VERSION_V3,
        }.get(record_versions)
        if expected_state_version is None:
            _fail("record-versions", str(record_versions))
        if not isinstance(model, PumpStationModel):
            _fail("world-run-identity", "free-form creation requires the two-pump model")
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
        return PumpStationWorldRun[PumpStationModel, PumpStationLegacyStewardshipState](
            repository=repository,
            package=package,
            model=model,
            manifest=manifest,
        )

    @classmethod
    def create_reference_system(
        cls,
        *,
        repository: PumpStationWorldRunRepository,
        run_id: str,
        episode_id: str,
        world_branch_id: str,
    ) -> PumpStationWorldRun[PumpStationCoupledModel, PumpStationCoupledStewardshipState]:
        """Create one registered RS1 root through the existing durable run."""
        definition_ref, profile_ref, profile = cls._load_registered_reference_profile()
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
            build_asw_8_reference_temporal_evidence_bundle,
        )

        bundle = build_asw_8_reference_temporal_evidence_bundle(
            profile.station_package,
            world_branch_id=world_branch_id,
        )
        manifest = cls._reference_system_manifest(
            definition_ref=definition_ref,
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
        return PumpStationWorldRun[PumpStationCoupledModel, PumpStationCoupledStewardshipState](
            repository=repository,
            package=profile.station_package,
            model=profile.model,
            manifest=manifest,
        )

    @classmethod
    def resume_reference_system(
        cls,
        *,
        repository: PumpStationWorldRunRepository,
        snapshot: PumpStationStateSnapshotRef,
    ) -> PumpStationWorldRun[PumpStationCoupledModel, PumpStationCoupledStewardshipState]:
        """Resume one manifest-bound RS1 run without caller-supplied profile data."""
        manifest = repository.load_manifest()
        if not isinstance(manifest, PumpStationWorldRunManifestV2):
            _fail(
                "reference-system-manifest-required",
                "registered profile resume requires manifest v2",
            )
        definition_ref = cls._definition_ref(manifest)
        profile_ref = cls._profile_ref(manifest)
        from aec_bench.task_world_templates.continual_catalogue import (
            default_continual_world_catalogue,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
            PumpStationContinualProfile,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
            build_asw_8_reference_temporal_evidence_bundle,
        )

        try:
            definition = default_continual_world_catalogue().resolve(definition_ref)
            loaded = definition.load_profile(profile_ref)
        except (KeyError, ValueError) as error:
            _fail("world-run-identity", f"registered profile differs: {error}")
        if not isinstance(loaded.value, PumpStationContinualProfile):
            _fail("world-run-identity", "registered profile has another task-owned value")
        profile = loaded.value
        bundle = build_asw_8_reference_temporal_evidence_bundle(
            profile.station_package,
            world_branch_id=manifest.world_branch_id,
        )
        expected_manifest = cls._reference_system_manifest(
            definition_ref=definition_ref,
            profile_ref=profile_ref,
            profile=profile,
            bundle=bundle,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
        )
        if manifest != expected_manifest:
            _fail("world-run-identity", "registered reference-system manifest differs")
        cls._verify_reference_temporal_evidence(
            repository=repository,
            package=profile.station_package,
            manifest=manifest,
            expected=bundle,
        )
        current = repository.current_snapshot()
        if current != snapshot:
            _fail("snapshot-drift", "requested snapshot is not the selected world state")
        return PumpStationWorldRun[PumpStationCoupledModel, PumpStationCoupledStewardshipState](
            repository=repository,
            package=profile.station_package,
            model=profile.model,
            manifest=manifest,
        )

    def migrate_to_v2(
        self,
        *,
        repository: PumpStationWorldRunRepository,
        run_id: str,
        world_branch_id: str,
    ) -> PumpStationWorldRun[PumpStationModel, PumpStationLegacyStewardshipState]:
        """Continue one version-1 state as a new version-2 run with lineage."""
        if self._manifest.record_versions != PUMP_STATION_RECORD_VERSIONS_V1:
            _fail("migration-source-version", str(self._manifest.record_versions))
        model = self._legacy_model()
        source_snapshot = self.snapshot()
        migrated_state = replace(
            self._legacy_state(),
            state_version=PUMP_STATION_STATE_VERSION_V2,
            dependencies=(),
            dependency_waivers=(),
            resource_reservations=(),
        )
        migrated = PumpStationWorldRun.create(
            repository=repository,
            package=self._package,
            model=model,
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

    def migrate_to_v3(
        self,
        *,
        repository: PumpStationWorldRunRepository,
        run_id: str,
        world_branch_id: str,
    ) -> PumpStationWorldRun[PumpStationModel, PumpStationLegacyStewardshipState]:
        """Continue one version-2 state as a new version-3 evidence-health run."""
        if self._manifest.record_versions != PUMP_STATION_RECORD_VERSIONS_V2:
            _fail("migration-source-version", str(self._manifest.record_versions))
        model = self._legacy_model()
        source_snapshot = self.snapshot()
        migrated_state = materialize_evidence_health_state(
            model,
            self._legacy_state(),
        )
        migrated = PumpStationWorldRun.create(
            repository=repository,
            package=self._package,
            model=model,
            initial_state=migrated_state,
            run_id=run_id,
            episode_id=self._manifest.episode_id,
            world_branch_id=world_branch_id,
            record_versions=PUMP_STATION_RECORD_VERSIONS_V3,
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
                source_authority_policy_version=self._manifest.authority_policy_version,
                source_transition_rule_version=self._manifest.transition_rule_version,
                target_run_id=migrated.manifest.run_id,
                target_world_branch_id=migrated.manifest.world_branch_id,
                target_state_id=target_snapshot.state_id,
                target_snapshot_version=migrated.manifest.snapshot_version,
                target_receipt_version=migrated.manifest.receipt_version,
                target_authority_policy_version=migrated.manifest.authority_policy_version,
                target_transition_rule_version=migrated.manifest.transition_rule_version,
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
    ) -> PumpStationWorldRun[PumpStationModel, PumpStationLegacyStewardshipState]:
        """Resume only the exact state currently selected by the repository."""
        manifest = repository.load_manifest()
        if isinstance(manifest, PumpStationWorldRunManifestV2):
            _fail(
                "reference-system-resume-required",
                "manifest v2 must resolve its registered profile from durable identity",
            )
        cls._validate_identity(manifest, package=package, model=model)
        current = repository.current_snapshot()
        if current != snapshot:
            _fail("snapshot-drift", "requested snapshot is not the selected world state")
        return PumpStationWorldRun[PumpStationModel, PumpStationLegacyStewardshipState](
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
    def model(self) -> _RunModelT:
        """Return the physical model bound to this run."""
        return self._model

    @property
    def manifest(self) -> PumpStationWorldRunManifestRecord:
        """Return the immutable run identity."""
        return self._manifest

    @property
    def continual_definition_ref(self) -> ContinualWorldDefinitionRef:
        """Return the exact registered implementation bound by manifest v2."""
        return self._definition_ref(self._reference_manifest())

    @property
    def continual_profile_ref(self) -> ContinualWorldProfileRef:
        """Return the exact registered profile bound by manifest v2."""
        return self._profile_ref(self._reference_manifest())

    @property
    def state(self) -> _RunStateT:
        """Reload the current complete state through the repository."""
        snapshot = self._repository.current_snapshot()
        return cast(_RunStateT, self._repository.load_state(snapshot.state_id))

    def snapshot(self) -> PumpStationStateSnapshotRef:
        """Return the exact currently selected dynamic state."""
        return self._repository.current_snapshot()

    def observe_v4_actor(
        self,
        *,
        session_id: str,
        agent_tenure_id: str,
    ) -> WorldActorObservation:
        """Return one V4 actor view bound to the exact selected commit."""
        manifest = self._reference_manifest()
        with self._repository.locked():
            snapshot = self._repository.current_snapshot()
            information_set = self._v4_information_set(
                snapshot,
                agent_tenure_id=agent_tenure_id,
            )
            view = information_set.base_view
            binding = WorldActorBinding(
                task_world_id=manifest.task_world_id,
                session_id=session_id,
                run_id=manifest.run_id,
                episode_id=manifest.episode_id,
                world_branch_id=manifest.world_branch_id,
                sequence=snapshot.sequence,
                state_id=snapshot.state_id,
                commit_id=snapshot.commit_id,
                agent_tenure_id=agent_tenure_id,
                actor_view_id=view.view_id,
                information_set_id=information_set.information_set_id,
            )
            return WorldActorObservation(
                binding=binding,
                view=cast(
                    dict[str, JsonValue],
                    canonical_stewardship_value(view, record_profile="v4"),
                ),
            )

    def apply_v4_actor_action(
        self,
        request: WorldActorActionRequest,
    ) -> PumpStationTransitionV4:
        """Apply or exactly recover one shared actor request on the V4 run."""
        manifest = self._reference_manifest()
        if not isinstance(self._model, PumpStationCoupledModel):
            _fail("world-run-identity", "V4 actor action requires the coupled model")
        command = self._v4_actor_command(request)
        with self._repository.locked():
            committed = self._repository.find_committed_v4_command(request.request_id)
            if committed is not None:
                return self._repository.validate_repeated_v4_command(
                    committed,
                    command,
                )
            recovered = self._repository._recover_staged_v4_command_under_lock(
                command,
            )
            if recovered is not None:
                return recovered
            prior = self._repository.current_snapshot()
            self._validate_v4_actor_scope(request.binding, prior)
            information_set = self._v4_information_set(
                prior,
                agent_tenure_id=request.binding.agent_tenure_id,
            )
            if (
                information_set.base_view.view_id != request.binding.actor_view_id
                or information_set.information_set_id != request.binding.information_set_id
            ):
                _fail(
                    "actor-request-binding",
                    "actor view or information set differs from the selected state",
                )
            try:
                arguments = validate_pump_station_actor_arguments_v2(
                    request.action_name,
                    cast(dict[str, object], request.arguments),
                )
            except WorldInterfaceError as error:
                _fail(error.code, error.detail)
            reason = arguments.get("reason")
            if not isinstance(reason, str) or reason != reason.strip():
                _fail(
                    "actor-action-arguments",
                    "reason must be non-empty and must not have surrounding whitespace",
                )
            proposal = pump_station_proposal_from_validated_arguments_v2(
                action_name=request.action_name,
                arguments=arguments,
                context=ProposalContext(
                    proposal_id=request.request_id,
                    agent_tenure_id=request.binding.agent_tenure_id,
                    based_on_sequence=request.binding.sequence,
                    base_view_id=request.binding.actor_view_id,
                    information_set_id=request.binding.information_set_id,
                    reason=reason,
                ),
            )
            state = cast(
                PumpStationCoupledStewardshipState,
                self._repository.load_state(prior.state_id),
            )
            try:
                transition = apply_stewardship_proposal_v4(
                    self._model,
                    state,
                    proposal,
                    information_set=information_set,
                )
            except (PumpStationProposalError, PumpStationCoupledWorldError) as error:
                _fail(error.code, str(error))
            staged = self._repository.stage_v4_transition(
                manifest=manifest,
                prior_snapshot=prior,
                command=command,
                proposal=proposal,
                information_set=information_set,
                transition=transition,
            )
            return self._repository._publish_staged_v4_transition_under_lock(staged)

    def apply_v4_control(
        self,
        request: PumpStationBoundControlRequest,
    ) -> PumpStationTransitionV4:
        """Apply or exactly recover one bound root host-control request."""
        manifest = self._reference_manifest()
        command = self._v4_control_command(request)
        with self._repository.locked():
            committed = self._repository.find_committed_v4_command(request.request_id)
            if committed is not None:
                return self._repository.validate_repeated_v4_command(
                    committed,
                    command,
                )
            recovered = self._repository._recover_staged_v4_command_under_lock(
                command,
            )
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
                manifest.run_id,
                manifest.episode_id,
                manifest.world_branch_id,
                prior.sequence,
                prior.state_id,
                prior.commit_id,
            )
            if observed != expected:
                _fail(
                    "control-request-scope",
                    "V4 control does not bind the selected world snapshot",
                )
            state = cast(
                PumpStationCoupledStewardshipState,
                self._repository.load_state(prior.state_id),
            )
            try:
                transition = apply_stewardship_control_v4(
                    state,
                    request.control,
                )
            except PumpStationCoupledWorldError as error:
                _fail(error.code, str(error))
            staged = self._repository.stage_v4_transition(
                manifest=manifest,
                prior_snapshot=prior,
                command=command,
                transition=transition,
            )
            return self._repository._publish_staged_v4_transition_under_lock(staged)

    def stage(
        self,
        proposal: PumpStationProposal,
        *,
        information_set: PumpStationInformationSet,
    ) -> PumpStationStagedTransition:
        """Write immutable transition evidence without selecting its state."""
        model = self._legacy_model()
        self._require_legacy_proposal_profile(proposal)
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
            state = self._legacy_state(prior.state_id)
            transition = apply_stewardship_proposal(
                model,
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
        model = self._legacy_model()
        self._require_legacy_proposal_profile(proposal)
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
            state = self._legacy_state(prior.state_id)
            transition = apply_stewardship_proposal(
                model,
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
            return self._repository._publish_staged_transition_under_lock(staged)

    def stage_evidence_treatment(
        self,
        request: PumpStationEvidenceTreatmentRequest,
    ) -> PumpStationStagedTransition:
        """Write immutable host-control evidence without selecting its state."""
        self._require_legacy_transitions()
        with self._repository.locked():
            prior = self._repository.current_snapshot()
            committed = self._repository.find_committed_control_request(
                request.request_id,
            )
            if committed is not None:
                _fail("control-request-already-committed", request.request_id)
            self._validate_control_scope(request, prior)
            state = self._legacy_state(prior.state_id)
            transition = apply_evidence_treatment_schedule(state, request)
            return self._repository.stage_control_transition(
                manifest=self._manifest,
                prior_snapshot=prior,
                control_request=request,
                transition=transition,
            )

    def schedule_evidence_treatment(
        self,
        request: PumpStationEvidenceTreatmentRequest,
    ) -> PumpStationTransition:
        """Schedule or exactly recover one durable evidence treatment."""
        self._require_legacy_transitions()
        with self._repository.locked():
            committed = self._repository.find_committed_control_request(
                request.request_id,
            )
            if committed is not None:
                return self._repository.validate_repeated_control_request(
                    committed,
                    request,
                )
            prior = self._repository.current_snapshot()
            self._validate_control_scope(request, prior)
            state = self._legacy_state(prior.state_id)
            transition = apply_evidence_treatment_schedule(state, request)
            staged = self._repository.stage_control_transition(
                manifest=self._manifest,
                prior_snapshot=prior,
                control_request=request,
                transition=transition,
            )
            return self._repository._publish_staged_transition_under_lock(staged)

    def recover_evidence_treatment(
        self,
        request_id: str,
    ) -> tuple[PumpStationEvidenceTreatmentRequest, PumpStationTransition]:
        """Reload one selected immutable treatment request and transition."""
        commit = self._repository.find_committed_control_request(request_id)
        if commit is None:
            _fail("control-request-not-found", request_id)
        request, transition = self._repository.recover_control_request(commit)
        if not isinstance(request, PumpStationEvidenceTreatmentRequest):
            _fail("control-request-type", request_id)
        return request, transition

    def apply_physical_treatment(
        self,
        request: PumpStationPhysicalTreatmentActivationRequest,
    ) -> PumpStationTransition:
        """Apply or exactly recover one governed physical treatment."""
        self._require_legacy_transitions()
        with self._repository.locked():
            committed = self._repository.find_committed_control_request(
                request.request_id,
            )
            if committed is not None:
                return self._repository.validate_repeated_control_request(
                    committed,
                    request,
                )
            prior = self._repository.current_snapshot()
            self._validate_control_scope(request, prior)
            state = self._legacy_state(prior.state_id)
            transition = apply_physical_treatment_activation(state, request)
            staged = self._repository.stage_control_transition(
                manifest=self._manifest,
                prior_snapshot=prior,
                control_request=request,
                transition=transition,
            )
            return self._repository._publish_staged_transition_under_lock(staged)

    def steps(self) -> tuple[PumpStationRunStep, ...]:
        """Reload all selected run steps for independent replay."""
        return self._repository.steps()

    def verify_v4(self) -> PumpStationVerificationReportV4:
        """Independently replay the selected V4 command chain."""
        manifest = self._reference_manifest()
        if not isinstance(self._model, PumpStationCoupledModel):
            _fail("world-run-identity", "V4 verification requires the coupled model")
        initial_state = cast(
            PumpStationCoupledStewardshipState,
            self._repository.load_state(manifest.initial_state_id),
        )
        with self._repository.locked():
            steps = self._repository.v4_steps()
            expected_final_state_id = self._repository.current_snapshot().state_id
        return verify_stewardship_run_v4(
            self._model,
            initial_state,
            steps,
            expected_final_state_id=expected_final_state_id,
            expected_task_world_id=manifest.task_world_id,
            expected_run_id=manifest.run_id,
            expected_episode_id=manifest.episode_id,
            expected_world_branch_id=manifest.world_branch_id,
            expected_actor_id="pump-station-actor",
            expected_source_artifact_ids=(
                manifest.reference_system_content_id,
                manifest.package_content_id,
                manifest.temporal_bundle_content_id,
            ),
        )

    @staticmethod
    def _load_registered_reference_profile() -> tuple[
        ContinualWorldDefinitionRef,
        ContinualWorldProfileRef,
        PumpStationContinualProfile,
    ]:
        """Load the one registered RS1 profile through its task definition."""
        from aec_bench.task_world_templates.continual_catalogue import (
            default_continual_world_catalogue,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
            PUMP_STATION_RS1_PROFILE_VERSION,
            PumpStationContinualProfile,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
            PUMP_STATION_REFERENCE_SYSTEM_ID,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
            PUMP_STATION_TASK_WORLD_ID,
        )

        try:
            definition = default_continual_world_catalogue().get(
                PUMP_STATION_TASK_WORLD_ID,
            )
            profile_ref = definition.profile_ref(
                PUMP_STATION_REFERENCE_SYSTEM_ID,
                PUMP_STATION_RS1_PROFILE_VERSION,
            )
            loaded = definition.load_profile(profile_ref)
        except (KeyError, ValueError) as error:
            _fail("world-run-identity", f"registered profile differs: {error}")
        if not isinstance(loaded.value, PumpStationContinualProfile):
            _fail("world-run-identity", "registered pump profile has another value")
        return definition.ref, profile_ref, loaded.value

    @staticmethod
    def _reference_system_manifest(
        *,
        definition_ref: ContinualWorldDefinitionRef,
        profile_ref: ContinualWorldProfileRef,
        profile: PumpStationContinualProfile,
        bundle: TemporalEvidenceBundle,
        run_id: str,
        episode_id: str,
        world_branch_id: str,
    ) -> PumpStationWorldRunManifestV2:
        """Build the exact manifest-v2 root from registered task-owned values."""
        system = profile.reference_system
        package = profile.station_package
        model = profile.model
        opening_id, opening_sha256 = PumpStationWorldRun._descriptor_binding(
            system.descriptor,
            "opening_state",
        )
        event_schedule_id, event_schedule_sha256 = PumpStationWorldRun._descriptor_binding(
            system.descriptor,
            "event_schedule",
        )
        temporal_template_id, temporal_template_sha256 = PumpStationWorldRun._descriptor_binding(
            system.descriptor,
            "temporal_template",
        )
        return PumpStationWorldRunManifestV2(
            serialization_version=PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
            snapshot_version=PUMP_STATION_RECORD_VERSIONS_V4.snapshot_version,
            receipt_version=PUMP_STATION_RECORD_VERSIONS_V4.receipt_version,
            authority_policy_version=PUMP_STATION_RECORD_VERSIONS_V4.authority_policy_version,
            transition_rule_version=PUMP_STATION_RECORD_VERSIONS_V4.transition_rule_version,
            run_id=run_id,
            episode_id=episode_id,
            world_branch_id=world_branch_id,
            profile_id=package.profile_id,
            generation_id=package.generation_id,
            package_content_id=package.package_content_id,
            manifest_content_id=package.manifest_content_id,
            asset_id=model.asset_id,
            model_id=stewardship_content_id(model, record_profile="v4"),
            initial_sequence=profile.opening_state.sequence,
            initial_state_id=stewardship_state_id(profile.opening_state),
            task_world_id=definition_ref.task_world_id,
            definition_version=definition_ref.definition_version,
            definition_content_sha256=definition_ref.content_sha256,
            continual_profile_id=profile_ref.profile_id,
            continual_profile_version=profile_ref.profile_version,
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
    def _descriptor_binding(
        descriptor: Mapping[str, object],
        name: str,
    ) -> tuple[str, str]:
        """Return one exact ID and content hash from the registered descriptor."""
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
        """Publish and verify required RS1 temporal evidence before run selection."""
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.models import (
            TemporalEvidenceIntegrityError,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.repository import (
            TemporalEvidenceRepository,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.verification import (
            verify_temporal_evidence_repository,
        )

        temporal_repository = TemporalEvidenceRepository(repository.root / "temporal-evidence")
        try:
            loaded = temporal_repository.initialize(bundle, package=package)
            report = verify_temporal_evidence_repository(
                temporal_repository,
                package=package,
            )
        except (OSError, ValueError, TemporalEvidenceIntegrityError) as error:
            _fail("temporal-evidence", f"RS1 temporal initialization failed: {error}")
        if loaded != bundle or not report.valid:
            _fail("temporal-evidence", "RS1 temporal initialization differs")

    @staticmethod
    def _verify_reference_temporal_evidence(
        *,
        repository: PumpStationWorldRunRepository,
        package: ReferencePackage,
        manifest: PumpStationWorldRunManifestV2,
        expected: TemporalEvidenceBundle,
    ) -> None:
        """Require stored RS1 temporal evidence to match immutable run metadata."""
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.models import (
            TemporalEvidenceIntegrityError,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.repository import (
            TemporalEvidenceRepository,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.verification import (
            verify_temporal_evidence_repository,
        )

        temporal_repository = TemporalEvidenceRepository(repository.root / "temporal-evidence")
        try:
            loaded = temporal_repository.load_bundle(package=package)
            report = verify_temporal_evidence_repository(
                temporal_repository,
                package=package,
            )
        except (OSError, ValueError, TemporalEvidenceIntegrityError) as error:
            _fail("temporal-evidence", f"RS1 temporal evidence is invalid: {error}")
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
        if loaded != expected or observed != bound or not report.valid:
            _fail("temporal-evidence", "RS1 temporal evidence differs from the run manifest")

    @staticmethod
    def _definition_ref(
        manifest: PumpStationWorldRunManifestV2,
    ) -> ContinualWorldDefinitionRef:
        """Rebuild the exact registered definition reference from manifest v2."""
        try:
            return ContinualWorldDefinitionRef(
                task_world_id=PumpStationWorldRun._manifest_text(manifest, "task_world_id"),
                definition_version=PumpStationWorldRun._manifest_text(
                    manifest,
                    "definition_version",
                ),
                content_sha256=PumpStationWorldRun._manifest_text(
                    manifest,
                    "definition_content_sha256",
                ),
            )
        except ValueError as error:
            _fail("world-run-identity", f"definition reference differs: {error}")

    @staticmethod
    def _profile_ref(
        manifest: PumpStationWorldRunManifestV2,
    ) -> ContinualWorldProfileRef:
        """Rebuild the exact registered profile reference from manifest v2."""
        try:
            return ContinualWorldProfileRef(
                task_world_id=PumpStationWorldRun._manifest_text(manifest, "task_world_id"),
                profile_id=PumpStationWorldRun._manifest_text(
                    manifest,
                    "continual_profile_id",
                ),
                profile_version=PumpStationWorldRun._manifest_text(
                    manifest,
                    "continual_profile_version",
                ),
                profile_content_sha256=PumpStationWorldRun._manifest_text(
                    manifest,
                    "continual_profile_content_sha256",
                ),
            )
        except ValueError as error:
            _fail("world-run-identity", f"profile reference differs: {error}")

    @staticmethod
    def _manifest_text(
        manifest: PumpStationWorldRunManifestV2,
        field_name: str,
    ) -> str:
        """Require one manifest-v2 text binding."""
        value = getattr(manifest, field_name)
        if not isinstance(value, str) or not value.strip():
            _fail("world-run-identity", f"manifest lacks {field_name}")
        return value

    def _reference_manifest(self) -> PumpStationWorldRunManifestV2:
        """Return the required registered-profile manifest for reference access."""
        if not isinstance(self._manifest, PumpStationWorldRunManifestV2):
            _fail("reference-system-manifest-required", "run uses the legacy manifest")
        return self._manifest

    def _v4_information_set(
        self,
        snapshot: PumpStationStateSnapshotRef,
        *,
        agent_tenure_id: str,
    ) -> PumpStationInformationSet:
        """Build the exact V4 view, history, and visible commitment context."""
        manifest = self._reference_manifest()
        state = cast(
            PumpStationCoupledStewardshipState,
            self._repository.load_state(snapshot.state_id),
        )
        source_artifact_ids = (
            manifest.reference_system_content_id,
            manifest.package_content_id,
            manifest.temporal_bundle_content_id,
        )
        return project_coupled_information_set(
            state,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            actor_id="pump-station-actor",
            agent_tenure_id=agent_tenure_id,
            source_artifact_ids=source_artifact_ids,
            workspace_tool_ids=(PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID_V2,),
        )

    @staticmethod
    def _v4_actor_command(request: WorldActorActionRequest) -> PumpStationCommandV4:
        """Convert one shared actor request to the strict durable V4 command."""
        binding = request.binding
        return PumpStationCommandV4(
            command_version=PUMP_STATION_COMMAND_VERSION_V4,
            kind="actor",
            request_id=request.request_id,
            request_content_id=request.content_sha256,
            action_name=request.action_name,
            arguments_json=json.dumps(
                request.arguments,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            task_world_id=binding.task_world_id,
            run_id=binding.run_id,
            episode_id=binding.episode_id,
            world_branch_id=binding.world_branch_id,
            based_on_sequence=binding.sequence,
            base_state_id=binding.state_id,
            base_commit_id=binding.commit_id,
            session_id=binding.session_id,
            agent_tenure_id=binding.agent_tenure_id,
            actor_view_id=binding.actor_view_id,
            information_set_id=binding.information_set_id,
        )

    def _v4_control_command(
        self,
        request: PumpStationBoundControlRequest,
    ) -> PumpStationCommandV4:
        """Convert one bound root control to the strict durable V4 command."""
        control = request.control
        if isinstance(control, PumpStationOperationsBoundaryReviewRequest):
            kind = "operations_review"
            action_name = "operations_boundary_review"
        elif isinstance(control, PumpStationProcessOutcomeRequest):
            kind = "process_outcome"
            action_name = "process_outcome"
        elif isinstance(control, PumpStationCommonBoundaryRequest):
            kind = "common_boundary"
            action_name = "common_boundary_control"
        else:
            _fail("control-type", f"unsupported V4 control {type(control).__name__}")
        manifest = self._reference_manifest()
        return PumpStationCommandV4(
            command_version=PUMP_STATION_COMMAND_VERSION_V4,
            kind=kind,
            request_id=request.request_id,
            request_content_id=control.content_id,
            action_name=action_name,
            arguments_json=json.dumps(
                canonical_stewardship_value(control, record_profile="v4"),
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            task_world_id=manifest.task_world_id,
            run_id=request.run_id,
            episode_id=request.episode_id,
            world_branch_id=request.world_branch_id,
            based_on_sequence=request.based_on_sequence,
            base_state_id=request.base_state_id,
            base_commit_id=request.base_commit_id,
            authority_id=request.authority_id,
        )

    def _validate_v4_actor_scope(
        self,
        binding: WorldActorBinding,
        snapshot: PumpStationStateSnapshotRef,
    ) -> None:
        """Require one actor request to name the selected run and parent commit."""
        manifest = self._reference_manifest()
        observed = (
            binding.task_world_id,
            binding.run_id,
            binding.episode_id,
            binding.world_branch_id,
            binding.sequence,
            binding.state_id,
            binding.commit_id,
        )
        expected = (
            manifest.task_world_id,
            manifest.run_id,
            manifest.episode_id,
            manifest.world_branch_id,
            snapshot.sequence,
            snapshot.state_id,
            snapshot.commit_id,
        )
        if observed != expected:
            _fail(
                "actor-request-binding",
                "actor request does not bind the selected world snapshot",
            )

    def _require_legacy_transitions(self) -> None:
        """Keep V4 closed until its task-owned transition port uses this run."""
        if self._manifest.record_versions == PUMP_STATION_RECORD_VERSIONS_V4:
            _fail(
                "v4-transition-not-routed",
                "registered V4 transitions are not yet integrated",
            )

    @staticmethod
    def _require_legacy_proposal_profile(proposal: PumpStationProposal) -> None:
        """Reject V4-only fields before a legacy request can be retried or stored."""
        try:
            validate_legacy_proposal_profile(proposal)
        except PumpStationProposalError as error:
            _fail(error.code, str(error))

    def _legacy_model(self) -> PumpStationModel:
        """Return the two-pump model selected by legacy transition paths."""
        self._require_legacy_transitions()
        if not isinstance(self._model, PumpStationModel):
            _fail("world-run-identity", "legacy run has another physical model")
        return self._model

    def _legacy_state(self, state_id: str | None = None) -> PumpStationLegacyStewardshipState:
        """Reload one state after the durable version guard selects the legacy profile."""
        self._require_legacy_transitions()
        selected = self.state if state_id is None else self._repository.load_state(state_id)
        return cast(PumpStationLegacyStewardshipState, selected)

    def _validate_control_scope(
        self,
        request: (PumpStationEvidenceTreatmentRequest | PumpStationPhysicalTreatmentActivationRequest),
        snapshot: PumpStationStateSnapshotRef,
    ) -> None:
        observed = (
            request.run_id,
            request.episode_id,
            request.world_branch_id,
            request.base_state_id,
            request.base_commit_id,
            request.based_on_sequence,
        )
        expected = (
            self._manifest.run_id,
            self._manifest.episode_id,
            self._manifest.world_branch_id,
            snapshot.state_id,
            snapshot.commit_id,
            snapshot.sequence,
        )
        if observed != expected:
            _fail(
                "control-request-scope",
                "treatment request does not bind the selected world snapshot",
            )

    @staticmethod
    def _validate_identity(
        manifest: PumpStationWorldRunManifest,
        *,
        package: ReferencePackage,
        model: PumpStationModel,
    ) -> None:
        if manifest.serialization_version != PUMP_STATION_SERIALIZATION_VERSION:
            _fail("serialization-version", manifest.serialization_version)
        if not isinstance(model, PumpStationModel):
            _fail("world-run-identity", "legacy manifest requires the two-pump model")
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
