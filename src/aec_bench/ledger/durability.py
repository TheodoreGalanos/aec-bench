# ABOUTME: Provides lower filesystem primitives for durable directory and file publication.
# ABOUTME: Owns directory flushes, staged-tree flushes, and exact atomic byte replacement.

import os
import stat
import uuid
from pathlib import Path, PurePosixPath


class DurableFileReplaceError(RuntimeError):
    """Base error for one durable mutable-file replacement."""


class DurableFileReplaceConfinementError(DurableFileReplaceError):
    """Reject an unsafe directory, file name, or destination entry."""


class DurableFileReplaceIntegrityError(DurableFileReplaceError):
    """Reject temporary or final bytes that drift during replacement."""


def replace_file_bytes_durable(
    directory: Path,
    file_name: str,
    payload: bytes,
    *,
    host_private: bool = False,
) -> None:
    """Atomically replace one regular file with exact power-loss-durable bytes."""

    _require_durable_replace_features()
    selected_directory = Path(directory).expanduser().absolute()
    selected_name = _durable_file_name(file_name)
    content = bytes(payload)
    directory_descriptor = _open_durable_directory(selected_directory)
    temporary_name = f".{selected_name}.{uuid.uuid4().hex}.tmp"
    temporary_descriptor: int | None = None
    temporary_identity: tuple[int, int] | None = None
    active_error: BaseException | None = None
    try:
        _require_replaceable_destination(directory_descriptor, selected_name)
        temporary_descriptor = _create_durable_temporary(
            directory_descriptor,
            temporary_name,
            host_private=host_private,
        )
        temporary_identity = _regular_file_identity(
            temporary_descriptor,
            label="temporary file",
        )
        _write_durable_temporary(
            temporary_descriptor,
            content,
            host_private=host_private,
        )
        _require_entry_identity(
            directory_descriptor,
            temporary_name,
            temporary_identity,
        )
        try:
            os.replace(
                temporary_name,
                selected_name,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
            )
        except (OSError, NotImplementedError) as cause:
            raise DurableFileReplaceError(
                f"durable file cannot replace {selected_name}: {cause}",
            ) from cause
        _require_final_bytes(
            directory_descriptor,
            selected_name,
            expected_identity=temporary_identity,
            expected_bytes=content,
            host_private=host_private,
        )
        _require_durable_directory_binding(
            selected_directory,
            directory_descriptor,
        )
        try:
            os.fsync(directory_descriptor)
        except OSError as cause:
            raise DurableFileReplaceError(
                f"durable file parent cannot be flushed for {selected_name}: {cause}",
            ) from cause
    except BaseException as error:
        active_error = error
        raise
    finally:
        cleanup_errors: list[BaseException] = []
        if temporary_identity is not None:
            try:
                _unlink_owned_temporary(
                    directory_descriptor,
                    temporary_name,
                    temporary_identity,
                )
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if temporary_descriptor is not None:
            try:
                os.close(temporary_descriptor)
            except OSError as cleanup_error:
                cleanup_errors.append(
                    DurableFileReplaceError(
                        f"durable file temporary descriptor cannot be closed: {cleanup_error}",
                    )
                )
        try:
            os.close(directory_descriptor)
        except OSError as cleanup_error:
            cleanup_errors.append(
                DurableFileReplaceError(
                    f"durable file directory descriptor cannot be closed: {cleanup_error}",
                )
            )
        if cleanup_errors:
            if active_error is not None:
                for recorded_error in cleanup_errors:
                    active_error.add_note(str(recorded_error))
            else:
                failure = cleanup_errors[0]
                for recorded_error in cleanup_errors[1:]:
                    failure.add_note(str(recorded_error))
                raise failure


