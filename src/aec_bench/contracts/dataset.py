# ABOUTME: Contract models for versioned, immutable benchmark dataset snapshots.
# ABOUTME: Defines the manifest, description, task entry, and source provenance models.

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class DatasetTaskEntry(StrictModel):
    """One task instance in a dataset. Flat list — consumers group by domain/difficulty."""

    task_id: NonEmptyStr
    task_path: NonEmptyStr
    content_hash: NonEmptyStr
    domain: NonEmptyStr
    difficulty: NonEmptyStr
    tags: list[str] = Field(default_factory=list)


class DatasetDescription(StrictModel):
    """Structured metadata that renders in CLI and TUI."""

    summary: NonEmptyStr
    purpose: str | None = None
    standards: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    template_count: int = 0
    task_count: int = 0


class DatasetSource(StrictModel):
    """Provenance: how the dataset was created."""

    method: Literal["suite_config", "manual", "import"]
    suite_config: dict[str, Any] | None = None
    seed: int | None = None
    template_versions: dict[str, str] = Field(default_factory=dict)


class DatasetManifest(StrictModel):
    """Top-level dataset contract. Stored as manifest.json."""

    name: NonEmptyStr
    version: NonEmptyStr
    content_hash: NonEmptyStr
    description: DatasetDescription
    created_at: datetime
    tasks: list[DatasetTaskEntry]
    source: DatasetSource

    @field_validator("tasks")
    @classmethod
    def validate_tasks_non_empty(cls, value: list[DatasetTaskEntry]) -> list[DatasetTaskEntry]:
        if not value:
            msg = "tasks list must contain at least one task"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_unique_task_ids(self) -> DatasetManifest:
        seen: set[str] = set()
        for task in self.tasks:
            if task.task_id in seen:
                msg = f"task_id values must be unique, found duplicate: {task.task_id}"
                raise ValueError(msg)
            seen.add(task.task_id)
        return self
