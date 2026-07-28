# ABOUTME: Implements the approved C-R02 pinned-SWMM routing correction.
# ABOUTME: Reads exact authority bytes and exposes no generation or promotion behavior.

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, cast

AMENDMENT_SHA256 = (
    "9bafd0f955885d1b74893a1785f4607d3f6bbb099c6881cec0f420579883fc19"
)


class C_R02RepairError(ValueError):
    """Raised when the staged repair authority or inputs differ."""


def read_amendment(raw: bytes) -> dict[str, Any]:
    """Return the approved pinned-routing amendment after exact byte checks."""
    if hashlib.sha256(raw).hexdigest() != AMENDMENT_SHA256:
        raise C_R02RepairError("C-R02 amendment bytes differ")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise C_R02RepairError(
            f"C-R02 amendment JSON differs: {error}"
        ) from error
    if not isinstance(value, dict) or set(value) != {
        "authority",
        "boundaries",
        "failed_execution",
        "preserved",
        "rules",
        "source_evidence",
        "status",
        "superseded_rules",
    }:
        raise C_R02RepairError("C-R02 amendment shape differs")
    document = cast(dict[str, Any], value)
    if (
        document["status"] != "approved-pre-successor-run-amendment"
        or document["authority"].get("repair_schema_id")
        != "asw-0b5.w4-c-r02-routing-integration-amendment.v1"
        or document["authority"].get("engine_commit")
        != "7952ca837988b1c32f791812eccc9fd64547e093"
        or document["failed_execution"].get("generation_id")
        != "e31e64bd8f696dcb8edaa5bd2ad76f7286223094703f4181c6a203c03c49b2d0"
        or document["boundaries"].get(
            "candidate_numerical_values_allowed_in_correction"
        )
        is not False
    ):
        raise C_R02RepairError("C-R02 amendment authority differs")
    return document


def trapezoidal_right_end_defect(
    *,
    previous_net_flow_m3_s: float,
    current_net_flow_m3_s: float,
    interval_s: float,
) -> float:
    """Return SWMM's trapezoidal mass increment minus a right-end increment."""
    values = (
        previous_net_flow_m3_s,
        current_net_flow_m3_s,
        interval_s,
    )
    if any(not math.isfinite(value) for value in values):
        raise C_R02RepairError("routing-defect inputs must be finite")
    if interval_s <= 0.0:
        raise C_R02RepairError(
            "routing-defect interval must be positive"
        )
    return (
        0.5
        * interval_s
        * (previous_net_flow_m3_s - current_net_flow_m3_s)
    )
