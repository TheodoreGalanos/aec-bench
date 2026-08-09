# ABOUTME: Defines the task port used by shared chosen-point rollout orchestration.
# ABOUTME: Keeps task state opaque while requiring exact origin and child verification.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildReceipt,
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualWorldSnapshotRef,
)


@dataclass(frozen=True, slots=True)
class VerifiedContinualWorldBranchOrigin:
    """Exact task-verified origin plus opaque task context for materialization."""

    parent_snapshot: ContinualWorldSnapshotRef
    parent_manifest_content_sha256: str
    origin_verification_content_sha256: str
    ancestor_world_branch_ids: tuple[str, ...]
    task_context: object


@dataclass(frozen=True, slots=True)
class ContinualWorldBranchMaterialization:
    """Shared child facts returned by one task-owned branch implementation."""

    initial_snapshot: ContinualWorldSnapshotRef
    child_manifest_content_sha256: str
    task_branch_receipt_content_sha256: str
    ancestor_world_branch_ids: tuple[str, ...]


class ContinualWorldBranchPort(Protocol):
    """Task-owned operations required by the shared rollout coordinator."""

    def verify_origin(
        self,
        *,
        profile_value: object,
        package_root: Path | None,
        parent_run_root: Path,
        request: ContinualRolloutGroupRequest,
    ) -> VerifiedContinualWorldBranchOrigin:
        """Verify one exact branchable snapshot without changing the parent."""

    def materialize_child(
        self,
        *,
        profile_value: object,
        package_root: Path | None,
        parent_run_root: Path,
        child_run_root: Path,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        origin: VerifiedContinualWorldBranchOrigin,
    ) -> ContinualWorldBranchMaterialization:
        """Create or exactly recover one isolated child from the verified origin.

        The shared coordinator serializes calls for one group and child identity.
        """

    def verify_child(
        self,
        *,
        profile_value: object,
        package_root: Path | None,
        parent_run_root: Path,
        child_run_root: Path,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        receipt: ContinualRolloutChildReceipt,
    ) -> None:
        """Verify the persisted child against its immutable shared receipt."""
