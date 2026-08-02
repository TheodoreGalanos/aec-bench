# ABOUTME: Publishes immutable canonical artifacts beneath one confined durable root.
# ABOUTME: Reloads exact bytes or typed models while rejecting collisions and path escapes.

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Generic, TypeVar

from pydantic import JsonValue, TypeAdapter

from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.ledger.immutable_artifact_store import ImmutableArtifact as ImmutableArtifact
from aec_bench.ledger.immutable_artifact_store import (
    ImmutableArtifactCollisionError as ImmutableArtifactCollisionError,
)
from aec_bench.ledger.immutable_artifact_store import (
    ImmutableArtifactConfinementError as ImmutableArtifactConfinementError,
)
from aec_bench.ledger.immutable_artifact_store import (
    ImmutableArtifactIntegrityError as ImmutableArtifactIntegrityError,
)
from aec_bench.ledger.immutable_artifact_store import (
    ImmutableArtifactStoreError as ImmutableArtifactStoreError,
)
from aec_bench.ledger.immutable_artifact_store import (
    ImmutableByteStore,
    validate_immutable_artifact_root,
)

ModelT = TypeVar("ModelT")
ContentModelT = TypeVar("ContentModelT", bound=ContentAddressedModel)
LogicalIdentity = Mapping[str, JsonValue] | str


@dataclass(frozen=True, slots=True)
class StoredEvidenceModel(Generic[ModelT]):
    """Typed model joined to its exact immutable physical artifact."""

    model: ModelT
    artifact: ImmutableArtifact


class ImmutableArtifactStore(ImmutableByteStore):
    """Narrow immutable store for canonical bytes and Pydantic-supported models."""

    def __init__(
        self,
        root: Path,
        *,
        disjoint_roots: Iterable[Path] = (),
        host_private: bool = False,
    ) -> None:
        protected_roots = tuple(disjoint_roots)
        selected = validate_evidence_root(
            root,
            disjoint_roots=protected_roots,
        )
        super().__init__(
            selected,
            disjoint_roots=protected_roots,
            host_private=host_private,
        )

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

    return validate_immutable_artifact_root(
        root,
        disjoint_roots=disjoint_roots,
        must_exist=must_exist,
    )
