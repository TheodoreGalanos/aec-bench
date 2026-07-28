# ABOUTME: Executes the ordered W3 independent certification pipeline and emits deterministic non-promotable results.
# ABOUTME: Separates structural, exact, qualitative, and pending-quantitative outcomes without owning W4 acceptance.

from __future__ import annotations

import hashlib
from typing import Any

from certifier import boundary, candidate, cases, observations, physics, pipeline

RESULT_SCHEMA_ID = "asw-0b5.certifier-result.v1"
SENSITIVITY_RESULT_SCHEMA_ID = (
    "asw-0b5.certifier-sensitivity-result.v1"
)
RESULT_DOMAIN = b"asw-0b5.certifier-result.v1\0"
CERTIFIER_PROTOCOL_ID = "asw-0b4.independent-certification-protocol.v2"


def _result_content_id(value: dict[str, Any]) -> str:
    payload = {
        key: child for key, child in value.items() if key != "result_content_id"
    }
    return hashlib.sha256(
        RESULT_DOMAIN + boundary.canonical_json_bytes(payload)
    ).hexdigest()


def _result(
    *,
    bundle_bytes: bytes,
    cases: list[dict[str, Any]],
    checks: list[dict[str, str]],
    first_failing_stage: str,
    residual_register: list[dict[str, Any]],
    schema_id: str = RESULT_SCHEMA_ID,
    terminal_state: str,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "authorities": {
            "profile_id": candidate.PROFILE_ID,
            "protocol_id": CERTIFIER_PROTOCOL_ID,
            "w1_sha256": dict(boundary.AUTHORITIES)["w1"],
            "w3_sha256": dict(boundary.AUTHORITIES)["w3"],
        },
        "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "cases": cases,
        "checks": checks,
        "first_failing_stage": first_failing_stage,
        "promotable": False,
        "residual_register": residual_register,
        "result_content_id": "",
        "schema_id": schema_id,
        "terminal_state": terminal_state,
    }
    value["result_content_id"] = _result_content_id(value)
    return value


def certify_bundle(
    bundle_bytes: bytes,
    authority_bytes: bytes,
) -> dict[str, Any]:
    """Certify one complete W2 byte bundle or emit its deterministic first rejection."""
    try:
        segments = candidate.read_bundle(bundle_bytes)
    except candidate.CandidateError as error:
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-INPUT",
                    "outcome": "reject",
                    "stage": error.stage,
                }
            ],
            first_failing_stage=error.stage,
            residual_register=[],
            terminal_state="certifier-input-reject",
        )
    try:
        authority = boundary.read_w1_declaration(authority_bytes)
        result_cases, checks = pipeline.certify(segments, authority)
        return _result(
            bundle_bytes=bundle_bytes,
            cases=result_cases,
            checks=checks,
            first_failing_stage="w4-tolerance-required",
            residual_register=pipeline.residual_register(),
            terminal_state="quantitative-pending-w4",
        )
    except candidate.CandidateError as error:
        terminal = (
            "structural-reject"
            if error.stage.startswith(("request", "semantic", "curve"))
            else "exact-reject"
        )
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-CANDIDATE",
                    "outcome": "reject",
                    "stage": error.stage,
                }
            ],
            first_failing_stage=error.stage,
            residual_register=[],
            terminal_state=terminal,
        )
    except boundary.CertifierBoundaryError as error:
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-AUTHORITY",
                    "outcome": "reject",
                    "stage": error.reason,
                }
            ],
            first_failing_stage=error.reason,
            residual_register=[],
            terminal_state="structural-reject",
        )
    except (cases.CaseError, observations.ObservationError, physics.PhysicsError) as error:
        stage = type(error).__name__.removesuffix("Error").lower()
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-EXACT",
                    "outcome": "reject",
                    "stage": stage,
                }
            ],
            first_failing_stage=stage,
            residual_register=[],
            terminal_state="exact-reject",
        )
    except pipeline.PipelineReject as error:
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-W3",
                    "outcome": "reject",
                    "stage": error.stage,
                }
            ],
            first_failing_stage=error.stage,
            residual_register=[],
            terminal_state=error.terminal_state,
        )
    except Exception as error:  # pragma: no cover - defensive result boundary
        stage = f"internal-{type(error).__name__.lower()}"
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-INTERNAL",
                    "outcome": "reject",
                    "stage": stage,
                }
            ],
            first_failing_stage=stage,
            residual_register=[],
            terminal_state="certifier-internal-error",
        )


