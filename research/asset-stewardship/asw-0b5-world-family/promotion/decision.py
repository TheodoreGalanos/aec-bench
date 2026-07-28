# ABOUTME: Independently reads a W4 family result and issues one immutable W5 decision.
# ABOUTME: A rejected family yields no payload, package, manifest, gate, rights, or absence claim.

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, NoReturn, cast

FAMILY_RESULT_DOMAIN = b"asw-0b5.family-decision.v1\0"
PASSING_FAMILY_RESULT_DOMAIN = b"asw-0b5.family-decision.v2\0"
PROMOTION_DECISION_DOMAIN = b"asw-0b5.promotion-decision.v1\0"
ISSUED_DECISION_DOMAIN = b"asw-0b5.promotion-decision.v2\0"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class PromotionDecisionError(ValueError):
    """Raised when a promotion decision cannot be read or issued exactly."""


def _fail(detail: str) -> NoReturn:
    raise PromotionDecisionError(f"promotion-decision: {detail}")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            _fail(f"duplicate key {key!r}")
        value[key] = child
    return value


def _check_types(value: object) -> None:
    if value is None or isinstance(value, float):
        _fail("null and JSON floating-point values are forbidden")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("object key is not text")
            _check_types(child)
    elif isinstance(value, list):
        for child in value:
            _check_types(child)
    elif not isinstance(value, str | int | bool):
        _fail("unsupported JSON value")


