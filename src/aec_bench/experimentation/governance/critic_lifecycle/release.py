# ABOUTME: Releases critics from exact published evaluation regimes under human authority.
# ABOUTME: Binds hidden escrow and executable-anchor calibration to one exact regime reference.

from __future__ import annotations

from pydantic import ValidationError

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipalKind,
    BasisReference,
    TaintLabel,
)
from aec_bench.contracts.evaluation_outcome import EvaluationOutcome
from aec_bench.contracts.evaluation_plane import (
    Critic,
    EvaluationRegime,
    ExecutableAnchorCalibrationCadence,
    ExecutableAnchorCalibrationEvidence,
    ExecutableAnchorCalibrationPolicy,
)
from aec_bench.contracts.evaluation_refs import CriticRef, CriticRole, EvaluationRegimeRef
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.evaluation.regime import validate_evaluation_regime_ref
from aec_bench.experimentation.governance.acceptance_manifest_escrow import load_acceptance_manifest_escrow
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
    StoredAuthorityEvent,
    StoredBasis,
)

from .evidence import (
    _critic_subject_id,
    _load_evidence_reference,
    _observe_critic,
    _observe_governance_evidence,
    _resolve_human_approval,
    _resolve_release_authority,
)


def release_critic(
    *,
    ledger: AuthorityLedger,
    evaluation_regime: EvaluationRegime,
    evaluation_regime_ref: EvaluationRegimeRef,
    critic: Critic,
    human_approval: BasisReference,
    event_id: str,
    kernel_ref: KernelRef,
    anchor_calibration_evidence: BasisReference | None = None,
) -> StoredAuthorityEvent:
    """Release one critic from an exact published regime."""

    regime = EvaluationRegime.model_validate(evaluation_regime.model_dump(mode="python"))
    selected = Critic.model_validate(critic.model_dump(mode="python"))
    try:
        validate_evaluation_regime_ref(regime, evaluation_regime_ref)
    except ValueError as error:
        raise AuthorityLedgerIntegrityError(str(error)) from error
    if selected not in regime.critics:
        raise AuthorityLedgerIntegrityError("critic release does not belong to the published evaluation regime")
    critic_ref = selected.ref(evaluation_regime_ref)
    regime_basis = _observe_governance_evidence(
        ledger=ledger,
        artifact_id=f"critic-release.{event_id}.evaluation-regime",
        model=regime,
        operation_id="release-critic",
        invocation_id=event_id,
    )
    acceptance_escrow = (
        load_acceptance_manifest_escrow(
            ledger=ledger,
            evaluation_regime=evaluation_regime_ref,
            critic=selected,
        )
        if selected.role is CriticRole.ACCEPTANCE
        else None
    )
    calibration_bases = _resolve_release_calibration(
        ledger=ledger,
        regime=regime,
        regime_ref=evaluation_regime_ref,
        critic=selected,
        critic_ref=critic_ref,
        calibration_evidence=anchor_calibration_evidence,
        event_id=event_id,
    )
    escrow_basis: StoredBasis | None = None
    if acceptance_escrow is not None:
        escrow_basis = _observe_governance_evidence(
            ledger=ledger,
            artifact_id=f"critic-release.{event_id}.acceptance-escrow-publication",
            model=acceptance_escrow.publication_receipt,
            operation_id="release-critic",
            invocation_id=event_id,
        )
    subject_id = _critic_subject_id(critic_ref)
    approval = _resolve_human_approval(
        ledger=ledger,
        reference=human_approval,
        action=AuthorityAction.RELEASE_CRITIC,
        subject_id=subject_id,
        subject_sha256=evaluation_regime_ref.artifact.sha256,
        mismatch_message="human approval does not match the exact critic release",
    )
    critic_basis = _observe_critic(
        ledger=ledger,
        critic=selected,
        event_id=event_id,
        operation_id="release-critic",
    )
    acceptance = selected.role is CriticRole.ACCEPTANCE
    event = AuthorityEvent(
        event_id=event_id,
        principal=approval.principal,
        action=AuthorityAction.RELEASE_CRITIC,
        decision=AuthorityDecision.GRANTED,
        subject_id=subject_id,
        subject_sha256=evaluation_regime_ref.artifact.sha256,
        basis=(
            human_approval,
            critic_basis.reference,
            *((escrow_basis.reference,) if escrow_basis is not None else ()),
            regime_basis.reference,
            *(basis.reference for basis in calibration_bases),
        ),
        kernel_ref=kernel_ref,
        critic=critic_ref,
        reasons=(
            "human approved the exact published regime critic",
            *(("release bound completed executable-anchor calibration",) if calibration_bases else ()),
        ),
        revalidation_triggers=(
            *(("acceptance_manifest_reveal_due",) if acceptance else ()),
            "critic_change",
            *(("executable_anchor_recalibration_due",) if calibration_bases else ()),
        ),
    )
    return ledger.issue_authority_event(event)


