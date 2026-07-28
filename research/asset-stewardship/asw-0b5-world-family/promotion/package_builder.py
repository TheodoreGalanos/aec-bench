# ABOUTME: Builds the exact four-file certified reference package from approved research evidence.
# ABOUTME: Promotes only one public profile, one physical member, compact checks, and one manifest.

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from promotion import package_gate, reviews

PROFILE_ID = "AU-NSW-LH-SYN-SPS-v1"
PAYLOAD_DOMAIN = b"asw-0b5.promoted-payload.v1\0"
PACKAGE_DOMAIN = b"asw-0b5.promoted-package.v1\0"
MANIFEST_DOMAIN = b"asw-0b5.promotion-manifest.v1\0"
MEMBER_DOMAIN = b"asw-0b4.member.v1\0"
FIELD_DOMAIN = b"asw-0b5.promoted-field.v1\0"
GATE_DOMAIN = b"asw-0b5.gate-review.v1\0"
ANCHOR_DOMAIN = b"asw-0b5.w4-composition-result.v3\0"
CERTIFIER_DOMAIN = b"asw-0b5.certifier-result.v1\0"
W1_DECLARATION_SHA256 = (
    "4470e8af16bb6238a11045847199ffad95f1a7f57f64e85978a009bdda30ded9"
)
LICENSE_SHA256 = (
    "a5e57c0e89c4ca0b40ae583b3ac895847abc28515323cbe6bc8f639d20af76c4"
)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PAYLOAD_PATHS = {
    "physical-member": "physical-member.json",
    "physical-reference-checks": "physical-reference-checks.json",
    "public-profile": "public-profile.json",
}
ROLE_VISIBILITY = {
    "physical-member": "host-private",
    "physical-reference-checks": "host-private",
    "public-profile": "public",
}
ROLE_SCHEMAS = {
    "physical-member": "asw-0b5.physical-member.v1",
    "physical-reference-checks": (
        "asw-0b5.physical-reference-checks.v1"
    ),
    "public-profile": "asw-0b5.public-profile.v1",
}
PERMITTED_CLAIMS = tuple(f"CL-{index:03d}" for index in range(1, 11))
PROHIBITED_CLAIMS = (
    "PCL-REAL-ASSET",
    "PCL-UTILITY-REPRESENTATION",
    "PCL-COMPLIANCE",
    "PCL-OPERATIONAL-RECOMMENDATION",
    "PCL-OBSERVED-FAILURE-RATE",
    "PCL-DIGITAL-TWIN",
    "PCL-FIELD-CALIBRATION",
    "PCL-GENERAL-RELIABILITY",
    "PCL-POPULATION-GENERALISATION",
    "PCL-STUDY-OUTCOME",
)


class PackageBuildError(ValueError):
    """Raised before or during exact certified package construction."""


@dataclass(frozen=True)
class BuiltPackage:
    """Names one immutable package root and its two content identities."""

    manifest_content_id: str
    package_content_id: str
    rights_review: dict[str, Any]
    root: Path
    visibility_review: dict[str, Any]


def _canonical(value: object) -> bytes:
    def check(child: object) -> None:
        if child is None or isinstance(child, float):
            raise PackageBuildError(
                "package values cannot contain null or floating-point JSON"
            )
        if isinstance(child, dict):
            for key, nested in child.items():
                if not isinstance(key, str):
                    raise PackageBuildError(
                        "package object key is not text"
                    )
                check(nested)
        elif isinstance(child, list):
            for nested in child:
                check(nested)
        elif not isinstance(child, str | int | bool):
            raise PackageBuildError(
                "package contains an unsupported value"
            )

    check(value)
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _content_id(
    domain: bytes,
    value: dict[str, Any],
    identity_field: str,
) -> str:
    payload = {
        key: child
        for key, child in value.items()
        if key != identity_field
    }
    return hashlib.sha256(domain + _canonical(payload)).hexdigest()


