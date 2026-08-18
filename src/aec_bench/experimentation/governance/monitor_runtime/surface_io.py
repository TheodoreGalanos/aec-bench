# ABOUTME: Owns canonical, symlink-safe I/O for physical canaries and external monitor evidence.
# ABOUTME: Centralizes monitored-surface confinement, exact publication, and typed evidence loading.

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from pydantic import JsonValue, TypeAdapter

from aec_bench.contracts.harness_kernel import FrozenStrictModel
from aec_bench.experimentation.governance.monitor_repository import (
    MonitorRuntimeCollisionError,
    MonitorRuntimeConfinementError,
    MonitorRuntimeIntegrityError,
)
from aec_bench.experimentation.governance.monitor_runtime.contracts import MonitorCanarySurface
from aec_bench.experimentation.governance.standing_monitors import (
    CanaryCommitment,
    CanaryKind,
)
from aec_bench.ledger.durability import fsync_directory

_JSON_VALUE_ADAPTER: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def validate_canary_payload(
    *,
    commitment: CanaryCommitment,
    payload: JsonValue,
) -> None:
    """Require physical JSON to match its exact canary commitment."""

    if hashlib.sha256(canonical_json_bytes(payload)[:-1]).hexdigest() != commitment.artifact_sha256:
        raise MonitorRuntimeIntegrityError(f"physical payload for {commitment.canary_id} does not match its commitment")
    if commitment.kind is CanaryKind.MOTIF and motif_effective_state(payload) is None:
        raise MonitorRuntimeIntegrityError("motif canary payload requires a non-empty effective_state")


def motif_effective_state(payload: JsonValue) -> str | None:
    """Return the motif state exposed by canonical canary JSON."""

    if not isinstance(payload, dict):
        return None
    value = payload.get("effective_state")
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def publish_surface_exact(
    *,
    surface_root: Path,
    path: Path,
    content: bytes,
) -> None:
    """Publish one immutable canary with an atomic hard-link commit."""

    guard_surface_path(surface_root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    guard_surface_path(surface_root, path)
    if os.path.lexists(path):
        if (
            read_surface_file(
                surface_root=surface_root,
                path=path,
                label="physical canary payload",
            )
            != content
        ):
            raise MonitorRuntimeCollisionError("host canary placement contains different content")
        return
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o644,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if (
                read_surface_file(
                    surface_root=surface_root,
                    path=path,
                    label="physical canary payload",
                )
                != content
            ):
                raise MonitorRuntimeCollisionError("host canary placement contains different content") from None
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def load_external_model[ModelT: FrozenStrictModel](
    path: Path,
    model_type: type[ModelT],
    *,
    label: str,
) -> ModelT:
    """Load a canonically serialized typed model from host evidence."""

    encoded = read_external_file(path, label=label)
    try:
        model = model_type.model_validate_json(encoded)
    except ValueError as error:
        raise MonitorRuntimeIntegrityError(f"{label} is corrupt or has the wrong typed schema") from error
    if canonical_model_bytes(model) != encoded:
        raise MonitorRuntimeIntegrityError(f"{label} is not canonically serialized")
    return model


def read_external_file(path: Path, *, label: str) -> bytes:
    """Read one regular, non-symlink host-evidence file."""

    if not os.path.lexists(path):
        raise MonitorRuntimeIntegrityError(f"{label} is missing")
    if path.is_symlink():
        raise MonitorRuntimeConfinementError(f"{label} must not be a symlink")
    if not path.is_file():
        raise MonitorRuntimeConfinementError(f"{label} must be a regular file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise MonitorRuntimeIntegrityError(f"{label} is unreadable") from error


def read_surface_file(
    *,
    surface_root: Path,
    path: Path,
    label: str,
) -> bytes:
    """Read a regular file confined beneath one monitored surface."""

    guard_surface_path(surface_root, path)
    if not os.path.lexists(path):
        raise MonitorRuntimeIntegrityError(f"{label} is missing")
    if path.is_symlink():
        raise MonitorRuntimeConfinementError(f"{label} must not be a symlink")
    if not path.is_file():
        raise MonitorRuntimeConfinementError(f"{label} must be a regular file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise MonitorRuntimeIntegrityError(f"{label} is unreadable") from error


def read_surface_canonical_json(
    *,
    surface_root: Path,
    path: Path,
    label: str,
) -> JsonValue:
    """Read canonical JSON from a confined monitored surface."""

    encoded = read_surface_file(
        surface_root=surface_root,
        path=path,
        label=label,
    )
    try:
        payload: JsonValue = _JSON_VALUE_ADAPTER.validate_json(encoded)
    except ValueError as error:
        raise MonitorRuntimeIntegrityError(f"{label} is not valid JSON") from error
    if canonical_json_bytes(payload) != encoded:
        raise MonitorRuntimeIntegrityError(f"{label} is not canonically serialized")
    return payload


def guard_surface_path(surface_root: Path, path: Path) -> None:
    """Reject escapes and symlink traversal beneath a monitored surface."""

    absolute_root = Path(os.path.abspath(surface_root))
    absolute = Path(os.path.abspath(path))
    if not absolute.is_relative_to(absolute_root):
        raise MonitorRuntimeConfinementError("physical canary path escapes its monitored surface root")
    cursor = absolute_root
    if os.path.lexists(cursor) and cursor.is_symlink():
        raise MonitorRuntimeConfinementError("monitored canary surface root must not be a symlink")
    for part in absolute.relative_to(absolute_root).parts:
        cursor /= part
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise MonitorRuntimeConfinementError("physical canary path contains a symlink")


def validate_canary_surface(
    *,
    surface: MonitorCanarySurface,
    kind: CanaryKind,
    monitor_root: Path,
    authority_root: Path,
    candidate_roots: tuple[Path, ...],
) -> None:
    """Require one canonical canary surface inside the supplied candidate roots."""

    host_root = Path(surface.host_root)
    if (
        surface.kind is not kind
        or not host_root.is_absolute()
        or str(host_root.resolve(strict=False)) != surface.host_root
    ):
        raise MonitorRuntimeConfinementError(
            "monitored canary surface must have an exact kind and canonical absolute host root"
        )
    if host_root.is_symlink() or not host_root.is_dir():
        raise MonitorRuntimeConfinementError("monitored canary surface root must be a regular non-symlink directory")
    normalized_authority = Path(authority_root).resolve(strict=False)
    if paths_overlap(host_root, monitor_root) or paths_overlap(
        host_root,
        normalized_authority,
    ):
        raise MonitorRuntimeConfinementError("monitored canary surface must remain outside monitor and authority roots")
    if not any(host_root == candidate or host_root.is_relative_to(candidate) for candidate in candidate_roots):
        raise MonitorRuntimeConfinementError("monitored canary surface must be inside a supplied candidate root")


def canonical_model_bytes(model: FrozenStrictModel) -> bytes:
    """Encode one content-addressed model in the repository canonical form."""

    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def canonical_json_bytes(payload: JsonValue) -> bytes:
    """Encode JSON in the monitor runtime canonical form."""

    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def paths_overlap(left: Path, right: Path) -> bool:
    """Return whether either resolved root contains the other."""

    return left == right or left.is_relative_to(right) or right.is_relative_to(left)
