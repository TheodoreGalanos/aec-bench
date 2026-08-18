# ABOUTME: Migrates fully resolvable legacy evaluation plans into one published regime artifact.
# ABOUTME: Leaves plans read-only when any outcome-affecting component is missing or corrupt.

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import Field, FiniteFloat, JsonValue, NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment as CurrentAcceptanceManifestCommitment,
)
from aec_bench.contracts.evaluation_plane import (
    AcceptancePolicy,
    ArtifactCriticSource,
    CalibrationPolicy,
    Critic,
    CriticFeedbackVisibility,
    DenominatorPolicy,
    EligibilityPolicy,
    EvaluationAssignment,
    EvaluationBudget,
    EvaluationRegime,
    EvidencePolicy,
    MonitoringPolicy,
    RepositoryCriticSource,
    StoppingPolicy,
)
from aec_bench.contracts.evaluation_refs import CriticRole, EvaluationRegimeRef
from aec_bench.contracts.harness_kernel import FrozenStrictModel, KernelRef, canonical_json_sha256, validate_sha256
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.evaluation.regime import publish_evaluation_regime
from aec_bench.ledger.artifact_repository import ArtifactRepository

type LegacyComponentResolver = Callable[[str], JsonValue | None] | Mapping[str, JsonValue]
type MigratedCriticSource = RepositoryCriticSource | ArtifactCriticSource


class AcceptanceManifestCommitment(FrozenStrictModel):
    """Complete hidden-content commitment from the legacy plan shape."""

    schema_version: Literal["aecbench.acceptance-manifest-commitment.v1"] = "aecbench.acceptance-manifest-commitment.v1"
    critic_id: NonEmptyStr
    critic_version: NonEmptyStr
    salted_commitment_sha256: str
    publication_receipt_sha256: str
    reveal_rule: Literal["on_generation_retirement"] = "on_generation_retirement"

    @field_validator("salted_commitment_sha256", "publication_receipt_sha256")
    @classmethod
    def validate_commitment(cls, value: str) -> str:
        return validate_sha256(value)


