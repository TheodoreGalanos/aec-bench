# ABOUTME: Provides owner-only filesystem and hashing primitives for sealed lifecycle snapshots.
# ABOUTME: Keeps write-once path safety separate from holdout authority and TrialRecord semantics.

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar, cast

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.validators import StrictModel
from aec_bench.ledger.durability import fsync_directory, mkdir_durable

_ModelT = TypeVar("_ModelT", bound=StrictModel)


def copy_tree_exact(source: Path, destination: Path) -> None:
    validate_tree_source(source, label="snapshot source")
    destination.mkdir(parents=True)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            copy_regular_file(path, target)


def copy_regular_file(source: Path, destination: Path) -> None:
    require_regular_file(source, label="snapshot source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o600)


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_private_record(path: Path, record: TrialRecord, ledger_root: Path) -> None:
    content = (json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode("utf-8")
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
            raise ValueError("sealed holdout TrialRecord already exists with different content")
        return
    mkdir_durable(path.parent)
    set_owner_only_directory(path.parent, ledger_root)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def exclusive_finalization_lock(root: Path, experiment_id: str, trial_id: str) -> Iterator[None]:
    lock_path = root / f".{experiment_id}.{trial_id}.lock"
    validate_owner_only_tree(root)
    if lock_path.is_symlink():
        raise ValueError("private holdout finalization lock must not be a symlink")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise ValueError("private holdout finalization lock could not be opened safely") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (hasattr(os, "getuid") and opened.st_uid != os.getuid())
        ):
            raise ValueError("private holdout finalization lock is not an owned regular file")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def validate_private_root_destination(root: Path) -> None:
    if not root.is_absolute():
        raise ValueError("private holdout ledger root must be absolute")
    if root.is_symlink():
        raise ValueError("private holdout ledger root must not be a symlink")
    if root.exists():
        validate_private_root(root)
    elif root.resolve(strict=False) != root:
        raise ValueError("private holdout ledger root must be canonical")


def prepare_private_root(root: Path) -> None:
    if not root.exists():
        root.mkdir(mode=0o700, parents=True)
        os.chmod(root, 0o700)
        fsync_directory(root.parent)
    validate_private_root(root)


def validate_private_root(root: Path) -> None:
    if root.is_symlink() or not root.is_dir() or root.resolve() != root:
        raise ValueError("private holdout ledger root must be a canonical directory")
    if stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise ValueError("private holdout ledger root must be owner-only")


def validate_nonoverlap(root: Path, sources: tuple[Path, ...]) -> None:
    root_path = root.resolve(strict=False)
    for source in sources:
        source_path = source.resolve(strict=False)
        if root_path == source_path or root_path in source_path.parents or source_path in root_path.parents:
            raise ValueError("private holdout ledger root must not overlap source evidence")


def validate_tree_source(root: Path, *, label: str) -> None:
    if root.is_symlink() or not root.is_dir() or root.resolve() != root:
        raise ValueError(f"{label} must be a canonical directory")
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"{label} must not contain symlinks")
        if not stat.S_ISDIR(mode) and not stat.S_ISREG(mode):
            raise ValueError(f"{label} contains a non-regular filesystem entry")


def require_regular_file(path: Path, *, label: str) -> None:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"{label} must be a regular file and not a symlink")


def set_owner_only_directory(path: Path, ledger_root: Path) -> None:
    current = path
    root = ledger_root.resolve()
    while current.exists():
        try:
            current.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("private holdout path escapes the ledger root") from exc
        if current.is_symlink():
            raise ValueError("private holdout path must not contain symlinks")
        if current.is_dir():
            os.chmod(current, 0o700)
        if current.resolve() == root:
            break
        current = current.parent


def set_owner_only_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink():
            raise ValueError("private holdout snapshot must not contain symlinks")
        os.chmod(path, 0o700 if path.is_dir() else 0o600)
    os.chmod(root, 0o700)


def validate_owner_only_tree(root: Path) -> None:
    for path in (root, *root.rglob("*")):
        if path.is_symlink():
            raise ValueError("private holdout ledger contains a symlink")
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError("private holdout ledger must remain owner-only")


def tree_hashes(root: Path) -> dict[str, str]:
    validate_tree_source(root, label="snapshot tree")
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(root.rglob("*")) if path.is_file()}


def tree_structure_sha256(root: Path) -> str:
    validate_tree_source(root, label="snapshot tree")
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        kind = b"directory" if path.is_dir() else b"file"
        digest.update(len(kind).to_bytes(8, "big"))
        digest.update(kind)
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        if path.is_file():
            content_hash = bytes.fromhex(sha256(path))
            digest.update(len(content_hash).to_bytes(8, "big"))
            digest.update(content_hash)
    return digest.hexdigest()


def first_ledger_timestamp(path: Path) -> str:
    timestamps = ledger_timestamps(path)
    if not timestamps:
        raise ValueError("sealed lifecycle ledger has no timestamped events")
    return min(timestamps).isoformat()


def ledger_duration_seconds(path: Path) -> float:
    timestamps = ledger_timestamps(path)
    if not timestamps:
        return 0.0
    return max(0.0, (max(timestamps) - min(timestamps)).total_seconds())


def ledger_timestamps(path: Path) -> list[datetime]:
    require_regular_file(path, label="lifecycle ledger")
    timestamps: list[datetime] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict) or not isinstance(payload.get("created_at"), str):
            raise ValueError(f"lifecycle ledger timestamp is malformed at line {line_number}")
        timestamps.append(datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00")))
    return timestamps


def read_model(path: Path, model_type: type[_ModelT]) -> _ModelT:
    require_regular_file(path, label="write-once authority")
    return model_type.model_validate_json(path.read_bytes())


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def validate_relative_path(raw_path: str) -> None:
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != raw_path:
        raise ValueError("holdout artifact path must be safe and relative")


def media_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }.get(path.suffix.lower(), "application/octet-stream")


def canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
