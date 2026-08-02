# ABOUTME: Publishes one pump-station run to a host-supplied filesystem root.
# ABOUTME: Owns immutable evidence, file locking, atomic current-state selection, and strict reload.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NoReturn, TypeGuard, cast

from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.task_world_templates.continual.durability import (
    DurableFileReplaceConfinementError,
    DurableFileReplaceError,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactStoreError,
    ImmutableByteStore,
    exclusive_local_file_lock,
    mkdir_durable,
    replace_file_bytes_durable,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID_V2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    project_coupled_information_set,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PumpStationPhysicalTreatmentActivationRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_state_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_STATE_VERSION_V4,
    CancelProcess,
    ContinueOperation,
    PumpStationCoupledStewardshipState,
    PumpStationLegacyStewardshipState,
    PumpStationProposal,
    PumpStationStewardshipState,
    PumpStationStewardshipStateRecord,
    PumpStationTransition,
    PumpStationTransitionReceipt,
    PumpStationTransitionReceiptV4,
    PumpStationTransitionV4,
    RequestConditionalDeferral,
    RequestConditionCheck,
    RequestDependencyWaiver,
    RequestDutyAssignment,
    RequestFunctionalCheck,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalClosure,
    RequestProvisionalReturn,
    RequestVerification,
    ResumeProcess,
    TransferDuty,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationRunStep,
    PumpStationRunStepV4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationActorView,
    PumpStationCoupledActorView,
    PumpStationInformationSet,
    PumpStationStructuredHandoverV4,
    actor_history_entry_v4,
    bind_information_set,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_commands import (
    decode_pump_station_v4_command,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_SERIALIZATION_VERSION,
    PumpStationAppliedEventBatch,
    PumpStationCommandV4,
    PumpStationCurrentRunPointer,
    PumpStationStagedTransition,
    PumpStationStagedTransitionV4,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunCommit,
    PumpStationWorldRunCommitRecord,
    PumpStationWorldRunCommitV2,
    PumpStationWorldRunError,
    PumpStationWorldRunManifest,
    PumpStationWorldRunManifestRecord,
    PumpStationWorldRunManifestV2,
    PumpStationWorldRunMigration,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
    pump_station_artifact_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session_activation import (
    PUMP_STATION_ACTIVE_SESSION_POINTER_VERSION,
    PUMP_STATION_SESSION_ACTIVATION_CLAIM_VERSION,
    PumpStationActiveSessionPointer,
    PumpStationSessionActivationBinding,
    PumpStationSessionActivationClaim,
)

_SESSION_AUTHORITY_ROOT = "session-authority"
_SESSION_BINDING_COLLECTION = f"{_SESSION_AUTHORITY_ROOT}/bindings"
_SESSION_ACTIVATION_CLAIM_COLLECTION = f"{_SESSION_AUTHORITY_ROOT}/activation-claims"
_SESSION_HANDOVER_COLLECTION = f"{_SESSION_AUTHORITY_ROOT}/handovers"
_ACTIVE_SESSION_POINTER_NAME = "active.json"

_PROPOSAL_TYPES: dict[str, type[object]] = {
    proposal_type.__name__: proposal_type
    for proposal_type in (
        ContinueOperation,
        TransferDuty,
        RequestDutyAssignment,
        RequestInspection,
        RequestConditionalDeferral,
        RequestConditionCheck,
        RequestObstructionClearance,
        RequestFunctionalCheck,
        RequestProvisionalReturn,
        RequestProvisionalClosure,
        RequestVerification,
        ResumeProcess,
        CancelProcess,
        RequestDependencyWaiver,
    )
}

type PumpStationControlInput = PumpStationEvidenceTreatmentRequest | PumpStationPhysicalTreatmentActivationRequest
type PumpStationDurableInput = PumpStationProposal | PumpStationControlInput

_CONTROL_TYPES: dict[str, type[PumpStationControlInput]] = {
    item.__name__: item
    for item in (
        PumpStationEvidenceTreatmentRequest,
        PumpStationPhysicalTreatmentActivationRequest,
    )
}


def _is_control_input(value: object) -> TypeGuard[PumpStationControlInput]:
    return isinstance(
        value,
        PumpStationEvidenceTreatmentRequest | PumpStationPhysicalTreatmentActivationRequest,
    )


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationWorldRunError(code, detail)


class PumpStationWorldRunRepository:
    """A confined durable repository for exactly one pump-station world run."""

    def __init__(self, root: Path) -> None:
        selected = Path(root)
        if selected.exists() and (selected.is_symlink() or not selected.is_dir()):
            _fail("artifact-confinement", "world-run root must be a plain directory")
        mkdir_durable(selected, created_mode=0o700)
        selected.chmod(0o700)
        self._root = selected.resolve(strict=True)
        self._lock_path = self._root / ".world-run.lock"
        try:
            self._artifacts = ImmutableByteStore(self._root, host_private=True)
        except ImmutableArtifactConfinementError as error:
            _fail("artifact-confinement", f"world-run root is unsafe: {error}")
        except ImmutableArtifactStoreError as error:
            _fail("artifact-integrity", f"world-run byte store is unavailable: {error}")

    @property
    def root(self) -> Path:
        """Return the exact host-supplied run root."""
        return self._root

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serialize state selection across local processes."""
        with exclusive_local_file_lock(
            self._root,
            ".world-run.lock",
            error_factory=lambda error: PumpStationWorldRunError(
                "artifact-confinement",
                f"world-run lock is unsafe: {error}",
            ),
        ):
            yield

    def initialize(
        self,
        manifest: PumpStationWorldRunManifestRecord,
        initial_state: PumpStationStewardshipStateRecord,
        *,
        before_select: Callable[[], None] | None = None,
    ) -> PumpStationStateSnapshotRef:
        """Publish initial evidence, complete required setup, and select it atomically."""
        with self.locked():
            if stewardship_state_id(initial_state) != manifest.initial_state_id:
                _fail("world-run-identity", "initial state differs from manifest")
            expected_state_version = {
                "pump-station-state-snapshot.v1": "pump-station-stewardship-state.v1",
                "pump-station-state-snapshot.v2": "pump-station-stewardship-state.v2",
                "pump-station-state-snapshot.v3": "pump-station-stewardship-state.v3",
                "pump-station-state-snapshot.v4": "pump-station-stewardship-state.v4",
            }[manifest.snapshot_version]
            if initial_state.state_version != expected_state_version:
                _fail("state-version", "state and snapshot versions differ")
            if (self._root / "current.json").exists():
                if self.load_manifest() != manifest:
                    _fail("world-run-exists", f"{manifest.run_id} has different identity")
                if self.load_state(manifest.initial_state_id) != initial_state:
                    _fail("world-run-exists", f"{manifest.run_id} has different initial state")
                current = self.current_snapshot()
                if current.sequence != manifest.initial_sequence or current.state_id != manifest.initial_state_id:
                    _fail("world-run-exists", f"{manifest.run_id} has already advanced")
                return current
            self._publish_root_immutable("manifest.json", manifest)
            self._publish_state(initial_state)
            commit = PumpStationWorldRunCommit(
                serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
                run_id=manifest.run_id,
                sequence=manifest.initial_sequence,
                parent_commit_id=None,
                state_id=manifest.initial_state_id,
                proposal_id=None,
                proposal_content_id=None,
                information_set_content_id=None,
                receipt_content_id=None,
                event_batch_content_id=None,
            )
            commit_id = pump_station_artifact_id(commit)
            self._publish_content("commits", commit_id, commit)
            if before_select is not None:
                before_select()
            pointer = PumpStationCurrentRunPointer(
                serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
                run_id=manifest.run_id,
                sequence=manifest.initial_sequence,
                state_id=manifest.initial_state_id,
                commit_id=commit_id,
            )
            self._replace_current(pointer)
            return self._snapshot(manifest, pointer)

    def load_manifest(self) -> PumpStationWorldRunManifestRecord:
        """Reload the immutable run identity."""
        return cast(
            PumpStationWorldRunManifestRecord,
            load_pump_station_artifact(
                self._read(self._root / "manifest.json", "world-run manifest"),
                PumpStationWorldRunManifest | PumpStationWorldRunManifestV2,
            ),
        )

    def current_snapshot(self) -> PumpStationStateSnapshotRef:
        """Reload and validate the atomically selected state reference."""
        manifest = self.load_manifest()
        pointer = self._load_current()
        if pointer.run_id != manifest.run_id:
            _fail("artifact-integrity", "current pointer belongs to another run")
        commit = self.load_commit(pointer.commit_id)
        if (
            commit.run_id != manifest.run_id
            or commit.sequence != pointer.sequence
            or commit.state_id != pointer.state_id
        ):
            _fail("artifact-integrity", "current pointer and commit differ")
        self.load_state(pointer.state_id)
        return self._snapshot(manifest, pointer)

    def publish_session_activation(
        self,
        binding: PumpStationSessionActivationBinding,
    ) -> PumpStationSessionActivationBinding:
        """Publish and select one exact host-approved V4 session binding."""

        with self.locked():
            return self._publish_session_activation_under_lock(binding)

    def _publish_session_activation_under_lock(
        self,
        binding: PumpStationSessionActivationBinding,
    ) -> PumpStationSessionActivationBinding:
        """Publish and select a session binding while the caller owns the run lock."""

        manifest = self._require_v4_session_manifest()
        self._require_session_activation_scope(binding, manifest)
        self._require_current_session_snapshot(binding)
        active = self._selected_session_activation_if_present(manifest)
        if active is not None:
            pointer, current_binding = active
            if binding.binding_id == pointer.active_binding_id:
                if binding != current_binding:
                    _fail(
                        "artifact-integrity",
                        "active session binding content differs from its identity",
                    )
                return current_binding
            if binding.active_activation_id == pointer.active_activation_id:
                _fail(
                    "session-activation-conflict",
                    f"{binding.active_activation_id} already selects another binding",
                )
            if (
                binding.prior_binding_id != pointer.active_binding_id
                or binding.session_event_sequence != pointer.session_event_sequence + 1
            ):
                _fail(
                    "session-activation-stale",
                    "replacement does not extend the active session binding",
                )
            if binding.host_authority_id != current_binding.host_authority_id:
                _fail(
                    "session-activation-authority",
                    "replacement session binding uses another host authority",
                )
        elif binding.prior_binding_id is not None or binding.session_event_sequence != 0:
            _fail(
                "session-activation-stale",
                "initial session binding must start a new activation chain",
            )

        claim = PumpStationSessionActivationClaim(
            claim_version=PUMP_STATION_SESSION_ACTIVATION_CLAIM_VERSION,
            active_activation_id=binding.active_activation_id,
            binding_id=binding.binding_id,
        )
        self._require_session_activation_claim(claim)
        self._publish_session_binding(binding)
        self._publish_session_activation_claim(claim)
        self._replace_active_session_pointer(
            PumpStationActiveSessionPointer(
                pointer_version=PUMP_STATION_ACTIVE_SESSION_POINTER_VERSION,
                run_id=binding.run_id,
                episode_id=binding.episode_id,
                world_branch_id=binding.world_branch_id,
                active_activation_id=binding.active_activation_id,
                active_binding_id=binding.binding_id,
                session_event_sequence=binding.session_event_sequence,
            )
        )
        return binding

    def load_session_activation(
        self,
        binding_id: str,
    ) -> PumpStationSessionActivationBinding:
        """Reload one immutable V4 session binding by exact content identity."""

        with self.locked():
            manifest = self._require_v4_session_manifest()
            return self._load_session_binding(binding_id, manifest)

    def load_active_session_activation(self) -> PumpStationSessionActivationBinding:
        """Reload the active V4 session binding only at its selected world position."""

        with self.locked():
            manifest = self._require_v4_session_manifest()
            active = self._selected_session_activation_if_present(manifest)
            if active is None:
                _fail("session-activation-missing", "run has no active session binding")
            _, binding = active
            self._require_current_session_snapshot(binding)
            return binding

    def load_selected_session_activation(self) -> PumpStationSessionActivationBinding:
        """Reload the pointer-selected V4 session even when the world has advanced."""

        with self.locked():
            manifest = self._require_v4_session_manifest()
            active = self._selected_session_activation_if_present(manifest)
            if active is None:
                _fail("session-activation-missing", "run has no active session binding")
            _, binding = active
            return binding

    def publish_structured_handover(
        self,
        handover: PumpStationStructuredHandoverV4,
    ) -> PumpStationStructuredHandoverV4:
        """Publish one full immutable V4 handover without selecting world state."""

        with self.locked():
            return self._publish_structured_handover_under_lock(handover)

    def _publish_structured_handover_under_lock(
        self,
        handover: PumpStationStructuredHandoverV4,
    ) -> PumpStationStructuredHandoverV4:
        """Publish one V4 handover while the session coordinator owns the run lock."""

        manifest = self._require_v4_session_manifest()
        path = self._structured_handover_path(handover.handover_id)
        if path.exists() or path.is_symlink():
            observed = self._load_structured_handover(
                handover.handover_id,
                manifest,
            )
            if observed != handover:
                _fail(
                    "artifact-integrity",
                    "structured handover content differs from its identity",
                )
            return observed
        self._require_structured_handover_scope(handover, manifest)
        self._require_current_structured_handover_snapshot(handover)
        self._require_selected_structured_handover_session(handover, manifest)
        self._require_structured_handover_record(handover, manifest)
        self._publish_content(
            _SESSION_HANDOVER_COLLECTION,
            handover.handover_id,
            handover,
            record_profile="v4",
        )
        return handover

    def load_structured_handover(
        self,
        handover_id: str,
    ) -> PumpStationStructuredHandoverV4:
        """Reload one complete immutable V4 handover by content identity."""

        with self.locked():
            manifest = self._require_v4_session_manifest()
            return self._load_structured_handover(handover_id, manifest)

    def has_structured_handover(self, handover_id: str) -> bool:
        """Return whether one valid content identity selects a durable handover file."""

        try:
            validate_sha256(handover_id)
        except ValueError:
            return False
        return self._structured_handover_path(handover_id).is_file()

    def _require_active_session_activation_under_lock(
        self,
        binding_id: str,
    ) -> PumpStationSessionActivationBinding:
        """Require one current active binding while the caller owns the run lock."""

        manifest = self._require_v4_session_manifest()
        active = self._selected_session_activation_if_present(manifest)
        if active is None:
            _fail("session-activation-missing", "run has no active session binding")
        pointer, binding = active
        if pointer.active_binding_id != binding_id:
            _fail(
                "actor-session-revoked",
                "actor command does not use the active session binding",
            )
        self._require_current_session_snapshot(binding)
        return binding

    def load_state(self, state_id: str) -> PumpStationStewardshipStateRecord:
        """Reload a complete state and verify its semantic identity."""
        state = load_pump_station_artifact(
            self._read_content("states", state_id),
            PumpStationStewardshipState,
        )
        if stewardship_state_id(state) != state_id:
            _fail("artifact-integrity", f"state identity differs for {state_id}")
        return state

    def load_legacy_state(self, state_id: str) -> PumpStationLegacyStewardshipState:
        """Reload one state only when its record profile is legacy V1 to V3."""
        state = self.load_state(state_id)
        if state.state_version == PUMP_STATION_STATE_VERSION_V4:
            _fail("record-versions", "legacy state access selected a V4 state")
        return cast(PumpStationLegacyStewardshipState, state)

    def load_commit(self, commit_id: str) -> PumpStationWorldRunCommitRecord:
        """Reload one immutable commit by content identity."""
        commit = cast(
            PumpStationWorldRunCommitRecord,
            load_pump_station_artifact(
                self._read_content("commits", commit_id),
                PumpStationWorldRunCommit | PumpStationWorldRunCommitV2,
            ),
        )
        if pump_station_artifact_id(commit) != commit_id:
            _fail("artifact-integrity", f"commit identity differs for {commit_id}")
        return commit

    def snapshot_for_commit(
        self,
        commit: PumpStationWorldRunCommitRecord,
    ) -> PumpStationStateSnapshotRef:
        """Return the exact snapshot selected by one commit on the live chain."""
        commit_id = pump_station_artifact_id(commit)
        if all(pump_station_artifact_id(item) != commit_id for item in self.commits()):
            _fail("artifact-integrity", "commit is not on the selected chain")
        manifest = self.load_manifest()
        return PumpStationStateSnapshotRef(
            snapshot_version=manifest.snapshot_version,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            sequence=commit.sequence,
            state_id=commit.state_id,
            commit_id=commit_id,
        )

    def stage_transition(
        self,
        *,
        manifest: PumpStationWorldRunManifestRecord,
        prior_snapshot: PumpStationStateSnapshotRef,
        proposal: PumpStationProposal,
        information_set: PumpStationInformationSet,
        transition: PumpStationTransition,
    ) -> PumpStationStagedTransition:
        """Publish all immutable evidence without changing the current pointer."""
        receipt = transition.receipt
        if (
            receipt.sequence != prior_snapshot.sequence + 1
            or receipt.pre_state_id != prior_snapshot.state_id
            or receipt.post_state_id != stewardship_state_id(transition.state)
            or receipt.proposal_id != proposal.context.proposal_id
            or receipt.receipt_version != manifest.receipt_version
            or receipt.authority_policy_version != manifest.authority_policy_version
            or receipt.transition_rule_version != manifest.transition_rule_version
        ):
            _fail("transition-integrity", "transition does not extend the selected state")
        self._reject_proposal_collision(
            proposal,
            information_set=information_set,
            parent_commit_id=prior_snapshot.commit_id,
        )
        state_id = self._publish_state(transition.state)
        proposal_content_id = pump_station_artifact_id(proposal)
        information_set_content_id = pump_station_artifact_id(information_set)
        receipt_content_id = pump_station_artifact_id(receipt)
        event_batch = PumpStationAppliedEventBatch(
            transition_id=receipt.transition_id,
            sequence=receipt.sequence,
            event_ids=receipt.applied_event_ids,
            event_types=receipt.applied_event_types,
        )
        event_batch_content_id = pump_station_artifact_id(event_batch)
        self._publish_content("proposals", proposal_content_id, proposal)
        self._publish_content(
            "information-sets",
            information_set_content_id,
            information_set,
        )
        self._publish_content("receipts", receipt_content_id, receipt)
        self._publish_content("events", event_batch_content_id, event_batch)
        commit = PumpStationWorldRunCommit(
            serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
            run_id=manifest.run_id,
            sequence=receipt.sequence,
            parent_commit_id=prior_snapshot.commit_id,
            state_id=state_id,
            proposal_id=proposal.context.proposal_id,
            proposal_content_id=proposal_content_id,
            information_set_content_id=information_set_content_id,
            receipt_content_id=receipt_content_id,
            event_batch_content_id=event_batch_content_id,
        )
        commit_id = pump_station_artifact_id(commit)
        self._publish_content("commits", commit_id, commit)
        snapshot = PumpStationStateSnapshotRef(
            snapshot_version=manifest.snapshot_version,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            sequence=receipt.sequence,
            state_id=state_id,
            commit_id=commit_id,
        )
        return PumpStationStagedTransition(
            prior_snapshot=prior_snapshot,
            snapshot=snapshot,
            proposal=proposal,
            information_set=information_set,
            transition=transition,
            commit=commit,
        )

    def stage_control_transition(
        self,
        *,
        manifest: PumpStationWorldRunManifestRecord,
        prior_snapshot: PumpStationStateSnapshotRef,
        control_request: PumpStationControlInput,
        transition: PumpStationTransition,
    ) -> PumpStationStagedTransition:
        """Publish one host-control transition without an actor information set."""
        receipt = transition.receipt
        if (
            receipt.sequence != prior_snapshot.sequence + 1
            or receipt.pre_state_id != prior_snapshot.state_id
            or receipt.post_state_id != stewardship_state_id(transition.state)
            or receipt.proposal_id is not None
            or receipt.receipt_version != manifest.receipt_version
            or receipt.authority_policy_version != manifest.authority_policy_version
            or receipt.transition_rule_version != manifest.transition_rule_version
            or control_request.based_on_sequence != prior_snapshot.sequence
            or control_request.base_state_id != prior_snapshot.state_id
            or control_request.base_commit_id != prior_snapshot.commit_id
        ):
            _fail("transition-integrity", "control transition does not extend the selected state")
        self._reject_control_collision(
            control_request,
            parent_commit_id=prior_snapshot.commit_id,
        )
        state_id = self._publish_state(transition.state)
        request_content_id = pump_station_artifact_id(control_request)
        receipt_content_id = pump_station_artifact_id(receipt)
        event_batch = PumpStationAppliedEventBatch(
            transition_id=receipt.transition_id,
            sequence=receipt.sequence,
            event_ids=receipt.applied_event_ids,
            event_types=receipt.applied_event_types,
        )
        event_batch_content_id = pump_station_artifact_id(event_batch)
        self._publish_content(
            "control-requests",
            request_content_id,
            control_request,
        )
        self._publish_content("receipts", receipt_content_id, receipt)
        self._publish_content("events", event_batch_content_id, event_batch)
        commit = PumpStationWorldRunCommit(
            serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
            run_id=manifest.run_id,
            sequence=receipt.sequence,
            parent_commit_id=prior_snapshot.commit_id,
            state_id=state_id,
            proposal_id=control_request.request_id,
            proposal_content_id=request_content_id,
            information_set_content_id=None,
            receipt_content_id=receipt_content_id,
            event_batch_content_id=event_batch_content_id,
        )
        commit_id = pump_station_artifact_id(commit)
        self._publish_content("commits", commit_id, commit)
        snapshot = PumpStationStateSnapshotRef(
            snapshot_version=manifest.snapshot_version,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            sequence=receipt.sequence,
            state_id=state_id,
            commit_id=commit_id,
        )
        return PumpStationStagedTransition(
            prior_snapshot=prior_snapshot,
            snapshot=snapshot,
            proposal=None,
            information_set=None,
            transition=transition,
            commit=commit,
            control_request=control_request,
        )

    def stage_v4_transition(
        self,
        *,
        manifest: PumpStationWorldRunManifestV2,
        prior_snapshot: PumpStationStateSnapshotRef,
        command: PumpStationCommandV4,
        transition: PumpStationTransitionV4,
        proposal: PumpStationProposal | None = None,
        information_set: PumpStationInformationSet | None = None,
    ) -> PumpStationStagedTransitionV4:
        """Publish complete V4 command evidence without selecting its state."""
        stored_manifest = self.load_manifest()
        if not isinstance(stored_manifest, PumpStationWorldRunManifestV2) or stored_manifest != manifest:
            _fail("world-run-identity", "V4 caller manifest differs from the stored run")
        self._require_v4_command_scope(command, stored_manifest)
        decode_pump_station_v4_command(command)
        receipt = transition.receipt
        actor_step = command.kind == "actor"
        if (
            command.task_world_id != manifest.task_world_id
            or command.run_id != manifest.run_id
            or command.episode_id != manifest.episode_id
            or command.world_branch_id != manifest.world_branch_id
            or command.based_on_sequence != prior_snapshot.sequence
            or command.base_state_id != prior_snapshot.state_id
            or command.base_commit_id != prior_snapshot.commit_id
            or receipt.sequence != prior_snapshot.sequence + 1
            or receipt.before_state_id != prior_snapshot.state_id
            or receipt.after_state_id != stewardship_state_id(transition.state)
            or receipt.request_id != command.request_id
            or receipt.action_or_control_kind != command.action_name
            or receipt.actor_action != actor_step
            or receipt.receipt_version != manifest.receipt_version
            or receipt.authority_policy_version != manifest.authority_policy_version
            or receipt.transition_rule_version != manifest.transition_rule_version
            or actor_step != (proposal is not None and information_set is not None)
        ):
            _fail("transition-integrity", "V4 transition does not extend the selected state")
        if actor_step:
            assert proposal is not None
            assert information_set is not None
            parent_state = self._load_v4_state(prior_snapshot.state_id)
            self._require_v4_actor_information_set(
                stored_manifest,
                parent_state,
                command,
                information_set,
            )
            if (
                proposal.context.proposal_id != command.request_id
                or proposal.context.agent_tenure_id != command.agent_tenure_id
                or proposal.context.based_on_sequence != command.based_on_sequence
                or proposal.context.base_view_id != command.actor_view_id
                or proposal.context.information_set_id != command.information_set_id
                or information_set.information_set_id != command.information_set_id
            ):
                _fail("transition-integrity", "V4 actor evidence bindings differ")
        self._reject_v4_command_collision(
            command,
            parent_commit_id=prior_snapshot.commit_id,
        )
        state_id = self._publish_state(transition.state)
        command_content_id = pump_station_artifact_id(command, record_profile="v4")
        receipt_content_id = pump_station_artifact_id(receipt, record_profile="v4")
        proposal_content_id: str | None = None
        information_set_content_id: str | None = None
        self._publish_content(
            "commands",
            command_content_id,
            command,
            record_profile="v4",
        )
        if proposal is not None and information_set is not None:
            proposal_content_id = pump_station_artifact_id(
                proposal,
                record_profile="v4",
            )
            information_set_content_id = pump_station_artifact_id(
                information_set,
                record_profile="v4",
            )
            self._publish_content(
                "proposals",
                proposal_content_id,
                proposal,
                record_profile="v4",
            )
            self._publish_content(
                "information-sets",
                information_set_content_id,
                information_set,
                record_profile="v4",
            )
        self._publish_content(
            "receipts",
            receipt_content_id,
            receipt,
            record_profile="v4",
        )
        commit = PumpStationWorldRunCommitV2(
            serialization_version=manifest.serialization_version,
            run_id=manifest.run_id,
            sequence=receipt.sequence,
            parent_commit_id=prior_snapshot.commit_id,
            state_id=state_id,
            request_id=command.request_id,
            command_content_id=command_content_id,
            proposal_content_id=proposal_content_id,
            information_set_content_id=information_set_content_id,
            receipt_content_id=receipt_content_id,
        )
        commit_id = pump_station_artifact_id(commit, record_profile="v4")
        self._publish_content(
            "commits",
            commit_id,
            commit,
            record_profile="v4",
        )
        snapshot = PumpStationStateSnapshotRef(
            snapshot_version=manifest.snapshot_version,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            sequence=receipt.sequence,
            state_id=state_id,
            commit_id=commit_id,
        )
        return PumpStationStagedTransitionV4(
            prior_snapshot=prior_snapshot,
            snapshot=snapshot,
            command=command,
            transition=transition,
            commit=commit,
            proposal=proposal,
            information_set=information_set,
        )

    def publish_staged_transition(
        self,
        staged: PumpStationStagedTransition,
    ) -> PumpStationTransition:
        """Lock and select a fully staged transition with one pointer replacement."""
        with self.locked():
            return self._publish_staged_transition_under_lock(staged)

    def publish_staged_v4_transition(
        self,
        staged: PumpStationStagedTransitionV4,
    ) -> PumpStationTransitionV4:
        """Lock and select one fully staged V4 transition."""
        with self.locked():
            return self._publish_staged_v4_transition_under_lock(staged)

    def _publish_staged_v4_transition_under_lock(
        self,
        staged: PumpStationStagedTransitionV4,
    ) -> PumpStationTransitionV4:
        """Select one staged V4 transition while the caller owns the run lock."""
        transition = self._require_staged_v4_identity(staged)
        current = self.current_snapshot()
        if current == staged.snapshot:
            return transition
        if current != staged.prior_snapshot:
            _fail("stale-publication", "world run advanced after V4 transition preparation")
        self._replace_current(
            PumpStationCurrentRunPointer(
                serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
                run_id=staged.snapshot.run_id,
                sequence=staged.snapshot.sequence,
                state_id=staged.snapshot.state_id,
                commit_id=staged.snapshot.commit_id,
            )
        )
        return transition

    def _publish_staged_transition_under_lock(
        self,
        staged: PumpStationStagedTransition,
    ) -> PumpStationTransition:
        """Select one staged transition while the caller owns the run lock."""
        transition = self._require_staged_transition_identity(staged)
        current = self.current_snapshot()
        if current == staged.snapshot:
            return transition
        if current != staged.prior_snapshot:
            _fail("stale-publication", "world run advanced after transition preparation")
        self._replace_current(
            PumpStationCurrentRunPointer(
                serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
                run_id=staged.snapshot.run_id,
                sequence=staged.snapshot.sequence,
                state_id=staged.snapshot.state_id,
                commit_id=staged.snapshot.commit_id,
            )
        )
        return transition

    def _require_staged_transition_identity(
        self,
        staged: PumpStationStagedTransition,
    ) -> PumpStationTransition:
        """Require one durable parent, commit, and next-snapshot identity chain."""
        prior = staged.prior_snapshot
        snapshot = staged.snapshot
        commit = staged.commit
        if (
            pump_station_artifact_id(commit) != snapshot.commit_id
            or commit.run_id != snapshot.run_id
            or commit.sequence != snapshot.sequence
            or commit.parent_commit_id != prior.commit_id
            or commit.state_id != snapshot.state_id
            or snapshot.snapshot_version != prior.snapshot_version
            or snapshot.run_id != prior.run_id
            or snapshot.episode_id != prior.episode_id
            or snapshot.world_branch_id != prior.world_branch_id
            or snapshot.sequence != prior.sequence + 1
        ):
            _fail("transition-integrity", "staged snapshot and commit chain differ")
        stored_commit = self.load_commit(snapshot.commit_id)
        if not isinstance(stored_commit, PumpStationWorldRunCommit) or stored_commit != commit:
            _fail("transition-integrity", "stored staged commit differs")
        parent = self.load_commit(prior.commit_id)
        if not isinstance(parent, PumpStationWorldRunCommit):
            _fail("transition-integrity", "legacy transition has a V4 parent")
        if parent.run_id != prior.run_id or parent.sequence != prior.sequence or parent.state_id != prior.state_id:
            _fail("transition-integrity", "staged prior snapshot and commit differ")
        durable_input, information_set, transition = self._load_step(commit)
        if not self._step_extends_parent(
            parent,
            commit,
            durable_input,
            information_set,
            transition,
        ):
            _fail("transition-integrity", "staged transition does not extend its parent")
        return transition

    def _require_staged_v4_identity(
        self,
        staged: PumpStationStagedTransitionV4,
    ) -> PumpStationTransitionV4:
        """Require one durable V4 parent, commit, command, and next snapshot."""
        prior = staged.prior_snapshot
        snapshot = staged.snapshot
        commit = staged.commit
        if (
            pump_station_artifact_id(commit, record_profile="v4") != snapshot.commit_id
            or commit.run_id != snapshot.run_id
            or commit.sequence != snapshot.sequence
            or commit.parent_commit_id != prior.commit_id
            or commit.state_id != snapshot.state_id
            or snapshot.snapshot_version != prior.snapshot_version
            or snapshot.run_id != prior.run_id
            or snapshot.episode_id != prior.episode_id
            or snapshot.world_branch_id != prior.world_branch_id
            or snapshot.sequence != prior.sequence + 1
        ):
            _fail("transition-integrity", "staged V4 snapshot and commit chain differ")
        if self.load_commit(snapshot.commit_id) != commit:
            _fail("transition-integrity", "stored staged V4 commit differs")
        parent = self.load_commit(prior.commit_id)
        if parent.run_id != prior.run_id or parent.sequence != prior.sequence or parent.state_id != prior.state_id:
            _fail("transition-integrity", "staged V4 prior snapshot and commit differ")
        command, proposal, information_set, transition = self._load_v4_step(commit)
        if (
            command != staged.command
            or proposal != staged.proposal
            or information_set != staged.information_set
            or transition != staged.transition
            or not self._v4_step_extends_parent(parent, commit, command, transition)
        ):
            _fail("transition-integrity", "staged V4 evidence does not extend its parent")
        return transition

    @staticmethod
    def _v4_step_extends_parent(
        parent: PumpStationWorldRunCommitRecord,
        commit: PumpStationWorldRunCommitV2,
        command: PumpStationCommandV4,
        transition: PumpStationTransitionV4,
    ) -> bool:
        """Return whether one V4 command and receipt bind their exact parent."""
        parent_content_id = pump_station_artifact_id(parent)
        return (
            commit.sequence == parent.sequence + 1
            and commit.parent_commit_id == parent_content_id
            and command.based_on_sequence == parent.sequence
            and command.base_state_id == parent.state_id
            and command.base_commit_id == parent_content_id
            and transition.receipt.sequence == commit.sequence
            and transition.receipt.before_state_id == parent.state_id
            and transition.receipt.after_state_id == commit.state_id
            and transition.receipt.request_id == command.request_id
            and transition.receipt.action_or_control_kind == command.action_name
        )

    @staticmethod
    def _step_extends_parent(
        parent: PumpStationWorldRunCommit,
        commit: PumpStationWorldRunCommit,
        durable_input: PumpStationDurableInput,
        information_set: PumpStationInformationSet | None,
        transition: PumpStationTransition,
    ) -> bool:
        """Return whether one durable step is bound to its exact parent commit."""
        parent_content_id = pump_station_artifact_id(parent)
        if (
            commit.sequence != parent.sequence + 1
            or commit.parent_commit_id != parent_content_id
            or transition.receipt.pre_state_id != parent.state_id
        ):
            return False
        if _is_control_input(durable_input):
            return (
                information_set is None
                and durable_input.based_on_sequence == parent.sequence
                and durable_input.base_state_id == parent.state_id
                and durable_input.base_commit_id == parent_content_id
            )
        proposal = cast(PumpStationProposal, durable_input)
        return (
            information_set is not None
            and isinstance(information_set.base_view, PumpStationActorView)
            and proposal.context.based_on_sequence == parent.sequence
            and information_set.base_view.current_state.state_sequence == parent.sequence
        )

    def find_committed_proposal(
        self,
        proposal_id: str,
    ) -> PumpStationWorldRunCommit | None:
        """Return a proposal commit only when it is on the selected chain."""
        for commit in reversed(self.commits()):
            if (
                isinstance(commit, PumpStationWorldRunCommit)
                and commit.proposal_id == proposal_id
                and commit.information_set_content_id is not None
            ):
                return commit
        return None

    def find_committed_control_request(
        self,
        request_id: str,
    ) -> PumpStationWorldRunCommit | None:
        """Return one selected host-control commit by idempotent request identity."""
        for commit in reversed(self.commits()):
            if (
                isinstance(commit, PumpStationWorldRunCommit)
                and commit.proposal_id == request_id
                and commit.information_set_content_id is None
                and commit.proposal_content_id is not None
            ):
                return commit
        return None

    def find_committed_v4_command(
        self,
        request_id: str,
    ) -> PumpStationWorldRunCommitV2 | None:
        """Return one selected V4 commit by its cross-surface request identity."""
        for commit in reversed(self.commits()):
            if isinstance(commit, PumpStationWorldRunCommitV2) and commit.request_id == request_id:
                return commit
        return None

    def recover_staged_v4_command(
        self,
        command: PumpStationCommandV4,
    ) -> PumpStationTransitionV4 | None:
        """Select one exact complete V4 command left durable before selection."""
        with self.locked():
            return self._recover_staged_v4_command_under_lock(command)

    def _recover_staged_v4_command_under_lock(
        self,
        command: PumpStationCommandV4,
    ) -> PumpStationTransitionV4 | None:
        """Recover one unselected V4 commit while the caller owns the run lock."""
        manifest = self.load_manifest()
        if not isinstance(manifest, PumpStationWorldRunManifestV2):
            _fail("record-versions", "legacy manifest cannot recover a V4 command")
        self._require_v4_command_scope(command, manifest)
        decode_pump_station_v4_command(command)
        matches: list[
            tuple[
                PumpStationWorldRunCommitV2,
                PumpStationProposal | None,
                PumpStationInformationSet | None,
                PumpStationTransitionV4,
            ]
        ] = []
        commits_root = self._root / "commits"
        if not commits_root.exists():
            return None
        for path in sorted(commits_root.glob("*.json")):
            commit = self.load_commit(path.stem)
            if isinstance(commit, PumpStationWorldRunCommit):
                if commit.proposal_id == command.request_id:
                    _fail(
                        "v4-command-id-conflict",
                        f"{command.request_id} is already used by a legacy transition",
                    )
                continue
            if commit.request_id != command.request_id:
                continue
            stored_command, proposal, information_set, transition = self._load_v4_step(commit)
            if stored_command != command or commit.parent_commit_id != command.base_commit_id:
                _fail(
                    "v4-command-id-conflict",
                    f"{command.request_id} has different staged content",
                )
            matches.append((commit, proposal, information_set, transition))
        if not matches:
            return None
        if len(matches) != 1:
            _fail(
                "v4-command-id-conflict",
                f"{command.request_id} has more than one durable outcome",
            )
        commit, proposal, information_set, transition = matches[0]
        parent = self.load_commit(commit.parent_commit_id)
        if not self._v4_step_extends_parent(
            parent,
            commit,
            command,
            transition,
        ):
            _fail("transition-integrity", "staged V4 recovery does not extend its parent")
        prior_snapshot = PumpStationStateSnapshotRef(
            snapshot_version=manifest.snapshot_version,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            sequence=parent.sequence,
            state_id=parent.state_id,
            commit_id=commit.parent_commit_id,
        )
        commit_id = pump_station_artifact_id(commit, record_profile="v4")
        snapshot = PumpStationStateSnapshotRef(
            snapshot_version=manifest.snapshot_version,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            sequence=commit.sequence,
            state_id=commit.state_id,
            commit_id=commit_id,
        )
        staged = PumpStationStagedTransitionV4(
            prior_snapshot=prior_snapshot,
            snapshot=snapshot,
            command=command,
            transition=transition,
            commit=commit,
            proposal=proposal,
            information_set=information_set,
        )
        return self._publish_staged_v4_transition_under_lock(staged)

    def validate_repeated_v4_command(
        self,
        commit: PumpStationWorldRunCommitV2,
        command: PumpStationCommandV4,
    ) -> PumpStationTransitionV4:
        """Return a selected V4 retry only when the complete command is identical."""
        stored_command, _, _, transition = self._load_v4_step(commit)
        if stored_command != command:
            _fail(
                "v4-command-id-conflict",
                f"{command.request_id} is already bound to different content",
            )
        return transition

    def commits(self) -> tuple[PumpStationWorldRunCommitRecord, ...]:
        """Reload the exact selected commit chain from initial state to current."""
        pointer = self._load_current()
        chain: list[PumpStationWorldRunCommitRecord] = []
        seen: set[str] = set()
        commit_id: str | None = pointer.commit_id
        while commit_id is not None:
            if commit_id in seen:
                _fail("artifact-integrity", "commit chain contains a cycle")
            seen.add(commit_id)
            commit = self.load_commit(commit_id)
            chain.append(commit)
            commit_id = commit.parent_commit_id
        chain.reverse()
        self._validate_chain(tuple(chain), pointer)
        return tuple(chain)

    def steps(self) -> tuple[PumpStationRunStep, ...]:
        """Reload every committed proposal, information set, receipt, event batch, and state."""
        steps: list[PumpStationRunStep] = []
        for commit in self.commits()[1:]:
            if not isinstance(commit, PumpStationWorldRunCommit):
                _fail("record-versions", "legacy step access selected a V4 commit")
            durable_input, information_set, transition = self._load_step(commit)
            if _is_control_input(durable_input):
                steps.append(
                    PumpStationRunStep(
                        proposal=None,
                        information_set=None,
                        transition=transition,
                        control_request=durable_input,
                    )
                )
            else:
                if information_set is None:
                    _fail(
                        "artifact-integrity",
                        "proposal commit lacks an information set",
                    )
                proposal = cast(PumpStationProposal, durable_input)
                steps.append(
                    PumpStationRunStep(
                        proposal=proposal,
                        information_set=information_set,
                        transition=transition,
                    )
                )
        return tuple(steps)

    def v4_steps(
        self,
    ) -> tuple[PumpStationRunStepV4, ...]:
        """Reload every selected V4 command and its complete transition evidence."""
        steps: list[PumpStationRunStepV4] = []
        for commit in self.commits()[1:]:
            if not isinstance(commit, PumpStationWorldRunCommitV2):
                _fail("record-versions", "V4 step access selected a legacy commit")
            command, proposal, information_set, transition = self._load_v4_step(commit)
            steps.append(
                PumpStationRunStepV4(
                    command=command,
                    proposal=proposal,
                    information_set=information_set,
                    transition=transition,
                )
            )
        return tuple(steps)

    def load_transition(
        self,
        commit: PumpStationWorldRunCommit,
    ) -> PumpStationTransition:
        """Reload the transition selected by one non-initial commit."""
        _, _, transition = self._load_step(commit)
        return transition

    def validate_repeated_proposal(
        self,
        commit: PumpStationWorldRunCommit,
        proposal: PumpStationProposal,
        information_set: PumpStationInformationSet,
    ) -> PumpStationTransition:
        """Return a committed retry only when its complete input is identical."""
        stored_input, stored_information_set, transition = self._load_step(commit)
        if _is_control_input(stored_input) or stored_input != proposal or stored_information_set != information_set:
            _fail(
                "proposal-id-conflict",
                f"{proposal.context.proposal_id} was already bound to different content",
            )
        return transition

    def validate_repeated_control_request(
        self,
        commit: PumpStationWorldRunCommit,
        request: PumpStationControlInput,
    ) -> PumpStationTransition:
        """Return one committed control retry only when its input is identical."""
        stored_input, information_set, transition = self._load_step(commit)
        if stored_input != request or information_set is not None:
            _fail(
                "control-request-id-conflict",
                f"{request.request_id} is already bound to different content",
            )
        return transition

    def recover_control_request(
        self,
        commit: PumpStationWorldRunCommit,
    ) -> tuple[PumpStationControlInput, PumpStationTransition]:
        """Reload one immutable host-control input and its transition."""
        stored_input, information_set, transition = self._load_step(commit)
        if not _is_control_input(stored_input) or information_set is not None:
            _fail("artifact-integrity", "commit is not a host-control transition")
        return stored_input, transition

    def publish_migration(self, migration: PumpStationWorldRunMigration) -> None:
        """Publish one immutable migration lineage record at the target root."""
        manifest = self.load_manifest()
        if (
            migration.target_run_id != manifest.run_id
            or migration.target_world_branch_id != manifest.world_branch_id
            or migration.target_state_id != manifest.initial_state_id
            or migration.target_snapshot_version != manifest.snapshot_version
            or migration.target_receipt_version != manifest.receipt_version
            or migration.target_authority_policy_version != manifest.authority_policy_version
            or migration.target_transition_rule_version != manifest.transition_rule_version
        ):
            _fail("migration-integrity", "migration target differs from manifest")
        self._publish_root_immutable("migration.json", migration)

    def load_migration(self) -> PumpStationWorldRunMigration:
        """Reload the immutable migration lineage for a migrated run."""
        return load_pump_station_artifact(
            self._read(self._root / "migration.json", "world-run migration"),
            PumpStationWorldRunMigration,
        )

    def _load_step(
        self,
        commit: PumpStationWorldRunCommit,
    ) -> tuple[
        PumpStationDurableInput,
        PumpStationInformationSet | None,
        PumpStationTransition,
    ]:
        if None in {
            commit.proposal_id,
            commit.proposal_content_id,
            commit.receipt_content_id,
            commit.event_batch_content_id,
        }:
            _fail("artifact-integrity", "transition commit lacks evidence references")
        control_step = commit.information_set_content_id is None
        durable_input: PumpStationDurableInput
        if control_step:
            payload = self._read_content(
                "control-requests",
                cast(str, commit.proposal_content_id),
            )
            try:
                type_name = json.loads(payload)["$type"]
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                _fail("artifact-type", f"stored control input has no valid type: {error}")
            control_type = _CONTROL_TYPES.get(type_name)
            if control_type is None:
                _fail("artifact-type", f"unknown stored control type {type_name!r}")
            durable_input = load_pump_station_artifact(payload, control_type)
            information_set = None
        else:
            durable_input = self._load_proposal(cast(str, commit.proposal_content_id))
            information_set = load_pump_station_artifact(
                self._read_content(
                    "information-sets",
                    cast(str, commit.information_set_content_id),
                ),
                PumpStationInformationSet,
            )
        receipt = load_pump_station_artifact(
            self._read_content("receipts", cast(str, commit.receipt_content_id)),
            PumpStationTransitionReceipt,
        )
        event_batch = load_pump_station_artifact(
            self._read_content(
                "events",
                cast(str, commit.event_batch_content_id),
            ),
            PumpStationAppliedEventBatch,
        )
        state = self.load_state(commit.state_id)
        if state.state_version == PUMP_STATION_STATE_VERSION_V4:
            _fail("record-versions", "legacy transition evidence selects a V4 state")
        legacy_state = cast(PumpStationLegacyStewardshipState, state)
        if (
            pump_station_artifact_id(durable_input) != commit.proposal_content_id
            or pump_station_artifact_id(receipt) != commit.receipt_content_id
            or pump_station_artifact_id(event_batch) != commit.event_batch_content_id
            or receipt.sequence != commit.sequence
            or receipt.post_state_id != commit.state_id
            or event_batch.transition_id != receipt.transition_id
            or event_batch.sequence != receipt.sequence
            or event_batch.event_ids != receipt.applied_event_ids
            or event_batch.event_types != receipt.applied_event_types
        ):
            _fail("artifact-integrity", "commit evidence does not reconcile")
        if _is_control_input(durable_input):
            if (
                information_set is not None
                or durable_input.request_id != commit.proposal_id
                or receipt.proposal_id is not None
                or not receipt.trigger.startswith("host-control:")
            ):
                _fail("artifact-integrity", "control commit evidence does not reconcile")
        else:
            proposal = cast(PumpStationProposal, durable_input)
            if (
                information_set is None
                or pump_station_artifact_id(information_set) != commit.information_set_content_id
                or proposal.context.proposal_id != commit.proposal_id
                or proposal.context.information_set_id != information_set.information_set_id
                or receipt.proposal_id != commit.proposal_id
            ):
                _fail("artifact-integrity", "proposal commit evidence does not reconcile")
        return (
            durable_input,
            information_set,
            PumpStationTransition(
                state=legacy_state,
                receipt=receipt,
            ),
        )

    def _load_v4_step(
        self,
        commit: PumpStationWorldRunCommitV2,
    ) -> tuple[
        PumpStationCommandV4,
        PumpStationProposal | None,
        PumpStationInformationSet | None,
        PumpStationTransitionV4,
    ]:
        """Reload and reconcile one strict V4 command, state, and receipt."""
        command = load_pump_station_artifact(
            self._read_content("commands", commit.command_content_id),
            PumpStationCommandV4,
            record_profile="v4",
        )
        manifest = self.load_manifest()
        if not isinstance(manifest, PumpStationWorldRunManifestV2):
            _fail("record-versions", "legacy manifest selected a V4 command")
        self._require_v4_command_scope(command, manifest)
        decode_pump_station_v4_command(command)
        proposal: PumpStationProposal | None = None
        information_set: PumpStationInformationSet | None = None
        if commit.proposal_content_id is not None:
            if commit.information_set_content_id is None:
                _fail("artifact-integrity", "V4 actor commit lacks an information set")
            proposal = self._load_proposal(
                commit.proposal_content_id,
                record_profile="v4",
            )
            information_set = load_pump_station_artifact(
                self._read_content(
                    "information-sets",
                    commit.information_set_content_id,
                ),
                PumpStationInformationSet,
                record_profile="v4",
            )
        receipt = load_pump_station_artifact(
            self._read_content("receipts", commit.receipt_content_id),
            PumpStationTransitionReceiptV4,
            record_profile="v4",
        )
        state = self.load_state(commit.state_id)
        if state.state_version != PUMP_STATION_STATE_VERSION_V4:
            _fail("record-versions", "V4 transition evidence selects a legacy state")
        coupled_state = cast(PumpStationCoupledStewardshipState, state)
        transition = PumpStationTransitionV4(
            state=coupled_state,
            receipt=receipt,
        )
        if (
            pump_station_artifact_id(command, record_profile="v4") != commit.command_content_id
            or pump_station_artifact_id(receipt, record_profile="v4") != commit.receipt_content_id
            or command.request_id != commit.request_id
            or receipt.request_id != commit.request_id
            or receipt.sequence != commit.sequence
            or receipt.after_state_id != commit.state_id
            or receipt.actor_action != (command.kind == "actor")
        ):
            _fail("artifact-integrity", "V4 commit evidence does not reconcile")
        if command.kind == "actor":
            if proposal is None or information_set is None:
                _fail("artifact-integrity", "V4 actor command lacks bound proposal evidence")
            parent = self.load_commit(commit.parent_commit_id)
            parent_state = self._load_v4_state(parent.state_id)
            self._require_v4_actor_information_set(
                manifest,
                parent_state,
                command,
                information_set,
            )
            if (
                pump_station_artifact_id(proposal, record_profile="v4") != commit.proposal_content_id
                or pump_station_artifact_id(information_set, record_profile="v4") != commit.information_set_content_id
                or proposal.context.proposal_id != command.request_id
                or proposal.context.information_set_id != information_set.information_set_id
            ):
                _fail("artifact-integrity", "V4 actor evidence does not reconcile")
        elif proposal is not None or information_set is not None:
            _fail("artifact-integrity", "V4 host control contains actor evidence")
        return command, proposal, information_set, transition

    @staticmethod
    def _require_v4_command_scope(
        command: PumpStationCommandV4,
        manifest: PumpStationWorldRunManifestV2,
    ) -> None:
        """Require one V4 command to use the immutable stored world scope."""
        observed = (
            command.task_world_id,
            command.run_id,
            command.episode_id,
            command.world_branch_id,
        )
        expected = (
            manifest.task_world_id,
            manifest.run_id,
            manifest.episode_id,
            manifest.world_branch_id,
        )
        if observed != expected:
            _fail("world-run-identity", "V4 command scope differs from the stored run")

    def _load_v4_state(
        self,
        state_id: str,
    ) -> PumpStationCoupledStewardshipState:
        """Reload one state only when it uses the registered V4 profile."""
        state = self.load_state(state_id)
        if state.state_version != PUMP_STATION_STATE_VERSION_V4:
            _fail("record-versions", "V4 command selected a legacy state")
        return cast(PumpStationCoupledStewardshipState, state)

    @staticmethod
    def _project_v4_information_set(
        manifest: PumpStationWorldRunManifestV2,
        state: PumpStationCoupledStewardshipState,
        command: PumpStationCommandV4,
    ) -> PumpStationInformationSet:
        """Rebuild the only actor information set valid for one V4 parent."""
        if command.agent_tenure_id is None:
            _fail("command-content", "V4 actor command lacks its tenure")
        return project_coupled_information_set(
            state,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            actor_id="pump-station-actor",
            agent_tenure_id=command.agent_tenure_id,
            source_artifact_ids=(
                manifest.reference_system_content_id,
                manifest.package_content_id,
                manifest.temporal_bundle_content_id,
            ),
            workspace_tool_ids=(PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID_V2,),
        )

    def _require_v4_actor_information_set(
        self,
        manifest: PumpStationWorldRunManifestV2,
        state: PumpStationCoupledStewardshipState,
        command: PumpStationCommandV4,
        information_set: PumpStationInformationSet,
    ) -> None:
        """Reconcile dynamic session context with one deterministic V4 view."""
        if command.session_binding_id is None:
            _fail("artifact-integrity", "V4 actor command lacks a session binding")
        session_binding = self._load_session_binding(
            command.session_binding_id,
            manifest,
        )
        expected = self._project_v4_information_set(manifest, state, command)
        view = information_set.base_view
        if not isinstance(view, PumpStationCoupledActorView):
            _fail("artifact-integrity", "V4 actor information set has a legacy view")
        if (
            session_binding.session_id != command.session_id
            or session_binding.agent_tenure_id != command.agent_tenure_id
            or session_binding.sequence != command.based_on_sequence
            or session_binding.state_id != command.base_state_id
            or session_binding.commit_id != command.base_commit_id
            or session_binding.actor_view_id != command.actor_view_id
            or view != expected.base_view
            or information_set.information_set_id != command.information_set_id
            or bind_information_set(
                view,
                information_set.observation_history,
                information_set.current_context,
            )
            != information_set
            or information_set.current_context.workspace_tool_ids != (PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID_V2,)
            or not set(view.source_artifact_ids).issubset(
                information_set.current_context.visible_material_ids,
            )
        ):
            _fail(
                "artifact-integrity",
                "V4 actor session, view, or information-set evidence differs",
            )

    def _load_proposal(
        self,
        content_id: str,
        *,
        record_profile: str | None = None,
    ) -> PumpStationProposal:
        payload = self._read_content("proposals", content_id)
        try:
            document = json.loads(payload)
            type_name = document["$type"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            _fail("artifact-type", f"stored proposal has no valid type: {error}")
        proposal_type = _PROPOSAL_TYPES.get(type_name)
        if proposal_type is None:
            _fail("artifact-type", f"unknown stored proposal type {type_name!r}")
        return cast(
            PumpStationProposal,
            load_pump_station_artifact(
                payload,
                proposal_type,
                record_profile=record_profile,
            ),
        )

    def _reject_proposal_collision(
        self,
        proposal: PumpStationProposal,
        *,
        information_set: PumpStationInformationSet,
        parent_commit_id: str,
    ) -> None:
        commits_root = self._root / "commits"
        if not commits_root.exists():
            return
        for path in commits_root.glob("*.json"):
            commit = self.load_commit(path.stem)
            if isinstance(commit, PumpStationWorldRunCommitV2):
                if commit.request_id == proposal.context.proposal_id:
                    _fail(
                        "proposal-id-conflict",
                        f"{proposal.context.proposal_id} is already used by a V4 transition",
                    )
                continue
            if commit.proposal_id != proposal.context.proposal_id:
                continue
            stored_input, stored_information_set, _ = self._load_step(commit)
            if (
                stored_input != proposal
                or stored_information_set != information_set
                or commit.parent_commit_id != parent_commit_id
            ):
                _fail(
                    "proposal-id-conflict",
                    f"{proposal.context.proposal_id} has different staged content",
                )

    def _reject_control_collision(
        self,
        request: PumpStationControlInput,
        *,
        parent_commit_id: str,
    ) -> None:
        commits_root = self._root / "commits"
        if not commits_root.exists():
            return
        for path in commits_root.glob("*.json"):
            commit = self.load_commit(path.stem)
            if isinstance(commit, PumpStationWorldRunCommitV2):
                if commit.request_id == request.request_id:
                    _fail(
                        "control-request-id-conflict",
                        f"{request.request_id} is already used by a V4 transition",
                    )
                continue
            if commit.proposal_id != request.request_id:
                continue
            stored_input, information_set, _ = self._load_step(commit)
            if stored_input != request or information_set is not None or commit.parent_commit_id != parent_commit_id:
                _fail(
                    "control-request-id-conflict",
                    f"{request.request_id} has different staged content",
                )

    def _reject_v4_command_collision(
        self,
        command: PumpStationCommandV4,
        *,
        parent_commit_id: str,
    ) -> None:
        """Reject reuse of one V4 request identity for changed staged content."""
        commits_root = self._root / "commits"
        if not commits_root.exists():
            return
        for path in commits_root.glob("*.json"):
            commit = self.load_commit(path.stem)
            if isinstance(commit, PumpStationWorldRunCommit):
                if commit.proposal_id == command.request_id:
                    _fail(
                        "v4-command-id-conflict",
                        f"{command.request_id} is already used by a legacy transition",
                    )
                continue
            if commit.request_id != command.request_id:
                continue
            stored, _, _, _ = self._load_v4_step(commit)
            if stored == command and commit.parent_commit_id == parent_commit_id:
                _fail(
                    "v4-command-already-staged",
                    f"{command.request_id} already has one durable staged outcome",
                )
            else:
                _fail(
                    "v4-command-id-conflict",
                    f"{command.request_id} has different staged content",
                )

    def _validate_chain(
        self,
        chain: tuple[PumpStationWorldRunCommitRecord, ...],
        pointer: PumpStationCurrentRunPointer,
    ) -> None:
        if (
            not chain
            or chain[0].sequence != self.load_manifest().initial_sequence
            or chain[0].parent_commit_id is not None
        ):
            _fail("artifact-integrity", "commit chain lacks one initial state")
        manifest = self.load_manifest()
        if chain[0].state_id != manifest.initial_state_id:
            _fail("artifact-integrity", "initial commit differs from manifest")
        previous: PumpStationWorldRunCommitRecord = chain[0]
        for commit in chain[1:]:
            valid = False
            if isinstance(commit, PumpStationWorldRunCommitV2):
                if not isinstance(manifest, PumpStationWorldRunManifestV2):
                    _fail("record-versions", "legacy manifest selected a V4 commit")
                command, _, _, transition_v4 = self._load_v4_step(commit)
                valid = self._v4_step_extends_parent(
                    previous,
                    commit,
                    command,
                    transition_v4,
                )
            elif isinstance(previous, PumpStationWorldRunCommit):
                durable_input, information_set, transition = self._load_step(commit)
                valid = self._step_extends_parent(
                    previous,
                    commit,
                    durable_input,
                    information_set,
                    transition,
                )
            if not valid:
                _fail("artifact-integrity", "commit does not extend its parent")
            previous = commit
        if (
            previous.sequence != pointer.sequence
            or previous.state_id != pointer.state_id
            or pump_station_artifact_id(previous) != pointer.commit_id
        ):
            _fail("artifact-integrity", "commit chain does not reach current pointer")

    def _require_v4_session_manifest(self) -> PumpStationWorldRunManifestV2:
        manifest = self.load_manifest()
        if not isinstance(manifest, PumpStationWorldRunManifestV2):
            _fail("record-versions", "session activation requires a registered V4 run")
        return manifest

    @staticmethod
    def _require_session_activation_scope(
        binding: PumpStationSessionActivationBinding,
        manifest: PumpStationWorldRunManifestV2,
    ) -> None:
        observed = (
            binding.run_id,
            binding.episode_id,
            binding.world_branch_id,
        )
        expected = (
            manifest.run_id,
            manifest.episode_id,
            manifest.world_branch_id,
        )
        if observed != expected:
            _fail(
                "session-activation-scope",
                "session binding belongs to another world run",
            )

    def _require_current_session_snapshot(
        self,
        binding: PumpStationSessionActivationBinding,
    ) -> None:
        current = self.current_snapshot()
        observed = (
            binding.sequence,
            binding.state_id,
            binding.commit_id,
        )
        expected = (
            current.sequence,
            current.state_id,
            current.commit_id,
        )
        if observed != expected:
            _fail(
                "session-activation-stale",
                "session binding does not use the selected world snapshot",
            )

    def _selected_session_activation_if_present(
        self,
        manifest: PumpStationWorldRunManifestV2,
    ) -> tuple[PumpStationActiveSessionPointer, PumpStationSessionActivationBinding] | None:
        pointer_path = self._root / _SESSION_AUTHORITY_ROOT / _ACTIVE_SESSION_POINTER_NAME
        if not pointer_path.exists() and not pointer_path.is_symlink():
            return None
        pointer = load_pump_station_artifact(
            self._read(pointer_path, "active session pointer"),
            PumpStationActiveSessionPointer,
            record_profile="v4",
        )
        if (
            pointer.run_id,
            pointer.episode_id,
            pointer.world_branch_id,
        ) != (
            manifest.run_id,
            manifest.episode_id,
            manifest.world_branch_id,
        ):
            _fail(
                "session-activation-scope",
                "active session pointer belongs to another world run",
            )
        binding = self._load_session_binding(pointer.active_binding_id, manifest)
        if (
            pointer.active_activation_id != binding.active_activation_id
            or pointer.session_event_sequence != binding.session_event_sequence
        ):
            _fail(
                "artifact-integrity",
                "active session pointer and binding differ",
            )
        claim = self._load_session_activation_claim(binding.active_activation_id)
        if claim.binding_id != binding.binding_id:
            _fail(
                "artifact-integrity",
                "active session claim and binding differ",
            )
        return pointer, binding

    def _load_session_binding(
        self,
        binding_id: str,
        manifest: PumpStationWorldRunManifestV2,
    ) -> PumpStationSessionActivationBinding:
        try:
            validate_sha256(binding_id)
        except ValueError as error:
            _fail("artifact-type", f"invalid session binding identity: {error}")
        binding = load_pump_station_artifact(
            self._read(
                self._root / _SESSION_BINDING_COLLECTION / f"{binding_id}.json",
                f"session binding {binding_id}",
            ),
            PumpStationSessionActivationBinding,
            record_profile="v4",
        )
        if binding.binding_id != binding_id:
            _fail(
                "artifact-integrity",
                f"session binding identity differs for {binding_id}",
            )
        self._require_session_activation_scope(binding, manifest)
        return binding

    @staticmethod
    def _session_activation_claim_key(active_activation_id: str) -> str:
        return hashlib.sha256(active_activation_id.encode("utf-8")).hexdigest()

    def _session_activation_claim_path(self, active_activation_id: str) -> Path:
        claim_key = self._session_activation_claim_key(active_activation_id)
        return self._root / _SESSION_ACTIVATION_CLAIM_COLLECTION / f"{claim_key}.json"

    def _load_session_activation_claim(
        self,
        active_activation_id: str,
    ) -> PumpStationSessionActivationClaim:
        claim = load_pump_station_artifact(
            self._read(
                self._session_activation_claim_path(active_activation_id),
                f"session activation claim {active_activation_id}",
            ),
            PumpStationSessionActivationClaim,
            record_profile="v4",
        )
        if claim.active_activation_id != active_activation_id:
            _fail(
                "artifact-integrity",
                "session activation claim identity differs",
            )
        return claim

    def _require_session_activation_claim(
        self,
        expected: PumpStationSessionActivationClaim,
    ) -> None:
        path = self._session_activation_claim_path(expected.active_activation_id)
        if not path.exists() and not path.is_symlink():
            return
        observed = self._load_session_activation_claim(expected.active_activation_id)
        if observed != expected:
            _fail(
                "session-activation-conflict",
                f"{expected.active_activation_id} already selects another binding",
            )

    def _publish_session_binding(
        self,
        binding: PumpStationSessionActivationBinding,
    ) -> None:
        payload = pump_station_artifact_bytes(binding, record_profile="v4")
        if hashlib.sha256(payload).hexdigest() != binding.binding_id:
            _fail("artifact-integrity", "session binding content identity differs")
        self._publish_immutable(
            self._root / _SESSION_BINDING_COLLECTION / f"{binding.binding_id}.json",
            payload,
        )

    def _publish_session_activation_claim(
        self,
        claim: PumpStationSessionActivationClaim,
    ) -> None:
        self._publish_immutable(
            self._session_activation_claim_path(claim.active_activation_id),
            pump_station_artifact_bytes(claim, record_profile="v4"),
        )

    def _replace_active_session_pointer(
        self,
        pointer: PumpStationActiveSessionPointer,
    ) -> None:
        try:
            replace_file_bytes_durable(
                self._root / _SESSION_AUTHORITY_ROOT,
                _ACTIVE_SESSION_POINTER_NAME,
                pump_station_artifact_bytes(pointer, record_profile="v4"),
                host_private=True,
            )
        except DurableFileReplaceConfinementError as error:
            _fail("artifact-confinement", f"active session pointer is unsafe: {error}")
        except DurableFileReplaceError as error:
            _fail(
                "artifact-integrity",
                f"active session pointer cannot be replaced: {error}",
            )

    def _structured_handover_path(self, handover_id: str) -> Path:
        return self._root / _SESSION_HANDOVER_COLLECTION / f"{handover_id}.json"

    def _load_structured_handover(
        self,
        handover_id: str,
        manifest: PumpStationWorldRunManifestV2,
    ) -> PumpStationStructuredHandoverV4:
        try:
            validate_sha256(handover_id)
        except ValueError as error:
            _fail("artifact-type", f"invalid structured handover identity: {error}")
        handover = load_pump_station_artifact(
            self._read(
                self._structured_handover_path(handover_id),
                f"structured handover {handover_id}",
            ),
            PumpStationStructuredHandoverV4,
            record_profile="v4",
        )
        if handover.handover_id != handover_id:
            _fail(
                "artifact-integrity",
                f"structured handover identity differs for {handover_id}",
            )
        self._require_structured_handover_record(handover, manifest)
        return handover

    def _require_structured_handover_record(
        self,
        handover: PumpStationStructuredHandoverV4,
        manifest: PumpStationWorldRunManifestV2,
    ) -> None:
        self._require_structured_handover_scope(handover, manifest)
        commit = self.load_commit(handover.commit_id)
        if (
            commit.run_id != handover.run_id
            or commit.sequence != handover.sequence
            or commit.state_id != handover.state_id
        ):
            _fail(
                "artifact-integrity",
                "structured handover commit and world position differ",
            )
        state = self._load_v4_state(handover.state_id)
        expected_view = project_coupled_information_set(
            state,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            actor_id="pump-station-actor",
            agent_tenure_id=handover.to_tenure_id,
            source_artifact_ids=(
                manifest.reference_system_content_id,
                manifest.package_content_id,
                manifest.temporal_bundle_content_id,
            ),
            workspace_tool_ids=(PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID_V2,),
        ).base_view
        if handover.current_actor_view != expected_view:
            _fail(
                "artifact-integrity",
                "structured handover view differs from the deterministic projection",
            )
        expected_history = tuple(
            actor_history_entry_v4(step.transition, step.proposal)
            for step in self.v4_steps()
            if step.proposal is not None and step.transition.receipt.sequence <= handover.sequence
        )[-handover.maximum_history_entries :]
        if handover.history != expected_history:
            _fail(
                "artifact-integrity",
                "structured handover history differs from selected actor transitions",
            )
        source = self._load_session_binding(
            handover.from_session_binding_id,
            manifest,
        )
        recipient = self._load_session_binding(
            handover.to_session_binding_id,
            manifest,
        )
        if (
            source.session_id != handover.from_session_id
            or source.agent_tenure_id != handover.from_tenure_id
            or recipient.session_id != handover.to_session_id
            or recipient.agent_tenure_id != handover.to_tenure_id
            or recipient.actor_view_id != handover.current_actor_view.view_id
            or recipient.state_id != handover.state_id
            or recipient.commit_id != handover.commit_id
            or recipient.sequence != handover.sequence
            or recipient.prior_binding_id != source.binding_id
            or recipient.session_event_sequence != source.session_event_sequence + 1
            or recipient.host_authority_id != source.host_authority_id
        ):
            _fail(
                "structured-handover-session",
                "structured handover session bindings differ from its content",
            )

    @staticmethod
    def _require_structured_handover_scope(
        handover: PumpStationStructuredHandoverV4,
        manifest: PumpStationWorldRunManifestV2,
    ) -> None:
        if (
            handover.run_id,
            handover.episode_id,
            handover.world_branch_id,
        ) != (
            manifest.run_id,
            manifest.episode_id,
            manifest.world_branch_id,
        ):
            _fail(
                "structured-handover-scope",
                "structured handover belongs to another world run",
            )

    def _require_current_structured_handover_snapshot(
        self,
        handover: PumpStationStructuredHandoverV4,
    ) -> None:
        current = self.current_snapshot()
        if (
            handover.sequence,
            handover.state_id,
            handover.commit_id,
        ) != (
            current.sequence,
            current.state_id,
            current.commit_id,
        ):
            _fail(
                "structured-handover-stale",
                "structured handover does not use the selected world snapshot",
            )

    def _require_selected_structured_handover_session(
        self,
        handover: PumpStationStructuredHandoverV4,
        manifest: PumpStationWorldRunManifestV2,
    ) -> None:
        active = self._selected_session_activation_if_present(manifest)
        if active is None:
            _fail(
                "structured-handover-session",
                "structured handover has no selected recipient session",
            )
        _, recipient = active
        if recipient.binding_id != handover.to_session_binding_id:
            _fail(
                "structured-handover-session",
                "structured handover recipient session is not selected",
            )

    def _publish_state(self, state: PumpStationStewardshipStateRecord) -> str:
        state_id = stewardship_state_id(state)
        self._publish_content("states", state_id, state)
        return state_id

    def _publish_content(
        self,
        collection: str,
        content_id: str,
        value: object,
        *,
        record_profile: str | None = None,
    ) -> None:
        payload = pump_station_artifact_bytes(
            value,
            record_profile=record_profile,
        )
        if collection != "states" and hashlib.sha256(payload).hexdigest() != content_id:
            _fail("artifact-integrity", f"{collection} content identity differs")
        path = self._root / collection / f"{content_id}.json"
        self._publish_immutable(path, payload)

    def _publish_root_immutable(self, name: str, value: object) -> None:
        self._publish_immutable(self._root / name, pump_station_artifact_bytes(value))

    def _publish_immutable(self, path: Path, payload: bytes) -> None:
        relative_path = path.relative_to(self._root).as_posix()
        try:
            self._artifacts.publish_bytes(relative_path, payload)
        except ImmutableArtifactCollisionError:
            _fail("artifact-collision", relative_path)
        except ImmutableArtifactConfinementError as error:
            _fail("artifact-confinement", f"{relative_path} is unsafe: {error}")
        except ImmutableArtifactStoreError as error:
            _fail("artifact-integrity", f"{relative_path} cannot be published: {error}")

    def _replace_current(self, pointer: PumpStationCurrentRunPointer) -> None:
        payload = pump_station_artifact_bytes(pointer)
        try:
            replace_file_bytes_durable(
                self._root,
                "current.json",
                payload,
                host_private=True,
            )
        except DurableFileReplaceConfinementError as error:
            _fail("artifact-confinement", f"current pointer is unsafe: {error}")
        except DurableFileReplaceError as error:
            _fail("artifact-integrity", f"current pointer cannot be replaced: {error}")

    def _load_current(self) -> PumpStationCurrentRunPointer:
        return load_pump_station_artifact(
            self._read(self._root / "current.json", "current pointer"),
            PumpStationCurrentRunPointer,
        )

    def _read_content(self, collection: str, content_id: str) -> bytes:
        return self._read(
            self._root / collection / f"{content_id}.json",
            f"{collection}/{content_id}.json",
        )

    def _read(self, path: Path, label: str) -> bytes:
        relative_path = path.relative_to(self._root).as_posix()
        try:
            return self._artifacts.load_bytes(relative_path)
        except ImmutableArtifactConfinementError as error:
            _fail("artifact-confinement", f"{label} is unsafe: {error}")
        except ImmutableArtifactStoreError as error:
            _fail("artifact-integrity", f"{label} cannot be read: {error}")
        raise AssertionError("unreachable")

    @staticmethod
    def _snapshot(
        manifest: PumpStationWorldRunManifestRecord,
        pointer: PumpStationCurrentRunPointer,
    ) -> PumpStationStateSnapshotRef:
        return PumpStationStateSnapshotRef(
            snapshot_version=manifest.snapshot_version,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            sequence=pointer.sequence,
            state_id=pointer.state_id,
            commit_id=pointer.commit_id,
        )
