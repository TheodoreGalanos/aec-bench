# ABOUTME: Issues promotion authority only after exact evaluation and current standing-monitor gates pass.
# ABOUTME: Persists typed basis evidence while keeping monitors detection-only and promotions host-authorized.

from __future__ import annotations

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    BasisReference,
    MotifPromotionAssurance,
    MotifPromotionQualification,
    PromotionMonitorAttestation,
    PromotionSubjectLineage,
    TaintLabel,
)
from aec_bench.contracts.evaluation_outcome import (
    CriticEvaluationOutcome,
    EvaluationDisposition,
    EvaluationOutcome,
)
from aec_bench.contracts.evaluation_plane import CriticRole
from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
    StoredAuthorityEvent,
    StoredBasis,
)
from aec_bench.meta_harness.motif_assurance import (
    MotifAssuranceBoundary,
    MotifAssurancePin,
    MotifAssuranceSnapshot,
    assert_motif_assurance_current,
    motif_subject_sha256,
)
from aec_bench.meta_harness.motifs import HarnessProgramMotif, MotifStatus
from aec_bench.meta_harness.standing_monitors import (
    CycleMonitorReport,
    ProductionCycleMonitorEnvelope,
    StandingMonitorPlan,
    StandingMonitorPolicy,
    assert_current_cycle_monitor_report,
    assert_current_production_cycle_monitor_envelope,
)


class GovernedPromotionError(ValueError):
    """Raised when evaluation or monitor evidence cannot authorize a promotion."""


_PROMOTION_ACTIONS = {
    AuthorityAction.POLICY_PROMOTION,
    AuthorityAction.MOTIF_PROMOTION,
    AuthorityAction.MOTIF_STATE_CHANGE,
}


def issue_governed_promotion(
    *,
    ledger: AuthorityLedger,
    action: AuthorityAction,
    event_id: str,
    subject_id: str,
    subject_sha256: str,
    kernel_sha256: str,
    evaluation_outcome: BasisReference,
    monitor_plan: StandingMonitorPlan,
    monitor_report: CycleMonitorReport,
    cycle_id: str,
    cycle_index: int,
    assurance_snapshot_sha256: str,
    promotion_lineage: PromotionSubjectLineage | None = None,
    motif: HarnessProgramMotif | None = None,
    motif_assurance_pin: MotifAssurancePin | None = None,
    motif_assurance_snapshot: MotifAssuranceSnapshot | None = None,
) -> StoredAuthorityEvent:
    """Persist promotion authority only when exact evaluation and monitor gates pass."""
    if action not in _PROMOTION_ACTIONS:
        raise GovernedPromotionError("governed promotion requires a closed promotion action")
    outcome_basis, critic_outcome = _resolve_acceptance_outcome(
        ledger=ledger,
        reference=evaluation_outcome,
    )
    outcome = critic_outcome.outcome
    plan = StandingMonitorPlan.model_validate(monitor_plan.model_dump(mode="python"))
    report = CycleMonitorReport.model_validate(monitor_report.model_dump(mode="python"))
    try:
        assert_current_cycle_monitor_report(
            report,
            plan=plan,
            cycle_id=cycle_id,
            cycle_index=cycle_index,
            assurance_snapshot_sha256=assurance_snapshot_sha256,
        )
    except ValueError as error:
        raise GovernedPromotionError(f"monitor gate blocked promotion: {error}") from error
    if outcome.evaluation_plan_sha256 != plan.evaluation_plan_sha256:
        raise GovernedPromotionError("evaluation outcome and monitor plan do not bind the same evaluation plan")
    _assert_promotion_eligible(outcome)
    selected_motif, assurance = _resolve_motif_transition(
        action=action,
        subject_sha256=subject_sha256,
        kernel_sha256=kernel_sha256,
        critic_outcome=critic_outcome,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        motif=motif,
        pin=motif_assurance_pin,
        snapshot=motif_assurance_snapshot,
    )
    lineage = _resolve_promotion_lineage(
        action=action,
        subject_id=subject_id,
        subject_sha256=subject_sha256,
        critic_outcome=critic_outcome,
        motif=selected_motif,
        supplied=promotion_lineage,
    )
    return _persist_governed_promotion(
        ledger=ledger,
        action=action,
        event_id=event_id,
        subject_id=subject_id,
        subject_sha256=subject_sha256,
        kernel_sha256=kernel_sha256,
        outcome_basis=outcome_basis,
        critic_outcome=critic_outcome,
        promotion_lineage=lineage,
        motif=selected_motif,
        motif_assurance=assurance,
        monitor_basis_model=report,
        monitor_artifact_id=f"cycle-monitor-report.{cycle_id}",
        monitor_process_id="aecbench.standing-monitors",
        evaluation_plan_sha256=outcome.evaluation_plan_sha256,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        cycle_id=cycle_id,
        cycle_index=cycle_index,
    )


