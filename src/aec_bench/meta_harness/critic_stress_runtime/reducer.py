# ABOUTME: Reduces critic-stress evidence into causally grounded findings and regression cases.
# ABOUTME: Keeps classification provider-free and prevents red-team evidence from authorizing promotion.

from __future__ import annotations

from aec_bench.contracts.evaluation_outcome import CriticGapDecomposition

from .contracts import (
    AcceptanceGroundingKind,
    AdaptiveCriticStressMeasurement,
    AdaptiveCriticStressReport,
    CriticRegressionCase,
    CriticStressClassificationPolicy,
    CriticStressFinding,
    CriticStressFindingKind,
    CriticStressLimitation,
    ReplayedBoundaryEvidence,
    VerifiedCausalSeamEvidence,
    VRedChallengeEvidence,
)


def reduce_critic_stress(
    *,
    policy: CriticStressClassificationPolicy,
    measurement: AdaptiveCriticStressMeasurement,
    causal_seam_evidence: tuple[VerifiedCausalSeamEvidence, ...] = (),
    replayed_boundary_evidence: tuple[ReplayedBoundaryEvidence, ...] = (),
    vred_challenges: tuple[VRedChallengeEvidence, ...] = (),
    current_promotion_basis_sha256s: tuple[str, ...] = (),
) -> AdaptiveCriticStressReport:
    """Classify one raw measurement without provider work or self-authorized promotion."""
    selected_policy = CriticStressClassificationPolicy.model_validate(policy.model_dump(mode="python"))
    selected_measurement = AdaptiveCriticStressMeasurement.model_validate(measurement.model_dump(mode="python"))
    selected_causal = tuple(
        VerifiedCausalSeamEvidence.model_validate(item.model_dump(mode="python")) for item in causal_seam_evidence
    )
    selected_replayed = tuple(
        ReplayedBoundaryEvidence.model_validate(item.model_dump(mode="python")) for item in replayed_boundary_evidence
    )
    selected_challenges = tuple(
        VRedChallengeEvidence.model_validate(item.model_dump(mode="python")) for item in vred_challenges
    )
    finding, regression_case = derive_classification(
        policy=selected_policy,
        measurement=selected_measurement,
        causal_seam_evidence=selected_causal,
        replayed_boundary_evidence=selected_replayed,
    )
    limitations = (
        (CriticStressLimitation.HIDDEN_RUBRIC_CONDITIONAL_GAP,)
        if selected_measurement.acceptance_grounding.kind is AcceptanceGroundingKind.HIDDEN_RUBRIC
        else ()
    )
    return AdaptiveCriticStressReport(
        policy=selected_policy,
        measurement=selected_measurement,
        causal_seam_evidence=selected_causal,
        replayed_boundary_evidence=selected_replayed,
        vred_challenges=selected_challenges,
        finding=finding,
        regression_case=regression_case,
        limitations=limitations,
        current_promotion_basis_sha256s=current_promotion_basis_sha256s,
        next_generation_challenge_sha256s=tuple(challenge.content_sha256 for challenge in selected_challenges),
    )


def derive_classification(
    *,
    policy: CriticStressClassificationPolicy,
    measurement: AdaptiveCriticStressMeasurement,
    causal_seam_evidence: tuple[VerifiedCausalSeamEvidence, ...],
    replayed_boundary_evidence: tuple[ReplayedBoundaryEvidence, ...],
) -> tuple[CriticStressFinding, CriticRegressionCase | None]:
    """Derive a finding and optional regression case from already validated evidence."""
    gap = measurement.gap
    if replayed_boundary_evidence:
        kind = CriticStressFindingKind.INTEGRITY_BREACH
        evidence_sha256s = tuple(item.content_sha256 for item in replayed_boundary_evidence)
    elif gap.common_mode_breach is not None and gap.common_mode_breach > 0:
        if gap.common_mode_basis is None:  # pragma: no cover - enforced upstream
            raise ValueError("common-mode breach requires independent truth evidence")
        kind = CriticStressFindingKind.COMMON_MODE_SHARED_CRITIC_BREACH
        evidence_sha256s = (
            gap.content_sha256,
            gap.common_mode_basis.basis_sha256,
        )
    elif clears_residual_gate(policy, gap) and causal_seam_evidence:
        kind = CriticStressFindingKind.DIFFERENTIAL_SEAM
        evidence_sha256s = (
            gap.content_sha256,
            *(item.content_sha256 for item in causal_seam_evidence),
        )
    elif (
        gap.raw_critic_gap > 0
        and gap.null_estimate.interval_low <= gap.fresh_differential_gap <= gap.null_estimate.interval_high
    ):
        kind = CriticStressFindingKind.SELECTION_NOISE
        evidence_sha256s = (
            gap.content_sha256,
            gap.null_estimate.evidence_sha256,
        )
    else:
        kind = CriticStressFindingKind.INCONCLUSIVE
        evidence_sha256s = (gap.content_sha256,)

    regression_case_eligible = kind in {
        CriticStressFindingKind.DIFFERENTIAL_SEAM,
        CriticStressFindingKind.COMMON_MODE_SHARED_CRITIC_BREACH,
        CriticStressFindingKind.INTEGRITY_BREACH,
    }
    finding = CriticStressFinding(
        kind=kind,
        measurement_sha256=measurement.content_sha256,
        evidence_sha256s=evidence_sha256s,
        regression_case_eligible=regression_case_eligible,
        detail=kind.value,
    )
    if not regression_case_eligible:
        return finding, None
    return finding, CriticRegressionCase(
        case_id=f"critic-regression.{measurement.measurement_id}.{kind.value}",
        finding_sha256=finding.content_sha256,
        measurement_sha256=measurement.content_sha256,
        source_critic_generation_sha256=policy.current_critic_generation_sha256,
        target_critic_generation_sha256=policy.next_critic_generation_sha256,
        evidence_sha256s=finding.evidence_sha256s,
    )


def clears_residual_gate(
    policy: CriticStressClassificationPolicy,
    gap: CriticGapDecomposition,
) -> bool:
    """Return whether a differential gap clears the preregistered null residual gate."""
    return (
        gap.fresh_differential_gap > gap.null_estimate.interval_high
        and gap.null_adjusted_residual > policy.minimum_null_adjusted_residual
    )
