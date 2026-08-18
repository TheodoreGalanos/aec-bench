# ABOUTME: Exercises the host-confined content-addressed authority ledger on a real filesystem.
# ABOUTME: Proves confinement, canonical persistence, typed basis closure, and human transition authority.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    BasisReference,
    HumanAuthorityApproval,
    TaintLabel,
)
from aec_bench.contracts.evaluation_outcome import (
    CandidatePlaneCost,
    CriticPlaneCost,
    EvaluationCostBreakdown,
    EvaluationDisposition,
    EvaluationOutcome,
    IntegrityCheck,
    IntegrityEvaluation,
    ResourceCost,
)
from aec_bench.contracts.evaluation_refs import CriticRef, CriticRole
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerCollisionError,
    AuthorityLedgerConfinementError,
    AuthorityLedgerIntegrityError,
    StoredBasis,
)
from tests.support.evaluation_regimes import fake_regime_ref


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _principal(principal_id: str, kind: AuthorityPrincipalKind) -> AuthorityPrincipal:
    return AuthorityPrincipal(principal_id=principal_id, kind=kind)


def _kernel_ref() -> KernelRef:
    return KernelRef(kernel_id="test-kernel", version="1.0.0")


def _ledger(tmp_path: Path) -> AuthorityLedger:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    return AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
    )


def _observe(
    ledger: AuthorityLedger,
    *,
    artifact_id: str,
    content: bytes,
    kind: BasisKind,
    producer: AuthorityPrincipal,
    operation_taint: tuple[TaintLabel, ...],
    parent_origin_sha256s: tuple[str, ...] = (),
    channel: str = "host-input",
) -> StoredBasis:
    return ledger.observe_basis(
        kind=kind,
        artifact_id=artifact_id,
        content=content,
        producer=producer,
        producer_process_id=f"process.{producer.principal_id}",
        observed_by=_principal("host.authority", AuthorityPrincipalKind.HOST_RUNTIME),
        channel=channel,
        operation_id="authority-ledger.observe",
        invocation_id=f"invocation.{artifact_id}",
        parent_origin_sha256s=parent_origin_sha256s,
        operation_taint=operation_taint,
    )


def _critic_release_event(
    *,
    event_id: str,
    principal: AuthorityPrincipal,
    basis: BasisReference,
    reason: str = "approved critic release",
) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=event_id,
        principal=principal,
        action=AuthorityAction.RELEASE_CRITIC,
        decision=AuthorityDecision.GRANTED,
        subject_id="critic.acceptance.v2",
        subject_sha256=_sha("critic.acceptance.v2"),
        basis=(basis,),
        kernel_ref=_kernel_ref(),
        critic=CriticRef(
            regime=fake_regime_ref(),
            critic_id="critic.acceptance",
            role=CriticRole.ACCEPTANCE,
        ),
        reasons=(reason,),
        revalidation_triggers=("critic_change",),
    )


