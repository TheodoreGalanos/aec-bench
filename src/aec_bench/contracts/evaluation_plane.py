# ABOUTME: Defines critic, evaluation, budget, and acceptance-escrow contracts.
# ABOUTME: Separates visible development feedback from hidden, independently governed promotion evidence.

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import Field, FiniteFloat, JsonValue, NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.authority import (
    BasisKind,
    BasisReference,
    CriticGenerationIdentity,
    EvaluationPlanIdentity,
)
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelRef,
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr


class CriticRole(StrEnum):
    """Independent roles in the evaluation plane."""

    DEVELOPMENT = "development"
    ACCEPTANCE = "acceptance"
    RED_TEAM = "red_team"


class CriticFeedbackVisibility(StrEnum):
    """Whether critic feedback is visible to candidate-generating operators."""

    VISIBLE = "visible"
    HOST_ONLY = "host_only"


class AcceptanceManifestRevealRule(StrEnum):
    """Closed lifecycle point at which hidden acceptance cases become auditable."""

    ON_GENERATION_RETIREMENT = "on_generation_retirement"


class ExecutableAnchorCalibrationCadence(StrEnum):
    """Lifecycle cadence at which a critic must be checked against executable truth."""

    EVERY_CRITIC_RELEASE = "every_critic_release"


class ExecutableAnchorCalibrationPolicy(FrozenStrictModel):
    """Typed policy whose digest is already frozen by an EvaluationPlan."""

    schema_version: Literal["aecbench.executable-anchor-calibration-policy.v1"] = (
        "aecbench.executable-anchor-calibration-policy.v1"
    )
    cadence: ExecutableAnchorCalibrationCadence
    critic_roles: tuple[CriticRole, ...] = (CriticRole.ACCEPTANCE,)

    @field_validator("critic_roles")
    @classmethod
    def canonicalize_critic_roles(cls, value: tuple[CriticRole, ...]) -> tuple[CriticRole, ...]:
        if not value:
            raise ValueError("executable-anchor calibration policy requires at least one critic role")
        if len(value) != len(set(value)):
            raise ValueError("executable-anchor calibration policy critic roles must be unique")
        order = {role: index for index, role in enumerate(CriticRole)}
        return tuple(sorted(value, key=order.__getitem__))


def executable_anchor_calibration_policy_commitment(
    policy: ExecutableAnchorCalibrationPolicy,
) -> str:
    """Return the named compatibility commitment frozen by an evaluation plan."""

    return canonical_json_sha256(policy.model_dump(mode="json"))


class ExecutableAnchorCalibrationEvidence(FrozenStrictModel):
    """Completed release-time comparison of one exact critic against executable anchors."""

    schema_version: Literal["aecbench.executable-anchor-calibration-evidence.v1"] = (
        "aecbench.executable-anchor-calibration-evidence.v1"
    )
    calibration_id: NonEmptyStr
    evaluation_plan: EvaluationPlanIdentity
    critic_generation: CriticGenerationIdentity
    anchor_calibration_policy_sha256: str
    executable_anchor_sha256s: tuple[str, ...] = Field(min_length=1)
    evaluation_outcomes: tuple[BasisReference, ...] = Field(min_length=1)
    completed: bool
    passed: bool

    @field_validator(
        "anchor_calibration_policy_sha256",
    )
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("executable_anchor_sha256s")
    @classmethod
    def canonicalize_anchor_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("executable-anchor calibration identities must be unique")
        return tuple(sorted(value))

    @field_validator("evaluation_outcomes")
    @classmethod
    def canonicalize_evaluation_outcomes(
        cls,
        value: tuple[BasisReference, ...],
    ) -> tuple[BasisReference, ...]:
        if any(reference.kind is not BasisKind.EVALUATION_OUTCOME for reference in value):
            raise ValueError("executable-anchor calibration requires evaluation_outcome basis references")
        identities = tuple((reference.artifact_id, reference.artifact_sha256) for reference in value)
        if len(identities) != len(set(identities)):
            raise ValueError("executable-anchor calibration outcomes must be unique")
        return tuple(sorted(value, key=lambda reference: (reference.artifact_id, reference.artifact_sha256)))

    @model_validator(mode="after")
    def validate_completion(self) -> Self:
        if self.passed and not self.completed:
            raise ValueError("incomplete executable-anchor calibration cannot pass")
        return self


