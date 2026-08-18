# ABOUTME: Validates the complete typed evidence closure for granted promotion authority.
# ABOUTME: Joins critic, release, lineage, monitor, qualification, and assurance bases exactly.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipalKind,
    BasisKind,
    MotifPromotionAssurance,
    MotifPromotionQualification,
    PromotionMonitorAttestation,
    PromotionSubjectLineage,
    TaintLabel,
)
from aec_bench.contracts.evaluation_outcome import CriticEvaluationOutcome
from aec_bench.contracts.evaluation_refs import CriticRole, EvaluationRegimeRef
from aec_bench.experimentation.governance.authority_ledger import (
    _HOST_PRINCIPAL_KINDS,
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
    StoredBasis,
)

_PROMOTION_REQUIRED_BASIS: dict[AuthorityAction, frozenset[BasisKind]] = {
    AuthorityAction.POLICY_PROMOTION: frozenset(
        {
            BasisKind.CRITIC_EVALUATION_OUTCOME,
            BasisKind.MONITOR_REPORT,
            BasisKind.PROMOTION_MONITOR,
            BasisKind.PROMOTION_LINEAGE,
            BasisKind.AUTHORITY_EVENT,
        }
    ),
    AuthorityAction.MOTIF_PROMOTION: frozenset(
        {
            BasisKind.CRITIC_EVALUATION_OUTCOME,
            BasisKind.MONITOR_REPORT,
            BasisKind.PROMOTION_MONITOR,
            BasisKind.PROMOTION_LINEAGE,
            BasisKind.AUTHORITY_EVENT,
            BasisKind.MOTIF_QUALIFICATION,
        }
    ),
    AuthorityAction.MOTIF_STATE_CHANGE: frozenset(
        {
            BasisKind.CRITIC_EVALUATION_OUTCOME,
            BasisKind.MONITOR_REPORT,
            BasisKind.PROMOTION_MONITOR,
            BasisKind.PROMOTION_LINEAGE,
            BasisKind.AUTHORITY_EVENT,
            BasisKind.MOTIF_ASSURANCE,
        }
    ),
}


@dataclass(frozen=True)
class _PromotionEvidence:
    """Typed promotion bases after their causal and provenance joins validate."""

    critic_basis: StoredBasis
    critic_outcome: CriticEvaluationOutcome
    release_basis: StoredBasis
    release: AuthorityEvent
    lineage_basis: StoredBasis
    lineage: PromotionSubjectLineage
    monitor_basis: StoredBasis
    monitor_attestation_basis: StoredBasis
    monitor_attestation: PromotionMonitorAttestation


def validate_promotion_basis(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    basis: tuple[StoredBasis, ...],
) -> None:
    """Enforce the causal evidence closure for one granted promotion."""

    grouped = _promotion_basis_by_kind(event=event, basis=basis)
    critic_basis, critic_outcome = _validated_acceptance_critic(
        ledger=ledger,
        event=event,
        grouped=grouped,
    )
    release_basis, release = _validated_critic_release(
        ledger=ledger,
        critic_outcome=critic_outcome,
        grouped=grouped,
    )
    lineage_basis, lineage = _validated_promotion_lineage(
        ledger=ledger,
        event=event,
        critic_outcome=critic_outcome,
        grouped=grouped,
    )
    monitor_basis, monitor_attestation_basis, monitor_attestation = _validated_promotion_monitor(
        ledger=ledger,
        critic_outcome=critic_outcome,
        grouped=grouped,
    )
    evidence = _PromotionEvidence(
        critic_basis=critic_basis,
        critic_outcome=critic_outcome,
        release_basis=release_basis,
        release=release,
        lineage_basis=lineage_basis,
        lineage=lineage,
        monitor_basis=monitor_basis,
        monitor_attestation_basis=monitor_attestation_basis,
        monitor_attestation=monitor_attestation,
    )
    if event.action is AuthorityAction.MOTIF_PROMOTION:
        _validate_motif_promotion_qualification(
            ledger=ledger,
            event=event,
            grouped=grouped,
            evidence=evidence,
        )
    if event.action is AuthorityAction.MOTIF_STATE_CHANGE:
        _validate_motif_state_assurance(
            ledger=ledger,
            event=event,
            grouped=grouped,
            evidence=evidence,
        )


