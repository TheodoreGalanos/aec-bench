# ABOUTME: Publishes one current pump-station run to a host-supplied filesystem root.
# ABOUTME: Owns immutable evidence, locking, atomic state selection, recovery, and replay loading.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NoReturn, cast

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
    PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    project_coupled_information_set,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_state_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    CancelProcess,
    ContinueOperation,
    PumpStationCoupledStewardshipState,
    PumpStationCoupledTransition,
    PumpStationCoupledTransitionReceipt,
    PumpStationProposal,
    PumpStationStewardshipState,
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
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationCoupledRunStep,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationCoupledActorView,
    PumpStationInformationSet,
    bind_information_set,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_commands import (
    decode_pump_station_command,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_POINTER_RECORD_VERSION,
    PumpStationCommand,
    PumpStationCommandCommit,
    PumpStationCommit,
    PumpStationCurrentRunPointer,
    PumpStationRegisteredWorldRunManifest,
    PumpStationStagedCommand,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunCommit,
    PumpStationWorldRunError,
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
        RequestDutyAssignment,
        RequestInspection,
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


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationWorldRunError(code, detail)


class PumpStationWorldRunRepository:
    """A confined durable repository for exactly one current pump-station run."""

    def __init__(self, root: Path) -> None:
        selected = Path(root)
        if selected.exists() and (selected.is_symlink() or not selected.is_dir()):
            _fail("artifact-confinement", "world-run root must be a plain directory")
        mkdir_durable(selected, created_mode=0o700)
        selected.chmod(0o700)
        self._root = selected.resolve(strict=True)
        try:
            self._artifacts = ImmutableByteStore(self._root, host_private=True)
        except ImmutableArtifactConfinementError as error:
            _fail("artifact-confinement", f"world-run root is unsafe: {error}")
        except ImmutableArtifactStoreError as error:
            _fail("artifact-integrity", f"world-run byte store is unavailable: {error}")

    @property
    def root(self) -> Path:
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
        manifest: PumpStationRegisteredWorldRunManifest,
        initial_state: PumpStationCoupledStewardshipState,
        *,
        before_select: Callable[[], None] | None = None,
    ) -> PumpStationStateSnapshotRef:
        """Publish the current opening state and select it atomically."""
        with self.locked():
            if stewardship_state_id(initial_state) != manifest.initial_state_id:
                _fail("world-run-identity", "initial state differs from manifest")
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
                serialization_version=PUMP_STATION_POINTER_RECORD_VERSION,
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
                serialization_version=PUMP_STATION_POINTER_RECORD_VERSION,
                run_id=manifest.run_id,
                sequence=manifest.initial_sequence,
                state_id=manifest.initial_state_id,
                commit_id=commit_id,
            )
            self._replace_current(pointer)
            return self._snapshot(manifest, pointer)

    def load_manifest(self) -> PumpStationRegisteredWorldRunManifest:
        return load_pump_station_artifact(
            self._read(self._root / "manifest.json", "world-run manifest"),
            PumpStationRegisteredWorldRunManifest,
        )

    def current_snapshot(self) -> PumpStationStateSnapshotRef:
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

    def load_state(self, state_id: str) -> PumpStationCoupledStewardshipState:
        state = load_pump_station_artifact(
            self._read_content("states", state_id),
            PumpStationStewardshipState,
        )
        if stewardship_state_id(state) != state_id:
            _fail("artifact-integrity", f"state identity differs for {state_id}")
        return state

    def load_commit(self, commit_id: str) -> PumpStationCommit:
        commit = cast(
            PumpStationCommit,
            load_pump_station_artifact(
                self._read_content("commits", commit_id),
                PumpStationWorldRunCommit | PumpStationCommandCommit,
            ),
        )
        if pump_station_artifact_id(commit) != commit_id:
            _fail("artifact-integrity", f"commit identity differs for {commit_id}")
        return commit

    def snapshot_for_commit(self, commit: PumpStationCommit) -> PumpStationStateSnapshotRef:
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

    def stage_command_transition(
        self,
        *,
        manifest: PumpStationRegisteredWorldRunManifest,
        prior_snapshot: PumpStationStateSnapshotRef,
        command: PumpStationCommand,
        transition: PumpStationCoupledTransition,
        proposal: PumpStationProposal | None = None,
        information_set: PumpStationInformationSet | None = None,
    ) -> PumpStationStagedCommand:
        """Publish complete current command evidence without selecting its state."""
        if self.load_manifest() != manifest:
            _fail("world-run-identity", "caller manifest differs from the stored run")
        self._require_command_scope(command, manifest)
        decode_pump_station_command(command)
        receipt = transition.receipt
        actor_step = command.kind == "actor"
        if (
            command.based_on_sequence != prior_snapshot.sequence
            or command.base_state_id != prior_snapshot.state_id
            or command.base_commit_id != prior_snapshot.commit_id
            or receipt.sequence != prior_snapshot.sequence + 1
            or receipt.before_state_id != prior_snapshot.state_id
            or receipt.after_state_id != stewardship_state_id(transition.state)
            or receipt.request_id != command.request_id
            or receipt.action_or_control_kind != command.action_name
            or receipt.actor_action != actor_step
            or actor_step != (proposal is not None and information_set is not None)
        ):
            _fail("transition-integrity", "transition does not extend the selected state")
        if actor_step:
            assert proposal is not None
            assert information_set is not None
            self._require_actor_information_set(
                manifest,
                self.load_state(prior_snapshot.state_id),
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
                _fail("transition-integrity", "actor evidence bindings differ")
        self._reject_command_collision(command, parent_commit_id=prior_snapshot.commit_id)
        state_id = self._publish_state(transition.state)
        command_content_id = pump_station_artifact_id(command)
        receipt_content_id = pump_station_artifact_id(receipt)
        proposal_content_id: str | None = None
        information_set_content_id: str | None = None
        self._publish_content("commands", command_content_id, command)
        if proposal is not None and information_set is not None:
            proposal_content_id = pump_station_artifact_id(proposal)
            information_set_content_id = pump_station_artifact_id(information_set)
            self._publish_content("proposals", proposal_content_id, proposal)
            self._publish_content(
                "information-sets",
                information_set_content_id,
                information_set,
            )
        self._publish_content("receipts", receipt_content_id, receipt)
        commit = PumpStationCommandCommit(
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
        commit_id = pump_station_artifact_id(commit)
        self._publish_content("commits", commit_id, commit)
        return PumpStationStagedCommand(
            prior_snapshot=prior_snapshot,
            snapshot=PumpStationStateSnapshotRef(
                snapshot_version=manifest.snapshot_version,
                run_id=manifest.run_id,
                episode_id=manifest.episode_id,
                world_branch_id=manifest.world_branch_id,
                sequence=receipt.sequence,
                state_id=state_id,
                commit_id=commit_id,
            ),
            command=command,
            transition=transition,
            commit=commit,
            proposal=proposal,
            information_set=information_set,
        )

    def publish_staged_command(self, staged: PumpStationStagedCommand) -> PumpStationCoupledTransition:
        with self.locked():
            return self._publish_staged_command_under_lock(staged)

    def _publish_staged_command_under_lock(
        self,
        staged: PumpStationStagedCommand,
    ) -> PumpStationCoupledTransition:
        transition = self._require_staged_command_identity(staged)
        current = self.current_snapshot()
        if current == staged.snapshot:
            return transition
        if current != staged.prior_snapshot:
            _fail("stale-publication", "world run advanced after transition preparation")
        self._replace_current(
            PumpStationCurrentRunPointer(
                serialization_version=PUMP_STATION_POINTER_RECORD_VERSION,
                run_id=staged.snapshot.run_id,
                sequence=staged.snapshot.sequence,
                state_id=staged.snapshot.state_id,
                commit_id=staged.snapshot.commit_id,
            )
        )
        return transition

    def _require_staged_command_identity(
        self,
        staged: PumpStationStagedCommand,
    ) -> PumpStationCoupledTransition:
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
        command, proposal, information_set, transition = self._load_command_step(commit)
        if (
            command != staged.command
            or proposal != staged.proposal
            or information_set != staged.information_set
            or transition != staged.transition
            or not self._command_step_extends_parent(parent, commit, command, transition)
        ):
            _fail("transition-integrity", "staged evidence does not extend its parent")
        return transition

    @staticmethod
    def _command_step_extends_parent(
        parent: PumpStationCommit,
        commit: PumpStationCommandCommit,
        command: PumpStationCommand,
        transition: PumpStationCoupledTransition,
    ) -> bool:
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

    def find_committed_command(self, request_id: str) -> PumpStationCommandCommit | None:
        for commit in reversed(self.commits()):
            if isinstance(commit, PumpStationCommandCommit) and commit.request_id == request_id:
                return commit
        return None

    def recover_staged_command(self, command: PumpStationCommand) -> PumpStationCoupledTransition | None:
        with self.locked():
            return self._recover_staged_command_under_lock(command)

    def _recover_staged_command_under_lock(
        self,
        command: PumpStationCommand,
    ) -> PumpStationCoupledTransition | None:
        manifest = self.load_manifest()
        self._require_command_scope(command, manifest)
        decode_pump_station_command(command)
        matches: list[
            tuple[
                PumpStationCommandCommit,
                PumpStationProposal | None,
                PumpStationInformationSet | None,
                PumpStationCoupledTransition,
            ]
        ] = []
        commits_root = self._root / "commits"
        if not commits_root.exists():
            return None
        for path in sorted(commits_root.glob("*.json")):
            commit = self.load_commit(path.stem)
            if not isinstance(commit, PumpStationCommandCommit) or commit.request_id != command.request_id:
                continue
            stored_command, proposal, information_set, transition = self._load_command_step(commit)
            if stored_command != command or commit.parent_commit_id != command.base_commit_id:
                _fail("command-id-conflict", f"{command.request_id} has different staged content")
            matches.append((commit, proposal, information_set, transition))
        if not matches:
            return None
        if len(matches) != 1:
            _fail("command-id-conflict", f"{command.request_id} has more than one durable outcome")
        commit, proposal, information_set, transition = matches[0]
        parent = self.load_commit(commit.parent_commit_id)
        if not self._command_step_extends_parent(parent, commit, command, transition):
            _fail("transition-integrity", "staged recovery does not extend its parent")
        staged = PumpStationStagedCommand(
            prior_snapshot=PumpStationStateSnapshotRef(
                snapshot_version=manifest.snapshot_version,
                run_id=manifest.run_id,
                episode_id=manifest.episode_id,
                world_branch_id=manifest.world_branch_id,
                sequence=parent.sequence,
                state_id=parent.state_id,
                commit_id=commit.parent_commit_id,
            ),
            snapshot=PumpStationStateSnapshotRef(
                snapshot_version=manifest.snapshot_version,
                run_id=manifest.run_id,
                episode_id=manifest.episode_id,
                world_branch_id=manifest.world_branch_id,
                sequence=commit.sequence,
                state_id=commit.state_id,
                commit_id=pump_station_artifact_id(commit),
            ),
            command=command,
            transition=transition,
            commit=commit,
            proposal=proposal,
            information_set=information_set,
        )
        return self._publish_staged_command_under_lock(staged)

    def validate_repeated_command(
        self,
        commit: PumpStationCommandCommit,
        command: PumpStationCommand,
    ) -> PumpStationCoupledTransition:
        stored_command, _, _, transition = self._load_command_step(commit)
        if stored_command != command:
            _fail("command-id-conflict", f"{command.request_id} is already bound to different content")
        return transition

    def commits(self) -> tuple[PumpStationCommit, ...]:
        pointer = self._load_current()
        chain: list[PumpStationCommit] = []
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

    def commits_through(self, snapshot: PumpStationStateSnapshotRef) -> tuple[PumpStationCommit, ...]:
        manifest = self.load_manifest()
        if (
            snapshot.snapshot_version,
            snapshot.run_id,
            snapshot.episode_id,
            snapshot.world_branch_id,
        ) != (
            manifest.snapshot_version,
            manifest.run_id,
            manifest.episode_id,
            manifest.world_branch_id,
        ):
            _fail("snapshot-drift", "requested snapshot belongs to another world run")
        chain = self.commits()
        for index, commit in enumerate(chain):
            if pump_station_artifact_id(commit) != snapshot.commit_id:
                continue
            if (commit.sequence, commit.state_id) != (snapshot.sequence, snapshot.state_id):
                _fail("snapshot-drift", "requested snapshot and commit differ")
            self.load_state(snapshot.state_id)
            return chain[: index + 1]
        _fail("snapshot-drift", "requested snapshot is not on the selected history")

    def command_steps(self) -> tuple[PumpStationCoupledRunStep, ...]:
        return self._command_steps(self.commits())

    def command_steps_through(
        self,
        snapshot: PumpStationStateSnapshotRef,
    ) -> tuple[PumpStationCoupledRunStep, ...]:
        return self._command_steps(self.commits_through(snapshot))

    def _command_steps(self, commits: tuple[PumpStationCommit, ...]) -> tuple[PumpStationCoupledRunStep, ...]:
        steps: list[PumpStationCoupledRunStep] = []
        for commit in commits[1:]:
            if not isinstance(commit, PumpStationCommandCommit):
                _fail("artifact-integrity", "non-initial history contains an opening commit")
            command, proposal, information_set, transition = self._load_command_step(commit)
            steps.append(
                PumpStationCoupledRunStep(
                    command=command,
                    proposal=proposal,
                    information_set=information_set,
                    transition=transition,
                )
            )
        return tuple(steps)

    def _load_command_step(
        self,
        commit: PumpStationCommandCommit,
    ) -> tuple[
        PumpStationCommand,
        PumpStationProposal | None,
        PumpStationInformationSet | None,
        PumpStationCoupledTransition,
    ]:
        command = load_pump_station_artifact(
            self._read_content("commands", commit.command_content_id),
            PumpStationCommand,
        )
        manifest = self.load_manifest()
        self._require_command_scope(command, manifest)
        decode_pump_station_command(command)
        proposal: PumpStationProposal | None = None
        information_set: PumpStationInformationSet | None = None
        if commit.proposal_content_id is not None:
            if commit.information_set_content_id is None:
                _fail("artifact-integrity", "actor commit lacks an information set")
            proposal = self._load_proposal(commit.proposal_content_id)
            information_set = load_pump_station_artifact(
                self._read_content("information-sets", commit.information_set_content_id),
                PumpStationInformationSet,
            )
        receipt = load_pump_station_artifact(
            self._read_content("receipts", commit.receipt_content_id),
            PumpStationCoupledTransitionReceipt,
        )
        state = self.load_state(commit.state_id)
        transition = PumpStationCoupledTransition(state=state, receipt=receipt)
        if (
            pump_station_artifact_id(command) != commit.command_content_id
            or pump_station_artifact_id(receipt) != commit.receipt_content_id
            or command.request_id != commit.request_id
            or receipt.request_id != commit.request_id
            or receipt.sequence != commit.sequence
            or receipt.after_state_id != commit.state_id
            or receipt.actor_action != (command.kind == "actor")
        ):
            _fail("artifact-integrity", "commit evidence does not reconcile")
        if command.kind == "actor":
            if proposal is None or information_set is None:
                _fail("artifact-integrity", "actor command lacks bound proposal evidence")
            parent_state = self.load_state(self.load_commit(commit.parent_commit_id).state_id)
            self._require_actor_information_set(manifest, parent_state, command, information_set)
            if (
                pump_station_artifact_id(proposal) != commit.proposal_content_id
                or pump_station_artifact_id(information_set) != commit.information_set_content_id
                or proposal.context.proposal_id != command.request_id
                or proposal.context.information_set_id != information_set.information_set_id
            ):
                _fail("artifact-integrity", "actor evidence does not reconcile")
        elif proposal is not None or information_set is not None:
            _fail("artifact-integrity", "host control contains actor evidence")
        return command, proposal, information_set, transition

    @staticmethod
    def _require_command_scope(
        command: PumpStationCommand,
        manifest: PumpStationRegisteredWorldRunManifest,
    ) -> None:
        if (
            command.task_world_id,
            command.run_id,
            command.episode_id,
            command.world_branch_id,
        ) != (
            manifest.task_world_id,
            manifest.run_id,
            manifest.episode_id,
            manifest.world_branch_id,
        ):
            _fail("world-run-identity", "command scope differs from the stored run")

    @staticmethod
    def _project_information_set(
        manifest: PumpStationRegisteredWorldRunManifest,
        state: PumpStationCoupledStewardshipState,
        command: PumpStationCommand,
    ) -> PumpStationInformationSet:
        if command.agent_tenure_id is None:
            _fail("command-content", "actor command lacks its tenure")
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
            workspace_tool_ids=(PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID,),
        )

    def _require_actor_information_set(
        self,
        manifest: PumpStationRegisteredWorldRunManifest,
        state: PumpStationCoupledStewardshipState,
        command: PumpStationCommand,
        information_set: PumpStationInformationSet,
    ) -> None:
        expected = self._project_information_set(manifest, state, command)
        view = information_set.base_view
        if not isinstance(view, PumpStationCoupledActorView):
            _fail("artifact-integrity", "actor information set has the wrong view")
        if (
            command.actor_id != view.actor_id
            or view != expected.base_view
            or information_set.information_set_id != command.information_set_id
            or bind_information_set(
                view,
                information_set.observation_history,
                information_set.current_context,
            )
            != information_set
            or information_set.current_context.workspace_tool_ids != (PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID,)
            or not set(view.source_artifact_ids).issubset(information_set.current_context.visible_material_ids)
        ):
            _fail("artifact-integrity", "actor decision or information-set evidence differs")

    def _load_proposal(self, content_id: str) -> PumpStationProposal:
        payload = self._read_content("proposals", content_id)
        try:
            type_name = json.loads(payload)["$type"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            _fail("artifact-type", f"stored proposal has no valid type: {error}")
        proposal_type = _PROPOSAL_TYPES.get(type_name)
        if proposal_type is None:
            _fail("artifact-type", f"unknown stored proposal type {type_name!r}")
        return cast(
            PumpStationProposal,
            load_pump_station_artifact(payload, proposal_type),
        )

    def _reject_command_collision(self, command: PumpStationCommand, *, parent_commit_id: str) -> None:
        commits_root = self._root / "commits"
        if not commits_root.exists():
            return
        for path in commits_root.glob("*.json"):
            commit = self.load_commit(path.stem)
            if not isinstance(commit, PumpStationCommandCommit) or commit.request_id != command.request_id:
                continue
            stored, _, _, _ = self._load_command_step(commit)
            if stored == command and commit.parent_commit_id == parent_commit_id:
                _fail("command-already-staged", f"{command.request_id} already has one durable staged outcome")
            _fail("command-id-conflict", f"{command.request_id} has different staged content")

    def _validate_chain(
        self,
        chain: tuple[PumpStationCommit, ...],
        pointer: PumpStationCurrentRunPointer,
    ) -> None:
        manifest = self.load_manifest()
        if (
            not chain
            or not isinstance(chain[0], PumpStationWorldRunCommit)
            or chain[0].sequence != manifest.initial_sequence
            or chain[0].state_id != manifest.initial_state_id
        ):
            _fail("artifact-integrity", "commit chain lacks the manifest opening state")
        previous: PumpStationCommit = chain[0]
        for commit in chain[1:]:
            if not isinstance(commit, PumpStationCommandCommit):
                _fail("artifact-integrity", "opening commit appears after the initial state")
            command, _, _, transition = self._load_command_step(commit)
            if not self._command_step_extends_parent(previous, commit, command, transition):
                _fail("artifact-integrity", "commit does not extend its parent")
            previous = commit
        if (
            previous.sequence != pointer.sequence
            or previous.state_id != pointer.state_id
            or pump_station_artifact_id(previous) != pointer.commit_id
        ):
            _fail("artifact-integrity", "commit chain does not reach current pointer")

    def _publish_state(self, state: PumpStationCoupledStewardshipState) -> str:
        state_id = stewardship_state_id(state)
        self._publish_content("states", state_id, state)
        return state_id

    def _publish_content(
        self,
        collection: str,
        content_id: str,
        value: object,
    ) -> None:
        payload = pump_station_artifact_bytes(value)
        if collection != "states" and hashlib.sha256(payload).hexdigest() != content_id:
            _fail("artifact-integrity", f"{collection} content identity differs")
        self._publish_immutable(self._root / collection / f"{content_id}.json", payload)

    def _publish_root_immutable(self, name: str, value: object) -> None:
        self._publish_immutable(
            self._root / name,
            pump_station_artifact_bytes(value),
        )

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
        try:
            replace_file_bytes_durable(
                self._root,
                "current.json",
                pump_station_artifact_bytes(pointer),
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

    @staticmethod
    def _snapshot(
        manifest: PumpStationRegisteredWorldRunManifest,
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


__all__ = ["PumpStationWorldRunRepository"]
