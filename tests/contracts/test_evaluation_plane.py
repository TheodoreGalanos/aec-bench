# ABOUTME: Tests immutable evaluation identities, critic separation, budgets, and escrow reveal.
# ABOUTME: Proves acceptance comparisons fail closed without exposing live hidden case manifests.

from __future__ import annotations

import hashlib

import pytest
from pydantic import JsonValue, ValidationError

from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment,
    AcceptanceManifestReveal,
    CriticFeedbackVisibility,
    CriticReleaseAuthorityRef,
    CriticRole,
    CriticSpec,
    EvaluationBudgetPartition,
    EvaluationBudgetPlan,
    EvaluationPlan,
    EvaluationPlanAuthorityScope,
    EvaluationPlanRef,
    TaskVerifierFileInventoryEntry,
    TaskVerifierSurface,
    TaskVerifierSurfaceScope,
    assert_acceptance_compatible,
)
from aec_bench.contracts.harness_kernel import canonical_content_sha256


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _commitment(
    *,
    critic_id: str = "critic.acceptance",
    critic_version: str = "1.0.0",
) -> tuple[
    AcceptanceManifestCommitment,
    str,
    dict[str, JsonValue],
    dict[str, JsonValue],
]:
    salt = "retirement-escrow-salt"
    cases: dict[str, JsonValue] = {
        "case_ids": ["hidden-01", "hidden-02"],
        "split": "acceptance",
    }
    scoring: dict[str, JsonValue] = {
        "threshold": 0.8,
        "denominator": "all_planned_cases",
    }
    commitment = AcceptanceManifestCommitment.create(
        critic_id=critic_id,
        critic_version=critic_version,
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
        publication_receipt_sha256=_sha("commitment-publication"),
    )
    return commitment, salt, cases, scoring


def _critic(
    role: CriticRole,
    *,
    case_label: str,
    principal: str,
    denominator_label: str = "all-planned-cases",
    commitment: AcceptanceManifestCommitment | None = None,
    case_manifest_sha256: str | None = None,
    rubric_policy_sha256: str | None = None,
) -> CriticSpec:
    return CriticSpec(
        critic_id=f"critic.{role.value}",
        version="1.0.0",
        role=role,
        implementation_sha256=_sha("shared-deterministic-scoring"),
        rubric_policy_sha256=rubric_policy_sha256 or _sha("shared-rubric"),
        case_manifest_sha256=case_manifest_sha256 or _sha(case_label),
        eligibility_policy_sha256=_sha("complete-evidence-only"),
        denominator_policy_sha256=_sha(denominator_label),
        threshold_policy_sha256=_sha("threshold"),
        evidence_inclusion_policy_sha256=_sha("inclusion"),
        runtime_environment_sha256=_sha("runtime"),
        feedback_visibility=(
            CriticFeedbackVisibility.VISIBLE if role is CriticRole.DEVELOPMENT else CriticFeedbackVisibility.HOST_ONLY
        ),
        execution_principal_id=principal,
        compatibility_generation="evaluation-generation-1",
        acceptance_manifest_commitment=commitment,
    )


def _budgets() -> EvaluationBudgetPlan:
    partition = EvaluationBudgetPartition(
        case_count=8,
        max_attempts=8,
        max_turns=32,
        max_tokens=100_000,
        max_cost_usd=1.0,
        max_wall_time_seconds=600.0,
    )
    return EvaluationBudgetPlan(
        proposal=partition,
        execution=partition,
        development=partition,
        acceptance=partition,
        red_team=partition,
        monitor=partition,
        audit=partition,
    )


