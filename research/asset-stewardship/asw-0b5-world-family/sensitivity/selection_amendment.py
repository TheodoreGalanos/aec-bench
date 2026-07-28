# ABOUTME: Applies the approved family-member selection amendment to two interaction roles.
# ABOUTME: Preserves the predecessor catalogue and rejects unexpected probe, case-map, or selection drift.

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sensitivity import catalogue

AMENDMENT_SHA256 = (
    "594e507ee5e8e783c80137512bfb918bbc91e5a00692465be0a5c5739b2b1ba5"
)
REPLACEMENTS = {
    "INT.01.hydraulic-supporting": {
        "inflow.Q_low": "lower",
        "inflow.Q_nominal": "lower",
        "system.K_minor": "lower",
        "system.epsilon": "lower",
    },
    "INT.03.primary-dominant": {
        "mechanism.r_c_runtime": "lower",
        "mechanism.r_o_runtime": "upper",
        "mechanism.r_o_start": "upper",
    },
}
MEMBER_IDS = {
    "INT.01.hydraulic-supporting": (
        "3811f8cd17548f8c6b11b524504a9b62c49ab999099ea17e84dda7eac99484c3"
    ),
    "INT.03.primary-dominant": (
        "915c0289e22b33601647958a74040bdb52c48cd1a6d54e4c9775492513c40953"
    ),
}
PREDECESSORS = {
    "INT.01.hydraulic-supporting": {
        "inflow.Q_assess": "lower",
        "inflow.Q_low": "lower",
        "inflow.Q_nominal": "lower",
        "system.D": "upper",
        "system.K_minor": "lower",
        "system.L": "lower",
        "system.epsilon": "lower",
        "system.z_d": "lower",
        "well.D_w": "lower",
        "well.h_high": "lower",
        "well.h_overflow": "lower",
        "well.h_start": "lower",
        "well.h_stop": "upper",
    },
    "INT.03.primary-dominant": {
        "mechanism.a_c": "lower",
        "mechanism.a_o": "upper",
        "mechanism.b_c": "lower",
        "mechanism.b_o": "upper",
        "mechanism.r_c_runtime": "lower",
        "mechanism.r_o_runtime": "upper",
        "mechanism.r_o_start": "upper",
    },
}


class SelectionAmendmentError(ValueError):
    """Raised when the exact family-member amendment cannot compose."""


def read(raw: bytes) -> dict[str, Any]:
    """Read the exact approved family-member selection amendment."""
    value = catalogue._read_exact(raw, AMENDMENT_SHA256)
    if set(value) != {
        "authority",
        "failed_members",
        "forbidden",
        "replacements",
        "status",
    }:
        raise SelectionAmendmentError(
            "family-member selection amendment shape differs"
        )
    if value["authority"] != {
        "amendment_schema_id": (
            "asw-0b5.family-member-selection-amendment.v1"
        ),
        "decision_record_sha256": (
            "9bd131a3e623b6204426f07f38868a9f2cf4862392153f6b3de70f2a02386c2d"
        ),
        "family_coverage_repair_sha256": (
            catalogue.FAMILY_COVERAGE_REPAIR_SHA256
        ),
        "probe_catalogue_sha256": catalogue.PROBE_CATALOGUE_SHA256,
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "scope": "research-private",
        "w4_sha256": (
            "56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f"
        ),
    }:
        raise SelectionAmendmentError(
            "family-member selection authority differs"
        )
    expected_replacements = [
        {
            "member_content_id": MEMBER_IDS[probe_id],
            "probe_id": probe_id,
            "selections": REPLACEMENTS[probe_id],
        }
        for probe_id in REPLACEMENTS
    ]
    if (
        value["replacements"] != expected_replacements
        or value["status"]
        != "approved-before-fresh-family-execution"
    ):
        raise SelectionAmendmentError(
            "family-member replacement differs"
        )
    return value


def apply(
    probe_catalogue: dict[str, Any],
    amendment_bytes: bytes,
) -> dict[str, Any]:
    """Return a copy with only the two approved interaction replacements."""
    read(amendment_bytes)
    amended = deepcopy(probe_catalogue)
    interactions = {
        item.get("probe_id"): item
        for item in amended["interactions"]
    }
    if len(interactions) != len(amended["interactions"]):
        raise SelectionAmendmentError(
            "interaction identities are not unique"
        )
    for probe_id, replacement in REPLACEMENTS.items():
        item = interactions.get(probe_id)
        if (
            not isinstance(item, dict)
            or item.get("selections") != PREDECESSORS[probe_id]
        ):
            raise SelectionAmendmentError(
                f"predecessor selections differ for {probe_id}"
            )
        item["selections"] = dict(replacement)
    return amended
