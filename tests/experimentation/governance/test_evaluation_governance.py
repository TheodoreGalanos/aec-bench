# ABOUTME: Integrates evaluation outcomes, standing monitors, and authority-ledger promotion gates.
# ABOUTME: Proves monitor incidents preserve evidence while leaving durable promotion authority absent.

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import JsonValue

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    HumanAuthorityApproval,
    MotifPromotionQualification,
    PromotionMonitorAttestation,
    PromotionSubjectLineage,
    TaintLabel,
)
from aec_bench.contracts.evaluation_outcome import (
    CandidatePlaneCost,
    CriticEvaluationOutcome,
    CriticPlaneCost,
    EvaluationCostBreakdown,
    EvaluationOutcome,
    IntegrityCheck,
    ResourceCost,
    UtilityEvaluation,
    ValidityEvaluation,
)
from aec_bench.contracts.evaluation_refs import CriticRef, CriticRole, EvaluationRegimeRef
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.evaluation.integrity_gate import evaluate_with_integrity_gate
from aec_bench.evaluation.regime import expected_evaluation_regime_ref
from aec_bench.experimentation.governance.acceptance_manifest_escrow import escrow_acceptance_manifest
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
    StoredBasis,
)
from aec_bench.experimentation.governance.critic_lifecycle import release_critic
from aec_bench.experimentation.governance.governance_gate import (
    GovernedPromotionError,
    issue_governed_production_promotion,
    issue_governed_promotion,
)
from aec_bench.experimentation.governance.motif_assurance import (
    MotifAssuranceEntry,
    MotifAssuranceLedger,
    MotifAssurancePin,
    MotifAssuranceSnapshot,
    MotifAssuranceState,
    MotifLifecycleEvent,
    append_authorized_motif_event,
    apply_governed_motif_promotion,
    derive_motif_assurance_snapshot,
    motif_subject_sha256,
)
from aec_bench.experimentation.governance.motifs import (
    HarnessProgramMotif,
    MotifStatus,
    decide_motif_promotion,
)
from aec_bench.experimentation.governance.motifs.promotion import apply_authorized_motif_promotion
from aec_bench.experimentation.governance.standing_monitors import (
    CanaryCommitment,
    CanaryKind,
    CanaryObservation,
    CycleMonitorPlan,
    CycleMonitorReport,
    FlowAction,
    FlowSurface,
    MonitorCoverageAttestation,
    ProductionCycleMonitorEnvelope,
    RuntimeFlowObservation,
    StandingMonitorPlan,
    StandingMonitorPolicy,
    default_forbidden_flow_rules,
    run_production_cycle_monitors,
    run_standing_monitors,
)
from tests.experimentation.governance.test_motif_library import _motif, _policy, _transfer
from tests.support.evaluation_regimes import make_regime


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _kernel_ref() -> KernelRef:
    return KernelRef(kernel_id="aec-bench.adaptive-harness", version="1.6.0")


def _evaluation_regime_identity() -> EvaluationRegimeRef:
    return expected_evaluation_regime_ref(make_regime())


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


def _accepted_outcome(*, candidate_sha256: str | None = None) -> EvaluationOutcome:
    return evaluate_with_integrity_gate(
        candidate_sha256=candidate_sha256 or _sha("candidate"),
        evidence_set_sha256=_sha("evidence"),
        integrity_checks=(IntegrityCheck(check_id="runtime-integrity", passed=True),),
        costs=_zero_costs(),
        validity_evaluator=lambda: ValidityEvaluation(
            verifier_completed=True,
            output_parseable=True,
            schema_valid=True,
            output_contract_valid=True,
            valid=True,
        ),
        utility_evaluator=lambda validity: UtilityEvaluation(
            normalized_utility=0.9,
            reward=0.9,
            solved=validity.valid,
            acceptance_threshold_met=True,
        ),
    )