def _plan(
    *,
    development: CriticSpec | None = None,
    acceptance: CriticSpec | None = None,
    task_verifier_sha256: str | None = None,
) -> EvaluationPlan:
    commitment, *_ = _commitment()
    return EvaluationPlan(
        plan_id="evaluation-plan.stage-9",
        evaluation_generation="evaluation-generation-1",
        kernel_sha256=_sha("kernel"),
        harness_policy_sha256=_sha("harness-policy"),
        candidate_manifest_sha256=_sha("candidate-manifest"),
        task_manifest_sha256=_sha("task-manifest"),
        split_manifest_sha256=_sha("split-manifest"),
        task_verifier_sha256=task_verifier_sha256 or _sha("task-verifier"),
        development_critic=development
        or _critic(
            CriticRole.DEVELOPMENT,
            case_label="development-cases",
            principal="principal.dev",
        ),
        acceptance_critic=acceptance
        or _critic(
            CriticRole.ACCEPTANCE,
            case_label="acceptance-cases",
            principal="principal.accept",
            commitment=commitment,
        ),
        red_team_critic=_critic(
            CriticRole.RED_TEAM,
            case_label="red-team-cases",
            principal="principal.red",
        ),
        budgets=_budgets(),
        integrity_policy_sha256=_sha("integrity-policy"),
        utility_policy_sha256=_sha("utility-policy"),
        selection_null_protocol_sha256=_sha("selection-null"),
        anchor_calibration_policy_sha256=_sha("anchor-calibration"),
        monitor_plan_sha256=_sha("monitor-plan"),
        opening_policy_sha256=_sha("opening-policy"),
        stopping_policy_sha256=_sha("stopping-policy"),
        confirmatory_suite_sha256=_sha("confirmatory-suite"),
        challenge_suite_sha256=_sha("challenge-suite"),
    )


def test_acceptance_critic_requires_salted_manifest_commitment() -> None:
    with pytest.raises(ValidationError, match="acceptance critic requires"):
        _critic(
            CriticRole.ACCEPTANCE,
            case_label="acceptance-cases",
            principal="principal.accept",
        )


def test_shared_scoring_code_is_allowed_but_cases_and_principals_must_be_separate() -> None:
    commitment, *_ = _commitment()
    development = _critic(
        CriticRole.DEVELOPMENT,
        case_label="development-cases",
        principal="principal.dev",
    )
    acceptance = _critic(
        CriticRole.ACCEPTANCE,
        case_label="acceptance-cases",
        principal="principal.accept",
        commitment=commitment,
    )

    plan = _plan(development=development, acceptance=acceptance)

    assert plan.development_critic.implementation_sha256 == plan.acceptance_critic.implementation_sha256
    assert plan.development_critic.case_manifest_sha256 != plan.acceptance_critic.case_manifest_sha256
    assert plan.development_critic.execution_principal_id != plan.acceptance_critic.execution_principal_id

    with pytest.raises(ValidationError, match="case manifests must be distinct"):
        _plan(
            development=development,
            acceptance=_critic(
                CriticRole.ACCEPTANCE,
                case_label="development-cases",
                principal="principal.accept",
                commitment=commitment,
            ),
        )

    with pytest.raises(ValidationError, match="execution principals must be distinct"):
        _plan(
            development=development,
            acceptance=_critic(
                CriticRole.ACCEPTANCE,
                case_label="acceptance-cases",
                principal="principal.dev",
                commitment=commitment,
            ),
        )


def test_acceptance_identity_changes_for_denominator_policy_and_comparison_fails_closed() -> None:
    commitment, *_ = _commitment()
    original = _plan()
    changed = _plan(
        acceptance=_critic(
            CriticRole.ACCEPTANCE,
            case_label="acceptance-cases",
            principal="principal.accept",
            denominator_label="eligible-only",
            commitment=commitment,
        )
    )

    assert original.acceptance_critic.content_sha256 != changed.acceptance_critic.content_sha256
    with pytest.raises(ValueError, match="acceptance critic identity"):
        assert_acceptance_compatible(original, changed)


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    [
        ("implementation_sha256", _sha("different-implementation")),
        ("rubric_policy_sha256", _sha("different-rubric")),
        ("case_manifest_sha256", _sha("different-cases")),
        ("eligibility_policy_sha256", _sha("different-eligibility")),
        ("denominator_policy_sha256", _sha("different-denominator")),
        ("threshold_policy_sha256", _sha("different-threshold")),
        ("evidence_inclusion_policy_sha256", _sha("different-inclusion")),
        ("runtime_environment_sha256", _sha("different-runtime")),
        ("execution_principal_id", "principal.accept.replacement"),
        ("compatibility_generation", "evaluation-generation-2"),
        ("parent_critic_sha256", _sha("parent-critic")),
    ],
)
def test_every_acceptance_relevant_spec_change_creates_a_new_identity(
    field_name: str,
    changed_value: str,
) -> None:
    original = _plan().acceptance_critic
    payload = original.model_dump(mode="json", exclude={"content_sha256"})
    payload[field_name] = changed_value

    changed = CriticSpec.model_validate(payload)

    assert changed.content_sha256 != original.content_sha256


