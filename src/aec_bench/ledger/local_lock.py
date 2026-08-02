# ABOUTME: Provides a confined local POSIX file lock for durable filesystem operations.
# ABOUTME: Anchors lock paths below one trusted root and preserves protected-operation errors.

from __future__ import annotations

import fcntl
import os
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import NoReturn

from aec_bench.ledger.durability import mkdir_durable


class LocalFileLockError(RuntimeError):
    """Raised when a local file lock cannot be prepared, acquired, or released."""


class LocalFileLockConfinementError(LocalFileLockError):
    """Raised when a relative lock path selects an unsafe filesystem object."""


type LocalFileLockErrorFactory = Callable[[LocalFileLockError], BaseException]


@contextmanager
def exclusive_local_file_lock(
    root: Path,
    relative_path: str,
    *,
    error_factory: LocalFileLockErrorFactory | None = None,
) -> Iterator[None]:
    """Hold one exclusive POSIX lock at a confined path below a trusted root."""
    directory_descriptors: list[int] = []
    lock_descriptor: int | None = None
    try:
        try:
            directory_descriptors, lock_descriptor = _open_confined_lock(
                Path(root).absolute(),
                relative_path,
            )
            fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        except LocalFileLockError as lock_error:
            _close_after_setup_failure(lock_descriptor, directory_descriptors, lock_error)
            _raise_lock_error(lock_error, error_factory)
        except OSError as lock_cause:
            acquisition_error = LocalFileLockError(f"local lock cannot be acquired: {lock_cause}")
            _close_after_setup_failure(lock_descriptor, directory_descriptors, acquisition_error)
            _raise_lock_error(acquisition_error, error_factory, lock_cause)
        except BaseException as interruption:
            _close_after_setup_failure(lock_descriptor, directory_descriptors, interruption)
            raise

        body_error: BaseException | None = None
        try:
            yield
        except BaseException as protected_error:
            body_error = protected_error
            raise
        finally:
            cleanup = _release_and_close(lock_descriptor, directory_descriptors)
            if cleanup is not None:
                cleanup_error, cleanup_cause = cleanup
                if body_error is not None:
                    body_error.add_note(f"Local file lock cleanup also failed: {cleanup_error}")
                else:
                    _raise_lock_error(cleanup_error, error_factory, cleanup_cause)
    finally:
        directory_descriptors.clear()


def _open_confined_lock(root: Path, relative_path: str) -> tuple[list[int], int]:
    parts = _relative_lock_parts(relative_path)
    if root.name in {"", ".", ".."}:
        raise LocalFileLockConfinementError("local lock root must select one directory")
    try:
        mkdir_durable(root)
    except OSError as cause:
        raise LocalFileLockError(f"local lock root cannot be created: {cause}") from cause

    descriptors: list[int] = []
    try:
        root_descriptor = _open_directory(root, "local lock root")
        descriptors.append(root_descriptor)
        for part in parts[:-1]:
            descriptors.append(_open_or_create_child_directory(descriptors[-1], part))
        lock_descriptor = _open_private_regular_file(descriptors[-1], parts[-1])
    except BaseException as error:
        _close_after_setup_failure(None, descriptors, error)
        raise
    return descriptors, lock_descriptor


def _relative_lock_parts(relative_path: str) -> tuple[str, ...]:
    selected = PurePosixPath(relative_path)
    raw_parts = relative_path.split("/")
    if (
        not relative_path
        or selected.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
        or "\x00" in relative_path
    ):
        raise LocalFileLockConfinementError(
            "local lock path must be a normalized confined relative file path",
        )
    return tuple(raw_parts)


def _open_directory(path: Path, label: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(path, flags)
    except OSError as cause:
        raise LocalFileLockConfinementError(f"{label} is unsafe: {cause}") from cause


def _open_or_create_child_directory(parent_descriptor: int, name: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(name, flags, dir_fd=parent_descriptor)
    except FileNotFoundError:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
            os.fsync(parent_descriptor)
        except FileExistsError:
            pass
        except OSError as cause:
            raise LocalFileLockError(
                f"local lock parent directory cannot be created: {cause}",
            ) from cause
        try:
            return os.open(name, flags, dir_fd=parent_descriptor)
        except OSError as cause:
            raise LocalFileLockConfinementError(
                f"local lock parent directory is unsafe: {cause}",
            ) from cause
    except OSError as cause:
        raise LocalFileLockConfinementError(
            f"local lock parent directory is unsafe: {cause}",
        ) from cause


def _open_private_regular_file(parent_descriptor: int, name: str) -> int:
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, 0o600, dir_fd=parent_descriptor)
    except OSError as cause:
        raise LocalFileLockConfinementError(f"local lock file is unsafe: {cause}") from cause
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise LocalFileLockConfinementError("local lock target is not a regular file")
        if stat.S_IMODE(details.st_mode) & 0o077:
            raise LocalFileLockConfinementError("local lock file must be host-private")
    except BaseException as error:
        _close_after_setup_failure(descriptor, [], error)
        raise
    return descriptor


def _close_after_setup_failure(
    lock_descriptor: int | None,
    directory_descriptors: list[int],
    active_error: BaseException,
) -> None:
    close_errors = _close_descriptors(lock_descriptor, directory_descriptors)
    if close_errors:
        active_error.add_note(_cleanup_note(close_errors))


def _release_and_close(
    lock_descriptor: int | None,
    directory_descriptors: list[int],
) -> tuple[LocalFileLockError, BaseException] | None:
    errors: list[tuple[str, BaseException]] = []
    if lock_descriptor is not None:
        try:
            fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        except BaseException as cause:
            errors.append(("release", cause))
    errors.extend(_close_descriptors(lock_descriptor, directory_descriptors))
    if not errors:
        return None
    error = LocalFileLockError(_cleanup_note(errors))
    return error, errors[0][1]


def _close_descriptors(
    lock_descriptor: int | None,
    directory_descriptors: list[int],
) -> list[tuple[str, BaseException]]:
    errors: list[tuple[str, BaseException]] = []
    descriptors = ([lock_descriptor] if lock_descriptor is not None else []) + list(
        reversed(directory_descriptors),
    )
    directory_descriptors.clear()
    for descriptor in descriptors:
        try:
            os.close(descriptor)
        except BaseException as cause:
            errors.append(("close", cause))
    return errors


def _cleanup_note(errors: list[tuple[str, BaseException]]) -> str:
    details = "; ".join(f"{operation} failed: {cause}" for operation, cause in errors)
    return f"local lock cleanup failed: {details}"


def _raise_lock_error(
    error: LocalFileLockError,
    error_factory: LocalFileLockErrorFactory | None,
    cause: BaseException | None = None,
) -> NoReturn:
    translated = error if error_factory is None else error_factory(error)
    if translated is error:
        raise error
    raise translated from (cause or error)
