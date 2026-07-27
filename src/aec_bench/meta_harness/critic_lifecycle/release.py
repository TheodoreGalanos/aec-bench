# ABOUTME: Releases exact critic generations and replays their human-authorized authority chain.
# ABOUTME: Binds escrow, predecessor audit closure, and executable-anchor calibration evidence.


from __future__ import annotations

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
    CriticRole,
    CriticSpec,
    EvaluationPlan,
    ExecutableAnchorCalibrationCadence,
    ExecutableAnchorCalibrationEvidence,
    ExecutableAnchorCalibrationPolicy,
)
from aec_bench.meta_harness.acceptance_manifest_escrow import (
    load_acceptance_manifest_escrow,
)
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
    StoredAuthorityEvent,
    StoredBasis,
)

from .evidence import (
    _critic_subject_id,
    _load_evidence_reference,
    _observe_authority_event_basis,
    _observe_critic_spec,
    _observe_governance_evidence,
    _resolve_human_approval,
    _resolve_release_authority,
)
from .reveal import assert_acceptance_audit_closed


def release_critic_generation(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    human_approval: BasisReference,
    event_id: str,
    kernel_sha256: str,
    prior_retirement_authority: StoredAuthorityEvent | None = None,
    prior_reveal_authority: StoredAuthorityEvent | None = None,
    evaluation_plan: EvaluationPlan | None = None,
    anchor_calibration_policy: ExecutableAnchorCalibrationPolicy | None = None,
    anchor_calibration_evidence: BasisReference | None = None,
) -> StoredAuthorityEvent:
    """Release one exact critic generation under matching host-observed human authority."""
    selected = CriticSpec.model_validate(critic_spec.model_dump(mode="python"))
    acceptance_escrow = (
        load_acceptance_manifest_escrow(
            ledger=ledger,
            critic_spec=selected,
        )
        if selected.role is CriticRole.ACCEPTANCE
        else None
    )
    closure_bases = _resolve_release_predecessor_closure(
        ledger=ledger,
        critic_spec=selected,
        retirement_authority=prior_retirement_authority,
        reveal_authority=prior_reveal_authority,
        event_id=event_id,
    )
    calibration_bases = _resolve_release_calibration(
        ledger=ledger,
        critic_spec=selected,
        evaluation_plan=evaluation_plan,
        calibration_policy=anchor_calibration_policy,
        calibration_evidence=anchor_calibration_evidence,
        event_id=event_id,
        kernel_sha256=kernel_sha256,
    )
    acceptance_escrow_basis: StoredBasis | None = None
    if acceptance_escrow is not None:
        acceptance_escrow_basis = _observe_governance_evidence(
            ledger=ledger,
            artifact_id=f"critic-release.{event_id}.acceptance-escrow-publication",
            model=acceptance_escrow.publication_receipt,
            operation_id="release-critic-generation",
            invocation_id=event_id,
        )
    subject_id = _critic_subject_id(selected)
    approval = _resolve_human_approval(
        ledger=ledger,
        reference=human_approval,
        action=AuthorityAction.RELEASE_CRITIC_GENERATION,
        subject_id=subject_id,
        subject_sha256=selected.content_sha256,
        mismatch_message="human approval does not match the exact critic release",
    )
    critic_basis = _observe_critic_spec(
        ledger=ledger,
        critic_spec=selected,
        event_id=event_id,
        operation_id="release-critic-generation",
    )
    acceptance = selected.role is CriticRole.ACCEPTANCE
    event = AuthorityEvent(
        event_id=event_id,
        principal=approval.principal,
        action=AuthorityAction.RELEASE_CRITIC_GENERATION,
        decision=AuthorityDecision.GRANTED,
        subject_id=subject_id,
        subject_sha256=selected.content_sha256,
        basis=(
            human_approval,
            critic_basis.reference,
            *((acceptance_escrow_basis.reference,) if acceptance_escrow_basis is not None else ()),
            *(basis.reference for basis in closure_bases),
            *(basis.reference for basis in calibration_bases),
        ),
        kernel_sha256=kernel_sha256,
        critic_generation_sha256=selected.content_sha256,
        reasons=tuple(
            [
                (
                    "human approved exact escrowed acceptance critic generation"
                    if acceptance
                    else "human approved exact critic generation"
                ),
                *(["release bound completed executable-anchor calibration"] if calibration_bases else []),
            ]
        ),
        revalidation_triggers=tuple(
            [
                *(
                    [
                        "acceptance_manifest_reveal_due",
                        "critic_generation_change",
                    ]
                    if acceptance
                    else ["critic_generation_change"]
                ),
                *(["executable_anchor_recalibration_due"] if calibration_bases else []),
            ]
        ),
    )
    return ledger.issue_authority_event(event)


