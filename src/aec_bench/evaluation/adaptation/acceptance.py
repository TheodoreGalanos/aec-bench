# ABOUTME: Pure acceptance-band policy for adaptation trial outputs in Phase 6A.
# ABOUTME: Classifies TrialRecords into explicit preservation grades from evaluation facts.

from collections import Counter
from enum import StrEnum

from pydantic import Field

from aec_bench.contracts.trial_record import Completeness, TrialRecord
from aec_bench.contracts.validators import StrictModel


class AcceptanceBand(StrEnum):
    BENCHMARK_GRADE = "benchmark_grade"
    TRAINING_GRADE = "training_grade"
    ANALYSIS_GRADE = "analysis_grade"
    VERIFIER_TEST_GRADE = "verifier_test_grade"


class AcceptanceThresholds(StrictModel):
    benchmark_min_reward: float = 0.95
    training_min_reward: float = 0.60


class AcceptanceDecision(StrictModel):
    trial_id: str
    band: AcceptanceBand
    preserve: bool
    reasons: list[str] = Field(default_factory=list)


class AcceptanceBandSummary(StrictModel):
    total_trials: int
    band_counts: dict[str, int]


def classify_adaptation_trial(
    record: TrialRecord,
    *,
    thresholds: AcceptanceThresholds | None = None,
) -> AcceptanceDecision:
    policy = thresholds or AcceptanceThresholds()
    validity = record.evaluation.validity

    if not validity.verifier_completed:
        return AcceptanceDecision(
            trial_id=record.trial_id,
            band=AcceptanceBand.ANALYSIS_GRADE,
            preserve=False,
            reasons=["verifier_incomplete"],
        )

    if not validity.output_parseable or not validity.schema_valid:
        return AcceptanceDecision(
            trial_id=record.trial_id,
            band=AcceptanceBand.VERIFIER_TEST_GRADE,
            preserve=True,
            reasons=["output_invalid_but_verifier_completed"],
        )

    if record.evaluation.reward >= policy.benchmark_min_reward and record.completeness is Completeness.COMPLETE:
        return AcceptanceDecision(
            trial_id=record.trial_id,
            band=AcceptanceBand.BENCHMARK_GRADE,
            preserve=True,
            reasons=["reward_meets_benchmark_threshold"],
        )

    if record.evaluation.reward >= policy.training_min_reward:
        return AcceptanceDecision(
            trial_id=record.trial_id,
            band=AcceptanceBand.TRAINING_GRADE,
            preserve=True,
            reasons=["reward_meets_training_threshold"],
        )

    return AcceptanceDecision(
        trial_id=record.trial_id,
        band=AcceptanceBand.ANALYSIS_GRADE,
        preserve=False,
        reasons=["reward_below_training_threshold"],
    )


def summarize_acceptance_bands(
    records: list[TrialRecord],
    *,
    thresholds: AcceptanceThresholds | None = None,
) -> AcceptanceBandSummary:
    decisions = [classify_adaptation_trial(record, thresholds=thresholds) for record in records]
    counts = Counter(decision.band.value for decision in decisions)
    return AcceptanceBandSummary(
        total_trials=len(records),
        band_counts={band.value: counts.get(band.value, 0) for band in AcceptanceBand},
    )
