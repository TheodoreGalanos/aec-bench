# ABOUTME: Tests fail-closed evaluation outcomes, critic-gap decomposition, and cost attribution.
# ABOUTME: Keeps selection noise, null-adjusted disagreement, common-mode breaches, and judging spend distinct.

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from aec_bench.contracts.evaluation_outcome import (
    CandidatePlaneCost,
    CommonModeBasis,
    CommonModeBasisKind,
    CriticEvaluationOutcome,
    CriticGapDecomposition,
    CriticPlaneCost,
    EvaluationCostBreakdown,
    EvaluationDisposition,
    EvaluationOutcome,
    IntegrityCheck,
    IntegrityEvaluation,
    ResourceCost,
    SelectionNullEstimate,
    UtilityEvaluation,
    ValidityEvaluation,
)
from aec_bench.contracts.evaluation_plane import (
    CriticRef,
    CriticRole,
    EvaluationPlanRef,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _resource(*, calls: int = 0, cost: float = 0.0) -> ResourceCost:
    return ResourceCost(
        provider_calls=calls,
        tokens=calls * 100,
        provider_cost_usd=cost,
        wall_time_seconds=float(calls),
    )


def _null_estimate() -> SelectionNullEstimate:
    return SelectionNullEstimate(
        differential_estimate=0.04,
        interval_low=-0.08,
        interval_high=0.16,
        null_envelope_coverage=0.95,
        monte_carlo_standard_error=0.005,
        resample_count=10_000,
        independent_selection_blocks=20,
        candidate_pool_width=16,
        evidence_sha256=_sha("selection-null-evidence"),
    )


def _costs() -> EvaluationCostBreakdown:
    return EvaluationCostBreakdown(
        candidate=CandidatePlaneCost(
            proposal=_resource(calls=1, cost=0.1),
            execution=_resource(calls=2, cost=0.9),
        ),
        critic_plane=CriticPlaneCost(
            development=_resource(calls=1, cost=0.2),
            acceptance=_resource(calls=2, cost=0.4),
            red_team=_resource(calls=1, cost=0.3),
            monitor=_resource(calls=1, cost=0.1),
            human_audit=_resource(calls=1, cost=0.5),
        ),
    )


def _validity(*, valid: bool = True) -> ValidityEvaluation:
    return ValidityEvaluation(
        verifier_completed=True,
        output_parseable=valid,
        schema_valid=valid,
        output_contract_valid=valid,
        valid=valid,
        reasons=() if valid else ("output contract failed",),
    )


def _utility(*, accepted: bool = True) -> UtilityEvaluation:
    score = 0.9 if accepted else 0.4
    return UtilityEvaluation(
        normalized_utility=score,
        reward=score,
        solved=accepted,
        acceptance_threshold_met=accepted,
    )


def test_critic_gap_separates_selection_optimism_residual_and_common_mode() -> None:
    gap = CriticGapDecomposition.create(
        selection_sample_development_gain=0.30,
        fresh_sample_development_gain=0.18,
        acceptance_gain=0.12,
        null_estimate=_null_estimate(),
        common_mode_basis=CommonModeBasis(
            kind=CommonModeBasisKind.EXECUTABLE_ANCHOR,
            basis_id="executable-anchor.drainage",
            basis_sha256=_sha("executable-anchor"),
            truth_gain=0.05,
        ),
    )

    assert gap.raw_critic_gap == pytest.approx(0.18)
    assert gap.selection_optimism == pytest.approx(0.12)
    assert gap.fresh_differential_gap == pytest.approx(0.06)
    assert gap.null_adjusted_residual == pytest.approx(0.02)
    assert gap.common_mode_breach == pytest.approx(0.07)
    payload = gap.model_dump(mode="json")
    assert "exploitation_gap" not in payload
    assert "seam_classification" not in payload
    assert "null_adjusted_seam_residual" not in payload


def test_selection_null_requires_uncertainty_resampling_and_pool_width() -> None:
    with pytest.raises(ValidationError):
        SelectionNullEstimate.model_validate(
            {
                "differential_estimate": 0.04,
                "evidence_sha256": _sha("point-estimate-only"),
            }
        )

    estimate = _null_estimate()
    assert estimate.null_envelope_coverage == pytest.approx(0.95)
    assert estimate.interval_low < estimate.differential_estimate < estimate.interval_high

    with pytest.raises(
        ValidationError,
        match="independent blocks cannot exceed resamples",
    ):
        SelectionNullEstimate(
            differential_estimate=0.0,
            interval_low=-0.1,
            interval_high=0.1,
            monte_carlo_standard_error=0.01,
            resample_count=1,
            independent_selection_blocks=2,
            candidate_pool_width=1,
            evidence_sha256=_sha("invalid-block-count"),
        )

    with pytest.raises(ValidationError):
        CriticGapDecomposition.model_validate(
            {
                "selection_sample_development_gain": 0.30,
                "fresh_sample_development_gain": 0.18,
                "acceptance_gain": 0.12,
                "null_estimate": 0.04,
                "raw_critic_gap": 0.18,
                "selection_optimism": 0.12,
                "fresh_differential_gap": 0.06,
                "null_adjusted_residual": 0.02,
            }
        )


def test_common_mode_breach_requires_executable_anchor_or_human_audit_basis() -> None:
    with pytest.raises(ValidationError, match="common-mode breach requires"):
        CriticGapDecomposition(
            selection_sample_development_gain=0.30,
            fresh_sample_development_gain=0.18,
            acceptance_gain=0.12,
            null_estimate=_null_estimate(),
            raw_critic_gap=0.18,
            selection_optimism=0.12,
            fresh_differential_gap=0.06,
            null_adjusted_residual=0.02,
            common_mode_breach=0.07,
        )


def test_candidate_and_critic_plane_costs_remain_separate() -> None:
    costs = _costs()

    assert costs.candidate_provider_cost_usd == pytest.approx(1.0)
    assert costs.critic_plane_provider_cost_usd == pytest.approx(1.5)
    assert costs.all_in_provider_cost_usd == pytest.approx(2.5)
    payload = costs.model_dump(mode="json")
    assert set(payload) >= {"candidate", "critic_plane"}
    assert payload["candidate"]["execution"]["provider_cost_usd"] == pytest.approx(0.9)
    assert payload["critic_plane"]["acceptance"]["provider_cost_usd"] == pytest.approx(0.4)


def test_critic_outcome_binds_exact_plan_critic_generation_and_release() -> None:
    outcome = EvaluationOutcome(
        evaluation_plan_sha256=_sha("plan"),
        candidate_sha256=_sha("candidate"),
        evidence_set_sha256=_sha("evidence"),
        integrity=IntegrityEvaluation.create(
            checks=(IntegrityCheck(check_id="runtime-integrity", passed=True),),
        ),
        validity=_validity(),
        utility=_utility(),
        costs=_costs(),
        disposition=EvaluationDisposition.ACCEPT,
        promotion_eligible=True,
        reasons=("acceptance threshold met",),
    )
    critic = CriticRef(
        critic_id="critic.acceptance",
        version="1",
        role=CriticRole.ACCEPTANCE,
        compatibility_generation="evaluation-generation.1",
        content_sha256=_sha("critic.acceptance"),
        acceptance_manifest_commitment_sha256=_sha("acceptance-commitment"),
    )
    binding = CriticEvaluationOutcome(
        evaluation_plan_ref=EvaluationPlanRef(
            plan_id="plan",
            evaluation_generation="evaluation-generation.1",
            content_sha256=outcome.evaluation_plan_sha256,
        ),
        critic=critic,
        execution_principal_id="critic-runtime.acceptance",
        critic_release_authority_event_id="authority.release.acceptance",
        critic_release_authority_event_sha256=_sha("authority.release.acceptance"),
        kernel_sha256=_sha("kernel"),
        outcome=outcome,
    )

    assert binding.outcome == outcome
    assert binding.critic == critic

    wrong_plan = binding.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    wrong_plan["evaluation_plan_ref"]["content_sha256"] = _sha("different-plan")
    with pytest.raises(ValidationError, match="exact evaluation plan"):
        CriticEvaluationOutcome.model_validate(wrong_plan)

    wrong_generation = binding.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    wrong_generation["critic"]["compatibility_generation"] = "evaluation-generation.2"
    with pytest.raises(ValidationError, match="generation differs"):
        CriticEvaluationOutcome.model_validate(wrong_generation)


def test_critic_ref_requires_role_appropriate_acceptance_commitment() -> None:
    with pytest.raises(ValidationError, match="acceptance critic requires"):
        CriticRef(
            critic_id="critic.acceptance",
            version="1",
            role=CriticRole.ACCEPTANCE,
            compatibility_generation="evaluation-generation.1",
            content_sha256=_sha("critic.acceptance"),
        )

    with pytest.raises(ValidationError, match="only acceptance critics"):
        CriticRef(
            critic_id="critic.development",
            version="1",
            role=CriticRole.DEVELOPMENT,
            compatibility_generation="evaluation-generation.1",
            content_sha256=_sha("critic.development"),
            acceptance_manifest_commitment_sha256=_sha("acceptance-commitment"),
        )


def test_integrity_failure_cannot_carry_validity_utility_or_promotion() -> None:
    integrity = IntegrityEvaluation.create(
        checks=(
            IntegrityCheck(
                check_id="forbidden-flow",
                passed=False,
                evidence_sha256s=(_sha("flow-violation"),),
                reasons=("acceptance evidence reached proposal plane",),
            ),
        )
    )

    with pytest.raises(ValidationError, match="integrity failure blocks"):
        EvaluationOutcome(
            evaluation_plan_sha256=_sha("plan"),
            candidate_sha256=_sha("candidate"),
            evidence_set_sha256=_sha("evidence"),
            integrity=integrity,
            validity=_validity(),
            utility=_utility(),
            costs=_costs(),
            disposition=EvaluationDisposition.ACCEPT,
            promotion_eligible=True,
            reasons=("injected success",),
        )
