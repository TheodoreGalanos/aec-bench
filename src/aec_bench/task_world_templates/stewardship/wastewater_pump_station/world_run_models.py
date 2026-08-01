# ABOUTME: Defines durable run, snapshot, commit, and event records for the pump station.
# ABOUTME: Keeps evolving state references separate from compiled world-package identity.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V1,
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V2,
    PUMP_STATION_RECEIPT_VERSION_V1,
    PUMP_STATION_RECEIPT_VERSION_V2,
    PUMP_STATION_TRANSITION_RULE_VERSION_V1,
    PUMP_STATION_TRANSITION_RULE_VERSION_V2,
    PumpStationEventType,
    PumpStationProposal,
    PumpStationTransition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
)

PUMP_STATION_SERIALIZATION_VERSION = "pump-station-world-run.v1"
PUMP_STATION_SNAPSHOT_VERSION_V1 = "pump-station-state-snapshot.v1"
PUMP_STATION_SNAPSHOT_VERSION_V2 = "pump-station-state-snapshot.v2"
PUMP_STATION_SNAPSHOT_VERSION = PUMP_STATION_SNAPSHOT_VERSION_V1
PUMP_STATION_MIGRATION_VERSION = "pump-station-world-run-migration.v1"


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
PUMP_STATION_SUPPORTED_RECORD_VERSIONS = (
    PUMP_STATION_RECORD_VERSIONS_V1,
    PUMP_STATION_RECORD_VERSIONS_V2,
)


class PumpStationWorldRunError(RuntimeError):
    """Raised when durable pump-station run evidence is invalid or unsafe."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def require_world_run_text(value: str, field_name: str) -> None:
    """Require one non-empty durable identity."""
    if not value.strip():
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
class PumpStationWorldRunManifest:
    """Immutable identity and initial state for one continuing world branch."""

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

    def __post_init__(self) -> None:
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
            self.serialization_version,
            PUMP_STATION_SERIALIZATION_VERSION,
            "serialization-version",
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
        if self.record_versions not in PUMP_STATION_SUPPORTED_RECORD_VERSIONS:
            raise PumpStationWorldRunError(
                "record-versions",
                "snapshot, receipt, policy, and rule versions differ",
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
            (PUMP_STATION_SNAPSHOT_VERSION_V1, PUMP_STATION_SNAPSHOT_VERSION_V2),
            "snapshot-version",
        )


@dataclass(frozen=True, slots=True)
class PumpStationWorldRunMigration:
    """Immutable source lineage for one version-1 to version-2 continuation."""

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
        if source != PUMP_STATION_RECORD_VERSIONS_V1:
            raise PumpStationWorldRunError("migration-source-version", str(source))
        if target != PUMP_STATION_RECORD_VERSIONS_V2:
            raise PumpStationWorldRunError("migration-target-version", str(target))


@dataclass(frozen=True, slots=True)
class PumpStationAppliedEventBatch:
    """Events applied by one transition, including an empty proposal-only batch."""

    transition_id: str
    sequence: int
    event_ids: tuple[str, ...]
    event_types: tuple[PumpStationEventType, ...]


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
    proposal: PumpStationProposal
    information_set: PumpStationInformationSet
    transition: PumpStationTransition
    commit: PumpStationWorldRunCommit
