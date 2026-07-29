# ABOUTME: Tests for EvaluationResult and its nested analysis models.
# ABOUTME: These tests define the scored-result boundary consumed by communication and feedback.

import math
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import aec_bench.contracts as contracts
from aec_bench.contracts.evaluation_result import (
    Annotation,
    ConfidenceMetadata,
    ErrorSource,
    ErrorTag,
    EvaluationResult,
    Judgment,
    StewardshipEvaluation,
    StewardshipEvaluationEvidence,
    StewardshipIntegrityGates,
    StewardshipMetricVector,
    StewardshipTerminalLiability,
    ValidityCheck,
)

# --- Valid construction ---


def test_stewardship_evaluation_contracts_are_public_library_exports() -> None:
    assert {
        "StewardshipEvaluation",
        "StewardshipEvaluationEvidence",
        "StewardshipIntegrityGates",
        "StewardshipMetricVector",
        "StewardshipTerminalLiability",
    }.issubset(contracts.__all__)


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
    with pytest.raises(ValidationError, match="invalid outputs"):
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


def test_evaluation_result_rejects_schema_invalid_output_with_nonzero_reward() -> None:
    with pytest.raises(ValidationError, match="invalid outputs"):
        EvaluationResult(
            reward=0.5,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=False,
                verifier_completed=True,
            ),
        )


def _stewardship_evaluation(
    *,
    artifact_and_replay_integrity: bool = True,
) -> StewardshipEvaluation:
    gates = StewardshipIntegrityGates(
        artifact_and_replay_integrity=artifact_and_replay_integrity,
        output_and_action_contract_validity=True,
        authority_and_execution_consistency=True,
        decision_time_validity=True,
        obligation_and_restriction_integrity=True,
        physical_and_service_outcomes_available=True,
        resource_stewardship_available=True,
        evidence_and_record_integrity=True,
        handover_continuity_integrity=True,
        terminal_stewardship_available=True,
        errors=(() if artifact_and_replay_integrity else ("artifact and replay evidence differs",)),
    )
    return StewardshipEvaluation(
        schema_version="stewardship-evaluation.v1",
        valid=artifact_and_replay_integrity,
        gates=gates,
        metrics=StewardshipMetricVector(
            decision_time_invalid_count=0,
            physical_service_review_required=False,
            maintenance_intervention_count=1,
            obligation_breach_count=0,
            restriction_breach_count=0,
            evidence_integrity_gap_count=0,
            consumed_maintenance_resource_count=1,
            handover_count=1,
            handover_omission_count=0,
            terminal_liability=StewardshipTerminalLiability(
                review_required_physical_state=False,
                active_restriction_count=1,
                overdue_calendar_seconds=0,
                overdue_affected_pump_runtime_seconds=0,
                breached_obligation_count=0,
                unresolved_verification_count=0,
                deferred_work_count=0,
                unavailable_pump_count=1,
                consumed_maintenance_resource_count=1,
                unresolved_evidence=False,
            ),
        ),
        evidence=StewardshipEvaluationEvidence(
            world_run_manifest_content_id="a" * 64,
            initial_state_id="b" * 64,
            terminal_state_id="c" * 64,
            replayed_transition_ids=("transition-0001",),
            imported_artifact_sha256=("d" * 64,),
        ),
    )


def test_evaluation_result_carries_stewardship_metric_vector() -> None:
    stewardship = _stewardship_evaluation()

    result = EvaluationResult(
        reward=1.0,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
        stewardship=stewardship,
    )
    restored = EvaluationResult.model_validate(result.model_dump(mode="json"))

    assert restored.stewardship == stewardship
    assert restored.stewardship is not None
    assert restored.stewardship.metrics.terminal_liability.active_restriction_count == 1


def test_evaluation_result_blocks_reward_when_stewardship_integrity_fails() -> None:
    with pytest.raises(ValidationError, match="stewardship integrity failures"):
        EvaluationResult(
            reward=1.0,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
            stewardship=_stewardship_evaluation(
                artifact_and_replay_integrity=False,
            ),
        )


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
