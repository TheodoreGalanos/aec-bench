# ABOUTME: Tests the single evaluation-regime identity and separate assignment commitments.
# ABOUTME: Proves critic configuration is embedded while hidden acceptance content stays committed.

from __future__ import annotations

import pytest
from pydantic import JsonValue, ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment,
    AcceptanceManifestReveal,
    AcceptancePolicy,
    ArtifactCriticSource,
    CandidateManifestScope,
    Critic,
    CriticFeedbackVisibility,
    CriticReleaseAuthorityRef,
    EvaluationAssignment,
    EvaluationRegime,
    EvaluationRegimeAuthorityScope,
    RepositoryCriticSource,
    TaskVerifierFileInventoryEntry,
    TaskVerifierSurface,
    TaskVerifierSurfaceScope,
    assert_evaluation_regimes_compatible,
    candidate_manifest_scope_commitment,
    task_verifier_surface_commitment,
)
from aec_bench.contracts.evaluation_refs import CriticRole
from aec_bench.contracts.harness_kernel import KernelRef
from tests.support.evaluation_regimes import fake_regime_ref, make_regime, sha


def test_regime_embeds_policies_without_nested_versions_or_component_hash_matrix() -> None:
    regime = make_regime()
    payload = regime.model_dump(mode="json")

    assert EvaluationRegime.model_validate(payload) == regime
    assert "schema_version" not in str(payload)
    assert "compatibility_generation" not in str(payload)
    assert "critic_version" not in str(payload)
    assert "implementation_sha256" not in str(payload)
    assert "policy_sha256" not in str(payload)
    assert payload["acceptance_policy"]["configuration"] == {"threshold": 0.8}


@pytest.mark.parametrize(
    "field",
    ("schema_version", "content_sha256", "implementation_sha256", "published_at", "local_path"),
)
def test_regime_policy_rejects_nested_identity_and_diagnostic_metadata(field: str) -> None:
    with pytest.raises(ValidationError, match="nonsemantic identity or metadata"):
        AcceptancePolicy(policy_id="acceptance", configuration={"nested": {field: "not-semantic"}})


def test_critic_has_one_stable_id_and_embedded_configuration() -> None:
    critic = make_regime().critic(CriticRole.DEVELOPMENT)

    assert critic.critic_id == "critic.development"
    assert critic.configuration == {"rubric": "shared", "cases": ["public-01"]}
    assert isinstance(critic.source, RepositoryCriticSource)
    assert critic.source.source_revision == "1" * 40
    assert set(critic.model_dump()) == {
        "critic_id",
        "role",
        "source",
        "configuration",
        "feedback_visibility",
        "execution_principal_id",
        "acceptance_manifest_commitment",
    }


def test_repository_critic_source_requires_an_exact_git_revision() -> None:
    with pytest.raises(ValidationError, match="40-character Git commit"):
        RepositoryCriticSource(source_revision="main", entrypoint="aec_bench.evaluation.rubric_scorer")


def test_external_critic_source_uses_one_artifact_reference() -> None:
    artifact = ArtifactRef(
        artifact_id=f"artifacts/sha256/{'a' * 2}/{'a' * 64}",
        sha256="a" * 64,
        size_bytes=100,
        media_type="application/vnd.aec-bench.critic+python",
    )
    source = ArtifactCriticSource(artifact=artifact)

    assert source.model_dump() == {"kind": "artifact", "artifact": artifact.model_dump()}


def test_acceptance_critic_requires_a_matching_salted_commitment() -> None:
    with pytest.raises(ValidationError, match="acceptance critic requires"):
        Critic(
            critic_id="critic.acceptance",
            role=CriticRole.ACCEPTANCE,
            source=RepositoryCriticSource(
                source_revision="1" * 40,
                entrypoint="aec_bench.evaluation.rubric_scorer",
            ),
            feedback_visibility=CriticFeedbackVisibility.HOST_ONLY,
            execution_principal_id="principal.acceptance",
        )

    wrong = AcceptanceManifestCommitment.create(
        critic_id="critic.other",
        case_manifest={"case_ids": ["hidden"]},
        scoring_policy={"threshold": 1.0},
        salt="random-salt",
    )
    with pytest.raises(ValidationError, match="identities must match"):
        Critic(
            critic_id="critic.acceptance",
            role=CriticRole.ACCEPTANCE,
            source=RepositoryCriticSource(
                source_revision="1" * 40,
                entrypoint="aec_bench.evaluation.rubric_scorer",
            ),
            feedback_visibility=CriticFeedbackVisibility.HOST_ONLY,
            execution_principal_id="principal.acceptance",
            acceptance_manifest_commitment=wrong,
        )


def test_acceptance_commitment_can_generate_a_host_only_random_salt() -> None:
    commitment, salt = AcceptanceManifestCommitment.create_with_random_salt(
        critic_id="critic.acceptance",
        case_manifest={"case_ids": ["hidden"]},
        scoring_policy={"threshold": 1.0},
    )

    assert len(salt) == 64
    assert salt not in commitment.model_dump_json()
    assert commitment == AcceptanceManifestCommitment.create(
        critic_id="critic.acceptance",
        case_manifest={"case_ids": ["hidden"]},
        scoring_policy={"threshold": 1.0},
        salt=salt,
    )


