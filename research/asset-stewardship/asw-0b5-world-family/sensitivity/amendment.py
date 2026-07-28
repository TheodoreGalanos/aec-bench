# ABOUTME: Reads exact post-rejection W4 C-R07 and C-R08 amendment authorities.
# ABOUTME: Rejects byte drift before amended tolerance composition or generation binding.

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

C_R07_AMENDMENT_SHA256 = (
    "488c82d09696472533669f21017c19cd4156952f4d075b278de91b580bf2cbf2"
)
C_R08_AMENDMENT_SHA256 = (
    "047576621781aa294b8251be433b9dba7c2efd66ffe759e633d67f26960d9a65"
)


class AmendmentBoundaryError(ValueError):
    """Raised when the approved amendment bytes or document shape differ."""


def read_amendment(raw: bytes) -> dict[str, Any]:
    """Return the one approved amendment after exact byte and shape checks."""
    if hashlib.sha256(raw).hexdigest() != C_R08_AMENDMENT_SHA256:
        raise AmendmentBoundaryError("amendment bytes differ")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AmendmentBoundaryError(f"amendment JSON differs: {error}") from error
    if not isinstance(value, dict) or set(value) != {
        "authority",
        "boundaries",
        "failed_execution",
        "preserved",
        "rules",
        "status",
        "superseded_rules",
    }:
        raise AmendmentBoundaryError("amendment shape differs")
    document = cast(dict[str, Any], value)
    if (
        document["status"] != "approved-post-rejection-pre-rerun-amendment"
        or document["authority"].get("repair_schema_id")
        != "asw-0b5.w4-c-r08-ceiling-amendment.v1"
        or document["failed_execution"].get("generation_id")
        != "255e5b5cce2b4361bf37857ffbb386ef233bca47e9051b8f25e1689077edff06"
    ):
        raise AmendmentBoundaryError("amendment authority differs")
    return document


def read_c_r07_amendment(raw: bytes) -> dict[str, Any]:
    """Return the approved paired-closure amendment after exact byte checks."""
    if hashlib.sha256(raw).hexdigest() != C_R07_AMENDMENT_SHA256:
        raise AmendmentBoundaryError("C-R07 amendment bytes differ")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AmendmentBoundaryError(
            f"C-R07 amendment JSON differs: {error}"
        ) from error
    if not isinstance(value, dict) or set(value) != {
        "authority",
        "boundaries",
        "failed_execution",
        "preserved",
        "rules",
        "status",
        "superseded_rules",
    }:
        raise AmendmentBoundaryError("C-R07 amendment shape differs")
    document = cast(dict[str, Any], value)
    if (
        document["status"] != "approved-pre-successor-run-amendment"
        or document["authority"].get("repair_schema_id")
        != "asw-0b5.w4-c-r07-composition-amendment.v1"
        or document["authority"].get("c_r08_amendment_sha256")
        != C_R08_AMENDMENT_SHA256
    ):
        raise AmendmentBoundaryError("C-R07 amendment authority differs")
    return document
