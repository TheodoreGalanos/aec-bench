# ABOUTME: Exercises causal critic-stress classification over immutable gap measurements.
# ABOUTME: Proves regression evidence is grounded and red-team challenges cannot promote themselves.

from __future__ import annotations

import hashlib

import pytest

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    OriginStamp,
    TaintLabel,
)
from aec_bench.contracts.evaluation_outcome import (
    CommonModeBasis,
    CommonModeBasisKind,
    CriticGapDecomposition,
    SelectionNullEstimate,
)
from aec_bench.meta_harness.critic_stress_runtime import (
    AcceptanceGrounding,
    AcceptanceGroundingKind,
    AdaptiveCriticStressMeasurement,
    CriticStressClassificationPolicy,
    CriticStressFindingKind,
    CriticStressLimitation,
    CriticStressMeasurement,
    CriticStressReport,
    ReplayedBoundaryEvidence,
    ReplayedBoundaryKind,
    VerifiedCausalSeamEvidence,
    VRedChallengeEvidence,
    reduce_critic_stress,
)
from aec_bench.meta_harness.critic_stress_runtime import (
    reduce_critic_stress as reduce_adaptive_critic_stress,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _null() -> SelectionNullEstimate:
    return SelectionNullEstimate(
        differential_estimate=0.0,
        interval_low=-0.05,
        interval_high=0.05,
        null_envelope_coverage=0.95,
        monte_carlo_standard_error=0.005,
        resample_count=1_000,
        independent_selection_blocks=100,
        candidate_pool_width=8,
        evidence_sha256=_sha("selection-null"),
    )


def _gap(
    *,
    selection_gain: float,
    fresh_gain: float,
    acceptance_gain: float,
    common_mode_basis: CommonModeBasis | None = None,
) -> CriticGapDecomposition:
    return CriticGapDecomposition.create(
        selection_sample_development_gain=selection_gain,
        fresh_sample_development_gain=fresh_gain,
        acceptance_gain=acceptance_gain,
        null_estimate=_null(),
        common_mode_basis=common_mode_basis,
    )


def _grounding(
    kind: AcceptanceGroundingKind = AcceptanceGroundingKind.EXECUTABLE_TRUTH,
) -> AcceptanceGrounding:
    return AcceptanceGrounding(
        kind=kind,
        basis_sha256=_sha(f"acceptance-grounding:{kind.value}"),
    )


def _measurement(
    gap: CriticGapDecomposition,
    *,
    grounding: AcceptanceGrounding | None = None,
) -> AdaptiveCriticStressMeasurement:
    return AdaptiveCriticStressMeasurement(
        measurement_id="critic-stress.measurement-001",
        critic_generation_sha256=_sha("critic-generation-current"),
        gap=gap,
        acceptance_grounding=grounding or _grounding(),
    )


def _policy() -> CriticStressClassificationPolicy:
    return CriticStressClassificationPolicy(
        policy_id="critic-stress.policy-001",
        current_critic_generation_sha256=_sha("critic-generation-current"),
        next_critic_generation_sha256=_sha("critic-generation-next"),
        minimum_null_adjusted_residual=0.10,
    )


def _challenge(
    policy: CriticStressClassificationPolicy,
    *,
    target_generation_sha256: str | None = None,
) -> VRedChallengeEvidence:
    artifact_sha256 = _sha("vred-challenge-artifact")
    challenge_id = "vred.challenge-001"
    origin = OriginStamp(
        artifact_id=challenge_id,
        artifact_sha256=artifact_sha256,
        producer=AuthorityPrincipal(
            principal_id="critic.red-team",
            kind=AuthorityPrincipalKind.RED_TEAM,
        ),
        producer_process_id="aecbench.adaptive-red-team",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="critic-stress",
        operation_id="propose-challenge",
        invocation_id="critic-stress.iteration-001",
        taint_labels=(TaintLabel.RUNTIME_OBSERVED,),
    )
    return VRedChallengeEvidence(
        challenge_id=challenge_id,
        artifact_sha256=artifact_sha256,
        origin=origin,
        source_critic_generation_sha256=policy.current_critic_generation_sha256,
        eligible_critic_generation_sha256=(target_generation_sha256 or policy.next_critic_generation_sha256),
    )


def test_evergreen_runtime_preserves_adaptive_schema_bytes_and_hashes() -> None:
    measurement = _measurement(
        _gap(
            selection_gain=0.50,
            fresh_gain=0.12,
            acceptance_gain=0.10,
        )
    )
    adaptive = reduce_adaptive_critic_stress(
        policy=_policy(),
        measurement=measurement,
    )
    evergreen = reduce_critic_stress(
        policy=_policy(),
        measurement=measurement,
    )

    assert CriticStressMeasurement is AdaptiveCriticStressMeasurement
    assert CriticStressReport is type(adaptive)
    assert evergreen == adaptive
    assert measurement.content_sha256 == "66e0073536aae3914e1edb56fcb7ed04fd920565749a273b3b194e74093f4a86"
    assert adaptive.content_sha256 == "63ae86526532b28ad1beec13f1234a9a29c4541191edfb6d3e82875b4ab26d45"
    assert hashlib.sha256(measurement.model_dump_json().encode()).hexdigest() == (
        "efc8bee8b0e371e2b193a7c132fe0ea8837b6fa80562627d9914a3fdcbd5a4a6"
    )
    assert hashlib.sha256(adaptive.model_dump_json().encode()).hexdigest() == (
        "57f79759f8ea349c90555658f2ceadb2d6c1efd65db6129726eccebd88d81f0a"
    )


def test_positive_raw_selection_noise_gap_does_not_create_a_regression_case() -> None:
    measurement = _measurement(
        _gap(
            selection_gain=0.50,
            fresh_gain=0.12,
            acceptance_gain=0.10,
        )
    )

    report = reduce_adaptive_critic_stress(
        policy=_policy(),
        measurement=measurement,
    )

    assert measurement.gap.raw_critic_gap > 0
    assert report.finding.kind is CriticStressFindingKind.SELECTION_NOISE
    assert report.regression_case is None


def test_residual_requires_causal_seam_evidence_before_becoming_a_regression() -> None:
    policy = _policy()
    measurement = _measurement(
        _gap(
            selection_gain=0.45,
            fresh_gain=0.40,
            acceptance_gain=0.10,
        )
    )
    challenge = _challenge(policy)

    detector_only = reduce_adaptive_critic_stress(
        policy=policy,
        measurement=measurement,
        vred_challenges=(challenge,),
    )
    assert detector_only.finding.kind is CriticStressFindingKind.INCONCLUSIVE
    assert detector_only.regression_case is None

    causal = VerifiedCausalSeamEvidence(
        evidence_id="causal-seam-001",
        measurement_sha256=measurement.content_sha256,
        challenge_artifact_sha256=challenge.artifact_sha256,
        candidate_action_sha256=_sha("candidate-action"),
        causal_replay_sha256=_sha("causal-replay"),
        seam_kind="acceptance-eligibility",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
    )
    grounded = reduce_adaptive_critic_stress(
        policy=policy,
        measurement=measurement,
        causal_seam_evidence=(causal,),
        vred_challenges=(challenge,),
    )

    assert grounded.finding.kind is CriticStressFindingKind.DIFFERENTIAL_SEAM
    assert grounded.regression_case is not None
    assert grounded.regression_case.target_critic_generation_sha256 == policy.next_critic_generation_sha256
    assert not grounded.regression_case.current_promotion_basis_permitted
    with pytest.raises(ValueError, match="forbidden as current promotion basis"):
        reduce_adaptive_critic_stress(
            policy=policy,
            measurement=measurement,
            causal_seam_evidence=(causal,),
            vred_challenges=(challenge,),
            current_promotion_basis_sha256s=(grounded.regression_case.content_sha256,),
        )


def test_near_zero_gap_with_independent_truth_credits_shared_critic_breach() -> None:
    truth = CommonModeBasis(
        kind=CommonModeBasisKind.EXECUTABLE_ANCHOR,
        basis_id="executable-task-truth",
        basis_sha256=_sha("executable-task-truth"),
        truth_gain=0.10,
    )
    measurement = _measurement(
        _gap(
            selection_gain=0.41,
            fresh_gain=0.40,
            acceptance_gain=0.39,
            common_mode_basis=truth,
        )
    )

    report = reduce_adaptive_critic_stress(
        policy=_policy(),
        measurement=measurement,
    )

    assert abs(measurement.gap.fresh_differential_gap) < 0.05
    assert measurement.gap.common_mode_breach == pytest.approx(0.29)
    assert report.finding.kind is CriticStressFindingKind.COMMON_MODE_SHARED_CRITIC_BREACH
    assert report.regression_case is not None
    assert truth.basis_sha256 in report.regression_case.evidence_sha256s


def test_replayed_forbidden_flow_creates_an_integrity_regression() -> None:
    policy = _policy()
    measurement = _measurement(
        _gap(
            selection_gain=0.20,
            fresh_gain=0.10,
            acceptance_gain=0.10,
        )
    )
    replay = ReplayedBoundaryEvidence(
        evidence_id="forbidden-flow-replay-001",
        kind=ReplayedBoundaryKind.FORBIDDEN_FLOW,
        measurement_sha256=measurement.content_sha256,
        replay_evidence_sha256=_sha("forbidden-flow-replay"),
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
    )

    report = reduce_adaptive_critic_stress(
        policy=policy,
        measurement=measurement,
        replayed_boundary_evidence=(replay,),
    )

    assert report.finding.kind is CriticStressFindingKind.INTEGRITY_BREACH
    assert report.regression_case is not None


def test_hidden_rubric_acceptance_records_the_conditional_gap_limitation() -> None:
    measurement = _measurement(
        _gap(
            selection_gain=0.50,
            fresh_gain=0.12,
            acceptance_gain=0.10,
        ),
        grounding=_grounding(AcceptanceGroundingKind.HIDDEN_RUBRIC),
    )

    report = reduce_adaptive_critic_stress(
        policy=_policy(),
        measurement=measurement,
    )

    assert CriticStressLimitation.HIDDEN_RUBRIC_CONDITIONAL_GAP in report.limitations
    assert report.finding.kind is CriticStressFindingKind.SELECTION_NOISE


def test_vred_challenge_cannot_support_current_promotion_or_skip_a_generation() -> None:
    policy = _policy()
    measurement = _measurement(
        _gap(
            selection_gain=0.50,
            fresh_gain=0.12,
            acceptance_gain=0.10,
        )
    )
    challenge = _challenge(policy)

    with pytest.raises(ValueError, match="forbidden as current promotion basis"):
        reduce_adaptive_critic_stress(
            policy=policy,
            measurement=measurement,
            vred_challenges=(challenge,),
            current_promotion_basis_sha256s=(challenge.artifact_sha256,),
        )

    later_challenge = _challenge(
        policy,
        target_generation_sha256=_sha("critic-generation-after-next"),
    )
    with pytest.raises(ValueError, match="next critic generation"):
        reduce_adaptive_critic_stress(
            policy=policy,
            measurement=measurement,
            vred_challenges=(later_challenge,),
        )
