# ABOUTME: Evaluates integrity, validity, and utility in a fail-closed lexical order.
# ABOUTME: Prevents invalid evidence from reaching scoring or promotion decisions.

from __future__ import annotations

from collections.abc import Callable

from aec_bench.contracts.evaluation_outcome import (
    CriticGapDecomposition,
    EvaluationCostBreakdown,
    EvaluationDisposition,
    EvaluationOutcome,
    IntegrityCheck,
    IntegrityEvaluation,
    UtilityEvaluation,
    ValidityEvaluation,
)

ValidityEvaluator = Callable[[], ValidityEvaluation]
UtilityEvaluator = Callable[[ValidityEvaluation], UtilityEvaluation]
CriticGapEvaluator = Callable[
    [ValidityEvaluation, UtilityEvaluation],
    CriticGapDecomposition,
]


def evaluate_with_integrity_gate(
    *,
    evaluation_plan_sha256: str,
    candidate_sha256: str,
    evidence_set_sha256: str,
    integrity_checks: tuple[IntegrityCheck, ...],
    costs: EvaluationCostBreakdown,
    validity_evaluator: ValidityEvaluator,
    utility_evaluator: UtilityEvaluator,
    critic_gap_evaluator: CriticGapEvaluator | None = None,
) -> EvaluationOutcome:
    """Evaluate one candidate in integrity-before-validity-before-utility order."""
    integrity = IntegrityEvaluation.create(checks=integrity_checks)

    if not integrity.passed:
        return EvaluationOutcome(
            evaluation_plan_sha256=evaluation_plan_sha256,
            candidate_sha256=candidate_sha256,
            evidence_set_sha256=evidence_set_sha256,
            integrity=integrity,
            costs=costs,
            disposition=EvaluationDisposition.EXPERIMENT_ERROR,
            promotion_eligible=False,
            reasons=_integrity_failure_reasons(integrity),
        )

    validity = validity_evaluator()
    if not validity.verifier_completed:
        return EvaluationOutcome(
            evaluation_plan_sha256=evaluation_plan_sha256,
            candidate_sha256=candidate_sha256,
            evidence_set_sha256=evidence_set_sha256,
            integrity=integrity,
            validity=validity,
            costs=costs,
            disposition=EvaluationDisposition.EXPERIMENT_ERROR,
            promotion_eligible=False,
            reasons=validity.reasons,
        )

    if not validity.valid:
        return EvaluationOutcome(
            evaluation_plan_sha256=evaluation_plan_sha256,
            candidate_sha256=candidate_sha256,
            evidence_set_sha256=evidence_set_sha256,
            integrity=integrity,
            validity=validity,
            utility=UtilityEvaluation.zero(),
            costs=costs,
            disposition=EvaluationDisposition.REJECT,
            promotion_eligible=False,
            reasons=validity.reasons,
        )

    utility = utility_evaluator(validity)
    critic_gap = None if critic_gap_evaluator is None else critic_gap_evaluator(validity, utility)
    promotion_eligible = utility.acceptance_threshold_met
    return EvaluationOutcome(
        evaluation_plan_sha256=evaluation_plan_sha256,
        candidate_sha256=candidate_sha256,
        evidence_set_sha256=evidence_set_sha256,
        integrity=integrity,
        validity=validity,
        utility=utility,
        critic_gap=critic_gap,
        costs=costs,
        disposition=(EvaluationDisposition.ACCEPT if promotion_eligible else EvaluationDisposition.REJECT),
        promotion_eligible=promotion_eligible,
        reasons=(
            ("integrity, validity, and utility gates passed",) if promotion_eligible else ("utility threshold not met",)
        ),
    )


def _integrity_failure_reasons(
    integrity: IntegrityEvaluation,
) -> tuple[str, ...]:
    reasons = {
        f"{check.check_id}: {reason}" for check in integrity.checks if not check.passed for reason in check.reasons
    }
    return tuple(sorted(reasons))