class AcceptanceManifestCommitment(FrozenStrictModel):
    """Public salted commitment to one hidden acceptance manifest and scoring policy."""

    schema_version: Literal["aecbench.acceptance-manifest-commitment.v1"] = "aecbench.acceptance-manifest-commitment.v1"
    critic_id: NonEmptyStr
    critic_version: NonEmptyStr
    salted_commitment_sha256: str
    publication_receipt_sha256: str
    reveal_rule: AcceptanceManifestRevealRule = AcceptanceManifestRevealRule.ON_GENERATION_RETIREMENT

    @field_validator(
        "salted_commitment_sha256",
        "publication_receipt_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @classmethod
    def create(
        cls,
        *,
        critic_id: str,
        critic_version: str,
        case_manifest: JsonValue,
        scoring_policy: JsonValue,
        salt: str,
        publication_receipt_sha256: str,
    ) -> AcceptanceManifestCommitment:
        """Commit canonical hidden case and scoring bytes without retaining the salt publicly."""
        if not salt:
            raise ValueError("acceptance manifest commitment salt must not be empty")
        return cls(
            critic_id=critic_id,
            critic_version=critic_version,
            salted_commitment_sha256=_salted_manifest_sha256(
                case_manifest=case_manifest,
                scoring_policy=scoring_policy,
                salt=salt,
            ),
            publication_receipt_sha256=publication_receipt_sha256,
        )


class CriticRef(FrozenStrictModel):
    """Opaque critic identity safe to expose without hidden case or policy digests."""

    schema_version: Literal["aecbench.critic-ref.v1"] = "aecbench.critic-ref.v1"
    critic_id: NonEmptyStr
    version: NonEmptyStr
    role: CriticRole
    compatibility_generation: NonEmptyStr
    acceptance_manifest_commitment: AcceptanceManifestCommitment | None = None

    @model_validator(mode="after")
    def validate_role_contract(self) -> Self:
        if self.role is CriticRole.ACCEPTANCE and self.acceptance_manifest_commitment is None:
            raise ValueError("acceptance critic requires an acceptance manifest commitment")
        if self.role is not CriticRole.ACCEPTANCE and self.acceptance_manifest_commitment is not None:
            raise ValueError("only acceptance critics may bind an acceptance manifest commitment")
        return self

    @property
    def authority_identity(self) -> CriticGenerationIdentity:
        """Return the public critic identity used by authority records."""

        return CriticGenerationIdentity(
            critic_id=self.critic_id,
            version=self.version,
            compatibility_generation=self.compatibility_generation,
        )


class CriticSpec(FrozenStrictModel):
    """Host-only critic configuration whose ref reveals no live case identity."""

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
    parent_critic_ref: CriticRef | None = None
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
    def validate_hashes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_role_contract(self) -> Self:
        if self.role is CriticRole.ACCEPTANCE:
            if self.acceptance_manifest_commitment is None:
                raise ValueError("acceptance critic requires an acceptance manifest commitment")
            if self.feedback_visibility is not CriticFeedbackVisibility.HOST_ONLY:
                raise ValueError("acceptance critic feedback must remain host-only")
            if (
                self.acceptance_manifest_commitment.critic_id,
                self.acceptance_manifest_commitment.critic_version,
            ) != (self.critic_id, self.version):
                raise ValueError("acceptance critic and manifest commitment identities must match")
        elif self.acceptance_manifest_commitment is not None:
            raise ValueError("only acceptance critics may bind an acceptance manifest commitment")
        if self.role is CriticRole.DEVELOPMENT and self.feedback_visibility is not CriticFeedbackVisibility.VISIBLE:
            raise ValueError("development critic feedback must be visible")
        return self

    @property
    def ref(self) -> CriticRef:
        """Return the public critic identity without unsalted case or policy digests."""
        return CriticRef(
            critic_id=self.critic_id,
            version=self.version,
            role=self.role,
            compatibility_generation=self.compatibility_generation,
            acceptance_manifest_commitment=self.acceptance_manifest_commitment,
        )


def critic_spec_commitment(spec: CriticSpec) -> str:
    """Return the named host-only commitment used for critic release authority."""

    return canonical_json_sha256(spec.model_dump(mode="json"))


class AcceptanceManifestReveal(FrozenStrictModel):
    """Retirement-time reveal that verifies the host-only spec and public commitment."""

    schema_version: Literal["aecbench.acceptance-manifest-reveal.v1"] = "aecbench.acceptance-manifest-reveal.v1"
    critic_spec: CriticSpec
    case_manifest: JsonValue
    scoring_policy: JsonValue
    salt: NonEmptyStr
    retirement_authority_event_sha256: str
    evaluation_outcome_sha256s: tuple[str, ...] = ()
    promotion_sha256s: tuple[str, ...] = ()

    @field_validator("retirement_authority_event_sha256")
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("evaluation_outcome_sha256s", "promotion_sha256s")
    @classmethod
    def canonicalize_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("acceptance reveal references must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_reveal(self) -> Self:
        commitment = self.critic_spec.acceptance_manifest_commitment
        if self.critic_spec.role is not CriticRole.ACCEPTANCE or commitment is None:
            raise ValueError("acceptance reveal requires an acceptance critic spec")
        if canonical_json_sha256(self.case_manifest) != self.critic_spec.case_manifest_sha256:
            raise ValueError("acceptance reveal case manifest does not match its critic spec")
        if canonical_json_sha256(self.scoring_policy) != self.critic_spec.rubric_policy_sha256:
            raise ValueError("acceptance reveal scoring policy does not match its critic spec")
        expected = _salted_manifest_sha256(
            case_manifest=self.case_manifest,
            scoring_policy=self.scoring_policy,
            salt=self.salt,
        )
        if expected != commitment.salted_commitment_sha256:
            raise ValueError("acceptance reveal does not match the salted commitment")
        return self

    @classmethod
    def create(
        cls,
        *,
        critic_spec: CriticSpec,
        case_manifest: JsonValue,
        scoring_policy: JsonValue,
        salt: str,
        retirement_authority_event_sha256: str,
        evaluation_outcome_sha256s: tuple[str, ...] = (),
        promotion_sha256s: tuple[str, ...] = (),
    ) -> AcceptanceManifestReveal:
        """Construct and verify a retirement-time reveal against one exact critic spec."""
        commitment = critic_spec.acceptance_manifest_commitment
        if commitment is None:
            raise ValueError("acceptance reveal requires a committed acceptance critic")
        return cls(
            critic_spec=critic_spec,
            case_manifest=case_manifest,
            scoring_policy=scoring_policy,
            salt=salt,
            retirement_authority_event_sha256=retirement_authority_event_sha256,
            evaluation_outcome_sha256s=evaluation_outcome_sha256s,
            promotion_sha256s=promotion_sha256s,
        )


def acceptance_manifest_reveal_commitment(reveal: AcceptanceManifestReveal) -> str:
    """Return the named commitment used for retirement-time reveal authority."""

    return canonical_json_sha256(reveal.model_dump(mode="json"))


class EvaluationBudgetPartition(FrozenStrictModel):
    """Hard resource ceiling for one component of an evaluation generation."""

    case_count: NonNegativeInt
    max_attempts: NonNegativeInt
    max_turns: NonNegativeInt
    max_tokens: NonNegativeInt
    max_cost_usd: FiniteFloat = Field(ge=0)
    max_wall_time_seconds: FiniteFloat = Field(ge=0)


class EvaluationBudgetPlan(FrozenStrictModel):
    """Separate candidate and critic-plane budget partitions."""

    schema_version: Literal["aecbench.evaluation-budget-plan.v1"] = "aecbench.evaluation-budget-plan.v1"
    proposal: EvaluationBudgetPartition
    execution: EvaluationBudgetPartition
    development: EvaluationBudgetPartition
    acceptance: EvaluationBudgetPartition
    red_team: EvaluationBudgetPartition
    monitor: EvaluationBudgetPartition
    audit: EvaluationBudgetPartition


class CandidateManifestScope(FrozenStrictModel):
    """One evaluation commitment over one or more task-scoped candidate manifests."""

    schema_version: Literal["aecbench.candidate-manifest-scope.v1"] = "aecbench.candidate-manifest-scope.v1"
    scope_id: NonEmptyStr
    candidate_manifest_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator("candidate_manifest_sha256s")
    @classmethod
    def canonicalize_candidate_manifest_sha256s(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("candidate manifest scope identities must be unique")
        return tuple(sorted(value))


def candidate_manifest_scope_commitment(scope: CandidateManifestScope) -> str:
    """Return the named evaluation commitment for a candidate-manifest scope."""

    return canonical_json_sha256(scope.model_dump(mode="json"))


class TaskVerifierFileInventoryEntry(FrozenStrictModel):
    """One file on a host-only task verifier surface."""

    path: NonEmptyStr
    sha256: str
    byte_size: NonNegativeInt
    role: Literal["verifier_only", "sealed_verifier_only"]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("task verifier file paths must be contained and relative")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)


class TaskVerifierSurface(FrozenStrictModel):
    """Task-specific inventory of verifier-only and sealed-verifier-only files."""

    schema_version: Literal["aecbench.task-verifier-surface.v1"] = "aecbench.task-verifier-surface.v1"
    task_id: NonEmptyStr
    task_revision: str
    source_task_package_sha256: str
    sealed_task_package_sha256: str | None = None
    files: tuple[TaskVerifierFileInventoryEntry, ...] = Field(min_length=1)

    @field_validator(
        "task_revision",
        "source_task_package_sha256",
        "sealed_task_package_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @field_validator("files")
    @classmethod
    def canonicalize_files(
        cls,
        value: tuple[TaskVerifierFileInventoryEntry, ...],
    ) -> tuple[TaskVerifierFileInventoryEntry, ...]:
        paths = tuple(item.path for item in value)
        if len(paths) != len(set(paths)):
            raise ValueError("task verifier file paths must be unique")
        return tuple(sorted(value, key=lambda item: item.path))

    @model_validator(mode="after")
    def validate_sealed_inventory(self) -> Self:
        sealed_files = tuple(item for item in self.files if item.role == "sealed_verifier_only")
        if (self.sealed_task_package_sha256 is None) is not (not sealed_files):
            raise ValueError(
                "sealed verifier files and sealed task package identity must be present together",
            )
        return self


class TaskVerifierSurfaceScope(FrozenStrictModel):
    """One evaluation commitment over one or more task-specific verifier surfaces."""

    schema_version: Literal["aecbench.task-verifier-surface-scope.v1"] = "aecbench.task-verifier-surface-scope.v1"
    scope_id: NonEmptyStr
    task_surfaces: tuple[TaskVerifierSurface, ...] = Field(min_length=1)

    @field_validator("task_surfaces")
    @classmethod
    def canonicalize_task_surfaces(
        cls,
        value: tuple[TaskVerifierSurface, ...],
    ) -> tuple[TaskVerifierSurface, ...]:
        identities = tuple((surface.task_id, surface.task_revision) for surface in value)
        if len(identities) != len(set(identities)):
            raise ValueError("task verifier surface task identities must be unique")
        return tuple(
            sorted(
                value,
                key=lambda surface: (surface.task_id, surface.task_revision),
            )
        )


def task_verifier_surface_commitment(
    surface: TaskVerifierSurface | TaskVerifierSurfaceScope,
) -> str:
    """Return the named evaluation commitment for a verifier surface."""

    return canonical_json_sha256(surface.model_dump(mode="json"))


class EvaluationPlanRef(FrozenStrictModel):
    """Opaque evaluation-plan identity safe to attach to candidate-derived provenance."""

    schema_version: Literal["aecbench.evaluation-plan-ref.v1"] = "aecbench.evaluation-plan-ref.v1"
    plan_id: NonEmptyStr
    evaluation_generation: NonEmptyStr

    @property
    def authority_identity(self) -> EvaluationPlanIdentity:
        """Return the stable plan identity used by authority records."""

        return EvaluationPlanIdentity(
            plan_id=self.plan_id,
            evaluation_generation=self.evaluation_generation,
        )


class CriticReleaseAuthorityRef(FrozenStrictModel):
    """Replayable host-side reference to one exact critic release authority event."""

    schema_version: Literal["aecbench.critic-release-authority-ref.v1"] = "aecbench.critic-release-authority-ref.v1"
    critic: CriticRef
    authority_event_id: NonEmptyStr
    authority_event_sha256: str

    @field_validator("authority_event_sha256")
    @classmethod
    def validate_authority_event_hash(cls, value: str) -> str:
        return validate_sha256(value)


class EvaluationPlanAuthorityScope(FrozenStrictModel):
    """Authority evidence released after an evaluation plan and outside its digest."""

    schema_version: Literal["aecbench.evaluation-plan-authority-scope.v1"] = (
        "aecbench.evaluation-plan-authority-scope.v1"
    )
    scope_id: NonEmptyStr
    evaluation_plan_ref: EvaluationPlanRef
    critic_releases: tuple[CriticReleaseAuthorityRef, ...]

    @field_validator("critic_releases")
    @classmethod
    def canonicalize_critic_releases(
        cls,
        value: tuple[CriticReleaseAuthorityRef, ...],
    ) -> tuple[CriticReleaseAuthorityRef, ...]:
        roles = tuple(item.critic.role for item in value)
        if len(roles) != len(set(roles)):
            raise ValueError("critic roles must be unique")
        required = {CriticRole.DEVELOPMENT, CriticRole.ACCEPTANCE}
        if not required.issubset(roles):
            raise ValueError("evaluation authority requires development and acceptance critic releases")
        critic_ids = tuple((item.critic.critic_id, item.critic.version) for item in value)
        if len(critic_ids) != len(set(critic_ids)):
            raise ValueError("critic generation identities must be unique")
        event_ids = tuple(item.authority_event_id for item in value)
        event_hashes = tuple(item.authority_event_sha256 for item in value)
        if len(event_ids) != len(set(event_ids)) or len(event_hashes) != len(set(event_hashes)):
            raise ValueError("critic release authority events must be unique")
        return tuple(sorted(value, key=lambda item: item.critic.role.value))

    @model_validator(mode="after")
    def validate_compatibility_generation(self) -> Self:
        if any(
            item.critic.compatibility_generation != self.evaluation_plan_ref.evaluation_generation
            for item in self.critic_releases
        ):
            raise ValueError("critic release compatibility generation differs from the evaluation plan")
        return self


class EvaluationPlan(FrozenStrictModel):
    """Host-side preregistration binding critics, evidence surfaces, budgets, and gates.

    The candidate-manifest digest binds either one task-scoped manifest directly
    or one ``CandidateManifestScope`` for a multi-task study.
    The task-verifier digest likewise binds one ``TaskVerifierSurface`` directly
    or one ``TaskVerifierSurfaceScope`` for a multi-task study.
    """

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
    def validate_critic_separation(self) -> Self:
        if self.development_critic.role is not CriticRole.DEVELOPMENT:
            raise ValueError("development_critic must have the development role")
        if self.acceptance_critic.role is not CriticRole.ACCEPTANCE:
            raise ValueError("acceptance_critic must have the acceptance role")
        if self.red_team_critic is not None and self.red_team_critic.role is not CriticRole.RED_TEAM:
            raise ValueError("red_team_critic must have the red_team role")
        critics = tuple(
            critic
            for critic in (
                self.development_critic,
                self.acceptance_critic,
                self.red_team_critic,
            )
            if critic is not None
        )
        if any(critic.compatibility_generation != self.evaluation_generation for critic in critics):
            raise ValueError("all critics must bind the evaluation plan compatibility generation")
        case_manifests = tuple(critic.case_manifest_sha256 for critic in critics)
        if len(case_manifests) != len(set(case_manifests)):
            raise ValueError("critic case manifests must be distinct")
        principals = tuple(critic.execution_principal_id for critic in critics)
        if len(principals) != len(set(principals)):
            raise ValueError("critic execution principals must be distinct")
        return self

    @property
    def ref(self) -> EvaluationPlanRef:
        """Return the plan identity without exposing critic configuration or hidden manifests."""
        return EvaluationPlanRef(
            plan_id=self.plan_id,
            evaluation_generation=self.evaluation_generation,
        )


def assert_acceptance_compatible(left: EvaluationPlan, right: EvaluationPlan) -> None:
    """Fail closed when two candidate plans do not share one exact acceptance regime."""
    left_identity = (
        left.evaluation_generation,
        left.kernel_ref,
        left.harness_policy_sha256,
        left.task_manifest_sha256,
        left.split_manifest_sha256,
        left.task_verifier_sha256,
        left.acceptance_critic,
        left.budgets.acceptance.model_dump(mode="json"),
        left.integrity_policy_sha256,
        left.utility_policy_sha256,
        left.anchor_calibration_policy_sha256,
        left.monitor_plan_sha256,
        left.opening_policy_sha256,
        left.stopping_policy_sha256,
        left.confirmatory_suite_sha256,
    )
    right_identity = (
        right.evaluation_generation,
        right.kernel_ref,
        right.harness_policy_sha256,
        right.task_manifest_sha256,
        right.split_manifest_sha256,
        right.task_verifier_sha256,
        right.acceptance_critic,
        right.budgets.acceptance.model_dump(mode="json"),
        right.integrity_policy_sha256,
        right.utility_policy_sha256,
        right.anchor_calibration_policy_sha256,
        right.monitor_plan_sha256,
        right.opening_policy_sha256,
        right.stopping_policy_sha256,
        right.confirmatory_suite_sha256,
    )
    if left_identity != right_identity:
        raise ValueError("acceptance critic identity or acceptance regime does not match")


def _salted_manifest_sha256(
    *,
    case_manifest: JsonValue,
    scoring_policy: JsonValue,
    salt: str,
) -> str:
    return canonical_json_sha256(
        {
            "domain": "aecbench.acceptance-manifest-commitment.v1",
            "salt": salt,
            "case_manifest": case_manifest,
            "scoring_policy": scoring_policy,
        }
    )
