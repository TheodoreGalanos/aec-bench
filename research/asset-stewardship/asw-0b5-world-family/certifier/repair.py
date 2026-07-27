# ABOUTME: Reads the exact approved pre-W3 quantitative-composition repair declaration.
# ABOUTME: Rejects changed or noncanonical authority bytes before any tolerance composition can run.

from __future__ import annotations

import hashlib
from typing import Any

from certifier import boundary

COMPOSITION_REPAIR_SHA256 = "38ca15bf46f67ee98aa66539701bbd8fc1889c1e268d42f0f724f7942b3c2ff8"


class CompositionRepairError(ValueError):
    """Raised when the quantitative-composition repair authority differs."""


def canonical_json_bytes(value: object) -> bytes:
    """Encode the same canonical JSON form required by every B5 declaration."""
    return boundary.canonical_json_bytes(value)


def read_composition_repair(raw: bytes) -> dict[str, Any]:
    """Read only the reviewed canonical repair declaration."""
    try:
        declaration = boundary._parse_canonical_object(raw)
    except boundary.CertifierBoundaryError as error:
        raise CompositionRepairError(f"composition repair is not canonical: {error}") from error
    if hashlib.sha256(raw).hexdigest() != COMPOSITION_REPAIR_SHA256:
        raise CompositionRepairError("composition repair content identity differs")
    return declaration
