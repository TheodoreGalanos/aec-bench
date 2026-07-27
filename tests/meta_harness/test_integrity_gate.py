# ABOUTME: Tests the lexicographic integrity, validity, and utility evaluation gate.
# ABOUTME: Proves failed or incomplete evidence cannot reach scoring or promotion.

from __future__ import annotations

import hashlib
from collections.abc import Callable

from aec_bench.contracts.evaluation_outcome import (
    CandidatePlaneCost,
    CriticGapDecomposition,
    CriticPlaneCost,
    EvaluationCostBreakdown,
    EvaluationDisposition,
    EvaluationOutcome,
    IntegrityCheck,
    ResourceCost,
    SelectionNullEstimate,
    UtilityEvaluation,
    ValidityEvaluation,
)
from aec_bench.meta_harness.integrity_gate import evaluate_with_integrity_gate


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _zero_cost() -> ResourceCost:
    return ResourceCost(
        provider_calls=0,
        tokens=0,
        provider_cost_usd=0.0,
        wall_time_seconds=0.0,
    )


def _critic_gap() -> CriticGapDecomposition:
    return CriticGapDecomposition.create(
        selection_sample_development_gain=0.30,
        fresh_sample_development_gain=0.18,
        acceptance_gain=0.12,
        null_estimate=SelectionNullEstimate(
            differential_estimate=0.04,
            interval_low=0.02,
            interval_high=0.06,
            monte_carlo_standard_error=0.005,
            resample_count=10_000,
            independent_selection_blocks=20,
            candidate_pool_width=16,
            evidence_sha256=_sha("selection-null-evidence"),
        ),
    )


def _costs() -> EvaluationCostBreakdown:
    zero = _zero_cost()
    return EvaluationCostBreakdown(
        candidate=CandidatePlaneCost(proposal=zero, execution=zero),
        critic_plane=CriticPlaneCost(
            development=zero,
            acceptance=zero,
            red_team=zero,
            monitor=zero,
            human_audit=zero,
        ),
    )


def _evaluate(
    *,
    integrity_checks: tuple[IntegrityCheck, ...],
    validity_evaluator: Callable[[], ValidityEvaluation],
    utility_evaluator: Callable[[ValidityEvaluation], UtilityEvaluation],
    critic_gap_evaluator: (Callable[[ValidityEvaluation, UtilityEvaluation], CriticGapDecomposition] | None) = None,
) -> EvaluationOutcome:
    return evaluate_with_integrity_gate(
        evaluation_plan_sha256=_sha("plan"),
        candidate_sha256=_sha("candidate"),
        evidence_set_sha256=_sha("evidence"),
        integrity_checks=integrity_checks,
        costs=_costs(),
        validity_evaluator=validity_evaluator,
        utility_evaluator=utility_evaluator,
        critic_gap_evaluator=critic_gap_evaluator,
    )


def test_integrity_failure_blocks_validity_scoring_and_promotion() -> None:
    calls: list[str] = []

    def validity_evaluator() -> ValidityEvaluation:
        calls.append("validity")
        return ValidityEvaluation(
            verifier_completed=True,
            output_parseable=True,
            schema_valid=True,
            output_contract_valid=True,
            valid=True,
        )

    def utility_evaluator(validity: ValidityEvaluation) -> UtilityEvaluation:
        calls.append("utility")
        return UtilityEvaluation(
            normalized_utility=1.0,
            reward=1.0,
            solved=True,
            acceptance_threshold_met=True,
        )

    def critic_gap_evaluator(
        validity: ValidityEvaluation,
        utility: UtilityEvaluation,
    ) -> CriticGapDecomposition:
        calls.append("critic_gap")
        return _critic_gap()

    outcome = _evaluate(
        integrity_checks=(
            IntegrityCheck(
                check_id="forbidden-flow",
                passed=False,
                evidence_sha256s=(_sha("flow-violation"),),
                reasons=("acceptance evidence reached proposal plane",),
            ),
        ),
        validity_evaluator=validity_evaluator,
        utility_evaluator=utility_evaluator,
        critic_gap_evaluator=critic_gap_evaluator,
    )

    assert calls == []
    assert outcome.validity is None
    assert outcome.utility is None
    assert outcome.disposition is EvaluationDisposition.EXPERIMENT_ERROR
    assert outcome.promotion_eligible is False