def _require_durable_replace_features() -> None:
    missing: list[str] = []
    if os.name != "posix":
        missing.append("POSIX operating system")
    for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"):
        if not hasattr(os, name):
            missing.append(name)
    supports_dir_fd: set[object] = set(getattr(os, "supports_dir_fd", set()))
    for function in (os.open, os.stat, os.unlink, os.rename):
        if function not in supports_dir_fd:
            missing.append(f"{function.__name__}(dir_fd)")
    supports_no_follow: set[object] = set(
        getattr(os, "supports_follow_symlinks", set()),
    )
    if os.stat not in supports_no_follow:
        missing.append("stat(follow_symlinks)")
    if not hasattr(os, "fchmod"):
        missing.append("fchmod")
    if missing:
        raise DurableFileReplaceConfinementError(
            "durable file replacement requires POSIX descriptor features: " + ", ".join(missing),
        )


def _durable_file_name(file_name: str) -> str:
    candidate = PurePosixPath(file_name)
    if (
        not file_name
        or "\x00" in file_name
        or candidate.is_absolute()
        or len(candidate.parts) != 1
        or candidate.parts[0] != file_name
        or file_name in {".", ".."}
    ):
        raise DurableFileReplaceConfinementError(
            "durable file name must be one normalized directory entry",
        )
    return file_name


def _open_durable_directory(directory: Path) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError as cause:
        raise DurableFileReplaceConfinementError(
            f"durable file directory is unsafe: {directory}: {cause}",
        ) from cause
    try:
        _require_durable_directory_binding(directory, descriptor)
        return descriptor
    except BaseException as error:
        try:
            os.close(descriptor)
        except OSError as cleanup_error:
            error.add_note(
                f"durable file directory descriptor cannot be closed after validation failure: {cleanup_error}",
            )
        raise


def _require_durable_directory_binding(directory: Path, descriptor: int) -> None:
    try:
        opened = os.fstat(descriptor)
        selected = os.stat(directory, follow_symlinks=False)
    except OSError as cause:
        raise DurableFileReplaceConfinementError(
            f"durable file directory cannot be inspected: {directory}: {cause}",
        ) from cause
    if (
        not stat.S_ISDIR(opened.st_mode)
        or stat.S_ISLNK(selected.st_mode)
        or not stat.S_ISDIR(selected.st_mode)
        or (opened.st_dev, opened.st_ino) != (selected.st_dev, selected.st_ino)
    ):
        raise DurableFileReplaceConfinementError(
            f"durable file directory identity is unsafe: {directory}",
        )


