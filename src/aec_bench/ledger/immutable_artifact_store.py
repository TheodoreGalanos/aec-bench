# ABOUTME: Publishes and reloads exact immutable bytes below one trusted filesystem root.
# ABOUTME: Uses descriptor-confined paths, atomic first-writer links, and durable private files.

from __future__ import annotations

import errno
import hashlib
import os
import stat
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_NATIVE_DIR_FD_FUNCTIONS = (os.open, os.stat, os.mkdir, os.unlink, os.link)
_NATIVE_NO_FOLLOW_FUNCTIONS = (os.stat, os.link)


class ImmutableArtifactStoreError(RuntimeError):
    """Base error for confined immutable byte storage."""


class ImmutableArtifactConfinementError(ImmutableArtifactStoreError):
    """Reject an unsafe root, relative path, filesystem object, or file mode."""


class ImmutableArtifactCollisionError(ImmutableArtifactStoreError):
    """Reject reuse of one logical path with different immutable bytes."""


class ImmutableArtifactIntegrityError(ImmutableArtifactStoreError):
    """Reject missing, non-regular, unreadable, or digest-mismatched content."""


class _ImmutableArtifactMissingError(ImmutableArtifactIntegrityError):
    """Identify a missing path for the public exists operation."""


@dataclass(frozen=True, slots=True)
class ImmutableArtifact:
    """Exact physical reference returned after durable publication."""

    path: Path
    sha256: str
    size_bytes: int


