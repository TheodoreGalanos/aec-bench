# ABOUTME: Defines exact build and profile identity for registered Interactive Worlds.
# ABOUTME: Keeps category identity separate from optional persistence, control, and rollout records.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.contracts.harness_kernel import validate_sha256


@dataclass(frozen=True, slots=True)
class InteractiveWorldProfileRef:
    """Exact identity of one task-owned Interactive World profile."""

    task_world_id: str
    profile_id: str
    profile_content_sha256: str

    def __post_init__(self) -> None:
        if not self.task_world_id.strip() or not self.profile_id.strip():
            raise ValueError("Interactive World profile identity values must be non-empty")
        validate_sha256(self.profile_content_sha256)


@dataclass(frozen=True, slots=True)
class WorldBuildRef:
    """Exact executable artifact selected for one registered world."""

    task_world_id: str
    entry_point: str
    artifact_sha256: str

    def __post_init__(self) -> None:
        if not self.task_world_id.strip() or not self.entry_point.strip():
            raise ValueError("world-build identity values must be non-empty")
        validate_sha256(self.artifact_sha256)