class CriticSpec(FrozenStrictModel):
    """Legacy critic hash matrix accepted only by the migration boundary."""

    schema_version: Literal["aecbench.critic-spec.v1"] = "aecbench.critic-spec.v1"
    critic_id: NonEmptyStr
    version: NonEmptyStr
    role: CriticRole
    implementation_sha256: str
    rubric_policy_sha256: str
    case_manifest_sha256: str
    eligibility_policy_sha256: str
    denominator_policy_sha256: str
    threshold_policy_sha256: str
    evidence_inclusion_policy_sha256: str
    runtime_environment_sha256: str
    feedback_visibility: CriticFeedbackVisibility
    execution_principal_id: NonEmptyStr
    compatibility_generation: NonEmptyStr
    parent_critic_ref: JsonValue = None
    acceptance_manifest_commitment: AcceptanceManifestCommitment | None = None

    @field_validator(
        "implementation_sha256",
        "rubric_policy_sha256",
        "case_manifest_sha256",
        "eligibility_policy_sha256",
        "denominator_policy_sha256",
        "threshold_policy_sha256",
        "evidence_inclusion_policy_sha256",
        "runtime_environment_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_role_contract(self) -> Self:
        if self.role is CriticRole.ACCEPTANCE:
            if self.acceptance_manifest_commitment is None:
                raise ValueError("legacy acceptance critic requires an acceptance manifest commitment")
            if self.feedback_visibility is not CriticFeedbackVisibility.HOST_ONLY:
                raise ValueError("legacy acceptance critic feedback must remain host-only")
            if self.acceptance_manifest_commitment.critic_id != self.critic_id:
                raise ValueError("legacy critic and manifest commitment identities must match")
        elif self.acceptance_manifest_commitment is not None:
            raise ValueError("only legacy acceptance critics may carry a manifest commitment")
        if self.role is CriticRole.DEVELOPMENT and self.feedback_visibility is not CriticFeedbackVisibility.VISIBLE:
            raise ValueError("legacy development critic feedback must be visible")
        return self


class LegacyEvaluationBudgetPartition(FrozenStrictModel):
    """Legacy budget partition with the same semantic values as the regime partition."""

    case_count: NonNegativeInt
    max_attempts: NonNegativeInt
    max_turns: NonNegativeInt
    max_tokens: NonNegativeInt
    max_cost_usd: FiniteFloat = Field(ge=0)
    max_wall_time_seconds: FiniteFloat = Field(ge=0)


class EvaluationBudgetPlan(FrozenStrictModel):
    """Legacy collection of evaluation budget partitions."""

    schema_version: Literal["aecbench.evaluation-budget-plan.v1"] = "aecbench.evaluation-budget-plan.v1"
    proposal: LegacyEvaluationBudgetPartition
    execution: LegacyEvaluationBudgetPartition
    development: LegacyEvaluationBudgetPartition
    acceptance: LegacyEvaluationBudgetPartition
    red_team: LegacyEvaluationBudgetPartition
    monitor: LegacyEvaluationBudgetPartition
    audit: LegacyEvaluationBudgetPartition


class EvaluationPlan(FrozenStrictModel):
    """Read-only input contract for the superseded evaluation-plan format."""

    schema_version: Literal["aecbench.evaluation-plan.v1"] = "aecbench.evaluation-plan.v1"
    plan_id: NonEmptyStr
    evaluation_generation: NonEmptyStr
    kernel_ref: KernelRef
    harness_policy_sha256: str
    candidate_manifest_sha256: str
    task_manifest_sha256: str
    split_manifest_sha256: str
    task_verifier_sha256: str
    development_critic: CriticSpec
    acceptance_critic: CriticSpec
    red_team_critic: CriticSpec | None = None
    budgets: EvaluationBudgetPlan
    integrity_policy_sha256: str
    utility_policy_sha256: str
    selection_null_protocol_sha256: str
    anchor_calibration_policy_sha256: str
    monitor_plan_sha256: str
    opening_policy_sha256: str
    stopping_policy_sha256: str
    confirmatory_suite_sha256: str
    challenge_suite_sha256: str

    @field_validator(
        "harness_policy_sha256",
        "candidate_manifest_sha256",
        "task_manifest_sha256",
        "split_manifest_sha256",
        "task_verifier_sha256",
        "integrity_policy_sha256",
        "utility_policy_sha256",
        "selection_null_protocol_sha256",
        "anchor_calibration_policy_sha256",
        "monitor_plan_sha256",
        "opening_policy_sha256",
        "stopping_policy_sha256",
        "confirmatory_suite_sha256",
        "challenge_suite_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_critic_bindings(self) -> Self:
        if self.development_critic.role is not CriticRole.DEVELOPMENT:
            raise ValueError("legacy development critic must have the development role")
        if self.acceptance_critic.role is not CriticRole.ACCEPTANCE:
            raise ValueError("legacy acceptance critic must have the acceptance role")
        if self.red_team_critic is not None and self.red_team_critic.role is not CriticRole.RED_TEAM:
            raise ValueError("legacy red-team critic must have the red-team role")
        if any(critic.compatibility_generation != self.evaluation_generation for critic in _legacy_critics(self)):
            raise ValueError("legacy critics must bind the plan compatibility generation")
        return self


@dataclass(frozen=True)
class LegacyRegimeMigration:
    """Migration result that is publishable only when all components resolve."""

    evaluation_regime: EvaluationRegime | None
    evaluation_regime_ref: EvaluationRegimeRef | None
    evaluation_assignment: EvaluationAssignment | None
    unresolved_components: tuple[str, ...]
    read_only: bool


def migrate_legacy_evaluation_plan(
    *,
    plan: EvaluationPlan,
    resolver: LegacyComponentResolver,
    repository: ArtifactRepository,
) -> LegacyRegimeMigration:
    """Resolve, verify, reconstruct, and publish one legacy evaluation plan."""

    selected = EvaluationPlan.model_validate(plan.model_dump(mode="python"))
    resolved: dict[str, JsonValue] = {}
    unresolved: list[str] = []
    for digest in _component_digests(selected):
        value = resolver.get(digest) if isinstance(resolver, Mapping) else resolver(digest)
        if value is None or canonical_json_sha256(value) != digest:
            unresolved.append(digest)
        else:
            resolved[digest] = value
    unresolved.extend(
        critic.implementation_sha256
        for critic in _legacy_critics(selected)
        if critic.implementation_sha256 in resolved
        and _legacy_critic_source(resolved[critic.implementation_sha256]) is None
    )
    if unresolved:
        return LegacyRegimeMigration(
            evaluation_regime=None,
            evaluation_regime_ref=None,
            evaluation_assignment=None,
            unresolved_components=tuple(sorted(set(unresolved))),
            read_only=True,
        )

    try:
        regime = _build_regime(selected, resolved)
    except ValueError:
        return LegacyRegimeMigration(
            evaluation_regime=None,
            evaluation_regime_ref=None,
            evaluation_assignment=None,
            unresolved_components=tuple(sorted(set(_component_digests(selected)))),
            read_only=True,
        )
    regime_ref = publish_evaluation_regime(repository, regime)
    assignment = EvaluationAssignment(
        assignment_id=f"{selected.plan_id}.assignment",
        regime=regime_ref,
        kernel_ref=selected.kernel_ref,
        harness_policy_commitment=selected.harness_policy_sha256,
        candidate_manifest_commitment=selected.candidate_manifest_sha256,
        task_manifest_commitment=selected.task_manifest_sha256,
        split_manifest_commitment=selected.split_manifest_sha256,
        task_verifier_commitment=selected.task_verifier_sha256,
    )
    return LegacyRegimeMigration(
        evaluation_regime=regime,
        evaluation_regime_ref=regime_ref,
        evaluation_assignment=assignment,
        unresolved_components=(),
        read_only=False,
    )


def _component_digests(plan: EvaluationPlan) -> tuple[str, ...]:
    configured_critics = (plan.development_critic, plan.acceptance_critic, plan.red_team_critic)
    critics = tuple(critic for critic in configured_critics if critic is not None)
    critic_digests = tuple(
        digest
        for critic in critics
        for digest in (
            critic.implementation_sha256,
            critic.rubric_policy_sha256,
            critic.case_manifest_sha256,
            critic.eligibility_policy_sha256,
            critic.denominator_policy_sha256,
            critic.threshold_policy_sha256,
            critic.evidence_inclusion_policy_sha256,
            critic.runtime_environment_sha256,
        )
    )
    escrow_receipt_digests = tuple(
        critic.acceptance_manifest_commitment.publication_receipt_sha256
        for critic in critics
        if critic.acceptance_manifest_commitment is not None
    )
    plan_digests = (
        plan.harness_policy_sha256,
        plan.candidate_manifest_sha256,
        plan.task_manifest_sha256,
        plan.split_manifest_sha256,
        plan.task_verifier_sha256,
        plan.integrity_policy_sha256,
        plan.utility_policy_sha256,
        plan.selection_null_protocol_sha256,
        plan.anchor_calibration_policy_sha256,
        plan.monitor_plan_sha256,
        plan.opening_policy_sha256,
        plan.stopping_policy_sha256,
        plan.confirmatory_suite_sha256,
        plan.challenge_suite_sha256,
    )
    return tuple(dict.fromkeys((*critic_digests, *escrow_receipt_digests, *plan_digests)))


def _build_regime(plan: EvaluationPlan, resolved: Mapping[str, JsonValue]) -> EvaluationRegime:
    critics = tuple(_build_critic(critic, resolved) for critic in _legacy_critics(plan))
    return EvaluationRegime(
        regime_id=plan.plan_id,
        critics=critics,
        budget=EvaluationBudget.model_validate(plan.budgets.model_dump(mode="python", exclude={"schema_version"})),
        acceptance_policy=AcceptancePolicy(
            policy_id="acceptance",
            configuration={"utility": resolved[plan.utility_policy_sha256]},
        ),
        eligibility_policy=EligibilityPolicy(
            policy_id="eligibility",
            configuration={
                "integrity": resolved[plan.integrity_policy_sha256],
                "opening": resolved[plan.opening_policy_sha256],
            },
        ),
        denominator_policy=DenominatorPolicy(
            policy_id="denominator",
            configuration={"selection_null": resolved[plan.selection_null_protocol_sha256]},
        ),
        evidence_policy=EvidencePolicy(
            policy_id="evidence",
            configuration={"authority": "task_owned"},
        ),
        calibration_policy=CalibrationPolicy(
            policy_id="calibration",
            configuration={"executable_anchor": resolved[plan.anchor_calibration_policy_sha256]},
        ),
        stopping_policy=StoppingPolicy(
            policy_id="stopping",
            configuration={"rules": resolved[plan.stopping_policy_sha256]},
        ),
        monitoring_policy=MonitoringPolicy(
            policy_id="monitoring",
            configuration={"standing_policy": resolved[plan.monitor_plan_sha256]},
        ),
    )


def _legacy_critics(plan: EvaluationPlan) -> tuple[CriticSpec, ...]:
    configured_critics = (plan.development_critic, plan.acceptance_critic, plan.red_team_critic)
    return tuple(critic for critic in configured_critics if critic is not None)


def _build_critic(critic: CriticSpec, resolved: Mapping[str, JsonValue]) -> Critic:
    source = _legacy_critic_source(resolved[critic.implementation_sha256])
    if source is None:
        raise AssertionError("validated legacy critic source became unresolved")
    commitment = critic.acceptance_manifest_commitment
    return Critic(
        critic_id=critic.critic_id,
        role=critic.role,
        source=source,
        configuration={
            **(
                {}
                if critic.role is CriticRole.ACCEPTANCE
                else {
                    "rubric": resolved[critic.rubric_policy_sha256],
                    "cases": resolved[critic.case_manifest_sha256],
                }
            ),
            "eligibility": resolved[critic.eligibility_policy_sha256],
            "denominator": resolved[critic.denominator_policy_sha256],
            "threshold": resolved[critic.threshold_policy_sha256],
            "evidence": resolved[critic.evidence_inclusion_policy_sha256],
            "runtime": resolved[critic.runtime_environment_sha256],
        },
        feedback_visibility=critic.feedback_visibility,
        execution_principal_id=critic.execution_principal_id,
        acceptance_manifest_commitment=(
            None
            if commitment is None
            else CurrentAcceptanceManifestCommitment(
                critic_id=commitment.critic_id,
                salted_commitment_sha256=commitment.salted_commitment_sha256,
            )
        ),
    )


def _legacy_critic_source(value: JsonValue) -> MigratedCriticSource | None:
    if not isinstance(value, dict):
        return None
    try:
        if value.get("kind") == "artifact":
            return ArtifactCriticSource.model_validate(value)
        return RepositoryCriticSource.model_validate(value)
    except ValueError:
        return None


__all__ = (
    "EvaluationPlan",
    "LegacyRegimeMigration",
    "migrate_legacy_evaluation_plan",
)