def _recorded_critic_outcome(
    ledger: AuthorityLedger,
    *,
    role: CriticRole = CriticRole.ACCEPTANCE,
    candidate_sha256: str | None = None,
    suffix: str | None = None,
) -> tuple[StoredBasis, CriticEvaluationOutcome]:
    outcome = _accepted_outcome(candidate_sha256=candidate_sha256)
    selected_suffix = suffix or role.value
    regime = make_regime()
    regime_ref = expected_evaluation_regime_ref(regime)
    critic_spec = regime.critic(role)
    critic = critic_spec.ref(regime_ref)
    human = AuthorityPrincipal(
        principal_id="human.theo",
        kind=AuthorityPrincipalKind.HUMAN,
    )
    subject_id = f"{regime_ref.regime_id}:{critic.critic_id}"
    approval = HumanAuthorityApproval(
        approval_id=f"approval.release.{selected_suffix}",
        principal=human,
        action=AuthorityAction.RELEASE_CRITIC,
        subject_id=subject_id,
        subject_sha256=regime_ref.artifact.sha256,
        approved=True,
        reason="release exact regime critic for governed evaluation",
    )
    approval_basis = ledger.observe_model_basis(
        kind=BasisKind.HUMAN_APPROVAL,
        artifact_id=approval.approval_id,
        model=approval,
        producer=human,
        producer_process_id="aecbench.human-approval",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="human-approval",
        operation_id="release-critic",
        invocation_id=approval.approval_id,
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
    )
    if role is CriticRole.ACCEPTANCE:
        escrow_acceptance_manifest(
            ledger=ledger,
            evaluation_regime=regime_ref,
            critic_id=critic.critic_id,
            case_manifest={"case_ids": ["hidden-01", "hidden-02"]},
            scoring_policy={"threshold": 0.8},
            salt="test-acceptance-salt",
        )
    stored_release = release_critic(
        ledger=ledger,
        evaluation_regime=regime,
        evaluation_regime_ref=regime_ref,
        critic=critic_spec,
        human_approval=approval_basis.reference,
        event_id=f"authority.release.{selected_suffix}",
        kernel_ref=_kernel_ref(),
    )
    bound = CriticEvaluationOutcome(
        evaluation_regime_ref=regime_ref,
        critic=critic,
        execution_principal_id=f"critic-runtime.{role.value}",
        critic_release_authority_event_id=stored_release.event.event_id,
        critic_release_authority_event_sha256=(stored_release.event.content_sha256),
        kernel_ref=_kernel_ref(),
        outcome=outcome,
    )
    stored = ledger.observe_model_basis(
        kind=BasisKind.CRITIC_EVALUATION_OUTCOME,
        artifact_id=f"evaluation-outcome.{selected_suffix}",
        model=bound,
        producer=AuthorityPrincipal(
            principal_id=bound.execution_principal_id,
            kind=AuthorityPrincipalKind.CRITIC_AUTHORITY,
        ),
        producer_process_id=f"aecbench.{role.value}-evaluator",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel=f"{role.value}-evaluation",
        operation_id=f"{role.value}-evaluation",
        invocation_id=f"evaluation.{selected_suffix}",
        operation_taint=(
            TaintLabel.CRITIC_AUTHORITY,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )
    return stored, bound


def _monitor_plan() -> StandingMonitorPlan:
    motif = CanaryCommitment.create(
        canary_id="canary.motif.revoked-attractive",
        kind=CanaryKind.MOTIF,
        artifact_payload={
            "motif_subject_sha256": _sha("motif-subject"),
            "effective_state": "revoked",
        },
        expected_effective_state="revoked",
    )
    ordinary_ledger = CanaryCommitment.create(
        canary_id="canary.ordinary-ledger.authority-shaped",
        kind=CanaryKind.ORDINARY_LEDGER,
        artifact_payload={
            "stage": "authority_event",
            "status": "granted",
        },
    )
    return StandingMonitorPlan(
        monitor_id="monitor.governed-cycle",
        version="1.0.0",
        evaluation_regime=_evaluation_regime_identity(),
        canaries=(motif, ordinary_ledger),
        forbidden_flow_rules=default_forbidden_flow_rules(),
        report_validity_cycles=1,
    )


def _monitor_policy() -> StandingMonitorPolicy:
    legacy = _monitor_plan()
    return StandingMonitorPolicy(
        monitor_id=legacy.monitor_id,
        version="2.0.0",
        canaries=legacy.canaries,
        forbidden_flow_rules=legacy.forbidden_flow_rules,
        report_validity_cycles=legacy.report_validity_cycles,
    )


def _canary_observations(
    plan: StandingMonitorPlan | StandingMonitorPolicy,
    *,
    ordinary_ledger_referenced: bool = False,
) -> tuple[CanaryObservation, ...]:
    payloads: dict[CanaryKind, JsonValue] = {
        CanaryKind.MOTIF: {
            "motif_subject_sha256": _sha("motif-subject"),
            "effective_state": "revoked",
        },
        CanaryKind.ORDINARY_LEDGER: {
            "stage": "authority_event",
            "status": "granted",
        },
    }
    return tuple(
        CanaryObservation.observe(
            commitment=commitment,
            observed_payload=payloads[commitment.kind],
            occurrence_count=1,
            referenced=(ordinary_ledger_referenced and commitment.kind is CanaryKind.ORDINARY_LEDGER),
            observed_effective_state=("revoked" if commitment.kind is CanaryKind.MOTIF else None),
        )
        for commitment in plan.canaries
    )


def _ledger(tmp_path: Path) -> AuthorityLedger:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    return AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
        typed_basis_models={BasisKind.MONITOR_REPORT: CycleMonitorReport},
    )


