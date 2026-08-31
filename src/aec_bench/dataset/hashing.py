# ABOUTME: Computes retained task-tree digests for packaged AEC-Bench tasks.
# ABOUTME: Dataset identity uses Git commits or enclosing ArtifactRef values.

from __future__ import annotations

import hashlib
from pathlib import Path

_EXCLUDE_DIRS = {"__pycache__"}
_EXCLUDE_SUFFIXES = {".pyc"}


def hash_task_directory(task_dir: Path) -> str:
    """Compute SHA256 hash of a task directory's contents.

    Walks the file tree lexicographically, hashing each file's relative
    path and content. Excludes __pycache__ directories and .pyc files.
    """
    hasher = hashlib.sha256()

    file_entries: list[tuple[str, Path]] = []
    for file_path in sorted(task_dir.rglob("*")):
        if not file_path.is_file():
            continue
        if any(part in _EXCLUDE_DIRS for part in file_path.parts):
            continue
        if file_path.suffix in _EXCLUDE_SUFFIXES:
            continue
        relative = file_path.relative_to(task_dir).as_posix()
        file_entries.append((relative, file_path))

    for relative, file_path in file_entries:
        hasher.update(relative.encode("utf-8"))
        hasher.update(file_path.read_bytes())

    return hasher.hexdigest()
