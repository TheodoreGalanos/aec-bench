# ABOUTME: Reads schema-1 dataset manifests only for bounded verification and migration.
# ABOUTME: Republishes legacy data only when all historical hashes match supplied task bytes.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from aec_bench.contracts.dataset import DatasetManifest, DatasetPublication, DatasetTaskEntry
from aec_bench.dataset.hashing import hash_task_directory
from aec_bench.dataset.publication import publish_dataset
from aec_bench.dataset.storage import save_dataset


class LegacyMigrationStatus(StrEnum):
    """Verification state for one schema-1 manifest."""

    FULLY_VERIFIED = "fully_verified"
    PARTIALLY_VERIFIED = "partially_verified"
    INVALID = "invalid"


@dataclass(frozen=True)
class LegacyMigrationResult:
    """A migration decision and its verified schema-2 result, when safe."""

    status: LegacyMigrationStatus
    manifest: DatasetManifest | None
    issues: tuple[str, ...]


def _manifest_hash(task_pairs: list[tuple[str, str]]) -> str:
    content = "\n".join(f"{task_id}:{digest}" for task_id, digest in sorted(task_pairs))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_document(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read v1 dataset manifest: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("v1 dataset manifest must be a JSON object")
    return document


def _string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"v1 dataset {field} must be a non-empty string")
    return value


def _legacy_tasks(document: dict[str, Any]) -> tuple[tuple[DatasetTaskEntry, str], ...]:
    tasks = document.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("v1 dataset tasks must be a non-empty list")

    converted: list[tuple[DatasetTaskEntry, str]] = []
    for index, raw_task in enumerate(tasks):
        if not isinstance(raw_task, dict):
            raise ValueError(f"v1 dataset task {index} must be an object")
        task_id = _string(raw_task.get("task_id"), field=f"tasks[{index}].task_id")
        task_path = _string(raw_task.get("task_path"), field=f"tasks[{index}].task_path")
        digest = _string(raw_task.get("content_hash"), field=f"tasks[{index}].content_hash")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"v1 dataset tasks[{index}].content_hash must be a lowercase SHA-256 digest")
        try:
            entry = DatasetTaskEntry(task_id=task_id, path=task_path, task_kind="artifact")
        except ValidationError as error:
            raise ValueError(str(error)) from error
        converted.append((entry, digest))
    return tuple(converted)


def inspect_v1_manifest(path: Path, *, project_root: Path | None = None) -> LegacyMigrationResult:
    """Inspect a v1 manifest without treating partial evidence as a valid conversion."""

    try:
        document = _load_document(path)
        dataset_id = _string(document.get("name"), field="name")
        top_level_hash = _string(document.get("content_hash"), field="content_hash")
        description = document.get("description")
        if not isinstance(description, dict):
            raise ValueError("v1 dataset description must be an object")
        summary = _string(description.get("summary"), field="description.summary")
        tasks = _legacy_tasks(document)
        expected_top_level_hash = _manifest_hash([(task.task_id, digest) for task, digest in tasks])
        if top_level_hash != expected_top_level_hash:
            return LegacyMigrationResult(
                status=LegacyMigrationStatus.INVALID,
                manifest=None,
                issues=("top-level content_hash mismatch",),
            )
        if project_root is None:
            return LegacyMigrationResult(
                status=LegacyMigrationStatus.PARTIALLY_VERIFIED,
                manifest=None,
                issues=("task bytes were not supplied for v1 hash verification",),
            )

        root = project_root.resolve()
        issues: list[str] = []
        for task, expected_hash in tasks:
            task_directory = (root / task.path).resolve()
            try:
                task_directory.relative_to(root)
            except ValueError:
                issues.append(f"task path escapes project root: {task.task_id}")
                continue
            if not task_directory.is_dir():
                issues.append(f"task is missing: {task.task_id}")
            elif hash_task_directory(task_directory) != expected_hash:
                issues.append(f"task hash mismatch: {task.task_id}")
        if issues:
            return LegacyMigrationResult(
                status=LegacyMigrationStatus.INVALID,
                manifest=None,
                issues=tuple(issues),
            )

        manifest = DatasetManifest(
            dataset_id=dataset_id,
            description=summary,
            tasks=tuple(task for task, _ in tasks),
        )
    except (TypeError, ValueError) as error:
        return LegacyMigrationResult(
            status=LegacyMigrationStatus.INVALID,
            manifest=None,
            issues=(str(error),),
        )

    return LegacyMigrationResult(
        status=LegacyMigrationStatus.FULLY_VERIFIED,
        manifest=manifest,
        issues=(),
    )


def migrate_v1_dataset(
    path: Path,
    *,
    project_root: Path | None,
    datasets_root: Path,
    label: str,
) -> DatasetPublication:
    """Republish a v1 dataset as a schema-2 detached bundle after complete verification."""

    result = inspect_v1_manifest(path, project_root=project_root)
    if result.status is not LegacyMigrationStatus.FULLY_VERIFIED or result.manifest is None or project_root is None:
        detail = "; ".join(result.issues) or result.status.value
        raise ValueError(f"v1 dataset must be fully verified before migration: {detail}")
    save_dataset(datasets_root, result.manifest)
    return publish_dataset(
        manifest=result.manifest,
        datasets_root=datasets_root,
        project_root=project_root,
        label=label,
    )


__all__ = (
    "LegacyMigrationResult",
    "LegacyMigrationStatus",
    "inspect_v1_manifest",
    "migrate_v1_dataset",
)
