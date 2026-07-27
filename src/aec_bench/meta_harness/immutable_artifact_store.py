# ABOUTME: Publishes immutable canonical artifacts beneath one confined durable root.
# ABOUTME: Reloads exact bytes or typed models while rejecting collisions and path escapes.

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Generic, TypeVar

from pydantic import JsonValue, TypeAdapter

from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.ledger.durability import fsync_directory, mkdir_durable


class ImmutableArtifactStoreError(RuntimeError):
    """Base error for confined immutable artifact storage."""


class ImmutableArtifactConfinementError(ImmutableArtifactStoreError):
    """Reject an unsafe root, relative path, or symbolic-link component."""


class ImmutableArtifactCollisionError(ImmutableArtifactStoreError):
    """Reject reuse of one logical path with different immutable bytes."""


class ImmutableArtifactIntegrityError(ImmutableArtifactStoreError):
    """Reject missing, non-regular, or invalid persisted content."""


@dataclass(frozen=True, slots=True)
class ImmutableArtifact:
    """Exact physical reference returned after durable publication."""

    path: Path
    sha256: str
    size_bytes: int


ModelT = TypeVar("ModelT")
ContentModelT = TypeVar("ContentModelT", bound=ContentAddressedModel)
LogicalIdentity = Mapping[str, JsonValue] | str


@dataclass(frozen=True, slots=True)
class StoredEvidenceModel(Generic[ModelT]):
    """Typed model joined to its exact immutable physical artifact."""

    model: ModelT
    artifact: ImmutableArtifact


