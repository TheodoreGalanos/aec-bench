# ABOUTME: Verifies that every declared invalid input reaches its exact first rejection boundary.
# ABOUTME: Combines isolated certifier results with ordered physical checks without weakening success prerequisites.

from __future__ import annotations

import hashlib
import json
from typing import Any

from sensitivity import anchor, catalogue, mass

from adversarial import mutations

RESULT_DOMAIN = b"asw-0b5.mutation-catalogue-evaluation.v1\0"
EXPECTED_W3 = {
    "M01": ("certifier-input-reject", "bundle-role"),
    "M02": ("structural-reject", "semantic-shape"),
    "M03": ("structural-reject", "semantic-bytes"),
    "M04": ("structural-reject", "semantic-bytes"),
    "M05": ("structural-reject", "semantic-binary32"),
    "M06": ("structural-reject", "semantic-series"),
    "M07": ("structural-reject", "semantic-period"),
    "M08": ("structural-reject", "semantic-series"),
    "M09": ("structural-reject", "curve-shape"),
    "M10": ("structural-reject", "curve-endpoint"),
    "M11": ("structural-reject", "curve-order"),
    "M12": ("exact-reject", "label-curve-symmetry"),
    "M13": ("exact-reject", "observation"),
    "M14": ("exact-reject", "observation"),
    "M15": ("quantitative-pending-w4", "w4-tolerance-required"),
    "M16": ("quantitative-pending-w4", "w4-tolerance-required"),
    "M17": ("quantitative-pending-w4", "w4-tolerance-required"),
    "M19": ("exact-reject", "case"),
    "M20": ("exact-reject", "case"),
    "M21": ("exact-reject", "case"),
    "M22": ("exact-reject", "case"),
    "M23": ("exact-reject", "transfer-carry-identity"),
    "M24": ("exact-reject", "case"),
    "M25": ("exact-reject", "case"),
    "M26": ("qualitative-reject", "ambiguity-response-collapse"),
    "M27": ("qualitative-reject", "label-mirror-hydraulics"),
    "M28": ("exact-reject", "observation"),
    "M29": ("structural-reject", "semantic-maturity"),
    "M30": ("structural-reject", "semantic-shape"),
}
EXPECTED_W4 = {
    "M15": "C-R13-off-flow",
    "M16": "C-R01-storage-identity",
    "M17": "C-R02-corrected-residual",
    "M18": "C-R09-full-pipe",
}


class MutationEvaluationError(ValueError):
    """Raised when invalid-input evidence is missing or misclassified."""


def _read_result(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw)
    if (
        not isinstance(value, dict)
        or catalogue.canonical_json_bytes(value) != raw
    ):
        raise MutationEvaluationError(
            "mutation certifier result is not canonical"
        )
    return value


def _first_composable_failure(value: dict[str, Any]) -> str:
    return next(
        (
            check["first_failure"]
            for check in value["checks"].values()
            if check["outcome"] != "pass"
        ),
        "none",
    )


def _result_id(value: dict[str, Any]) -> str:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    return hashlib.sha256(
        RESULT_DOMAIN + catalogue.canonical_json_bytes(payload)
    ).hexdigest()