class ImmutableByteStore:
    """Confined first-writer store for exact task-neutral bytes."""

    def __init__(
        self,
        root: Path,
        *,
        disjoint_roots: Iterable[Path] = (),
        host_private: bool = False,
    ) -> None:
        _require_posix_descriptor_features()
        protected_roots = _canonical_disjoint_roots(disjoint_roots)
        selected, prospective = _select_prospective_root(Path(root))
        _require_disjoint_roots(prospective, protected_roots)
        self._host_private = host_private
        self._root, self._root_identity = _prepare_trusted_root(
            selected,
            host_private=host_private,
            protected_roots=protected_roots,
        )
        _require_disjoint_roots(self._root, protected_roots)
        self._assert_root_binding()

    @property
    def root(self) -> Path:
        """Return the canonical physical storage root."""

        self._assert_root_binding()
        return self._root

    def publish_bytes(
        self,
        relative_path: str,
        payload: bytes,
    ) -> ImmutableArtifact:
        """Publish exact bytes once, replaying equality and rejecting collisions."""

        parts = _relative_parts(relative_path)
        content = bytes(payload)
        with self._open_parent(parts, create=True) as parent_descriptor:
            observed = self._load_optional_at(
                parent_descriptor,
                parts[-1],
                relative_path,
            )
            if observed is not None:
                if observed != content:
                    raise ImmutableArtifactCollisionError(
                        f"immutable artifact collision at {relative_path}",
                    )
                self._flush_parent(parent_descriptor, relative_path)
                return self._artifact(parts, observed)

            temporary_name = f".{parts[-1]}.{uuid.uuid4().hex}.tmp"
            temporary_created = False
            temporary_descriptor: int | None = None
            temporary_identity: tuple[int, int] | None = None
            publication_error: BaseException | None = None
            try:
                temporary_descriptor = self._create_temporary(
                    parent_descriptor,
                    temporary_name,
                )
                temporary_created = True
                temporary_identity = self._temporary_identity(
                    temporary_descriptor,
                )
                self._write_temporary(
                    temporary_descriptor,
                    content,
                )
                self._require_entry_identity(
                    parent_descriptor,
                    temporary_name,
                    temporary_identity,
                )
                try:
                    os.link(
                        temporary_name,
                        parts[-1],
                        src_dir_fd=parent_descriptor,
                        dst_dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    observed = self._load_at(
                        parent_descriptor,
                        parts[-1],
                        relative_path,
                    )
                    if observed != content:
                        raise ImmutableArtifactCollisionError(
                            f"immutable artifact collision at {relative_path}",
                        ) from None
                except OSError as cause:
                    raise ImmutableArtifactStoreError(
                        f"immutable artifact cannot be linked at {relative_path}: {cause}",
                    ) from cause
                else:
                    linked_identity = self._entry_identity(
                        parent_descriptor,
                        parts[-1],
                        label="published artifact",
                    )
                    try:
                        observed, linked_details = self._load_with_metadata_at(
                            parent_descriptor,
                            parts[-1],
                            relative_path,
                        )
                        opened_identity = linked_details.st_dev, linked_details.st_ino
                        if (
                            linked_identity != temporary_identity
                            or opened_identity != linked_identity
                            or observed != content
                        ):
                            raise ImmutableArtifactIntegrityError(
                                f"immutable artifact drifted during publication at {relative_path}",
                            )
                    except BaseException as validation_error:
                        try:
                            removed = self._unlink_if_identity(
                                parent_descriptor,
                                parts[-1],
                                linked_identity,
                                label="published artifact",
                            )
                            if removed:
                                self._flush_parent(parent_descriptor, relative_path)
                        except BaseException as rollback_error:
                            validation_error.add_note(
                                f"immutable artifact publication rollback failed: {rollback_error}",
                            )
                        raise
                self._flush_parent(parent_descriptor, relative_path)
            except BaseException as error:
                publication_error = error
                raise
            finally:
                cleanup_errors: list[BaseException] = []
                if temporary_created and temporary_identity is not None:
                    try:
                        self._unlink_if_identity(
                            parent_descriptor,
                            temporary_name,
                            temporary_identity,
                            label="temporary file",
                        )
                    except BaseException as unlink_error:
                        cleanup_errors.append(unlink_error)
                if temporary_descriptor is not None:
                    try:
                        self._close_temporary_descriptor(temporary_descriptor)
                    except BaseException as close_error:
                        cleanup_errors.append(close_error)
                if cleanup_errors:
                    if publication_error is not None:
                        for recorded_error in cleanup_errors:
                            publication_error.add_note(str(recorded_error))
                    else:
                        failure = cleanup_errors[0]
                        for recorded_error in cleanup_errors[1:]:
                            failure.add_note(str(recorded_error))
                        raise failure

            observed = self._load_at(
                parent_descriptor,
                parts[-1],
                relative_path,
            )
            if observed != content:
                raise ImmutableArtifactIntegrityError(
                    f"immutable artifact drifted during publication at {relative_path}",
                )
            return self._artifact(parts, observed)

    def load_bytes(
        self,
        relative_path: str,
        *,
        expected_sha256: str | None = None,
    ) -> bytes:
        """Load exact regular-file bytes from one descriptor-confined path."""

        parts = _relative_parts(relative_path)
        with self._open_parent(parts, create=False) as parent_descriptor:
            payload = self._load_at(parent_descriptor, parts[-1], relative_path)
        if expected_sha256 is not None:
            expected = _validate_sha256(expected_sha256)
            observed = hashlib.sha256(payload).hexdigest()
            if observed != expected:
                raise ImmutableArtifactIntegrityError(
                    f"immutable artifact digest mismatch at {relative_path}",
                )
        self._assert_root_binding()
        return payload

    def exists(self, relative_path: str) -> bool:
        """Return whether one confined logical path has a safe filesystem entry."""

        parts = _relative_parts(relative_path)
        try:
            with self._open_parent(parts, create=False) as parent_descriptor:
                self._metadata_at(parent_descriptor, parts[-1], relative_path)
                return True
        except _ImmutableArtifactMissingError:
            self._assert_root_binding()
            return False

    def reference(self, relative_path: str) -> ImmutableArtifact:
        """Return a digest and size for one exact persisted artifact."""

        parts = _relative_parts(relative_path)
        payload = self.load_bytes(relative_path)
        return self._artifact(parts, payload)

    def prepare_directory_destination(
        self,
        parent_relative_path: str,
        directory_name: str,
    ) -> Path:
        """Prepare a confined parent and require its optional directory leaf to be safe."""
        parent_parts = _relative_parts(parent_relative_path)
        leaf_parts = _relative_parts(directory_name)
        if len(leaf_parts) != 1:
            raise ImmutableArtifactConfinementError(
                "immutable directory destination leaf must be one name",
            )
        with self._open_parent((*parent_parts, ".directory-destination"), create=True) as parent_descriptor:
            leaf_descriptor: int | None = None
            try:
                leaf_descriptor = self._open_child_directory(
                    parent_descriptor,
                    leaf_parts[0],
                    create=False,
                )
            except _ImmutableArtifactMissingError:
                pass
            finally:
                if leaf_descriptor is not None:
                    try:
                        os.close(leaf_descriptor)
                    except OSError as cause:
                        raise ImmutableArtifactStoreError(
                            f"immutable directory destination cannot be closed: {cause}",
                        ) from cause
        self._assert_root_binding()
        return self._root.joinpath(*parent_parts, leaf_parts[0])

    def _path(self, relative_path: str) -> Path:
        """Return one validated logical path for compatibility-layer policies."""

        parts = _relative_parts(relative_path)
        self._assert_root_binding()
        path = self._root.joinpath(*parts)
        _reject_relative_symlinks(self._root, parts)
        self._assert_root_binding()
        return path

    @contextmanager
    def _open_parent(
        self,
        parts: tuple[str, ...],
        *,
        create: bool,
    ) -> Iterator[int]:
        descriptors: list[int] = []
        active_error: BaseException | None = None
        try:
            root_descriptor = _open_root_directory(self._root)
            descriptors.append(root_descriptor)
            self._validate_root_descriptor(root_descriptor)
            for part in parts[:-1]:
                descriptors.append(
                    self._open_child_directory(
                        descriptors[-1],
                        part,
                        create=create,
                    )
                )
            yield descriptors[-1]
            self._assert_root_binding()
        except BaseException as error:
            active_error = error
            raise
        finally:
            cleanup_errors: list[BaseException] = []
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except BaseException as cleanup_error:
                    cleanup_errors.append(cleanup_error)
            if cleanup_errors:
                detail = "; ".join(str(error) for error in cleanup_errors)
                failure = ImmutableArtifactStoreError(
                    f"immutable artifact directory cleanup failed: {detail}",
                )
                if active_error is not None:
                    active_error.add_note(str(failure))
                else:
                    raise failure from cleanup_errors[0]

    def _open_child_directory(
        self,
        parent_descriptor: int,
        name: str,
        *,
        create: bool,
    ) -> int:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            inspected = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            inspected = None
        except OSError as cause:
            raise ImmutableArtifactConfinementError(
                f"immutable artifact parent is unsafe: {cause}",
            ) from cause
        if inspected is not None and stat.S_ISLNK(inspected.st_mode):
            raise ImmutableArtifactConfinementError(
                f"immutable artifact parent contains a symbolic-link component: {name}",
            )
        created = False
        try:
            descriptor = os.open(name, flags, dir_fd=parent_descriptor)
        except FileNotFoundError as cause:
            if not create:
                raise _ImmutableArtifactMissingError(
                    "immutable artifact parent is missing",
                ) from cause
            try:
                os.mkdir(
                    name,
                    mode=0o700 if self._host_private else 0o777,
                    dir_fd=parent_descriptor,
                )
                created = True
            except FileExistsError:
                pass
            except OSError as create_cause:
                raise ImmutableArtifactStoreError(
                    f"immutable artifact parent cannot be created: {create_cause}",
                ) from create_cause
            try:
                descriptor = os.open(name, flags, dir_fd=parent_descriptor)
            except OSError as open_cause:
                raise ImmutableArtifactConfinementError(
                    f"immutable artifact parent is unsafe: {open_cause}",
                ) from open_cause
        except OSError as cause:
            raise ImmutableArtifactConfinementError(
                f"immutable artifact parent is unsafe: {cause}",
            ) from cause
        active_error: BaseException | None = None
        try:
            details = os.fstat(descriptor)
            if self._host_private and stat.S_IMODE(details.st_mode) & 0o077:
                raise ImmutableArtifactConfinementError(
                    f"immutable artifact parent permissions are not host-private: {name}",
                )
            if created:
                if self._host_private:
                    os.fchmod(descriptor, 0o700)
                os.fsync(descriptor)
            if create:
                os.fsync(parent_descriptor)
            return descriptor
        except OSError as cause:
            active_error = ImmutableArtifactStoreError(
                f"immutable artifact parent cannot be made durable: {cause}",
            )
            raise active_error from cause
        except BaseException as error:
            active_error = error
            raise
        finally:
            if active_error is not None:
                try:
                    os.close(descriptor)
                except BaseException as cleanup_error:
                    active_error.add_note(
                        f"immutable artifact parent cannot be closed after failure: {cleanup_error}",
                    )

    def _create_temporary(
        self,
        parent_descriptor: int,
        name: str,
    ) -> int:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
        flags |= os.O_NOFOLLOW
        try:
            return os.open(name, flags, 0o600, dir_fd=parent_descriptor)
        except OSError as cause:
            raise ImmutableArtifactStoreError(
                f"immutable artifact temporary file cannot be created: {cause}",
            ) from cause

    def _write_temporary(
        self,
        descriptor: int,
        payload: bytes,
    ) -> None:
        try:
            os.fchmod(descriptor, 0o600)
            remaining = memoryview(payload)
            while remaining:
                written = os.write(descriptor, remaining)
                if written == 0:
                    raise ImmutableArtifactStoreError(
                        "immutable artifact temporary write made no progress",
                    )
                remaining = remaining[written:]
            os.fsync(descriptor)
        except OSError as cause:
            raise ImmutableArtifactStoreError(
                f"immutable artifact temporary file cannot be written: {cause}",
            ) from cause

    def _temporary_identity(self, descriptor: int) -> tuple[int, int]:
        try:
            details = os.fstat(descriptor)
        except OSError as cause:
            raise ImmutableArtifactStoreError(
                f"immutable artifact temporary file cannot be inspected: {cause}",
            ) from cause
        if not stat.S_ISREG(details.st_mode):
            raise ImmutableArtifactIntegrityError(
                "immutable artifact temporary file is not a regular file",
            )
        return details.st_dev, details.st_ino

    def _require_entry_identity(
        self,
        parent_descriptor: int,
        name: str,
        expected_identity: tuple[int, int],
    ) -> None:
        observed_identity = self._entry_identity(
            parent_descriptor,
            name,
            label="temporary file",
        )
        if observed_identity != expected_identity:
            raise ImmutableArtifactIntegrityError(
                "immutable artifact temporary file changed before publication",
            )

    @staticmethod
    def _entry_identity(
        parent_descriptor: int,
        name: str,
        *,
        label: str,
    ) -> tuple[int, int]:
        try:
            details = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError as cause:
            raise ImmutableArtifactIntegrityError(
                f"immutable artifact {label} is missing",
            ) from cause
        except OSError as cause:
            raise ImmutableArtifactIntegrityError(
                f"immutable artifact {label} cannot be inspected: {cause}",
            ) from cause
        return details.st_dev, details.st_ino

    def _unlink_if_identity(
        self,
        parent_descriptor: int,
        name: str,
        expected_identity: tuple[int, int],
        *,
        label: str,
    ) -> bool:
        try:
            details = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return False
        except OSError as cause:
            raise ImmutableArtifactStoreError(
                f"immutable artifact {label} cannot be inspected for removal: {cause}",
            ) from cause
        if (details.st_dev, details.st_ino) != expected_identity:
            return False
        try:
            os.unlink(name, dir_fd=parent_descriptor)
        except FileNotFoundError:
            return False
        except OSError as cause:
            raise ImmutableArtifactStoreError(
                f"immutable artifact {label} cannot be removed: {cause}",
            ) from cause
        return True

    @staticmethod
    def _close_temporary_descriptor(descriptor: int) -> None:
        try:
            os.close(descriptor)
        except BaseException as cleanup_error:
            raise ImmutableArtifactStoreError(
                f"immutable artifact temporary file cannot be closed: {cleanup_error}",
            ) from cleanup_error

    def _flush_parent(self, descriptor: int, relative_path: str) -> None:
        try:
            os.fsync(descriptor)
        except OSError as cause:
            raise ImmutableArtifactStoreError(
                f"immutable artifact parent cannot be flushed at {relative_path}: {cause}",
            ) from cause

    def _load_optional_at(
        self,
        parent_descriptor: int,
        name: str,
        relative_path: str,
    ) -> bytes | None:
        try:
            return self._load_at(parent_descriptor, name, relative_path)
        except _ImmutableArtifactMissingError:
            return None

    def _metadata_at(
        self,
        parent_descriptor: int,
        name: str,
        relative_path: str,
    ) -> os.stat_result:
        descriptor = self._open_artifact(
            parent_descriptor,
            name,
            relative_path,
        )
        active_error: BaseException | None = None
        try:
            return self._validate_artifact_descriptor(descriptor, relative_path)
        except BaseException as error:
            active_error = error
            raise
        finally:
            self._close_artifact_descriptor(descriptor, active_error=active_error)

    def _load_at(
        self,
        parent_descriptor: int,
        name: str,
        relative_path: str,
    ) -> bytes:
        payload, _ = self._load_with_metadata_at(
            parent_descriptor,
            name,
            relative_path,
        )
        return payload

    def _load_with_metadata_at(
        self,
        parent_descriptor: int,
        name: str,
        relative_path: str,
    ) -> tuple[bytes, os.stat_result]:
        descriptor = self._open_artifact(
            parent_descriptor,
            name,
            relative_path,
        )
        active_error: BaseException | None = None
        try:
            details = self._validate_artifact_descriptor(descriptor, relative_path)
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 64 * 1024):
                chunks.append(chunk)
            return b"".join(chunks), details
        except OSError as cause:
            active_error = ImmutableArtifactIntegrityError(
                f"immutable artifact cannot be read at {relative_path}: {cause}",
            )
            raise active_error from cause
        except BaseException as error:
            active_error = error
            raise
        finally:
            self._close_artifact_descriptor(descriptor, active_error=active_error)

    def _open_artifact(
        self,
        parent_descriptor: int,
        name: str,
        relative_path: str,
    ) -> int:
        try:
            inspected = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError as cause:
            raise _ImmutableArtifactMissingError(
                f"immutable artifact is missing: {relative_path}",
            ) from cause
        except OSError as cause:
            raise ImmutableArtifactIntegrityError(
                f"immutable artifact cannot be inspected at {relative_path}: {cause}",
            ) from cause
        if stat.S_ISLNK(inspected.st_mode):
            raise ImmutableArtifactConfinementError(
                f"immutable artifact path contains a symbolic-link component: {relative_path}",
            )

        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        flags |= getattr(os, "O_CLOEXEC", 0)
        try:
            return os.open(name, flags, dir_fd=parent_descriptor)
        except FileNotFoundError as cause:
            raise _ImmutableArtifactMissingError(
                f"immutable artifact is missing: {relative_path}",
            ) from cause
        except OSError as cause:
            if cause.errno in {errno.ELOOP, errno.EMLINK}:
                raise ImmutableArtifactConfinementError(
                    f"immutable artifact path became a symbolic link at {relative_path}: {cause}",
                ) from cause
            raise ImmutableArtifactIntegrityError(
                f"immutable artifact cannot be opened at {relative_path}: {cause}",
            ) from cause

    def _validate_artifact_descriptor(
        self,
        descriptor: int,
        relative_path: str,
    ) -> os.stat_result:
        try:
            details = os.fstat(descriptor)
        except OSError as cause:
            raise ImmutableArtifactIntegrityError(
                f"immutable artifact metadata cannot be read at {relative_path}: {cause}",
            ) from cause
        if not stat.S_ISREG(details.st_mode):
            raise ImmutableArtifactIntegrityError(
                f"immutable artifact is not a regular file: {relative_path}",
            )
        if self._host_private and stat.S_IMODE(details.st_mode) & 0o077:
            raise ImmutableArtifactConfinementError(
                f"immutable artifact permissions are not host-private: {relative_path}",
            )
        return details

    @staticmethod
    def _close_artifact_descriptor(
        descriptor: int,
        *,
        active_error: BaseException | None,
    ) -> None:
        try:
            os.close(descriptor)
        except BaseException as cleanup_error:
            failure = ImmutableArtifactStoreError(
                f"immutable artifact file cannot be closed: {cleanup_error}",
            )
            if active_error is not None:
                active_error.add_note(str(failure))
            else:
                raise failure from cleanup_error

    def _artifact(
        self,
        parts: tuple[str, ...],
        payload: bytes,
    ) -> ImmutableArtifact:
        self._assert_root_binding()
        return ImmutableArtifact(
            path=self._root.joinpath(*parts),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )

    def _validate_root_descriptor(self, descriptor: int) -> None:
        details = _root_details(descriptor)
        if (details.st_dev, details.st_ino) != self._root_identity:
            raise ImmutableArtifactConfinementError(
                "immutable artifact root identity changed after store creation",
            )
        if self._host_private and stat.S_IMODE(details.st_mode) & 0o077:
            raise ImmutableArtifactConfinementError(
                "host-private immutable artifact root permissions are not private",
            )

    def _assert_root_binding(self) -> None:
        descriptor = _open_root_directory(self._root)
        active_error: BaseException | None = None
        try:
            self._validate_root_descriptor(descriptor)
        except BaseException as error:
            active_error = error
            raise
        finally:
            try:
                os.close(descriptor)
            except BaseException as cleanup_error:
                failure = ImmutableArtifactStoreError(
                    f"immutable artifact root cannot be closed: {cleanup_error}",
                )
                if active_error is not None:
                    active_error.add_note(str(failure))
                else:
                    raise failure from cleanup_error


