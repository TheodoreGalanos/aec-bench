# ABOUTME: Converts proposal-session evidence values into deterministic canonical JSON.
# ABOUTME: Owns the exact JSON byte representation used for content-addressed evidence artifacts.

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, JsonValue


# This ordered type dispatch is one cohesive serialization boundary; splitting it
# would obscure the precedence that keeps bools, enums, models, and dataclasses stable.
def json_compatible(value: Any) -> JsonValue:  # noqa: C901
    """Return the exact JSON-compatible projection accepted by session evidence."""

    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite numbers are not canonical JSON")
        return value
    if isinstance(value, Enum):
        return json_compatible(value.value)
    if isinstance(value, BaseModel):
        return json_compatible(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: json_compatible(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical JSON objects require string keys")
        return {key: json_compatible(nested) for key, nested in value.items()}
    if isinstance(value, list | tuple):
        return [json_compatible(item) for item in value]
    raise TypeError(f"value of type {type(value).__name__} is not JSON-compatible")


def canonical_json_bytes(payload: Mapping[str, JsonValue]) -> bytes:
    """Encode one proposal-session JSON object into its canonical artifact bytes."""

    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
