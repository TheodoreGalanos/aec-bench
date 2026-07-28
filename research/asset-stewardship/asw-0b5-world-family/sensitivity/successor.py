# ABOUTME: Aggregates all amended anchor evidence under the preregistered W4 check order.
# ABOUTME: Issues a content-addressed pass or rejection without changing predecessor evidence.

from __future__ import annotations

import hashlib
from typing import Any

from repairs import c_r02, control_edge_trajectory, solver_convergence
from sensitivity import (
    amendment,
    anchor,
    catalogue,
    composition,
    inputs,
    mass,
    relationships,
    trajectory,
)

RESULT_DOMAIN = b"asw-0b5.w4-composition-result.v3\0"
PREDECESSOR_RESULT_DOMAIN = b"asw-0b5.w4-composition-result.v2\0"
CHECK_ORDER = tuple(f"C-R{index:02d}" for index in range(1, 25))


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


def _predecessor_result_id(value: dict[str, Any]) -> str:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    return hashlib.sha256(
        PREDECESSOR_RESULT_DOMAIN
        + catalogue.canonical_json_bytes(payload)
    ).hexdigest()


def compose_predecessor_generation(
    *,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
) -> dict[str, Any]:
    """Compose the predecessor rules to their first ordered rejection."""
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
            "w4-input: predecessor first mass failure differs"
        )
    result: dict[str, Any] = {
        "authorities": {
            "c_r07_amendment_sha256": (
                amendment.C_R07_AMENDMENT_SHA256
            ),
            "c_r08_amendment_sha256": (
                amendment.C_R08_AMENDMENT_SHA256
            ),
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
    result["result_content_id"] = _predecessor_result_id(result)
    return result


def predecessor_composition_result_bytes(
    value: dict[str, Any],
) -> bytes:
    """Return exact predecessor W4 bytes after identity checking."""
    if value.get("result_content_id") != _predecessor_result_id(
        value
    ):
        raise inputs.SensitivityInputError(
            "w4-input: predecessor composition identity differs"
        )
    return catalogue.canonical_json_bytes(value)


def compose_generation(
    *,
    c_r02_amendment_bytes: bytes,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
    control_edge_amendment_bytes: bytes,
    probe_catalogue_bytes: bytes,
    solver_convergence_bytes: bytes,
) -> dict[str, Any]:
    """Compose every amended anchor check in the declared W4 order."""
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
    relationship_result = relationships.evaluate_relationship_checks(
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
        mass_result=mass_result,
        probe_catalogue_bytes=probe_catalogue_bytes,
        trajectory_result=trajectory_result,
    )
    if amended_hydraulics["first_failure"] != "none":
        raise inputs.SensitivityInputError(
            "w4-input: approved hydraulic amendment did not compose"
        )
    check_map = {
        **composable["checks"],
        **mass_result["checks"],
        **trajectory_result["checks"],
        **relationship_result["checks"],
    }
    if tuple(sorted(check_map)) != CHECK_ORDER:
        raise inputs.SensitivityInputError(
            "w4-input: successor check inventory differs"
        )
    first_failure = "none"
    for check_id in CHECK_ORDER:
        check = check_map[check_id]
        if check["outcome"] != "pass":
            first_failure = str(check["first_failure"])
            if first_failure == "none":
                first_failure = f"{check_id}-reject"
            break
    passed = first_failure == "none"
    result: dict[str, Any] = {
        "authorities": {
            "c_r02_amendment_sha256": c_r02.AMENDMENT_SHA256,
            "c_r07_amendment_sha256": amendment.C_R07_AMENDMENT_SHA256,
            "c_r08_amendment_sha256": amendment.C_R08_AMENDMENT_SHA256,
            "composition_repair_sha256": (
                "38ca15bf46f67ee98aa66539701bbd8fc1889c1e268d42f0f724f7942b3c2ff8"
            ),
            "control_edge_trajectory_amendment_sha256": (
                control_edge_trajectory.AMENDMENT_SHA256
            ),
            "profile_id": "AU-NSW-LH-SYN-SPS-v1",
            "probe_catalogue_sha256": catalogue.PROBE_CATALOGUE_SHA256,
            "solver_convergence_amendment_sha256": (
                solver_convergence.AMENDMENT_SHA256
            ),
            "w4_sha256": (
                "56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f"
            ),
        },
        "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "certifier_result_sha256": hashlib.sha256(
            certifier_result_bytes
        ).hexdigest(),
        "evidence": {
            "amended_hydraulics": _canonical_evidence(
                amended_hydraulics
            ),
            "composable_anchor_checks": _canonical_evidence(
                composable
            ),
            "mass": _canonical_evidence(mass_result),
            "relationships": _canonical_evidence(
                relationship_result
            ),
            "trajectory": _canonical_evidence(
                trajectory_result
            ),
        },
        "evaluation_scope": "complete-anchor-c-r01-through-c-r24",
        "first_failure": first_failure,
        "promotable": False,
        "result_content_id": "",
        "schema_id": "asw-0b5.w4-composition-result.v3",
        "terminal_state": (
            "w4-checks-pass" if passed else "w4-checks-reject"
        ),
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
