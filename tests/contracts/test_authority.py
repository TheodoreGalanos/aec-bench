# ABOUTME: Tests typed origin, basis, authority, taint, and closed operator capabilities.
# ABOUTME: Proves candidate and red-team artifacts cannot grant trust or change critic generations.

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    BasisReference,
    CriticEvaluationOutcomeIdentity,
    CriticGenerationIdentity,
    EvaluationPlanIdentity,
    HumanAuthorityApproval,
    MotifPromotionQualification,
    OperatorCapability,
    OperatorRole,
    OriginStamp,
    TaintLabel,
    derive_origin_stamp,
    operator_authority_for,
)
from aec_bench.contracts.harness_kernel import KernelRef, kernel_abi_commitment


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _basis(label: str = "evaluation") -> BasisReference:
    return BasisReference(
        kind=BasisKind.EVALUATION_OUTCOME,
        artifact_id=label,
        artifact_sha256=_sha(label),
    )


def _event(
    *,
    principal_kind: AuthorityPrincipalKind,
    action: AuthorityAction,
) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=f"event.{action.value}",
        principal=AuthorityPrincipal(
            principal_id=f"principal.{principal_kind.value}",
            kind=principal_kind,
        ),
        action=action,
        decision=AuthorityDecision.GRANTED,
        subject_id="subject.candidate-1",
        subject_sha256=_sha("candidate-1"),
        basis=(_basis(),),
        kernel_ref=KernelRef(kernel_id="aec-bench", version="1.0.0"),
        critic_generation=CriticGenerationIdentity(
            critic_id="critic.acceptance",
            version="1",
            compatibility_generation="evaluation-generation.1",
        ),
        reasons=("all_integrity_gates_passed",),
        revalidation_triggers=("critic_generation_change",),
    )


