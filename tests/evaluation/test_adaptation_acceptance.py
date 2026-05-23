# ABOUTME: Tests the Phase 6A acceptance-band evaluator for adaptation trial outputs.
# ABOUTME: Verifies explicit benchmark, training, analysis, and verifier-test grading.

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    Completeness,
    DerivationStepRecord,
)
from aec_bench.evaluation.adaptation import (
    AcceptanceBand,
    AcceptanceThresholds,
    classify_adaptation_trial,
    summarize_acceptance_bands,
)
from tests.support.trial_record_factories import make_trial_record


def test_classify_adaptation_trial_returns_benchmark_grade_for_complete_high_reward() -> None:
    record = make_trial_record(
        adaptation=AdaptationProvenance(
            family_id="heat-load-family",
            seed_task_id="mechanical/heat-load/au-office",
            variation_key="jurisdiction=us",
            variation={"jurisdiction": "us"},
            derivation_lineage=[
                DerivationStepRecord(
                    axis="jurisdiction",
                    parent_value="au",
                    value="us",
                )
            ],
        ),
        evaluation=EvaluationResult(
            reward=0.98,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
        completeness=Completeness.COMPLETE,
    )

    decision = classify_adaptation_trial(record)

    assert decision.band is AcceptanceBand.BENCHMARK_GRADE
    assert decision.preserve is True
    assert decision.reasons == ["reward_meets_benchmark_threshold"]


def test_classify_adaptation_trial_returns_training_grade_for_valid_mid_reward() -> None:
    record = make_trial_record(
        evaluation=EvaluationResult(
            reward=0.72,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
        completeness=Completeness.PARTIAL,
    )

    decision = classify_adaptation_trial(record)

    assert decision.band is AcceptanceBand.TRAINING_GRADE
    assert decision.reasons == ["reward_meets_training_threshold"]


def test_classify_adaptation_trial_returns_verifier_test_grade_for_invalid_output() -> None:
    record = make_trial_record(
        evaluation=EvaluationResult(
            reward=0.0,
            validity=ValidityCheck(
                output_parseable=False,
                schema_valid=False,
                verifier_completed=True,
                errors=["schema mismatch"],
            ),
        )
    )

    decision = classify_adaptation_trial(record)

    assert decision.band is AcceptanceBand.VERIFIER_TEST_GRADE
    assert decision.preserve is True
    assert decision.reasons == ["output_invalid_but_verifier_completed"]


def test_classify_adaptation_trial_returns_analysis_grade_for_incomplete_verifier() -> None:
    record = make_trial_record(
        evaluation=EvaluationResult(
            reward=0.0,
            validity=ValidityCheck(
                output_parseable=False,
                schema_valid=False,
                verifier_completed=False,
                errors=["timeout"],
            ),
        )
    )

    decision = classify_adaptation_trial(record)

    assert decision.band is AcceptanceBand.ANALYSIS_GRADE
    assert decision.preserve is False
    assert decision.reasons == ["verifier_incomplete"]


def test_summarize_acceptance_bands_counts_bands() -> None:
    records = [
        make_trial_record(
            evaluation=EvaluationResult(
                reward=0.99,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
            completeness=Completeness.COMPLETE,
        ),
        make_trial_record(
            trial_id="trial-002",
            evaluation=EvaluationResult(
                reward=0.75,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
            completeness=Completeness.PARTIAL,
        ),
        make_trial_record(
            trial_id="trial-003",
            evaluation=EvaluationResult(
                reward=0.0,
                validity=ValidityCheck(
                    output_parseable=False,
                    schema_valid=False,
                    verifier_completed=True,
                ),
            ),
        ),
    ]

    summary = summarize_acceptance_bands(records, thresholds=AcceptanceThresholds())

    assert summary.total_trials == 3
    assert summary.band_counts == {
        "benchmark_grade": 1,
        "training_grade": 1,
        "analysis_grade": 0,
        "verifier_test_grade": 1,
    }