def release_acceptance_critic_generation(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    human_approval: BasisReference,
    event_id: str,
    kernel_sha256: str,
    prior_retirement_authority: StoredAuthorityEvent | None = None,
    prior_reveal_authority: StoredAuthorityEvent | None = None,
    evaluation_plan: EvaluationPlan | None = None,
    anchor_calibration_policy: ExecutableAnchorCalibrationPolicy | None = None,
    anchor_calibration_evidence: BasisReference | None = None,
) -> StoredAuthorityEvent:
    """Release one exact escrowed acceptance critic under matching human authority."""
    selected = CriticSpec.model_validate(critic_spec.model_dump(mode="python"))
    if selected.role is not CriticRole.ACCEPTANCE:
        raise AuthorityLedgerIntegrityError("acceptance critic release requires an acceptance critic spec")
    if selected.acceptance_manifest_commitment is None:
        raise AuthorityLedgerIntegrityError("acceptance critic release requires a hidden-manifest escrow commitment")
    return release_critic_generation(
        ledger=ledger,
        critic_spec=selected,
        human_approval=human_approval,
        event_id=event_id,
        kernel_sha256=kernel_sha256,
        prior_retirement_authority=prior_retirement_authority,
        prior_reveal_authority=prior_reveal_authority,
        evaluation_plan=evaluation_plan,
        anchor_calibration_policy=anchor_calibration_policy,
        anchor_calibration_evidence=anchor_calibration_evidence,
    )


def assert_critic_generation_released(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    release_authority: StoredAuthorityEvent,
) -> StoredAuthorityEvent:
    """Replay one critic release through its exact human approval and critic basis."""

    selected = CriticSpec.model_validate(critic_spec.model_dump(mode="python"))
    return _resolve_release_authority(
        ledger=ledger,
        stored=release_authority,
        critic_spec=selected,
    )


def _resolve_release_predecessor_closure(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    retirement_authority: StoredAuthorityEvent | None,
    reveal_authority: StoredAuthorityEvent | None,
    event_id: str,
) -> tuple[StoredBasis, ...]:
    parent_sha256 = critic_spec.parent_critic_sha256
    requires_closure = critic_spec.role is CriticRole.ACCEPTANCE and parent_sha256 is not None
    if not requires_closure:
        if retirement_authority is not None or reveal_authority is not None:
            raise AuthorityLedgerIntegrityError(
                "critic without an acceptance parent cannot bind predecessor audit closure"
            )
        return ()
    if retirement_authority is None:
        raise AuthorityLedgerIntegrityError("successor acceptance critic requires its parent retirement audit closure")
    closure = assert_acceptance_audit_closed(
        ledger=ledger,
        retirement_authority=retirement_authority,
        reveal_authority=reveal_authority,
    )
    if closure.retirement.retirement.critic_generation_sha256 != parent_sha256:
        raise AuthorityLedgerIntegrityError(
            "successor acceptance critic parent does not match the closed predecessor generation"
        )
    retirement_basis = _observe_authority_event_basis(
        ledger=ledger,
        stored=closure.retirement.authority_event,
        artifact_id=f"critic-release.{event_id}.parent-retirement",
        operation_id="release-critic-generation",
        invocation_id=event_id,
    )
    reveal_basis = _observe_authority_event_basis(
        ledger=ledger,
        stored=closure.reveal.authority_event,
        artifact_id=f"critic-release.{event_id}.parent-reveal",
        operation_id="release-critic-generation",
        invocation_id=event_id,
    )
    return retirement_basis, reveal_basis


def _resolve_release_calibration(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
    evaluation_plan: EvaluationPlan | None,
    calibration_policy: ExecutableAnchorCalibrationPolicy | None,
    calibration_evidence: BasisReference | None,
    event_id: str,
    kernel_sha256: str,
) -> tuple[StoredBasis, ...]:
    selected = _select_calibration_inputs(
        evaluation_plan=evaluation_plan,
        calibration_policy=calibration_policy,
        calibration_evidence=calibration_evidence,
    )
    if selected is None:
        return ()
    plan, policy = selected
    _validate_calibration_plan(
        plan=plan,
        policy=policy,
        critic_spec=critic_spec,
        kernel_sha256=kernel_sha256,
    )
    if not _require_release_calibration(
        critic_spec=critic_spec,
        policy=policy,
        calibration_evidence=calibration_evidence,
    ):
        return ()
    assert calibration_evidence is not None
    evidence_basis, evidence = _load_release_calibration_evidence(
        ledger=ledger,
        calibration_evidence=calibration_evidence,
    )
    _validate_calibration_evidence(
        ledger=ledger,
        evidence=evidence,
        plan=plan,
        policy=policy,
        critic_spec=critic_spec,
    )
    plan_basis = _observe_governance_evidence(
        ledger=ledger,
        artifact_id=f"critic-release.{event_id}.evaluation-plan",
        model=plan,
        operation_id="release-critic-generation",
        invocation_id=event_id,
    )
    policy_basis = _observe_governance_evidence(
        ledger=ledger,
        artifact_id=f"critic-release.{event_id}.anchor-calibration-policy",
        model=policy,
        operation_id="release-critic-generation",
        invocation_id=event_id,
    )
    return plan_basis, policy_basis, evidence_basis


