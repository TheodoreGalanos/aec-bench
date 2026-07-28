# ABOUTME: Builds the complete W4 analytical inventory and freezes one family decision.
# ABOUTME: Retains planned probes while enforcing any ordered anchor rejection.

from __future__ import annotations

import hashlib
import re
from typing import Any

from sensitivity import catalogue, members, probes, selection_amendment

INVENTORY_DOMAIN = b"asw-0b5.w4-analytical-inventory.v1\0"
AMENDED_INVENTORY_DOMAIN = b"asw-0b5.w4-analytical-inventory.v2\0"
FAMILY_RESULT_DOMAIN = b"asw-0b5.family-decision.v1\0"
PASSING_FAMILY_RESULT_DOMAIN = b"asw-0b5.family-decision.v2\0"
ANCHOR_RESULT_DOMAIN = b"asw-0b5.w4-composition-result.v3\0"
MEMBER_RESULT_DOMAIN = b"asw-0b5.fixed-member-evaluation.v1\0"
ENGINE_RESULT_DOMAIN = b"asw-0b5.engine-variant-evaluation.v1\0"
MUTATION_RESULT_DOMAIN = (
    b"asw-0b5.mutation-catalogue-evaluation.v1\0"
)
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
    declaration = catalogue.read_probe_catalogue(probe_catalogue_bytes)
    return _build_analytical_inventory(
        authority_bytes=authority_bytes,
        declaration=declaration,
        schema_id="asw-0b5.w4-analytical-inventory.v1",
        selection_amendment_sha256=None,
    )


def build_amended_analytical_inventory(
    *,
    authority_bytes: bytes,
    probe_catalogue_bytes: bytes,
    selection_amendment_bytes: bytes,
) -> dict[str, Any]:
    """Build the exact inventory selected for the fresh family execution."""
    declaration = selection_amendment.apply(
        catalogue.read_probe_catalogue(probe_catalogue_bytes),
        selection_amendment_bytes,
    )
    return _build_analytical_inventory(
        authority_bytes=authority_bytes,
        declaration=declaration,
        schema_id="asw-0b5.w4-analytical-inventory.v2",
        selection_amendment_sha256=selection_amendment.AMENDMENT_SHA256,
    )


def _build_analytical_inventory(
    *,
    authority_bytes: bytes,
    declaration: dict[str, Any],
    schema_id: str,
    selection_amendment_sha256: str | None,
) -> dict[str, Any]:
    authority = members.read_w1_authority(authority_bytes)
    value: dict[str, Any] = {
        "boundaries": probes.evaluate_boundaries(
            authority,
            declaration["boundaries"],
        ),
        "content_id": "",
        "engine_case_ids": declaration["engine_case_ids"],
        "engine_variants": declaration["engine_variants"],
        "grid_cardinalities": {
            name: len(items)
            for name, items in declaration["grids"].items()
        },
        "grid_results": probes.evaluate_grids(
            authority,
            declaration["grids"],
        ),
        "interactions": members.build_interaction_results(
            authority,
            declaration,
        ),
        "mutation_ids": declaration["mutation_ids"],
        "oat": members.build_oat_results(authority, declaration),
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "replay_ordinals": declaration["replay_ordinals"],
        "schema_id": schema_id,
        "terminal_state": "pre-engine-inventory-frozen",
    }
    if selection_amendment_sha256 is not None:
        value["selection_amendment_sha256"] = (
            selection_amendment_sha256
        )
    value["content_id"] = _identity(
        _inventory_domain(value),
        value,
        "content_id",
    )
    return value


def analytical_inventory_bytes(value: dict[str, Any]) -> bytes:
    """Return exact inventory bytes after independently recomputing identity."""
    if value.get("content_id") != _identity(
        _inventory_domain(value),
        value,
        "content_id",
    ):
        raise FamilyDecisionError("analytical inventory identity differs")
    return catalogue.canonical_json_bytes(value)


def _inventory_domain(value: dict[str, Any]) -> bytes:
    schema_id = value.get("schema_id")
    if schema_id == "asw-0b5.w4-analytical-inventory.v1":
        return INVENTORY_DOMAIN
    if schema_id == "asw-0b5.w4-analytical-inventory.v2":
        return AMENDED_INVENTORY_DOMAIN
    raise FamilyDecisionError("analytical inventory schema differs")


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


def _require_result(
    value: dict[str, Any],
    *,
    domain: bytes,
    schema_id: str,
    terminal_state: str,
    label: str,
) -> None:
    if value.get("result_content_id") != _identity(
        domain,
        value,
        "result_content_id",
    ):
        raise FamilyDecisionError(f"{label} result identity differs")
    if (
        value.get("schema_id") != schema_id
        or value.get("terminal_state") != terminal_state
        or value.get("first_failure") != "none"
        or value.get("promotable") is not False
    ):
        raise FamilyDecisionError(f"{label} result state differs")