def _production_ledger(tmp_path: Path) -> AuthorityLedger:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    return AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
        typed_basis_models={BasisKind.MONITOR_REPORT: ProductionCycleMonitorEnvelope},
    )


def _production_cycle(
    policy: StandingMonitorPolicy,
    *,
    coverage_complete: bool = True,
) -> ProductionCycleMonitorEnvelope:
    cycle_plan = CycleMonitorPlan(
        cycle_id="cycle.010",
        cycle_index=10,
        evaluation_regime=_evaluation_regime_identity(),
        standing_policy_sha256=policy.content_sha256,
        assurance_snapshot_sha256=_sha("assurance-snapshot"),
    )
    coverage = MonitorCoverageAttestation(
        cycle_monitor_plan_sha256=cycle_plan.content_sha256,
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        collection_complete=coverage_complete,
        covered_canary_commitment_sha256s=tuple(canary.content_sha256 for canary in policy.canaries),
        covered_forbidden_flow_rules=policy.forbidden_flow_rules,
        covered_basis_replay_requirement_sha256s=(),
        evidence_sha256=_sha("host-monitor-collection"),
    )
    return run_production_cycle_monitors(
        policy=policy,
        cycle_plan=cycle_plan,
        coverage_attestation=coverage,
        canary_observations=_canary_observations(policy),
        flow_observations=(),
        basis_replay_observations=(),
    )


def test_promotion_authority_requires_current_monitor_and_accepted_evaluation(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    plan = _monitor_plan()
    outcome_basis, critic_outcome = _recorded_critic_outcome(ledger)
    assurance_sha256 = _sha("assurance-snapshot")
    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.001",
        cycle_index=1,
        assurance_snapshot_sha256=assurance_sha256,
        canary_observations=_canary_observations(plan),
        flow_observations=(),
        basis_replay_observations=(),
    )

    promoted = issue_governed_promotion(
        ledger=ledger,
        action=AuthorityAction.POLICY_PROMOTION,
        event_id="authority.promote-policy-001",
        subject_id="candidate",
        subject_sha256=critic_outcome.outcome.candidate_sha256,
        kernel_ref=_kernel_ref(),
        kernel_abi_sha256=_sha("kernel"),
        evaluation_outcome=outcome_basis.reference,
        monitor_plan=plan,
        monitor_report=report,
        cycle_id="cycle.001",
        cycle_index=1,
        assurance_snapshot_sha256=assurance_sha256,
    )

    assert {item.kind for item in promoted.event.basis} == {
        BasisKind.CRITIC_EVALUATION_OUTCOME,
        BasisKind.AUTHORITY_EVENT,
        BasisKind.MONITOR_REPORT,
        BasisKind.PROMOTION_MONITOR,
        BasisKind.PROMOTION_LINEAGE,
    }
    assert (
        ledger.resolve_authority_event(
            event_id=promoted.event.event_id,
            content_sha256=promoted.event.content_sha256,
        )
        == promoted
    )