def _promotion_basis_by_kind(
    *,
    event: AuthorityEvent,
    basis: tuple[StoredBasis, ...],
) -> dict[BasisKind, tuple[StoredBasis, ...]]:
    required = _PROMOTION_REQUIRED_BASIS[event.action]
    grouped = {kind: tuple(item for item in basis if item.reference.kind is kind) for kind in required}
    missing = tuple(sorted(kind.value for kind, items in grouped.items() if not items))
    if missing:
        raise AuthorityLedgerIntegrityError("promotion requires typed basis: " + ", ".join(missing))
    duplicated = tuple(sorted(kind.value for kind, items in grouped.items() if len(items) != 1))
    if duplicated:
        raise AuthorityLedgerIntegrityError("promotion requires exactly one basis for: " + ", ".join(duplicated))
    return grouped


def _validated_acceptance_critic(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    grouped: dict[BasisKind, tuple[StoredBasis, ...]],
) -> tuple[StoredBasis, CriticEvaluationOutcome]:
    critic_basis = grouped[BasisKind.CRITIC_EVALUATION_OUTCOME][0]
    critic_outcome = ledger._load_model(
        critic_basis.content_path,
        CriticEvaluationOutcome,
        label="critic evaluation outcome basis",
    )
    if critic_outcome.critic.role is not CriticRole.ACCEPTANCE:
        raise AuthorityLedgerIntegrityError("promotion requires an acceptance critic outcome")
    if (
        critic_basis.origin.producer.kind is not AuthorityPrincipalKind.CRITIC_AUTHORITY
        or critic_basis.origin.producer.principal_id != critic_outcome.execution_principal_id
        or TaintLabel.CRITIC_AUTHORITY not in critic_basis.origin.taint_labels
        or TaintLabel.RUNTIME_OBSERVED not in critic_basis.origin.taint_labels
    ):
        raise AuthorityLedgerIntegrityError("acceptance outcome lacks exact runtime-observed critic provenance")
    outcome = critic_outcome.outcome
    if (
        not outcome.integrity.passed
        or outcome.validity is None
        or not outcome.validity.valid
        or outcome.utility is None
        or not outcome.promotion_eligible
    ):
        raise AuthorityLedgerIntegrityError("acceptance outcome is not promotion eligible")
    if event.kernel_ref != critic_outcome.kernel_ref or event.critic != critic_outcome.critic.authority_identity:
        raise AuthorityLedgerIntegrityError("promotion event does not bind the outcome kernel and regime critic")
    return critic_basis, critic_outcome


def _validated_critic_release(
    *,
    ledger: AuthorityLedger,
    critic_outcome: CriticEvaluationOutcome,
    grouped: dict[BasisKind, tuple[StoredBasis, ...]],
) -> tuple[StoredBasis, AuthorityEvent]:
    release_basis = grouped[BasisKind.AUTHORITY_EVENT][0]
    release = ledger._load_model(
        release_basis.content_path,
        AuthorityEvent,
        label="critic release authority basis",
    )
    if (
        release.content_sha256 != critic_outcome.critic_release_authority_event_sha256
        or release.event_id != critic_outcome.critic_release_authority_event_id
        or release.action is not AuthorityAction.RELEASE_CRITIC
        or release.decision is not AuthorityDecision.GRANTED
        or release.critic != critic_outcome.critic.authority_identity
    ):
        raise AuthorityLedgerIntegrityError("promotion does not bind the exact released acceptance critic")
    if (
        release_basis.origin.producer != release.principal
        or release_basis.origin.producer.kind is not AuthorityPrincipalKind.HUMAN
        or TaintLabel.HUMAN_AUTHORITY not in release_basis.origin.taint_labels
        or TaintLabel.RUNTIME_OBSERVED not in release_basis.origin.taint_labels
    ):
        raise AuthorityLedgerIntegrityError("critic release basis lacks host-observed human authority")
    return release_basis, release


