# ABOUTME: Independently gates W5 package-root creation on one passing W4 family result.
# ABOUTME: Creates no directory or payload when the family is rejected, malformed, or changed.

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, NoReturn, cast

FAMILY_RESULT_DOMAIN = b"asw-0b5.family-decision.v1\0"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class PackageGateError(ValueError):
    """Raised before any package mutation when family authority is insufficient."""


def _fail(detail: str) -> NoReturn:
    raise PackageGateError(f"package-gate: {detail}")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            _fail(f"duplicate key {key!r}")
        value[key] = child
    return value


def _canonical(value: object) -> bytes:
    def check(child: object) -> None:
        if child is None or isinstance(child, float):
            _fail("null and JSON floating-point values are forbidden")
        if isinstance(child, dict):
            for key, nested in child.items():
                if not isinstance(key, str):
                    _fail("object key is not text")
                check(nested)
        elif isinstance(child, list):
            for nested in child:
                check(nested)
        elif not isinstance(child, str | int | bool):
            _fail("unsupported JSON value")

    check(value)
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _read_family(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
        _fail("family bytes require exactly one terminal LF")
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(str(error))
    if not isinstance(parsed, dict):
        _fail("family result is not an object")
    value = cast(dict[str, Any], parsed)
    if _canonical(value) != raw:
        _fail("family result is not canonical")
    if set(value) != {
        "analytical_inventory_content_id",
        "composition_result_content_id",
        "coverage",
        "execution",
        "first_failure",
        "profile_id",
        "promotable",
        "result_content_id",
        "schema_id",
        "terminal_state",
    }:
        _fail("family result shape differs")
    payload = {key: child for key, child in value.items() if key != "result_content_id"}
    expected = hashlib.sha256(FAMILY_RESULT_DOMAIN + _canonical(payload)).hexdigest()
    if (
        not isinstance(value["result_content_id"], str)
        or SHA256.fullmatch(value["result_content_id"]) is None
        or value["result_content_id"] != expected
    ):
        _fail("family result content identity differs")
    if (
        value["profile_id"] != "AU-NSW-LH-SYN-SPS-v1"
        or value["schema_id"] != "asw-0b5.family-decision.v1"
        or value["promotable"] is not False
    ):
        _fail("family authority differs")
    return value


def authorize_package_root(
    *,
    family_result_bytes: bytes,
    target: Path,
) -> Path:
    """Create an empty proposal root only after an exact passing family result."""
    value = _read_family(family_result_bytes)
    if value["terminal_state"] != "family-w4-checks-pass":
        _fail("family-w4-checks-pass is required before package construction")
    target = target.resolve()
    if target.exists() or target.is_symlink():
        _fail("package target must be absent")
    target.mkdir(parents=True)
    return target
