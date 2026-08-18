# ABOUTME: Verifies fail-closed migration from legacy component matrices to one regime artifact.
# ABOUTME: Confirms resolved semantics publish once while missing or corrupt components stay read-only.

from __future__ import annotations

from pathlib import Path

from pydantic import JsonValue

from aec_bench.contracts.evaluation_plane import AcceptanceManifestReveal, CriticFeedbackVisibility
from aec_bench.contracts.evaluation_refs import CriticRole
from aec_bench.contracts.harness_kernel import KernelRef, canonical_json_sha256
from aec_bench.evaluation.legacy_regime import (
    AcceptanceManifestCommitment,
    CriticSpec,
    EvaluationBudgetPlan,
    EvaluationPlan,
    LegacyEvaluationBudgetPartition,
    migrate_legacy_evaluation_plan,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository

_ACCEPTANCE_CASE_MANIFEST: JsonValue = {"hidden_case": "acceptance"}
_ACCEPTANCE_SCORING_POLICY: JsonValue = {"rubric": "acceptance"}
_CONFIRMATORY_SUITE: JsonValue = {"hidden_suite": "confirmatory"}
_CHALLENGE_SUITE: JsonValue = {"hidden_suite": "challenge"}
_ACCEPTANCE_SALT = "legacy-random-acceptance-salt"


def _component(value: JsonValue, components: dict[str, JsonValue]) -> str:
    digest = canonical_json_sha256(value)
    components[digest] = value
    return digest


def _legacy_plan() -> tuple[EvaluationPlan, dict[str, JsonValue]]:
    components: dict[str, JsonValue] = {}

    def critic(role: CriticRole) -> CriticSpec:
        critic_id = f"critic.{role.value}"
        case_manifest: JsonValue = (
            _ACCEPTANCE_CASE_MANIFEST if role is CriticRole.ACCEPTANCE else {"case_group": role.value}
        )
        scoring_policy: JsonValue = (
            _ACCEPTANCE_SCORING_POLICY if role is CriticRole.ACCEPTANCE else {"rubric": role.value}
        )
        return CriticSpec(
            critic_id=critic_id,
            version="7",
            role=role,
            implementation_sha256=_component(
                {
                    "kind": "repository",
                    "source_revision": "1" * 40,
                    "entrypoint": f"critics.{role.value}:run",
                },
                components,
            ),
            rubric_policy_sha256=_component(scoring_policy, components),
            case_manifest_sha256=_component(case_manifest, components),
            eligibility_policy_sha256=_component({"eligible": True, "role": role.value}, components),
            denominator_policy_sha256=_component({"population": role.value}, components),
            threshold_policy_sha256=_component({"minimum": 0.8, "role": role.value}, components),
            evidence_inclusion_policy_sha256=_component({"include": [role.value]}, components),
            runtime_environment_sha256=_component({"runtime": role.value}, components),
            feedback_visibility=(
                CriticFeedbackVisibility.VISIBLE
                if role is CriticRole.DEVELOPMENT
                else CriticFeedbackVisibility.HOST_ONLY
            ),
            execution_principal_id=f"principal.{role.value}",
            compatibility_generation="generation-7",
            acceptance_manifest_commitment=(
                None
                if role is not CriticRole.ACCEPTANCE
                else AcceptanceManifestCommitment(
                    critic_id=critic_id,
                    critic_version="7",
                    salted_commitment_sha256=canonical_json_sha256(
                        {
                            "domain": "aecbench.acceptance-manifest-commitment.v1",
                            "salt": _ACCEPTANCE_SALT,
                            "case_manifest": case_manifest,
                            "scoring_policy": scoring_policy,
                        }
                    ),
                    publication_receipt_sha256=_component({"escrow_receipt": critic_id}, components),
                )
            ),
        )

    partition = LegacyEvaluationBudgetPartition(
        case_count=1,
        max_attempts=1,
        max_turns=2,
        max_tokens=100,
        max_cost_usd=1.0,
        max_wall_time_seconds=10.0,
    )
    plan = EvaluationPlan(
        plan_id="regime.migrated",
        evaluation_generation="generation-7",
        kernel_ref=KernelRef(kernel_id="kernel", version="1"),
        harness_policy_sha256=_component({"harness": "fixed"}, components),
        candidate_manifest_sha256=_component({"candidates": ["candidate-a"]}, components),
        task_manifest_sha256=_component({"tasks": ["task-a"]}, components),
        split_manifest_sha256=_component({"split": "holdout"}, components),
        task_verifier_sha256=_component({"verifier": "task-owned"}, components),
        development_critic=critic(CriticRole.DEVELOPMENT),
        acceptance_critic=critic(CriticRole.ACCEPTANCE),
        budgets=EvaluationBudgetPlan(
            proposal=partition,
            execution=partition,
            development=partition,
            acceptance=partition,
            red_team=partition,
            monitor=partition,
            audit=partition,
        ),
        integrity_policy_sha256=_component({"integrity": "strict"}, components),
        utility_policy_sha256=_component({"utility": "normalized"}, components),
        selection_null_protocol_sha256=_component({"denominator": "matched"}, components),
        anchor_calibration_policy_sha256=_component(
            {"cadence": "every_critic_release", "critic_roles": ["acceptance"]},
            components,
        ),
        monitor_plan_sha256=_component({"monitor_id": "standing"}, components),
        opening_policy_sha256=_component({"opening": "closed"}, components),
        stopping_policy_sha256=_component({"stop": "budget"}, components),
        confirmatory_suite_sha256=_component(_CONFIRMATORY_SUITE, components),
        challenge_suite_sha256=_component(_CHALLENGE_SUITE, components),
    )
    return plan, components


def test_fully_resolved_legacy_plan_publishes_one_regime(tmp_path: Path) -> None:
    plan, components = _legacy_plan()

    result = migrate_legacy_evaluation_plan(
        plan=plan,
        resolver=components,
        repository=ArtifactRepository(tmp_path),
    )

    assert not result.read_only
    assert result.evaluation_regime_ref is not None
    assert result.evaluation_assignment is not None
    assert result.evaluation_assignment.regime == result.evaluation_regime_ref
    assert result.unresolved_components == ()
    assert result.evaluation_regime is not None
    acceptance = result.evaluation_regime.critic(CriticRole.ACCEPTANCE)
    assert "cases" not in acceptance.configuration
    assert "rubric" not in acceptance.configuration
    assert "hidden_case" not in result.evaluation_regime.model_dump_json()
    assert "hidden_suite" not in result.evaluation_regime.model_dump_json()
    AcceptanceManifestReveal.create(
        evaluation_regime=result.evaluation_regime_ref,
        critic=acceptance,
        case_manifest=_ACCEPTANCE_CASE_MANIFEST,
        scoring_policy=_ACCEPTANCE_SCORING_POLICY,
        salt=_ACCEPTANCE_SALT,
        retirement_authority_event_sha256="c" * 64,
    )


def test_missing_legacy_component_stays_read_only(tmp_path: Path) -> None:
    plan, components = _legacy_plan()
    components.pop(plan.monitor_plan_sha256)

    result = migrate_legacy_evaluation_plan(
        plan=plan,
        resolver=components,
        repository=ArtifactRepository(tmp_path),
    )

    assert result.read_only
    assert result.evaluation_regime_ref is None
    assert result.unresolved_components == (plan.monitor_plan_sha256,)


def test_missing_acceptance_escrow_receipt_stays_read_only(tmp_path: Path) -> None:
    plan, components = _legacy_plan()
    commitment = plan.acceptance_critic.acceptance_manifest_commitment
    assert commitment is not None
    components.pop(commitment.publication_receipt_sha256)

    result = migrate_legacy_evaluation_plan(
        plan=plan,
        resolver=components,
        repository=ArtifactRepository(tmp_path),
    )

    assert result.read_only
    assert result.evaluation_regime_ref is None
    assert result.unresolved_components == (commitment.publication_receipt_sha256,)


def test_hash_mismatched_legacy_component_stays_read_only(tmp_path: Path) -> None:
    plan, components = _legacy_plan()
    components[plan.stopping_policy_sha256] = {"stop": "changed"}

    result = migrate_legacy_evaluation_plan(
        plan=plan,
        resolver=components,
        repository=ArtifactRepository(tmp_path),
    )

    assert result.read_only
    assert result.evaluation_regime_ref is None
    assert result.unresolved_components == (plan.stopping_policy_sha256,)


def test_legacy_repository_critic_without_exact_source_stays_read_only(tmp_path: Path) -> None:
    plan, components = _legacy_plan()
    unresolved_source_sha256 = _component({"entrypoint": "critics.development:run"}, components)
    development = plan.development_critic.model_copy(update={"implementation_sha256": unresolved_source_sha256})
    plan = plan.model_copy(update={"development_critic": development})

    result = migrate_legacy_evaluation_plan(
        plan=plan,
        resolver=components,
        repository=ArtifactRepository(tmp_path),
    )

    assert result.read_only
    assert result.evaluation_regime_ref is None
    assert result.unresolved_components == (unresolved_source_sha256,)


def test_legacy_policy_with_nested_schema_identity_stays_read_only(tmp_path: Path) -> None:
    plan, components = _legacy_plan()
    invalid_policy_sha256 = _component(
        {"schema_version": "legacy.policy.v1", "stop": "budget"},
        components,
    )
    plan = plan.model_copy(update={"stopping_policy_sha256": invalid_policy_sha256})

    result = migrate_legacy_evaluation_plan(
        plan=plan,
        resolver=components,
        repository=ArtifactRepository(tmp_path),
    )

    assert result.read_only
    assert result.evaluation_regime_ref is None
    assert invalid_policy_sha256 in result.unresolved_components