def test_retired_acceptance_manifest_reveal_verifies_every_escrow_component() -> None:
    commitment, salt, cases, scoring = _commitment()
    acceptance = _critic(
        CriticRole.ACCEPTANCE,
        case_label="acceptance-cases",
        principal="principal.accept",
        commitment=commitment,
        case_manifest_sha256=canonical_content_sha256(cases),
        rubric_policy_sha256=canonical_content_sha256(scoring),
    )
    reveal = AcceptanceManifestReveal.create(
        critic_spec=acceptance,
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
        retirement_authority_event_sha256=_sha("human-retirement-event"),
        evaluation_outcome_sha256s=(_sha("outcome-2"), _sha("outcome-1")),
        promotion_sha256s=(_sha("promotion-1"),),
    )

    assert reveal.commitment_sha256 == commitment.content_sha256
    assert reveal.evaluation_outcome_sha256s == tuple(sorted((_sha("outcome-1"), _sha("outcome-2"))))

    with pytest.raises(ValidationError, match="salted commitment"):
        AcceptanceManifestReveal.create(
            critic_spec=acceptance,
            case_manifest=cases,
            scoring_policy=scoring,
            salt="wrong-salt",
            retirement_authority_event_sha256=_sha("human-retirement-event"),
        )

    with pytest.raises(ValidationError, match="case manifest"):
        AcceptanceManifestReveal.create(
            critic_spec=acceptance,
            case_manifest={
                "case_ids": ["different-hidden-case"],
                "split": "acceptance",
            },
            scoring_policy=scoring,
            salt=salt,
            retirement_authority_event_sha256=_sha("human-retirement-event"),
        )

    with pytest.raises(ValidationError, match="scoring policy"):
        AcceptanceManifestReveal.create(
            critic_spec=acceptance,
            case_manifest=cases,
            scoring_policy={
                "threshold": 0.1,
                "denominator": "changed",
            },
            salt=salt,
            retirement_authority_event_sha256=_sha("human-retirement-event"),
        )


def test_evaluation_plan_and_budget_partitions_are_content_addressed() -> None:
    plan = _plan()
    rebuilt = EvaluationPlan.model_validate(plan.model_dump(mode="json"))

    assert rebuilt == plan
    assert rebuilt.budgets.acceptance.case_count == 8
    assert rebuilt.content_sha256


def test_evaluation_authority_scope_binds_replayable_role_specific_critic_releases() -> None:
    plan = _plan()
    releases = tuple(
        CriticReleaseAuthorityRef(
            critic=critic.ref,
            authority_event_id=f"authority.release.{critic.role.value}",
            authority_event_sha256=_sha(f"authority:{critic.role.value}"),
        )
        for critic in (
            plan.acceptance_critic,
            plan.development_critic,
            plan.red_team_critic,
        )
        if critic is not None
    )

    scope = EvaluationPlanAuthorityScope(
        scope_id="evaluation-authority.stage-9",
        evaluation_plan_ref=plan.ref,
        critic_releases=releases,
    )

    assert tuple(item.critic.role for item in scope.critic_releases) == (
        CriticRole.ACCEPTANCE,
        CriticRole.DEVELOPMENT,
        CriticRole.RED_TEAM,
    )
    assert EvaluationPlanAuthorityScope.model_validate(scope.model_dump(mode="json")) == scope

    duplicate_role = tuple(
        (
            releases[0].model_copy(
                update={
                    "authority_event_id": "authority.release.acceptance-duplicate",
                    "authority_event_sha256": _sha("authority:acceptance-duplicate"),
                }
            )
            if item.critic.role is CriticRole.DEVELOPMENT
            else item
        )
        for item in releases
    )
    with pytest.raises(ValidationError, match="critic roles must be unique"):
        EvaluationPlanAuthorityScope(
            scope_id=scope.scope_id,
            evaluation_plan_ref=plan.ref,
            critic_releases=duplicate_role,
        )

    duplicate_event = tuple(
        (
            item.model_copy(
                update={
                    "authority_event_id": releases[0].authority_event_id,
                    "authority_event_sha256": releases[0].authority_event_sha256,
                }
            )
            if item.critic.role is CriticRole.DEVELOPMENT
            else item
        )
        for item in releases
    )
    with pytest.raises(ValidationError, match="authority events must be unique"):
        EvaluationPlanAuthorityScope(
            scope_id=scope.scope_id,
            evaluation_plan_ref=plan.ref,
            critic_releases=duplicate_event,
        )

    without_development = tuple(item for item in releases if item.critic.role is not CriticRole.DEVELOPMENT)
    with pytest.raises(
        ValidationError,
        match="development and acceptance critic releases",
    ):
        EvaluationPlanAuthorityScope(
            scope_id=scope.scope_id,
            evaluation_plan_ref=plan.ref,
            critic_releases=without_development,
        )


