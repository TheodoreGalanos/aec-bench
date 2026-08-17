# ABOUTME: Tests the versioned DeepSeek provider and feature qualification matrix.
# ABOUTME: Prevents keyless protocol checks from becoming unsupported live-provider claims.

from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.adapters.deepseek_harness.evidence import DeepSeekAttestationLevel
from aec_bench.adapters.deepseek_harness.qualification import (
    DEEPSEEK_QUALIFICATION_FEATURES,
    DeepSeekQualificationMatrix,
    load_deepseek_qualification_matrix,
)


def test_current_matrix_is_complete_and_links_each_passing_cell_to_a_test() -> None:
    matrix = load_deepseek_qualification_matrix()
    repository_root = Path(__file__).resolve().parents[2]

    assert matrix.schema_id == "aec-bench/deepseek-qualification/1"
    assert {row.provider_route for row in matrix.rows} == {"azure", "deepseek-official"}
    for row in matrix.rows:
        assert set(row.features) == set(DEEPSEEK_QUALIFICATION_FEATURES)
        for cell in row.features.values():
            for reference in cell.evidence:
                relative_path, separator, test_name = reference.partition("::")
                assert separator == "::"
                source = repository_root / relative_path
                assert source.is_file()
                assert f"def {test_name}(" in source.read_text(encoding="utf-8")


def test_matrix_import_preserves_unknown_future_fields() -> None:
    payload = load_deepseek_qualification_matrix().model_dump(mode="json", by_alias=True)
    payload["future_matrix_field"] = {"retained": True}
    payload["rows"][0]["features"]["keyless_protocol"]["future_cell_field"] = "retained"

    imported = DeepSeekQualificationMatrix.model_validate(payload).model_dump(mode="json", by_alias=True)

    assert imported["future_matrix_field"] == {"retained": True}
    assert imported["rows"][0]["features"]["keyless_protocol"]["future_cell_field"] == "retained"


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
