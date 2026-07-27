# ABOUTME: Builds deterministic B5-W0 test declarations and receipt envelopes from explicit authority identities.
# ABOUTME: Keeps test-data construction outside both independent reader implementations.

from __future__ import annotations

import hashlib
import json
from typing import Any

PROFILE_ID = "AU-NSW-LH-SYN-SPS-v1"

AUTHORITY_HASHES = (
    (
        "profile",
        "1956883951dd70ce52ec89f4c24ed69e5aaa4617796b803668e44002eafed954",
    ),
    (
        "w1",
        "337aeab9465a8a1801b67c2ab0b408a2a2f07becddffc4a02161b64e6a8630de",
    ),
    (
        "w2",
        "66e96610b19920f93ddfa613a1f42e5d9bec6a4eb704905f82ce7b301961d130",
    ),
    (
        "w3",
        "2b0b13a6f9facaf2f0e18f19a5d41069d8e5708a2df77b6dc6d6ed6c9ec65cde",
    ),
    (
        "w4",
        "56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f",
    ),
    (
        "w2-w4-repair",
        "862ef1f5fc70d882d156c0ef9842bb565301344725d2206edfa49c10910576ca",
    ),
    (
        "w5",
        "82adf876f18fe51d9f9cc7dfcb0ef02d15c2500993385fffe56974330cf5f3d3",
    ),
)

CASE_IDS = (
    "G00_ZERO_STATIC",
    "G10_CLEAN_A_BASE",
    "G11_CLEAN_B_BASE",
    "G12_CLEAN_ASSESS",
    "G20_OBSTRUCTION_HALF",
    "G21_OBSTRUCTION_TRIGGER",
    "G22_OBSTRUCTION_UPPER",
    "G30_CLEARANCE_HALF",
    "G31_CLEARANCE_UPPER",
    "G40_COMBINED_HALF",
    "G41_COMBINED_UPPER",
    "G50_CLEAR_A_PRE",
    "G51_CLEAR_A_POST",
    "G52_CLEAR_B_PRE",
    "G53_CLEAR_B_POST",
    "G60_REPAIR_PRE",
    "G61_REPAIR_POST",
    "G70_TRANSFER",
    "G80_NO_MAINTENANCE",
)

RECEIPT_KINDS = (
    "generation-declaration",
    "engine-build",
    "generator-case",
    "certifier-case",
    "w4-case",
    "sensitivity-member",
    "family-decision",
    "gate-decision",
    "rights-review",
    "visibility-review",
    "package-conformance",
    "absence-proof",
    "promotion-decision",
)


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def generation_declaration() -> dict[str, Any]:
    return {
        "authorities": [{"role": role, "sha256": sha256} for role, sha256 in AUTHORITY_HASHES],
        "cases": [{"case_id": case_id, "content_id": digest(case_id)} for case_id in CASE_IDS],
        "certifier": {
            "dependency_inventory_id": digest("certifier-dependencies"),
            "environment_id": digest("certifier-environment"),
            "source_inventory_id": digest("certifier-source"),
        },
        "engine": {
            "commit": "7952ca837988b1c32f791812eccc9fd64547e093",
            "configuration_id": digest("engine-configuration"),
            "patch_sha256": ("522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894"),
            "repository": "https://github.com/USEPA/Stormwater-Management-Model.git",
            "version": "5.2.4",
        },
        "generator": {
            "configuration_id": digest("generator-configuration"),
            "dependency_inventory_id": digest("generator-dependencies"),
            "source_inventory_id": digest("generator-source"),
        },
        "manifest_specification_id": ("asw-0b5.promotion-manifest-specification.v1"),
        "member_content_id": digest("anchor-member"),
        "package_profile_id": "asw-au-nsw-lh-syn-sps.package.v1",
        "profile_id": PROFILE_ID,
        "receipt_profile": {
            "identity": "asw-0b5.research-receipts.v1",
            "kinds": list(RECEIPT_KINDS),
        },
        "replay_policy": {
            "ordinals": [0, 1],
            "workspace_policy": "fresh-absent-root",
        },
        "schema_id": "asw-0b5.generation-declaration.v1",
        "w4_probe_catalogue_content_id": digest("w4-probe-catalogue"),
    }


def receipt_envelope(
    *,
    generation_id: str,
    kind: str = "generation-declaration",
    parents: tuple[str, ...] = (),
    profile_id: str = PROFILE_ID,
) -> dict[str, Any]:
    return {
        "authorities": [{"role": role, "sha256": sha256} for role, sha256 in AUTHORITY_HASHES],
        "first_failure": {"code": "none", "owner": "none"},
        "generation_id": generation_id,
        "inputs": [{"content_id": generation_id, "role": "generation"}],
        "outputs": [],
        "parent_receipt_ids": list(parents),
        "profile_id": profile_id,
        "promotable": False,
        "receipt_kind": kind,
        "receipt_version": "asw-0b5.research-receipt.v1",
        "terminal_state": "attempt-frozen",
        "visibility": "certification-private",
    }
