# ABOUTME: Serializes durable pump-station artifacts as strict canonical JSON.
# ABOUTME: Rebuilds only declared task-owned dataclasses, enums, decimals, and tuples.

from __future__ import annotations

import hashlib
import json
import types
from dataclasses import fields, is_dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, NoReturn, TypeVar, cast, get_args, get_origin, get_type_hints, overload

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunError,
)

PUMP_STATION_SERIALIZATION_VERSION = "pump-station-world-run.v1"
PUMP_STATION_TRANSPORT_FIELD_EXCLUSIONS: tuple[str, ...] = ()

ArtifactT = TypeVar("ArtifactT")


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationWorldRunError(code, detail)


def _encoded(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "$type": type(value).__name__,
            **{field.name: _encoded(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, tuple):
        return [_encoded(item) for item in value]
    if value is None or type(value) in {str, int, bool}:
        return value
    _fail("artifact-type", f"unsupported value {type(value).__name__}")
    raise AssertionError("unreachable")


def pump_station_artifact_bytes(value: object) -> bytes:
    """Return one canonical, newline-terminated task artifact."""
    return (
        json.dumps(
            _encoded(value),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def pump_station_artifact_id(value: object) -> str:
    """Return the content identity of one canonical task artifact."""
    return hashlib.sha256(pump_station_artifact_bytes(value)).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, child in pairs:
        if key in value:
            _fail("canonical-json", f"duplicate field {key}")
        value[key] = child
    return value


def _reject_number(value: str) -> NoReturn:
    _fail("canonical-json", f"unsupported JSON number {value}")


def _expected_value(expected: object) -> object:
    return getattr(expected, "__value__", expected)


def _decode_union(value: object, expected: object) -> object:
    options = get_args(expected)
    if value is None and type(None) in options:
        return None
    if isinstance(value, dict) and isinstance(value.get("$type"), str):
        type_name = value["$type"]
        for option in options:
            candidate = _expected_value(option)
            if isinstance(candidate, type) and is_dataclass(candidate) and candidate.__name__ == type_name:
                return _decode(value, candidate)
        _fail("artifact-type", f"unknown stored type {type_name}")
    failures: list[PumpStationWorldRunError] = []
    for option in options:
        if option is type(None):
            continue
        try:
            return _decode(value, option)
        except PumpStationWorldRunError as error:
            failures.append(error)
    detail = failures[0] if failures else "no matching union member"
    _fail("artifact-type", str(detail))
    raise AssertionError("unreachable")


def _decode_dataclass(value: object, expected: type[Any]) -> object:
    if not isinstance(value, dict):
        _fail("artifact-shape", f"{expected.__name__} must be an object")
    if value.get("$type") != expected.__name__:
        _fail(
            "artifact-type",
            f"expected {expected.__name__}, received {value.get('$type')!r}",
        )
    declared_fields = fields(expected)
    expected_keys = {"$type", *(field.name for field in declared_fields)}
    if set(value) != expected_keys:
        _fail("artifact-shape", f"{expected.__name__} fields differ")
    type_hints = get_type_hints(expected)
    decoded = {field.name: _decode(value[field.name], type_hints[field.name]) for field in declared_fields}
    try:
        return expected(**decoded)
    except PumpStationWorldRunError:
        raise
    except (TypeError, ValueError) as error:
        _fail("artifact-shape", f"{expected.__name__}: {error}")
    raise AssertionError("unreachable")


def _decode_tuple(value: object, expected: object) -> tuple[object, ...]:
    if not isinstance(value, list):
        _fail("artifact-shape", "tuple value must be a JSON array")
    members = get_args(expected)
    if len(members) == 2 and members[1] is Ellipsis:
        return tuple(_decode(item, members[0]) for item in value)
    if len(value) != len(members):
        _fail("artifact-shape", "fixed tuple length differs")
    return tuple(_decode(item, member) for item, member in zip(value, members, strict=True))


def _decode(value: object, expected: object) -> object:
    expected = _expected_value(expected)
    origin = get_origin(expected)
    if origin is types.UnionType or isinstance(expected, types.UnionType):
        return _decode_union(value, expected)
    if origin is tuple:
        return _decode_tuple(value, expected)
    if isinstance(expected, type) and is_dataclass(expected):
        return _decode_dataclass(value, expected)
    if isinstance(expected, type) and issubclass(expected, Enum):
        try:
            return expected(value)
        except (TypeError, ValueError):
            _fail("artifact-type", f"invalid {expected.__name__} value")
    if expected is Decimal:
        if not isinstance(value, str):
            _fail("artifact-type", "decimal must be stored as text")
        try:
            decoded_decimal = Decimal(value)
        except (InvalidOperation, ValueError):
            _fail("artifact-type", "invalid decimal text")
        if not decoded_decimal.is_finite():
            _fail("artifact-type", "decimal must be finite")
        return decoded_decimal
    if expected in {str, int, bool}:
        if type(value) is not expected:
            _fail(
                "artifact-type",
                f"expected {cast(type[object], expected).__name__}",
            )
        return value
    if expected is type(None) and value is None:
        return None
    _fail("artifact-type", f"unsupported declared type {expected!r}")
    raise AssertionError("unreachable")


@overload
def load_pump_station_artifact(payload: bytes, expected_type: type[ArtifactT]) -> ArtifactT: ...


@overload
def load_pump_station_artifact(payload: bytes, expected_type: object) -> object: ...


def load_pump_station_artifact(payload: bytes, expected_type: object) -> object:
    """Strictly rebuild one declared task artifact from canonical bytes."""
    try:
        text = payload.decode("utf-8")
        document = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except PumpStationWorldRunError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail("canonical-json", str(error))
    restored = _decode(document, expected_type)
    if pump_station_artifact_bytes(restored) != payload:
        _fail("canonical-json", "stored bytes are not canonical")
    return restored
