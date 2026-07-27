# ABOUTME: Exercises human-authorized critic release and retirement through the host authority ledger.
# ABOUTME: Proves acceptance critics additionally require exact escrow, retirement, and reveal closure.

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
from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment,
    CriticFeedbackVisibility,
    CriticRole,
    CriticSpec,
    EvaluationBudgetPartition,
    EvaluationBudgetPlan,
    EvaluationPlan,
    ExecutableAnchorCalibrationCadence,
    ExecutableAnchorCalibrationEvidence,
    ExecutableAnchorCalibrationPolicy,
)
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.meta_harness.acceptance_manifest_escrow import (
    AcceptanceManifestEscrowIntegrityError,
    escrow_acceptance_manifest,
    load_acceptance_manifest_escrow,
)
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
    StoredAuthorityEvent,
    StoredBasis,
)
from aec_bench.meta_harness.critic_governance import (
    StoredAcceptanceManifestReveal,
    StoredCriticGenerationRetirement,
    assert_acceptance_audit_closed,
    assert_critic_generation_released,
    load_acceptance_manifest_reveal,
    load_critic_generation_retirement,
    prepare_acceptance_manifest_reveal,
    prepare_critic_generation_retirement,
    release_acceptance_critic_generation,
    release_critic_generation,
    retire_acceptance_critic_generation,
    retire_critic_generation,
    reveal_retired_acceptance_manifest,
)
from aec_bench.meta_harness.monitors import CycleMonitorReport
from tests.support.governed_promotion import issue_test_governed_promotion


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _host() -> AuthorityPrincipal:
    return AuthorityPrincipal(
        principal_id="host.critic-governance",
        kind=AuthorityPrincipalKind.HOST_POLICY,
    )


def _human() -> AuthorityPrincipal:
    return AuthorityPrincipal(
        principal_id="human.theo",
        kind=AuthorityPrincipalKind.HUMAN,
    )


def _acceptance_material() -> tuple[dict[str, JsonValue], dict[str, JsonValue], str]:
    cases: dict[str, JsonValue] = {
        "case_ids": ["hidden-01"],
        "split": "acceptance",
    }
    scoring: dict[str, JsonValue] = {
        "threshold": 0.8,
        "denominator": "all_planned_cases",
    }
    return cases, scoring, "retirement-escrow-salt"


def _acceptance_critic(
    ledger: AuthorityLedger,
    *,
    version: str = "2.0.0",
    parent_critic_sha256: str | None = None,
) -> CriticSpec:
    cases, scoring, salt = _acceptance_material()
    escrow = escrow_acceptance_manifest(
        ledger=ledger,
        critic_id="critic.acceptance",
        critic_version=version,
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    commitment = AcceptanceManifestCommitment.create(
        critic_id="critic.acceptance",
        critic_version=version,
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
        publication_receipt_sha256=escrow.publication_receipt.content_sha256,
    )
    return CriticSpec(
        critic_id="critic.acceptance",
        version=version,
        role=CriticRole.ACCEPTANCE,
        implementation_sha256=_sha("implementation"),
        rubric_policy_sha256=canonical_content_sha256(scoring),
        case_manifest_sha256=canonical_content_sha256(cases),
        eligibility_policy_sha256=_sha("eligibility"),
        denominator_policy_sha256=_sha("denominator"),
        threshold_policy_sha256=_sha("threshold"),
        evidence_inclusion_policy_sha256=_sha("inclusion"),
        runtime_environment_sha256=_sha("runtime"),
        feedback_visibility=CriticFeedbackVisibility.HOST_ONLY,
        execution_principal_id=f"principal.acceptance-{version}",
        compatibility_generation="evaluation-generation-2",
        parent_critic_sha256=parent_critic_sha256,
        acceptance_manifest_commitment=commitment,
    )


def _development_critic() -> CriticSpec:
    return CriticSpec(
        critic_id="critic.development",
        version="2.0.0",
        role=CriticRole.DEVELOPMENT,
        implementation_sha256=_sha("development-implementation"),
        rubric_policy_sha256=_sha("development-rubric"),
        case_manifest_sha256=_sha("development-cases"),
        eligibility_policy_sha256=_sha("development-eligibility"),
        denominator_policy_sha256=_sha("development-denominator"),
        threshold_policy_sha256=_sha("development-threshold"),
        evidence_inclusion_policy_sha256=_sha("development-inclusion"),
        runtime_environment_sha256=_sha("development-runtime"),
        feedback_visibility=CriticFeedbackVisibility.VISIBLE,
        execution_principal_id="principal.development-v2",
        compatibility_generation="evaluation-generation-2",
    )


def _ledger(tmp_path: Path) -> AuthorityLedger:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    return AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
        typed_basis_models={BasisKind.MONITOR_REPORT: CycleMonitorReport},
    )