class ImmutableArtifactStore:
    """Narrow immutable store for canonical bytes and Pydantic-supported models."""

    def __init__(
        self,
        root: Path,
        *,
        disjoint_roots: Iterable[Path] = (),
        host_private: bool = False,
    ) -> None:
        selected = validate_evidence_root(
            root,
            disjoint_roots=disjoint_roots,
        )
        _mkdir_storage_path(
            selected,
            host_private=host_private,
        )
        self._root = selected.resolve(strict=True)
        self._host_private = host_private
        if self._host_private:
            _require_private_directory(self._root)

    @property
    def root(self) -> Path:
        """Return the exact confined storage root."""

        return self._root

    def publish_bytes(
        self,
        relative_path: str,
        payload: bytes,
    ) -> ImmutableArtifact:
        """Publish exact bytes once, replaying equality and rejecting collisions."""

        path = self._path(relative_path)
        content = bytes(payload)
        if os.path.lexists(path):
            observed = self.load_bytes(relative_path)
            if observed != content:
                raise ImmutableArtifactCollisionError(
                    f"immutable artifact collision at {relative_path}",
                )
            return _artifact(path, observed)

        _mkdir_storage_path(
            path.parent,
            host_private=self._host_private,
        )
        _reject_symlinks(path.parent, label="immutable artifact parent")
        temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                observed = self.load_bytes(relative_path)
                if observed != content:
                    raise ImmutableArtifactCollisionError(
                        f"immutable artifact collision at {relative_path}",
                    ) from None
            fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)
        observed = self.load_bytes(relative_path)
        if observed != content:
            raise ImmutableArtifactIntegrityError(
                f"immutable artifact drifted during publication at {relative_path}",
            )
        return _artifact(path, observed)

    def load_bytes(
        self,
        relative_path: str,
        *,
        expected_sha256: str | None = None,
    ) -> bytes:
        """Load exact regular-file bytes from one confined logical path."""

        path = self._path(relative_path)
        if path.is_symlink():
            raise ImmutableArtifactConfinementError(
                f"immutable artifact is a symbolic link: {relative_path}",
            )
        try:
            inspected = path.stat(follow_symlinks=False)
        except OSError as error:
            raise ImmutableArtifactIntegrityError(
                f"immutable artifact is missing: {relative_path}",
            ) from error
        if not stat.S_ISREG(inspected.st_mode):
            raise ImmutableArtifactIntegrityError(
                f"immutable artifact is not a regular file: {relative_path}",
            )
        if self._host_private and stat.S_IMODE(inspected.st_mode) & 0o077:
            raise ImmutableArtifactConfinementError(
                f"immutable artifact must retain host-only permissions: {relative_path}",
            )
        payload = path.read_bytes()
        if expected_sha256 is not None:
            validate_sha256(expected_sha256)
            observed_sha256 = hashlib.sha256(payload).hexdigest()
            if observed_sha256 != expected_sha256:
                raise ImmutableArtifactIntegrityError(
                    f"immutable artifact digest mismatch at {relative_path}",
                )
        return payload

    def exists(self, relative_path: str) -> bool:
        """Return whether a confined logical path has any filesystem entry."""

        return os.path.lexists(self._path(relative_path))

    def publish_model(
        self,
        relative_path: str,
        model: ModelT,
        adapter: TypeAdapter[ModelT],
    ) -> ModelT:
        """Publish a model as canonical JSON and return its exact typed replay."""

        payload = _canonical_model_bytes(model, adapter)
        self.publish_bytes(relative_path, payload)
        selected = self.load_model(relative_path, adapter)
        if selected != model:
            raise ImmutableArtifactIntegrityError(
                f"persisted model differs at {relative_path}",
            )
        return selected

    def load_model(
        self,
        relative_path: str,
        adapter: TypeAdapter[ModelT],
    ) -> ModelT:
        """Validate exact persisted bytes as the requested model type."""

        try:
            return adapter.validate_json(self.load_bytes(relative_path))
        except ValueError as error:
            raise ImmutableArtifactIntegrityError(
                f"immutable model is invalid at {relative_path}: {error}",
            ) from error

    def load_optional_model(
        self,
        relative_path: str,
        adapter: TypeAdapter[ModelT],
    ) -> ModelT | None:
        """Load one typed model when its confined logical path exists."""

        if not self.exists(relative_path):
            return None
        return self.load_model(relative_path, adapter)

    def reference(self, relative_path: str) -> ImmutableArtifact:
        """Return a digest and size for one exact persisted artifact."""

        path = self._path(relative_path)
        return _artifact(path, self.load_bytes(relative_path))

    def _path(self, relative_path: str) -> Path:
        logical = PurePosixPath(relative_path)
        if logical.is_absolute() or not logical.parts or any(part in {"", ".", ".."} for part in logical.parts):
            raise ImmutableArtifactConfinementError(
                "immutable artifact path must be contained and relative",
            )
        path = self._root.joinpath(*logical.parts)
        _reject_symlinks(path, label="immutable artifact path")
        if not path.resolve(strict=False).is_relative_to(self._root):
            raise ImmutableArtifactConfinementError(
                "immutable artifact path escapes its root",
            )
        return path