def test_acceptance_critic_rejects_hidden_case_or_scoring_configuration() -> None:
    commitment = AcceptanceManifestCommitment.create(
        critic_id="critic.acceptance",
        case_manifest={"case_ids": ["hidden"]},
        scoring_policy={"threshold": 1.0},
        salt="random-salt",
    )
    with pytest.raises(ValidationError, match=r"hidden material at configuration\.case_manifest"):
        Critic(
            critic_id="critic.acceptance",
            role=CriticRole.ACCEPTANCE,
            source=RepositoryCriticSource(
                source_revision="1" * 40,
                entrypoint="aec_bench.evaluation.rubric_scorer",
            ),
            configuration={"case_manifest": {"case_ids": ["hidden"]}},
            feedback_visibility=CriticFeedbackVisibility.HOST_ONLY,
            execution_principal_id="principal.acceptance",
            acceptance_manifest_commitment=commitment,
        )


def test_hidden_acceptance_content_is_absent_from_public_regime_and_reveal_verifies_it() -> None:
    cases: JsonValue = {"case_ids": ["hidden-01", "hidden-02"], "split": "acceptance"}
    scoring: JsonValue = {"threshold": 0.8, "denominator": "all_planned_cases"}
    salt = "retirement-escrow-salt"
    commitment = AcceptanceManifestCommitment.create(
        critic_id="critic.acceptance",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    base = make_regime()
    acceptance = base.critic(CriticRole.ACCEPTANCE).model_copy(update={"acceptance_manifest_commitment": commitment})
    regime = base.model_copy(
        update={
            "critics": tuple(acceptance if critic.role is CriticRole.ACCEPTANCE else critic for critic in base.critics)
        }
    )
    regime_ref = fake_regime_ref(regime_id=regime.regime_id)

    assert "hidden-01" not in str(regime.model_dump(mode="json"))
    reveal = AcceptanceManifestReveal.create(
        evaluation_regime=regime_ref,
        critic=acceptance,
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
        retirement_authority_event_sha256=sha("retirement"),
    )
    assert reveal.case_manifest == cases

    with pytest.raises(ValidationError, match="salted commitment"):
        AcceptanceManifestReveal.create(
            evaluation_regime=regime_ref,
            critic=acceptance,
            case_manifest=cases,
            scoring_policy=scoring,
            salt="wrong-salt",
            retirement_authority_event_sha256=sha("retirement"),
        )


def test_one_artifact_digest_determines_compatibility_across_store_ids() -> None:
    left = fake_regime_ref(label="same")
    right = left.model_copy(
        update={"artifact": left.artifact.model_copy(update={"artifact_id": f"mirror/{left.artifact.sha256}"})}
    )
    assert_evaluation_regimes_compatible(left, right)

    with pytest.raises(ValueError, match="artifacts do not match"):
        assert_evaluation_regimes_compatible(left, fake_regime_ref(label="changed"))


def test_candidate_and_split_bindings_are_outside_the_public_regime() -> None:
    regime = make_regime()
    ref = fake_regime_ref(regime_id=regime.regime_id)
    assignment = EvaluationAssignment(
        assignment_id="assignment.acceptance-01",
        regime=ref,
        kernel_ref=KernelRef(kernel_id="kernel.fixed", version="1"),
        harness_policy_commitment=sha("harness"),
        candidate_manifest_commitment=sha("candidate"),
        task_manifest_commitment=sha("task"),
        split_manifest_commitment=sha("split"),
        task_verifier_commitment=sha("verifier"),
    )

    assert assignment.regime == ref
    assert "candidate_manifest_commitment" not in regime.model_dump(mode="json")
    assert "split_manifest_commitment" not in regime.model_dump(mode="json")


def test_regime_authority_scope_binds_critic_releases_to_one_exact_regime() -> None:
    regime = make_regime()
    ref = fake_regime_ref(regime_id=regime.regime_id)
    releases = tuple(
        CriticReleaseAuthorityRef(
            critic=critic.ref(ref),
            authority_event_id=f"authority.release.{critic.role.value}",
            authority_event_sha256=sha(f"authority:{critic.role.value}"),
        )
        for critic in regime.critics
    )
    scope = EvaluationRegimeAuthorityScope(
        scope_id="evaluation-authority.standard",
        regime=ref,
        critic_releases=releases,
    )

    assert tuple(item.critic.role for item in scope.critic_releases) == (
        CriticRole.DEVELOPMENT,
        CriticRole.ACCEPTANCE,
    )
    wrong_ref = fake_regime_ref(label="other", regime_id=regime.regime_id)
    with pytest.raises(ValidationError, match="different evaluation regime"):
        EvaluationRegimeAuthorityScope(
            scope_id=scope.scope_id,
            regime=ref,
            critic_releases=(
                releases[0].model_copy(update={"critic": releases[0].critic.model_copy(update={"regime": wrong_ref})}),
                releases[1],
            ),
        )


def test_assignment_commitment_helpers_are_canonical() -> None:
    candidate_scope = CandidateManifestScope(
        scope_id="candidate-scope",
        candidate_manifest_sha256s=(sha("candidate-b"), sha("candidate-a")),
    )
    assert candidate_scope.candidate_manifest_sha256s == tuple(sorted(candidate_scope.candidate_manifest_sha256s))
    assert candidate_manifest_scope_commitment(candidate_scope) == candidate_manifest_scope_commitment(
        CandidateManifestScope(
            scope_id="candidate-scope",
            candidate_manifest_sha256s=tuple(reversed(candidate_scope.candidate_manifest_sha256s)),
        )
    )

    surface = TaskVerifierSurface(
        task_id="civil/drainage/alpha",
        task_revision=sha("revision"),
        source_task_package_sha256=sha("public-package"),
        files=(
            TaskVerifierFileInventoryEntry(
                path="tests/test.sh",
                sha256=sha("test"),
                byte_size=24,
                role="verifier_only",
            ),
        ),
    )
    verifier_scope = TaskVerifierSurfaceScope(scope_id="verifiers", task_surfaces=(surface,))
    assert task_verifier_surface_commitment(verifier_scope) == task_verifier_surface_commitment(verifier_scope)