def _read_authority(raw: bytes) -> dict[str, Any]:
    if hashlib.sha256(raw).hexdigest() != W1_DECLARATION_SHA256:
        raise PackageBuildError("W1 authority identity differs")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageBuildError(str(error)) from error
    if not isinstance(value, dict) or _canonical(value) != raw:
        raise PackageBuildError("W1 authority is not canonical")
    return value


def _member(authority: dict[str, Any]) -> dict[str, Any]:
    member: dict[str, Any] = {
        "composites": authority["composites"],
        "member_content_id": "",
        "parameters": [
            {
                "identity": parameter["identity"],
                "unit": parameter["unit"],
                "value": parameter["anchor"],
            }
            for parameter in authority["parameters"]
        ],
    }
    member["member_content_id"] = _content_id(
        MEMBER_DOMAIN,
        member,
        "member_content_id",
    )
    return member


def _payload_content_id(role: str, raw: bytes) -> str:
    return hashlib.sha256(
        PAYLOAD_DOMAIN
        + role.encode("ascii")
        + b"\0"
        + raw
    ).hexdigest()


def _gate_review_id(value: dict[str, Any]) -> str:
    return _content_id(GATE_DOMAIN, value, "result_content_id")


def _validate_gate_review(value: dict[str, Any]) -> None:
    if (
        value.get("result_content_id") != _gate_review_id(value)
        or value.get("schema_id") != "asw-0b5.gate-review.v1"
        or value.get("terminal_state") != "gate-review-pass"
        or value.get("first_failure") != "none"
        or value.get("promotable") is not False
        or value.get("validity")
        != {
            "v0": "pass",
            "v1": "pass",
            "v2": "pass",
            "v3": "pass",
            "v4": "unclaimed",
        }
        or [
            row.get("criterion_id") for row in value.get("gates", [])
        ]
        != [f"AG-{index:02d}" for index in range(1, 14)]
        or any(
            row.get("outcome") != "pass"
            or not row.get("evidence_ids")
            for row in value.get("gates", [])
        )
    ):
        raise PackageBuildError("gate review does not authorize a package")


def _check(
    anchor_result: dict[str, Any],
    area: str,
    check_id: str,
) -> dict[str, Any]:
    try:
        value = anchor_result["evidence"][area]["checks"][check_id]
    except (KeyError, TypeError) as error:
        raise PackageBuildError(
            f"compact reference {check_id} is absent"
        ) from error
    if (
        not isinstance(value, dict)
        or value.get("outcome") != "pass"
        or value.get("first_failure") != "none"
    ):
        raise PackageBuildError(
            f"compact reference {check_id} did not pass"
        )
    return value