def issue_governed_production_promotion(
    *,
    ledger: AuthorityLedger,
    action: AuthorityAction,
    event_id: str,
    subject_id: str,
    subject_sha256: str,
    kernel_sha256: str,
    evaluation_outcome: BasisReference,
    monitor_policy: StandingMonitorPolicy,
    monitor_envelope: ProductionCycleMonitorEnvelope,
    cycle_id: str,
    cycle_index: int,
    assurance_snapshot_sha256: str,
    promotion_lineage: PromotionSubjectLineage | None = None,
    motif: HarnessProgramMotif | None = None,
    motif_assurance_pin: MotifAssurancePin | None = None,
    motif_assurance_snapshot: MotifAssuranceSnapshot | None = None,
) -> StoredAuthorityEvent:
    """Persist promotion authority only from a complete v2 production monitor envelope."""
    if action not in _PROMOTION_ACTIONS:
        raise GovernedPromotionError("governed promotion requires a closed promotion action")
    outcome_basis, critic_outcome = _resolve_acceptance_outcome(
        ledger=ledger,
        reference=evaluation_outcome,
    )
    outcome = critic_outcome.outcome
    policy = StandingMonitorPolicy.model_validate(monitor_policy.model_dump(mode="python"))
    envelope = ProductionCycleMonitorEnvelope.model_validate(monitor_envelope.model_dump(mode="python"))
    try:
        assert_current_production_cycle_monitor_envelope(
            envelope,
            policy=policy,
            evaluation_plan_sha256=outcome.evaluation_plan_sha256,
            cycle_id=cycle_id,
            cycle_index=cycle_index,
            assurance_snapshot_sha256=assurance_snapshot_sha256,
        )
    except ValueError as error:
        raise GovernedPromotionError(f"monitor gate blocked promotion: {error}") from error
    _assert_promotion_eligible(outcome)
    selected_motif, assurance = _resolve_motif_transition(
        action=action,
        subject_sha256=subject_sha256,
        kernel_sha256=kernel_sha256,
        critic_outcome=critic_outcome,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        motif=motif,
        pin=motif_assurance_pin,
        snapshot=motif_assurance_snapshot,
    )
    lineage = _resolve_promotion_lineage(
        action=action,
        subject_id=subject_id,
        subject_sha256=subject_sha256,
        critic_outcome=critic_outcome,
        motif=selected_motif,
        supplied=promotion_lineage,
    )
    return _persist_governed_promotion(
        ledger=ledger,
        action=action,
        event_id=event_id,
        subject_id=subject_id,
        subject_sha256=subject_sha256,
        kernel_sha256=kernel_sha256,
        outcome_basis=outcome_basis,
        critic_outcome=critic_outcome,
        promotion_lineage=lineage,
        motif=selected_motif,
        motif_assurance=assurance,
        monitor_basis_model=envelope,
        monitor_artifact_id=f"production-cycle-monitor-envelope.{cycle_id}",
        monitor_process_id="aecbench.production-cycle-monitors",
        evaluation_plan_sha256=outcome.evaluation_plan_sha256,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        cycle_id=cycle_id,
        cycle_index=cycle_index,
    )


