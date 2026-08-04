# ABOUTME: Defines the current durable records for one registered pump-station run.
# ABOUTME: Uses one current codec with no historical schema selectors or version families.

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import NoReturn

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationCoupledTransition,
    PumpStationProposal,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
)


class PumpStationWorldRunError(RuntimeError):
    """Raised when durable pump-station run evidence is invalid or unsafe."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def require_world_run_text(value: object, field_name: str) -> None:
    """Require one non-empty durable identity."""
    if not isinstance(value, str) or not value.strip():
        raise PumpStationWorldRunError("world-run-shape", f"{field_name} must not be empty")


@dataclass(frozen=True, slots=True)
class PumpStationInitialStateSource:
    """Closed opening-state provenance for one root or rollout-child run."""

    kind: str
    opening_specification_id: str
    opening_specification_sha256: str
    parent_run_id: str | None = None
    parent_branch_id: str | None = None
    parent_state_id: str | None = None
    parent_commit_id: str | None = None
    rollout_group_request_id: str | None = None
    child_request_content_id: str | None = None
    rollout_group_request_content_id: str | None = None
    parent_manifest_content_id: str | None = None
    origin_verification_content_id: str | None = None
    parent_origin_remaining_schedule_sha256: str | None = None
    ancestor_branch_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_world_run_text(self.opening_specification_id, "opening_specification_id")
        require_world_run_text(self.opening_specification_sha256, "opening_specification_sha256")
        parent_fields = (
            self.parent_run_id,
            self.parent_branch_id,
            self.parent_state_id,
            self.parent_commit_id,
            self.rollout_group_request_id,
            self.child_request_content_id,
            self.rollout_group_request_content_id,
            self.parent_manifest_content_id,
            self.origin_verification_content_id,
            self.parent_origin_remaining_schedule_sha256,
        )
        if self.kind == "reference_system_specification":
            if any(value is not None for value in parent_fields) or self.ancestor_branch_ids:
                raise PumpStationWorldRunError(
                    "initial-state-source",
                    "root opening state must not contain rollout provenance",
                )
            return
        if self.kind != "rollout_parent_snapshot":
            raise PumpStationWorldRunError("initial-state-source", self.kind)
        if any(value is None for value in parent_fields):
            raise PumpStationWorldRunError(
                "initial-state-source",
                "rollout opening state lacks parent provenance",
            )
        for index, value in enumerate(parent_fields):
            require_world_run_text(value, f"parent_provenance[{index}]")
        if not self.ancestor_branch_ids:
            raise PumpStationWorldRunError(
                "initial-state-source",
                "rollout opening state lacks ancestor branches",
            )
        for index, branch_id in enumerate(self.ancestor_branch_ids):
            require_world_run_text(branch_id, f"ancestor_branch_ids[{index}]")


@dataclass(frozen=True, slots=True)
class PumpStationRegisteredWorldRunManifest:
    """Current persisted identity for one registered root or rollout branch."""

    run_id: str
    episode_id: str
    world_branch_id: str
    profile_id: str
    generation_id: str
    package_content_id: str
    manifest_content_id: str
    asset_id: str
    model_id: str
    initial_sequence: int
    initial_state_id: str
    task_world_id: str
    world_build_entry_point: str
    world_build_artifact_sha256: str
    continual_profile_id: str
    continual_profile_content_sha256: str
    reference_system_id: str
    reference_system_content_id: str
    opening_state_specification_id: str
    opening_state_specification_sha256: str
    event_schedule_id: str
    event_schedule_sha256: str
    temporal_template_id: str
    temporal_template_sha256: str
    temporal_bundle_content_id: str
    temporal_corpus_content_id: str
    temporal_capability_content_id: str
    initial_state_source: PumpStationInitialStateSource

    def __post_init__(self) -> None:
        for field_name in (
            "run_id",
            "episode_id",
            "world_branch_id",
            "profile_id",
            "generation_id",
            "package_content_id",
            "manifest_content_id",
            "asset_id",
            "model_id",
            "initial_state_id",
            "task_world_id",
            "world_build_entry_point",
            "world_build_artifact_sha256",
            "continual_profile_id",
            "continual_profile_content_sha256",
            "reference_system_id",
            "reference_system_content_id",
            "opening_state_specification_id",
            "opening_state_specification_sha256",
            "event_schedule_id",
            "event_schedule_sha256",
            "temporal_template_id",
            "temporal_template_sha256",
            "temporal_bundle_content_id",
            "temporal_corpus_content_id",
            "temporal_capability_content_id",
        ):
            require_world_run_text(getattr(self, field_name), field_name)
        if self.initial_sequence < 0:
            raise PumpStationWorldRunError("world-run-shape", "initial sequence must be non-negative")
        if (
            self.initial_state_source.opening_specification_id != self.opening_state_specification_id
            or self.initial_state_source.opening_specification_sha256 != self.opening_state_specification_sha256
        ):
            raise PumpStationWorldRunError(
                "manifest-bindings",
                "initial-state source differs from the opening-state binding",
            )
        if self.initial_state_source.kind == "reference_system_specification" and self.initial_sequence != 0:
            raise PumpStationWorldRunError(
                "manifest-bindings",
                "reference-system roots must start at sequence zero",
            )


@dataclass(frozen=True, slots=True)
class PumpStationStateSnapshotRef:
    """Exact dynamic state selected for one durable pump-station run."""

    run_id: str
    episode_id: str
    world_branch_id: str
    sequence: int
    state_id: str
    commit_id: str

    def __post_init__(self) -> None:
        for field_name in ("run_id", "episode_id", "world_branch_id", "state_id", "commit_id"):
            require_world_run_text(getattr(self, field_name), field_name)
        if self.sequence < 0:
            raise PumpStationWorldRunError("world-run-shape", "snapshot sequence must be non-negative")


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, child in pairs:
        if key in value:
            raise PumpStationWorldRunError("canonical-json", f"duplicate field {key}")
        value[key] = child
    return value


def _reject_nonstandard_json_constant(value: str) -> NoReturn:
    raise PumpStationWorldRunError("canonical-json", f"non-standard JSON constant {value}")


@dataclass(frozen=True, slots=True)
class PumpStationCommand:
    """Persistence-edge command bound to one selected current parent."""

    kind: str
    request_id: str
    request_content_id: str
    action_name: str
    arguments_json: str
    task_world_id: str
    run_id: str
    episode_id: str
    world_branch_id: str
    based_on_sequence: int
    base_state_id: str
    base_commit_id: str
    decision_id: str | None = None
    actor_id: str | None = None
    agent_tenure_id: str | None = None
    actor_view_id: str | None = None
    information_set_id: str | None = None
    authority_id: str | None = None

    def __post_init__(self) -> None:
        expected_actions = {
            "operations_review": "operations_boundary_review",
            "process_outcome": "process_outcome",
            "common_boundary": "common_boundary_control",
            "coupled_treatment": "coupled_physical_treatment",
        }
        if self.kind != "actor" and self.kind not in expected_actions:
            raise PumpStationWorldRunError("command-kind", self.kind)
        if self.kind in expected_actions and self.action_name != expected_actions[self.kind]:
            raise PumpStationWorldRunError("command-kind", self.action_name)
        for field_name in (
            "request_id",
            "request_content_id",
            "action_name",
            "task_world_id",
            "run_id",
            "episode_id",
            "world_branch_id",
            "base_state_id",
            "base_commit_id",
        ):
            require_world_run_text(getattr(self, field_name), field_name)
        if self.based_on_sequence < 0:
            raise PumpStationWorldRunError("command-shape", "based_on_sequence must be non-negative")
        actor_fields = (
            ("decision_id", self.decision_id),
            ("actor_id", self.actor_id),
            ("agent_tenure_id", self.agent_tenure_id),
            ("actor_view_id", self.actor_view_id),
            ("information_set_id", self.information_set_id),
        )
        if self.kind == "actor":
            if any(value is None for _, value in actor_fields) or self.authority_id is not None:
                raise PumpStationWorldRunError("command-shape", "actor command lacks its actor binding")
            for field_name, value in actor_fields:
                require_world_run_text(value, field_name)
        else:
            if any(value is not None for _, value in actor_fields) or self.authority_id is None:
                raise PumpStationWorldRunError(
                    "command-shape",
                    "host-control command has an actor binding or lacks authority",
                )
            require_world_run_text(self.authority_id, "authority_id")
        try:
            arguments = json.loads(
                self.arguments_json,
                object_pairs_hook=_unique_json_object,
                parse_constant=_reject_nonstandard_json_constant,
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise PumpStationWorldRunError("canonical-json", str(error)) from error
        if not isinstance(arguments, dict):
            raise PumpStationWorldRunError("command-shape", "arguments must be an object")
        canonical = json.dumps(arguments, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if canonical != self.arguments_json:
            raise PumpStationWorldRunError("canonical-json", "command arguments are not canonical")


@dataclass(frozen=True, slots=True)
class PumpStationWorldRunCommit:
    """Opening commit for the one current run record family."""

    run_id: str
    sequence: int
    parent_commit_id: None
    state_id: str
    proposal_id: None
    proposal_content_id: None
    information_set_content_id: None
    receipt_content_id: None
    event_batch_content_id: None

    def __post_init__(self) -> None:
        require_world_run_text(self.run_id, "run_id")
        require_world_run_text(self.state_id, "state_id")
        if self.sequence < 0:
            raise PumpStationWorldRunError("world-run-shape", "initial commit sequence must be non-negative")


@dataclass(frozen=True, slots=True)
class PumpStationCommandCommit:
    """Immutable link from one parent commit to complete current command evidence."""

    run_id: str
    sequence: int
    parent_commit_id: str
    state_id: str
    request_id: str
    command_content_id: str
    proposal_content_id: str | None
    information_set_content_id: str | None
    receipt_content_id: str

    def __post_init__(self) -> None:
        for field_name in (
            "run_id",
            "parent_commit_id",
            "state_id",
            "request_id",
            "command_content_id",
            "receipt_content_id",
        ):
            require_world_run_text(getattr(self, field_name), field_name)
        if self.sequence < 1:
            raise PumpStationWorldRunError("world-run-shape", "transition commit sequence must be positive")
        if (self.proposal_content_id is None) != (self.information_set_content_id is None):
            raise PumpStationWorldRunError(
                "world-run-shape",
                "actor proposal and information set must appear together",
            )
        if self.proposal_content_id is not None:
            require_world_run_text(self.proposal_content_id, "proposal_content_id")
            require_world_run_text(self.information_set_content_id, "information_set_content_id")


type PumpStationCommit = PumpStationWorldRunCommit | PumpStationCommandCommit


@dataclass(frozen=True, slots=True)
class PumpStationCurrentRunPointer:
    """Single mutable selector for the last atomically published commit."""

    run_id: str
    sequence: int
    state_id: str
    commit_id: str


@dataclass(frozen=True, slots=True)
class PumpStationStagedCommand:
    """Immutable command evidence prepared before current-state selection."""

    prior_snapshot: PumpStationStateSnapshotRef
    snapshot: PumpStationStateSnapshotRef
    command: PumpStationCommand
    transition: PumpStationCoupledTransition
    commit: PumpStationCommandCommit
    proposal: PumpStationProposal | None = None
    information_set: PumpStationInformationSet | None = None

    def __post_init__(self) -> None:
        actor_step = self.command.kind == "actor"
        if actor_step != (self.proposal is not None and self.information_set is not None):
            raise PumpStationWorldRunError(
                "transition-integrity",
                "actor evidence requires one proposal and information set",
            )


__all__ = [
    "PumpStationCommand",
    "PumpStationCommandCommit",
    "PumpStationCommit",
    "PumpStationCurrentRunPointer",
    "PumpStationInitialStateSource",
    "PumpStationRegisteredWorldRunManifest",
    "PumpStationStagedCommand",
    "PumpStationStateSnapshotRef",
    "PumpStationWorldRunError",
    "PumpStationWorldRunCommit",
]
