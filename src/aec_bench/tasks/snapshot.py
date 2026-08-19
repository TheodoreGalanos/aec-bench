# ABOUTME: Builds and validates deterministic detached runnable-task archives.
# ABOUTME: Rejects unsafe paths, links, duplicate members, and oversized decompressed payloads.

from __future__ import annotations

import io
import stat
import tarfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from types import MappingProxyType

import zstandard

TASK_SNAPSHOT_MEDIA_TYPE = "application/vnd.aec-bench.task-snapshot+tar+zstd"
_IGNORED_NAMES = frozenset({".DS_Store"})
_IGNORED_DIRECTORIES = frozenset({"__pycache__", ".pytest_cache"})
_MAX_DECOMPRESSED_BYTES = 1_073_741_824


def _portable_path(value: str) -> PurePosixPath:
    if "\\" in value:
        raise ValueError(f"task snapshot member is not a portable relative path: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"task snapshot member is not a portable relative path: {value}")
    if path.as_posix() != value:
        raise ValueError(f"task snapshot member is not a portable relative path: {value}")
    return path


def _ignored(relative: Path) -> bool:
    return relative.name in _IGNORED_NAMES or any(part in _IGNORED_DIRECTORIES for part in relative.parts)


def _tar_info(name: str, payload: bytes, *, mode: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def build_task_snapshot_archive(task_dir: Path) -> bytes:
    """Build deterministic detached bytes for one complete runnable task directory."""

    root = Path(task_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"task package does not exist: {root}")

    members: list[tuple[str, bytes, int]] = []
    for path in sorted(root.rglob("*"), key=lambda candidate: candidate.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if _ignored(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"task snapshots cannot contain symbolic links: {relative.as_posix()}")
        if not path.is_file():
            continue
        mode = 0o755 if stat.S_IMODE(path.stat(follow_symlinks=False).st_mode) & 0o111 else 0o644
        members.append((relative.as_posix(), path.read_bytes(), mode))
    if not members:
        raise ValueError("task snapshot must contain at least one file")

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, payload, mode in members:
            archive.addfile(_tar_info(name, payload, mode=mode), io.BytesIO(payload))
    return zstandard.ZstdCompressor(level=10, write_checksum=True, write_content_size=True).compress(
        tar_buffer.getvalue()
    )


def read_task_snapshot_archive(data: bytes) -> Mapping[str, bytes]:
    """Validate untrusted detached task bytes without extracting them."""

    if not data:
        raise ValueError("task snapshot archive must not be empty")
    try:
        tar_bytes = zstandard.ZstdDecompressor().decompress(data, max_output_size=_MAX_DECOMPRESSED_BYTES)
    except zstandard.ZstdError as error:
        raise ValueError(f"invalid task snapshot compression: {error}") from error

    members: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
            for member in archive.getmembers():
                name = _portable_path(member.name).as_posix()
                if name in members:
                    raise ValueError(f"duplicate task snapshot path: {name}")
                if not member.isfile():
                    raise ValueError(f"task snapshots may contain regular files only: {name}")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError(f"cannot read task snapshot member: {name}")
                payload = extracted.read()
                if len(payload) != member.size:
                    raise ValueError(f"task snapshot member size mismatch: {name}")
                members[name] = payload
    except tarfile.TarError as error:
        raise ValueError(f"invalid task snapshot archive: {error}") from error
    if not members:
        raise ValueError("task snapshot archive must contain at least one file")
    return MappingProxyType(members)


__all__ = (
    "TASK_SNAPSHOT_MEDIA_TYPE",
    "build_task_snapshot_archive",
    "read_task_snapshot_archive",
)