def build_compact_reference_checks(
    *,
    anchor_result: dict[str, Any],
    certifier_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Select nine compact falsification roles from certified evidence."""
    if (
        anchor_result.get("result_content_id")
        != _content_id(
            ANCHOR_DOMAIN,
            anchor_result,
            "result_content_id",
        )
        or anchor_result.get("schema_id")
        != "asw-0b5.w4-composition-result.v3"
        or anchor_result.get("terminal_state") != "w4-checks-pass"
    ):
        raise PackageBuildError("anchor reference authority differs")
    if (
        certifier_result.get("result_content_id")
        != _content_id(
            CERTIFIER_DOMAIN,
            certifier_result,
            "result_content_id",
        )
        or certifier_result.get("schema_id")
        != "asw-0b5.certifier-result.v1"
        or certifier_result.get("terminal_state")
        != "quantitative-pending-w4"
    ):
        raise PackageBuildError("certifier reference authority differs")
    cases = {
        case.get("case_id"): case
        for case in certifier_result.get("cases", [])
        if isinstance(case, dict)
    }

    def state_ids(*case_ids: str) -> list[str]:
        try:
            identities = [
                cases[case_id]["case_content_id"]
                for case_id in case_ids
            ]
        except (KeyError, TypeError) as error:
            raise PackageBuildError(
                "compact reference case is absent"
            ) from error
        if any(
            not isinstance(identity, str)
            or SHA256.fullmatch(identity) is None
            for identity in identities
        ):
            raise PackageBuildError(
                "compact reference case identity differs"
            )
        return identities

    def capability(case_id: str, field: str) -> str:
        try:
            value = cases[case_id]["segments"][0]["capability"][field]
        except (KeyError, IndexError, TypeError) as error:
            raise PackageBuildError(
                "compact capability reference is absent"
            ) from error
        if not isinstance(value, str):
            raise PackageBuildError(
                "compact capability reference differs"
            )
        return value

    zero = _check(
        anchor_result,
        "composable_anchor_checks",
        "C-R13",
    )
    label = _check(anchor_result, "relationships", "C-R15")
    transfer = _check(anchor_result, "relationships", "C-R16")
    boundary = _check(anchor_result, "relationships", "C-R18")
    intervention = _check(anchor_result, "relationships", "C-R19")
    _check(anchor_result, "relationships", "C-R20")
    ambiguity = _check(anchor_result, "relationships", "C-R21")
    no_maintenance = _check(
        anchor_result,
        "relationships",
        "C-R22",
    )
    w3_id = certifier_result["result_content_id"]
    w4_id = anchor_result["result_content_id"]
    common = {
        "w3_result_content_id": w3_id,
        "w4_result_content_id": w4_id,
    }
    values: list[dict[str, Any]] = [
        {
            **common,
            "check_id": "C-R20/C-R21",
            "expected": {
                "classification": "pass",
                "finite_scalar": ambiguity["minimum_excess_m3_s"],
                "unit": "m³/s",
            },
            "input_state_ids": state_ids(
                "G40_COMBINED_HALF",
                "G41_COMBINED_UPPER",
            ),
            "reference_id": "reference-ambiguity",
            "role": "ambiguity",
            "rule_ids": [
                "asw-0b4.rule.observation-quantization.v1"
            ],
        },
        {
            **common,
            "check_id": "C-R18",
            "expected": {
                "classification": "pass",
                "finite_scalar": str(
                    boundary["boundary_fragile_count"]
                ),
                "unit": "1",
            },
            "input_state_ids": state_ids(
                "G21_OBSTRUCTION_TRIGGER",
                "G41_COMBINED_UPPER",
            ),
            "reference_id": "reference-boundary",
            "role": "boundary",
            "rule_ids": [
                "asw-0b4.rule.capability-predicate.v1"
            ],
        },
        {
            **common,
            "check_id": "C-R18",
            "expected": {
                "classification": "pass",
                "finite_scalar": capability(
                    "G12_CLEAN_ASSESS",
                    "operating_flow_m3_s",
                ),
                "unit": "m³/s",
            },
            "input_state_ids": state_ids("G12_CLEAN_ASSESS"),
            "reference_id": "reference-clean",
            "role": "clean",
            "rule_ids": [
                "asw-0b4.rule.capability-predicate.v1"
            ],
        },
        {
            **common,
            "check_id": "C-R18",
            "expected": {
                "classification": "pass",
                "finite_scalar": capability(
                    "G21_OBSTRUCTION_TRIGGER",
                    "drawdown_s",
                ),
                "unit": "s",
            },
            "input_state_ids": state_ids(
                "G21_OBSTRUCTION_TRIGGER"
            ),
            "reference_id": "reference-degraded",
            "role": "degraded",
            "rule_ids": [
                "asw-0b4.rule.combined-pump-curve.v1",
                "asw-0b4.rule.capability-predicate.v1",
            ],
        },
        {
            **common,
            "check_id": "C-R19",
            "expected": {
                "classification": "pass",
                "finite_scalar": intervention[
                    "minimum_excess_m3_s"
                ],
                "unit": "m³/s",
            },
            "input_state_ids": state_ids(
                "G50_CLEAR_A_PRE",
                "G51_CLEAR_A_POST",
                "G60_REPAIR_PRE",
                "G61_REPAIR_POST",
            ),
            "reference_id": "reference-intervention",
            "role": "intervention",
            "rule_ids": [
                "asw-0b4.rule.obstruction-clearing.v1",
                "asw-0b4.rule.clearance-repair.v1",
            ],
        },
        {
            **common,
            "check_id": "C-R15",
            "expected": {
                "classification": "pass",
                "finite_scalar": str(label["compared_series"]),
                "unit": "1",
            },
            "input_state_ids": state_ids(
                "G10_CLEAN_A_BASE",
                "G11_CLEAN_B_BASE",
            ),
            "reference_id": "reference-label-symmetry",
            "role": "label-symmetry",
            "rule_ids": [
                "asw-0b4.rule.combined-pump-curve.v1"
            ],
        },
        {
            **common,
            "check_id": "C-R22",
            "expected": {
                "classification": "pass",
                "classification_sequence": no_maintenance[
                    "classification_sequence"
                ],
                "finite_scalar": no_maintenance["flow_loss_m3_s"],
                "unit": "m³/s",
            },
            "input_state_ids": state_ids("G80_NO_MAINTENANCE"),
            "reference_id": "reference-no-maintenance",
            "role": "no-maintenance",
            "rule_ids": [
                "asw-0b4.rule.obstruction-progression.v1",
                "asw-0b4.rule.clearance-progression.v1",
            ],
        },
        {
            **common,
            "check_id": "C-R16/C-R17",
            "expected": {
                "classification": "pass",
                "content_hash": transfer["carry_sha256"],
                "finite_scalar": "0",
                "unit": "1",
            },
            "input_state_ids": state_ids("G70_TRANSFER"),
            "reference_id": "reference-transfer",
            "role": "transfer",
            "rule_ids": ["asw-0b4.rule.transfer.v1"],
        },
        {
            **common,
            "check_id": "C-R13",
            "expected": {
                "classification": "pass",
                "finite_scalar": zero["maximum_ratio"],
                "unit": "1",
            },
            "input_state_ids": state_ids("G00_ZERO_STATIC"),
            "reference_id": "reference-zero-flow",
            "role": "zero-flow",
            "rule_ids": [
                "asw-0b4.rule.wet-well-balance.v1"
            ],
        },
    ]
    _validate_references(values)
    return values


def _validate_references(
    values: list[dict[str, Any]],
) -> None:
    expected_roles = {
        "ambiguity",
        "boundary",
        "clean",
        "degraded",
        "intervention",
        "label-symmetry",
        "no-maintenance",
        "transfer",
        "zero-flow",
    }
    if (
        len(values) != len(expected_roles)
        or {value.get("role") for value in values} != expected_roles
    ):
        raise PackageBuildError("compact reference inventory differs")
    for value in values:
        if (
            set(value)
            != {
                "check_id",
                "expected",
                "input_state_ids",
                "reference_id",
                "role",
                "rule_ids",
                "w3_result_content_id",
                "w4_result_content_id",
            }
            or not isinstance(value["reference_id"], str)
            or not value["reference_id"]
            or not isinstance(value["check_id"], str)
            or not value["check_id"].startswith("C-R")
            or not value["input_state_ids"]
            or any(
                SHA256.fullmatch(identity) is None
                for identity in value["input_state_ids"]
            )
            or SHA256.fullmatch(value["w3_result_content_id"]) is None
            or SHA256.fullmatch(value["w4_result_content_id"]) is None
        ):
            raise PackageBuildError("compact reference shape differs")


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _leaves(
    value: object,
    pointer: str = "",
) -> list[tuple[str, object]]:
    if isinstance(value, dict):
        return [
            item
            for key, child in value.items()
            for item in _leaves(
                child,
                pointer + "/" + _escape_pointer(key),
            )
        ]
    if isinstance(value, list):
        return [
            item
            for index, child in enumerate(value)
            for item in _leaves(child, pointer + f"/{index}")
        ]
    return [(pointer, value)]


def _quantity(
    *,
    payload: dict[str, Any],
    pointer: str,
    role: str,
) -> dict[str, str]:
    parts = pointer.strip("/").split("/")
    if (
        role == "physical-member"
        and len(parts) == 3
        and parts[0] == "parameters"
        and parts[2] == "value"
    ):
        parameter = payload["parameters"][int(parts[1])]
        return {
            "classification": "physical-quantity",
            "identity": parameter["identity"],
            "unit": parameter["unit"],
        }
    if (
        role == "physical-reference-checks"
        and len(parts) == 4
        and parts[0] == "checks"
        and parts[2] == "expected"
        and parts[3] == "finite_scalar"
    ):
        check = payload["checks"][int(parts[1])]
        return {
            "classification": "reference-scalar",
            "identity": check["reference_id"],
            "unit": check["expected"]["unit"],
        }
    return {
        "classification": "non-numeric",
        "identity": "not-applicable",
        "unit": "none",
    }


def _field_rows(
    payloads: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in sorted(payloads):
        for pointer, _value in _leaves(payloads[role]):
            field_id = hashlib.sha256(
                FIELD_DOMAIN
                + role.encode("ascii")
                + b"\0"
                + pointer.encode("utf-8")
            ).hexdigest()
            rows.append(
                {
                    "assumption_link_set_id": (
                        "original-synthetic-assumptions"
                    ),
                    "certification_link_set_id": (
                        "independent-certification"
                    ),
                    "claim_id": (
                        "CL-005"
                        if role != "public-profile"
                        else "CL-001"
                    ),
                    "evidence_link_set_id": (
                        "accepted-evidence-classes"
                    ),
                    "field_semantic_id": field_id,
                    "generation_link_set_id": (
                        "accepted-world-generation"
                    ),
                    "json_pointer": pointer,
                    "later_consumer": (
                        "ASW-2A0"
                        if role == "public-profile"
                        else "ASW-2A1"
                    ),
                    "quantity": _quantity(
                        payload=payloads[role],
                        pointer=pointer,
                        role=role,
                    ),
                    "rights_decision_id": (
                        "repository-original-redistributable"
                    ),
                    "semantic_role": role,
                    "sensitivity_link_set_id": (
                        "accepted-family-sensitivity"
                    ),
                    "source_link_set_id": "accepted-source-register",
                    "transformation_link_set_id": (
                        "declared-physical-transformations"
                    ),
                    "visibility_class": ROLE_VISIBILITY[role],
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["semantic_role"],
            row["json_pointer"],
        ),
    )


def _payloads(
    *,
    authority: dict[str, Any],
    generation_id: str,
    reference_checks: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    member = _member(authority)
    asset = {
        "asset_id": "synthetic-wastewater-pump-station",
        "component_ids": ["pump-a", "pump-b"],
        "initial_duty_component_id": "pump-a",
        "initial_standby_component_id": "pump-b",
        "maximum_duty_transfers": 1,
    }
    return {
        "physical-member": {
            "asset": asset,
            "composites": member["composites"],
            "member_content_id": member["member_content_id"],
            "orderings": authority["orderings"],
            "parameters": member["parameters"],
            "profile_id": PROFILE_ID,
            "rules": authority["rules"],
            "schema_id": ROLE_SCHEMAS["physical-member"],
        },
        "physical-reference-checks": {
            "checks": sorted(
                reference_checks,
                key=lambda value: value["reference_id"],
            ),
            "generation_id": generation_id,
            "member_content_id": member["member_content_id"],
            "profile_id": PROFILE_ID,
            "schema_id": ROLE_SCHEMAS[
                "physical-reference-checks"
            ],
        },
        "public-profile": {
            "asset": asset,
            "claim_ceiling": "construct-valid-synthetic-benchmark",
            "context": {
                "country": "Australia",
                "fictional": True,
                "region": "Lower Hunter",
                "state": "New South Wales",
            },
            "generation_id": generation_id,
            "license": {
                "identifier": "MIT",
                "notice": (
                    "Copyright (c) 2026 AEC-Bench contributors"
                ),
                "sha256": LICENSE_SHA256,
            },
            "manifest_specification_id": (
                "asw-0b5.promotion-manifest-specification.v1"
            ),
            "permitted_claim_ids": list(PERMITTED_CLAIMS),
            "profile_id": PROFILE_ID,
            "prohibited_claim_ids": list(PROHIBITED_CLAIMS),
            "schema_id": ROLE_SCHEMAS["public-profile"],
        },
    }


def _link_sets(
    *,
    family_result_content_id: str,
    gate_review_content_id: str,
    generation_id: str,
) -> dict[str, list[str]]:
    return {
        "accepted-evidence-classes": ["N", "P", "S"],
        "accepted-family-sensitivity": [
            family_result_content_id,
            "OAT-68",
            "BND-11",
            "ENG-7",
            "MUT-30",
        ],
        "accepted-source-register": [
            "AUTH-001",
            "AUTH-003",
            "N-001",
            "N-002",
            "N-003",
            "N-004",
            "P-001",
            "P-002",
            "P-003",
            "P-004",
        ],
        "accepted-world-generation": [
            generation_id,
            gate_review_content_id,
        ],
        "declared-physical-transformations": [
            "W1-parameter-selection",
            "W2-semantic-transformation",
        ],
        "independent-certification": [
            "W3-independent-certification",
            "W4-tolerance-evaluation",
        ],
        "original-synthetic-assumptions": [
            "A-001",
            "A-002",
            "A-003",
            "A-004",
            "A-005",
        ],
    }


def _write_absent(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise PackageBuildError(f"package path already exists: {path.name}")
    path.write_bytes(raw)


def build_certified_reference_package(
    *,
    authority_bytes: bytes,
    family_result_bytes: bytes,
    gate_review: dict[str, Any],
    generation_id: str,
    reference_checks: list[dict[str, Any]],
    target: Path,
) -> BuiltPackage:
    """Build one immutable certified reference package in an absent root."""
    family_result = package_gate.read_passing_family(
        family_result_bytes
    )
    family_result_content_id = family_result["result_content_id"]
    if (
        SHA256.fullmatch(generation_id) is None
    ):
        raise PackageBuildError("generation identity differs")
    _validate_gate_review(gate_review)
    _validate_references(reference_checks)
    target = target.resolve()
    if target.exists() or target.is_symlink():
        raise PackageBuildError("package target must be absent")
    authority = _read_authority(authority_bytes)
    payload_values = _payloads(
        authority=authority,
        generation_id=generation_id,
        reference_checks=reference_checks,
    )
    payload_bytes = {
        PAYLOAD_PATHS[role]: _canonical(payload)
        for role, payload in payload_values.items()
    }
    field_rows = _field_rows(payload_values)
    rights = reviews.review_payload_rights(
        field_rows=field_rows,
        payloads=payload_bytes,
        repository_license_sha256=LICENSE_SHA256,
    )
    visibility = reviews.review_payload_visibility(
        field_rows=field_rows,
        role_visibility=ROLE_VISIBILITY,
    )
    if (
        rights["terminal_state"] != "rights-review-pass"
        or visibility["terminal_state"] != "visibility-review-pass"
    ):
        raise PackageBuildError("package review rejected")

    field_ids_by_role = {
        role: [
            row["field_semantic_id"]
            for row in field_rows
            if row["semantic_role"] == role
        ]
        for role in sorted(payload_values)
    }
    inventory: list[dict[str, Any]] = []
    for role, path in sorted(
        PAYLOAD_PATHS.items(),
        key=lambda item: item[1],
    ):
        raw = payload_bytes[path]
        inventory.append(
            {
                "field_semantic_ids": field_ids_by_role[role],
                "media_type": "application/json",
                "payload_content_id": _payload_content_id(role, raw),
                "relative_path": path,
                "rights_review_content_id": rights[
                    "result_content_id"
                ],
                "schema_identity": ROLE_SCHEMAS[role],
                "semantic_role": role,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "visibility_class": ROLE_VISIBILITY[role],
            }
        )
    package_content_id = hashlib.sha256(
        PACKAGE_DOMAIN + _canonical(inventory)
    ).hexdigest()
    gate_id = gate_review["result_content_id"]
    manifest: dict[str, Any] = {
        "authority": {
            "absence_checker_identity": (
                "asw-0b5.package-only-absence-check.v1"
            ),
            "family_result_content_id": family_result_content_id,
            "gate_review_content_id": gate_id,
            "manifest_specification_id": (
                "asw-0b5.promotion-manifest-specification.v1"
            ),
            "package_checker_identity": (
                "asw-0b5.package-conformance-checker.v1"
            ),
            "profile_id": PROFILE_ID,
            "rights_review_content_id": rights[
                "result_content_id"
            ],
            "visibility_review_content_id": visibility[
                "result_content_id"
            ],
            "w1_sha256": (
                "337aeab9465a8a1801b67c2ab0b408a2a2f07becddffc4a02161b64e6a8630de"
            ),
            "w2_sha256": (
                "66e96610b19920f93ddfa613a1f42e5d9bec6a4eb704905f82ce7b301961d130"
            ),
            "w3_sha256": (
                "2b0b13a6f9facaf2f0e18f19a5d41069d8e5708a2df77b6dc6d6ed6c9ec65cde"
            ),
            "w4_sha256": (
                "56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f"
            ),
            "w5_sha256": (
                "82adf876f18fe51d9f9cc7dfcb0ef02d15c2500993385fffe56974330cf5f3d3"
            ),
        },
        "claims": {
            "certified_envelope": (
                "one fictional Lower Hunter duty-standby pump station"
            ),
            "permitted": list(PERMITTED_CLAIMS),
            "prohibited": list(PROHIBITED_CLAIMS),
        },
        "compatibility": {
            "historical_runtime_bytes": "none",
            "migration": "none",
            "predecessor": "none",
            "replacement": "new-manifest-and-package-id-only",
            "supersession": "immutable",
            "unknown_fields": "reject",
            "unknown_files": "reject",
        },
        "evidence": {
            "evidence_rights_sha256": (
                "8d8e057792763531ebd3c8709f039c0aa7150a22ce734857221cef3339378e96"
            ),
            "link_sets": _link_sets(
                family_result_content_id=family_result_content_id,
                gate_review_content_id=gate_id,
                generation_id=generation_id,
            ),
            "profile_claim_sha256": (
                "1956883951dd70ce52ec89f4c24ed69e5aaa4617796b803668e44002eafed954"
            ),
        },
        "fields": field_rows,
        "generation": {
            "reference_world_generation_id": generation_id,
            "runtime_member_id": payload_values["physical-member"][
                "member_content_id"
            ],
            "v0": "pass",
            "v1": "pass",
            "v2": "pass",
            "v3": "pass",
            "v4": "unclaimed",
        },
        "package": {
            "external_dependencies": [],
            "package_content_id": package_content_id,
            "payloads": inventory,
            "root_file_count": 4,
        },
        "retirement": {
            "b3_current_tree": "retained-pending-asw-2a0",
            "b4_current_tree": "retained-pending-asw-2a0",
            "b5_current_tree": "retained-pending-asw-2a0",
        },
        "versions": {
            "manifest": "asw-0b5.promotion-manifest.v1",
            "package": "asw-au-nsw-lh-syn-sps.package.v1",
            "physical_member": ROLE_SCHEMAS["physical-member"],
            "physical_reference_checks": ROLE_SCHEMAS[
                "physical-reference-checks"
            ],
            "public_profile": ROLE_SCHEMAS["public-profile"],
        },
        "visibility": {
            "actor_visible_payloads": [],
            "certification_private_payloads": [],
            "holdout_sensitive_payloads": [],
            "host_private_payloads": [
                "physical-member",
                "physical-reference-checks",
            ],
            "public_payloads": ["public-profile"],
        },
    }
    manifest_bytes = _canonical(manifest)
    manifest_content_id = hashlib.sha256(
        MANIFEST_DOMAIN + manifest_bytes
    ).hexdigest()
    package_gate.authorize_package_root(
        family_result_bytes=family_result_bytes,
        target=target,
    )
    for path, raw in sorted(payload_bytes.items()):
        _write_absent(target / path, raw)
    _write_absent(
        target / "promotion-manifest.json",
        manifest_bytes,
    )
    return BuiltPackage(
        manifest_content_id=manifest_content_id,
        package_content_id=package_content_id,
        rights_review=rights,
        root=target,
        visibility_review=visibility,
    )
