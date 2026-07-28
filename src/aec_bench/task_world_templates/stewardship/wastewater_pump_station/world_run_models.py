# ABOUTME: Defines durable run, snapshot, commit, and event records for the pump station.
# ABOUTME: Keeps evolving state references separate from compiled world-package identity.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationEventType,
    PumpStationProposal,
    PumpStationTransition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
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


@dataclass(frozen=True, slots=True)
class PumpStationWorldRunManifest:
    """Immutable identity and initial state for one continuing world branch."""

    serialization_version: str
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


@dataclass(frozen=True, slots=True)
class PumpStationCurrentRunPointer:
    """Single mutable selector for the last atomically published commit."""

    serialization_version: str
    run_id: str
    sequence: int
    state_id: str
    commit_id: str


@dataclass(frozen=True, slots=True)
class PumpStationStagedTransition:
    """Immutable evidence prepared before the current-state commit point."""

    prior_snapshot: PumpStationStateSnapshotRef
    snapshot: PumpStationStateSnapshotRef
    proposal: PumpStationProposal
    information_set: PumpStationInformationSet
    transition: PumpStationTransition
    commit: PumpStationWorldRunCommit