class EvidenceRepository(ImmutableArtifactStore):
    """Immutable evidence store with content paths and logical identity claims."""

    def relative_path(self, path: Path) -> str:
        """Convert one exact repository path to its confined logical path."""

        absolute = Path(os.path.abspath(path))
        if not absolute.is_relative_to(self.root):
            raise ImmutableArtifactConfinementError(
                "evidence artifact path must remain beneath its repository root",
            )
        relative_path = absolute.relative_to(self.root).as_posix()
        self._path(relative_path)
        return relative_path

    def list_child_files(
        self,
        relative_root: str,
        *,
        filename: str,
    ) -> tuple[str, ...]:
        """List one named file beneath each immediate child directory."""

        logical_filename = PurePosixPath(filename)
        if (
            logical_filename.is_absolute()
            or len(logical_filename.parts) != 1
            or logical_filename.name in {"", ".", ".."}
        ):
            raise ImmutableArtifactConfinementError(
                "evidence child filename must be one relative path segment",
            )
        directory = self._path(relative_root)
        if not os.path.lexists(directory):
            return ()
        inspected = directory.stat(follow_symlinks=False)
        if not stat.S_ISDIR(inspected.st_mode):
            raise ImmutableArtifactConfinementError(
                "evidence child listing root must be a regular directory",
            )
        paths: list[str] = []
        for child in directory.iterdir():
            candidate = child / filename
            if not os.path.lexists(candidate):
                continue
            paths.append(self.relative_path(candidate))
        return tuple(sorted(paths))

    def publish_canonical_model(
        self,
        relative_path: str,
        model: ModelT,
        adapter: TypeAdapter[ModelT],
    ) -> StoredEvidenceModel[ModelT]:
        """Publish canonical model bytes at one fixed confined logical path."""

        self.publish_model(relative_path, model, adapter)
        return self.load_stored_canonical_model(relative_path, adapter)

    def load_stored_canonical_model(
        self,
        relative_path: str,
        adapter: TypeAdapter[ModelT],
    ) -> StoredEvidenceModel[ModelT]:
        """Reload a canonical model together with its exact physical artifact."""

        return StoredEvidenceModel(
            model=self.load_canonical_model(relative_path, adapter),
            artifact=self.reference(relative_path),
        )

    def load_optional_canonical_model(
        self,
        relative_path: str,
        adapter: TypeAdapter[ModelT],
    ) -> StoredEvidenceModel[ModelT] | None:
        """Reload an optional canonical model and its exact physical artifact."""

        if not self.exists(relative_path):
            return None
        return self.load_stored_canonical_model(relative_path, adapter)

    def publish_content_addressed_model(
        self,
        *,
        collection: str,
        filename: str,
        model: ContentModelT,
        adapter: TypeAdapter[ContentModelT],
    ) -> StoredEvidenceModel[ContentModelT]:
        """Publish a model beneath the digest asserted by its contract identity."""

        content_sha256 = validate_sha256(model.content_sha256)
        relative_path = self.content_model_path(
            collection=collection,
            content_sha256=content_sha256,
            filename=filename,
        )
        self.publish_canonical_model(relative_path, model, adapter)
        return self.load_content_addressed_model(
            collection=collection,
            content_sha256=content_sha256,
            filename=filename,
            adapter=adapter,
        )

    def load_content_addressed_model(
        self,
        *,
        collection: str,
        content_sha256: str,
        filename: str,
        adapter: TypeAdapter[ContentModelT],
    ) -> StoredEvidenceModel[ContentModelT]:
        """Reload canonical model bytes and revalidate their asserted digest path."""

        expected_sha256 = validate_sha256(content_sha256)
        relative_path = self.content_model_path(
            collection=collection,
            content_sha256=expected_sha256,
            filename=filename,
        )
        model = self.load_canonical_model(relative_path, adapter)
        if model.content_sha256 != expected_sha256:
            raise ImmutableArtifactIntegrityError(
                f"content-addressed model identity mismatch at {relative_path}",
            )
        return StoredEvidenceModel(
            model=model,
            artifact=self.reference(relative_path),
        )

    def publish_logical_model(
        self,
        *,
        collection: str,
        logical_identity: LogicalIdentity,
        filename: str,
        model: ModelT,
        adapter: TypeAdapter[ModelT],
    ) -> StoredEvidenceModel[ModelT]:
        """Atomically bind one logical identity path to canonical immutable bytes."""

        relative_path = self.logical_model_path(
            collection=collection,
            logical_identity=logical_identity,
            filename=filename,
        )
        self.publish_canonical_model(relative_path, model, adapter)
        return self.load_logical_model(
            collection=collection,
            logical_identity=logical_identity,
            filename=filename,
            adapter=adapter,
        )

    def load_logical_model(
        self,
        *,
        collection: str,
        logical_identity: LogicalIdentity,
        filename: str,
        adapter: TypeAdapter[ModelT],
    ) -> StoredEvidenceModel[ModelT]:
        """Reload canonical model bytes from one deterministic logical identity."""

        relative_path = self.logical_model_path(
            collection=collection,
            logical_identity=logical_identity,
            filename=filename,
        )
        return self.load_stored_canonical_model(relative_path, adapter)

    def load_canonical_model(
        self,
        relative_path: str,
        adapter: TypeAdapter[ModelT],
    ) -> ModelT:
        """Reload a typed model only when its bytes use canonical JSON encoding."""

        encoded = self.load_bytes(relative_path)
        try:
            model = adapter.validate_json(encoded)
        except ValueError as error:
            raise ImmutableArtifactIntegrityError(
                f"immutable model is invalid at {relative_path}: {error}",
            ) from error
        if _canonical_model_bytes(model, adapter) != encoded:
            raise ImmutableArtifactIntegrityError(
                f"immutable model is not canonically serialized at {relative_path}",
            )
        return model

    def content_model_path(
        self,
        *,
        collection: str,
        content_sha256: str,
        filename: str,
    ) -> str:
        """Return the confined relative path for one content-addressed model."""

        digest = validate_sha256(content_sha256)
        relative_path = f"{collection}/{digest}/{filename}"
        self._path(relative_path)
        return relative_path

    def logical_model_path(
        self,
        *,
        collection: str,
        logical_identity: LogicalIdentity,
        filename: str,
    ) -> str:
        """Return the confined hashed path for one logical identity claim."""

        identity_bytes = _logical_identity_bytes(logical_identity)
        relative_path = f"{collection}/{hashlib.sha256(identity_bytes).hexdigest()}/{filename}"
        self._path(relative_path)
        return relative_path