def _validated_promotion_lineage(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    critic_outcome: CriticEvaluationOutcome,
    grouped: dict[BasisKind, tuple[StoredBasis, ...]],
) -> tuple[StoredBasis, PromotionSubjectLineage]:
    outcome = critic_outcome.outcome
    lineage_basis = grouped[BasisKind.PROMOTION_LINEAGE][0]
    lineage = ledger._load_model(
        lineage_basis.content_path,
        PromotionSubjectLineage,
        label="promotion subject lineage basis",
    )
    if (
        lineage_basis.origin.producer.kind not in _HOST_PRINCIPAL_KINDS
        or TaintLabel.RUNTIME_OBSERVED not in lineage_basis.origin.taint_labels
        or lineage.action is not event.action
        or lineage.critic_evaluation_outcome != critic_outcome.authority_identity
        or lineage.candidate_sha256 != outcome.candidate_sha256
        or lineage.subject_id != event.subject_id
        or lineage.subject_sha256 != event.subject_sha256
    ):
        raise AuthorityLedgerIntegrityError("promotion subject is not causally joined to the evaluated candidate")
    return lineage_basis, lineage


def _validated_promotion_monitor(
    *,
    ledger: AuthorityLedger,
    critic_outcome: CriticEvaluationOutcome,
    grouped: dict[BasisKind, tuple[StoredBasis, ...]],
) -> tuple[StoredBasis, StoredBasis, PromotionMonitorAttestation]:
    monitor_basis = grouped[BasisKind.MONITOR_REPORT][0]
    if (
        monitor_basis.origin.producer.kind is not AuthorityPrincipalKind.MONITOR
        or TaintLabel.RUNTIME_OBSERVED not in monitor_basis.origin.taint_labels
    ):
        raise AuthorityLedgerIntegrityError("promotion monitor basis lacks runtime-observed monitor provenance")
    monitor_attestation_basis = grouped[BasisKind.PROMOTION_MONITOR][0]
    monitor_attestation = ledger._load_model(
        monitor_attestation_basis.content_path,
        PromotionMonitorAttestation,
        label="promotion monitor attestation basis",
    )
    if (
        monitor_attestation_basis.origin.producer.kind not in _HOST_PRINCIPAL_KINDS
        or TaintLabel.RUNTIME_OBSERVED not in monitor_attestation_basis.origin.taint_labels
    ):
        raise AuthorityLedgerIntegrityError("promotion monitor attestation lacks runtime-observed host provenance")
    _validate_promotion_monitor_attestation(
        ledger=ledger,
        monitor_basis=monitor_basis,
        attestation=monitor_attestation,
        evaluation_regime=critic_outcome.evaluation_regime_ref.authority_identity,
    )
    return monitor_basis, monitor_attestation_basis, monitor_attestation


def _validate_motif_promotion_qualification(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    grouped: dict[BasisKind, tuple[StoredBasis, ...]],
    evidence: _PromotionEvidence,
) -> None:
    qualification_basis = grouped[BasisKind.MOTIF_QUALIFICATION][0]
    qualification = ledger._load_model(
        qualification_basis.content_path,
        MotifPromotionQualification,
        label="motif promotion qualification basis",
    )
    outcome = evidence.critic_outcome.outcome
    expected_qualification = MotifPromotionQualification(
        subject_id=event.subject_id,
        provisional_motif_sha256=outcome.candidate_sha256,
        motif_subject_sha256=event.subject_sha256,
        candidate_sha256=outcome.candidate_sha256,
        critic_evaluation_outcome=evidence.critic_outcome.authority_identity,
        promotion_lineage_sha256=evidence.lineage.content_sha256,
        promotion_monitor_attestation_sha256=evidence.monitor_attestation.content_sha256,
        monitor_report_sha256=evidence.monitor_attestation.monitor_report_sha256,
        evaluation_regime=evidence.critic_outcome.evaluation_regime_ref.authority_identity,
        critic_release_authority_event_sha256=evidence.release.content_sha256,
        critic=evidence.critic_outcome.critic.authority_identity,
        kernel_ref=evidence.critic_outcome.kernel_ref,
        kernel_abi_sha256=qualification.kernel_abi_sha256,
    )
    expected_parent_origins = tuple(
        sorted(
            item.origin.content_sha256
            for item in (
                evidence.critic_basis,
                evidence.release_basis,
                evidence.lineage_basis,
                evidence.monitor_basis,
                evidence.monitor_attestation_basis,
            )
        )
    )
    if (
        qualification_basis.origin.producer.kind not in _HOST_PRINCIPAL_KINDS
        or TaintLabel.RUNTIME_OBSERVED not in qualification_basis.origin.taint_labels
        or qualification_basis.origin.parent_origin_sha256s != expected_parent_origins
        or qualification != expected_qualification
        or evidence.lineage.derivation_evidence_sha256s
        != (
            ()
            if evidence.lineage.candidate_sha256 == evidence.lineage.subject_sha256
            else (qualification.provisional_motif_sha256,)
        )
    ):
        raise AuthorityLedgerIntegrityError(
            "motif promotion qualification does not recompute from the exact durable bases"
        )


