# ABOUTME: Tests for EvaluationResult and its nested analysis models.
# ABOUTME: These tests define the scored-result boundary consumed by communication and feedback.

import math
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aec_bench.contracts.evaluation_result import (
    Annotation,
    ConfidenceMetadata,
    ErrorSource,
    ErrorTag,
    EvaluationResult,
    Judgment,
    ValidityCheck,
)

# --- Valid construction ---


def test_evaluation_result_accepts_minimal_valid_payload() -> None:
    result = EvaluationResult(
        reward=0.75,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
            errors=[],
        ),
        breakdown={"findings_found": 3},
        error_taxonomy=[
            ErrorTag(
                category="tool failure",
                description="Tool returned an error",
                source=ErrorSource.MECHANICAL,
            )
        ],
        confidence=ConfidenceMetadata(
            annotator_count=2,
            inter_rater_agreement=0.8,
            confidence_interval=(0.7, 0.8),
            confidence_method="bootstrap",
        ),
        annotations=[
            Annotation(
                reviewer_id="rev-1",
                reviewer_discipline="Electrical",
                timestamp=datetime(2026, 3, 13, 10, 0, tzinfo=UTC),
                judgment=Judgment.PASS,
                categories=["clear output"],
                notes="Looks good.",
            )
        ],
    )

    assert result.reward == 0.75
    assert result.validity.output_parseable is True


def test_evaluation_result_accepts_bare_minimum_fields() -> None:
    result = EvaluationResult(
        reward=0.0,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
    )

    assert result.breakdown is None
    assert result.error_taxonomy is None
    assert result.confidence is None
    assert result.annotations is None


def test_evaluation_result_accepts_boundary_reward_values() -> None:
    low = EvaluationResult(
        reward=0.0,
        validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
    )
    high = EvaluationResult(
        reward=1.0,
        validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
    )

    assert low.reward == 0.0
    assert high.reward == 1.0


# --- Reward validation ---


def test_evaluation_result_rejects_reward_out_of_bounds() -> None:
    with pytest.raises(ValidationError):
        EvaluationResult(
            reward=1.1,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        )


def test_evaluation_result_rejects_negative_reward() -> None:
    with pytest.raises(ValidationError):
        EvaluationResult(
            reward=-0.1,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        )


def test_evaluation_result_rejects_nan_reward() -> None:
    with pytest.raises(ValidationError):
        EvaluationResult(
            reward=math.nan,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        )


def test_evaluation_result_rejects_inf_reward() -> None:
    with pytest.raises(ValidationError):
        EvaluationResult(
            reward=math.inf,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        )


# --- Cross-field validation ---


def test_evaluation_result_rejects_unparseable_output_with_nonzero_reward() -> None:
    with pytest.raises(ValidationError, match="unparseable"):
        EvaluationResult(
            reward=0.5,
            validity=ValidityCheck(
                output_parseable=False,
                schema_valid=False,
                verifier_completed=True,
            ),
        )


def test_evaluation_result_allows_unparseable_output_with_zero_reward() -> None:
    result = EvaluationResult(
        reward=0.0,
        validity=ValidityCheck(
            output_parseable=False,
            schema_valid=False,
            verifier_completed=True,
        ),
    )

    assert result.reward == 0.0


# --- ConfidenceMetadata ---


def test_confidence_metadata_rejects_interval_low_exceeds_high() -> None:
    with pytest.raises(ValidationError, match="low bound"):
        ConfidenceMetadata(confidence_interval=(0.9, 0.1))


def test_confidence_metadata_accepts_equal_interval_bounds() -> None:
    meta = ConfidenceMetadata(confidence_interval=(0.5, 0.5))

    assert meta.confidence_interval == (0.5, 0.5)


def test_confidence_metadata_rejects_negative_annotator_count() -> None:
    with pytest.raises(ValidationError):
        ConfidenceMetadata(annotator_count=-1)


def test_confidence_metadata_rejects_agreement_above_one() -> None:
    with pytest.raises(ValidationError):
        ConfidenceMetadata(inter_rater_agreement=1.1)


def test_confidence_metadata_rejects_agreement_below_zero() -> None:
    with pytest.raises(ValidationError):
        ConfidenceMetadata(inter_rater_agreement=-0.1)


# --- Nested model isolation ---


def test_validity_check_accepts_with_errors_list() -> None:
    v = ValidityCheck(
        output_parseable=True,
        schema_valid=True,
        verifier_completed=True,
        errors=["minor warning"],
    )

    assert v.errors == ["minor warning"]


def test_error_tag_rejects_blank_category() -> None:
    with pytest.raises(ValidationError):
        ErrorTag(category="   ", source=ErrorSource.MECHANICAL)


def test_annotation_rejects_blank_reviewer_id() -> None:
    with pytest.raises(ValidationError):
        Annotation(
            reviewer_id="   ",
            timestamp=datetime(2026, 3, 13, tzinfo=UTC),
            judgment=Judgment.PASS,
        )


# --- Round-trip serialization ---


def test_evaluation_result_roundtrip_serialization() -> None:
    original = EvaluationResult(
        reward=0.75,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
            errors=["warning"],
        ),
        breakdown={"findings_found": 3, "details": {"sub": True}},
        error_taxonomy=[
            ErrorTag(
                category="tool failure",
                description="timeout",
                source=ErrorSource.MECHANICAL,
            )
        ],
        confidence=ConfidenceMetadata(
            annotator_count=2,
            inter_rater_agreement=0.8,
            confidence_interval=(0.7, 0.8),
            confidence_method="bootstrap",
        ),
        annotations=[
            Annotation(
                reviewer_id="rev-1",
                timestamp=datetime(2026, 3, 13, 10, 0, tzinfo=UTC),
                judgment=Judgment.PASS,
            )
        ],
    )

    serialized = original.model_dump(mode="json")
    restored = EvaluationResult.model_validate(serialized)

    assert restored == original
    assert restored.confidence is not None
    assert restored.confidence.confidence_interval == (0.7, 0.8)
