# ABOUTME: Builds the complete W4 analytical inventory and freezes one family decision.
# ABOUTME: Retains planned probes while enforcing any ordered anchor rejection.

from __future__ import annotations

import hashlib
import re
from typing import Any

from sensitivity import catalogue, members

INVENTORY_DOMAIN = b"asw-0b5.w4-analytical-inventory.v1\0"
FAMILY_RESULT_DOMAIN = b"asw-0b5.family-decision.v1\0"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class FamilyDecisionError(ValueError):
    """Raised when a family result cannot be frozen without weakening W4."""


def _identity(
    domain: bytes,
    value: dict[str, Any],
    identity_field: str,
) -> str:
    payload = {key: child for key, child in value.items() if key != identity_field}
    return hashlib.sha256(domain + catalogue.canonical_json_bytes(payload)).hexdigest()


def build_analytical_inventory(
    *,
    authority_bytes: bytes,
    probe_catalogue_bytes: bytes,
) -> dict[str, Any]:
    """Build every pre-engine W4 role from exact reviewed declarations."""
    authority = members.read_w1_authority(authority_bytes)
    probes = catalogue.read_probe_catalogue(probe_catalogue_bytes)
    value: dict[str, Any] = {
        "boundaries": probes["boundaries"],
        "content_id": "",
        "engine_case_ids": probes["engine_case_ids"],
        "engine_variants": probes["engine_variants"],
        "grid_cardinalities": {name: len(items) for name, items in probes["grids"].items()},
        "interactions": members.build_interaction_results(
            authority,
            probes,
        ),
        "mutation_ids": probes["mutation_ids"],
        "oat": members.build_oat_results(authority, probes),
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "replay_ordinals": probes["replay_ordinals"],
        "schema_id": "asw-0b5.w4-analytical-inventory.v1",
        "terminal_state": "pre-engine-inventory-frozen",
    }
    value["content_id"] = _identity(
        INVENTORY_DOMAIN,
        value,
        "content_id",
    )
    return value


def analytical_inventory_bytes(value: dict[str, Any]) -> bytes:
    """Return exact inventory bytes after independently recomputing identity."""
    if value.get("content_id") != _identity(
        INVENTORY_DOMAIN,
        value,
        "content_id",
    ):
        raise FamilyDecisionError("analytical inventory identity differs")
    return catalogue.canonical_json_bytes(value)


def freeze_family_decision(
    *,
    analytical_inventory: dict[str, Any],
    composition_result_content_id: str,
    composition_terminal_state: str,
    composition_first_failure: str,
) -> dict[str, Any]:
    """Freeze the W4 family rejection caused by the anchor's first failure."""
    analytical_inventory_bytes(analytical_inventory)
    if not isinstance(composition_result_content_id, str) or SHA256.fullmatch(composition_result_content_id) is None:
        raise FamilyDecisionError("composition content identity differs")
    if composition_terminal_state not in {
        "w4-budget-reject",
        "w4-numerical-reject",
    }:
        raise FamilyDecisionError("family rejection requires an anchor rejection")
    if composition_first_failure not in {
        "C-R02-corrected-residual",
        "C-R08-derived-budget-lower-bound-exceeds-relative-ceiling",
    }:
        raise FamilyDecisionError("anchor rejection reason differs")
    family_failure = (
        "anchor-w4-budget-reject"
        if composition_terminal_state == "w4-budget-reject"
        else "anchor-w4-numerical-reject"
    )
    value: dict[str, Any] = {
        "analytical_inventory_content_id": analytical_inventory["content_id"],
        "composition_result_content_id": composition_result_content_id,
        "coverage": {
            "boundary_probe_count": len(analytical_inventory["boundaries"]),
            "engine_variant_count": len(analytical_inventory["engine_variants"]),
            "interaction_probe_count": len(analytical_inventory["interactions"]),
            "mutation_count": len(analytical_inventory["mutation_ids"]),
            "oat_probe_count": len(analytical_inventory["oat"]),
        },
        "execution": {
            "anchor": composition_terminal_state,
            "downstream": "not-executed-after-anchor-rejection",
            "ordered_stop_owner": composition_first_failure,
        },
        "first_failure": family_failure,
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "result_content_id": "",
        "schema_id": "asw-0b5.family-decision.v1",
        "terminal_state": "family-member-reject",
    }
    value["result_content_id"] = _identity(
        FAMILY_RESULT_DOMAIN,
        value,
        "result_content_id",
    )
    return value


def family_result_bytes(value: dict[str, Any]) -> bytes:
    """Return exact family-result bytes after recomputing its identity."""
    if value.get("result_content_id") != _identity(
        FAMILY_RESULT_DOMAIN,
        value,
        "result_content_id",
    ):
        raise FamilyDecisionError("family result identity differs")
    return catalogue.canonical_json_bytes(value)
