# ABOUTME: Reads the exact repaired W4 probe catalogue using a sensitivity-owned canonicalizer.
# ABOUTME: Rejects changed matrix bytes before member construction, composition, or engine execution.

from __future__ import annotations

import hashlib
import json
from typing import Any, NoReturn, cast

PROBE_CATALOGUE_SHA256 = "7337b5286853f782e4bc60e5dbdcad5eb296a3e234504e4c815c049a30f0a9a7"
FAMILY_COVERAGE_REPAIR_SHA256 = "828bec8786523ef8b2e1485d2cfbb2df08731708b038ecaaf6bc09b66da79fce"


class ProbeCatalogueError(ValueError):
    """Fail-closed W4 probe-catalogue rejection."""


def _fail(detail: str) -> NoReturn:
    raise ProbeCatalogueError(f"w4-probe-catalogue: {detail}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            _fail(f"duplicate key {key!r}")
        value[key] = child
    return value


def _check_types(value: object) -> None:
    if value is None or isinstance(value, float):
        _fail("null and JSON floating-point values are forbidden")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("object key is not text")
            _check_types(child)
    elif isinstance(value, list):
        for child in value:
            _check_types(child)
    elif not isinstance(value, str | int | bool):
        _fail(f"unsupported JSON type {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """Encode canonical W4 declaration bytes without another role's helper."""
    _check_types(value)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{encoded}\n".encode()


def _read_exact(raw: bytes, expected_sha256: str) -> dict[str, Any]:
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
        _fail("exactly one terminal LF is required")
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(str(error))
    if not isinstance(parsed, dict):
        _fail("top-level value must be an object")
    declaration = cast(dict[str, Any], parsed)
    if canonical_json_bytes(declaration) != raw:
        _fail("bytes are not canonical")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("content identity differs")
    return declaration


def read_probe_catalogue(raw: bytes) -> dict[str, Any]:
    """Read only the reviewed W4 catalogue identity."""
    return _read_exact(raw, PROBE_CATALOGUE_SHA256)


def read_family_coverage_repair(raw: bytes) -> dict[str, Any]:
    """Read only the pre-generation W4 family-coverage repair."""
    return _read_exact(raw, FAMILY_COVERAGE_REPAIR_SHA256)