def test_raw_ledger_rejects_monitor_attestation_for_a_different_report(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    plan = _monitor_plan()
    outcome_basis, critic_outcome = _recorded_critic_outcome(ledger)
    assurance_sha256 = _sha("assurance-snapshot")
    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.monitor-join",
        cycle_index=1,
        assurance_snapshot_sha256=assurance_sha256,
        canary_observations=_canary_observations(plan),
        flow_observations=(),
        basis_replay_observations=(),
    )
    promoted = issue_governed_promotion(
        ledger=ledger,
        action=AuthorityAction.POLICY_PROMOTION,
        event_id="authority.monitor-join.valid",
        subject_id="candidate",
        subject_sha256=critic_outcome.outcome.candidate_sha256,
        kernel_ref=_kernel_ref(),
        kernel_abi_sha256=_sha("kernel"),
        evaluation_outcome=outcome_basis.reference,
        monitor_plan=plan,
        monitor_report=report,
        cycle_id="cycle.monitor-join",
        cycle_index=1,
        assurance_snapshot_sha256=assurance_sha256,
    )
    references = {reference.kind: reference for reference in promoted.event.basis}
    _, original_attestation = ledger.resolve_model_basis(
        references[BasisKind.PROMOTION_MONITOR],
        PromotionMonitorAttestation,
    )
    bad_attestation = PromotionMonitorAttestation(
        monitor_basis_sha256=original_attestation.monitor_basis_sha256,
        monitor_report_sha256=_sha("different-monitor-report"),
        evaluation_regime=original_attestation.evaluation_regime,
        assurance_snapshot_sha256=original_attestation.assurance_snapshot_sha256,
        cycle_id=original_attestation.cycle_id,
        cycle_index=original_attestation.cycle_index,
    )
    bad_basis = ledger.observe_model_basis(
        kind=BasisKind.PROMOTION_MONITOR,
        artifact_id="promotion-monitor.authority.monitor-join.bad",
        model=bad_attestation,
        producer=AuthorityPrincipal(
            principal_id="host.promotion-policy",
            kind=AuthorityPrincipalKind.HOST_POLICY,
        ),
        producer_process_id="aecbench.promotion-policy",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="monitor-gate",
        operation_id="promotion-monitor-attestation",
        invocation_id="authority.monitor-join.bad",
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    bad_event = AuthorityEvent(
        event_id="authority.monitor-join.bad",
        principal=promoted.event.principal,
        action=promoted.event.action,
        decision=promoted.event.decision,
        subject_id=promoted.event.subject_id,
        subject_sha256=promoted.event.subject_sha256,
        basis=tuple(
            bad_basis.reference if reference.kind is BasisKind.PROMOTION_MONITOR else reference
            for reference in promoted.event.basis
        ),
        kernel_ref=promoted.event.kernel_ref,
        critic=promoted.event.critic,
        reasons=promoted.event.reasons,
        revalidation_triggers=promoted.event.revalidation_triggers,
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="monitor report"):
        ledger.issue_authority_event(bad_event)


def test_first_motif_promotion_derives_independent_qualification_without_assurance(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    plan = _monitor_plan()
    provisional = _motif(status=MotifStatus.PROVISIONAL)
    subject_sha256 = motif_subject_sha256(provisional)
    outcome_basis, critic_outcome = _recorded_critic_outcome(
        ledger,
        candidate_sha256=provisional.motif_sha256,
    )
    monitor_state_sha256 = _sha("pre-promotion-monitor-state")
    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.motif-promotion",
        cycle_index=2,
        assurance_snapshot_sha256=monitor_state_sha256,
        canary_observations=_canary_observations(plan),
        flow_observations=(),
        basis_replay_observations=(),
    )

    promoted = issue_governed_promotion(
        ledger=ledger,
        action=AuthorityAction.MOTIF_PROMOTION,
        event_id="authority.promote-motif-001",
        subject_id="motif.review-first",
        subject_sha256=subject_sha256,
        kernel_ref=_kernel_ref(),
        kernel_abi_sha256=provisional.kernel_abi_sha256,
        evaluation_outcome=outcome_basis.reference,
        monitor_plan=plan,
        monitor_report=report,
        cycle_id="cycle.motif-promotion",
        cycle_index=2,
        assurance_snapshot_sha256=monitor_state_sha256,
        motif=provisional,
    )

    assert {item.kind for item in promoted.event.basis} == {
        BasisKind.AUTHORITY_EVENT,
        BasisKind.CRITIC_EVALUATION_OUTCOME,
        BasisKind.MONITOR_REPORT,
        BasisKind.MOTIF_QUALIFICATION,
        BasisKind.PROMOTION_LINEAGE,
        BasisKind.PROMOTION_MONITOR,
    }
    references = {item.kind: item for item in promoted.event.basis}
    qualification_basis, qualification = ledger.resolve_model_basis(
        references[BasisKind.MOTIF_QUALIFICATION],
        MotifPromotionQualification,
    )
    _, lineage = ledger.resolve_model_basis(
        references[BasisKind.PROMOTION_LINEAGE],
        PromotionSubjectLineage,
    )
    _, monitor = ledger.resolve_model_basis(
        references[BasisKind.PROMOTION_MONITOR],
        PromotionMonitorAttestation,
    )

    assert qualification.provisional_motif_sha256 == provisional.motif_sha256
    assert qualification.motif_subject_sha256 == subject_sha256
    assert qualification.critic_evaluation_outcome == critic_outcome.authority_identity
    assert qualification.promotion_lineage_sha256 == lineage.content_sha256
    assert qualification.promotion_monitor_attestation_sha256 == monitor.content_sha256
    assert qualification.critic_release_authority_event_sha256 == critic_outcome.critic_release_authority_event_sha256
    assert qualification.critic == critic_outcome.critic.authority_identity
    assert qualification.kernel_ref == _kernel_ref()
    assert qualification.kernel_abi_sha256 == provisional.kernel_abi_sha256
    assert qualification_basis.origin.parent_origin_sha256s == tuple(
        sorted(
            ledger.resolve_basis(reference).origin.content_sha256
            for kind, reference in references.items()
            if kind is not BasisKind.MOTIF_QUALIFICATION
        )
    )

    policy = _policy()
    promoted_motif = apply_governed_motif_promotion(
        provisional,
        decide_motif_promotion(provisional, MotifStatus.REUSABLE, policy),
        policy,
        authority_ledger=ledger,
        authority_event_sha256=promoted.event.content_sha256,
    )
    assert promoted_motif.status is MotifStatus.REUSABLE
    assert promoted_motif.parent_motif_sha256 == provisional.motif_sha256


def test_candidate_authored_motif_qualification_cannot_authorize_promotion(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    plan = _monitor_plan()
    provisional = _motif(status=MotifStatus.PROVISIONAL)
    subject_sha256 = motif_subject_sha256(provisional)
    outcome_basis, _ = _recorded_critic_outcome(
        ledger,
        candidate_sha256=provisional.motif_sha256,
    )
    monitor_state_sha256 = _sha("candidate-qualification-monitor-state")
    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.candidate-qualification",
        cycle_index=2,
        assurance_snapshot_sha256=monitor_state_sha256,
        canary_observations=_canary_observations(plan),
        flow_observations=(),
        basis_replay_observations=(),
    )
    promoted = issue_governed_promotion(
        ledger=ledger,
        action=AuthorityAction.MOTIF_PROMOTION,
        event_id="authority.promote-motif-candidate-qualification",
        subject_id="motif.review-first",
        subject_sha256=subject_sha256,
        kernel_ref=_kernel_ref(),
        kernel_abi_sha256=provisional.kernel_abi_sha256,
        evaluation_outcome=outcome_basis.reference,
        monitor_plan=plan,
        monitor_report=report,
        cycle_id="cycle.candidate-qualification",
        cycle_index=2,
        assurance_snapshot_sha256=monitor_state_sha256,
        motif=provisional,
    )
    qualification_reference = next(
        reference for reference in promoted.event.basis if reference.kind is BasisKind.MOTIF_QUALIFICATION
    )
    _, qualification = ledger.resolve_model_basis(
        qualification_reference,
        MotifPromotionQualification,
    )
    candidate_qualification = ledger.observe_model_basis(
        kind=BasisKind.MOTIF_QUALIFICATION,
        artifact_id="candidate-authored-motif-qualification",
        model=qualification,
        producer=AuthorityPrincipal(
            principal_id="candidate.optimizer",
            kind=AuthorityPrincipalKind.CANDIDATE,
        ),
        producer_process_id="candidate-process",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="candidate-output",
        operation_id="propose-qualification",
        invocation_id="candidate-qualification",
        operation_taint=(
            TaintLabel.CANDIDATE_AUTHORED,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )
    shaped_event = AuthorityEvent(
        event_id="authority.promote-motif-candidate-shaped",
        principal=promoted.event.principal,
        action=promoted.event.action,
        decision=promoted.event.decision,
        subject_id=promoted.event.subject_id,
        subject_sha256=promoted.event.subject_sha256,
        basis=tuple(
            candidate_qualification.reference if reference.kind is BasisKind.MOTIF_QUALIFICATION else reference
            for reference in promoted.event.basis
        ),
        kernel_ref=promoted.event.kernel_ref,
        critic=promoted.event.critic,
        reasons=promoted.event.reasons,
        revalidation_triggers=promoted.event.revalidation_triggers,
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="does not recompute"):
        ledger.issue_authority_event(shaped_event)

    caller_asserted_qualification = ledger.observe_model_basis(
        kind=BasisKind.MOTIF_QUALIFICATION,
        artifact_id="caller-asserted-motif-qualification",
        model=qualification,
        producer=AuthorityPrincipal(
            principal_id="host.promotion-policy",
            kind=AuthorityPrincipalKind.HOST_POLICY,
        ),
        producer_process_id="caller-process",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="caller-input",
        operation_id="assert-qualification",
        invocation_id="caller-qualification",
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    caller_shaped_event = AuthorityEvent(
        event_id="authority.promote-motif-caller-shaped",
        principal=promoted.event.principal,
        action=promoted.event.action,
        decision=promoted.event.decision,
        subject_id=promoted.event.subject_id,
        subject_sha256=promoted.event.subject_sha256,
        basis=tuple(
            caller_asserted_qualification.reference if reference.kind is BasisKind.MOTIF_QUALIFICATION else reference
            for reference in promoted.event.basis
        ),
        kernel_ref=promoted.event.kernel_ref,
        critic=promoted.event.critic,
        reasons=promoted.event.reasons,
        revalidation_triggers=promoted.event.revalidation_triggers,
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="does not recompute"):
        ledger.issue_authority_event(caller_shaped_event)


def test_motif_state_change_requires_current_assurance_and_complete_authority_chain(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    plan = _monitor_plan()
    policy = _policy()
    provisional = _motif(status=MotifStatus.PROVISIONAL)
    subject_sha256 = motif_subject_sha256(provisional)
    promotion_outcome_basis, _ = _recorded_critic_outcome(
        ledger,
        candidate_sha256=provisional.motif_sha256,
        suffix="motif-initial",
    )
    initial_monitor_state = _sha("initial-monitor-state")
    initial_report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.motif-initial",
        cycle_index=1,
        assurance_snapshot_sha256=initial_monitor_state,
        canary_observations=_canary_observations(plan),
        flow_observations=(),
        basis_replay_observations=(),
    )
    promotion = issue_governed_promotion(
        ledger=ledger,
        action=AuthorityAction.MOTIF_PROMOTION,
        event_id="authority.motif-initial",
        subject_id="motif.review-first",
        subject_sha256=subject_sha256,
        kernel_ref=_kernel_ref(),
        kernel_abi_sha256=provisional.kernel_abi_sha256,
        evaluation_outcome=promotion_outcome_basis.reference,
        monitor_plan=plan,
        monitor_report=initial_report,
        cycle_id="cycle.motif-initial",
        cycle_index=1,
        assurance_snapshot_sha256=initial_monitor_state,
        motif=provisional,
    )
    assurance = append_authorized_motif_event(
        MotifAssuranceLedger.create(),
        MotifLifecycleEvent(
            event_id="motif-lifecycle.initial",
            motif_subject_sha256=subject_sha256,
            state=MotifAssuranceState.ACTIVE,
            cause="governed_promotion",
            authority_event_sha256=promotion.event.content_sha256,
            kernel_ref=_kernel_ref(),
            kernel_abi_sha256=provisional.kernel_abi_sha256,
            critic=promotion.event.critic,
            applicability_sha256=_sha("motif-applicability"),
        ),
        authority_ledger=ledger,
    )
    snapshot = derive_motif_assurance_snapshot(assurance)
    reusable = apply_authorized_motif_promotion(
        provisional,
        decide_motif_promotion(provisional, MotifStatus.REUSABLE, policy),
        policy,
    )
    pin = MotifAssurancePin.create(
        selection_id="selection.transfer-validation",
        selected_motif_sha256=reusable.motif_sha256,
        motif_subject_sha256=subject_sha256,
        snapshot=snapshot,
    )
    enriched = HarnessProgramMotif.create(
        status=MotifStatus.REUSABLE,
        kernel_abi_sha256=reusable.kernel_abi_sha256,
        hx_template=reusable.hx_template,
        px_template=reusable.px_template,
        applicability=reusable.applicability,
        descriptor=reusable.descriptor,
        accepted_repair_refs=reusable.accepted_repair_refs,
        harness_program_evidence_refs=reusable.harness_program_evidence_refs,
        quality_evidence_refs=reusable.quality_evidence_refs,
        transfer_evidence_refs=(_transfer(),),
        parent_motif_sha256=reusable.motif_sha256,
    )
    state_outcome_basis, _ = _recorded_critic_outcome(
        ledger,
        candidate_sha256=enriched.motif_sha256,
        suffix="motif-state-change",
    )
    assurance_entry = snapshot.require(subject_sha256)
    mismatched_entry = MotifAssuranceEntry(
        **{
            **assurance_entry.model_dump(
                mode="python",
                exclude={"critic"},
            ),
            "critic": CriticRef(
                regime=_evaluation_regime_identity(),
                critic_id="critic.different",
                role=CriticRole.ACCEPTANCE,
            ),
        }
    )
    mismatched_snapshot = MotifAssuranceSnapshot(
        source_ledger_sha256=snapshot.source_ledger_sha256,
        entries=(mismatched_entry,),
    )
    mismatched_pin = MotifAssurancePin.create(
        selection_id="selection.transfer-validation.mismatched-critic",
        selected_motif_sha256=reusable.motif_sha256,
        motif_subject_sha256=subject_sha256,
        snapshot=mismatched_snapshot,
    )
    mismatched_report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.motif-state-change.mismatched-critic",
        cycle_index=2,
        assurance_snapshot_sha256=mismatched_snapshot.content_sha256,
        canary_observations=_canary_observations(plan),
        flow_observations=(),
        basis_replay_observations=(),
    )
    with pytest.raises(
        GovernedPromotionError,
        match="assurance does not bind the transition kernel and regime critic",
    ):
        issue_governed_promotion(
            ledger=ledger,
            action=AuthorityAction.MOTIF_STATE_CHANGE,
            event_id="authority.motif-state-change.mismatched-critic",
            subject_id="motif.review-first",
            subject_sha256=subject_sha256,
            kernel_ref=_kernel_ref(),
            kernel_abi_sha256=enriched.kernel_abi_sha256,
            evaluation_outcome=state_outcome_basis.reference,
            monitor_plan=plan,
            monitor_report=mismatched_report,
            cycle_id="cycle.motif-state-change.mismatched-critic",
            cycle_index=2,
            assurance_snapshot_sha256=mismatched_snapshot.content_sha256,
            motif=enriched,
            motif_assurance_pin=mismatched_pin,
            motif_assurance_snapshot=mismatched_snapshot,
        )
    state_report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.motif-state-change",
        cycle_index=2,
        assurance_snapshot_sha256=snapshot.content_sha256,
        canary_observations=_canary_observations(plan),
        flow_observations=(),
        basis_replay_observations=(),
    )

    state_change = issue_governed_promotion(
        ledger=ledger,
        action=AuthorityAction.MOTIF_STATE_CHANGE,
        event_id="authority.motif-state-change",
        subject_id="motif.review-first",
        subject_sha256=subject_sha256,
        kernel_ref=_kernel_ref(),
        kernel_abi_sha256=enriched.kernel_abi_sha256,
        evaluation_outcome=state_outcome_basis.reference,
        monitor_plan=plan,
        monitor_report=state_report,
        cycle_id="cycle.motif-state-change",
        cycle_index=2,
        assurance_snapshot_sha256=snapshot.content_sha256,
        motif=enriched,
        motif_assurance_pin=pin,
        motif_assurance_snapshot=snapshot,
    )

    assert {item.kind for item in state_change.event.basis} == {
        BasisKind.AUTHORITY_EVENT,
        BasisKind.CRITIC_EVALUATION_OUTCOME,
        BasisKind.MONITOR_REPORT,
        BasisKind.MOTIF_ASSURANCE,
        BasisKind.PROMOTION_LINEAGE,
        BasisKind.PROMOTION_MONITOR,
    }
    incomplete = AuthorityEvent(
        event_id="authority.motif-state-change.incomplete",
        principal=state_change.event.principal,
        action=state_change.event.action,
        decision=state_change.event.decision,
        subject_id=state_change.event.subject_id,
        subject_sha256=state_change.event.subject_sha256,
        basis=tuple(item for item in state_change.event.basis if item.kind is not BasisKind.MOTIF_ASSURANCE),
        kernel_ref=state_change.event.kernel_ref,
        critic=state_change.event.critic,
        reasons=state_change.event.reasons,
        revalidation_triggers=state_change.event.revalidation_triggers,
    )
    with pytest.raises(AuthorityLedgerIntegrityError, match="motif_assurance"):
        ledger.issue_authority_event(incomplete)


def test_governance_rejects_subject_unrelated_to_evaluated_candidate_or_lineage(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    plan = _monitor_plan()
    outcome_basis, critic_outcome = _recorded_critic_outcome(ledger)
    assurance_sha256 = _sha("assurance-snapshot")
    unrelated_subject_sha256 = _sha("unrelated-motif")
    assert unrelated_subject_sha256 != critic_outcome.outcome.candidate_sha256
    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.unrelated-subject",
        cycle_index=3,
        assurance_snapshot_sha256=assurance_sha256,
        canary_observations=_canary_observations(plan),
        flow_observations=(),
        basis_replay_observations=(),
    )

    with pytest.raises(GovernedPromotionError, match="candidate|lineage"):
        issue_governed_promotion(
            ledger=ledger,
            action=AuthorityAction.POLICY_PROMOTION,
            event_id="authority.unrelated-subject",
            subject_id="motif.unrelated",
            subject_sha256=unrelated_subject_sha256,
            kernel_ref=_kernel_ref(),
            kernel_abi_sha256=_sha("kernel"),
            evaluation_outcome=outcome_basis.reference,
            monitor_plan=plan,
            monitor_report=report,
            cycle_id="cycle.unrelated-subject",
            cycle_index=3,
            assurance_snapshot_sha256=assurance_sha256,
        )


def test_governance_cannot_relabel_development_outcome_as_acceptance_evidence(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    plan = _monitor_plan()
    assurance_sha256 = _sha("assurance-snapshot")
    development_basis, development_outcome = _recorded_critic_outcome(
        ledger,
        role=CriticRole.DEVELOPMENT,
    )
    assert development_basis.origin.producer.principal_id == development_outcome.execution_principal_id
    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.development-outcome",
        cycle_index=4,
        assurance_snapshot_sha256=assurance_sha256,
        canary_observations=_canary_observations(plan),
        flow_observations=(),
        basis_replay_observations=(),
    )

    with pytest.raises(GovernedPromotionError, match="acceptance"):
        issue_governed_promotion(
            ledger=ledger,
            action=AuthorityAction.POLICY_PROMOTION,
            event_id="authority.development-outcome",
            subject_id="candidate",
            subject_sha256=development_outcome.outcome.candidate_sha256,
            kernel_ref=_kernel_ref(),
            kernel_abi_sha256=_sha("kernel"),
            evaluation_outcome=development_basis.reference,
            monitor_plan=plan,
            monitor_report=report,
            cycle_id="cycle.development-outcome",
            cycle_index=4,
            assurance_snapshot_sha256=assurance_sha256,
        )


def test_red_team_promotion_flow_raises_incident_and_leaves_promotion_absent(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    plan = _monitor_plan()
    outcome_basis, critic_outcome = _recorded_critic_outcome(ledger)
    assurance_sha256 = _sha("assurance-snapshot")
    durable_motif_state = MotifAssuranceLedger.create()
    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.002",
        cycle_index=2,
        assurance_snapshot_sha256=assurance_sha256,
        canary_observations=_canary_observations(
            plan,
            ordinary_ledger_referenced=True,
        ),
        flow_observations=(
            RuntimeFlowObservation(
                flow_id="flow.red-team-promotion",
                source_principal_kind=AuthorityPrincipalKind.RED_TEAM,
                target_surface=FlowSurface.PROMOTION,
                action=FlowAction.CITE,
                evidence_sha256=_sha("red-team-flow-evidence"),
            ),
        ),
        basis_replay_observations=(),
    )

    with pytest.raises(GovernedPromotionError, match="monitor"):
        issue_governed_promotion(
            ledger=ledger,
            action=AuthorityAction.POLICY_PROMOTION,
            event_id="authority.blocked-promotion",
            subject_id="motif.poisoned-canary",
            subject_sha256=critic_outcome.outcome.candidate_sha256,
            kernel_ref=_kernel_ref(),
            kernel_abi_sha256=_sha("kernel"),
            evaluation_outcome=outcome_basis.reference,
            monitor_plan=plan,
            monitor_report=report,
            cycle_id="cycle.002",
            cycle_index=2,
            assurance_snapshot_sha256=assurance_sha256,
        )

    with pytest.raises(AuthorityLedgerIntegrityError, match="not registered"):
        ledger.resolve_authority_event(
            event_id="authority.blocked-promotion",
            content_sha256=_sha("nonexistent-event"),
        )
    assert MotifAssuranceLedger.create() == durable_motif_state


def test_production_promotion_persists_the_complete_monitor_envelope(
    tmp_path: Path,
) -> None:
    ledger = _production_ledger(tmp_path)
    policy = _monitor_policy()
    outcome_basis, critic_outcome = _recorded_critic_outcome(ledger)
    envelope = _production_cycle(policy)

    promoted = issue_governed_production_promotion(
        ledger=ledger,
        action=AuthorityAction.POLICY_PROMOTION,
        event_id="authority.promote-policy-002",
        subject_id="candidate",
        subject_sha256=critic_outcome.outcome.candidate_sha256,
        kernel_ref=_kernel_ref(),
        kernel_abi_sha256=_sha("kernel"),
        evaluation_outcome=outcome_basis.reference,
        monitor_policy=policy,
        monitor_envelope=envelope,
        cycle_id="cycle.010",
        cycle_index=10,
        assurance_snapshot_sha256=_sha("assurance-snapshot"),
    )

    monitor_reference = next(
        reference for reference in promoted.event.basis if reference.kind is BasisKind.MONITOR_REPORT
    )
    _, stored_envelope = ledger.resolve_model_basis(
        monitor_reference,
        ProductionCycleMonitorEnvelope,
    )
    assert stored_envelope == envelope


def test_production_promotion_rejects_incomplete_monitor_collection(
    tmp_path: Path,
) -> None:
    ledger = _production_ledger(tmp_path)
    policy = _monitor_policy()
    outcome_basis, critic_outcome = _recorded_critic_outcome(ledger)
    envelope = _production_cycle(policy, coverage_complete=False)

    with pytest.raises(GovernedPromotionError, match="monitor"):
        issue_governed_production_promotion(
            ledger=ledger,
            action=AuthorityAction.POLICY_PROMOTION,
            event_id="authority.blocked-production-promotion",
            subject_id="motif.review-first",
            subject_sha256=critic_outcome.outcome.candidate_sha256,
            kernel_ref=_kernel_ref(),
            kernel_abi_sha256=_sha("kernel"),
            evaluation_outcome=outcome_basis.reference,
            monitor_policy=policy,
            monitor_envelope=envelope,
            cycle_id="cycle.010",
            cycle_index=10,
            assurance_snapshot_sha256=_sha("assurance-snapshot"),
        )
