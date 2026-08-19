# ABOUTME: Defines the two authoritative identities for exact runnable task snapshots.
# ABOUTME: Uses one Git revision and path or one detached artifact reference without parallel hashes.

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, field_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


def _validate_full_git_sha(value: str) -> str:
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("source_revision must be a lowercase 40-character Git commit")
    return value


def _validate_relative_path(value: str) -> str:
    if "\\" in value:
        raise ValueError("task_path must use portable forward slashes")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("task_path must be a portable relative path")
    if path.as_posix() != value:
        raise ValueError("task_path must be a normalized portable relative path")
    return value


class RepositoryTaskSnapshotRef(FrozenStrictModel):
    """One task retained in Git at an exact commit and repository-relative path."""

    kind: Literal["repository"] = "repository"
    task_id: NonEmptyStr
    source_revision: NonEmptyStr
    task_path: NonEmptyStr

    @field_validator("source_revision")
    @classmethod
    def validate_source_revision(cls, value: str) -> str:
        return _validate_full_git_sha(value)

    @field_validator("task_path")
    @classmethod
    def validate_task_path(cls, value: str) -> str:
        return _validate_relative_path(value)

    @property
    def commitment_sha256(self) -> str:
        """Return one named commitment for contracts that must bind this exact reference."""

        return task_snapshot_commitment(self)


class ArtifactTaskSnapshotRef(FrozenStrictModel):
    """One detached runnable task package retained as exact artifact bytes."""

    kind: Literal["artifact"] = "artifact"
    task_id: NonEmptyStr
    artifact: ArtifactRef

    @property
    def commitment_sha256(self) -> str:
        """Return one named commitment for contracts that must bind this exact reference."""

        return task_snapshot_commitment(self)


type TaskSnapshotRef = Annotated[
    RepositoryTaskSnapshotRef | ArtifactTaskSnapshotRef,
    Field(discriminator="kind"),
]


def task_snapshot_id(reference: TaskSnapshotRef) -> str:
    """Return the stable task domain ID without creating another identity field."""

    return reference.task_id


def task_snapshot_commitment(reference: TaskSnapshotRef) -> str:
    """Commit to one exact task relationship without adding another stored identity field."""

    return canonical_json_sha256(reference.model_dump(mode="json"))


def task_snapshot_source_key(reference: TaskSnapshotRef) -> tuple[object, ...]:
    """Return the exact retained source coordinate without the stable task domain ID."""

    if isinstance(reference, RepositoryTaskSnapshotRef):
        return (reference.kind, reference.source_revision, reference.task_path)
    return (
        reference.kind,
        reference.artifact.artifact_id,
        reference.artifact.sha256,
        reference.artifact.size_bytes,
        reference.artifact.media_type,
    )


__all__ = (
    "ArtifactTaskSnapshotRef",
    "RepositoryTaskSnapshotRef",
    "TaskSnapshotRef",
    "task_snapshot_commitment",
    "task_snapshot_id",
    "task_snapshot_source_key",
)
