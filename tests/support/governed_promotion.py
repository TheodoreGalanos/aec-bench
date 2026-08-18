# ABOUTME: Builds complete provider-free governance chains for promotion integration tests.
# ABOUTME: Uses real contracts, monitor evaluation, ledger persistence, and authority replay without mock modes.

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pydantic import JsonValue

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    HumanAuthorityApproval,
    PromotionSubjectLineage,
    TaintLabel,
)
from aec_bench.contracts.evaluation_outcome import (
    CandidatePlaneCost,
    CriticEvaluationOutcome,
    CriticPlaneCost,
    EvaluationCostBreakdown,
    EvaluationDisposition,
    EvaluationOutcome,
    IntegrityCheck,
    IntegrityEvaluation,
    ResourceCost,
    UtilityEvaluation,
    ValidityEvaluation,
)
from aec_bench.contracts.evaluation_plane import Critic, EvaluationRegime
from aec_bench.contracts.evaluation_refs import CriticRef, CriticRole, EvaluationRegimeRef
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.evaluation.regime import expected_evaluation_regime_ref
from aec_bench.experimentation.governance.acceptance_manifest_escrow import escrow_acceptance_manifest
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger, StoredAuthorityEvent
from aec_bench.experimentation.governance.critic_lifecycle import release_acceptance_critic
from aec_bench.experimentation.governance.governance_gate import issue_governed_promotion
from aec_bench.experimentation.governance.motif_assurance import (
    MotifAssurancePin,
    MotifAssuranceSnapshot,
    motif_subject_sha256,
)
from aec_bench.experimentation.governance.motifs import HarnessProgramMotif
from aec_bench.experimentation.governance.standing_monitors import (
    CanaryCommitment,
    CanaryKind,
    CanaryObservation,
    CycleMonitorReport,
    StandingMonitorPlan,
    run_standing_monitors,
)
from tests.support.evaluation_regimes import make_regime


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


@dataclass(frozen=True)
class GovernedPromotionFixture:
    """Exact evidence returned by one complete test-only governed promotion."""

    promotion: StoredAuthorityEvent
    critic_outcome: CriticEvaluationOutcome
    assurance_snapshot: MotifAssuranceSnapshot | None
    assurance_pin: MotifAssurancePin | None