def _observe_action_approval(
    ledger: AuthorityLedger,
    *,
    action: AuthorityAction,
    subject_id: str,
    subject_sha256: str,
    producer: AuthorityPrincipal,
    taint: tuple[TaintLabel, ...],
    suffix: str,
) -> StoredBasis:
    approval = HumanAuthorityApproval(
        approval_id=f"approval.{suffix}",
        principal=_human(),
        action=action,
        subject_id=subject_id,
        subject_sha256=subject_sha256,
        approved=True,
        reason=f"approved exact {action.value} transition",
    )
    return ledger.observe_model_basis(
        kind=BasisKind.HUMAN_APPROVAL,
        artifact_id=approval.approval_id,
        model=approval,
        producer=producer,
        producer_process_id="codex-desktop",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="human-approval",
        operation_id=f"approve-{action.value}",
        invocation_id=f"approval-invocation-{suffix}",
        operation_taint=taint,
    )


def _observe_release_approval(
    ledger: AuthorityLedger,
    *,
    critic: CriticSpec,
    producer: AuthorityPrincipal,
    taint: tuple[TaintLabel, ...],
    suffix: str = "release",
) -> StoredBasis:
    return _observe_action_approval(
        ledger,
        action=AuthorityAction.RELEASE_CRITIC_GENERATION,
        subject_id=f"{critic.critic_id}@{critic.version}",
        subject_sha256=critic.content_sha256,
        producer=producer,
        taint=taint,
        suffix=suffix,
    )