def test_derived_origin_inherits_all_parent_and_operation_taint() -> None:
    first = OriginStamp(
        artifact_id="artifact.first",
        artifact_sha256=_sha("first"),
        producer=AuthorityPrincipal(
            principal_id="candidate.one",
            kind=AuthorityPrincipalKind.CANDIDATE,
        ),
        producer_process_id="candidate-process",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="candidate-output",
        operation_id="proposal",
        invocation_id="invocation-1",
        taint_labels=(TaintLabel.CANDIDATE_AUTHORED,),
    )
    second = OriginStamp(
        artifact_id="artifact.second",
        artifact_sha256=_sha("second"),
        producer=AuthorityPrincipal(
            principal_id="external.source",
            kind=AuthorityPrincipalKind.EXTERNAL,
        ),
        producer_process_id="import-process",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="external-import",
        operation_id="import",
        invocation_id="invocation-2",
        taint_labels=(TaintLabel.EXTERNAL_UNVERIFIED,),
    )

    derived = derive_origin_stamp(
        artifact_id="artifact.derived",
        artifact_sha256=_sha("derived"),
        producer=AuthorityPrincipal(
            principal_id="host.compiler",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        producer_process_id="compiler-process",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="compile",
        operation_id="compile",
        invocation_id="invocation-3",
        parents=(first, second),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )

    assert derived.parent_origin_sha256s == tuple(sorted((first.content_sha256, second.content_sha256)))
    assert derived.taint_labels == (
        TaintLabel.CANDIDATE_AUTHORED,
        TaintLabel.EXTERNAL_UNVERIFIED,
        TaintLabel.RUNTIME_OBSERVED,
    )


@pytest.mark.parametrize(
    "principal_kind",
    [
        AuthorityPrincipalKind.CANDIDATE,
        AuthorityPrincipalKind.MODEL,
        AuthorityPrincipalKind.OPTIMIZER,
        AuthorityPrincipalKind.RED_TEAM,
        AuthorityPrincipalKind.MONITOR,
    ],
)
def test_untrusted_or_non_authoritative_principals_cannot_grant_promotion(
    principal_kind: AuthorityPrincipalKind,
) -> None:
    with pytest.raises(ValidationError, match="cannot grant"):
        _event(
            principal_kind=principal_kind,
            action=AuthorityAction.MOTIF_PROMOTION,
        )


@pytest.mark.parametrize(
    "action",
    [
        AuthorityAction.RELEASE_CRITIC_GENERATION,
        AuthorityAction.RETIRE_CRITIC_GENERATION,
        AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST,
        AuthorityAction.RELEASE_EVALUATION_COHORT,
        AuthorityAction.RETIRE_EVALUATION_COHORT,
    ],
)
def test_human_governance_transitions_require_human_principal(action: AuthorityAction) -> None:
    with pytest.raises(ValidationError, match="human principal"):
        _event(
            principal_kind=AuthorityPrincipalKind.HOST_POLICY,
            action=action,
        )

    event = _event(
        principal_kind=AuthorityPrincipalKind.HUMAN,
        action=action,
    )
    assert event.principal.kind is AuthorityPrincipalKind.HUMAN


def test_human_approval_binds_the_exact_principal_action_and_subject() -> None:
    approval = HumanAuthorityApproval(
        approval_id="approval.critic-v2",
        principal=AuthorityPrincipal(
            principal_id="human.theo",
            kind=AuthorityPrincipalKind.HUMAN,
        ),
        action=AuthorityAction.RELEASE_CRITIC_GENERATION,
        subject_id="critic.acceptance.v2",
        subject_sha256=_sha("critic.acceptance.v2"),
        approved=True,
        reason="approved exact acceptance critic generation",
    )

    assert HumanAuthorityApproval.model_validate(approval.model_dump(mode="json")) == approval

    with pytest.raises(ValidationError, match="human principal"):
        HumanAuthorityApproval(
            approval_id="approval.not-human",
            principal=AuthorityPrincipal(
                principal_id="host.policy",
                kind=AuthorityPrincipalKind.HOST_POLICY,
            ),
            action=AuthorityAction.RELEASE_CRITIC_GENERATION,
            subject_id="critic.acceptance.v2",
            subject_sha256=_sha("critic.acceptance.v2"),
            approved=True,
            reason="host tried to impersonate the principal",
        )


def test_motif_promotion_qualification_binds_the_exact_provisional_candidate() -> None:
    evaluation_plan = EvaluationPlanIdentity(
        plan_id="evaluation-plan",
        evaluation_generation="evaluation-generation.1",
    )
    critic_generation = CriticGenerationIdentity(
        critic_id="critic.acceptance",
        version="1",
        compatibility_generation="evaluation-generation.1",
    )
    critic_outcome = CriticEvaluationOutcomeIdentity(
        evaluation_plan=evaluation_plan,
        critic_generation=critic_generation,
        candidate_sha256=_sha("provisional-motif"),
    )
    kernel_ref = KernelRef(kernel_id="aec-bench", version="1.0.0")
    qualification = MotifPromotionQualification(
        subject_id="motif.subject",
        provisional_motif_sha256=_sha("provisional-motif"),
        motif_subject_sha256=_sha("motif-subject"),
        candidate_sha256=_sha("provisional-motif"),
        critic_evaluation_outcome=critic_outcome,
        promotion_lineage_sha256=_sha("promotion-lineage"),
        promotion_monitor_attestation_sha256=_sha("promotion-monitor"),
        monitor_report_sha256=_sha("monitor-report"),
        evaluation_plan=evaluation_plan,
        critic_release_authority_event_sha256=_sha("critic-release"),
        critic_generation=critic_generation,
        kernel_ref=kernel_ref,
        kernel_abi_sha256=kernel_abi_commitment(kernel_ref),
    )

    assert MotifPromotionQualification.model_validate(qualification.model_dump(mode="json")) == qualification

    with pytest.raises(ValidationError, match="exact provisional motif"):
        MotifPromotionQualification(
            **{
                **qualification.model_dump(
                    mode="python",
                    exclude={"content_sha256", "candidate_sha256"},
                ),
                "candidate_sha256": _sha("different-candidate"),
            }
        )


def test_operator_roles_have_closed_capabilities_without_promotion() -> None:
    repair = operator_authority_for("repair.operator", OperatorRole.DIAGNOSTIC_REPAIR)
    optimizer = operator_authority_for("optimizer.operator", OperatorRole.PERFORMANCE_OPTIMIZATION)
    red_team = operator_authority_for("red.operator", OperatorRole.ADAPTIVE_RED_TEAM)

    assert repair.capabilities == (
        OperatorCapability.READ_DIAGNOSTIC_EVIDENCE,
        OperatorCapability.PROPOSE_TYPED_PATCH,
    )
    assert OperatorCapability.PROPOSE_CANDIDATE in optimizer.capabilities
    assert red_team.capabilities == (
        OperatorCapability.READ_DEVELOPMENT_FEEDBACK,
        OperatorCapability.PROPOSE_CHALLENGE,
        OperatorCapability.WRITE_CHALLENGE_CASE,
    )
    assert all("promotion" not in capability.value for capability in red_team.capabilities)


def test_authority_event_is_content_addressed_and_tampering_is_rejected() -> None:
    event = _event(
        principal_kind=AuthorityPrincipalKind.HUMAN,
        action=AuthorityAction.MOTIF_PROMOTION,
    )
    payload = event.model_dump(mode="json")
    payload["subject_sha256"] = _sha("different-subject")

    with pytest.raises(ValidationError, match="content_sha256"):
        AuthorityEvent.model_validate(payload)
