# ABOUTME: Tests the versioned DeepSeek provider and feature qualification matrix.
# ABOUTME: Prevents keyless protocol checks from becoming unsupported live-provider claims.

import pytest
from pydantic import ValidationError

from aec_bench.adapters.deepseek_harness.evidence import DeepSeekAttestationLevel
from aec_bench.adapters.deepseek_harness.qualification import (
    DEEPSEEK_QUALIFICATION_FEATURES,
    DeepSeekQualificationMatrix,
    LegacyDeepSeekQualificationMatrix,
    load_deepseek_qualification_matrix,
)


def test_current_matrix_has_exact_versioned_content_addressed_cells() -> None:
    matrix = load_deepseek_qualification_matrix()

    assert isinstance(matrix, DeepSeekQualificationMatrix)
    assert matrix.schema_id == "aec-bench/deepseek-qualification/2"
    assert {cell.provider_route for cell in matrix.cells} == {"azure", "deepseek-official"}
    for route in {"azure", "deepseek-official"}:
        assert {cell.feature for cell in matrix.cells_for(route)} == set(DEEPSEEK_QUALIFICATION_FEATURES)
    for cell in matrix.cells:
        assert cell.adapter_identity.source_revision is not None
        if cell.status == "qualified":
            assert cell.evidence
            assert cell.qualified_at is not None
        if cell.feature.startswith("live_"):
            assert cell.evidence_level == "live"
            assert cell.status != "qualified"


def test_matrix_import_preserves_unknown_future_fields() -> None:
    payload = load_deepseek_qualification_matrix().model_dump(mode="json", by_alias=True)
    payload["future_matrix_field"] = {"retained": True}
    payload["cells"][0]["future_cell_field"] = "retained"

    imported = DeepSeekQualificationMatrix.model_validate(payload).model_dump(mode="json", by_alias=True)

    assert imported["future_matrix_field"] == {"retained": True}
    assert imported["cells"][0]["future_cell_field"] == "retained"


def test_qualification_v1_remains_readable() -> None:
    unpassed = {"status": "not-run", "reason": "No retained evidence."}
    rows = []
    for route in ("azure", "deepseek-official"):
        rows.append(
            {
                "provider_route": route,
                "sdk_version": "0.1.0rc6",
                "runtime_version": "0.1.0rc6",
                "status": "partial",
                "features": {
                    **{feature: dict(unpassed) for feature in DEEPSEEK_QUALIFICATION_FEATURES},
                    "keyless_protocol": {
                        "status": "passed",
                        "evidence": [
                            "tests/deepseek_harness/test_qualification.py::test_qualification_v1_remains_readable"
                        ],
                    },
                },
            }
        )

    legacy = LegacyDeepSeekQualificationMatrix.model_validate(
        {
            "schema": "aec-bench/deepseek-qualification/1",
            "matrix_id": "retained-v1",
            "qualification_date": "2026-08-17",
            "aec_bench_version": "0.1.0",
            "aec_bench_revision": "a" * 40,
            "rows": rows,
        }
    )

    assert legacy.schema_id == "aec-bench/deepseek-qualification/1"
    assert legacy.row_for("azure").passed_features == ("keyless_protocol",)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"status": "complete", "artifacts": []}, "complete attestation requires artifacts"),
        (
            {
                "status": "unavailable",
                "reason": "sdk-does-not-expose",
                "artifacts": [{"path": "x", "sha256": "a" * 64}],
            },
            "unavailable attestation requires a reason and cannot reference artifacts",
        ),
        ({"status": "partial"}, "partial attestation requires an artifact or a reason"),
    ],
)
def test_attestation_levels_reject_false_or_unexplained_claims(payload: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        DeepSeekAttestationLevel.model_validate(payload)
