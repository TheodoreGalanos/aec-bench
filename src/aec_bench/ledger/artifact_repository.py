# ABOUTME: Publishes canonical models and exact bytes through one immutable artifact-reference boundary.
# ABOUTME: Resolves stable artifact IDs and verifies size and SHA-256 on every referenced read.

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePath
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.ledger.immutable_byte_store import ImmutableArtifactIntegrityError, ImmutableByteStore

_ARTIFACT_COLLECTION = "artifacts/sha256"


class ArtifactRepository:
    """Content-addressed exact-byte repository with portable typed references."""

    def __init__(
        self,
        root: Path,
        *,
        disjoint_roots: Iterable[Path] = (),
        host_private: bool = False,
    ) -> None:
        self._bytes = ImmutableByteStore(root, disjoint_roots=disjoint_roots, host_private=host_private)

    @property
    def root(self) -> Path:
        """Return the trusted physical repository root."""

        return self._bytes.root

    def publish_bytes(self, *, data: bytes, media_type: str) -> ArtifactRef:
        """Publish non-empty exact bytes and return their stable repository reference."""

        payload = bytes(data)
        if not payload:
            raise ValueError("artifact bytes must not be empty")
        digest = hashlib.sha256(payload).hexdigest()
        artifact_id = _artifact_id(digest)
        stored = self._bytes.publish_bytes(artifact_id, payload)
        return ArtifactRef(
            artifact_id=artifact_id,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            media_type=media_type,
        )

    def publish_model(self, *, value: BaseModel, media_type: str) -> ArtifactRef:
        """Publish one Pydantic model with the repository canonical JSON encoding."""

        return self.publish_bytes(data=canonical_model_bytes(value), media_type=media_type)

    def read_bytes(self, ref: ArtifactRef) -> bytes:
        """Read referenced bytes and fail closed on locator, size, or digest mismatch."""

        expected_id = _artifact_id(ref.sha256)
        if ref.artifact_id != expected_id:
            raise ImmutableArtifactIntegrityError("artifact reference ID does not match its SHA-256")
        payload = self._bytes.load_bytes(ref.artifact_id, expected_sha256=ref.sha256)
        if len(payload) != ref.size_bytes:
            raise ImmutableArtifactIntegrityError(f"immutable artifact size mismatch at {ref.artifact_id}")
        return payload


def canonical_model_bytes(value: BaseModel) -> bytes:
    """Encode one model as canonical UTF-8 JSON with one final newline."""

    payload = value.model_dump(mode="python", round_trip=True, by_alias=True)
    normalized = _canonical_json_value(payload)
    return (
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _artifact_id(digest: str) -> str:
    return f"{_ARTIFACT_COLLECTION}/{digest[:2]}/{digest}"


def _canonical_json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, Enum):
        return _canonical_json_value(value.value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical artifact numbers must be finite")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("canonical artifact decimals must be finite")
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is not None and value.utcoffset() == UTC.utcoffset(value):
            return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return value.isoformat()
    if isinstance(value, date | time):
        return value.isoformat()
    if isinstance(value, UUID | PurePath):
        return str(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("canonical artifact bytes must contain UTF-8") from error
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("canonical artifact object keys must be strings")
        return {key: _canonical_json_value(item) for key, item in value.items()}
    if isinstance(value, set | frozenset):
        normalized = [_canonical_json_value(item) for item in value]
        return sorted(normalized, key=_canonical_sort_key)
    if isinstance(value, list | tuple):
        return [_canonical_json_value(item) for item in value]
    try:
        converted = to_jsonable_python(value, inf_nan_mode="constants")
    except (TypeError, ValueError) as error:
        raise ValueError(f"canonical artifact value is not JSON serializable: {type(value).__name__}") from error
    if converted is value:
        raise ValueError(f"canonical artifact value is not JSON serializable: {type(value).__name__}")
    return _canonical_json_value(converted)


def _canonical_sort_key(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


__all__ = ("ArtifactRepository", "canonical_model_bytes")
