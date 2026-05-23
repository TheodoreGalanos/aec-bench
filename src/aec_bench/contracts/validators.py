# ABOUTME: Shared validation helpers for contract models in the aec-bench Python implementation.
# ABOUTME: Keeps common string and path rules explicit and reusable across boundary models.

import os
from pathlib import PurePath
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict


class StrictModel(BaseModel):
    """Base for all contract models. Rejects extra fields at construction."""

    model_config = ConfigDict(extra="forbid")


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