def certify_sensitivity_bundle(
    bundle_bytes: bytes,
    authority_bytes: bytes,
) -> dict[str, Any]:
    """Certify one declared sensitivity member and fixed W2 case map."""
    try:
        bundle = candidate.read_sensitivity_bundle(bundle_bytes)
        first_request = candidate.read_request(
            bundle.segments[0].roles["request"]
        )
        if (
            first_request["member"]["member_content_id"]
            != bundle.member_content_id
        ):
            raise pipeline.PipelineReject(
                "exact-reject",
                "sensitivity-member-binding",
            )
        authority = boundary.read_w1_declaration(authority_bytes)
        result_cases, checks = pipeline.certify(
            bundle.segments,
            authority,
            case_ids=bundle.case_ids,
            require_anchor_witnesses=False,
        )
        return _result(
            bundle_bytes=bundle_bytes,
            cases=result_cases,
            checks=checks,
            first_failing_stage="w4-tolerance-required",
            residual_register=pipeline.residual_register(),
            schema_id=SENSITIVITY_RESULT_SCHEMA_ID,
            terminal_state="quantitative-pending-w4",
        )
    except candidate.CandidateError as error:
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-INPUT",
                    "outcome": "reject",
                    "stage": error.stage,
                }
            ],
            first_failing_stage=error.stage,
            residual_register=[],
            schema_id=SENSITIVITY_RESULT_SCHEMA_ID,
            terminal_state="certifier-input-reject",
        )
    except boundary.CertifierBoundaryError as error:
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-AUTHORITY",
                    "outcome": "reject",
                    "stage": error.reason,
                }
            ],
            first_failing_stage=error.reason,
            residual_register=[],
            schema_id=SENSITIVITY_RESULT_SCHEMA_ID,
            terminal_state="structural-reject",
        )
    except (
        cases.CaseError,
        observations.ObservationError,
        physics.PhysicsError,
    ) as error:
        stage = type(error).__name__.removesuffix("Error").lower()
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-EXACT",
                    "outcome": "reject",
                    "stage": stage,
                }
            ],
            first_failing_stage=stage,
            residual_register=[],
            schema_id=SENSITIVITY_RESULT_SCHEMA_ID,
            terminal_state="exact-reject",
        )
    except pipeline.PipelineReject as error:
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-W3",
                    "outcome": "reject",
                    "stage": error.stage,
                }
            ],
            first_failing_stage=error.stage,
            residual_register=[],
            schema_id=SENSITIVITY_RESULT_SCHEMA_ID,
            terminal_state=error.terminal_state,
        )
    except Exception as error:  # pragma: no cover - defensive boundary
        stage = f"internal-{type(error).__name__.lower()}"
        return _result(
            bundle_bytes=bundle_bytes,
            cases=[],
            checks=[
                {
                    "check_id": "C-INTERNAL",
                    "outcome": "reject",
                    "stage": stage,
                }
            ],
            first_failing_stage=stage,
            residual_register=[],
            schema_id=SENSITIVITY_RESULT_SCHEMA_ID,
            terminal_state="certifier-internal-error",
        )


def certification_result_bytes(value: dict[str, Any]) -> bytes:
    """Return exact canonical W3 result bytes."""
    return boundary.canonical_json_bytes(value)
