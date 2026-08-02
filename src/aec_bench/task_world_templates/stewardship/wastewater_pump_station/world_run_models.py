# ABOUTME: Defines durable run, snapshot, commit, and event records for the pump station.
# ABOUTME: Keeps evolving state references separate from compiled world-package identity.

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import NoReturn

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PumpStationPhysicalTreatmentActivationRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V1,
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V2,
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V3,
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V4,
    PUMP_STATION_RECEIPT_VERSION_V1,
    PUMP_STATION_RECEIPT_VERSION_V2,
    PUMP_STATION_RECEIPT_VERSION_V3,
    PUMP_STATION_RECEIPT_VERSION_V4,
    PUMP_STATION_TRANSITION_RULE_VERSION_V1,
    PUMP_STATION_TRANSITION_RULE_VERSION_V2,
    PUMP_STATION_TRANSITION_RULE_VERSION_V3,
    PUMP_STATION_TRANSITION_RULE_VERSION_V4,
    PumpStationEventType,
    PumpStationProposal,
    PumpStationTransition,
    PumpStationTransitionV4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
)

PUMP_STATION_SERIALIZATION_VERSION = "pump-station-world-run.v1"
PUMP_STATION_WORLD_MANIFEST_VERSION_V2 = "pump-station-world-run.v2"
PUMP_STATION_SNAPSHOT_VERSION_V1 = "pump-station-state-snapshot.v1"
PUMP_STATION_SNAPSHOT_VERSION_V2 = "pump-station-state-snapshot.v2"
PUMP_STATION_SNAPSHOT_VERSION_V3 = "pump-station-state-snapshot.v3"
PUMP_STATION_SNAPSHOT_VERSION_V4 = "pump-station-state-snapshot.v4"
PUMP_STATION_SNAPSHOT_VERSION = PUMP_STATION_SNAPSHOT_VERSION_V1
PUMP_STATION_MIGRATION_VERSION = "pump-station-world-run-migration.v1"
PUMP_STATION_COMMAND_VERSION_V4 = "pump-station-world-command.v4"


@dataclass(frozen=True, slots=True)
class PumpStationRecordVersions:
    """One coherent snapshot, receipt, policy, and rule version set."""

    snapshot_version: str
    receipt_version: str
    authority_policy_version: str
    transition_rule_version: str


PUMP_STATION_RECORD_VERSIONS_V1 = PumpStationRecordVersions(
    snapshot_version=PUMP_STATION_SNAPSHOT_VERSION_V1,
    receipt_version=PUMP_STATION_RECEIPT_VERSION_V1,
    authority_policy_version=PUMP_STATION_AUTHORITY_POLICY_VERSION_V1,
    transition_rule_version=PUMP_STATION_TRANSITION_RULE_VERSION_V1,
)
PUMP_STATION_RECORD_VERSIONS_V2 = PumpStationRecordVersions(
    snapshot_version=PUMP_STATION_SNAPSHOT_VERSION_V2,
    receipt_version=PUMP_STATION_RECEIPT_VERSION_V2,
    authority_policy_version=PUMP_STATION_AUTHORITY_POLICY_VERSION_V2,
    transition_rule_version=PUMP_STATION_TRANSITION_RULE_VERSION_V2,
)
PUMP_STATION_RECORD_VERSIONS_V3 = PumpStationRecordVersions(
    snapshot_version=PUMP_STATION_SNAPSHOT_VERSION_V3,
    receipt_version=PUMP_STATION_RECEIPT_VERSION_V3,
    authority_policy_version=PUMP_STATION_AUTHORITY_POLICY_VERSION_V3,
    transition_rule_version=PUMP_STATION_TRANSITION_RULE_VERSION_V3,
)
PUMP_STATION_RECORD_VERSIONS_V4 = PumpStationRecordVersions(
    snapshot_version=PUMP_STATION_SNAPSHOT_VERSION_V4,
    receipt_version=PUMP_STATION_RECEIPT_VERSION_V4,
    authority_policy_version=PUMP_STATION_AUTHORITY_POLICY_VERSION_V4,
    transition_rule_version=PUMP_STATION_TRANSITION_RULE_VERSION_V4,
)
PUMP_STATION_SUPPORTED_RECORD_VERSIONS = (
    PUMP_STATION_RECORD_VERSIONS_V1,
    PUMP_STATION_RECORD_VERSIONS_V2,
    PUMP_STATION_RECORD_VERSIONS_V3,
    PUMP_STATION_RECORD_VERSIONS_V4,
)