def _assert_promotion_eligible(outcome: EvaluationOutcome) -> None:
    if (
        not outcome.integrity.passed
        or outcome.validity is None
        or not outcome.validity.valid
        or outcome.utility is None
        or outcome.disposition is not EvaluationDisposition.ACCEPT
        or not outcome.promotion_eligible
    ):
        raise GovernedPromotionError("evaluation outcome is not eligible for promotion")


def _resolve_acceptance_outcome(
    *,
    ledger: AuthorityLedger,
    reference: BasisReference,
) -> tuple[StoredBasis, CriticEvaluationOutcome]:
    if not isinstance(reference, BasisReference) or reference.kind is not BasisKind.CRITIC_EVALUATION_OUTCOME:
        raise GovernedPromotionError("promotion requires an existing critic-bound acceptance outcome")
    try:
        stored, critic_outcome = ledger.resolve_model_basis(
            reference,
            CriticEvaluationOutcome,
        )
        release = ledger.resolve_authority_event(
            event_id=critic_outcome.critic_release_authority_event_id,
            content_sha256=critic_outcome.critic_release_authority_event_sha256,
        )
    except AuthorityLedgerError as error:
        raise GovernedPromotionError(f"acceptance outcome authority cannot be resolved: {error}") from error
    if critic_outcome.critic.role is not CriticRole.ACCEPTANCE:
        raise GovernedPromotionError("promotion requires an acceptance critic outcome")
    if (
        stored.origin.producer.kind is not AuthorityPrincipalKind.CRITIC_AUTHORITY
        or stored.origin.producer.principal_id != critic_outcome.execution_principal_id
        or TaintLabel.CRITIC_AUTHORITY not in stored.origin.taint_labels
        or TaintLabel.RUNTIME_OBSERVED not in stored.origin.taint_labels
    ):
        raise GovernedPromotionError("acceptance outcome lacks exact runtime-observed critic provenance")
    release_event = release.event
    if (
        release_event.action is not AuthorityAction.RELEASE_CRITIC_GENERATION
        or release_event.decision is not AuthorityDecision.GRANTED
        or release_event.subject_sha256 != critic_outcome.critic.content_sha256
        or release_event.critic_generation_sha256 != critic_outcome.critic.content_sha256
    ):
        raise GovernedPromotionError("acceptance outcome does not bind its exact released critic generation")
    return stored, critic_outcome


def _resolve_promotion_lineage(
    *,
    action: AuthorityAction,
    subject_id: str,
    subject_sha256: str,
    critic_outcome: CriticEvaluationOutcome,
    motif: HarnessProgramMotif | None,
    supplied: PromotionSubjectLineage | None,
) -> PromotionSubjectLineage:
    outcome = critic_outcome.outcome
    if motif is not None:
        expected = PromotionSubjectLineage(
            action=action,
            critic_evaluation_outcome_sha256=critic_outcome.content_sha256,
            candidate_sha256=outcome.candidate_sha256,
            subject_id=subject_id,
            subject_sha256=subject_sha256,
            derivation_evidence_sha256s=(() if outcome.candidate_sha256 == subject_sha256 else (motif.motif_sha256,)),
        )
        if supplied is not None:
            lineage = PromotionSubjectLineage.model_validate(supplied.model_dump(mode="python"))
            if lineage != expected:
                raise GovernedPromotionError("motif lineage must equal the host-derived candidate-to-subject join")
        return expected
    if supplied is None:
        if subject_sha256 != outcome.candidate_sha256:
            raise GovernedPromotionError(
                "promotion subject differs from the evaluated candidate and has no causal lineage"
            )
        return PromotionSubjectLineage(
            action=action,
            critic_evaluation_outcome_sha256=critic_outcome.content_sha256,
            candidate_sha256=outcome.candidate_sha256,
            subject_id=subject_id,
            subject_sha256=subject_sha256,
        )
    lineage = PromotionSubjectLineage.model_validate(supplied.model_dump(mode="python"))
    if (
        lineage.action is not action
        or lineage.critic_evaluation_outcome_sha256 != critic_outcome.content_sha256
        or lineage.candidate_sha256 != outcome.candidate_sha256
        or lineage.subject_id != subject_id
        or lineage.subject_sha256 != subject_sha256
    ):
        raise GovernedPromotionError("promotion subject lineage does not join the evaluated candidate")
    return lineage