def evaluate(
    *,
    base_bundle_bytes: bytes,
    base_certifier_result_bytes: bytes,
    bundle_mutations: dict[str, bytes],
    certifier_results: dict[str, bytes],
    c_r02_amendment_bytes: bytes,
    solver_convergence_bytes: bytes,
) -> dict[str, Any]:
    """Verify all thirty invalid inputs against their ordered boundaries."""
    if (
        tuple(bundle_mutations) != tuple(EXPECTED_W3)
        or set(certifier_results) != set(EXPECTED_W3)
    ):
        raise MutationEvaluationError(
            "mutation bundle or certifier-result inventory differs"
        )
    outcomes: dict[str, dict[str, Any]] = {}
    first_failure = "none"
    for mutation_id, expected_state in EXPECTED_W3.items():
        result = _read_result(certifier_results[mutation_id])
        actual_state = (
            result.get("terminal_state"),
            result.get("first_failing_stage"),
        )
        if actual_state != expected_state:
            first_failure = f"{mutation_id}:unexpected-w3-rejection"
            outcomes[mutation_id] = {
                "actual_first_failure": str(actual_state[1]),
                "actual_terminal_state": str(actual_state[0]),
                "expected_first_failure": expected_state[1],
                "expected_terminal_state": expected_state[0],
                "outcome": "reject",
            }
            break
        outcomes[mutation_id] = {
            "actual_first_failure": actual_state[1],
            "actual_terminal_state": actual_state[0],
            "expected_first_failure": expected_state[1],
            "expected_terminal_state": expected_state[0],
            "outcome": "pass",
        }
    if first_failure == "none":
        for mutation_id in ("M15", "M16"):
            result = anchor.evaluate_composable_checks(
                bundle_bytes=bundle_mutations[mutation_id],
                certifier_result_bytes=certifier_results[
                    mutation_id
                ],
            )
            actual_failure = _first_composable_failure(result)
            expected_failure = EXPECTED_W4[mutation_id]
            outcomes[mutation_id][
                "physical_first_failure"
            ] = actual_failure
            if actual_failure != expected_failure:
                outcomes[mutation_id]["outcome"] = "reject"
                first_failure = (
                    f"{mutation_id}:unexpected-physical-rejection"
                )
                break
    if first_failure == "none":
        mass_result = mass.evaluate_amended_mass_checks(
            amendment_bytes=c_r02_amendment_bytes,
            bundle_bytes=bundle_mutations["M17"],
            certifier_result_bytes=certifier_results["M17"],
            solver_convergence_bytes=solver_convergence_bytes,
        )
        actual_failure = str(mass_result["first_failure"])
        outcomes["M17"][
            "physical_first_failure"
        ] = actual_failure
        if actual_failure != EXPECTED_W4["M17"]:
            outcomes["M17"]["outcome"] = "reject"
            first_failure = "M17:unexpected-physical-rejection"
    if first_failure == "none":
        result_mutation = mutations.build_result_mutations(
            base_certifier_result_bytes
        )["M18"]
        capacity = anchor.evaluate_composable_checks(
            bundle_bytes=base_bundle_bytes,
            certifier_result_bytes=result_mutation,
        )
        actual_failure = _first_composable_failure(capacity)
        outcomes["M18"] = {
            "actual_first_failure": actual_failure,
            "actual_terminal_state": capacity["terminal_state"],
            "expected_first_failure": EXPECTED_W4["M18"],
            "expected_terminal_state": (
                "composable-anchor-checks-reject"
            ),
            "mutation_target": "certifier-residual-register",
            "outcome": (
                "pass"
                if actual_failure == EXPECTED_W4["M18"]
                else "reject"
            ),
        }
        if actual_failure != EXPECTED_W4["M18"]:
            first_failure = "M18:unexpected-physical-rejection"
    ordered_outcomes = {
        mutation_id: outcomes[mutation_id]
        for mutation_id in mutations.MUTATION_IDS
        if mutation_id in outcomes
    }
    value: dict[str, Any] = {
        "base_bundle_sha256": hashlib.sha256(
            base_bundle_bytes
        ).hexdigest(),
        "first_failure": first_failure,
        "mutation_count": len(ordered_outcomes),
        "mutations": ordered_outcomes,
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "result_content_id": "",
        "schema_id": "asw-0b5.mutation-catalogue-evaluation.v1",
        "terminal_state": (
            "mutation-catalogue-pass"
            if first_failure == "none"
            and len(ordered_outcomes) == len(mutations.MUTATION_IDS)
            else "mutation-catalogue-reject"
        ),
    }
    value["result_content_id"] = _result_id(value)
    return value


def evaluation_bytes(value: dict[str, Any]) -> bytes:
    """Return canonical mutation evidence after identity checking."""
    if value.get("result_content_id") != _result_id(value):
        raise MutationEvaluationError(
            "mutation catalogue identity differs"
        )
    return catalogue.canonical_json_bytes(value)