def _require_replaceable_destination(
    directory_descriptor: int,
    file_name: str,
) -> None:
    try:
        details = os.stat(
            file_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    except OSError as cause:
        raise DurableFileReplaceConfinementError(
            f"durable file destination is unsafe: {file_name}: {cause}",
        ) from cause
    if stat.S_ISLNK(details.st_mode):
        raise DurableFileReplaceConfinementError(
            f"durable file destination is a symbolic link: {file_name}",
        )
    if not stat.S_ISREG(details.st_mode):
        raise DurableFileReplaceConfinementError(
            f"durable file destination is not a regular file: {file_name}",
        )


def _create_durable_temporary(
    directory_descriptor: int,
    temporary_name: str,
    *,
    host_private: bool,
) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        return os.open(
            temporary_name,
            flags,
            0o600 if host_private else 0o666,
            dir_fd=directory_descriptor,
        )
    except OSError as cause:
        raise DurableFileReplaceError(
            f"durable file temporary cannot be created: {cause}",
        ) from cause


def _regular_file_identity(descriptor: int, *, label: str) -> tuple[int, int]:
    try:
        details = os.fstat(descriptor)
    except OSError as cause:
        raise DurableFileReplaceIntegrityError(
            f"durable file {label} cannot be inspected: {cause}",
        ) from cause
    if not stat.S_ISREG(details.st_mode):
        raise DurableFileReplaceIntegrityError(
            f"durable file {label} is not regular",
        )
    return details.st_dev, details.st_ino


def _write_durable_temporary(
    descriptor: int,
    payload: bytes,
    *,
    host_private: bool,
) -> None:
    try:
        if host_private:
            os.fchmod(descriptor, 0o600)
        remaining = memoryview(payload)
        while remaining:
            written = os.write(descriptor, remaining)
            if written == 0:
                raise DurableFileReplaceError(
                    "durable file temporary write made no progress",
                )
            remaining = remaining[written:]
        os.fsync(descriptor)
    except OSError as cause:
        raise DurableFileReplaceError(
            f"durable file temporary cannot be written: {cause}",
        ) from cause


def _require_entry_identity(
    directory_descriptor: int,
    temporary_name: str,
    expected_identity: tuple[int, int],
) -> None:
    try:
        details = os.stat(
            temporary_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except OSError as cause:
        raise DurableFileReplaceIntegrityError(
            f"durable file temporary changed before replacement: {cause}",
        ) from cause
    if (details.st_dev, details.st_ino) != expected_identity:
        raise DurableFileReplaceIntegrityError(
            "durable file temporary changed before replacement",
        )


def _require_final_bytes(
    directory_descriptor: int,
    file_name: str,
    *,
    expected_identity: tuple[int, int],
    expected_bytes: bytes,
    host_private: bool,
) -> None:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        inspected = os.stat(
            file_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except OSError as cause:
        raise DurableFileReplaceIntegrityError(
            f"durable file final entry cannot be inspected: {file_name}: {cause}",
        ) from cause
    if stat.S_ISLNK(inspected.st_mode):
        raise DurableFileReplaceConfinementError(
            f"durable file final entry is a symbolic link: {file_name}",
        )
    if not stat.S_ISREG(inspected.st_mode):
        raise DurableFileReplaceIntegrityError(
            f"durable file final entry is not regular: {file_name}",
        )
    try:
        descriptor = os.open(file_name, flags, dir_fd=directory_descriptor)
    except OSError as cause:
        raise DurableFileReplaceIntegrityError(
            f"durable file final entry cannot be opened: {file_name}: {cause}",
        ) from cause
    active_error: BaseException | None = None
    try:
        details = os.fstat(descriptor)
        observed_identity = details.st_dev, details.st_ino
        if (
            not stat.S_ISREG(details.st_mode)
            or observed_identity != expected_identity
            or observed_identity != (inspected.st_dev, inspected.st_ino)
        ):
            raise DurableFileReplaceIntegrityError(
                f"durable file final identity changed: {file_name}",
            )
        if host_private and stat.S_IMODE(details.st_mode) != 0o600:
            raise DurableFileReplaceConfinementError(
                f"durable file final permissions are not private: {file_name}",
            )
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 64 * 1024):
            chunks.append(chunk)
        if b"".join(chunks) != expected_bytes:
            raise DurableFileReplaceIntegrityError(
                f"durable file final bytes changed: {file_name}",
            )
    except OSError as cause:
        active_error = DurableFileReplaceIntegrityError(
            f"durable file final bytes cannot be read: {file_name}: {cause}",
        )
        raise active_error from cause
    except BaseException as error:
        active_error = error
        raise
    finally:
        try:
            os.close(descriptor)
        except OSError as cleanup_error:
            failure = DurableFileReplaceError(
                f"durable file final descriptor cannot be closed: {cleanup_error}",
            )
            if active_error is not None:
                active_error.add_note(str(failure))
            else:
                raise failure from cleanup_error


def _unlink_owned_temporary(
    directory_descriptor: int,
    temporary_name: str,
    expected_identity: tuple[int, int],
) -> None:
    try:
        details = os.stat(
            temporary_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    except OSError as cause:
        raise DurableFileReplaceError(
            f"durable file temporary cannot be inspected for cleanup: {cause}",
        ) from cause
    if (details.st_dev, details.st_ino) != expected_identity:
        return
    try:
        os.unlink(temporary_name, dir_fd=directory_descriptor)
    except FileNotFoundError:
        return
    except OSError as cause:
        raise DurableFileReplaceError(
            f"durable file temporary cannot be removed: {cause}",
        ) from cause


def mkdir_durable(
    path: Path,
    *,
    created_mode: int | None = None,
) -> None:
    """Create a directory tree, set new modes, and flush changed parent entries."""
    target = Path(path)
    missing: list[Path] = []
    cursor = target
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            if not directory.is_dir():
                raise
            continue
        if created_mode is not None:
            directory.chmod(created_mode)
        fsync_directory(directory.parent)
    target.mkdir(parents=True, exist_ok=True)


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
