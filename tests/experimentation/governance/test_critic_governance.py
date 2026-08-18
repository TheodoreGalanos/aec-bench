# ABOUTME: Tests human-authorized critic lifecycle operations against one published regime identity.
# ABOUTME: Verifies hidden escrow, retirement reveal, exact references, and embedded calibration policy.

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import JsonValue

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
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
from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment,
    AcceptanceManifestReveal,
    CalibrationPolicy,
    Critic,
    ExecutableAnchorCalibrationEvidence,
    ExecutableAnchorCalibrationPolicy,
    acceptance_manifest_reveal_commitment,
)
from aec_bench.contracts.evaluation_refs import CriticRole
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.evaluation.regime import expected_evaluation_regime_ref
from aec_bench.experimentation.governance.acceptance_manifest_escrow import (
    AcceptanceManifestEscrowIntegrityError,
    escrow_acceptance_manifest,
    load_acceptance_manifest_escrow,
)
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
    StoredBasis,
)
from aec_bench.experimentation.governance.critic_lifecycle import (
    assert_acceptance_audit_closed,
    assert_critic_released,
    load_acceptance_manifest_reveal,
    load_critic_retirement,
    prepare_acceptance_manifest_reveal,
    prepare_critic_retirement,
    release_acceptance_critic,
    retire_acceptance_critic,
    reveal_retired_acceptance_manifest,
)
from aec_bench.experimentation.governance.critic_lifecycle.contracts import critic_retirement_commitment
from tests.support.evaluation_regimes import make_regime


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _kernel_ref() -> KernelRef:
    return KernelRef(kernel_id="aec-bench.adaptive-harness", version="1.6.0")


def _human() -> AuthorityPrincipal:
    return AuthorityPrincipal(principal_id="human.theo", kind=AuthorityPrincipalKind.HUMAN)


def _host_runtime() -> AuthorityPrincipal:
    return AuthorityPrincipal(principal_id="host.runtime", kind=AuthorityPrincipalKind.HOST_RUNTIME)


def _ledger(tmp_path: Path) -> AuthorityLedger:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    return AuthorityLedger(tmp_path / "authority", candidate_roots=(candidate_root,))


def _acceptance_material() -> tuple[dict[str, JsonValue], dict[str, JsonValue], str]:
    return (
        {"case_ids": ["hidden-01"], "split": "acceptance"},
        {"threshold": 0.8, "denominator": "all_planned_cases"},
        "retirement-escrow-salt",
    )


