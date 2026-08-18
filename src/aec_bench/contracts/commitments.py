# ABOUTME: Provides canonical JSON hashing for explicit semantic and operational commitments.
# ABOUTME: Keeps named commitments separate from exact-byte artifact identity and domain models.

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_sha256(payload: Any) -> str:
    """Return the SHA-256 digest of one canonical JSON-compatible payload."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_sha256(value: str) -> str:
    """Validate a lowercase hexadecimal SHA-256 digest."""

    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("SHA-256 digest must contain 64 lowercase hexadecimal characters")
    return value


__all__ = ("canonical_json_sha256", "validate_sha256")