def issue_test_governed_promotion(
    *,
    ledger: AuthorityLedger,
    action: AuthorityAction,
    event_id: str,
    subject_id: str,
    subject_sha256: str,
    kernel_ref: KernelRef,
    kernel_abi_sha256: str,
    critic: CriticRef | None = None,
    critic_execution_principal_id: str | None = None,
    critic_release: StoredAuthorityEvent | None = None,
    candidate_sha256: str | None = None,
    motif: HarnessProgramMotif | None = None,
    motif_assurance_snapshot: MotifAssuranceSnapshot | None = None,
    motif_assurance_pin: MotifAssurancePin | None = None,
) -> GovernedPromotionFixture:
    """Issue one real provider-free promotion chain for downstream lifecycle tests."""

    if action in {
        AuthorityAction.MOTIF_PROMOTION,
        AuthorityAction.MOTIF_STATE_CHANGE,
    }:
        if motif is None:
            raise ValueError(f"{action.value} fixture requires the exact motif")
        if motif_subject_sha256(motif) != subject_sha256 or motif.kernel_abi_sha256 != kernel_abi_sha256:
            raise ValueError("motif fixture does not bind the requested subject and kernel")
        candidate_digest = motif.motif_sha256
    else:
        if motif is not None:
            raise ValueError("policy promotion fixture cannot carry a motif")
        candidate_digest = candidate_sha256 or subject_sha256
    if critic is None:
        regime = make_regime(regime_id=f"evaluation-regime.{event_id}")
        critic_spec = regime.critic(CriticRole.ACCEPTANCE)
        critic_ref = critic_spec.ref(expected_evaluation_regime_ref(regime))
    else:
        if critic_release is None:
            raise ValueError("a supplied critic reference requires its exact release authority")
        critic_ref = critic
    execution_principal_id = critic_execution_principal_id or f"critic-runtime.{event_id}"
    if critic_release is None:
        release = _release_critic(
            ledger=ledger,
            regime=regime,
            critic=critic_spec,
            critic_ref=critic_ref,
            event_id=event_id,
            kernel_ref=kernel_ref,
        )
    else:
        release = critic_release
    outcome = EvaluationOutcome(
        candidate_sha256=candidate_digest,
        evidence_set_sha256=_sha(f"evidence-set:{event_id}"),
        integrity=IntegrityEvaluation.create(
            checks=(IntegrityCheck(check_id="runtime-integrity", passed=True),),
        ),
        validity=ValidityEvaluation(
            verifier_completed=True,
            output_parseable=True,
            schema_valid=True,
            output_contract_valid=True,
            valid=True,
        ),
        utility=UtilityEvaluation(
            normalized_utility=1.0,
            reward=1.0,
            solved=True,
            acceptance_threshold_met=True,
        ),
        costs=_zero_costs(),
        disposition=EvaluationDisposition.ACCEPT,
        promotion_eligible=True,
        reasons=("provider-free governance fixture passed",),
    )
    bound_outcome = CriticEvaluationOutcome(
        evaluation_regime_ref=critic_ref.regime,
        critic=critic_ref,
        execution_principal_id=execution_principal_id,
        critic_release_authority_event_id=release.event.event_id,
        critic_release_authority_event_sha256=release.event.content_sha256,
        kernel_ref=kernel_ref,
        outcome=outcome,
    )
    outcome_basis = ledger.observe_model_basis(
        kind=BasisKind.CRITIC_EVALUATION_OUTCOME,
        artifact_id=f"critic-evaluation-outcome.{event_id}",
        model=bound_outcome,
        producer=AuthorityPrincipal(
            principal_id=execution_principal_id,
            kind=AuthorityPrincipalKind.CRITIC_AUTHORITY,
        ),
        producer_process_id="aecbench.provider-free-critic",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="provider-free-evaluation",
        operation_id="critic-evaluation",
        invocation_id=event_id,
        operation_taint=(
            TaintLabel.CRITIC_AUTHORITY,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )
    assurance_snapshot_sha256 = (
        _sha(f"policy-assurance-snapshot:{event_id}")
        if motif_assurance_snapshot is None
        else motif_assurance_snapshot.content_sha256
    )
    monitor_plan, monitor_report = _passing_monitor(
        event_id=event_id,
        evaluation_regime=bound_outcome.evaluation_regime_ref.authority_identity,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
    )
    lineage = None
    if motif is None and candidate_digest != subject_sha256:
        lineage = PromotionSubjectLineage(
            action=action,
            critic_evaluation_outcome=bound_outcome.authority_identity,
            candidate_sha256=candidate_digest,
            subject_id=subject_id,
            subject_sha256=subject_sha256,
            derivation_evidence_sha256s=(_sha(f"derivation:{event_id}"),),
        )
    promotion = issue_governed_promotion(
        ledger=ledger,
        action=action,
        event_id=event_id,
        subject_id=subject_id,
        subject_sha256=subject_sha256,
        kernel_ref=kernel_ref,
        kernel_abi_sha256=kernel_abi_sha256,
        evaluation_outcome=outcome_basis.reference,
        monitor_plan=monitor_plan,
        monitor_report=monitor_report,
        cycle_id=f"cycle.{event_id}",
        cycle_index=1,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        promotion_lineage=lineage,
        motif=motif,
        motif_assurance_pin=motif_assurance_pin,
        motif_assurance_snapshot=motif_assurance_snapshot,
    )
    return GovernedPromotionFixture(
        promotion=promotion,
        critic_outcome=bound_outcome,
        assurance_snapshot=motif_assurance_snapshot,
        assurance_pin=motif_assurance_pin,
    )


def _release_critic(
    *,
    ledger: AuthorityLedger,
    regime: EvaluationRegime,
    critic: Critic,
    critic_ref: CriticRef,
    event_id: str,
    kernel_ref: KernelRef,
) -> StoredAuthorityEvent:
    human = AuthorityPrincipal(
        principal_id="human.theo",
        kind=AuthorityPrincipalKind.HUMAN,
    )
    subject_id = f"{critic_ref.regime.regime_id}:{critic_ref.critic_id}"
    approval = HumanAuthorityApproval(
        approval_id=f"approval.release.{event_id}",
        principal=human,
        action=AuthorityAction.RELEASE_CRITIC,
        subject_id=subject_id,
        subject_sha256=critic_ref.regime.artifact.sha256,
        approved=True,
        reason="release the exact provider-free acceptance critic fixture",
    )
    approval_basis = ledger.observe_model_basis(
        kind=BasisKind.HUMAN_APPROVAL,
        artifact_id=approval.approval_id,
        model=approval,
        producer=human,
        producer_process_id="codex-desktop",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="human-approval",
        operation_id="release-critic",
        invocation_id=event_id,
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
    )
    escrow_acceptance_manifest(
        ledger=ledger,
        evaluation_regime=critic_ref.regime,
        critic_id=critic.critic_id,
        case_manifest={"case_ids": ["hidden-01", "hidden-02"]},
        scoring_policy={"threshold": 0.8},
        salt="test-acceptance-salt",
    )
    return release_acceptance_critic(
        ledger=ledger,
        evaluation_regime=regime,
        evaluation_regime_ref=critic_ref.regime,
        critic=critic,
        human_approval=approval_basis.reference,
        event_id=f"authority.release.{event_id}",
        kernel_ref=kernel_ref,
    )


def _passing_monitor(
    *,
    event_id: str,
    evaluation_regime: EvaluationRegimeRef,
    assurance_snapshot_sha256: str,
) -> tuple[StandingMonitorPlan, CycleMonitorReport]:
    payload: dict[str, JsonValue] = {
        "event_id": event_id,
        "marker": "intact",
    }
    canary = CanaryCommitment.create(
        canary_id=f"canary.{event_id}",
        kind=CanaryKind.ORDINARY_LEDGER,
        artifact_payload=payload,
    )
    plan = StandingMonitorPlan(
        monitor_id=f"monitor.{event_id}",
        version="1",
        evaluation_regime=evaluation_regime,
        canaries=(canary,),
    )
    report = run_standing_monitors(
        plan=plan,
        cycle_id=f"cycle.{event_id}",
        cycle_index=1,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        canary_observations=(
            CanaryObservation.observe(
                commitment=canary,
                observed_payload=payload,
                occurrence_count=1,
            ),
        ),
        flow_observations=(),
        basis_replay_observations=(),
    )
    return plan, report


def _zero_costs() -> EvaluationCostBreakdown:
    zero = ResourceCost(
        provider_calls=0,
        tokens=0,
        provider_cost_usd=0.0,
        wall_time_seconds=0.0,
    )
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