def _select_calibration_inputs(
    *,
    evaluation_plan: EvaluationPlan | None,
    calibration_policy: ExecutableAnchorCalibrationPolicy | None,
    calibration_evidence: BasisReference | None,
) -> tuple[EvaluationPlan, ExecutableAnchorCalibrationPolicy] | None:
    supplied = (
        evaluation_plan is not None,
        calibration_policy is not None,
        calibration_evidence is not None,
    )
    if not any(supplied):
        return None
    if evaluation_plan is None or calibration_policy is None:
        raise AuthorityLedgerIntegrityError(
            "critic release executable-anchor calibration requires its exact evaluation plan and policy"
        )
    return (
        EvaluationPlan.model_validate(evaluation_plan.model_dump(mode="python")),
        ExecutableAnchorCalibrationPolicy.model_validate(calibration_policy.model_dump(mode="python")),
    )


def _validate_calibration_plan(
    *,
    plan: EvaluationPlan,
    policy: ExecutableAnchorCalibrationPolicy,
    critic_spec: CriticSpec,
    kernel_sha256: str,
) -> None:
    plan_critics = tuple(
        critic
        for critic in (
            plan.development_critic,
            plan.acceptance_critic,
            plan.red_team_critic,
        )
        if critic is not None
    )
    if critic_spec not in plan_critics:
        raise AuthorityLedgerIntegrityError("critic release evaluation plan does not bind the exact critic generation")
    if plan.kernel_sha256 != kernel_sha256:
        raise AuthorityLedgerIntegrityError("critic release evaluation plan kernel does not match release authority")
    if plan.anchor_calibration_policy_sha256 != policy.content_sha256:
        raise AuthorityLedgerIntegrityError(
            "critic release executable-anchor calibration policy does not match its evaluation plan"
        )


def _require_release_calibration(
    *,
    critic_spec: CriticSpec,
    policy: ExecutableAnchorCalibrationPolicy,
    calibration_evidence: BasisReference | None,
) -> bool:
    required = (
        critic_spec.role in policy.critic_roles
        and policy.cadence is ExecutableAnchorCalibrationCadence.EVERY_CRITIC_RELEASE
    )
    if not required:
        if calibration_evidence is not None:
            raise AuthorityLedgerIntegrityError(
                "critic role is outside the declared executable-anchor calibration cadence"
            )
        return False
    if calibration_evidence is None:
        raise AuthorityLedgerIntegrityError("critic release requires completed executable-anchor calibration evidence")
    return True


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
        raise AuthorityLedgerIntegrityError(
            "executable-anchor calibration evidence requires a host-observed task or critic authority"
        )
    if any(
        label
        in {
            TaintLabel.CANDIDATE_AUTHORED,
            TaintLabel.MODEL_REPORTED,
            TaintLabel.EXTERNAL_UNVERIFIED,
            TaintLabel.INTEGRITY_INCIDENT,
        }
        for label in evidence_basis.origin.taint_labels
    ):
        raise AuthorityLedgerIntegrityError(
            "executable-anchor calibration evidence cannot carry candidate or unverified taint"
        )
    return evidence_basis, evidence


def _validate_calibration_evidence(
    *,
    ledger: AuthorityLedger,
    evidence: ExecutableAnchorCalibrationEvidence,
    plan: EvaluationPlan,
    policy: ExecutableAnchorCalibrationPolicy,
    critic_spec: CriticSpec,
) -> None:
    if (
        evidence.evaluation_plan_sha256 != plan.content_sha256
        or evidence.critic_generation_sha256 != critic_spec.content_sha256
        or evidence.anchor_calibration_policy_sha256 != policy.content_sha256
    ):
        raise AuthorityLedgerIntegrityError(
            "executable-anchor calibration evidence does not match the exact plan, critic, and policy"
        )
    if not evidence.completed or not evidence.passed:
        raise AuthorityLedgerIntegrityError(
            "critic release requires completed passing executable-anchor calibration evidence"
        )
    _validate_calibration_outcomes(
        ledger=ledger,
        evidence=evidence,
        plan=plan,
    )


def _validate_calibration_outcomes(
    *,
    ledger: AuthorityLedger,
    evidence: ExecutableAnchorCalibrationEvidence,
    plan: EvaluationPlan,
) -> None:
    outcome_anchor_sha256s: list[str] = []
    for outcome_reference in evidence.evaluation_outcomes:
        _, outcome = ledger.resolve_model_basis(
            outcome_reference,
            EvaluationOutcome,
        )
        if outcome.evaluation_plan_sha256 != plan.content_sha256:
            raise AuthorityLedgerIntegrityError(
                "executable-anchor calibration outcome does not match the exact evaluation plan"
            )
        outcome_anchor_sha256s.append(outcome.evidence_set_sha256)
    if evidence.executable_anchor_sha256s != tuple(sorted(outcome_anchor_sha256s)):
        raise AuthorityLedgerIntegrityError(
            "executable-anchor calibration anchor identities do not match its resolved outcomes"
        )
