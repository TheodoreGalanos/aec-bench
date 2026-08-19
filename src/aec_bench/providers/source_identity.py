# ABOUTME: Resolves provider package source to one clean Git revision or retained snapshot.
# ABOUTME: Creates deterministic source archives when a revision cannot reconstruct exact bytes.

from __future__ import annotations

import hashlib
import io
import stat
import subprocess
import tarfile
from collections.abc import Sequence
from pathlib import Path

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.provider_provenance import ProviderAdapterIdentity

_IGNORED_PARTS = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".svelte-kit", "__pycache__", "node_modules"}
)


def resolve_provider_adapter_identity(
    *,
    adapter_id: str,
    package_version: str,
    source_root: Path,
    source_paths: Sequence[Path],
    snapshot_path: Path,
    snapshot_artifact_id: str,
) -> ProviderAdapterIdentity:
    """Use a full Git revision for clean source, or retain deterministic source bytes."""
    root = Path(source_root).resolve()
    selected = _validated_source_paths(root, source_paths)
    revision = _clean_git_revision(root, selected)
    if revision is not None:
        return ProviderAdapterIdentity(
            adapter_id=adapter_id,
            package_version=package_version,
            source_revision=revision,
        )
    write_deterministic_source_snapshot(root=root, source_paths=selected, destination=snapshot_path)
    content = snapshot_path.read_bytes()
    return ProviderAdapterIdentity(
        adapter_id=adapter_id,
        package_version=package_version,
        source_snapshot=ArtifactRef(
            artifact_id=snapshot_artifact_id,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type="application/x-tar",
        ),
    )


def write_deterministic_source_snapshot(
    *,
    root: Path,
    source_paths: Sequence[Path],
    destination: Path,
) -> Path:
    """Write stable tar bytes for the selected source without local root metadata."""
    resolved_root = Path(root).resolve()
    selected = _validated_source_paths(resolved_root, source_paths)
    files = _source_files(resolved_root, selected)
    if not files:
        raise ValueError("provider source snapshot requires at least one regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as stream, tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            relative = path.relative_to(resolved_root).as_posix()
            content = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(content)
            info.mode = 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(content))
    return destination


def _validated_source_paths(root: Path, source_paths: Sequence[Path]) -> tuple[Path, ...]:
    if not source_paths:
        raise ValueError("provider source identity requires at least one source path")
    selected: list[Path] = []
    for raw_path in source_paths:
        path = Path(raw_path).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"provider source path leaves its source root: {path}")
        if path.is_symlink() or not path.exists():
            raise ValueError(f"provider source path must exist and cannot be a symlink: {path}")
        selected.append(path)
    return tuple(sorted(set(selected)))


def _source_files(root: Path, source_paths: Sequence[Path]) -> tuple[Path, ...]:
    files: set[Path] = set()
    for source in source_paths:
        candidates = (source,) if source.is_file() else source.rglob("*")
        for path in candidates:
            relative = path.relative_to(root)
            if any(part in _IGNORED_PARTS for part in relative.parts) or path.suffix == ".pyc":
                continue
            if path.is_symlink():
                raise ValueError(f"provider source snapshot cannot contain a symlink: {relative.as_posix()}")
            if path.is_file():
                files.add(path)
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def _clean_git_revision(root: Path, source_paths: Sequence[Path]) -> str | None:
    try:
        repository_root = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
        relative_paths = tuple(path.relative_to(repository_root).as_posix() for path in source_paths)
        status = _git(repository_root, "status", "--porcelain=v1", "--untracked-files=all", "--", *relative_paths)
        tracked_output = _git(repository_root, "ls-files", "-z", "--", *relative_paths)
        tracked_paths = {path for path in tracked_output.split("\0") if path}
        selected_files = {path.relative_to(repository_root).as_posix() for path in _source_files(root, source_paths)}
        revision = _git(repository_root, "rev-parse", "HEAD")
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        return None
    if (
        status
        or not selected_files.issubset(tracked_paths)
        or len(revision) != 40
        or any(character not in "0123456789abcdef" for character in revision)
    ):
        return None
    return revision


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()


__all__ = ("resolve_provider_adapter_identity", "write_deterministic_source_snapshot")