def _canonical_model_bytes(
    model: ModelT,
    adapter: TypeAdapter[ModelT],
) -> bytes:
    payload = json.loads(adapter.dump_json(model))
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _artifact(path: Path, payload: bytes) -> ImmutableArtifact:
    return ImmutableArtifact(
        path=path.resolve(strict=True),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


def _mkdir_storage_path(
    path: Path,
    *,
    host_private: bool,
) -> None:
    target = Path(path)
    missing: list[Path] = []
    cursor = target
    while not os.path.lexists(cursor):
        missing.append(cursor)
        cursor = cursor.parent
    mkdir_durable(target)
    if not host_private:
        return
    for directory in reversed(missing):
        directory.chmod(0o700)
        fsync_directory(directory.parent)


def _reject_symlinks(path: Path, *, label: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ImmutableArtifactConfinementError(
                f"{label} contains a symbolic-link component: {current}",
            )


def _require_private_directory(path: Path) -> None:
    inspected = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(inspected.st_mode):
        raise ImmutableArtifactConfinementError(
            "host-private immutable artifact root must be a directory",
        )
    if stat.S_IMODE(inspected.st_mode) & 0o077:
        raise ImmutableArtifactConfinementError(
            "host-private immutable artifact root must retain host-only permissions",
        )


def _logical_identity_bytes(logical_identity: LogicalIdentity) -> bytes:
    if isinstance(logical_identity, str):
        if not logical_identity:
            raise ImmutableArtifactConfinementError(
                "logical evidence identity must not be empty",
            )
        return logical_identity.encode("utf-8")
    if not logical_identity:
        raise ImmutableArtifactConfinementError(
            "logical evidence identity must not be empty",
        )
    try:
        return json.dumps(
            dict(logical_identity),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ImmutableArtifactConfinementError(
            "logical evidence identity must be canonical JSON",
        ) from error


def validate_evidence_root(
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
    _reject_symlinks(absolute, label="immutable artifact root")
    resolved = absolute.resolve(strict=must_exist)
    if resolved != absolute:
        raise ImmutableArtifactConfinementError(
            "immutable artifact root contains a symbolic-link or non-canonical component",
        )
    for disjoint_root in disjoint_roots:
        protected = Path(disjoint_root).expanduser()
        if not protected.is_absolute():
            raise ImmutableArtifactConfinementError(
                "immutable artifact disjoint roots must be absolute",
            )
        protected_absolute = protected.absolute()
        _reject_symlinks(
            protected_absolute,
            label="immutable artifact disjoint root",
        )
        protected_resolved = protected_absolute.resolve(strict=False)
        if protected_resolved != protected_absolute:
            raise ImmutableArtifactConfinementError(
                "immutable artifact disjoint root contains a symbolic-link or non-canonical component",
            )
        if _paths_overlap(resolved, protected_resolved):
            raise ImmutableArtifactConfinementError(
                "immutable artifact root must not overlap a disjoint root",
            )
    return resolved


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)