def freeze_passing_family_decision(
    *,
    analytical_inventory: dict[str, Any],
    anchor_result: dict[str, Any],
    member_results: dict[str, dict[str, Any]],
    engine_result: dict[str, Any],
    mutation_result: dict[str, Any],
    selection_amendment_bytes: bytes,
) -> dict[str, Any]:
    """Freeze a family pass from complete accepted and rejected evidence."""
    analytical_inventory_bytes(analytical_inventory)
    if (
        analytical_inventory.get("schema_id")
        != "asw-0b5.w4-analytical-inventory.v2"
        or analytical_inventory.get("terminal_state")
        != "pre-engine-inventory-frozen"
        or analytical_inventory.get("promotable") is not False
    ):
        raise FamilyDecisionError(
            "passing family requires the amended analytical inventory"
        )
    if (
        any(
            item.get("terminal_state") != "probe-pass"
            for role in ("oat", "boundaries", "interactions")
            for item in analytical_inventory[role]
        )
        or any(
            result.get("terminal_state") != "grid-pass"
            for result in analytical_inventory["grid_results"].values()
        )
    ):
        raise FamilyDecisionError("analytical coverage result differs")
    _require_result(
        anchor_result,
        domain=ANCHOR_RESULT_DOMAIN,
        schema_id="asw-0b5.w4-composition-result.v3",
        terminal_state="w4-checks-pass",
        label="anchor",
    )

    expected_member_ids = {
        item["probe_id"]: item["member"]["member_content_id"]
        for item in analytical_inventory["interactions"]
        if item["probe_id"]
        in {
            "INT.01.hydraulic-supporting",
            "INT.02.hydraulic-opposing",
            "INT.03.primary-dominant",
        }
    }
    if set(member_results) != set(expected_member_ids):
        raise FamilyDecisionError("member result inventory differs")
    for probe_id, member_content_id in expected_member_ids.items():
        result = member_results[probe_id]
        _require_result(
            result,
            domain=MEMBER_RESULT_DOMAIN,
            schema_id="asw-0b5.fixed-member-evaluation.v1",
            terminal_state="w4-checks-pass",
            label=probe_id,
        )
        if (
            result.get("probe_id") != probe_id
            or result.get("member_content_id") != member_content_id
        ):
            raise FamilyDecisionError(
                f"{probe_id} member authority differs"
            )

    _require_result(
        engine_result,
        domain=ENGINE_RESULT_DOMAIN,
        schema_id="asw-0b5.engine-variant-evaluation.v1",
        terminal_state="engine-variants-pass",
        label="engine",
    )
    expected_variants = [
        item["variant_id"]
        for item in analytical_inventory["engine_variants"]
    ]
    if engine_result.get("variant_ids") != expected_variants:
        raise FamilyDecisionError("engine result inventory differs")

    _require_result(
        mutation_result,
        domain=MUTATION_RESULT_DOMAIN,
        schema_id="asw-0b5.mutation-catalogue-evaluation.v1",
        terminal_state="mutation-catalogue-pass",
        label="mutation",
    )
    if (
        mutation_result.get("mutation_count")
        != len(analytical_inventory["mutation_ids"])
        or list(mutation_result.get("mutations", {}))
        != analytical_inventory["mutation_ids"]
    ):
        raise FamilyDecisionError("mutation result inventory differs")

    selection = selection_amendment.read(selection_amendment_bytes)
    retained_rejections = selection["failed_members"]
    value: dict[str, Any] = {
        "accepted_member_results": {
            probe_id: member_results[probe_id]["result_content_id"]
            for probe_id in sorted(member_results)
        },
        "analytical_inventory_content_id": analytical_inventory[
            "content_id"
        ],
        "anchor_result_content_id": anchor_result[
            "result_content_id"
        ],
        "coverage": {
            "accepted_interaction_count": len(member_results),
            "boundary_probe_count": len(
                analytical_inventory["boundaries"]
            ),
            "engine_variant_count": len(expected_variants),
            "grid_value_count": sum(
                analytical_inventory["grid_cardinalities"].values()
            ),
            "mutation_count": mutation_result["mutation_count"],
            "oat_probe_count": len(analytical_inventory["oat"]),
            "retained_predecessor_rejection_count": len(
                retained_rejections
            ),
        },
        "engine_result_content_id": engine_result["result_content_id"],
        "first_failure": "none",
        "mutation_result_content_id": mutation_result[
            "result_content_id"
        ],
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "result_content_id": "",
        "retained_predecessor_rejections": retained_rejections,
        "schema_id": "asw-0b5.family-decision.v2",
        "selection_amendment_sha256": (
            selection_amendment.AMENDMENT_SHA256
        ),
        "terminal_state": "family-w4-checks-pass",
    }
    value["result_content_id"] = _identity(
        PASSING_FAMILY_RESULT_DOMAIN,
        value,
        "result_content_id",
    )
    return value


def family_result_bytes(value: dict[str, Any]) -> bytes:
    """Return exact family-result bytes after recomputing its identity."""
    domain = (
        PASSING_FAMILY_RESULT_DOMAIN
        if value.get("schema_id") == "asw-0b5.family-decision.v2"
        else FAMILY_RESULT_DOMAIN
    )
    if value.get("result_content_id") != _identity(
        domain,
        value,
        "result_content_id",
    ):
        raise FamilyDecisionError("family result identity differs")
    return catalogue.canonical_json_bytes(value)