def _resolve_motif_transition(
    *,
    action: AuthorityAction,
    subject_sha256: str,
    kernel_sha256: str,
    critic_outcome: CriticEvaluationOutcome,
    assurance_snapshot_sha256: str,
    motif: HarnessProgramMotif | None,
    pin: MotifAssurancePin | None,
    snapshot: MotifAssuranceSnapshot | None,
) -> tuple[HarnessProgramMotif | None, MotifPromotionAssurance | None]:
    if action is AuthorityAction.POLICY_PROMOTION:
        if motif is not None or pin is not None or snapshot is not None:
            raise GovernedPromotionError("policy promotion cannot carry motif transition state")
        return None, None
    selected_motif = _validated_transition_motif(
        action=action,
        subject_sha256=subject_sha256,
        kernel_sha256=kernel_sha256,
        critic_outcome=critic_outcome,
        motif=motif,
    )
    if action is AuthorityAction.MOTIF_PROMOTION:
        if pin is not None or snapshot is not None:
            raise GovernedPromotionError("first motif promotion must not depend on prior motif assurance")
        return selected_motif, None
    if action is not AuthorityAction.MOTIF_STATE_CHANGE:
        raise GovernedPromotionError(f"unsupported motif transition action: {action.value}")
    assurance = _resolve_current_motif_assurance(
        subject_sha256=subject_sha256,
        kernel_sha256=kernel_sha256,
        critic_outcome=critic_outcome,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        pin=pin,
        snapshot=snapshot,
    )
    return selected_motif, assurance


def _validated_transition_motif(
    *,
    action: AuthorityAction,
    subject_sha256: str,
    kernel_sha256: str,
    critic_outcome: CriticEvaluationOutcome,
    motif: HarnessProgramMotif | None,
) -> HarnessProgramMotif:
    if motif is None:
        raise GovernedPromotionError(f"{action.value} requires the exact motif record under evaluation")
    selected_motif = HarnessProgramMotif.model_validate(motif.model_dump(mode="python"))
    expected_status = MotifStatus.PROVISIONAL if action is AuthorityAction.MOTIF_PROMOTION else MotifStatus.REUSABLE
    if selected_motif.status is not expected_status:
        raise GovernedPromotionError(f"{action.value} requires an exact {expected_status.value} motif record")
    if (
        selected_motif.motif_sha256 != critic_outcome.outcome.candidate_sha256
        or motif_subject_sha256(selected_motif) != subject_sha256
        or selected_motif.kernel_abi_sha256 != kernel_sha256
        or critic_outcome.kernel_sha256 != kernel_sha256
    ):
        raise GovernedPromotionError(
            "motif transition does not bind the evaluated candidate, stable subject, and kernel"
        )
    return selected_motif


def _resolve_current_motif_assurance(
    *,
    subject_sha256: str,
    kernel_sha256: str,
    critic_outcome: CriticEvaluationOutcome,
    assurance_snapshot_sha256: str,
    pin: MotifAssurancePin | None,
    snapshot: MotifAssuranceSnapshot | None,
) -> MotifPromotionAssurance:
    if pin is None or snapshot is None:
        raise GovernedPromotionError("motif state change requires an exact current assurance pin and snapshot")
    try:
        selected = MotifAssurancePin.model_validate(pin.model_dump(mode="python"))
        current = MotifAssuranceSnapshot.model_validate(snapshot.model_dump(mode="python"))
        assert_motif_assurance_current(
            selected,
            current,
            boundary=MotifAssuranceBoundary.PROMOTION,
        )
    except ValueError as error:
        raise GovernedPromotionError(f"motif assurance blocked promotion: {error}") from error
    if current.content_sha256 != assurance_snapshot_sha256 or selected.motif_subject_sha256 != subject_sha256:
        raise GovernedPromotionError("motif assurance does not bind the transition subject and monitor snapshot")
    entry = current.require(subject_sha256)
    if entry.kernel_sha256 != kernel_sha256 or entry.critic_generation_sha256 != critic_outcome.critic.content_sha256:
        raise GovernedPromotionError("motif assurance does not bind the transition kernel and critic generation")
    assurance = MotifPromotionAssurance(
        motif_subject_sha256=selected.motif_subject_sha256,
        selected_motif_sha256=selected.selected_motif_sha256,
        assurance_snapshot_sha256=current.content_sha256,
        assurance_head_event_sha256=selected.assurance_head_event_sha256,
    )
    return assurance


