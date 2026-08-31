#!/usr/bin/env python3
# ABOUTME: Selects a deterministic shard of the maintained pytest files.
# ABOUTME: Gives nightly CI parallel execution without maintaining a second test inventory.

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SHARD_COUNT = 8


def discover_test_files(root: Path) -> tuple[str, ...]:
    """Return every pytest-discoverable Python test file under the repository test root."""

    test_root = root / "tests"
    files = {
        path.relative_to(root).as_posix()
        for path in test_root.rglob("*.py")
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    }
    return tuple(sorted(files))


def select_test_shard(test_files: tuple[str, ...], *, shard_index: int, shard_count: int) -> tuple[str, ...]:
    """Select one stable, non-overlapping shard from the complete test file set."""

    if shard_count < 1:
        raise ValueError("shard-count must be at least 1")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard-index must be between 0 and shard-count - 1")
    return tuple(path for position, path in enumerate(test_files) if position % shard_count == shard_index)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one deterministic pytest shard.")
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    root = args.root.resolve()
    test_files = discover_test_files(root)
    selected = select_test_shard(test_files, shard_index=args.shard_index, shard_count=args.shard_count)
    if not selected:
        parser.error(f"shard {args.shard_index} is empty for {len(test_files)} test files")
    print(f"Running shard {args.shard_index + 1}/{args.shard_count} ({len(selected)} files)")
    print(" ".join(selected))
    return subprocess.run([sys.executable, "-m", "pytest", "-q", *selected], cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
