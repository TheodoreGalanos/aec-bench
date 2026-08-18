# ABOUTME: Defines semantic dataset manifests and their two immutable execution references.
# ABOUTME: Keeps publication labels and event time outside dataset content identity.

from __future__ import annotations

import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

_DATASET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_FULL_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
type DatasetTaskKind = Literal["artifact", "lifecycle", "world"]


def _validate_dataset_id(value: str) -> str:
    if not _DATASET_ID_PATTERN.fullmatch(value):
        raise ValueError("dataset_id must use only letters, numbers, dot, underscore, and hyphen")
    return value


def _validate_portable_relative_path(value: str) -> str:
    if "\\" in value:
        raise ValueError("path must use portable forward slashes")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path must be a portable relative path")
    if path.as_posix() != value:
        raise ValueError("path must be a normalized portable relative path")
    return value


class DatasetTaskEntry(FrozenStrictModel):
    """One task selected by semantic identity and repository-relative location."""

    task_id: NonEmptyStr
    path: NonEmptyStr
    task_kind: DatasetTaskKind

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_portable_relative_path(value)


class DatasetGeneration(FrozenStrictModel):
    """Replay inputs for a generated selection, when the dataset has them."""

    seed: int | None = None
    config_ref: NonEmptyStr | None = None

    @field_validator("config_ref")
    @classmethod
    def validate_config_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_portable_relative_path(value)

    @model_validator(mode="after")
    def validate_not_empty(self) -> DatasetGeneration:
        if self.seed is None and self.config_ref is None:
            raise ValueError("generation must declare a seed, config_ref, or both")
        return self


class DatasetManifest(FrozenStrictModel):
    """Semantic dataset content. Exact source or bundle identity lives in a DatasetRef."""

    schema_version: Literal[2] = 2
    dataset_id: NonEmptyStr
    description: NonEmptyStr
    tasks: tuple[DatasetTaskEntry, ...]
    generation: DatasetGeneration | None = None

    @field_validator("dataset_id")
    @classmethod
    def validate_dataset_id(cls, value: str) -> str:
        return _validate_dataset_id(value)

    @field_validator("tasks")
    @classmethod
    def validate_tasks_non_empty(cls, value: tuple[DatasetTaskEntry, ...]) -> tuple[DatasetTaskEntry, ...]:
        if not value:
            raise ValueError("tasks list must contain at least one task")
        return value

    @model_validator(mode="after")
    def validate_unique_tasks(self) -> DatasetManifest:
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id values must be unique")

        task_paths = [task.path for task in self.tasks]
        if len(task_paths) != len(set(task_paths)):
            raise ValueError("task paths must be unique")
        ordered_paths = sorted(PurePosixPath(path).parts for path in task_paths)
        for index, parts in enumerate(ordered_paths[:-1]):
            following = ordered_paths[index + 1]
            if following[: len(parts)] == parts:
                raise ValueError("task paths must not overlap")
        return self


class RepositoryDatasetRef(FrozenStrictModel):
    """Dataset material retained by a Git repository at one exact commit."""

    kind: Literal["repository"] = "repository"
    dataset_id: NonEmptyStr
    source_revision: NonEmptyStr
    manifest_path: NonEmptyStr

    @field_validator("dataset_id")
    @classmethod
    def validate_dataset_id(cls, value: str) -> str:
        return _validate_dataset_id(value)

    @field_validator("source_revision")
    @classmethod
    def validate_source_revision(cls, value: str) -> str:
        if not _FULL_GIT_SHA_PATTERN.fullmatch(value):
            raise ValueError("source_revision must be a lowercase 40-character Git commit")
        return value

    @field_validator("manifest_path")
    @classmethod
    def validate_manifest_path(cls, value: str) -> str:
        return _validate_portable_relative_path(value)


class BundleDatasetRef(FrozenStrictModel):
    """Dataset material retained as one exact detached bundle."""

    kind: Literal["bundle"] = "bundle"
    dataset_id: NonEmptyStr
    artifact: ArtifactRef

    @field_validator("dataset_id")
    @classmethod
    def validate_dataset_id(cls, value: str) -> str:
        return _validate_dataset_id(value)


type DatasetRef = Annotated[RepositoryDatasetRef | BundleDatasetRef, Field(discriminator="kind")]


class DatasetPublication(FrozenStrictModel):
    """A human discovery label assigned to an immutable dataset reference."""

    dataset_ref: DatasetRef
    label: NonEmptyStr
    published_at: datetime

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        _validate_dataset_id(value)
        if value.casefold() == "latest":
            raise ValueError("latest is a mutable selector and cannot be a persisted publication label")
        return value

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must include a timezone")
        return value


def dataset_reference_key(reference: DatasetRef) -> str:
    """Return the immutable transitional string stored by the current TrialRecord contract."""

    if isinstance(reference, RepositoryDatasetRef):
        return f"repository:{reference.dataset_id}@{reference.source_revision}:{reference.manifest_path}"
    return f"bundle:{reference.dataset_id}@{reference.artifact.sha256}"


__all__ = (
    "BundleDatasetRef",
    "DatasetGeneration",
    "DatasetManifest",
    "DatasetPublication",
    "DatasetRef",
    "DatasetTaskEntry",
    "DatasetTaskKind",
    "RepositoryDatasetRef",
    "dataset_reference_key",
)
