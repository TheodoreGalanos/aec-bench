# ABOUTME: Defines shared UUIDv7, human-readable identity, and portable path values.
# ABOUTME: Keeps durable identity and filesystem containment rules in one contract boundary.

from __future__ import annotations

import re
import secrets
import time
from enum import StrEnum
from pathlib import Path, PureWindowsPath
from typing import Annotated
from uuid import RFC_4122, UUID

from pydantic import Field, field_validator, model_validator
from pydantic_core import core_schema

from aec_bench.contracts.validators import FrozenStrictModel


class EntityKind(StrEnum):
    """Durable entity categories that use the shared identity factory."""

    TASK = "task"
    EXPERIMENT = "experiment"
    RUN = "run"
    PLAN = "plan"
    TRIAL = "trial"
    ATTEMPT = "attempt"
    ARTIFACT = "artifact"
    WORLD = "world"
    WORLD_PROFILE = "world_profile"
    LIFECYCLE = "lifecycle"
    VARIANT = "variant"
    STUDY = "study"
    RECEIPT = "receipt"
    CATALOGUE_RELEASE = "catalogue_release"


def _parse_uuid(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise TypeError("entity ID must be a UUID or UUID string")
    try:
        return UUID(value)
    except (ValueError, AttributeError) as error:
        raise ValueError("entity ID must be a valid UUID") from error


def validate_uuidv7(value: UUID | str) -> UUID:
    """Validate and return an RFC 9562 UUID version 7."""

    parsed = _parse_uuid(value)
    if parsed.version != 7 or parsed.variant != RFC_4122:
        raise ValueError("entity ID must be an RFC 9562 UUIDv7")
    return parsed


def new_entity_id(kind: EntityKind | str) -> UUID:
    """Create one random UUIDv7 for *kind*.

    The kind is validated at the call boundary to make accidental use of a
    free-form label visible. It is not encoded in the UUID.
    """

    try:
        EntityKind(kind)
    except (TypeError, ValueError) as error:
        raise ValueError(f"unsupported entity kind: {kind!r}") from error

    timestamp_ms = time.time_ns() // 1_000_000
    # UUIDv7: 48-bit Unix timestamp, version 7, 12 random bits, RFC 4122
    # variant, and 62 random bits. The random fields prevent same-millisecond
    # entity creation from colliding.
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    return _build_uuidv7(timestamp_ms, random_a, random_b)


def _build_uuidv7(timestamp_ms: int, random_a: int, random_b: int) -> UUID:
    if not 0 <= timestamp_ms < 1 << 48:
        raise ValueError("UUIDv7 timestamp must fit in 48 bits")
    if not 0 <= random_a < 1 << 12:
        raise ValueError("UUIDv7 rand_a must fit in 12 bits")
    if not 0 <= random_b < 1 << 62:
        raise ValueError("UUIDv7 rand_b must fit in 62 bits")
    value = (timestamp_ms << 80) | (7 << 76) | (random_a << 64) | (0b10 << 62) | random_b
    return UUID(int=value)


_KEY_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*")


def validate_entity_key(value: str) -> str:
    """Validate one stable, human-readable entity key."""

    if not isinstance(value, str):
        raise TypeError("entity key must be a string")
    if _KEY_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "entity key must use lowercase ASCII letters, numbers, hyphens, underscores, "
            "and non-empty slash-separated components"
        )
    return value


class EntityKey(str):
    """A validated human-readable key used to name a durable entity."""

    def __new__(cls, value: str) -> EntityKey:
        return str.__new__(cls, validate_entity_key(value))

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: object, handler: object) -> core_schema.CoreSchema:
        del source_type, handler
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema(strict=True))


class EntityIdentity(FrozenStrictModel):
    """Stable identity, readable key, and positive semantic version."""

    id: UUID
    key: EntityKey
    version: Annotated[int, Field(strict=True, gt=0)]
    aliases: tuple[EntityKey, ...] = ()

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, value: UUID | str) -> UUID:
        return validate_uuidv7(value)

    @model_validator(mode="after")
    def validate_aliases(self) -> EntityIdentity:
        if self.key in self.aliases:
            raise ValueError("entity aliases must not include the canonical key")
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("entity aliases must be unique")
        return self


_WINDOWS_RESERVED_NAMES = (
    frozenset({"CON", "PRN", "AUX", "NUL"})
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
_WINDOWS_FORBIDDEN_CHARS = frozenset('<>:"|?*')
_MAX_COMPONENT_BYTES = 255


def validate_portable_relative_path(value: str) -> str:
    """Validate one portable, slash-separated relative path."""

    if not isinstance(value, str):
        raise TypeError("portable relative path must be a string")
    if not value or any(ord(character) < 0x20 for character in value) or "\\" in value:
        raise ValueError(
            "portable relative path must be non-empty and must not contain control characters or backslashes"
        )
    if value.startswith("/"):
        raise ValueError("portable relative path must not be absolute")

    components = value.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise ValueError("portable relative path must contain only non-empty ordinary components")
    for component in components:
        if len(component.encode("utf-8")) > _MAX_COMPONENT_BYTES:
            raise ValueError("portable relative path component exceeds 255 UTF-8 bytes")
        if component[-1] in {".", " "} or any(character in _WINDOWS_FORBIDDEN_CHARS for character in component):
            raise ValueError("portable relative path contains a Windows-incompatible component")
        windows_name = component.split(".", 1)[0].upper()
        if windows_name in _WINDOWS_RESERVED_NAMES:
            raise ValueError("portable relative path contains a Windows-reserved component")
    if PureWindowsPath(value).drive:
        raise ValueError("portable relative path must not be drive-qualified")
    return value


class PortableRelativePath(str):
    """A validated slash-separated path that can be used on supported platforms."""

    def __new__(cls, value: str) -> PortableRelativePath:
        return str.__new__(cls, validate_portable_relative_path(value))

    @property
    def parts(self) -> tuple[str, ...]:
        return tuple(self.split("/"))

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: object, handler: object) -> core_schema.CoreSchema:
        del source_type, handler
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema(strict=True))


def resolve_below(root: Path, relative: PortableRelativePath | str) -> Path:
    """Resolve *relative* below *root*, including symlink containment."""

    validated = relative if isinstance(relative, PortableRelativePath) else PortableRelativePath(relative)
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*validated.parts).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError(f"path escapes its trusted root: {relative}")
    return candidate


def format_display_ref(key: EntityKey | str, entity_id: UUID | str) -> str:
    """Format a readable key and the display-only short UUID suffix."""

    return f"{EntityKey(key)} · {validate_uuidv7(entity_id).hex[-8:]}"


__all__ = (
    "EntityIdentity",
    "EntityKey",
    "EntityKind",
    "PortableRelativePath",
    "format_display_ref",
    "new_entity_id",
    "resolve_below",
    "validate_entity_key",
    "validate_portable_relative_path",
    "validate_uuidv7",
)
