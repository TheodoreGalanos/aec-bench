# ABOUTME: Dataset creator — builds versioned manifest from task definitions on disk.
# ABOUTME: Hashes each task directory, extracts description metadata, and writes to storage.

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from aec_bench.contracts.dataset import (
    DatasetDescription,
    DatasetManifest,
    DatasetSource,
    DatasetTaskEntry,
)
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.dataset.hashing import compute_manifest_hash, hash_task_directory
from aec_bench.dataset.storage import write_manifest

logger = logging.getLogger(__name__)


def _extract_standards(tasks: list[TaskDefinition]) -> list[str]:
    """Collect unique standard references from task metadata."""
    standards: set[str] = set()
    for task in tasks:
        standard = task.metadata.get("standard")
        if isinstance(standard, str) and standard.strip():
            standards.add(standard.strip())
    return sorted(standards)


def _build_description(
    tasks: list[DatasetTaskEntry],
    task_defs: list[TaskDefinition],
    summary: str | None,
    purpose: str | None,
) -> DatasetDescription:
    """Build structured description metadata from task entries and definitions."""
    domains = sorted({entry.domain for entry in tasks})
    difficulty_counts = Counter(entry.difficulty for entry in tasks)
    standards = _extract_standards(task_defs)

    return DatasetDescription(
        summary=summary or f"Dataset with {len(tasks)} tasks",
        purpose=purpose,
        domains=domains,
        difficulty_distribution=dict(difficulty_counts),
        standards=standards,
        task_count=len(tasks),
    )


def create_dataset_from_tasks(
    name: str,
    version: str,
    tasks: list[TaskDefinition],
    tasks_root: Path,
    datasets_root: Path,
    source: DatasetSource,
    summary: str | None = None,
    purpose: str | None = None,
    overwrite: bool = False,
) -> DatasetManifest:
    """Create a dataset manifest from task definitions on disk.

    Hashes each task directory, builds description metadata from the tasks,
    computes a manifest-level content hash, and writes the manifest to storage.
    Tasks whose directories are missing on disk are logged and skipped.
    """
    task_entries: list[DatasetTaskEntry] = []
    hash_pairs: list[tuple[str, str]] = []
    included_defs: list[TaskDefinition] = []

    for task_def in tasks:
        task_dir = tasks_root / task_def.task_id
        if not task_dir.is_dir():
            logger.warning(
                "skipping task %s — directory not found at %s",
                task_def.task_id,
                task_dir,
            )
            continue

        content_hash = hash_task_directory(task_dir)
        task_path = str(task_dir.relative_to(tasks_root.parent))

        entry = DatasetTaskEntry(
            task_id=task_def.task_id,
            task_path=task_path,
            content_hash=content_hash,
            domain=task_def.domain,
            difficulty=task_def.difficulty.value,
            tags=list(task_def.tags),
        )
        task_entries.append(entry)
        hash_pairs.append((task_def.task_id, content_hash))
        included_defs.append(task_def)

    manifest_hash = compute_manifest_hash(hash_pairs)
    description = _build_description(task_entries, included_defs, summary, purpose)

    manifest = DatasetManifest(
        name=name,
        version=version,
        content_hash=manifest_hash,
        description=description,
        created_at=datetime.now(tz=UTC),
        tasks=task_entries,
        source=source,
    )

    write_manifest(datasets_root, manifest, overwrite=overwrite)
    return manifest
