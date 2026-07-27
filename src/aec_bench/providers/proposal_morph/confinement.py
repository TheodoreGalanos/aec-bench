# ABOUTME: Enforces local-file and remote-path confinement for Morph proposal evidence.
# ABOUTME: Provides symlink-safe bounded reads and atomic content-addressed writes.

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from aec_bench.contracts.harness_kernel import canonical_content_sha256

from .boundary import ProposalMorphBoundaryError
from .constants import (
    PROPOSAL_EXACT_ARTIFACT_LIMITS,
    PROPOSAL_SESSION_ROOT,
    REMOTE_WORKSPACE_DIR,
)


def read_regular_tree(
    root: Path,
    *,
    label: str,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
) -> tuple[dict[str, bytes], dict[str, int]]:
    """Read one symlink-free tree while enforcing count and byte limits."""

    source = Path(root)
    if source.is_symlink() or not source.is_dir():
        raise ProposalMorphBoundaryError(f"{label} must be a non-symlink directory")
    payloads: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    total = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink():
            raise ProposalMorphBoundaryError(f"{label} contains a symbolic link: {relative}")
        if path.is_dir():
            continue
        if len(payloads) >= max_files:
            raise ProposalMorphBoundaryError(f"{label} exceeds its file-count limit")
        content, mode = read_regular_file_with_mode(
            path,
            label=f"{label} member {relative}",
            max_bytes=max_file_bytes,
        )
        total += len(content)
        if total > max_total_bytes:
            raise ProposalMorphBoundaryError(f"{label} exceeds its total-byte limit")
        relative_path = relative.as_posix()
        payloads[relative_path] = content
        modes[relative_path] = mode
    return payloads, modes


def read_regular_file(path: Path, *, label: str, max_bytes: int) -> bytes:
    """Read one stable regular file without following symbolic links."""

    content, _mode = read_regular_file_with_mode(
        path,
        label=label,
        max_bytes=max_bytes,
    )
    return content


def read_regular_file_with_mode(
    path: Path,
    *,
    label: str,
    max_bytes: int,
) -> tuple[bytes, int]:
    """Read stable bytes and the exact permission mode through one descriptor."""

    source = Path(path)
    try:
        before = source.stat(follow_symlinks=False)
    except OSError as error:
        raise ProposalMorphBoundaryError(f"{label} cannot be inspected") from error
    if stat.S_ISLNK(before.st_mode):
        raise ProposalMorphBoundaryError(f"{label} must not be a symbolic link")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as error:
        raise ProposalMorphBoundaryError(f"{label} cannot be opened safely") from error
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode) or before.st_dev != observed.st_dev or before.st_ino != observed.st_ino:
            raise ProposalMorphBoundaryError(f"{label} must be a stable regular file")
        if observed.st_size > max_bytes:
            raise ProposalMorphBoundaryError(f"{label} exceeds its byte limit")
        content = bytearray()
        while len(content) <= max_bytes:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, max_bytes + 1 - len(content)),
            )
            if not chunk:
                break
            content.extend(chunk)
        if len(content) > max_bytes:
            raise ProposalMorphBoundaryError(f"{label} exceeds its byte limit")
        after = os.fstat(descriptor)
        if (
            observed.st_dev != after.st_dev
            or observed.st_ino != after.st_ino
            or observed.st_mtime_ns != after.st_mtime_ns
            or observed.st_size != after.st_size
        ):
            raise ProposalMorphBoundaryError(f"{label} changed while it was read")
        return bytes(content), stat.S_IMODE(observed.st_mode)
    finally:
        os.close(descriptor)


def validated_remote_path(raw_path: str) -> str:
    """Return one canonical absolute remote path or fail closed."""

    if not raw_path.startswith("/") or "\x00" in raw_path:
        raise ProposalMorphBoundaryError(f"proposal remote path must be absolute and canonical: {raw_path!r}")
    path = PurePosixPath(raw_path)
    canonical = path.as_posix()
    if any(part in {"", ".", ".."} for part in raw_path.split("/")[1:]) or canonical != raw_path or canonical == "/":
        raise ProposalMorphBoundaryError(f"proposal remote path must be absolute and canonical: {raw_path!r}")
    return canonical


def is_handoff_path(path: str) -> bool:
    """Return whether the remote path belongs to the sealed handoff surface."""

    return path in PROPOSAL_EXACT_ARTIFACT_LIMITS or path.startswith(f"{PROPOSAL_SESSION_ROOT}/")


def is_candidate_upload_path(path: str) -> bool:
    """Return whether a candidate may receive content at the remote path."""

    return (
        path == REMOTE_WORKSPACE_DIR
        or path.startswith(f"{REMOTE_WORKSPACE_DIR}/")
        or path == "/logs/agent"
        or path.startswith("/logs/agent/")
    )


def payloads_sha256(
    payloads: Mapping[str, bytes],
    *,
    domain: bytes,
    modes: Mapping[str, int],
) -> str:
    """Hash payload names, modes, lengths, and bytes under a domain separator."""

    digest = hashlib.sha256(domain)
    for relative, content in sorted(payloads.items()):
        relative_bytes = relative.encode("utf-8")
        digest.update(len(relative_bytes).to_bytes(8, byteorder="big"))
        digest.update(relative_bytes)
        digest.update(modes[relative].to_bytes(4, byteorder="big"))
        digest.update(len(content).to_bytes(8, byteorder="big"))
        digest.update(content)
    return digest.hexdigest()


def write_payload_tree(
    root: Path,
    payloads: Mapping[str, bytes],
    *,
    modes: Mapping[str, int] | None = None,
) -> None:
    """Write an already-confined payload map beneath one host root."""

    for relative, content in sorted(payloads.items()):
        destination = root.joinpath(*PurePosixPath(relative).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        if modes is not None:
            destination.chmod(modes[relative])


def write_receipt(path: Path, payload: dict[str, object]) -> None:
    """Persist canonical receipt content with its embedded content identity."""

    receipt = dict(payload)
    receipt["content_sha256"] = canonical_content_sha256(receipt)
    write_json_atomic(path, receipt)


def write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    """Atomically replace one deterministic JSON object and fsync its bytes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