def _canonical(value: object) -> bytes:
    _check_types(value)
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _parse(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
        _fail("exactly one terminal LF is required")
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(str(error))
    if not isinstance(parsed, dict):
        _fail("top-level value is not an object")
    value = cast(dict[str, Any], parsed)
    if _canonical(value) != raw:
        _fail("bytes are not canonical")
    return value


def _family_result(raw: bytes) -> dict[str, Any]:
    value = _parse(raw)
    rejection_shape = {
        "analytical_inventory_content_id",
        "composition_result_content_id",
        "coverage",
        "execution",
        "first_failure",
        "profile_id",
        "promotable",
        "result_content_id",
        "schema_id",
        "terminal_state",
    }
    passing_shape = {
        "accepted_member_results",
        "analytical_inventory_content_id",
        "anchor_result_content_id",
        "coverage",
        "engine_result_content_id",
        "first_failure",
        "mutation_result_content_id",
        "profile_id",
        "promotable",
        "result_content_id",
        "retained_predecessor_rejections",
        "schema_id",
        "selection_amendment_sha256",
        "terminal_state",
    }
    schema_id = value.get("schema_id")
    if schema_id == "asw-0b5.family-decision.v1":
        shape = rejection_shape
        domain = FAMILY_RESULT_DOMAIN
    elif schema_id == "asw-0b5.family-decision.v2":
        shape = passing_shape
        domain = PASSING_FAMILY_RESULT_DOMAIN
    else:
        _fail("family result schema differs")
    if set(value) != shape:
        _fail("family result shape differs")
    payload = {key: child for key, child in value.items() if key != "result_content_id"}
    expected = hashlib.sha256(domain + _canonical(payload)).hexdigest()
    if value["result_content_id"] != expected:
        _fail("family result identity differs")
    if (
        value["profile_id"] != "AU-NSW-LH-SYN-SPS-v1"
        or value["promotable"] is not False
    ):
        _fail("family result authority differs")
    return value


def _decision_id(value: dict[str, Any]) -> str:
    payload = {key: child for key, child in value.items() if key != "decision_content_id"}
    domain = (
        ISSUED_DECISION_DOMAIN
        if value.get("schema_id") == "asw-0b5.promotion-decision.v2"
        else PROMOTION_DECISION_DOMAIN
    )
    return hashlib.sha256(domain + _canonical(payload)).hexdigest()


def refuse_v3(family_result_bytes: bytes) -> dict[str, Any]:
    """Issue the only valid V3 outcome for a rejected W4 family."""
    family = _family_result(family_result_bytes)
    if family["terminal_state"] != "family-member-reject":
        _fail("refusal requires family-member-reject")
    value: dict[str, Any] = {
        "decision_content_id": "",
        "downstream_stages": {
            "absence_proof": "not-executed-after-generation-reject",
            "gate_review": "not-executed-after-generation-reject",
            "package_conformance": "not-executed-after-generation-reject",
            "rights_review": "not-executed-after-generation-reject",
            "visibility_review": "not-executed-after-generation-reject",
        },
        "family_result_content_id": family["result_content_id"],
        "first_failure": "family-member-reject",
        "manifest_content_ids": [],
        "package_content_ids": [],
        "payload_content_ids": [],
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "schema_id": "asw-0b5.promotion-decision.v1",
        "terminal_state": "promotion-generation-reject",
        "v3": "refused",
        "v4": "unclaimed",
    }
    value["decision_content_id"] = _decision_id(value)
    return value


def issue_certified_reference_package(
    *,
    absence_proof_content_id: str,
    family_result_bytes: bytes,
    gate_review_content_id: str,
    manifest_content_id: str,
    package_conformance_content_id: str,
    package_content_id: str,
    payload_content_ids: tuple[str, str, str],
    rights_review_content_id: str,
    visibility_review_content_id: str,
) -> dict[str, Any]:
    """Issue one immutable decision for one completely checked package."""
    family = _family_result(family_result_bytes)
    if family["terminal_state"] != "family-w4-checks-pass":
        _fail("issuance requires family-w4-checks-pass")
    evidence = {
        "absence_proof_content_id": absence_proof_content_id,
        "gate_review_content_id": gate_review_content_id,
        "package_conformance_content_id": (
            package_conformance_content_id
        ),
        "rights_review_content_id": rights_review_content_id,
        "visibility_review_content_id": (
            visibility_review_content_id
        ),
    }
    identities = [
        *evidence.values(),
        manifest_content_id,
        package_content_id,
        *payload_content_ids,
    ]
    if (
        any(
            not isinstance(identity, str)
            or SHA256.fullmatch(identity) is None
            for identity in identities
        )
        or len(set(payload_content_ids)) != 3
    ):
        _fail("issued package identity differs")
    value: dict[str, Any] = {
        "decision_content_id": "",
        "evidence": evidence,
        "family_result_content_id": family["result_content_id"],
        "first_failure": "none",
        "manifest_content_ids": [manifest_content_id],
        "package_content_ids": [package_content_id],
        "payload_content_ids": list(payload_content_ids),
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": True,
        "schema_id": "asw-0b5.promotion-decision.v2",
        "terminal_state": "promotion-v3-issued",
        "v3": "issued",
        "v4": "unclaimed",
    }
    value["decision_content_id"] = _decision_id(value)
    return value


def promotion_decision_bytes(value: dict[str, Any]) -> bytes:
    """Return immutable canonical V3-decision bytes."""
    if value.get("decision_content_id") != _decision_id(value):
        _fail("promotion decision identity differs")
    return _canonical(value)


def read_promotion_decision(raw: bytes) -> dict[str, Any]:
    """Independently reload one exact refusal or issued decision."""
    value = _parse(raw)
    if value.get("decision_content_id") != _decision_id(value):
        _fail("promotion decision identity differs")
    if value.get("schema_id") == "asw-0b5.promotion-decision.v1":
        if (
            value.get("terminal_state")
            != "promotion-generation-reject"
            or value.get("promotable") is not False
            or value.get("v3") != "refused"
            or value.get("v4") != "unclaimed"
            or any(
                value.get(field) != []
                for field in (
                    "manifest_content_ids",
                    "package_content_ids",
                    "payload_content_ids",
                )
            )
        ):
            _fail("promotion refusal shape or state differs")
        return value
    if (
        value.get("schema_id") != "asw-0b5.promotion-decision.v1"
        and value.get("schema_id")
        != "asw-0b5.promotion-decision.v2"
    ):
        _fail("promotion decision schema differs")
    if (
        value.get("terminal_state") != "promotion-v3-issued"
        or value.get("promotable") is not True
        or value.get("v3") != "issued"
        or value.get("v4") != "unclaimed"
        or len(value.get("manifest_content_ids", [])) != 1
        or len(value.get("package_content_ids", [])) != 1
        or len(value.get("payload_content_ids", [])) != 3
    ):
        _fail("issued promotion shape or state differs")
    return value
