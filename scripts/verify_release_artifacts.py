#!/usr/bin/env python3
# ABOUTME: Checks that release archives contain only the public package surface.
# ABOUTME: Detects local workspaces, credentials, holdout material, and private build output before publication.

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

_FORBIDDEN_PARTS = {
    ".git",
    ".venv",
    "artefacts",
    "jobs",
    "private",
    "runs",
    "sealed",
    "task_decompositions",
    "task_genomes",
    "workspaces",
}
_FORBIDDEN_NAMES = {".env", "credentials.json"}
_FRONTEND_RUNS_SUFFIXES = (
    ("src", "aec_bench", "web", "frontend", "src", "runs"),
    ("aec_bench", "web", "frontend", "src", "runs"),
)


def _archive_names(path: Path) -> tuple[str, ...]:
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as archive:
            return tuple(archive.namelist())
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            return tuple(member.name for member in archive.getmembers())
    raise ValueError(f"unsupported release archive: {path}")


def verify_archive(path: Path) -> tuple[str, ...]:
    names = _archive_names(path)
    violations: list[str] = []
    for name in names:
        parts = PurePosixPath(name).parts
        parent_parts = parts[:-1]
        windows_parts = PureWindowsPath(name).parts
        if (
            name.startswith("/")
            or name.startswith("\\")
            or ".." in parts
            or ".." in windows_parts
            or PureWindowsPath(name).is_absolute()
        ):
            violations.append(f"{path.name}: unsafe archive path {name}")
            continue
        for part in parts:
            if part not in _FORBIDDEN_PARTS:
                continue
            # The frontend source legitimately contains ``src/runs``. A
            # top-level ``runs`` directory in an archive remains forbidden.
            if part == "runs" and any(parent_parts[-len(suffix) :] == suffix for suffix in _FRONTEND_RUNS_SUFFIXES):
                continue
            violations.append(f"{path.name}: forbidden path {name}")
            break
        if PurePosixPath(name).name in _FORBIDDEN_NAMES:
            violations.append(f"{path.name}: forbidden file {name}")
    if violations:
        raise ValueError("\n".join(violations))
    return names


def release_archives(dist: Path) -> tuple[Path, Path]:
    """Return the single wheel and source package selected for publication."""

    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError(f"expected exactly one wheel and one source package in {dist}")
    return wheels[0], sdists[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify release archive contents.")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()

    try:
        archives = release_archives(args.dist)
    except ValueError as error:
        parser.error(str(error))
    for archive in archives:
        names = verify_archive(archive)
        print(f"verified release scope: {archive.name} ({len(names)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