def validate_immutable_artifact_root(
    root: Path,
    *,
    disjoint_roots: Iterable[Path] = (),
    must_exist: bool = False,
) -> Path:
    """Resolve one canonical non-symlink root disjoint from protected roots."""

    selected = Path(root).expanduser()
    if not selected.is_absolute():
        raise ImmutableArtifactConfinementError(
            "immutable artifact root must be absolute",
        )
    absolute = selected.absolute()
    _reject_absolute_symlinks(absolute, label="immutable artifact root")
    resolved = absolute.resolve(strict=must_exist)
    if resolved != absolute:
        raise ImmutableArtifactConfinementError(
            "immutable artifact root contains a symbolic-link or non-canonical component",
        )
    _require_disjoint_roots(resolved, _canonical_disjoint_roots(disjoint_roots))
    return resolved


def _require_posix_descriptor_features() -> None:
    missing: list[str] = []
    if os.name != "posix":
        missing.append("POSIX operating system")
    for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"):
        if not hasattr(os, name):
            missing.append(name)
    supports_dir_fd: set[object] = set(getattr(os, "supports_dir_fd", set()))
    for function in _NATIVE_DIR_FD_FUNCTIONS:
        if function not in supports_dir_fd:
            missing.append(f"{function.__name__}(dir_fd)")
    supports_no_follow: set[object] = set(
        getattr(os, "supports_follow_symlinks", set()),
    )
    for function in _NATIVE_NO_FOLLOW_FUNCTIONS:
        if function not in supports_no_follow:
            missing.append(f"{function.__name__}(follow_symlinks)")
    if not hasattr(os, "fchmod"):
        missing.append("fchmod")
    if missing:
        raise ImmutableArtifactConfinementError(
            "immutable artifact store requires POSIX descriptor features: " + ", ".join(missing),
        )