def _validate_motif_state_assurance(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    grouped: dict[BasisKind, tuple[StoredBasis, ...]],
    evidence: _PromotionEvidence,
) -> None:
    assurance_basis = grouped[BasisKind.MOTIF_ASSURANCE][0]
    assurance = ledger._load_model(
        assurance_basis.content_path,
        MotifPromotionAssurance,
        label="motif assurance basis",
    )
    if (
        assurance_basis.origin.producer.kind not in _HOST_PRINCIPAL_KINDS
        or TaintLabel.RUNTIME_OBSERVED not in assurance_basis.origin.taint_labels
        or assurance.motif_subject_sha256 != event.subject_sha256
        or assurance.assurance_snapshot_sha256 != evidence.monitor_attestation.assurance_snapshot_sha256
        or evidence.lineage.derivation_evidence_sha256s
        != (
            ()
            if evidence.lineage.candidate_sha256 == evidence.lineage.subject_sha256
            else (evidence.lineage.candidate_sha256,)
        )
    ):
        raise AuthorityLedgerIntegrityError("motif state change lacks exact current assurance basis")


def _validate_promotion_monitor_attestation(
    *,
    ledger: AuthorityLedger,
    monitor_basis: StoredBasis,
    attestation: PromotionMonitorAttestation,
    evaluation_regime: EvaluationRegimeRef,
) -> None:
    from aec_bench.experimentation.governance.standing_monitors import (
        CycleMonitorReport,
        ProductionCycleMonitorEnvelope,
    )

    model_type = ledger._typed_basis_models.get(BasisKind.MONITOR_REPORT)
    if model_type not in {CycleMonitorReport, ProductionCycleMonitorEnvelope}:
        raise AuthorityLedgerIntegrityError("promotion monitor report requires a supported typed monitor schema")
    report_model: CycleMonitorReport | ProductionCycleMonitorEnvelope
    if model_type is CycleMonitorReport:
        report_model = ledger._load_model(
            monitor_basis.content_path,
            CycleMonitorReport,
            label="promotion monitor report basis",
        )
    else:
        report_model = ledger._load_model(
            monitor_basis.content_path,
            ProductionCycleMonitorEnvelope,
            label="promotion monitor report basis",
        )
    if isinstance(report_model, ProductionCycleMonitorEnvelope):
        report = report_model.report
        report_evaluation_regime = report_model.cycle_plan.evaluation_regime
    else:
        report = report_model
        report_evaluation_regime = evaluation_regime
    if (
        attestation.monitor_basis_sha256 != monitor_basis.reference.artifact_sha256
        or attestation.monitor_report_sha256 != monitor_basis.reference.artifact_sha256
        or attestation.evaluation_regime != evaluation_regime
        or report_evaluation_regime != evaluation_regime
        or attestation.assurance_snapshot_sha256 != report.assurance_snapshot_sha256
        or attestation.cycle_id != report.cycle_id
        or attestation.cycle_index != report.cycle_index
    ):
        raise AuthorityLedgerIntegrityError(
            "promotion monitor attestation does not bind the exact monitor report and acceptance regime"
        )
