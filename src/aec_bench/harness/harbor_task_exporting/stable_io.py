# ABOUTME: Reads Harbor control files through descriptor-bound regular-file snapshots.
# ABOUTME: Detects symlinks, inode swaps, and mutations across content-addressed checks.

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    size: int
    modified_ns: int
    changed_ns: int


@dataclass(frozen=True)
class RegularFileSnapshot:
    path: Path
    payload: bytes
    sha256: str
    identity: FileIdentity
    label: str


def read_stable_regular_file(
    path: Path,
    *,
    label: str,
    max_bytes: int,
) -> RegularFileSnapshot:
    """Read immutable-by-observation bytes through one non-following descriptor."""
    source = Path(path)
    before = _inspected_regular_file_identity(
        source,
        label=label,
        max_bytes=max_bytes,
    )
    descriptor = _open_regular_file_descriptor(source, label=label)
    try:
        observed = _validated_descriptor_identity(
            descriptor,
            expected=before,
            label=label,
            max_bytes=max_bytes,
        )
        payload = _read_bounded_descriptor(
            descriptor,
            label=label,
            max_bytes=max_bytes,
        )
        after = _file_identity(os.fstat(descriptor))
        if after != observed:
            raise ValueError(f"{label} changed while it was read")
    finally:
        os.close(descriptor)
    snapshot = RegularFileSnapshot(
        path=source,
        payload=payload,
        sha256=hashlib.sha256(payload).hexdigest(),
        identity=after,
        label=label,
    )
    _assert_path_identity(snapshot, timing="while")
    return snapshot


def assert_snapshot_current(snapshot: RegularFileSnapshot) -> None:
    """Reject a path whose current identity no longer matches validated bytes."""
    _assert_path_identity(snapshot, timing="after")


def snapshot_text(snapshot: RegularFileSnapshot) -> str:
    return snapshot.payload.decode("utf-8")


def snapshot_json_object(snapshot: RegularFileSnapshot) -> dict[str, Any]:
    payload = json.loads(snapshot_text(snapshot))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {snapshot.path}")
    return cast(dict[str, Any], payload)


def file_sha256(path: Path) -> str:
    candidate = Path(path)
    try:
        snapshot = read_stable_regular_file(
            candidate,
            label="content-addressed file",
            max_bytes=sys.maxsize,
        )
    except ValueError as exc:
        raise ValueError(f"content-addressed file is missing or unsafe: {candidate}") from exc
    return snapshot.sha256


def canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def directory_sha256(path: Path) -> str:
    root = Path(path)
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"content-addressed directory is missing or unsafe: {root}")
    manifest: dict[str, str] = {}
    for candidate in sorted(root.rglob("*")):
        if candidate.is_symlink():
            raise ValueError(f"content-addressed directory contains a symbolic link: {candidate}")
        if candidate.is_file():
            manifest[candidate.relative_to(root).as_posix()] = file_sha256(candidate)
    if not manifest:
        raise ValueError(f"content-addressed directory is empty: {root}")
    return canonical_sha256(manifest)


def _inspected_regular_file_identity(
    path: Path,
    *,
    label: str,
    max_bytes: int,
) -> FileIdentity:
    try:
        details = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ValueError(f"{label} cannot be inspected") from exc
    if stat.S_ISLNK(details.st_mode):
        raise ValueError(f"{label} must not be a symbolic link")
    if not stat.S_ISREG(details.st_mode):
        raise ValueError(f"{label} must be a regular file")
    if details.st_size > max_bytes:
        raise ValueError(f"{label} exceeds its byte limit")
    return _file_identity(details)


def _open_regular_file_descriptor(path: Path, *, label: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        return os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"{label} cannot be opened safely") from exc


def _validated_descriptor_identity(
    descriptor: int,
    *,
    expected: FileIdentity,
    label: str,
    max_bytes: int,
) -> FileIdentity:
    observed = os.fstat(descriptor)
    if not stat.S_ISREG(observed.st_mode):
        raise ValueError(f"{label} must be a regular file")
    identity = _file_identity(observed)
    if identity != expected:
        raise ValueError(f"{label} changed before it was read")
    if identity.size > max_bytes:
        raise ValueError(f"{label} exceeds its byte limit")
    return identity


def _read_bounded_descriptor(
    descriptor: int,
    *,
    label: str,
    max_bytes: int,
) -> bytes:
    payload = bytearray()
    while len(payload) <= max_bytes:
        chunk = os.read(
            descriptor,
            min(1024 * 1024, max_bytes + 1 - len(payload)),
        )
        if not chunk:
            break
        payload.extend(chunk)
    if len(payload) > max_bytes:
        raise ValueError(f"{label} exceeds its byte limit")
    return bytes(payload)


def _file_identity(details: os.stat_result) -> FileIdentity:
    return FileIdentity(
        device=details.st_dev,
        inode=details.st_ino,
        mode=details.st_mode,
        size=details.st_size,
        modified_ns=details.st_mtime_ns,
        changed_ns=details.st_ctime_ns,
    )


def _assert_path_identity(snapshot: RegularFileSnapshot, *, timing: str) -> None:
    try:
        current = snapshot.path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ValueError(f"{snapshot.label} changed {timing} it was read") from exc
    if _file_identity(current) != snapshot.identity:
        raise ValueError(f"{snapshot.label} changed {timing} it was read")