def _select_prospective_root(root: Path) -> tuple[Path, Path]:
    selected = Path(root).expanduser().absolute()
    if selected.name in {"", ".", ".."}:
        raise ImmutableArtifactConfinementError(
            "immutable artifact root must select one directory",
        )
    if os.path.lexists(selected) and selected.is_symlink():
        raise ImmutableArtifactConfinementError(
            "immutable artifact root contains a symbolic-link component",
        )
    try:
        prospective = selected.resolve(strict=False)
    except OSError as cause:
        raise ImmutableArtifactConfinementError(
            f"immutable artifact root is unsafe: {cause}",
        ) from cause
    return selected, prospective


def _canonical_disjoint_roots(disjoint_roots: Iterable[Path]) -> tuple[Path, ...]:
    canonical: list[Path] = []
    for disjoint_root in disjoint_roots:
        protected = Path(disjoint_root).expanduser()
        if not protected.is_absolute():
            raise ImmutableArtifactConfinementError(
                "immutable artifact disjoint roots must be absolute",
            )
        protected_absolute = protected.absolute()
        _reject_absolute_symlinks(
            protected_absolute,
            label="immutable artifact disjoint root",
        )
        protected_resolved = protected_absolute.resolve(strict=False)
        if protected_resolved != protected_absolute:
            raise ImmutableArtifactConfinementError(
                "immutable artifact disjoint root contains a symbolic-link or non-canonical component",
            )
        canonical.append(protected_resolved)
    return tuple(canonical)


