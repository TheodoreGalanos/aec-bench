# ABOUTME: Performs research-local gate, rights, and visibility reviews for one reference package.
# ABOUTME: Produces content-addressed decisions without importing generator or certifier code.

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

GATE_DOMAIN = b"asw-0b5.gate-review.v1\0"
RIGHTS_DOMAIN = b"asw-0b5.rights-review.v1\0"
VISIBILITY_DOMAIN = b"asw-0b5.visibility-review.v1\0"
ANCHOR_DOMAIN = b"asw-0b5.w4-composition-result.v3\0"
FAMILY_DOMAIN = b"asw-0b5.family-decision.v2\0"
ENGINE_DOMAIN = b"asw-0b5.engine-variant-evaluation.v1\0"
MUTATION_DOMAIN = b"asw-0b5.mutation-catalogue-evaluation.v1\0"
CERTIFIER_DOMAIN = b"asw-0b5.certifier-result.v1\0"
W1_DECLARATION_SHA256 = (
    "4470e8af16bb6238a11045847199ffad95f1a7f57f64e85978a009bdda30ded9"
)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class PromotionReviewError(ValueError):
    """Raised when package review evidence is incomplete or inconsistent."""


def _canonical(value: object) -> bytes:
    def check(child: object) -> None:
        if child is None or isinstance(child, float):
            raise PromotionReviewError(
                "review values cannot contain null or floating-point JSON"
            )
        if isinstance(child, dict):
            for key, nested in child.items():
                if not isinstance(key, str):
                    raise PromotionReviewError(
                        "review object key is not text"
                    )
                check(nested)
        elif isinstance(child, list):
            for nested in child:
                check(nested)
        elif not isinstance(child, str | int | bool):
            raise PromotionReviewError(
                "review contains an unsupported value"
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


def _identified(
    value: dict[str, Any],
    domain: bytes,
) -> dict[str, Any]:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    value["result_content_id"] = hashlib.sha256(
        domain + _canonical(payload)
    ).hexdigest()
    return value


def _require_result(
    value: dict[str, Any],
    *,
    domain: bytes,
    schema_id: str,
    terminal_state: str,
    failure_field: str,
    expected_failure: str,
    label: str,
) -> None:
    expected = _identified(
        {**value, "result_content_id": ""},
        domain,
    )["result_content_id"]
    if value.get("result_content_id") != expected:
        raise PromotionReviewError(f"{label} result identity differs")
    if (
        value.get("schema_id") != schema_id
        or value.get("terminal_state") != terminal_state
        or value.get(failure_field) != expected_failure
        or value.get("promotable") is not False
    ):
        raise PromotionReviewError(f"{label} result state differs")


def _read_authority(raw: bytes) -> dict[str, Any]:
    if hashlib.sha256(raw).hexdigest() != W1_DECLARATION_SHA256:
        raise PromotionReviewError("W1 authority identity differs")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PromotionReviewError(str(error)) from error
    if not isinstance(value, dict) or _canonical(value) != raw:
        raise PromotionReviewError("W1 authority is not canonical")
    return value


def _physical_checks(
    anchor_result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    evidence = anchor_result.get("evidence")
    if not isinstance(evidence, dict):
        raise PromotionReviewError("anchor physical evidence is absent")
    checks: dict[str, dict[str, Any]] = {}
    for area_name, area in evidence.items():
        if area_name == "amended_hydraulics":
            continue
        if not isinstance(area, dict):
            continue
        area_checks = area.get("checks")
        if not isinstance(area_checks, dict):
            continue
        for check_id, check in area_checks.items():
            if check_id in checks or not isinstance(check, dict):
                raise PromotionReviewError(
                    "anchor physical check identity is duplicated"
                )
            checks[check_id] = check
    expected = {f"C-R{index:02d}" for index in range(1, 25)}
    if set(checks) != expected or any(
        check.get("outcome") != "pass"
        or check.get("first_failure") != "none"
        for check in checks.values()
    ):
        raise PromotionReviewError("physical check inventory differs")
    return checks


def review_construct_validity(
    *,
    anchor_result: dict[str, Any],
    authority_bytes: bytes,
    certifier_environment: dict[str, Any],
    certifier_result: dict[str, Any],
    engine_result: dict[str, Any],
    family_result: dict[str, Any],
    generation_id: str,
    mutation_result: dict[str, Any],
) -> dict[str, Any]:
    """Review all thirteen world gates from exact completed evidence."""
    if SHA256.fullmatch(generation_id) is None:
        raise PromotionReviewError("generation identity differs")
    authority = _read_authority(authority_bytes)
    _require_result(
        anchor_result,
        domain=ANCHOR_DOMAIN,
        schema_id="asw-0b5.w4-composition-result.v3",
        terminal_state="w4-checks-pass",
        failure_field="first_failure",
        expected_failure="none",
        label="anchor",
    )
    checks = _physical_checks(anchor_result)
    _require_result(
        family_result,
        domain=FAMILY_DOMAIN,
        schema_id="asw-0b5.family-decision.v2",
        terminal_state="family-w4-checks-pass",
        failure_field="first_failure",
        expected_failure="none",
        label="family",
    )
    coverage = family_result.get("coverage")
    if (
        not isinstance(coverage, dict)
        or coverage.get("accepted_interaction_count") != 3
        or coverage.get("boundary_probe_count") != 11
        or coverage.get("engine_variant_count") != 7
        or coverage.get("grid_value_count") != 32
        or coverage.get("mutation_count") != 30
        or coverage.get("oat_probe_count") != 68
        or coverage.get("retained_predecessor_rejection_count") != 2
        or set(family_result.get("accepted_member_results", {}))
        != {
            "INT.01.hydraulic-supporting",
            "INT.02.hydraulic-opposing",
            "INT.03.primary-dominant",
        }
    ):
        raise PromotionReviewError("family coverage differs")
    _require_result(
        engine_result,
        domain=ENGINE_DOMAIN,
        schema_id="asw-0b5.engine-variant-evaluation.v1",
        terminal_state="engine-variants-pass",
        failure_field="first_failure",
        expected_failure="none",
        label="engine",
    )
    if len(engine_result.get("variant_ids", [])) != 7:
        raise PromotionReviewError("engine variant coverage differs")
    _require_result(
        mutation_result,
        domain=MUTATION_DOMAIN,
        schema_id="asw-0b5.mutation-catalogue-evaluation.v1",
        terminal_state="mutation-catalogue-pass",
        failure_field="first_failure",
        expected_failure="none",
        label="mutation",
    )
    if (
        mutation_result.get("mutation_count") != 30
        or len(mutation_result.get("mutations", {})) != 30
        or any(
            child.get("outcome") != "pass"
            for child in mutation_result.get("mutations", {}).values()
        )
    ):
        raise PromotionReviewError("mutation coverage differs")
    _require_result(
        certifier_result,
        domain=CERTIFIER_DOMAIN,
        schema_id="asw-0b5.certifier-result.v1",
        terminal_state="quantitative-pending-w4",
        failure_field="first_failing_stage",
        expected_failure="w4-tolerance-required",
        label="certifier",
    )
    certifier_stages = {
        child.get("stage")
        for child in certifier_result.get("checks", [])
        if child.get("outcome") == "satisfied"
    }
    if certifier_stages != {
        "canonical-request",
        "case-reconstruction",
        "curve-reconstruction",
        "engine-diagnostics",
        "exact-invariants",
        "qualitative-relations",
        "replay-identity",
        "semantic-candidate",
    }:
        raise PromotionReviewError("certifier check inventory differs")
    if (
        set(certifier_environment)
        != {
            "dependency_inventory_id",
            "environment_id",
            "execution_mode",
            "forbidden_dependencies_absent",
            "source_inventory_id",
        }
        or certifier_environment["execution_mode"]
        != "isolated-copy"
        or certifier_environment["forbidden_dependencies_absent"]
        != ["generator", "swmm"]
        or any(
            SHA256.fullmatch(certifier_environment[field]) is None
            for field in (
                "dependency_inventory_id",
                "environment_id",
                "source_inventory_id",
            )
        )
    ):
        raise PromotionReviewError(
            "isolated certifier environment differs"
        )

    parameter_ids = {
        parameter["identity"] for parameter in authority["parameters"]
    }
    rule_ids = set(authority["rules"])
    required_parameters = {
        "exposure.calendar_max",
        "exposure.runtime_max",
        "exposure.starts_max",
        "mechanism.a_c",
        "mechanism.a_o",
        "mechanism.r_c_runtime",
        "mechanism.r_o_runtime",
        "mechanism.r_o_start",
        "observation.flow_resolution",
        "observation.level_resolution",
        "resource.access_duration",
        "resource.concurrent_limit",
        "resource.kit_initial",
        "resource.kit_lead",
        "topology.max_running_pumps",
        "topology.transfer_limit",
    }
    required_rules = {
        "asw-0b4.rule.capability-predicate.v1",
        "asw-0b4.rule.clearance-progression.v1",
        "asw-0b4.rule.clearance-repair.v1",
        "asw-0b4.rule.observation-quantization.v1",
        "asw-0b4.rule.obstruction-clearing.v1",
        "asw-0b4.rule.obstruction-progression.v1",
        "asw-0b4.rule.transfer.v1",
        "asw-0b4.rule.wet-well-balance.v1",
    }
    if (
        not required_parameters <= parameter_ids
        or not required_rules <= rule_ids
    ):
        raise PromotionReviewError(
            "world mechanism or rule authority differs"
        )

    authority_id = hashlib.sha256(authority_bytes).hexdigest()
    anchor_id = anchor_result["result_content_id"]
    family_id = family_result["result_content_id"]
    engine_id = engine_result["result_content_id"]
    mutation_id = mutation_result["result_content_id"]
    certifier_id = certifier_result["result_content_id"]
    environment_id = certifier_environment["environment_id"]
    evidence_by_gate = {
        "AG-01": [authority_id, family_id, engine_id],
        "AG-02": [authority_id],
        "AG-03": [authority_id],
        "AG-04": [anchor_id],
        "AG-05": [authority_id],
        "AG-06": [anchor_id],
        "AG-07": [authority_id, anchor_id],
        "AG-08": [authority_id],
        "AG-09": [anchor_id, certifier_id],
        "AG-10": [certifier_id, environment_id],
        "AG-11": [anchor_id],
        "AG-12": [authority_id, mutation_id],
        "AG-13": [engine_id, anchor_id],
    }
    if (
        checks["C-R22"]["outcome"] != "pass"
        or checks["C-R19"]["outcome"] != "pass"
        or checks["C-R20"]["outcome"] != "pass"
        or checks["C-R21"]["outcome"] != "pass"
        or checks["C-R24"]["outcome"] != "pass"
    ):
        raise PromotionReviewError(
            "construct-critical physical relationship differs"
        )
    value: dict[str, Any] = {
        "first_failure": "none",
        "gates": [
            {
                "criterion_id": criterion_id,
                "evidence_ids": evidence_by_gate[criterion_id],
                "outcome": "pass",
            }
            for criterion_id in (
                f"AG-{index:02d}" for index in range(1, 14)
            )
        ],
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "result_content_id": "",
        "schema_id": "asw-0b5.gate-review.v1",
        "terminal_state": "gate-review-pass",
        "validity": {
            "v0": "pass",
            "v1": "pass",
            "v2": "pass",
            "v3": "pass",
            "v4": "unclaimed",
        },
    }
    return _identified(value, GATE_DOMAIN)


def review_payload_rights(
    *,
    field_rows: list[dict[str, Any]],
    payloads: dict[str, bytes],
    repository_license_sha256: str,
) -> dict[str, Any]:
    """Confirm every payload field uses the repository-original rights path."""
    expected_rights = "repository-original-redistributable"
    failure = "none"
    if (
        repository_license_sha256
        != "a5e57c0e89c4ca0b40ae583b3ac895847abc28515323cbe6bc8f639d20af76c4"
    ):
        failure = "repository-license-identity"
    elif any(
        row.get("rights_decision_id") != expected_rights
        for row in field_rows
    ):
        failure = "field-rights-decision"
    elif any(
        marker in raw.lower()
        for raw in payloads.values()
        for marker in (
            b"<html",
            b"copyright hunter water",
            b"creative commons",
        )
    ):
        failure = "external-source-bytes"
    value: dict[str, Any] = {
        "field_count": len(field_rows),
        "file_sha256": {
            path: hashlib.sha256(raw).hexdigest()
            for path, raw in sorted(payloads.items())
        },
        "first_failure": failure,
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "repository_license_sha256": repository_license_sha256,
        "result_content_id": "",
        "rights_decision_id": expected_rights,
        "schema_id": "asw-0b5.rights-review.v1",
        "terminal_state": (
            "rights-review-pass"
            if failure == "none"
            else "rights-review-reject"
        ),
    }
    return _identified(value, RIGHTS_DOMAIN)


def review_payload_visibility(
    *,
    field_rows: list[dict[str, Any]],
    role_visibility: dict[str, str],
) -> dict[str, Any]:
    """Confirm that each file and field has its one allowed visibility."""
    expected = {
        "physical-member": "host-private",
        "physical-reference-checks": "host-private",
        "public-profile": "public",
    }
    failure = "none"
    if role_visibility != expected:
        failure = "file-visibility"
    elif any(
        row.get("visibility_class")
        != expected.get(str(row.get("semantic_role")))
        for row in field_rows
    ):
        failure = "field-visibility"
    value: dict[str, Any] = {
        "field_count": len(field_rows),
        "first_failure": failure,
        "forbidden_payload_classes": {
            "actor-visible": 0,
            "certification-private": 0,
            "holdout-sensitive": 0,
        },
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "result_content_id": "",
        "role_visibility": role_visibility,
        "schema_id": "asw-0b5.visibility-review.v1",
        "terminal_state": (
            "visibility-review-pass"
            if failure == "none"
            else "visibility-review-reject"
        ),
    }
    return _identified(value, VISIBILITY_DOMAIN)


def review_bytes(
    value: dict[str, Any],
    *,
    domain: bytes,
) -> bytes:
    """Return canonical review bytes after recomputing its identity."""
    expected = _identified(
        {**value, "result_content_id": ""},
        domain,
    )["result_content_id"]
    if value.get("result_content_id") != expected:
        raise PromotionReviewError("review result identity differs")
    return _canonical(value)
