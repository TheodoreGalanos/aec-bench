# ABOUTME: Publishes one pump-station run to a host-supplied filesystem root.
# ABOUTME: Owns immutable evidence, file locking, atomic current-state selection, and strict reload.

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NoReturn, TypeGuard, cast

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
    CancelProcess,
    ContinueOperation,
    PumpStationProposal,
    PumpStationStewardshipState,
    PumpStationTransition,
    PumpStationTransitionReceipt,
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
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_SERIALIZATION_VERSION,
    PumpStationAppliedEventBatch,
    PumpStationCurrentRunPointer,
    PumpStationStagedTransition,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunCommit,
    PumpStationWorldRunError,
    PumpStationWorldRunManifest,
    PumpStationWorldRunMigration,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
    pump_station_artifact_id,
)

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
        manifest: PumpStationWorldRunManifest,
        initial_state: PumpStationStewardshipState,
    ) -> PumpStationStateSnapshotRef:
        """Publish an immutable initial state and select it atomically."""
        with self.locked():
            if stewardship_state_id(initial_state) != manifest.initial_state_id:
                _fail("world-run-identity", "initial state differs from manifest")
            expected_state_version = {
                "pump-station-state-snapshot.v1": "pump-station-stewardship-state.v1",
                "pump-station-state-snapshot.v2": "pump-station-stewardship-state.v2",
                "pump-station-state-snapshot.v3": "pump-station-stewardship-state.v3",
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
            pointer = PumpStationCurrentRunPointer(
                serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
                run_id=manifest.run_id,
                sequence=manifest.initial_sequence,
                state_id=manifest.initial_state_id,
                commit_id=commit_id,
            )
            self._replace_current(pointer)
            return self._snapshot(manifest, pointer)

    def load_manifest(self) -> PumpStationWorldRunManifest:
        """Reload the immutable run identity."""
        return load_pump_station_artifact(
            self._read(self._root / "manifest.json", "world-run manifest"),
            PumpStationWorldRunManifest,
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

    def load_state(self, state_id: str) -> PumpStationStewardshipState:
        """Reload a complete state and verify its semantic identity."""
        state = load_pump_station_artifact(
            self._read_content("states", state_id),
            PumpStationStewardshipState,
        )
        if stewardship_state_id(state) != state_id:
            _fail("artifact-integrity", f"state identity differs for {state_id}")
        return state

    def load_commit(self, commit_id: str) -> PumpStationWorldRunCommit:
        """Reload one immutable commit by content identity."""
        commit = load_pump_station_artifact(
            self._read_content("commits", commit_id),
            PumpStationWorldRunCommit,
        )
        if pump_station_artifact_id(commit) != commit_id:
            _fail("artifact-integrity", f"commit identity differs for {commit_id}")
        return commit

    def snapshot_for_commit(
        self,
        commit: PumpStationWorldRunCommit,
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
        manifest: PumpStationWorldRunManifest,
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
        manifest: PumpStationWorldRunManifest,
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

    def publish_staged_transition(
        self,
        staged: PumpStationStagedTransition,
    ) -> PumpStationTransition:
        """Lock and select a fully staged transition with one pointer replacement."""
        with self.locked():
            return self._publish_staged_transition_under_lock(staged)

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
        if self.load_commit(snapshot.commit_id) != commit:
            _fail("transition-integrity", "stored staged commit differs")
        parent = self.load_commit(prior.commit_id)
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
            and proposal.context.based_on_sequence == parent.sequence
            and information_set.base_view.current_state.state_sequence == parent.sequence
        )

    def find_committed_proposal(
        self,
        proposal_id: str,
    ) -> PumpStationWorldRunCommit | None:
        """Return a proposal commit only when it is on the selected chain."""
        for commit in reversed(self.commits()):
            if commit.proposal_id == proposal_id and commit.information_set_content_id is not None:
                return commit
        return None

    def find_committed_control_request(
        self,
        request_id: str,
    ) -> PumpStationWorldRunCommit | None:
        """Return one selected host-control commit by idempotent request identity."""
        for commit in reversed(self.commits()):
            if (
                commit.proposal_id == request_id
                and commit.information_set_content_id is None
                and commit.proposal_content_id is not None
            ):
                return commit
        return None

    def commits(self) -> tuple[PumpStationWorldRunCommit, ...]:
        """Reload the exact selected commit chain from initial state to current."""
        pointer = self._load_current()
        chain: list[PumpStationWorldRunCommit] = []
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
                state=state,
                receipt=receipt,
            ),
        )

    def _load_proposal(self, content_id: str) -> PumpStationProposal:
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
            load_pump_station_artifact(payload, proposal_type),
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
            if commit.proposal_id != request.request_id:
                continue
            stored_input, information_set, _ = self._load_step(commit)
            if stored_input != request or information_set is not None or commit.parent_commit_id != parent_commit_id:
                _fail(
                    "control-request-id-conflict",
                    f"{request.request_id} has different staged content",
                )

    def _validate_chain(
        self,
        chain: tuple[PumpStationWorldRunCommit, ...],
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
        previous = chain[0]
        for commit in chain[1:]:
            durable_input, information_set, transition = self._load_step(commit)
            if not self._step_extends_parent(
                previous,
                commit,
                durable_input,
                information_set,
                transition,
            ):
                _fail("artifact-integrity", "commit does not extend its parent")
            previous = commit
        if (
            previous.sequence != pointer.sequence
            or previous.state_id != pointer.state_id
            or pump_station_artifact_id(previous) != pointer.commit_id
        ):
            _fail("artifact-integrity", "commit chain does not reach current pointer")

    def _publish_state(self, state: PumpStationStewardshipState) -> str:
        state_id = stewardship_state_id(state)
        self._publish_content("states", state_id, state)
        return state_id

    def _publish_content(self, collection: str, content_id: str, value: object) -> None:
        payload = pump_station_artifact_bytes(value)
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
        manifest: PumpStationWorldRunManifest,
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