def _prepare_trusted_root(
    selected: Path,
    *,
    host_private: bool,
    protected_roots: tuple[Path, ...],
) -> tuple[Path, tuple[int, int]]:
    missing: list[str] = []
    cursor = selected
    while not os.path.lexists(cursor):
        missing.append(cursor.name)
        cursor = cursor.parent
    root_entries_were_missing = bool(missing)
    if not missing:
        missing.append(selected.name)
        cursor = selected.parent

    try:
        canonical_parent = cursor.resolve(strict=True)
    except OSError as cause:
        raise ImmutableArtifactConfinementError(
            f"immutable artifact root ancestor is unsafe: {cause}",
        ) from cause
    canonical_target = canonical_parent.joinpath(*reversed(missing))
    _require_disjoint_roots(canonical_target, protected_roots)

    descriptors: list[int] = []
    active_error: BaseException | None = None
    try:
        descriptors.append(_open_root_directory(Path(canonical_parent.anchor)))
        for component in canonical_parent.parts[1:]:
            descriptors.append(
                _open_root_child(descriptors[-1], component),
            )
        canonical_root = canonical_parent
        for name in reversed(missing):
            parent_descriptor = descriptors[-1]
            created = False
            try:
                os.mkdir(
                    name,
                    mode=0o700 if host_private else 0o777,
                    dir_fd=parent_descriptor,
                )
                created = True
            except FileExistsError:
                pass
            except OSError as cause:
                raise ImmutableArtifactStoreError(
                    f"immutable artifact root cannot be created: {cause}",
                ) from cause

            descriptor = _open_root_child(parent_descriptor, name)
            descriptors.append(descriptor)
            try:
                if created and host_private:
                    os.fchmod(descriptor, 0o700)
                if root_entries_were_missing or created:
                    os.fsync(descriptor)
                    os.fsync(parent_descriptor)
            except OSError as cause:
                raise ImmutableArtifactStoreError(
                    f"immutable artifact root creation cannot be made durable: {cause}",
                ) from cause
            canonical_root /= name

        root_descriptor = descriptors[-1]
        details = _root_details(root_descriptor)
        if host_private and stat.S_IMODE(details.st_mode) & 0o077:
            raise ImmutableArtifactConfinementError(
                "host-private immutable artifact root permissions are not private",
            )
        identity = details.st_dev, details.st_ino
        try:
            resolved_root = canonical_root.resolve(strict=True)
            path_details = os.stat(canonical_root, follow_symlinks=False)
        except OSError as cause:
            raise ImmutableArtifactConfinementError(
                f"immutable artifact root cannot be bound to its descriptor: {cause}",
            ) from cause
        if (
            resolved_root != canonical_root
            or (
                path_details.st_dev,
                path_details.st_ino,
            )
            != identity
        ):
            raise ImmutableArtifactConfinementError(
                "immutable artifact root identity changed during store creation",
            )
        return canonical_root, identity
    except BaseException as error:
        active_error = error
        raise
    finally:
        cleanup_errors: list[BaseException] = []
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if cleanup_errors:
            detail = "; ".join(str(error) for error in cleanup_errors)
            failure = ImmutableArtifactStoreError(
                f"immutable artifact root cannot be closed: {detail}",
            )
            if active_error is not None:
                active_error.add_note(str(failure))
            else:
                raise failure from cleanup_errors[0]


