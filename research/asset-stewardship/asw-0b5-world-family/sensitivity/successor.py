# ABOUTME: Aggregates amended successor W4 evidence under preregistered state precedence.
# ABOUTME: Issues a content-addressed C-R02 rejection without altering predecessor evidence.

from __future__ import annotations

import hashlib
from typing import Any

from sensitivity import (
    amendment,
    anchor,
    catalogue,
    composition,
    inputs,
    mass,
)

RESULT_DOMAIN = b"asw-0b5.w4-composition-result.v2\0"


def _result_id(value: dict[str, Any]) -> str:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    return hashlib.sha256(
        RESULT_DOMAIN + catalogue.canonical_json_bytes(payload)
    ).hexdigest()


def compose_generation(
    *,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
) -> dict[str, Any]:
    """Compose the amended generation and stop at its first ordered rejection."""
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
    mass_result = mass.evaluate_mass_checks(
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
    )
    if amended_hydraulics["first_failure"] != "none":
        raise inputs.SensitivityInputError(
            "w4-input: approved hydraulic amendment did not compose"
        )
    if composable["first_failure"] != "none":
        raise inputs.SensitivityInputError(
            "w4-input: independently composable anchor check rejected"
        )
    if mass_result["first_failure"] != "C-R02-corrected-residual":
        raise inputs.SensitivityInputError(
            "w4-input: successor first mass failure differs"
        )
    result: dict[str, Any] = {
        "authorities": {
            "c_r07_amendment_sha256": amendment.C_R07_AMENDMENT_SHA256,
            "c_r08_amendment_sha256": amendment.C_R08_AMENDMENT_SHA256,
            "composition_repair_sha256": (
                "38ca15bf46f67ee98aa66539701bbd8fc1889c1e268d42f0f724f7942b3c2ff8"
            ),
            "profile_id": "AU-NSW-LH-SYN-SPS-v1",
            "w4_sha256": (
                "56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f"
            ),
        },
        "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "certifier_result_sha256": hashlib.sha256(
            certifier_result_bytes
        ).hexdigest(),
        "evidence": {
            "amended_hydraulics": amended_hydraulics,
            "composable_anchor_checks": composable,
            "mass": mass_result,
        },
        "evaluation_scope": (
            "complete-anchor-through-first-ordered-c-r02-rejection"
        ),
        "first_failure": "C-R02-corrected-residual",
        "promotable": False,
        "result_content_id": "",
        "schema_id": "asw-0b5.w4-composition-result.v2",
        "terminal_state": "w4-numerical-reject",
    }
    result["result_content_id"] = _result_id(result)
    return result


def composition_result_bytes(value: dict[str, Any]) -> bytes:
    """Return exact successor W4 bytes after recomputing their identity."""
    if value.get("result_content_id") != _result_id(value):
        raise inputs.SensitivityInputError(
            "w4-input: successor composition identity differs"
        )
    return catalogue.canonical_json_bytes(value)
