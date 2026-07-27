# ABOUTME: Shared validation helpers for contract models in the aec-bench Python implementation.
# ABOUTME: Keeps common string and path rules explicit and reusable across boundary models.

import os
from collections.abc import Iterable
from copy import deepcopy
from pathlib import PurePath
from typing import Annotated, Any, Never, Self, SupportsIndex

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator


class StrictModel(BaseModel):
    """Base for all contract models. Rejects extra fields at construction."""

    model_config = ConfigDict(extra="forbid")


class _FrozenDict(dict[Any, Any]):
    """Dict-compatible JSON container that rejects mutation through its public API."""

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        copied = type(self)((deepcopy(key, memo), deepcopy(value, memo)) for key, value in self.items())
        memo[id(self)] = copied
        return copied

    @staticmethod
    def _reject_mutation() -> Never:
        raise TypeError("nested values in frozen contract models are immutable")

    def __setitem__(self, key: Any, value: Any) -> Never:
        self._reject_mutation()

    def __delitem__(self, key: Any) -> Never:
        self._reject_mutation()

    def __ior__(self, other: Any) -> Self:  # type: ignore[misc]
        self._reject_mutation()

    def clear(self) -> Never:
        self._reject_mutation()

    def pop(self, key: Any, default: Any = None) -> Never:
        self._reject_mutation()

    def popitem(self) -> Never:
        self._reject_mutation()

    def setdefault(self, key: Any, default: Any = None) -> Never:
        self._reject_mutation()

    def update(self, *args: Any, **kwargs: Any) -> Never:
        self._reject_mutation()


class _FrozenList(list[Any]):
    """List-compatible JSON container that rejects mutation through its public API."""

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        copied = type(self)(deepcopy(value, memo) for value in self)
        memo[id(self)] = copied
        return copied

    @staticmethod
    def _reject_mutation() -> Never:
        raise TypeError("nested values in frozen contract models are immutable")

    def __setitem__(self, key: Any, value: Any) -> Never:
        self._reject_mutation()

    def __delitem__(self, key: Any) -> Never:
        self._reject_mutation()

    def __iadd__(self, value: Iterable[Any]) -> Self:  # type: ignore[misc]
        self._reject_mutation()

    def __imul__(self, value: SupportsIndex) -> Self:
        self._reject_mutation()

    def append(self, value: Any) -> Never:
        self._reject_mutation()

    def clear(self) -> Never:
        self._reject_mutation()

    def extend(self, values: Any) -> Never:
        self._reject_mutation()

    def insert(self, index: SupportsIndex, value: Any) -> Never:
        self._reject_mutation()

    def pop(self, index: SupportsIndex = -1) -> Never:
        self._reject_mutation()

    def remove(self, value: Any) -> Never:
        self._reject_mutation()

    def reverse(self) -> Never:
        self._reject_mutation()

    def sort(self, *args: Any, **kwargs: Any) -> Never:
        self._reject_mutation()


def _deeply_freeze(value: Any) -> Any:
    if isinstance(value, _FrozenDict | _FrozenList):
        return value
    if isinstance(value, dict):
        return _FrozenDict((key, _deeply_freeze(item)) for key, item in value.items())
    if isinstance(value, list):
        return _FrozenList(_deeply_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_deeply_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_deeply_freeze(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(_deeply_freeze(item) for item in value)
    return value


class FrozenStrictModel(StrictModel):
    """Strict contract model with immutable fields and nested containers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def freeze_nested_containers(self) -> Self:
        for field_name in type(self).model_fields:
            object.__setattr__(self, field_name, _deeply_freeze(getattr(self, field_name)))
        return self


class LenientModel(BaseModel):
    """Base for external/third-party contract models. Accepts extra fields."""

    model_config = ConfigDict(extra="allow")


def resolve_env_ref(value: str) -> str:
    """Resolve an ``env:VAR_NAME`` reference to its environment value.

    If *value* starts with ``env:``, the remainder is treated as an
    environment variable name and looked up via ``os.environ``.
    All other strings are returned unchanged.

    Raises ``ValueError`` if the referenced variable is not set.
    """
    if not value.startswith("env:"):
        return value
    var_name = value[4:]
    env_value = os.environ.get(var_name)
    if env_value is None:
        msg = f"Environment variable '{var_name}' is not set (from '{value}')"
        raise ValueError(msg)
    return env_value


def ensure_non_empty_string(value: str) -> str:
    if not value.strip():
        msg = "value must not be blank"
        raise ValueError(msg)
    return value


NonEmptyStr = Annotated[str, BeforeValidator(ensure_non_empty_string)]


def ensure_optional_non_empty_string(value: str | None) -> str | None:
    if value is None:
        return None
    return ensure_non_empty_string(value)


def ensure_relative_path(value: str) -> str:
    ensure_non_empty_string(value)
    if PurePath(value).is_absolute():
        msg = "path must be relative"
        raise ValueError(msg)
    return value


def ensure_optional_relative_path(value: str | None) -> str | None:
    if value is None:
        return None
    return ensure_relative_path(value)


def normalize_workspace_path(path: str) -> str:
    """Ensure a workspace path has a leading slash."""
    if path.startswith("/"):
        return path
    return f"/{path}"


def infer_output_format(output_path: str) -> str:
    """Infer a short format label from the output file suffix."""
    suffix = PurePath(output_path).suffix.lower()
    formats = {".jsonl": "jsonl", ".json": "json", ".md": "markdown", ".csv": "csv"}
    return formats.get(suffix, "text")