def _regime_surface(*, calibration: bool = False):
    cases, scoring, salt = _acceptance_material()
    commitment = AcceptanceManifestCommitment.create(
        critic_id="critic.acceptance",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    base = make_regime(regime_id="evaluation.critic-governance")
    acceptance = base.critic(CriticRole.ACCEPTANCE).model_copy(update={"acceptance_manifest_commitment": commitment})
    critics = tuple(acceptance if critic.role is CriticRole.ACCEPTANCE else critic for critic in base.critics)
    updates: dict[str, object] = {"critics": critics}
    if calibration:
        policy = ExecutableAnchorCalibrationPolicy()
        updates["calibration_policy"] = CalibrationPolicy(
            policy_id="calibration.executable-anchor",
            configuration={"executable_anchor": policy.model_dump(mode="json")},
        )
    regime = type(base).model_validate({**base.model_dump(mode="python"), **updates})
    return regime, expected_evaluation_regime_ref(regime), acceptance


def _approval(
    ledger: AuthorityLedger,
    *,
    action: AuthorityAction,
    subject_id: str,
    subject_sha256: str,
    suffix: str,
) -> StoredBasis:
    approval = HumanAuthorityApproval(
        approval_id=f"approval.{suffix}",
        principal=_human(),
        action=action,
        subject_id=subject_id,
        subject_sha256=subject_sha256,
        approved=True,
        reason=f"approved {action.value}",
    )
    return ledger.observe_model_basis(
        kind=BasisKind.HUMAN_APPROVAL,
        artifact_id=approval.approval_id,
        model=approval,
        producer=_human(),
        producer_process_id="codex-desktop",
        observed_by=_host_runtime(),
        channel="human-approval",
        operation_id=f"approve-{action.value}",
        invocation_id=f"approval-{suffix}",
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
    )


def _escrow(ledger: AuthorityLedger, regime_ref, critic: Critic) -> None:
    cases, scoring, salt = _acceptance_material()
    escrow_acceptance_manifest(
        ledger=ledger,
        evaluation_regime=regime_ref,
        critic_id=critic.critic_id,
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )


def _release(ledger: AuthorityLedger, regime, regime_ref, critic: Critic, *, evidence=None):
    approval = _approval(
        ledger,
        action=AuthorityAction.RELEASE_CRITIC,
        subject_id=f"{regime_ref.regime_id}:{critic.critic_id}",
        subject_sha256=regime_ref.artifact.sha256,
        suffix="release",
    )
    return release_acceptance_critic(
        ledger=ledger,
        evaluation_regime=regime,
        evaluation_regime_ref=regime_ref,
        critic=critic,
        human_approval=approval.reference,
        event_id="authority.release",
        kernel_ref=_kernel_ref(),
        anchor_calibration_evidence=evidence,
    )


def test_acceptance_escrow_is_scoped_to_exact_regime_and_verifies_commitment(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    regime, regime_ref, critic = _regime_surface()
    _escrow(ledger, regime_ref, critic)

    stored = load_acceptance_manifest_escrow(
        ledger=ledger,
        evaluation_regime=regime_ref,
        critic=critic,
    )

    assert stored.payload.evaluation_regime == regime_ref
    assert "hidden-01" not in regime.model_dump_json()


def test_acceptance_escrow_rejects_a_different_regime_reference(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _, regime_ref, critic = _regime_surface()
    _escrow(ledger, regime_ref, critic)
    other = regime_ref.model_copy(update={"artifact": regime_ref.artifact.model_copy(update={"sha256": _sha("other")})})

    with pytest.raises(AcceptanceManifestEscrowIntegrityError, match="not published"):
        load_acceptance_manifest_escrow(ledger=ledger, evaluation_regime=other, critic=critic)


def test_release_binds_one_regime_artifact_and_stable_critic_id(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    regime, regime_ref, critic = _regime_surface()
    _escrow(ledger, regime_ref, critic)

    released = _release(ledger, regime, regime_ref, critic)

    assert released.event.subject_sha256 == regime_ref.artifact.sha256
    assert released.event.critic == critic.ref(regime_ref)
    assert_critic_released(
        ledger=ledger,
        critic=critic,
        critic_ref=critic.ref(regime_ref),
        release_authority=released,
    )


def test_release_replay_requires_the_exact_regime_evidence(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    regime, regime_ref, critic = _regime_surface()
    _escrow(ledger, regime_ref, critic)
    released = _release(ledger, regime, regime_ref, critic)
    incomplete = ledger.issue_authority_event(
        type(released.event).model_validate(
            {
                **released.event.model_dump(mode="python", exclude={"content_sha256", "event_id", "basis"}),
                "event_id": "authority.release-without-regime",
                "basis": tuple(
                    reference for reference in released.event.basis if reference.kind is not BasisKind.EVIDENCE
                ),
            }
        )
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="evaluation regime authority requires one exact"):
        assert_critic_released(
            ledger=ledger,
            critic=critic,
            critic_ref=critic.ref(regime_ref),
            release_authority=incomplete,
        )


def test_release_rejects_regime_bytes_that_do_not_match_the_reference(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    regime, regime_ref, critic = _regime_surface()
    _escrow(ledger, regime_ref, critic)
    changed = regime.model_copy(
        update={"acceptance_policy": regime.acceptance_policy.model_copy(update={"policy_id": "changed"})}
    )
    approval = _approval(
        ledger,
        action=AuthorityAction.RELEASE_CRITIC,
        subject_id=f"{regime_ref.regime_id}:{critic.critic_id}",
        subject_sha256=regime_ref.artifact.sha256,
        suffix="changed-release",
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="canonical regime bytes"):
        release_acceptance_critic(
            ledger=ledger,
            evaluation_regime=changed,
            evaluation_regime_ref=regime_ref,
            critic=critic,
            human_approval=approval.reference,
            event_id="authority.changed-release",
            kernel_ref=_kernel_ref(),
        )


def test_retirement_reveal_round_trip_closes_acceptance_audit(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    regime, regime_ref, critic = _regime_surface()
    _escrow(ledger, regime_ref, critic)
    released = _release(ledger, regime, regime_ref, critic)
    critic_ref = critic.ref(regime_ref)
    retirement = prepare_critic_retirement(
        ledger=ledger,
        critic=critic,
        critic_ref=critic_ref,
        release_authority=released,
        evaluation_outcomes=(),
        promotion_authority_events=(),
    )
    retirement_approval = _approval(
        ledger,
        action=AuthorityAction.RETIRE_CRITIC,
        subject_id=retirement.retirement_id,
        subject_sha256=critic_retirement_commitment(retirement),
        suffix="retirement",
    )
    retired = retire_acceptance_critic(
        ledger=ledger,
        critic=critic,
        critic_ref=critic_ref,
        retirement=retirement,
        release_authority=released,
        evaluation_outcomes=(),
        promotion_authority_events=(),
        human_approval=retirement_approval.reference,
        event_id="authority.retirement",
        kernel_ref=_kernel_ref(),
    )
    reveal = prepare_acceptance_manifest_reveal(
        ledger=ledger,
        evaluation_regime=regime_ref,
        critic=critic,
        retirement_authority=retired.authority_event,
        evaluation_outcomes=(),
        promotion_authority_events=(),
    )
    reveal_approval = _approval(
        ledger,
        action=AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST,
        subject_id=f"{regime_ref.regime_id}:{critic.critic_id}#acceptance-manifest-reveal",
        subject_sha256=acceptance_manifest_reveal_commitment(reveal),
        suffix="reveal",
    )
    revealed = reveal_retired_acceptance_manifest(
        ledger=ledger,
        reveal=reveal,
        retirement_authority=retired.authority_event,
        evaluation_outcomes=(),
        promotion_authority_events=(),
        human_approval=reveal_approval.reference,
        event_id="authority.reveal",
        kernel_ref=_kernel_ref(),
    )

    assert (
        load_critic_retirement(
            ledger=ledger,
            event_id=retired.authority_event.event.event_id,
            content_sha256=retired.authority_event.event.content_sha256,
        )
        == retired
    )
    assert (
        load_acceptance_manifest_reveal(
            ledger=ledger,
            event_id=revealed.authority_event.event.event_id,
            content_sha256=revealed.authority_event.event.content_sha256,
        )
        == revealed
    )
    assert_acceptance_audit_closed(
        ledger=ledger,
        retirement_authority=retired.authority_event,
        reveal_authority=revealed.authority_event,
    )


def test_reveal_mismatch_fails_before_authority(tmp_path: Path) -> None:
    regime, regime_ref, critic = _regime_surface()
    del regime
    cases, scoring, _ = _acceptance_material()

    with pytest.raises(ValueError, match="salted commitment"):
        AcceptanceManifestReveal.create(
            evaluation_regime=regime_ref,
            critic=critic,
            case_manifest=cases,
            scoring_policy=scoring,
            salt="wrong-salt",
            retirement_authority_event_sha256=_sha("retirement"),
        )


def test_embedded_calibration_policy_requires_matching_passing_evidence(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    regime, regime_ref, critic = _regime_surface(calibration=True)
    _escrow(ledger, regime_ref, critic)
    with pytest.raises(AuthorityLedgerIntegrityError, match="requires executable-anchor"):
        _release(ledger, regime, regime_ref, critic)

    outcome_basis, outcome = _evaluation_outcome_basis(ledger)
    calibration = ExecutableAnchorCalibrationEvidence(
        calibration_id="calibration.acceptance",
        evaluation_regime=regime_ref,
        critic=critic.ref(regime_ref),
        executable_anchor_sha256s=(outcome.evidence_set_sha256,),
        evaluation_outcomes=(outcome_basis.reference,),
        completed=True,
        passed=True,
    )
    calibration_basis = ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id="calibration.acceptance",
        model=calibration,
        producer=_host_runtime(),
        producer_process_id="aecbench.test",
        observed_by=_host_runtime(),
        channel="calibration",
        operation_id="calibrate-critic",
        invocation_id="calibration.acceptance",
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )

    released = _release(ledger, regime, regime_ref, critic, evidence=calibration_basis.reference)

    assert released.event.critic == critic.ref(regime_ref)


def _evaluation_outcome_basis(ledger: AuthorityLedger) -> tuple[StoredBasis, EvaluationOutcome]:
    zero = ResourceCost(provider_calls=0, tokens=0, provider_cost_usd=0.0, wall_time_seconds=0.0)
    outcome = EvaluationOutcome(
        candidate_sha256=_sha("candidate"),
        evidence_set_sha256=_sha("executable-anchor"),
        integrity=IntegrityEvaluation.create(
            checks=(IntegrityCheck(check_id="coverage", passed=False, reasons=("fixture",)),)
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
        reasons=("fixture",),
    )
    stored = ledger.observe_model_basis(
        kind=BasisKind.EVALUATION_OUTCOME,
        artifact_id="evaluation-outcome.calibration",
        model=outcome,
        producer=_host_runtime(),
        producer_process_id="aecbench.test",
        observed_by=_host_runtime(),
        channel="calibration",
        operation_id="record-anchor",
        invocation_id="anchor",
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    return stored, outcome