def _evaluation_outcome_basis(
    ledger: AuthorityLedger,
    *,
    suffix: str,
    evaluation_plan_sha256: str | None = None,
) -> StoredBasis:
    zero = ResourceCost(
        provider_calls=0,
        tokens=0,
        provider_cost_usd=0.0,
        wall_time_seconds=0.0,
    )
    outcome = EvaluationOutcome(
        evaluation_plan_sha256=evaluation_plan_sha256 or _sha(f"evaluation-plan-{suffix}"),
        candidate_sha256=_sha(f"candidate-{suffix}"),
        evidence_set_sha256=_sha(f"evidence-{suffix}"),
        integrity=IntegrityEvaluation.create(
            checks=(
                IntegrityCheck(
                    check_id="coverage",
                    passed=False,
                    reasons=("provider-free lifecycle fixture",),
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
        reasons=("provider-free lifecycle fixture",),
    )
    host = AuthorityPrincipal(
        principal_id="host.critic-governance",
        kind=AuthorityPrincipalKind.HOST_POLICY,
    )
    return ledger.observe_model_basis(
        kind=BasisKind.EVALUATION_OUTCOME,
        artifact_id=f"evaluation-outcome.{suffix}",
        model=outcome,
        producer=host,
        producer_process_id="aecbench.critic-governance-test",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="critic-history",
        operation_id="record-evaluation-outcome",
        invocation_id=f"evaluation-{suffix}",
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )


def _promotion_event(
    ledger: AuthorityLedger,
    *,
    critic: CriticSpec,
    critic_release: StoredAuthorityEvent,
    suffix: str,
) -> StoredAuthorityEvent:
    return issue_test_governed_promotion(
        ledger=ledger,
        action=AuthorityAction.POLICY_PROMOTION,
        event_id=f"authority.promotion.{suffix}",
        subject_id=f"candidate.{suffix}",
        subject_sha256=_sha(f"candidate-{suffix}"),
        kernel_sha256=_sha("kernel"),
        critic=critic.ref,
        critic_execution_principal_id=critic.execution_principal_id,
        critic_release=critic_release,
    ).promotion


def _release(
    ledger: AuthorityLedger,
    *,
    critic: CriticSpec,
    suffix: str,
) -> StoredAuthorityEvent:
    approval = _observe_release_approval(
        ledger,
        critic=critic,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix=f"release-{suffix}",
    )
    return release_critic_generation(
        ledger=ledger,
        critic_spec=critic,
        human_approval=approval.reference,
        event_id=f"authority.release-{suffix}",
        kernel_sha256=_sha("kernel"),
    )


def _retire(
    ledger: AuthorityLedger,
    *,
    critic: CriticSpec,
    release_authority: StoredAuthorityEvent,
    suffix: str,
) -> StoredCriticGenerationRetirement:
    retirement = prepare_critic_generation_retirement(
        ledger=ledger,
        critic_spec=critic,
        release_authority=release_authority,
        evaluation_outcomes=(),
        promotion_authority_events=(),
    )
    approval = _observe_action_approval(
        ledger,
        action=AuthorityAction.RETIRE_CRITIC_GENERATION,
        subject_id=retirement.retirement_id,
        subject_sha256=retirement.content_sha256,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix=f"retire-{suffix}",
    )
    return retire_acceptance_critic_generation(
        ledger=ledger,
        critic_spec=critic,
        retirement=retirement,
        release_authority=release_authority,
        evaluation_outcomes=(),
        promotion_authority_events=(),
        human_approval=approval.reference,
        event_id=f"authority.retire-{suffix}",
        kernel_sha256=_sha("kernel"),
    )


def _reveal(
    ledger: AuthorityLedger,
    *,
    critic: CriticSpec,
    retirement_authority: StoredAuthorityEvent,
    suffix: str,
) -> StoredAcceptanceManifestReveal:
    cases, scoring, salt = _acceptance_material()
    reveal = prepare_acceptance_manifest_reveal(
        ledger=ledger,
        critic_spec=critic,
        retirement_authority=retirement_authority,
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
        evaluation_outcomes=(),
        promotion_authority_events=(),
    )
    approval = _observe_action_approval(
        ledger,
        action=AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST,
        subject_id=f"{critic.critic_id}@{critic.version}#acceptance-manifest-reveal",
        subject_sha256=reveal.content_sha256,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix=f"reveal-{suffix}",
    )
    return reveal_retired_acceptance_manifest(
        ledger=ledger,
        reveal=reveal,
        retirement_authority=retirement_authority,
        evaluation_outcomes=(),
        promotion_authority_events=(),
        human_approval=approval.reference,
        event_id=f"authority.reveal-{suffix}",
        kernel_sha256=_sha("kernel"),
    )


def _calibration_policy() -> ExecutableAnchorCalibrationPolicy:
    return ExecutableAnchorCalibrationPolicy(
        cadence=ExecutableAnchorCalibrationCadence.EVERY_CRITIC_RELEASE,
    )


def _budget_partition() -> EvaluationBudgetPartition:
    return EvaluationBudgetPartition(
        case_count=1,
        max_attempts=1,
        max_turns=1,
        max_tokens=1,
        max_cost_usd=0.0,
        max_wall_time_seconds=1.0,
    )


def _evaluation_plan(
    *,
    critic: CriticSpec,
    policy: ExecutableAnchorCalibrationPolicy,
) -> EvaluationPlan:
    partition = _budget_partition()
    return EvaluationPlan(
        plan_id="critic-release-calibration",
        evaluation_generation=critic.compatibility_generation,
        kernel_sha256=_sha("kernel"),
        harness_policy_sha256=_sha("harness"),
        candidate_manifest_sha256=_sha("candidates"),
        task_manifest_sha256=_sha("tasks"),
        split_manifest_sha256=_sha("splits"),
        task_verifier_sha256=_sha("verifier"),
        development_critic=_development_critic(),
        acceptance_critic=critic,
        budgets=EvaluationBudgetPlan(
            proposal=partition,
            execution=partition,
            development=partition,
            acceptance=partition,
            red_team=partition,
            monitor=partition,
            audit=partition,
        ),
        integrity_policy_sha256=_sha("integrity"),
        utility_policy_sha256=_sha("utility"),
        selection_null_protocol_sha256=_sha("selection-null"),
        anchor_calibration_policy_sha256=policy.content_sha256,
        monitor_plan_sha256=_sha("monitor"),
        opening_policy_sha256=_sha("opening"),
        stopping_policy_sha256=_sha("stopping"),
        confirmatory_suite_sha256=_sha("confirmatory"),
        challenge_suite_sha256=_sha("challenge"),
    )


def test_acceptance_critic_release_binds_human_approval_spec_and_escrow_commitment(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _acceptance_critic(ledger)
    approval = _observe_release_approval(
        ledger,
        critic=critic,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
    )

    released = release_acceptance_critic_generation(
        ledger=ledger,
        critic_spec=critic,
        human_approval=approval.reference,
        event_id="authority.release-acceptance-v2",
        kernel_sha256=_sha("kernel"),
    )

    assert released.event.action is AuthorityAction.RELEASE_CRITIC_GENERATION
    assert released.event.subject_sha256 == critic.content_sha256
    assert released.event.critic_generation_sha256 == critic.content_sha256
    assert {item.kind for item in released.event.basis} == {
        BasisKind.CRITIC_SPEC,
        BasisKind.EVIDENCE,
        BasisKind.HUMAN_APPROVAL,
    }
    assert any(
        item.artifact_id == "critic-release.authority.release-acceptance-v2.acceptance-escrow-publication"
        for item in released.event.basis
    )
    assert critic.acceptance_manifest_commitment is not None
    assert (
        ledger.resolve_authority_event(
            event_id=released.event.event_id,
            content_sha256=released.event.content_sha256,
        )
        == released
    )


def test_acceptance_critic_release_requires_recoverable_escrow_bytes(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _acceptance_critic(ledger)
    stored = load_acceptance_manifest_escrow(
        ledger=ledger,
        critic_spec=critic,
    )
    stored.payload_path.unlink()
    approval = _observe_release_approval(
        ledger,
        critic=critic,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix="missing-escrow",
    )

    with pytest.raises(
        AcceptanceManifestEscrowIntegrityError,
        match="missing",
    ):
        release_acceptance_critic_generation(
            ledger=ledger,
            critic_spec=critic,
            human_approval=approval.reference,
            event_id="authority.release-missing-escrow",
            kernel_sha256=_sha("kernel"),
        )


def test_candidate_origin_cannot_authorize_an_exactly_shaped_critic_release(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _acceptance_critic(ledger)
    candidate_approval = _observe_release_approval(
        ledger,
        critic=critic,
        producer=AuthorityPrincipal(
            principal_id="candidate.optimizer",
            kind=AuthorityPrincipalKind.CANDIDATE,
        ),
        taint=(TaintLabel.CANDIDATE_AUTHORED,),
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="matching host-observed human"):
        release_acceptance_critic_generation(
            ledger=ledger,
            critic_spec=critic,
            human_approval=candidate_approval.reference,
            event_id="authority.forged-release",
            kernel_sha256=_sha("kernel"),
        )


def test_generic_critic_release_keeps_non_acceptance_roles_under_human_authority(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _development_critic()

    released = _release(
        ledger,
        critic=critic,
        suffix="development-v2",
    )

    assert released.event.action is AuthorityAction.RELEASE_CRITIC_GENERATION
    assert released.event.subject_id == f"{critic.critic_id}@{critic.version}"
    assert released.event.subject_sha256 == critic.content_sha256
    assert released.event.critic_generation_sha256 == critic.content_sha256
    assert (
        assert_critic_generation_released(
            ledger=ledger,
            critic_spec=critic,
            release_authority=released,
        )
        == released
    )


def test_generic_critic_retirement_keeps_development_generation_under_human_authority(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _development_critic()
    released = _release(
        ledger,
        critic=critic,
        suffix="development-retirement-v2",
    )
    retirement = prepare_critic_generation_retirement(
        ledger=ledger,
        critic_spec=critic,
        release_authority=released,
        evaluation_outcomes=(),
        promotion_authority_events=(),
    )
    approval = _observe_action_approval(
        ledger,
        action=AuthorityAction.RETIRE_CRITIC_GENERATION,
        subject_id=retirement.retirement_id,
        subject_sha256=retirement.content_sha256,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix="retire-development-v2",
    )

    retired = retire_critic_generation(
        ledger=ledger,
        critic_spec=critic,
        retirement=retirement,
        release_authority=released,
        evaluation_outcomes=(),
        promotion_authority_events=(),
        human_approval=approval.reference,
        event_id="authority.retire-development-v2",
        kernel_sha256=_sha("kernel"),
    )

    assert retired.authority_event.event.action is (AuthorityAction.RETIRE_CRITIC_GENERATION)
    assert retired.authority_event.event.critic_generation_sha256 == (critic.content_sha256)
    assert retired.authority_event.event.revalidation_triggers == ()
    assert (
        load_critic_generation_retirement(
            ledger=ledger,
            event_id=retired.authority_event.event.event_id,
            content_sha256=retired.authority_event.event.content_sha256,
        )
        == retired
    )


def test_exact_retirement_and_reveal_chain_reloads_from_a_fresh_ledger(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _acceptance_critic(ledger)
    released = _release(
        ledger,
        critic=critic,
        suffix="acceptance-v2",
    )
    first_outcome = _evaluation_outcome_basis(ledger, suffix="first")
    second_outcome = _evaluation_outcome_basis(ledger, suffix="second")
    promotion = _promotion_event(
        ledger,
        critic=critic,
        critic_release=released,
        suffix="first",
    )
    outcomes = (first_outcome.reference, second_outcome.reference)
    promotions = (promotion,)
    retirement = prepare_critic_generation_retirement(
        ledger=ledger,
        critic_spec=critic,
        release_authority=released,
        evaluation_outcomes=outcomes,
        promotion_authority_events=promotions,
    )
    retirement_approval = _observe_action_approval(
        ledger,
        action=AuthorityAction.RETIRE_CRITIC_GENERATION,
        subject_id=retirement.retirement_id,
        subject_sha256=retirement.content_sha256,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix="retire-acceptance-v2",
    )
    retired = retire_acceptance_critic_generation(
        ledger=ledger,
        critic_spec=critic,
        retirement=retirement,
        release_authority=released,
        evaluation_outcomes=outcomes,
        promotion_authority_events=promotions,
        human_approval=retirement_approval.reference,
        event_id="authority.retire-acceptance-v2",
        kernel_sha256=_sha("kernel"),
    )
    reveal = prepare_acceptance_manifest_reveal(
        ledger=ledger,
        critic_spec=critic,
        retirement_authority=retired.authority_event,
        evaluation_outcomes=outcomes,
        promotion_authority_events=promotions,
    )
    cases, scoring, salt = _acceptance_material()
    assert reveal.case_manifest == cases
    assert reveal.scoring_policy == scoring
    assert reveal.salt == salt
    reveal_approval = _observe_action_approval(
        ledger,
        action=AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST,
        subject_id=f"{critic.critic_id}@{critic.version}#acceptance-manifest-reveal",
        subject_sha256=reveal.content_sha256,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix="reveal-acceptance-v2",
    )
    revealed = reveal_retired_acceptance_manifest(
        ledger=ledger,
        reveal=reveal,
        retirement_authority=retired.authority_event,
        evaluation_outcomes=outcomes,
        promotion_authority_events=promotions,
        human_approval=reveal_approval.reference,
        event_id="authority.reveal-acceptance-v2",
        kernel_sha256=_sha("kernel"),
    )

    reloaded_ledger = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(tmp_path / "candidate",),
        typed_basis_models={BasisKind.MONITOR_REPORT: CycleMonitorReport},
    )
    reloaded_retirement = load_critic_generation_retirement(
        ledger=reloaded_ledger,
        event_id=retired.authority_event.event.event_id,
        content_sha256=retired.authority_event.event.content_sha256,
    )
    reloaded_reveal = load_acceptance_manifest_reveal(
        ledger=reloaded_ledger,
        event_id=revealed.authority_event.event.event_id,
        content_sha256=revealed.authority_event.event.content_sha256,
    )

    assert reloaded_retirement == retired
    assert reloaded_reveal == revealed
    assert reloaded_reveal.retirement == reloaded_retirement.retirement
    assert reloaded_reveal.reveal.retirement_authority_event_sha256 == (
        reloaded_retirement.authority_event.event.content_sha256
    )
    assert reloaded_reveal.reveal.evaluation_outcome_sha256s == retirement.evaluation_outcome_sha256s
    assert reloaded_reveal.reveal.promotion_sha256s == retirement.promotion_authority_event_sha256s


def test_reveal_fails_before_an_exact_retirement_authority_event(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _acceptance_critic(ledger)
    released = _release(
        ledger,
        critic=critic,
        suffix="acceptance-before-retirement",
    )
    cases, scoring, salt = _acceptance_material()

    with pytest.raises(AuthorityLedgerIntegrityError, match="retirement authority"):
        prepare_acceptance_manifest_reveal(
            ledger=ledger,
            critic_spec=critic,
            retirement_authority=released,
            case_manifest=cases,
            scoring_policy=scoring,
            salt=salt,
            evaluation_outcomes=(),
            promotion_authority_events=(),
        )


def test_retirement_rejects_a_release_for_the_wrong_critic_subject(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    acceptance = _acceptance_critic(ledger)
    development = _development_critic()
    wrong_release = _release(
        ledger,
        critic=development,
        suffix="wrong-subject",
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="exact critic subject"):
        prepare_critic_generation_retirement(
            ledger=ledger,
            critic_spec=acceptance,
            release_authority=wrong_release,
            evaluation_outcomes=(),
            promotion_authority_events=(),
        )


def test_non_human_origin_cannot_authorize_acceptance_retirement(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _acceptance_critic(ledger)
    released = _release(
        ledger,
        critic=critic,
        suffix="acceptance-non-human-retirement",
    )
    retirement = prepare_critic_generation_retirement(
        ledger=ledger,
        critic_spec=critic,
        release_authority=released,
        evaluation_outcomes=(),
        promotion_authority_events=(),
    )
    candidate_approval = _observe_action_approval(
        ledger,
        action=AuthorityAction.RETIRE_CRITIC_GENERATION,
        subject_id=retirement.retirement_id,
        subject_sha256=retirement.content_sha256,
        producer=AuthorityPrincipal(
            principal_id="candidate.optimizer",
            kind=AuthorityPrincipalKind.CANDIDATE,
        ),
        taint=(TaintLabel.CANDIDATE_AUTHORED,),
        suffix="forged-retirement",
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="matching host-observed human"):
        retire_acceptance_critic_generation(
            ledger=ledger,
            critic_spec=critic,
            retirement=retirement,
            release_authority=released,
            evaluation_outcomes=(),
            promotion_authority_events=(),
            human_approval=candidate_approval.reference,
            event_id="authority.forged-retirement",
            kernel_sha256=_sha("kernel"),
        )


@pytest.mark.parametrize(
    ("case_manifest", "scoring_policy", "salt", "message"),
    [
        (
            {"case_ids": ["wrong-hidden-case"], "split": "acceptance"},
            _acceptance_material()[1],
            _acceptance_material()[2],
            "case manifest",
        ),
        (
            _acceptance_material()[0],
            {"threshold": 0.1, "denominator": "changed"},
            _acceptance_material()[2],
            "scoring policy",
        ),
        (
            _acceptance_material()[0],
            _acceptance_material()[1],
            "wrong-salt",
            "salted commitment",
        ),
    ],
)
def test_reveal_rejects_wrong_escrow_material(
    tmp_path: Path,
    case_manifest: dict[str, JsonValue],
    scoring_policy: dict[str, JsonValue],
    salt: str,
    message: str,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _acceptance_critic(ledger)
    released = _release(
        ledger,
        critic=critic,
        suffix=f"wrong-material-{message.replace(' ', '-')}",
    )
    retirement = prepare_critic_generation_retirement(
        ledger=ledger,
        critic_spec=critic,
        release_authority=released,
        evaluation_outcomes=(),
        promotion_authority_events=(),
    )
    approval = _observe_action_approval(
        ledger,
        action=AuthorityAction.RETIRE_CRITIC_GENERATION,
        subject_id=retirement.retirement_id,
        subject_sha256=retirement.content_sha256,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix=f"retire-wrong-material-{message.replace(' ', '-')}",
    )
    retired = retire_acceptance_critic_generation(
        ledger=ledger,
        critic_spec=critic,
        retirement=retirement,
        release_authority=released,
        evaluation_outcomes=(),
        promotion_authority_events=(),
        human_approval=approval.reference,
        event_id=f"authority.retire-wrong-material-{message.replace(' ', '-')}",
        kernel_sha256=_sha("kernel"),
    )

    with pytest.raises(ValueError, match=message):
        prepare_acceptance_manifest_reveal(
            ledger=ledger,
            critic_spec=critic,
            retirement_authority=retired.authority_event,
            case_manifest=case_manifest,
            scoring_policy=scoring_policy,
            salt=salt,
            evaluation_outcomes=(),
            promotion_authority_events=(),
        )


def test_reveal_rejects_missing_retirement_bound_historical_coverage(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _acceptance_critic(ledger)
    released = _release(
        ledger,
        critic=critic,
        suffix="coverage",
    )
    first_outcome = _evaluation_outcome_basis(ledger, suffix="coverage-first")
    second_outcome = _evaluation_outcome_basis(ledger, suffix="coverage-second")
    all_outcomes: tuple[BasisReference, ...] = (
        first_outcome.reference,
        second_outcome.reference,
    )
    retirement = prepare_critic_generation_retirement(
        ledger=ledger,
        critic_spec=critic,
        release_authority=released,
        evaluation_outcomes=all_outcomes,
        promotion_authority_events=(),
    )
    approval = _observe_action_approval(
        ledger,
        action=AuthorityAction.RETIRE_CRITIC_GENERATION,
        subject_id=retirement.retirement_id,
        subject_sha256=retirement.content_sha256,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix="retire-coverage",
    )
    retired = retire_acceptance_critic_generation(
        ledger=ledger,
        critic_spec=critic,
        retirement=retirement,
        release_authority=released,
        evaluation_outcomes=all_outcomes,
        promotion_authority_events=(),
        human_approval=approval.reference,
        event_id="authority.retire-coverage",
        kernel_sha256=_sha("kernel"),
    )
    cases, scoring, salt = _acceptance_material()

    with pytest.raises(AuthorityLedgerIntegrityError, match="historical coverage"):
        prepare_acceptance_manifest_reveal(
            ledger=ledger,
            critic_spec=critic,
            retirement_authority=retired.authority_event,
            case_manifest=cases,
            scoring_policy=scoring,
            salt=salt,
            evaluation_outcomes=(first_outcome.reference,),
            promotion_authority_events=(),
        )


def test_campaign_audit_closure_fails_closed_until_retired_manifest_is_revealed(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    critic = _acceptance_critic(ledger)
    released = _release(
        ledger,
        critic=critic,
        suffix="closure-parent",
    )
    retired = _retire(
        ledger,
        critic=critic,
        release_authority=released,
        suffix="closure-parent",
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="unrevealed"):
        assert_acceptance_audit_closed(
            ledger=ledger,
            retirement_authority=retired.authority_event,
            reveal_authority=None,
        )

    revealed = _reveal(
        ledger,
        critic=critic,
        retirement_authority=retired.authority_event,
        suffix="closure-parent",
    )
    closure = assert_acceptance_audit_closed(
        ledger=ledger,
        retirement_authority=retired.authority_event,
        reveal_authority=revealed.authority_event,
    )

    assert closure.retirement == retired
    assert closure.reveal == revealed


def test_successor_acceptance_release_requires_parent_audit_closure(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    parent = _acceptance_critic(ledger)
    parent_release = _release(
        ledger,
        critic=parent,
        suffix="successor-parent",
    )
    parent_retirement = _retire(
        ledger,
        critic=parent,
        release_authority=parent_release,
        suffix="successor-parent",
    )
    successor = _acceptance_critic(
        ledger,
        version="3.0.0",
        parent_critic_sha256=parent.content_sha256,
    )
    approval = _observe_release_approval(
        ledger,
        critic=successor,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix="successor",
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="unrevealed"):
        release_acceptance_critic_generation(
            ledger=ledger,
            critic_spec=successor,
            human_approval=approval.reference,
            event_id="authority.release-successor",
            kernel_sha256=_sha("kernel"),
            prior_retirement_authority=parent_retirement.authority_event,
            prior_reveal_authority=None,
        )

    parent_reveal = _reveal(
        ledger,
        critic=parent,
        retirement_authority=parent_retirement.authority_event,
        suffix="successor-parent",
    )
    released = release_acceptance_critic_generation(
        ledger=ledger,
        critic_spec=successor,
        human_approval=approval.reference,
        event_id="authority.release-successor",
        kernel_sha256=_sha("kernel"),
        prior_retirement_authority=parent_retirement.authority_event,
        prior_reveal_authority=parent_reveal.authority_event,
    )

    authority_bases = tuple(
        ledger.resolve_model_basis(reference, AuthorityEvent)[1]
        for reference in released.event.basis
        if reference.kind is BasisKind.AUTHORITY_EVENT
    )
    assert {event.content_sha256 for event in authority_bases} == {
        parent_retirement.authority_event.event.content_sha256,
        parent_reveal.authority_event.event.content_sha256,
    }


def test_release_binds_completed_executable_anchor_calibration_when_declared(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    policy = _calibration_policy()
    critic = _acceptance_critic(ledger)
    plan = _evaluation_plan(critic=critic, policy=policy)
    approval = _observe_release_approval(
        ledger,
        critic=critic,
        producer=_human(),
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        suffix="calibrated-release",
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="executable-anchor calibration"):
        release_acceptance_critic_generation(
            ledger=ledger,
            critic_spec=critic,
            human_approval=approval.reference,
            event_id="authority.release-calibrated",
            kernel_sha256=_sha("kernel"),
            evaluation_plan=plan,
            anchor_calibration_policy=policy,
            anchor_calibration_evidence=None,
        )

    outcome = _evaluation_outcome_basis(
        ledger,
        suffix="release-calibration",
        evaluation_plan_sha256=plan.content_sha256,
    )
    _, outcome_model = ledger.resolve_model_basis(
        outcome.reference,
        EvaluationOutcome,
    )
    incomplete_evidence = ExecutableAnchorCalibrationEvidence(
        calibration_id="critic.acceptance@2.0.0#incomplete-release-calibration",
        evaluation_plan_sha256=plan.content_sha256,
        critic_generation_sha256=critic.content_sha256,
        anchor_calibration_policy_sha256=policy.content_sha256,
        executable_anchor_sha256s=(outcome_model.evidence_set_sha256,),
        evaluation_outcomes=(outcome.reference,),
        completed=False,
        passed=False,
    )
    incomplete_basis = ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=incomplete_evidence.calibration_id,
        model=incomplete_evidence,
        producer=AuthorityPrincipal(
            principal_id="critic.anchor-calibration",
            kind=AuthorityPrincipalKind.CRITIC_AUTHORITY,
        ),
        producer_process_id="aecbench.critic-calibration",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="executable-anchor-calibration",
        operation_id="calibrate-critic-release",
        invocation_id="incomplete-calibration-release",
        operation_taint=(
            TaintLabel.CRITIC_AUTHORITY,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="completed passing"):
        release_acceptance_critic_generation(
            ledger=ledger,
            critic_spec=critic,
            human_approval=approval.reference,
            event_id="authority.release-calibrated",
            kernel_sha256=_sha("kernel"),
            evaluation_plan=plan,
            anchor_calibration_policy=policy,
            anchor_calibration_evidence=incomplete_basis.reference,
        )

    mismatched_evidence = ExecutableAnchorCalibrationEvidence(
        calibration_id="critic.acceptance@2.0.0#mismatched-release-calibration",
        evaluation_plan_sha256=plan.content_sha256,
        critic_generation_sha256=critic.content_sha256,
        anchor_calibration_policy_sha256=policy.content_sha256,
        executable_anchor_sha256s=(_sha("unrelated-anchor"),),
        evaluation_outcomes=(outcome.reference,),
        completed=True,
        passed=True,
    )
    mismatched_basis = ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=mismatched_evidence.calibration_id,
        model=mismatched_evidence,
        producer=AuthorityPrincipal(
            principal_id="critic.anchor-calibration",
            kind=AuthorityPrincipalKind.CRITIC_AUTHORITY,
        ),
        producer_process_id="aecbench.critic-calibration",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="executable-anchor-calibration",
        operation_id="calibrate-critic-release",
        invocation_id="mismatched-calibration-release",
        operation_taint=(
            TaintLabel.CRITIC_AUTHORITY,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="anchor identities.*outcomes"):
        release_acceptance_critic_generation(
            ledger=ledger,
            critic_spec=critic,
            human_approval=approval.reference,
            event_id="authority.release-calibrated",
            kernel_sha256=_sha("kernel"),
            evaluation_plan=plan,
            anchor_calibration_policy=policy,
            anchor_calibration_evidence=mismatched_basis.reference,
        )

    evidence = ExecutableAnchorCalibrationEvidence(
        calibration_id="critic.acceptance@2.0.0#release-calibration",
        evaluation_plan_sha256=plan.content_sha256,
        critic_generation_sha256=critic.content_sha256,
        anchor_calibration_policy_sha256=policy.content_sha256,
        executable_anchor_sha256s=(outcome_model.evidence_set_sha256,),
        evaluation_outcomes=(outcome.reference,),
        completed=True,
        passed=True,
    )
    evidence_basis = ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=evidence.calibration_id,
        model=evidence,
        producer=AuthorityPrincipal(
            principal_id="critic.anchor-calibration",
            kind=AuthorityPrincipalKind.CRITIC_AUTHORITY,
        ),
        producer_process_id="aecbench.critic-calibration",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="executable-anchor-calibration",
        operation_id="calibrate-critic-release",
        invocation_id="calibration-release",
        operation_taint=(
            TaintLabel.CRITIC_AUTHORITY,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )

    released = release_acceptance_critic_generation(
        ledger=ledger,
        critic_spec=critic,
        human_approval=approval.reference,
        event_id="authority.release-calibrated",
        kernel_sha256=_sha("kernel"),
        evaluation_plan=plan,
        anchor_calibration_policy=policy,
        anchor_calibration_evidence=evidence_basis.reference,
    )

    assert evidence_basis.reference in released.event.basis
    assert {reference.artifact_id for reference in released.event.basis if reference.kind is BasisKind.EVIDENCE} == {
        "critic.acceptance@2.0.0#release-calibration",
        "critic-release.authority.release-calibrated.acceptance-escrow-publication",
        "critic-release.authority.release-calibrated.anchor-calibration-policy",
        "critic-release.authority.release-calibrated.evaluation-plan",
    }
    assert "executable_anchor_recalibration_due" in released.event.revalidation_triggers
