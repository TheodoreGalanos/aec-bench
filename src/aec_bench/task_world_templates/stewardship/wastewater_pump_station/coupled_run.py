# ABOUTME: Persists and independently replays ASW-8 v4 commands, states, receipts, and manifest bindings.
# ABOUTME: Publishes immutable generations behind one atomic head pointer for safe resume and recovery.

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Self, cast

from aec_bench.contracts.world_interface import WorldInterfaceError
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    pump_station_proposal_from_validated_arguments_v2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledTransitionReceipt,
    PumpStationCoupledTreatmentRequest,
    PumpStationCoupledWorldState,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
    apply_common_boundary_control,
    apply_coupled_actor_action,
    apply_coupled_handover,
    apply_coupled_treatment,
    apply_operations_boundary_review,
    apply_process_outcome,
    create_asw_8_world_state,
    project_coupled_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_ASW_8_EVENT_SCHEDULE_ID,
    PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID,
    PUMP_STATION_ASW_8_TEMPORAL_TEMPLATE_ID,
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
    stewardship_content_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    ProposalContext,
    PumpStationProposal,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.corpus import (
    build_asw_8_reference_temporal_evidence_bundle,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_RECORD_VERSIONS_V4,
    PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
    PumpStationInitialStateSource,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
)


class PumpStationCoupledRunError(RuntimeError):
    """Raised when durable ASW-8 run evidence is incomplete or changed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True, slots=True)
class PumpStationCoupledWorldRunManifest:
    """Immutable v2 run identity with full reference-system and temporal binding."""

    serialization_version: str
    run_id: str
    episode_id: str
    world_branch_id: str
    reference_system_id: str
    reference_system_content_id: str
    station_data_profile_id: str
    station_data_package_content_id: str
    opening_state_specification_id: str
    opening_state_specification_sha256: str
    event_schedule_id: str
    event_schedule_sha256: str
    temporal_template_id: str
    temporal_template_sha256: str
    temporal_bundle_content_id: str
    temporal_corpus_content_id: str
    temporal_capability_content_id: str
    snapshot_version: str
    receipt_version: str
    authority_policy_version: str
    transition_rule_version: str
    initial_state_id: str
    initial_state_source: PumpStationInitialStateSource

    @property
    def content_id(self) -> str:
        """Return the canonical manifest content identity."""
        return stewardship_content_id(self, record_profile="v4")


@dataclass(frozen=True, slots=True)
class PumpStationCoupledCommand:
    """Canonical actor or host-control input used for independent replay."""

    kind: str
    request_id: str
    action_name: str
    arguments_json: str

    @classmethod
    def actor(
        cls,
        request_id: str,
        action_name: str,
        arguments: dict[str, Any],
    ) -> Self:
        """Construct one canonical actor command."""
        return cls(
            kind="actor",
            request_id=request_id,
            action_name=action_name,
            arguments_json=json.dumps(
                arguments,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

    @classmethod
    def control(cls, request: PumpStationOperationsBoundaryReviewRequest) -> Self:
        """Construct one canonical host-control command."""
        return cls(
            kind="operations_review",
            request_id=request.review_id,
            action_name="operations_boundary_review",
            arguments_json=json.dumps(
                canonical_stewardship_value(request, record_profile="v4"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

    @classmethod
    def handover(
        cls,
        handover_id: str,
        from_tenure_id: str,
        to_tenure_id: str,
    ) -> Self:
        """Construct one canonical tenure-handover command."""
        return cls(
            kind="handover",
            request_id=handover_id,
            action_name="structured_handover",
            arguments_json=json.dumps(
                {"from_tenure_id": from_tenure_id, "to_tenure_id": to_tenure_id},
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

    @classmethod
    def treatment(cls, request: PumpStationCoupledTreatmentRequest) -> Self:
        """Construct one canonical private child-treatment command."""
        return cls(
            kind="coupled_treatment",
            request_id=request.request_id,
            action_name="coupled_physical_treatment",
            arguments_json=json.dumps(
                canonical_stewardship_value(request, record_profile="v4"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

    @classmethod
    def process_outcome(cls, request: PumpStationProcessOutcomeRequest) -> Self:
        """Construct one canonical host-owned process-outcome command."""
        return cls(
            kind="process_outcome",
            request_id=request.request_id,
            action_name="process_outcome",
            arguments_json=json.dumps(
                canonical_stewardship_value(request, record_profile="v4"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

    @classmethod
    def common_boundary(cls, request: PumpStationCommonBoundaryRequest) -> Self:
        """Construct one canonical common-boundary command."""
        return cls(
            kind="common_boundary",
            request_id=request.request_id,
            action_name="common_boundary_control",
            arguments_json=json.dumps(
                canonical_stewardship_value(request, record_profile="v4"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

    @property
    def arguments(self) -> dict[str, Any]:
        """Return the validated command arguments object."""
        value = json.loads(self.arguments_json)
        if not isinstance(value, dict):
            raise PumpStationCoupledRunError("command-shape", self.request_id)
        return cast(dict[str, Any], value)


def _default_proposal_context(
    run: PumpStationCoupledRun,
    *,
    request_id: str,
    reason: str,
) -> ProposalContext:
    view_id = stewardship_content_id(
        project_coupled_actor_view(run.state),
        record_profile="v4",
    )
    return ProposalContext(
        proposal_id=request_id,
        agent_tenure_id="reference-controller",
        based_on_sequence=run.state.sequence,
        base_view_id=view_id,
        information_set_id=stewardship_content_id(
            (
                run.manifest.run_id,
                run.manifest.world_branch_id,
                run.state.sequence,
                run.state.state_id,
                view_id,
                "reference-controller",
            ),
            record_profile="v4",
        ),
        reason=reason,
    )


def _coupled_proposal(
    run: PumpStationCoupledRun,
    *,
    request_id: str,
    action_name: str,
    arguments: dict[str, Any],
    proposal_context: ProposalContext | None,
) -> PumpStationProposal:
    reason = arguments.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise PumpStationCoupledRunError("proposal-context", "proposal reason is required")
    context = proposal_context or _default_proposal_context(
        run,
        request_id=request_id,
        reason=reason.strip(),
    )
    if (
        context.proposal_id != request_id
        or context.based_on_sequence != run.state.sequence
        or context.reason != reason.strip()
        or context.base_view_id
        != stewardship_content_id(
            project_coupled_actor_view(run.state),
            record_profile="v4",
        )
    ):
        raise PumpStationCoupledRunError(
            "proposal-context",
            "proposal does not match the current request and state",
        )
    try:
        return pump_station_proposal_from_validated_arguments_v2(
            action_name=action_name,
            arguments=arguments,
            context=context,
        )
    except WorldInterfaceError as error:
        raise PumpStationCoupledRunError("proposal-shape", str(error)) from error


@dataclass(frozen=True, slots=True)
class PumpStationCoupledRun:
    """Immutable command chain and its exact current state and receipts."""

    manifest: PumpStationCoupledWorldRunManifest
    state: PumpStationCoupledWorldState
    commands: tuple[PumpStationCoupledCommand, ...]
    receipts: tuple[PumpStationCoupledTransitionReceipt, ...]
    proposals: tuple[PumpStationProposal, ...] = ()
    origin_manifest: PumpStationCoupledWorldRunManifest | None = None
    origin_commands: tuple[PumpStationCoupledCommand, ...] = ()
    origin_proposals: tuple[PumpStationProposal, ...] = ()

    def apply_actor(
        self,
        *,
        request_id: str,
        action_name: str,
        arguments: dict[str, Any],
        proposal_context: ProposalContext | None = None,
    ) -> Self:
        """Apply and append one actor command."""
        command = PumpStationCoupledCommand.actor(request_id, action_name, arguments)
        proposal = _coupled_proposal(
            self,
            request_id=request_id,
            action_name=action_name,
            arguments=arguments,
            proposal_context=proposal_context,
        )
        transition = apply_coupled_actor_action(
            self.state,
            request_id=request_id,
            action_name=action_name,
            arguments=arguments,
        )
        return replace(
            self,
            state=transition.state,
            commands=(*self.commands, command),
            receipts=(*self.receipts, transition.receipt),
            proposals=(*self.proposals, proposal),
        )

    def apply_review(self, request: PumpStationOperationsBoundaryReviewRequest) -> Self:
        """Apply and append one host-only Operations review."""
        transition = apply_operations_boundary_review(self.state, request)
        return replace(
            self,
            state=transition.state,
            commands=(*self.commands, PumpStationCoupledCommand.control(request)),
            receipts=(*self.receipts, transition.receipt),
        )

    def handover(
        self,
        *,
        handover_id: str,
        from_tenure_id: str,
        to_tenure_id: str,
    ) -> Self:
        """Apply and append one structured handover."""
        transition = apply_coupled_handover(
            self.state,
            handover_id=handover_id,
            from_tenure_id=from_tenure_id,
            to_tenure_id=to_tenure_id,
        )
        return replace(
            self,
            state=transition.state,
            commands=(
                *self.commands,
                PumpStationCoupledCommand.handover(
                    handover_id,
                    from_tenure_id,
                    to_tenure_id,
                ),
            ),
            receipts=(*self.receipts, transition.receipt),
        )

    def apply_treatment(self, request: PumpStationCoupledTreatmentRequest) -> Self:
        """Apply and append one host-private coupled treatment."""
        transition = apply_coupled_treatment(self.state, request)
        return replace(
            self,
            state=transition.state,
            commands=(*self.commands, PumpStationCoupledCommand.treatment(request)),
            receipts=(*self.receipts, transition.receipt),
        )

    def apply_process_outcome(self, request: PumpStationProcessOutcomeRequest) -> Self:
        """Apply and append one host-owned process outcome."""
        transition = apply_process_outcome(self.state, request)
        return replace(
            self,
            state=transition.state,
            commands=(*self.commands, PumpStationCoupledCommand.process_outcome(request)),
            receipts=(*self.receipts, transition.receipt),
        )

    def apply_common_boundary(self, request: PumpStationCommonBoundaryRequest) -> Self:
        """Apply and append one host-owned common-boundary change."""
        transition = apply_common_boundary_control(self.state, request)
        return replace(
            self,
            state=transition.state,
            commands=(*self.commands, PumpStationCoupledCommand.common_boundary(request)),
            receipts=(*self.receipts, transition.receipt),
        )


def create_coupled_run(
    *,
    run_id: str,
    world_branch_id: str,
) -> PumpStationCoupledRun:
    """Create a root ASW-8 run only from the closed descriptor and verified temporal bundle."""
    system = load_reference_system()
    package = load_reference_package(profile_id=REFERENCE_PROFILE_V2)
    bundle = build_asw_8_reference_temporal_evidence_bundle(
        package,
        world_branch_id=world_branch_id,
    )
    state = create_asw_8_world_state()
    opening_binding = cast(dict[str, Any], dict(system.descriptor["opening_state"]))
    schedule_binding = cast(dict[str, Any], dict(system.descriptor["event_schedule"]))
    temporal_binding = cast(dict[str, Any], dict(system.descriptor["temporal_template"]))
    source = PumpStationInitialStateSource(
        kind="reference_system_specification",
        opening_specification_id=PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID,
        opening_specification_sha256=str(opening_binding["content_sha256"]),
    )
    manifest = PumpStationCoupledWorldRunManifest(
        serialization_version=PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
        run_id=run_id,
        episode_id=f"episode-{run_id}",
        world_branch_id=world_branch_id,
        reference_system_id=PUMP_STATION_REFERENCE_SYSTEM_ID,
        reference_system_content_id=system.descriptor_content_id,
        station_data_profile_id=package.profile_id,
        station_data_package_content_id=package.package_content_id,
        opening_state_specification_id=PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID,
        opening_state_specification_sha256=str(opening_binding["content_sha256"]),
        event_schedule_id=PUMP_STATION_ASW_8_EVENT_SCHEDULE_ID,
        event_schedule_sha256=str(schedule_binding["content_sha256"]),
        temporal_template_id=PUMP_STATION_ASW_8_TEMPORAL_TEMPLATE_ID,
        temporal_template_sha256=str(temporal_binding["content_sha256"]),
        temporal_bundle_content_id=bundle.content_sha256,
        temporal_corpus_content_id=bundle.corpus_manifest.content_sha256,
        temporal_capability_content_id=bundle.capability.content_sha256,
        snapshot_version=PUMP_STATION_RECORD_VERSIONS_V4.snapshot_version,
        receipt_version=PUMP_STATION_RECORD_VERSIONS_V4.receipt_version,
        authority_policy_version=PUMP_STATION_RECORD_VERSIONS_V4.authority_policy_version,
        transition_rule_version=PUMP_STATION_RECORD_VERSIONS_V4.transition_rule_version,
        initial_state_id=state.state_id,
        initial_state_source=source,
    )
    return PumpStationCoupledRun(
        manifest=manifest,
        state=state,
        commands=(),
        receipts=(),
        proposals=(),
    )


def replay_coupled_run(
    manifest: PumpStationCoupledWorldRunManifest,
    commands: tuple[PumpStationCoupledCommand, ...],
    *,
    proposals: tuple[PumpStationProposal, ...] = (),
    origin_manifest: PumpStationCoupledWorldRunManifest | None = None,
    origin_commands: tuple[PumpStationCoupledCommand, ...] = (),
    origin_proposals: tuple[PumpStationProposal, ...] = (),
) -> PumpStationCoupledRun:
    """Independently rebuild one complete v4 state and receipt chain."""
    if manifest.initial_state_source.kind == "reference_system_specification":
        fresh = create_coupled_run(
            run_id=manifest.run_id,
            world_branch_id=manifest.world_branch_id,
        )
        if fresh.manifest != manifest:
            raise PumpStationCoupledRunError("manifest-binding", manifest.run_id)
        run = fresh
    elif manifest.initial_state_source.kind == "rollout_parent_snapshot":
        if origin_manifest is None:
            raise PumpStationCoupledRunError("rollout-origin", manifest.run_id)
        parent = replay_coupled_run(
            origin_manifest,
            origin_commands,
            proposals=origin_proposals,
        )
        source = manifest.initial_state_source
        inherited = (
            manifest.reference_system_id,
            manifest.reference_system_content_id,
            manifest.station_data_profile_id,
            manifest.station_data_package_content_id,
            manifest.opening_state_specification_id,
            manifest.opening_state_specification_sha256,
            manifest.event_schedule_id,
            manifest.event_schedule_sha256,
            manifest.temporal_template_id,
            manifest.temporal_template_sha256,
            manifest.temporal_bundle_content_id,
            manifest.temporal_corpus_content_id,
            manifest.temporal_capability_content_id,
            manifest.snapshot_version,
            manifest.receipt_version,
            manifest.authority_policy_version,
            manifest.transition_rule_version,
        )
        parent_bindings = (
            origin_manifest.reference_system_id,
            origin_manifest.reference_system_content_id,
            origin_manifest.station_data_profile_id,
            origin_manifest.station_data_package_content_id,
            origin_manifest.opening_state_specification_id,
            origin_manifest.opening_state_specification_sha256,
            origin_manifest.event_schedule_id,
            origin_manifest.event_schedule_sha256,
            origin_manifest.temporal_template_id,
            origin_manifest.temporal_template_sha256,
            origin_manifest.temporal_bundle_content_id,
            origin_manifest.temporal_corpus_content_id,
            origin_manifest.temporal_capability_content_id,
            origin_manifest.snapshot_version,
            origin_manifest.receipt_version,
            origin_manifest.authority_policy_version,
            origin_manifest.transition_rule_version,
        )
        expected_ancestors = (
            *origin_manifest.initial_state_source.ancestor_branch_ids,
            origin_manifest.world_branch_id,
        )
        if (
            inherited != parent_bindings
            or source.parent_manifest_content_id != origin_manifest.content_id
            or source.parent_run_id != origin_manifest.run_id
            or source.parent_branch_id != origin_manifest.world_branch_id
            or source.parent_state_id != parent.state.state_id
            or source.parent_commit_id != parent.state.state_id
            or manifest.initial_state_id != parent.state.state_id
            or source.ancestor_branch_ids != expected_ancestors
            or source.opening_specification_id != origin_manifest.opening_state_specification_id
            or source.opening_specification_sha256 != origin_manifest.opening_state_specification_sha256
            or any(
                value is None
                for value in (
                    source.rollout_group_request_id,
                    source.child_request_content_id,
                    source.rollout_group_request_content_id,
                    source.origin_verification_content_id,
                    source.parent_origin_remaining_schedule_sha256,
                )
            )
        ):
            raise PumpStationCoupledRunError("rollout-origin-binding", manifest.run_id)
        run = PumpStationCoupledRun(
            manifest=manifest,
            state=parent.state,
            commands=(),
            receipts=(),
            proposals=(),
            origin_manifest=origin_manifest,
            origin_commands=origin_commands,
            origin_proposals=origin_proposals,
        )
    else:
        raise PumpStationCoupledRunError(
            "initial-state-source",
            manifest.initial_state_source.kind,
        )
    proposals_by_id = {proposal.context.proposal_id: proposal for proposal in proposals}
    if len(proposals_by_id) != len(proposals):
        raise PumpStationCoupledRunError("proposal-identity", manifest.run_id)
    used_proposal_ids: set[str] = set()
    for command in commands:
        if command.kind == "actor":
            proposal = proposals_by_id.get(command.request_id)
            if proposal is not None:
                used_proposal_ids.add(command.request_id)
            run = run.apply_actor(
                request_id=command.request_id,
                action_name=command.action_name,
                arguments=command.arguments,
                proposal_context=(proposal.context if proposal is not None else None),
            )
        elif command.kind == "operations_review":
            run = run.apply_review(PumpStationOperationsBoundaryReviewRequest(**command.arguments))
        elif command.kind == "handover":
            run = run.handover(
                handover_id=command.request_id,
                from_tenure_id=str(command.arguments["from_tenure_id"]),
                to_tenure_id=str(command.arguments["to_tenure_id"]),
            )
        elif command.kind == "coupled_treatment":
            arguments = command.arguments
            arguments["affected_pump_ids"] = tuple(arguments["affected_pump_ids"])
            arguments["obstruction_delta"] = Decimal(str(arguments["obstruction_delta"]))
            arguments["clearance_loss_delta"] = Decimal(str(arguments["clearance_loss_delta"]))
            run = run.apply_treatment(PumpStationCoupledTreatmentRequest(**arguments))
        elif command.kind == "process_outcome":
            run = run.apply_process_outcome(PumpStationProcessOutcomeRequest(**command.arguments))
        elif command.kind == "common_boundary":
            run = run.apply_common_boundary(PumpStationCommonBoundaryRequest(**command.arguments))
        else:
            raise PumpStationCoupledRunError("command-kind", command.kind)
    if used_proposal_ids != set(proposals_by_id):
        raise PumpStationCoupledRunError("proposal-command-binding", manifest.run_id)
    if run.proposals != proposals:
        raise PumpStationCoupledRunError("proposal-replay", manifest.run_id)
    return run


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            canonical_stewardship_value(value, record_profile="v4"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


class PumpStationCoupledRunRepository(PumpStationWorldRunRepository):
    """V4 profile of the existing confined pump-station run repository."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)

    def create(self, run: PumpStationCoupledRun) -> None:
        """Publish a new exact root or rollout-child run."""
        with self.locked():
            if (self.root / "manifest.json").exists() or (self.root / "HEAD").exists():
                raise PumpStationCoupledRunError("run-exists", str(self.root))
            (self.root / "generations").mkdir(mode=0o700)
            self._write_private(self.root / "manifest.json", _canonical_bytes(run.manifest))
            if run.origin_manifest is not None:
                self._write_private(
                    self.root / "origin-manifest.json",
                    _canonical_bytes(run.origin_manifest),
                )
                self._write_private(
                    self.root / "origin-commands.json",
                    _canonical_bytes(run.origin_commands),
                )
                self._write_private(
                    self.root / "origin-proposals.json",
                    pump_station_artifact_bytes(
                        run.origin_proposals,
                        record_profile="v4",
                    ),
                )
            self._publish_generation(run)

    def append(self, run: PumpStationCoupledRun) -> None:
        """Publish one complete later generation and then move the head atomically."""
        with self.locked():
            current = self._open_selected()
            if current.manifest != run.manifest:
                raise PumpStationCoupledRunError("manifest-binding", run.manifest.run_id)
            if run.commands[: len(current.commands)] != current.commands:
                raise PumpStationCoupledRunError("command-history", run.manifest.run_id)
            if run.proposals[: len(current.proposals)] != current.proposals:
                raise PumpStationCoupledRunError("proposal-history", run.manifest.run_id)
            self._publish_generation(run)

    def open(self) -> PumpStationCoupledRun:
        """Load the selected immutable generation and verify it by replay."""
        with self.locked():
            return self._open_selected()

    def _open_selected(self) -> PumpStationCoupledRun:
        """Load the selected generation while the shared run lock is held."""
        manifest_value = self._read_json(self.root / "manifest.json")
        manifest = self._manifest(manifest_value)
        try:
            head = int((self.root / "HEAD").read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as error:
            raise PumpStationCoupledRunError("run-head", str(error)) from error
        generation = self.root / "generations" / f"{head:08d}"
        command_values = self._read_json(generation / "commands.json")
        if not isinstance(command_values, list):
            raise PumpStationCoupledRunError("command-shape", str(generation))
        commands = tuple(PumpStationCoupledCommand(**value) for value in command_values)
        proposals = self._read_proposals(generation / "proposals.json")
        origin_manifest = None
        origin_commands: tuple[PumpStationCoupledCommand, ...] = ()
        origin_proposals: tuple[PumpStationProposal, ...] = ()
        if manifest.initial_state_source.kind == "rollout_parent_snapshot":
            origin_manifest = self._manifest(self._read_json(self.root / "origin-manifest.json"))
            origin_values = self._read_json(self.root / "origin-commands.json")
            if not isinstance(origin_values, list):
                raise PumpStationCoupledRunError("command-shape", "rollout origin")
            origin_commands = tuple(PumpStationCoupledCommand(**value) for value in origin_values)
            origin_proposals = self._read_proposals(self.root / "origin-proposals.json")
        replay = replay_coupled_run(
            manifest,
            commands,
            proposals=proposals,
            origin_manifest=origin_manifest,
            origin_commands=origin_commands,
            origin_proposals=origin_proposals,
        )
        if self._read_json(generation / "state.json") != canonical_stewardship_value(
            replay.state,
            record_profile="v4",
        ):
            raise PumpStationCoupledRunError("state-replay", replay.state.state_id)
        if self._read_json(generation / "receipts.json") != canonical_stewardship_value(
            replay.receipts,
            record_profile="v4",
        ):
            raise PumpStationCoupledRunError("receipt-replay", manifest.run_id)
        return replay

    def open_generation(self, sequence: int) -> PumpStationCoupledRun:
        """Load and replay one immutable historical generation by command count."""
        with self.locked():
            return self._open_generation(sequence)

    def _open_generation(self, sequence: int) -> PumpStationCoupledRun:
        """Load one generation while the shared run lock is held."""
        if sequence < 0:
            raise PumpStationCoupledRunError("generation-sequence", str(sequence))
        manifest = self._manifest(self._read_json(self.root / "manifest.json"))
        generation = self.root / "generations" / f"{sequence:08d}"
        command_values = self._read_json(generation / "commands.json")
        if not isinstance(command_values, list):
            raise PumpStationCoupledRunError("command-shape", str(generation))
        commands = tuple(PumpStationCoupledCommand(**value) for value in command_values)
        proposals = self._read_proposals(generation / "proposals.json")
        if len(commands) != sequence:
            raise PumpStationCoupledRunError("generation-sequence", str(generation))
        origin_manifest = None
        origin_commands: tuple[PumpStationCoupledCommand, ...] = ()
        origin_proposals: tuple[PumpStationProposal, ...] = ()
        if manifest.initial_state_source.kind == "rollout_parent_snapshot":
            origin_manifest = self._manifest(self._read_json(self.root / "origin-manifest.json"))
            origin_values = self._read_json(self.root / "origin-commands.json")
            if not isinstance(origin_values, list):
                raise PumpStationCoupledRunError("command-shape", "rollout origin")
            origin_commands = tuple(PumpStationCoupledCommand(**value) for value in origin_values)
            origin_proposals = self._read_proposals(self.root / "origin-proposals.json")
        replay = replay_coupled_run(
            manifest,
            commands,
            proposals=proposals,
            origin_manifest=origin_manifest,
            origin_commands=origin_commands,
            origin_proposals=origin_proposals,
        )
        if self._read_json(generation / "state.json") != canonical_stewardship_value(
            replay.state,
            record_profile="v4",
        ):
            raise PumpStationCoupledRunError("state-replay", replay.state.state_id)
        if self._read_json(generation / "receipts.json") != canonical_stewardship_value(
            replay.receipts,
            record_profile="v4",
        ):
            raise PumpStationCoupledRunError("receipt-replay", manifest.run_id)
        return replay

    def _publish_generation(self, run: PumpStationCoupledRun) -> None:
        sequence = len(run.commands)
        generation = self.root / "generations" / f"{sequence:08d}"
        expected = {
            "commands.json": _canonical_bytes(run.commands),
            "proposals.json": pump_station_artifact_bytes(
                run.proposals,
                record_profile="v4",
            ),
            "state.json": _canonical_bytes(run.state),
            "receipts.json": _canonical_bytes(run.receipts),
        }
        try:
            generation.mkdir(mode=0o700)
        except FileExistsError:
            for name, payload in expected.items():
                path = generation / name
                if path.exists() and path.read_bytes() != payload:
                    raise PumpStationCoupledRunError(
                        "generation-content",
                        str(generation),
                    ) from None
        for name, payload in expected.items():
            path = generation / name
            if not path.exists():
                self._write_private(path, payload)
        self._sync_directory(generation)
        self._sync_directory(generation.parent)
        head_tmp = self.root / "HEAD.tmp"
        head_payload = f"{sequence}\n".encode()
        if head_tmp.exists():
            if head_tmp.is_symlink() or head_tmp.read_bytes() != head_payload:
                raise PumpStationCoupledRunError("run-head", "staged head differs")
        else:
            self._write_private(head_tmp, head_payload)
        os.replace(head_tmp, self.root / "HEAD")
        self._sync_directory(self.root)

    @staticmethod
    def _write_private(path: Path, payload: bytes) -> None:
        """Write one host-private artifact and sync it before publication."""
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        """Sync one directory after an atomic publication change."""
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            return json.loads(path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PumpStationCoupledRunError("artifact-read", f"{path}: {error}") from error

    @staticmethod
    def _read_proposals(path: Path) -> tuple[PumpStationProposal, ...]:
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise PumpStationCoupledRunError(
                "artifact-read",
                f"{path}: {error}",
            ) from error
        return load_pump_station_artifact(
            payload,
            tuple[PumpStationProposal, ...],
            record_profile="v4",
        )

    @staticmethod
    def _manifest(value: Any) -> PumpStationCoupledWorldRunManifest:
        if not isinstance(value, dict):
            raise PumpStationCoupledRunError("manifest-shape", "manifest is not an object")
        manifest_value = dict(value)
        source_value = cast(dict[str, Any], manifest_value.pop("initial_state_source"))
        source_value["ancestor_branch_ids"] = tuple(source_value.get("ancestor_branch_ids", ()))
        return PumpStationCoupledWorldRunManifest(
            **manifest_value,
            initial_state_source=PumpStationInitialStateSource(**source_value),
        )
