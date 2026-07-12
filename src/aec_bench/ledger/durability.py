# ABOUTME: Provides fsync-aware filesystem primitives for immutable ledger publication.
# ABOUTME: Makes newly created directories, staged trees, and parent entries power-loss durable.

import os
from pathlib import Path


def mkdir_durable(path: Path) -> None:
    """Create a directory tree and fsync every parent whose child entry changed."""
    target = Path(path)
    missing: list[Path] = []
    cursor = target
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    target.mkdir(parents=True, exist_ok=True)
    for directory in reversed(missing):
        fsync_directory(directory.parent)


def fsync_tree(root: Path) -> None:
    """Flush every regular file and directory in one staged publication tree."""
    for path in sorted(item for item in Path(root).rglob("*") if item.is_file()):
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    directories = [Path(root), *(item for item in Path(root).rglob("*") if item.is_dir())]
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        fsync_directory(path)


def fsync_directory(path: Path) -> None:
    """Flush one directory entry table."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
