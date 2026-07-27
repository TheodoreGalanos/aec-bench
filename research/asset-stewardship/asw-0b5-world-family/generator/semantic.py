# ABOUTME: Canonicalizes W1 hydraulic and setting series into exact path-free semantic bytes.
# ABOUTME: Owns binary32 normalization, SI scaling, series metadata, and semantic output identity only.

from __future__ import annotations

import hashlib
import math
import re
import struct
from collections.abc import Iterable
from typing import Any

from generator.request import canonical_json_bytes

BINARY32_PATTERN = re.compile(r"[0-9a-f]{8}\Z")
SEMANTIC_DOMAIN = b"asw-0b4.semantic-output.v1\0"


class SemanticError(ValueError):
    """Raised when a value cannot enter the canonical W1 semantic form."""


def round_binary32(value: float) -> float:
    """Round one finite Python float to IEEE-754 binary32, ties to even."""
    if not math.isfinite(value):
        raise SemanticError("binary32 value must be finite")
    try:
        rounded = struct.unpack(">f", struct.pack(">f", value))[0]
    except OverflowError as error:
        raise SemanticError("binary32 value must be finite") from error
    return 0.0 if rounded == 0.0 else rounded


def binary32_hex(value: float) -> str:
    """Encode one normalized finite binary32 as big-endian lower-case hex."""
    rounded = round_binary32(value)
    return struct.pack(">f", rounded).hex()


def binary32_from_hex(value: str) -> float:
    """Decode one canonical finite binary32 hex value."""
    if BINARY32_PATTERN.fullmatch(value) is None:
        raise SemanticError("binary32 hex value is not canonical")
    decoded = float(struct.unpack(">f", bytes.fromhex(value))[0])
    if not math.isfinite(decoded) or value == "80000000":
        raise SemanticError("binary32 hex value must be finite canonical non-negative-zero")
    return decoded


def scale_lps_to_m3_s(value: float) -> float:
    """Apply the exact LPS-to-m3/s scale and round the semantic result to binary32."""
    return round_binary32(value / 1000.0)


def binary32_series(
    values: Iterable[float],
    *,
    source: str,
    unit: str,
    scale_lps: bool = False,
) -> dict[str, Any]:
    """Build one canonical binary32 semantic-series object."""
    encoded = [
        binary32_hex(scale_lps_to_m3_s(value) if scale_lps else value)
        for value in values
    ]
    result: dict[str, Any] = {
        "representation": "ieee754-binary32-be-hex",
        "source": source,
        "unit": unit,
        "values": encoded,
    }
    if scale_lps:
        result["transformation"] = "asw-0b4.exact-scale.lps-to-m3-s.v1"
    return result


def integer_series(
    values: Iterable[int],
    *,
    source: str,
    unit: str,
) -> dict[str, Any]:
    """Build one exact-integer semantic-series object."""
    encoded = list(values)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in encoded):
        raise SemanticError("integer series contains a non-integer value")
    return {
        "representation": "exact-integer",
        "source": source,
        "unit": unit,
        "values": encoded,
    }


def semantic_bytes(value: dict[str, Any]) -> bytes:
    """Return canonical semantic output bytes."""
    return canonical_json_bytes(value)


def semantic_sha256(value: dict[str, Any]) -> str:
    """Return the domain-separated semantic output identity."""
    return hashlib.sha256(SEMANTIC_DOMAIN + semantic_bytes(value)).hexdigest()