def _approval_bytes(
    *,
    approval_id: str,
    reason: str = "approved exact acceptance regime critic",
    subject_sha256: str | None = None,
) -> bytes:
    approval = HumanAuthorityApproval(
        approval_id=approval_id,
        principal=_principal("human.theo", AuthorityPrincipalKind.HUMAN),
        action=AuthorityAction.RELEASE_CRITIC,
        subject_id="critic.acceptance.v2",
        subject_sha256=subject_sha256 or _sha("critic.acceptance.v2"),
        approved=True,
        reason=reason,
    )
    return (
        json.dumps(
            approval.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _failed_evaluation_outcome() -> EvaluationOutcome:
    zero = ResourceCost(
        provider_calls=0,
        tokens=0,
        provider_cost_usd=0.0,
        wall_time_seconds=0.0,
    )
    return EvaluationOutcome(
        candidate_sha256=_sha("candidate"),
        evidence_set_sha256=_sha("evidence-set"),
        integrity=IntegrityEvaluation.create(
            checks=(
                IntegrityCheck(
                    check_id="forbidden-flow",
                    passed=False,
                    reasons=("candidate wrote authority-shaped bytes",),
                ),
            )
        ),
        costs=EvaluationCostBreakdown(
            candidate=CandidatePlaneCost(proposal=zero, execution=zero),
            critic_plane=CriticPlaneCost(
                development=zero,
                acceptance=zero,
                red_team=zero,
                monitor=zero,
                human_audit=zero,
            ),
        ),
        disposition=EvaluationDisposition.EXPERIMENT_ERROR,
        promotion_eligible=False,
        reasons=("forbidden-flow: candidate wrote authority-shaped bytes",),
    )


def test_authority_root_must_be_disjoint_from_candidates_and_must_not_be_a_symlink(
    tmp_path: Path,
) -> None:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()

    with pytest.raises(AuthorityLedgerConfinementError, match="overlap"):
        AuthorityLedger(
            candidate_root / "authority",
            candidate_roots=(candidate_root,),
        )
    with pytest.raises(AuthorityLedgerConfinementError, match="overlap"):
        AuthorityLedger(
            tmp_path / "authority-parent",
            candidate_roots=(tmp_path / "authority-parent" / "candidate",),
        )

    real_root = tmp_path / "real-authority"
    real_root.mkdir()
    symlink_root = tmp_path / "authority-link"
    symlink_root.symlink_to(real_root, target_is_directory=True)
    with pytest.raises(AuthorityLedgerConfinementError, match="symlink"):
        AuthorityLedger(symlink_root)


def test_observed_basis_is_canonical_idempotent_and_rejects_logical_identity_collision(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    human = _principal("human.theo", AuthorityPrincipalKind.HUMAN)

    first = _observe(
        ledger,
        artifact_id="approval.critic-v2",
        content=_approval_bytes(approval_id="approval.critic-v2"),
        kind=BasisKind.HUMAN_APPROVAL,
        producer=human,
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
    )
    repeated = _observe(
        ledger,
        artifact_id="approval.critic-v2",
        content=_approval_bytes(approval_id="approval.critic-v2"),
        kind=BasisKind.HUMAN_APPROVAL,
        producer=human,
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
    )

    assert repeated == first
    assert first.content_path.read_bytes() == _approval_bytes(approval_id="approval.critic-v2")
    expected_origin = (
        json.dumps(
            first.origin.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    assert first.origin_path.read_bytes() == expected_origin
    assert first.origin_path.parent.name == first.origin.content_sha256

    with pytest.raises(AuthorityLedgerCollisionError, match="logical identity"):
        _observe(
            ledger,
            artifact_id="approval.critic-v2",
            content=_approval_bytes(
                approval_id="approval.critic-v2",
                reason="different approval scope",
            ),
            kind=BasisKind.HUMAN_APPROVAL,
            producer=human,
            operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
        )


def test_internal_symlink_cannot_redirect_authority_artifacts(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    (ledger.root / "basis-objects").symlink_to(redirected, target_is_directory=True)

    with pytest.raises(AuthorityLedgerConfinementError, match="symlink"):
        _observe(
            ledger,
            artifact_id="evidence.one",
            content=b"evidence\n",
            kind=BasisKind.EVIDENCE,
            producer=_principal("host.runtime", AuthorityPrincipalKind.HOST_RUNTIME),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )

    assert not tuple(redirected.iterdir())


def test_basis_resolution_is_kind_exact_and_detects_physical_tampering(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    observed = _observe(
        ledger,
        artifact_id="evidence.one",
        content=b"exact evidence bytes\n",
        kind=BasisKind.EVIDENCE,
        producer=_principal("host.runtime", AuthorityPrincipalKind.HOST_RUNTIME),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )

    resolved = ledger.resolve_basis(observed.reference)
    assert resolved == observed

    wrong_kind = BasisReference(
        kind=BasisKind.HUMAN_APPROVAL,
        artifact_id=observed.reference.artifact_id,
        artifact_sha256=observed.reference.artifact_sha256,
    )
    with pytest.raises(AuthorityLedgerIntegrityError, match="not registered"):
        ledger.resolve_basis(wrong_kind)

    observed.content_path.write_bytes(b"tampered evidence\n")
    with pytest.raises(AuthorityLedgerIntegrityError, match="hash"):
        ledger.resolve_basis(observed.reference)


def test_summary_bytes_cannot_satisfy_a_typed_evaluation_outcome_basis(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)

    with pytest.raises(AuthorityLedgerIntegrityError, match="typed evaluation_outcome"):
        _observe(
            ledger,
            artifact_id="evaluation.summary-only",
            content=b'{"summary":"candidate improved"}\n',
            kind=BasisKind.EVALUATION_OUTCOME,
            producer=_principal("host.policy", AuthorityPrincipalKind.HOST_POLICY),
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )


def test_evaluation_outcome_can_be_observed_as_its_exact_typed_basis(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    outcome = _failed_evaluation_outcome()

    stored = ledger.observe_model_basis(
        kind=BasisKind.EVALUATION_OUTCOME,
        artifact_id="evaluation.outcome-001",
        model=outcome,
        producer=_principal("host.policy", AuthorityPrincipalKind.HOST_POLICY),
        producer_process_id="process.evaluation-gate",
        observed_by=_principal("host.runtime", AuthorityPrincipalKind.HOST_RUNTIME),
        channel="evaluation-gate",
        operation_id="evaluation-outcome",
        invocation_id="invocation.evaluation-001",
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )

    assert stored.reference.artifact_sha256 == _sha(stored.content_path.read_text())
    assert ledger.resolve_basis(stored.reference) == stored


@pytest.mark.parametrize(
    "action",
    (
        AuthorityAction.MOTIF_PROMOTION,
        AuthorityAction.MOTIF_STATE_CHANGE,
        AuthorityAction.POLICY_PROMOTION,
    ),
)
def test_raw_authority_ledger_rejects_granted_promotion_without_required_typed_basis(
    tmp_path: Path,
    action: AuthorityAction,
) -> None:
    ledger = _ledger(tmp_path)
    generic_evidence = _observe(
        ledger,
        artifact_id=f"evidence.{action.value}",
        content=b'{"claim":"promotion is safe"}\n',
        kind=BasisKind.EVIDENCE,
        producer=_principal("host.policy", AuthorityPrincipalKind.HOST_POLICY),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    event = AuthorityEvent(
        event_id=f"event.{action.value}",
        principal=_principal("host.policy", AuthorityPrincipalKind.HOST_POLICY),
        action=action,
        decision=AuthorityDecision.GRANTED,
        subject_id=f"subject.{action.value}",
        subject_sha256=_sha(f"subject.{action.value}"),
        basis=(generic_evidence.reference,),
        kernel_ref=_kernel_ref(),
        reasons=("generic evidence claimed the subject was safe",),
    )

    with pytest.raises(AuthorityLedgerIntegrityError) as raised:
        ledger.validate_authority_event(event)

    message = str(raised.value)
    assert BasisKind.CRITIC_EVALUATION_OUTCOME.value in message
    assert BasisKind.MONITOR_REPORT.value in message
    assert BasisKind.PROMOTION_MONITOR.value in message
    assert BasisKind.PROMOTION_LINEAGE.value in message
    assert BasisKind.AUTHORITY_EVENT.value in message
    if action is AuthorityAction.MOTIF_PROMOTION:
        assert BasisKind.MOTIF_QUALIFICATION.value in message
    if action is AuthorityAction.MOTIF_STATE_CHANGE:
        assert BasisKind.MOTIF_ASSURANCE.value in message

    with pytest.raises(AuthorityLedgerIntegrityError):
        ledger.issue_authority_event(event)


def test_human_critic_transition_requires_matching_host_observed_human_basis(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    human = _principal("human.theo", AuthorityPrincipalKind.HUMAN)
    approval = _observe(
        ledger,
        artifact_id="approval.critic-v2",
        content=_approval_bytes(approval_id="approval.critic-v2"),
        kind=BasisKind.HUMAN_APPROVAL,
        producer=human,
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
    )
    event = _critic_release_event(
        event_id="event.release-critic-v2",
        principal=human,
        basis=approval.reference,
    )

    stored = ledger.issue_authority_event(event)

    expected_event = (
        json.dumps(
            event.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    assert stored.path.read_bytes() == expected_event
    assert (
        ledger.resolve_authority_event(
            event_id=event.event_id,
            content_sha256=event.content_sha256,
        )
        == stored
    )
    assert ledger.validate_authority_event(event) == (approval,)

    candidate_approval = _observe(
        ledger,
        artifact_id="approval.candidate-shaped",
        content=_approval_bytes(approval_id="approval.candidate-shaped"),
        kind=BasisKind.HUMAN_APPROVAL,
        producer=_principal("candidate.one", AuthorityPrincipalKind.CANDIDATE),
        operation_taint=(TaintLabel.CANDIDATE_AUTHORED,),
    )
    forged = _critic_release_event(
        event_id="event.forged-release",
        principal=human,
        basis=candidate_approval.reference,
    )
    with pytest.raises(AuthorityLedgerIntegrityError, match="matching host-observed human"):
        ledger.issue_authority_event(forged)

    wrong_scope = _observe(
        ledger,
        artifact_id="approval.wrong-subject",
        content=_approval_bytes(
            approval_id="approval.wrong-subject",
            subject_sha256=_sha("different-regime-critic"),
        ),
        kind=BasisKind.HUMAN_APPROVAL,
        producer=human,
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
    )
    wrong_scope_event = _critic_release_event(
        event_id="event.wrong-scope-release",
        principal=human,
        basis=wrong_scope.reference,
    )
    with pytest.raises(AuthorityLedgerIntegrityError, match="matching host-observed human"):
        ledger.issue_authority_event(wrong_scope_event)


def test_basis_closure_replays_parent_origins_and_fails_when_one_disappears(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    imported = _observe(
        ledger,
        artifact_id="evidence.external",
        content=b"external evidence\n",
        kind=BasisKind.EVIDENCE,
        producer=_principal("external.source", AuthorityPrincipalKind.EXTERNAL),
        operation_taint=(TaintLabel.EXTERNAL_UNVERIFIED,),
    )
    human = _principal("human.theo", AuthorityPrincipalKind.HUMAN)
    approval = _observe(
        ledger,
        artifact_id="approval.with-parent",
        content=_approval_bytes(
            approval_id="approval.with-parent",
            reason="approved with external evidence parent",
        ),
        kind=BasisKind.HUMAN_APPROVAL,
        producer=human,
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
        parent_origin_sha256s=(imported.origin.content_sha256,),
    )
    event = _critic_release_event(
        event_id="event.parent-replay",
        principal=human,
        basis=approval.reference,
    )

    assert ledger.validate_basis_closure(event) == (approval,)

    imported.origin_path.unlink()
    with pytest.raises(AuthorityLedgerIntegrityError, match="origin.*missing"):
        ledger.validate_basis_closure(event)


def test_authority_event_id_cannot_be_reused_for_different_content(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    human = _principal("human.theo", AuthorityPrincipalKind.HUMAN)
    approval = _observe(
        ledger,
        artifact_id="approval.collision",
        content=_approval_bytes(approval_id="approval.collision"),
        kind=BasisKind.HUMAN_APPROVAL,
        producer=human,
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
    )
    first = _critic_release_event(
        event_id="event.same-id",
        principal=human,
        basis=approval.reference,
    )
    changed = _critic_release_event(
        event_id="event.same-id",
        principal=human,
        basis=approval.reference,
        reason="different decision basis",
    )

    stored = ledger.issue_authority_event(first)
    assert ledger.issue_authority_event(first) == stored
    with pytest.raises(AuthorityLedgerCollisionError, match="logical identity"):
        ledger.issue_authority_event(changed)
