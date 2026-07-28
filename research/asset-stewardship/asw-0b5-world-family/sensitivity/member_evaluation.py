# ABOUTME: Evaluates one fixed family member against every applicable physical check.
# ABOUTME: Keeps partial case maps explicit and never treats one member pass as family acceptance.

from __future__ import annotations

import hashlib
from typing import Any

from sensitivity import (
    anchor,
    catalogue,
    composition,
    inputs,
    mass,
    relationships,
    trajectory,
)

RESULT_DOMAIN = b"asw-0b5.fixed-member-evaluation.v1\0"


def _canonical_evidence(value: object) -> object:
    if value is None:
        return "none"
    if isinstance(value, float):
        return composition._text(value)
    if isinstance(value, dict):
        return {
            key: _canonical_evidence(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_canonical_evidence(child) for child in value]
    return value


def _result_id(value: dict[str, Any]) -> str:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    return hashlib.sha256(
        RESULT_DOMAIN + catalogue.canonical_json_bytes(payload)
    ).hexdigest()


def _merge_checks(
    *collections: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for collection in collections:
        for check_id, check in collection.items():
            if check_id in merged:
                raise inputs.SensitivityInputError(
                    f"w4-input: duplicate member check {check_id}"
                )
            merged[check_id] = check
    return {
        check_id: merged[check_id]
        for check_id in sorted(merged)
    }


def evaluate_member(
    *,
    c_r02_amendment_bytes: bytes,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
    control_edge_amendment_bytes: bytes,
    probe_catalogue_bytes: bytes,
    solver_convergence_bytes: bytes,
) -> dict[str, Any]:
    """Evaluate the exact checks supported by one declared member case map."""
    bundle = inputs.read_canonical_object(bundle_bytes)
    if (
        bundle.get("schema_id")
        != "asw-0b5.certifier-sensitivity-bundle.v1"
    ):
        raise inputs.SensitivityInputError(
            "w4-input: fixed member bundle schema differs"
        )
    segments = inputs.read_transfer_bundle(bundle_bytes)
    member_ids = {
        segment.request["member"]["member_content_id"]
        for segment in segments
    }
    if (
        len(member_ids) != 1
        or member_ids != {bundle["member_content_id"]}
    ):
        raise inputs.SensitivityInputError(
            "w4-input: fixed member identity differs"
        )
    amended_hydraulics = (
        composition.compose_amended_hydraulic_checkpoint(
            bundle_bytes=bundle_bytes,
            certifier_result_bytes=certifier_result_bytes,
        )
    )
    composable = anchor.evaluate_composable_checks(
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
    )
    mass_result = mass.evaluate_amended_mass_checks(
        amendment_bytes=c_r02_amendment_bytes,
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
        solver_convergence_bytes=solver_convergence_bytes,
    )
    trajectory_result = trajectory.evaluate_trajectory_checks(
        amendment_bytes=c_r02_amendment_bytes,
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
        control_edge_amendment_bytes=control_edge_amendment_bytes,
        solver_convergence_bytes=solver_convergence_bytes,
    )
    relationship_result = (
        relationships.evaluate_member_relationship_checks(
            bundle_bytes=bundle_bytes,
            certifier_result_bytes=certifier_result_bytes,
            mass_result=mass_result,
            probe_catalogue_bytes=probe_catalogue_bytes,
            trajectory_result=trajectory_result,
        )
    )
    checks = _merge_checks(
        composable["checks"],
        mass_result["checks"],
        trajectory_result["checks"],
        relationship_result["checks"],
    )
    first_failure = "none"
    if amended_hydraulics["first_failure"] != "none":
        first_failure = str(amended_hydraulics["first_failure"])
    else:
        for check in checks.values():
            if check["outcome"] != "pass":
                first_failure = str(check["first_failure"])
                if first_failure == "none":
                    first_failure = "member-check-reject"
                break
    result: dict[str, Any] = {
        "applied_check_ids": list(checks),
        "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "certifier_result_sha256": hashlib.sha256(
            certifier_result_bytes
        ).hexdigest(),
        "evaluation_scope": "fixed-member-applicable-checks",
        "evidence": {
            "amended_hydraulics": _canonical_evidence(
                amended_hydraulics
            ),
            "checks": _canonical_evidence(checks),
        },
        "first_failure": first_failure,
        "member_content_id": bundle["member_content_id"],
        "probe_id": bundle["probe_id"],
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "result_content_id": "",
        "schema_id": "asw-0b5.fixed-member-evaluation.v1",
        "terminal_state": (
            "w4-checks-pass"
            if first_failure == "none"
            else "w4-checks-reject"
        ),
    }
    result["result_content_id"] = _result_id(result)
    return result


def member_evaluation_bytes(value: dict[str, Any]) -> bytes:
    """Return canonical member-evaluation bytes after identity checking."""
    if value.get("result_content_id") != _result_id(value):
        raise inputs.SensitivityInputError(
            "w4-input: member evaluation identity differs"
        )
    return catalogue.canonical_json_bytes(value)