def _persist_governed_promotion(
    *,
    ledger: AuthorityLedger,
    action: AuthorityAction,
    event_id: str,
    subject_id: str,
    subject_sha256: str,
    kernel_sha256: str,
    outcome_basis: StoredBasis,
    critic_outcome: CriticEvaluationOutcome,
    promotion_lineage: PromotionSubjectLineage,
    motif: HarnessProgramMotif | None,
    motif_assurance: MotifPromotionAssurance | None,
    monitor_basis_model: ContentAddressedModel,
    monitor_artifact_id: str,
    monitor_process_id: str,
    evaluation_plan_sha256: str,
    assurance_snapshot_sha256: str,
    cycle_id: str,
    cycle_index: int,
) -> StoredAuthorityEvent:
    host_policy = AuthorityPrincipal(
        principal_id="host.promotion-policy",
        kind=AuthorityPrincipalKind.HOST_POLICY,
    )
    host_runtime = AuthorityPrincipal(
        principal_id="host.runtime",
        kind=AuthorityPrincipalKind.HOST_RUNTIME,
    )
    release = ledger.resolve_authority_event(
        event_id=critic_outcome.critic_release_authority_event_id,
        content_sha256=critic_outcome.critic_release_authority_event_sha256,
    )
    release_basis = ledger.observe_model_basis(
        kind=BasisKind.AUTHORITY_EVENT,
        artifact_id=f"critic-release.{event_id}",
        model=release.event,
        producer=release.event.principal,
        producer_process_id="aecbench.critic-governance",
        observed_by=host_runtime,
        channel="critic-release",
        operation_id="promotion-evaluation",
        invocation_id=event_id,
        operation_taint=(
            TaintLabel.HUMAN_AUTHORITY,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )
    lineage_basis = ledger.observe_model_basis(
        kind=BasisKind.PROMOTION_LINEAGE,
        artifact_id=f"promotion-lineage.{event_id}",
        model=promotion_lineage,
        producer=host_policy,
        producer_process_id="aecbench.promotion-policy",
        observed_by=host_runtime,
        channel="promotion-lineage",
        operation_id="promotion-evaluation",
        invocation_id=event_id,
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    monitor_basis = ledger.observe_model_basis(
        kind=BasisKind.MONITOR_REPORT,
        artifact_id=monitor_artifact_id,
        model=monitor_basis_model,
        producer=AuthorityPrincipal(
            principal_id="monitor.standing",
            kind=AuthorityPrincipalKind.MONITOR,
        ),
        producer_process_id=monitor_process_id,
        observed_by=host_runtime,
        channel="monitor-gate",
        operation_id="promotion-monitor",
        invocation_id=event_id,
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    monitor_attestation = PromotionMonitorAttestation(
        monitor_basis_sha256=monitor_basis.reference.artifact_sha256,
        monitor_report_sha256=monitor_basis_model.content_sha256,
        evaluation_plan_sha256=evaluation_plan_sha256,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        cycle_id=cycle_id,
        cycle_index=cycle_index,
    )
    monitor_attestation_basis = ledger.observe_model_basis(
        kind=BasisKind.PROMOTION_MONITOR,
        artifact_id=f"promotion-monitor.{event_id}",
        model=monitor_attestation,
        producer=host_policy,
        producer_process_id="aecbench.promotion-policy",
        observed_by=host_runtime,
        channel="monitor-gate",
        operation_id="promotion-monitor-attestation",
        invocation_id=event_id,
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    assurance_basis = (
        None
        if motif_assurance is None
        else ledger.observe_model_basis(
            kind=BasisKind.MOTIF_ASSURANCE,
            artifact_id=f"motif-assurance.{event_id}",
            model=motif_assurance,
            producer=host_policy,
            producer_process_id="aecbench.motif-assurance",
            observed_by=host_runtime,
            channel="motif-assurance",
            operation_id="promotion-evaluation",
            invocation_id=event_id,
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
    )
    qualification_basis = None
    if action is AuthorityAction.MOTIF_PROMOTION:
        if motif is None:
            raise GovernedPromotionError("motif promotion qualification requires the exact provisional motif")
        _, resolved_outcome = ledger.resolve_model_basis(
            outcome_basis.reference,
            CriticEvaluationOutcome,
        )
        resolved_release = ledger.resolve_authority_event(
            event_id=resolved_outcome.critic_release_authority_event_id,
            content_sha256=resolved_outcome.critic_release_authority_event_sha256,
        ).event
        _, resolved_lineage = ledger.resolve_model_basis(
            lineage_basis.reference,
            PromotionSubjectLineage,
        )
        ledger.resolve_basis(monitor_basis.reference)
        _, resolved_monitor_attestation = ledger.resolve_model_basis(
            monitor_attestation_basis.reference,
            PromotionMonitorAttestation,
        )
        qualification = MotifPromotionQualification(
            subject_id=subject_id,
            provisional_motif_sha256=motif.motif_sha256,
            motif_subject_sha256=subject_sha256,
            candidate_sha256=resolved_outcome.outcome.candidate_sha256,
            critic_evaluation_outcome_sha256=resolved_outcome.content_sha256,
            promotion_lineage_sha256=resolved_lineage.content_sha256,
            promotion_monitor_attestation_sha256=(resolved_monitor_attestation.content_sha256),
            monitor_report_sha256=resolved_monitor_attestation.monitor_report_sha256,
            evaluation_plan_sha256=(resolved_outcome.evaluation_plan_ref.content_sha256),
            critic_release_authority_event_sha256=resolved_release.content_sha256,
            critic_generation_sha256=resolved_outcome.critic.content_sha256,
            kernel_sha256=resolved_outcome.kernel_sha256,
        )
        qualification_basis = ledger.observe_model_basis(
            kind=BasisKind.MOTIF_QUALIFICATION,
            artifact_id=f"motif-qualification.{event_id}",
            model=qualification,
            producer=host_policy,
            producer_process_id="aecbench.motif-qualification",
            observed_by=host_runtime,
            channel="motif-qualification",
            operation_id="promotion-evaluation",
            invocation_id=event_id,
            parent_origin_sha256s=tuple(
                sorted(
                    {
                        outcome_basis.origin.content_sha256,
                        release_basis.origin.content_sha256,
                        lineage_basis.origin.content_sha256,
                        monitor_basis.origin.content_sha256,
                        monitor_attestation_basis.origin.content_sha256,
                    }
                )
            ),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )
    event = AuthorityEvent(
        event_id=event_id,
        principal=host_policy,
        action=action,
        decision=AuthorityDecision.GRANTED,
        subject_id=subject_id,
        subject_sha256=subject_sha256,
        basis=(
            outcome_basis.reference,
            release_basis.reference,
            lineage_basis.reference,
            monitor_basis.reference,
            monitor_attestation_basis.reference,
            *((assurance_basis.reference,) if assurance_basis is not None else ()),
            *((qualification_basis.reference,) if qualification_basis is not None else ()),
        ),
        kernel_sha256=kernel_sha256,
        critic_generation_sha256=critic_outcome.critic.content_sha256,
        reasons=("evaluation and current standing-monitor gates passed",),
        revalidation_triggers=(
            "assurance_snapshot_change",
            "critic_generation_change",
            "monitor_incident",
        ),
    )
    return ledger.issue_authority_event(event)