def test_task_verifier_surface_canonically_binds_only_verifier_file_inventory() -> None:
    surface = TaskVerifierSurface(
        task_id="civil/drainage/alpha",
        task_revision=_sha("alpha-revision"),
        source_task_package_sha256=_sha("alpha-public-package"),
        sealed_task_package_sha256=_sha("alpha-sealed-package"),
        files=(
            TaskVerifierFileInventoryEntry(
                path="tests/secret.json",
                sha256=_sha("secret"),
                byte_size=12,
                role="sealed_verifier_only",
            ),
            TaskVerifierFileInventoryEntry(
                path="tests/test.sh",
                sha256=_sha("test-sh"),
                byte_size=24,
                role="verifier_only",
            ),
        ),
    )
    rebuilt = TaskVerifierSurface(
        task_id=surface.task_id,
        task_revision=surface.task_revision,
        source_task_package_sha256=surface.source_task_package_sha256,
        sealed_task_package_sha256=surface.sealed_task_package_sha256,
        files=tuple(reversed(surface.files)),
    )

    assert tuple(item.path for item in surface.files) == (
        "tests/secret.json",
        "tests/test.sh",
    )
    assert rebuilt == surface
    assert rebuilt.content_sha256 == surface.content_sha256

    with pytest.raises(ValidationError, match="sealed verifier files"):
        TaskVerifierSurface(
            task_id="civil/drainage/no-sealed-binding",
            task_revision=_sha("revision"),
            source_task_package_sha256=_sha("public-package"),
            files=surface.files,
        )


def test_task_verifier_scope_is_order_independent_and_rejects_duplicate_tasks() -> None:
    surfaces = tuple(
        TaskVerifierSurface(
            task_id=task_id,
            task_revision=_sha(f"revision:{task_id}"),
            source_task_package_sha256=_sha(f"public:{task_id}"),
            files=(
                TaskVerifierFileInventoryEntry(
                    path="tests/test.sh",
                    sha256=_sha(f"test:{task_id}"),
                    byte_size=32,
                    role="verifier_only",
                ),
            ),
        )
        for task_id in ("civil/drainage/beta", "civil/drainage/alpha")
    )
    scope = TaskVerifierSurfaceScope(
        scope_id="verifiers.phase9.1a",
        task_surfaces=surfaces,
    )
    rebuilt = TaskVerifierSurfaceScope(
        scope_id=scope.scope_id,
        task_surfaces=tuple(reversed(surfaces)),
    )

    assert tuple(surface.task_id for surface in scope.task_surfaces) == (
        "civil/drainage/alpha",
        "civil/drainage/beta",
    )
    assert rebuilt == scope
    assert _plan(task_verifier_sha256=scope.content_sha256).task_verifier_sha256 == scope.content_sha256

    with pytest.raises(ValidationError, match="task identities must be unique"):
        TaskVerifierSurfaceScope(
            scope_id=scope.scope_id,
            task_surfaces=(scope.task_surfaces[0], scope.task_surfaces[0]),
        )


def test_public_refs_do_not_expose_hidden_manifest_or_execution_details() -> None:
    plan = _plan()
    acceptance = plan.acceptance_critic
    critic_payload = acceptance.ref.model_dump(mode="json")
    plan_payload = plan.ref.model_dump(mode="json")
    public_commitment = acceptance.acceptance_manifest_commitment
    assert public_commitment is not None
    public_commitment_payload = public_commitment.model_dump(mode="json")

    assert CriticSpec.model_validate(acceptance.model_dump(mode="json")) == acceptance
    assert EvaluationPlanRef.model_validate(plan_payload) == plan.ref
    assert acceptance.case_manifest_sha256 not in str(critic_payload)
    assert acceptance.rubric_policy_sha256 not in str(critic_payload)
    assert acceptance.execution_principal_id not in str(critic_payload)
    assert acceptance.case_manifest_sha256 not in str(plan_payload)
    assert "case_manifest_sha256" not in public_commitment_payload
    assert "scoring_policy_sha256" not in public_commitment_payload