def release_acceptance_critic(
    *,
    ledger: AuthorityLedger,
    evaluation_regime: EvaluationRegime,
    evaluation_regime_ref: EvaluationRegimeRef,
    critic: Critic,
    human_approval: BasisReference,
    event_id: str,
    kernel_ref: KernelRef,
    anchor_calibration_evidence: BasisReference | None = None,
) -> StoredAuthorityEvent:
    """Release one escrowed acceptance critic from an exact regime."""

    selected = Critic.model_validate(critic.model_dump(mode="python"))
    if selected.role is not CriticRole.ACCEPTANCE or selected.acceptance_manifest_commitment is None:
        raise AuthorityLedgerIntegrityError("acceptance critic release requires a committed acceptance critic")
    return release_critic(
        ledger=ledger,
        evaluation_regime=evaluation_regime,
        evaluation_regime_ref=evaluation_regime_ref,
        critic=selected,
        human_approval=human_approval,
        event_id=event_id,
        kernel_ref=kernel_ref,
        anchor_calibration_evidence=anchor_calibration_evidence,
    )


def assert_critic_released(
    *,
    ledger: AuthorityLedger,
    critic: Critic,
    critic_ref: CriticRef,
    release_authority: StoredAuthorityEvent,
) -> StoredAuthorityEvent:
    """Replay one critic release through its human approval and critic basis."""

    selected = Critic.model_validate(critic.model_dump(mode="python"))
    return _resolve_release_authority(
        ledger=ledger,
        stored=release_authority,
        critic=selected,
        critic_ref=critic_ref,
    )


def _resolve_release_calibration(
    *,
    ledger: AuthorityLedger,
    regime: EvaluationRegime,
    regime_ref: EvaluationRegimeRef,
    critic: Critic,
    critic_ref: CriticRef,
    calibration_evidence: BasisReference | None,
    event_id: str,
) -> tuple[StoredBasis, ...]:
    policy = _embedded_anchor_policy(regime)
    if policy is None:
        if calibration_evidence is not None:
            raise AuthorityLedgerIntegrityError("evaluation regime does not configure executable-anchor calibration")
        return ()
    required = critic.role in policy.critic_roles and policy.cadence is (
        ExecutableAnchorCalibrationCadence.EVERY_CRITIC_RELEASE
    )
    if not required:
        if calibration_evidence is not None:
            raise AuthorityLedgerIntegrityError("critic role is outside the executable-anchor calibration policy")
        return ()
    if calibration_evidence is None:
        raise AuthorityLedgerIntegrityError("critic release requires executable-anchor calibration evidence")
    evidence_basis, evidence = _load_release_calibration_evidence(
        ledger=ledger,
        calibration_evidence=calibration_evidence,
    )
    _validate_calibration_evidence(
        ledger=ledger,
        evidence=evidence,
        regime_ref=regime_ref,
        critic_ref=critic_ref,
    )
    return (evidence_basis,)


def _embedded_anchor_policy(regime: EvaluationRegime) -> ExecutableAnchorCalibrationPolicy | None:
    if regime.calibration_policy is None:
        return None
    payload = regime.calibration_policy.configuration.get("executable_anchor")
    if payload is None:
        return None
    try:
        return ExecutableAnchorCalibrationPolicy.model_validate(payload)
    except ValidationError as error:
        raise AuthorityLedgerIntegrityError("evaluation regime executable-anchor policy is invalid") from error


def _load_release_calibration_evidence(
    *,
    ledger: AuthorityLedger,
    calibration_evidence: BasisReference,
) -> tuple[StoredBasis, ExecutableAnchorCalibrationEvidence]:
    evidence_basis, evidence = _load_evidence_reference(
        ledger=ledger,
        reference=calibration_evidence,
        model_type=ExecutableAnchorCalibrationEvidence,
        label="executable-anchor calibration",
    )
    if evidence_basis.origin.producer.kind not in {
        AuthorityPrincipalKind.HOST_RUNTIME,
        AuthorityPrincipalKind.HOST_POLICY,
        AuthorityPrincipalKind.TASK_AUTHORITY,
        AuthorityPrincipalKind.CRITIC_AUTHORITY,
    }:
        raise AuthorityLedgerIntegrityError("executable-anchor calibration requires task or critic authority")
    forbidden_taint = {
        TaintLabel.CANDIDATE_AUTHORED,
        TaintLabel.MODEL_REPORTED,
        TaintLabel.EXTERNAL_UNVERIFIED,
        TaintLabel.INTEGRITY_INCIDENT,
    }
    if forbidden_taint.intersection(evidence_basis.origin.taint_labels):
        raise AuthorityLedgerIntegrityError("executable-anchor calibration has candidate or unverified taint")
    return evidence_basis, evidence


def _validate_calibration_evidence(
    *,
    ledger: AuthorityLedger,
    evidence: ExecutableAnchorCalibrationEvidence,
    regime_ref: EvaluationRegimeRef,
    critic_ref: CriticRef,
) -> None:
    if evidence.evaluation_regime != regime_ref or evidence.critic != critic_ref:
        raise AuthorityLedgerIntegrityError("calibration evidence does not match the regime critic")
    if not evidence.completed or not evidence.passed:
        raise AuthorityLedgerIntegrityError("critic release requires completed passing calibration evidence")
    anchors: list[str] = []
    for outcome_reference in evidence.evaluation_outcomes:
        _, outcome = ledger.resolve_model_basis(outcome_reference, EvaluationOutcome)
        anchors.append(outcome.evidence_set_sha256)
    if evidence.executable_anchor_sha256s != tuple(sorted(anchors)):
        raise AuthorityLedgerIntegrityError("calibration anchors do not match the resolved outcomes")
