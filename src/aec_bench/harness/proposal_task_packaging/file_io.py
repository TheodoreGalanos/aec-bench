# ABOUTME: Reads proposal task-package files through one descriptor-bound lifecycle.
# ABOUTME: Brackets inode, size, and mutation checks around the exact bytes used downstream.

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from aec_bench.harness.proposal_task_packaging.contracts import ProposalTaskPackageError


def update_digest_field(digest: hashlib._Hash, value: bytes) -> None:
    """Append one length-delimited byte field to a package digest."""

    digest.update(len(value).to_bytes(8, byteorder="big", signed=False))
    digest.update(value)


# Keep the descriptor lifecycle contiguous so inode and mutation checks bracket one open file.
def read_regular_payload(  # noqa: C901
    path: Path,
    *,
    label: str,
    max_bytes: int,
) -> bytes:
    """Read one bounded regular file without following a swapped symbolic link."""

    try:
        before = path.stat(follow_symlinks=False)
    except OSError as error:
        raise ProposalTaskPackageError(f"{label} cannot be inspected") from error
    if stat.S_ISLNK(before.st_mode):
        raise ProposalTaskPackageError(f"{label} must not be a symbolic link")
    if not stat.S_ISREG(before.st_mode):
        raise ProposalTaskPackageError(f"{label} must be a regular file")
    if before.st_size > max_bytes:
        raise ProposalTaskPackageError(f"{label} exceeds its byte limit")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ProposalTaskPackageError(f"{label} cannot be opened safely") from error
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_dev != before.st_dev or observed.st_ino != before.st_ino:
            raise ProposalTaskPackageError(f"{label} changed before it was read")
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
            raise ProposalTaskPackageError(f"{label} exceeds its byte limit")
        after = os.fstat(descriptor)
        if observed.st_mtime_ns != after.st_mtime_ns or observed.st_size != after.st_size:
            raise ProposalTaskPackageError(f"{label} changed while it was read")
        return bytes(payload)
    finally:
        os.close(descriptor)
