# ABOUTME: Canonical hashing helpers for hydraulic source, package, and run identities.
# ABOUTME: Rejects ambiguous JSON values so equal declared inputs have equal bytes.

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Return one stable UTF-8 JSON encoding for an identity-bearing value."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    """Return the SHA-256 of the canonical JSON representation."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