def _open_root_directory(root: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        return os.open(root, flags)
    except OSError as cause:
        raise ImmutableArtifactConfinementError(
            f"immutable artifact root is unsafe: {cause}",
        ) from cause


def _open_root_child(parent_descriptor: int, name: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        inspected = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as cause:
        raise ImmutableArtifactConfinementError(
            f"immutable artifact root component is unsafe: {cause}",
        ) from cause
    if stat.S_ISLNK(inspected.st_mode):
        raise ImmutableArtifactConfinementError(
            f"immutable artifact root contains a symbolic-link component: {name}",
        )
    try:
        return os.open(name, flags, dir_fd=parent_descriptor)
    except OSError as cause:
        raise ImmutableArtifactConfinementError(
            f"immutable artifact root component is unsafe: {cause}",
        ) from cause


def _root_details(descriptor: int) -> os.stat_result:
    try:
        details = os.fstat(descriptor)
    except OSError as cause:
        raise ImmutableArtifactConfinementError(
            f"immutable artifact root identity cannot be read: {cause}",
        ) from cause
    if not stat.S_ISDIR(details.st_mode):
        raise ImmutableArtifactConfinementError(
            "immutable artifact root is not a directory",
        )
    return details


def _relative_parts(relative_path: str) -> tuple[str, ...]:
    logical = PurePosixPath(relative_path)
    raw_parts = relative_path.split("/")
    if (
        not relative_path
        or logical.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
        or "\x00" in relative_path
    ):
        raise ImmutableArtifactConfinementError(
            "immutable artifact path must be normalized, contained, and relative",
        )
    return tuple(raw_parts)


def _validate_sha256(value: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(
            "SHA-256 digest must contain 64 lowercase hexadecimal characters",
        )
    return value


def _reject_relative_symlinks(root: Path, parts: tuple[str, ...]) -> None:
    current = root
    for part in parts:
        current /= part
        if current.is_symlink():
            raise ImmutableArtifactConfinementError(
                f"immutable artifact path contains a symbolic-link component: {current}",
            )


def _reject_absolute_symlinks(path: Path, *, label: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ImmutableArtifactConfinementError(
                f"{label} contains a symbolic-link component: {current}",
            )


def _require_disjoint_roots(root: Path, disjoint_roots: Iterable[Path]) -> None:
    for protected in disjoint_roots:
        if _paths_overlap(root, protected):
            raise ImmutableArtifactConfinementError(
                "immutable artifact root must not overlap a disjoint root",
            )


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


__all__ = [
    "ImmutableArtifact",
    "ImmutableArtifactCollisionError",
    "ImmutableArtifactConfinementError",
    "ImmutableArtifactIntegrityError",
    "ImmutableArtifactStoreError",
    "ImmutableByteStore",
    "validate_immutable_artifact_root",
]