def test_valid_path_runs_integrity_then_validity_then_utility() -> None:
    calls: list[str] = []

    def validity_evaluator() -> ValidityEvaluation:
        calls.append("validity")
        return ValidityEvaluation(
            verifier_completed=True,
            output_parseable=True,
            schema_valid=True,
            output_contract_valid=True,
            valid=True,
        )

    def utility_evaluator(validity: ValidityEvaluation) -> UtilityEvaluation:
        assert validity.valid is True
        calls.append("utility")
        return UtilityEvaluation(
            normalized_utility=0.9,
            reward=0.9,
            solved=True,
            acceptance_threshold_met=True,
        )

    def critic_gap_evaluator(
        validity: ValidityEvaluation,
        utility: UtilityEvaluation,
    ) -> CriticGapDecomposition:
        assert validity.valid is True
        assert utility.acceptance_threshold_met is True
        calls.append("critic_gap")
        return _critic_gap()

    outcome = _evaluate(
        integrity_checks=(IntegrityCheck(check_id="forbidden-flow", passed=True),),
        validity_evaluator=validity_evaluator,
        utility_evaluator=utility_evaluator,
        critic_gap_evaluator=critic_gap_evaluator,
    )

    assert calls == ["validity", "utility", "critic_gap"]
    assert outcome.critic_gap is not None
    assert outcome.disposition is EvaluationDisposition.ACCEPT
    assert outcome.promotion_eligible is True


def test_verifier_complete_invalid_output_has_zero_utility_without_scoring() -> None:
    calls: list[str] = []

    def validity_evaluator() -> ValidityEvaluation:
        calls.append("validity")
        return ValidityEvaluation(
            verifier_completed=True,
            output_parseable=True,
            schema_valid=False,
            output_contract_valid=False,
            valid=False,
            reasons=("required evidence field missing",),
        )

    def utility_evaluator(validity: ValidityEvaluation) -> UtilityEvaluation:
        raise AssertionError(f"utility evaluator called for invalid output: {validity}")

    def critic_gap_evaluator(
        validity: ValidityEvaluation,
        utility: UtilityEvaluation,
    ) -> CriticGapDecomposition:
        calls.append("critic_gap")
        return _critic_gap()

    outcome = _evaluate(
        integrity_checks=(IntegrityCheck(check_id="forbidden-flow", passed=True),),
        validity_evaluator=validity_evaluator,
        utility_evaluator=utility_evaluator,
        critic_gap_evaluator=critic_gap_evaluator,
    )

    assert calls == ["validity"]
    assert outcome.validity is not None
    assert outcome.validity.valid is False
    assert outcome.utility is not None
    assert outcome.utility.normalized_utility == 0.0
    assert outcome.utility.reward == 0.0
    assert outcome.disposition is EvaluationDisposition.REJECT
    assert outcome.promotion_eligible is False


def test_incomplete_verifier_stops_before_utility() -> None:
    calls: list[str] = []

    def validity_evaluator() -> ValidityEvaluation:
        calls.append("validity")
        return ValidityEvaluation(
            verifier_completed=False,
            output_parseable=False,
            schema_valid=False,
            output_contract_valid=False,
            valid=False,
            reasons=("verifier did not complete",),
        )

    def utility_evaluator(validity: ValidityEvaluation) -> UtilityEvaluation:
        raise AssertionError(f"utility evaluator called before verifier completion: {validity}")

    def critic_gap_evaluator(
        validity: ValidityEvaluation,
        utility: UtilityEvaluation,
    ) -> CriticGapDecomposition:
        calls.append("critic_gap")
        return _critic_gap()

    outcome = _evaluate(
        integrity_checks=(IntegrityCheck(check_id="forbidden-flow", passed=True),),
        validity_evaluator=validity_evaluator,
        utility_evaluator=utility_evaluator,
        critic_gap_evaluator=critic_gap_evaluator,
    )

    assert calls == ["validity"]
    assert outcome.utility is None
    assert outcome.disposition is EvaluationDisposition.EXPERIMENT_ERROR
    assert outcome.promotion_eligible is False