class PumpStationWorldRunError(RuntimeError):
    """Raised when durable pump-station run evidence is invalid or unsafe."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def require_world_run_text(value: object, field_name: str) -> None:
    """Require one non-empty durable identity."""
    if not isinstance(value, str) or not value.strip():
        raise PumpStationWorldRunError(
            "world-run-shape",
            f"{field_name} must not be empty",
        )


def require_world_run_version(
    value: str,
    expected: str | tuple[str, ...],
    code: str,
) -> None:
    """Reject one unsupported durable artifact version."""
    supported = (expected,) if isinstance(expected, str) else expected
    if value not in supported:
        raise PumpStationWorldRunError(code, value)


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
        require_world_run_text(
            self.opening_specification_sha256,
            "opening_specification_sha256",
        )
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
            raise PumpStationWorldRunError(
                "initial-state-source",
                self.kind,
            )
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
class _PumpStationWorldRunManifestFields:
    """Common identity fields carried by both durable manifest versions."""

    serialization_version: str
    snapshot_version: str
    receipt_version: str
    authority_policy_version: str
    transition_rule_version: str
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

    def _validate_common_fields(self) -> None:
        for field_name in (
            "serialization_version",
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
        ):
            require_world_run_text(getattr(self, field_name), field_name)
        if self.initial_sequence < 0:
            raise PumpStationWorldRunError(
                "world-run-shape",
                "initial sequence must be non-negative",
            )
        require_world_run_version(
            self.snapshot_version,
            tuple(item.snapshot_version for item in PUMP_STATION_SUPPORTED_RECORD_VERSIONS),
            "snapshot-version",
        )
        require_world_run_version(
            self.receipt_version,
            tuple(item.receipt_version for item in PUMP_STATION_SUPPORTED_RECORD_VERSIONS),
            "receipt-version",
        )
        require_world_run_version(
            self.authority_policy_version,
            tuple(item.authority_policy_version for item in PUMP_STATION_SUPPORTED_RECORD_VERSIONS),
            "authority-policy-version",
        )
        require_world_run_version(
            self.transition_rule_version,
            tuple(item.transition_rule_version for item in PUMP_STATION_SUPPORTED_RECORD_VERSIONS),
            "transition-rule-version",
        )

    @property
    def record_versions(self) -> PumpStationRecordVersions:
        """Return the coherent record versions selected by the run."""
        return PumpStationRecordVersions(
            snapshot_version=self.snapshot_version,
            receipt_version=self.receipt_version,
            authority_policy_version=self.authority_policy_version,
            transition_rule_version=self.transition_rule_version,
        )


@dataclass(frozen=True, slots=True)
class PumpStationWorldRunManifest(_PumpStationWorldRunManifestFields):
    """Immutable legacy identity and initial state for one continuing branch."""

    def __post_init__(self) -> None:
        self._validate_common_fields()
        require_world_run_version(
            self.serialization_version,
            PUMP_STATION_SERIALIZATION_VERSION,
            "serialization-version",
        )
        if self.record_versions not in (
            PUMP_STATION_RECORD_VERSIONS_V1,
            PUMP_STATION_RECORD_VERSIONS_V2,
            PUMP_STATION_RECORD_VERSIONS_V3,
        ):
            raise PumpStationWorldRunError(
                "record-versions",
                "snapshot, receipt, policy, and rule versions differ",
            )


@dataclass(frozen=True, slots=True)
class PumpStationWorldRunManifestV2(_PumpStationWorldRunManifestFields):
    """Required registered-profile bindings for one V4 root or rollout branch."""

    task_world_id: str
    definition_version: str
    definition_content_sha256: str
    continual_profile_id: str
    continual_profile_version: str
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
        self._validate_common_fields()
        require_world_run_version(
            self.serialization_version,
            PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
            "serialization-version",
        )
        if self.record_versions != PUMP_STATION_RECORD_VERSIONS_V4:
            raise PumpStationWorldRunError(
                "record-versions",
                "manifest v2 requires the coherent V4 record set",
            )
        reference_bindings = (
            self.task_world_id,
            self.definition_version,
            self.definition_content_sha256,
            self.continual_profile_id,
            self.continual_profile_version,
            self.continual_profile_content_sha256,
            self.reference_system_id,
            self.reference_system_content_id,
            self.opening_state_specification_id,
            self.opening_state_specification_sha256,
            self.event_schedule_id,
            self.event_schedule_sha256,
            self.temporal_template_id,
            self.temporal_template_sha256,
            self.temporal_bundle_content_id,
            self.temporal_corpus_content_id,
            self.temporal_capability_content_id,
        )
        for index, value in enumerate(reference_bindings):
            require_world_run_text(value, f"reference_bindings[{index}]")
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


type PumpStationWorldRunManifestRecord = PumpStationWorldRunManifest | PumpStationWorldRunManifestV2


@dataclass(frozen=True, slots=True)
class PumpStationStateSnapshotRef:
    """Exact dynamic state selected for one durable pump-station run."""

    snapshot_version: str
    run_id: str
    episode_id: str
    world_branch_id: str
    sequence: int
    state_id: str
    commit_id: str

    def __post_init__(self) -> None:
        for field_name in (
            "run_id",
            "episode_id",
            "world_branch_id",
            "state_id",
            "commit_id",
        ):
            require_world_run_text(getattr(self, field_name), field_name)
        if self.sequence < 0:
            raise PumpStationWorldRunError(
                "world-run-shape",
                "snapshot sequence must be non-negative",
            )
        require_world_run_version(
            self.snapshot_version,
            (
                PUMP_STATION_SNAPSHOT_VERSION_V1,
                PUMP_STATION_SNAPSHOT_VERSION_V2,
                PUMP_STATION_SNAPSHOT_VERSION_V3,
                PUMP_STATION_SNAPSHOT_VERSION_V4,
            ),
            "snapshot-version",
        )


@dataclass(frozen=True, slots=True)
class PumpStationWorldRunMigration:
    """Immutable source lineage for one supported next-version continuation."""

    migration_version: str
    source_run_id: str
    source_world_branch_id: str
    source_state_id: str
    source_snapshot_version: str
    source_receipt_version: str
    source_authority_policy_version: str
    source_transition_rule_version: str
    target_run_id: str
    target_world_branch_id: str
    target_state_id: str
    target_snapshot_version: str
    target_receipt_version: str
    target_authority_policy_version: str
    target_transition_rule_version: str

    def __post_init__(self) -> None:
        require_world_run_version(
            self.migration_version,
            PUMP_STATION_MIGRATION_VERSION,
            "migration-version",
        )
        for field_name in (
            "source_run_id",
            "source_world_branch_id",
            "source_state_id",
            "target_run_id",
            "target_world_branch_id",
            "target_state_id",
        ):
            require_world_run_text(getattr(self, field_name), field_name)
        source = PumpStationRecordVersions(
            snapshot_version=self.source_snapshot_version,
            receipt_version=self.source_receipt_version,
            authority_policy_version=self.source_authority_policy_version,
            transition_rule_version=self.source_transition_rule_version,
        )
        target = PumpStationRecordVersions(
            snapshot_version=self.target_snapshot_version,
            receipt_version=self.target_receipt_version,
            authority_policy_version=self.target_authority_policy_version,
            transition_rule_version=self.target_transition_rule_version,
        )
        supported_pairs = {
            (PUMP_STATION_RECORD_VERSIONS_V1, PUMP_STATION_RECORD_VERSIONS_V2),
            (PUMP_STATION_RECORD_VERSIONS_V2, PUMP_STATION_RECORD_VERSIONS_V3),
        }
        if (source, target) not in supported_pairs:
            raise PumpStationWorldRunError(
                "migration-version-pair",
                f"{source} -> {target}",
            )


@dataclass(frozen=True, slots=True)
class PumpStationAppliedEventBatch:
    """Events applied by one transition, including an empty proposal-only batch."""

    transition_id: str
    sequence: int
    event_ids: tuple[str, ...]
    event_types: tuple[PumpStationEventType, ...]


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, child in pairs:
        if key in value:
            raise PumpStationWorldRunError("canonical-json", f"duplicate field {key}")
        value[key] = child
    return value


def _reject_nonstandard_json_constant(value: str) -> NoReturn:
    raise PumpStationWorldRunError(
        "canonical-json",
        f"non-standard JSON constant {value}",
    )


@dataclass(frozen=True, slots=True)
class PumpStationCommandV4:
    """Exact actor or host-control command bound to one selected V4 parent."""

    command_version: str
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
    session_id: str | None = None
    agent_tenure_id: str | None = None
    actor_view_id: str | None = None
    information_set_id: str | None = None
    authority_id: str | None = None

    def __post_init__(self) -> None:
        require_world_run_version(
            self.command_version,
            PUMP_STATION_COMMAND_VERSION_V4,
            "command-version",
        )
        expected_actions = {
            "operations_review": "operations_boundary_review",
            "process_outcome": "process_outcome",
            "common_boundary": "common_boundary_control",
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
            raise PumpStationWorldRunError(
                "command-shape",
                "based_on_sequence must be non-negative",
            )
        actor_fields = (
            ("session_id", self.session_id),
            ("agent_tenure_id", self.agent_tenure_id),
            ("actor_view_id", self.actor_view_id),
            ("information_set_id", self.information_set_id),
        )
        if self.kind == "actor":
            if any(value is None for _, value in actor_fields) or self.authority_id is not None:
                raise PumpStationWorldRunError(
                    "command-shape",
                    "actor command lacks its actor binding",
                )
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
        canonical = json.dumps(
            arguments,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        if canonical != self.arguments_json:
            raise PumpStationWorldRunError(
                "canonical-json",
                "command arguments are not canonical",
            )


@dataclass(frozen=True, slots=True)
class PumpStationWorldRunCommit:
    """Immutable link from one committed state to its complete transition evidence."""

    serialization_version: str
    run_id: str
    sequence: int
    parent_commit_id: str | None
    state_id: str
    proposal_id: str | None
    proposal_content_id: str | None
    information_set_content_id: str | None
    receipt_content_id: str | None
    event_batch_content_id: str | None

    def __post_init__(self) -> None:
        require_world_run_version(
            self.serialization_version,
            PUMP_STATION_SERIALIZATION_VERSION,
            "serialization-version",
        )


@dataclass(frozen=True, slots=True)
class PumpStationWorldRunCommitV2:
    """Immutable V4 link from one parent commit to complete command evidence."""

    serialization_version: str
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
        require_world_run_version(
            self.serialization_version,
            PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
            "serialization-version",
        )
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
            raise PumpStationWorldRunError(
                "world-run-shape",
                "V4 transition commit sequence must be positive",
            )
        if (self.proposal_content_id is None) != (self.information_set_content_id is None):
            raise PumpStationWorldRunError(
                "world-run-shape",
                "V4 actor proposal and information set must appear together",
            )
        if self.proposal_content_id is not None:
            require_world_run_text(self.proposal_content_id, "proposal_content_id")
            require_world_run_text(
                self.information_set_content_id,
                "information_set_content_id",
            )


type PumpStationWorldRunCommitRecord = PumpStationWorldRunCommit | PumpStationWorldRunCommitV2


@dataclass(frozen=True, slots=True)
class PumpStationCurrentRunPointer:
    """Single mutable selector for the last atomically published commit."""

    serialization_version: str
    run_id: str
    sequence: int
    state_id: str
    commit_id: str

    def __post_init__(self) -> None:
        require_world_run_version(
            self.serialization_version,
            PUMP_STATION_SERIALIZATION_VERSION,
            "serialization-version",
        )


@dataclass(frozen=True, slots=True)
class PumpStationStagedTransition:
    """Immutable evidence prepared before the current-state commit point."""

    prior_snapshot: PumpStationStateSnapshotRef
    snapshot: PumpStationStateSnapshotRef
    proposal: PumpStationProposal | None
    information_set: PumpStationInformationSet | None
    transition: PumpStationTransition
    commit: PumpStationWorldRunCommit
    control_request: PumpStationEvidenceTreatmentRequest | PumpStationPhysicalTreatmentActivationRequest | None = None


@dataclass(frozen=True, slots=True)
class PumpStationStagedTransitionV4:
    """Immutable V4 evidence prepared before current-state selection."""

    prior_snapshot: PumpStationStateSnapshotRef
    snapshot: PumpStationStateSnapshotRef
    command: PumpStationCommandV4
    transition: PumpStationTransitionV4
    commit: PumpStationWorldRunCommitV2
    proposal: PumpStationProposal | None = None
    information_set: PumpStationInformationSet | None = None

    def __post_init__(self) -> None:
        actor_step = self.command.kind == "actor"
        if actor_step != (self.proposal is not None and self.information_set is not None):
            raise PumpStationWorldRunError(
                "transition-integrity",
                "V4 actor evidence requires one proposal and information set",
            )
