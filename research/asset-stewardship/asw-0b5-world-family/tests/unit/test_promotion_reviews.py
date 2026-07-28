# ABOUTME: Specifies evidence-backed construct-validity review for the synthetic reference world.
# ABOUTME: Requires all physical, family, engine, mutation, and isolated-certifier evidence before a pass.

import hashlib
import json
from pathlib import Path

import pytest
from generator import boundary as generator_boundary
from promotion import reviews
from run_reference_certification import IsolatedCertifier

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = (
    B5_ROOT / "declarations" / "w1-member-authority.json"
)


def _identified(
    value: dict[str, object],
    domain: bytes,
) -> dict[str, object]:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    raw = (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    value["result_content_id"] = hashlib.sha256(
        domain + raw
    ).hexdigest()
    return value


def _evidence() -> dict[str, object]:
    checks = {
        f"C-R{index:02d}": {
            "first_failure": "none",
            "outcome": "pass",
        }
        for index in range(1, 25)
    }
    anchor = _identified(
        {
            "evidence": {
                "all_checks": {"checks": checks},
            },
            "first_failure": "none",
            "promotable": False,
            "result_content_id": "",
            "schema_id": "asw-0b5.w4-composition-result.v3",
            "terminal_state": "w4-checks-pass",
        },
        b"asw-0b5.w4-composition-result.v3\0",
    )
    family = _identified(
        {
            "accepted_member_results": {
                "INT.01.hydraulic-supporting": "1" * 64,
                "INT.02.hydraulic-opposing": "2" * 64,
                "INT.03.primary-dominant": "3" * 64,
            },
            "coverage": {
                "accepted_interaction_count": 3,
                "boundary_probe_count": 11,
                "engine_variant_count": 7,
                "grid_value_count": 32,
                "mutation_count": 30,
                "oat_probe_count": 68,
                "retained_predecessor_rejection_count": 2,
            },
            "first_failure": "none",
            "profile_id": "AU-NSW-LH-SYN-SPS-v1",
            "promotable": False,
            "result_content_id": "",
            "schema_id": "asw-0b5.family-decision.v2",
            "terminal_state": "family-w4-checks-pass",
        },
        b"asw-0b5.family-decision.v2\0",
    )
    engine = _identified(
        {
            "first_failure": "none",
            "promotable": False,
            "result_content_id": "",
            "schema_id": "asw-0b5.engine-variant-evaluation.v1",
            "terminal_state": "engine-variants-pass",
            "variant_ids": [
                "ENG.00.base",
                "ENG.01.curve-16",
                "ENG.02.curve-64",
                "ENG.03.report-2s",
                "ENG.04.route-report-2s",
                "ENG.05.outfall-order-swap",
                "ENG.06.outfall-target-swap",
            ],
        },
        b"asw-0b5.engine-variant-evaluation.v1\0",
    )
    mutation = _identified(
        {
            "first_failure": "none",
            "mutation_count": 30,
            "mutations": {
                f"M{index:02d}": {"outcome": "pass"}
                for index in range(1, 31)
            },
            "promotable": False,
            "result_content_id": "",
            "schema_id": (
                "asw-0b5.mutation-catalogue-evaluation.v1"
            ),
            "terminal_state": "mutation-catalogue-pass",
        },
        b"asw-0b5.mutation-catalogue-evaluation.v1\0",
    )
    certifier = _identified(
        {
            "checks": [
                {"outcome": "satisfied", "stage": stage}
                for stage in (
                    "replay-identity",
                    "canonical-request",
                    "case-reconstruction",
                    "curve-reconstruction",
                    "semantic-candidate",
                    "engine-diagnostics",
                    "exact-invariants",
                    "qualitative-relations",
                )
            ],
            "first_failing_stage": "w4-tolerance-required",
            "promotable": False,
            "result_content_id": "",
            "schema_id": "asw-0b5.certifier-result.v1",
            "terminal_state": "quantitative-pending-w4",
        },
        b"asw-0b5.certifier-result.v1\0",
    )
    return {
        "anchor_result": anchor,
        "certifier_result": certifier,
        "engine_result": engine,
        "family_result": family,
        "mutation_result": mutation,
    }


def test_complete_evidence_passes_all_thirteen_gates() -> None:
    result = reviews.review_construct_validity(
        authority_bytes=W1_DECLARATION.read_bytes(),
        certifier_environment={
            "dependency_inventory_id": "6" * 64,
            "environment_id": "7" * 64,
            "execution_mode": "isolated-copy",
            "forbidden_dependencies_absent": [
                "generator",
                "swmm",
            ],
            "source_inventory_id": "8" * 64,
        },
        generation_id="9" * 64,
        **_evidence(),
    )

    assert result["terminal_state"] == "gate-review-pass"
    assert result["first_failure"] == "none"
    assert [row["criterion_id"] for row in result["gates"]] == [
        f"AG-{index:02d}" for index in range(1, 14)
    ]
    assert all(row["outcome"] == "pass" for row in result["gates"])
    assert result["validity"] == {
        "v0": "pass",
        "v1": "pass",
        "v2": "pass",
        "v3": "pass",
        "v4": "unclaimed",
    }


def test_missing_no_maintenance_check_rejects_gate_review() -> None:
    evidence = _evidence()
    anchor = evidence["anchor_result"]
    del anchor["evidence"]["all_checks"]["checks"]["C-R22"]
    _identified(
        anchor,
        b"asw-0b5.w4-composition-result.v3\0",
    )

    with pytest.raises(
        reviews.PromotionReviewError,
        match="physical check inventory",
    ):
        reviews.review_construct_validity(
            authority_bytes=W1_DECLARATION.read_bytes(),
            certifier_environment={
                "dependency_inventory_id": "6" * 64,
                "environment_id": "7" * 64,
                "execution_mode": "isolated-copy",
                "forbidden_dependencies_absent": [
                    "generator",
                    "swmm",
                ],
                "source_inventory_id": "8" * 64,
            },
            generation_id="9" * 64,
            **evidence,
        )


def test_isolated_certifier_dispatches_sensitivity_bundle(
    tmp_path: Path,
) -> None:
    bundle = generator_boundary.canonical_json_bytes(
        {
            "member_content_id": "1" * 64,
            "probe_id": "INT.01.hydraulic-supporting",
            "profile_id": "AU-NSW-LH-SYN-SPS-v1",
            "promotable": False,
            "replays": [],
            "schema_id": (
                "asw-0b5.certifier-sensitivity-bundle.v1"
            ),
        }
    )
    certifier = IsolatedCertifier(
        authority_bytes=W1_DECLARATION.read_bytes(),
        workspace=tmp_path / "certifier",
    )
    try:
        result = json.loads(certifier.certify(bundle))
    finally:
        certifier.close()

    assert result["schema_id"] == (
        "asw-0b5.certifier-sensitivity-result.v1"
    )
    assert result["terminal_state"] == "certifier-input-reject"
    assert result["first_failing_stage"] == (
        "sensitivity-bundle-shape"
    )
