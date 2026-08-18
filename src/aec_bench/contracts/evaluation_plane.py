# ABOUTME: Defines one publishable evaluation regime and separate hidden-assignment commitments.
# ABOUTME: Keeps critic configuration embedded while preserving salted acceptance-manifest reveals.

from __future__ import annotations

import secrets
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, JsonValue, NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority import BasisKind, BasisReference
from aec_bench.contracts.evaluation_refs import CriticRef, CriticRole, EvaluationRegimeRef
from aec_bench.contracts.harness_kernel import KernelRef, canonical_json_sha256, validate_sha256
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class CriticFeedbackVisibility(StrEnum):
    """Whether critic feedback is visible to candidate-generating operators."""

    VISIBLE = "visible"
    HOST_ONLY = "host_only"


class AcceptanceManifestRevealRule(StrEnum):
    """Closed lifecycle point at which hidden acceptance cases become auditable."""

    ON_CRITIC_RETIREMENT = "on_critic_retirement"


class ExecutableAnchorCalibrationCadence(StrEnum):
    """Lifecycle cadence at which critics are checked against executable truth."""

    EVERY_CRITIC_RELEASE = "every_critic_release"


class ExecutableAnchorCalibrationPolicy(FrozenStrictModel):
    """Semantic release-time policy embedded in an evaluation regime."""

    cadence: Literal[ExecutableAnchorCalibrationCadence.EVERY_CRITIC_RELEASE] = (
        ExecutableAnchorCalibrationCadence.EVERY_CRITIC_RELEASE
    )
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


class ExecutableAnchorCalibrationEvidence(FrozenStrictModel):
    """Completed comparison of one regime critic against executable anchors."""

    schema_version: Literal["aecbench.executable-anchor-calibration-evidence.v2"] = (
        "aecbench.executable-anchor-calibration-evidence.v2"
    )
    calibration_id: NonEmptyStr
    evaluation_regime: EvaluationRegimeRef
    critic: CriticRef
    executable_anchor_sha256s: tuple[str, ...] = Field(min_length=1)
    evaluation_outcomes: tuple[BasisReference, ...] = Field(min_length=1)
    completed: bool
    passed: bool

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
    def validate_bindings(self) -> Self:
        if self.critic.regime != self.evaluation_regime:
            raise ValueError("calibration critic must belong to the evaluation regime")
        if self.passed and not self.completed:
            raise ValueError("incomplete executable-anchor calibration cannot pass")
        return self


class AcceptanceManifestCommitment(FrozenStrictModel):
    """Public salted commitment to hidden acceptance cases and scoring policy."""

    critic_id: NonEmptyStr
    algorithm: Literal["sha256"] = "sha256"
    salted_commitment_sha256: str
    reveal_rule: Literal[AcceptanceManifestRevealRule.ON_CRITIC_RETIREMENT] = (
        AcceptanceManifestRevealRule.ON_CRITIC_RETIREMENT
    )

    @field_validator("salted_commitment_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @classmethod
    def create(
        cls,
        *,
        critic_id: str,
        case_manifest: JsonValue,
        scoring_policy: JsonValue,
        salt: str,
    ) -> AcceptanceManifestCommitment:
        """Commit canonical hidden content without retaining the salt publicly."""

        if not salt:
            raise ValueError("acceptance manifest commitment salt must not be empty")
        return cls(
            critic_id=critic_id,
            salted_commitment_sha256=_salted_manifest_sha256(
                case_manifest=case_manifest,
                scoring_policy=scoring_policy,
                salt=salt,
            ),
        )

    @classmethod
    def create_with_random_salt(
        cls,
        *,
        critic_id: str,
        case_manifest: JsonValue,
        scoring_policy: JsonValue,
    ) -> tuple[AcceptanceManifestCommitment, str]:
        """Create a commitment and return its host-only 256-bit random salt."""

        salt = secrets.token_hex(32)
        return (
            cls.create(
                critic_id=critic_id,
                case_manifest=case_manifest,
                scoring_policy=scoring_policy,
                salt=salt,
            ),
            salt,
        )


class RepositoryCriticSource(FrozenStrictModel):
    """Repository critic entry point at one exact Git revision."""

    kind: Literal["repository"] = "repository"
    source_revision: NonEmptyStr
    entrypoint: NonEmptyStr

    @field_validator("source_revision")
    @classmethod
    def validate_source_revision(cls, value: str) -> str:
        if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("critic source_revision must be a lowercase 40-character Git commit")
        return value


class ArtifactCriticSource(FrozenStrictModel):
    """Exact independently distributed critic implementation."""

    kind: Literal["artifact"] = "artifact"
    artifact: ArtifactRef


type CriticSource = Annotated[RepositoryCriticSource | ArtifactCriticSource, Field(discriminator="kind")]


class Critic(FrozenStrictModel):
    """One stable critic ID with embedded outcome-affecting configuration."""

    critic_id: NonEmptyStr
    role: CriticRole
    source: CriticSource
    configuration: dict[str, JsonValue] = Field(default_factory=dict)
    feedback_visibility: CriticFeedbackVisibility
    execution_principal_id: NonEmptyStr
    acceptance_manifest_commitment: AcceptanceManifestCommitment | None = None

    @field_validator("configuration")
    @classmethod
    def reject_nonsemantic_configuration(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        prohibited_path = _prohibited_regime_metadata_path(value)
        if prohibited_path is not None:
            raise ValueError(f"critic configuration contains nonsemantic identity or metadata at {prohibited_path}")
        return value

    @model_validator(mode="after")
    def validate_role_contract(self) -> Self:
        if self.role is CriticRole.ACCEPTANCE:
            if self.acceptance_manifest_commitment is None:
                raise ValueError("acceptance critic requires an acceptance manifest commitment")
            if self.feedback_visibility is not CriticFeedbackVisibility.HOST_ONLY:
                raise ValueError("acceptance critic feedback must remain host-only")
            if self.acceptance_manifest_commitment.critic_id != self.critic_id:
                raise ValueError("acceptance critic and manifest commitment identities must match")
            hidden_path = _hidden_acceptance_configuration_path(self.configuration)
            if hidden_path is not None:
                raise ValueError(f"acceptance critic configuration contains hidden material at {hidden_path}")
        elif self.acceptance_manifest_commitment is not None:
            raise ValueError("only acceptance critics may bind an acceptance manifest commitment")
        if self.role is CriticRole.DEVELOPMENT and self.feedback_visibility is not CriticFeedbackVisibility.VISIBLE:
            raise ValueError("development critic feedback must be visible")
        return self

    def ref(self, regime: EvaluationRegimeRef) -> CriticRef:
        """Reference this critic inside one exact published regime."""

        return CriticRef(regime=regime, critic_id=self.critic_id, role=self.role)


class AcceptanceManifestReveal(FrozenStrictModel):
    """Retirement-time reveal that verifies one public salted commitment."""

    schema_version: Literal["aecbench.acceptance-manifest-reveal.v2"] = "aecbench.acceptance-manifest-reveal.v2"
    evaluation_regime: EvaluationRegimeRef
    critic: Critic
    case_manifest: JsonValue
    scoring_policy: JsonValue
    salt: NonEmptyStr
    retirement_authority_event_sha256: str
    evaluation_outcome_sha256s: tuple[str, ...] = ()
    promotion_sha256s: tuple[str, ...] = ()

    @field_validator("retirement_authority_event_sha256")
    @classmethod
    def validate_required_hash(cls, value: str) -> str:
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
        commitment = self.critic.acceptance_manifest_commitment
        if self.critic.role is not CriticRole.ACCEPTANCE or commitment is None:
            raise ValueError("acceptance reveal requires an acceptance critic")
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
        evaluation_regime: EvaluationRegimeRef,
        critic: Critic,
        case_manifest: JsonValue,
        scoring_policy: JsonValue,
        salt: str,
        retirement_authority_event_sha256: str,
        evaluation_outcome_sha256s: tuple[str, ...] = (),
        promotion_sha256s: tuple[str, ...] = (),
    ) -> AcceptanceManifestReveal:
        """Construct and verify a retirement-time reveal."""

        return cls(
            evaluation_regime=evaluation_regime,
            critic=critic,
            case_manifest=case_manifest,
            scoring_policy=scoring_policy,
            salt=salt,
            retirement_authority_event_sha256=retirement_authority_event_sha256,
            evaluation_outcome_sha256s=evaluation_outcome_sha256s,
            promotion_sha256s=promotion_sha256s,
        )


def acceptance_manifest_reveal_commitment(reveal: AcceptanceManifestReveal) -> str:
    """Return the named commitment used for reveal authority."""

    return canonical_json_sha256(reveal.model_dump(mode="json"))


class EvaluationBudgetPartition(FrozenStrictModel):
    """Hard resource ceiling for one component of an evaluation regime."""

    case_count: NonNegativeInt
    max_attempts: NonNegativeInt
    max_turns: NonNegativeInt
    max_tokens: NonNegativeInt
    max_cost_usd: FiniteFloat = Field(ge=0)
    max_wall_time_seconds: FiniteFloat = Field(ge=0)


class EvaluationBudget(FrozenStrictModel):
    """Candidate and critic-plane resource partitions."""

    proposal: EvaluationBudgetPartition
    execution: EvaluationBudgetPartition
    development: EvaluationBudgetPartition
    acceptance: EvaluationBudgetPartition
    red_team: EvaluationBudgetPartition
    monitor: EvaluationBudgetPartition
    audit: EvaluationBudgetPartition


class _EvaluationPolicy(FrozenStrictModel):
    policy_id: NonEmptyStr
    configuration: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("configuration")
    @classmethod
    def reject_nonsemantic_configuration(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        prohibited_path = _prohibited_regime_metadata_path(value)
        if prohibited_path is not None:
            raise ValueError(f"evaluation policy contains nonsemantic identity or metadata at {prohibited_path}")
        return value


class AcceptancePolicy(_EvaluationPolicy):
    """Rules that convert evaluated evidence into acceptance decisions."""


class EligibilityPolicy(_EvaluationPolicy):
    """Rules that determine which outcomes may enter evaluation."""


class DenominatorPolicy(_EvaluationPolicy):
    """Rules for the population used by aggregate measures."""


class EvidencePolicy(_EvaluationPolicy):
    """Rules for evidence inclusion and fail-closed treatment."""


class CalibrationPolicy(_EvaluationPolicy):
    """Rules for critic calibration and executable anchors."""


class StoppingPolicy(_EvaluationPolicy):
    """Rules that stop evaluation work."""


class MonitoringPolicy(_EvaluationPolicy):
    """Rules for standing and cycle-level evaluation monitors."""


class WorldEvaluationPolicy(_EvaluationPolicy):
    """Rules for using task-owned World evaluation evidence."""


type EvaluationPolicy = (
    AcceptancePolicy
    | EligibilityPolicy
    | DenominatorPolicy
    | EvidencePolicy
    | CalibrationPolicy
    | StoppingPolicy
    | MonitoringPolicy
    | WorldEvaluationPolicy
)


def evaluation_policy_commitment(policy: EvaluationPolicy | ExecutableAnchorCalibrationPolicy) -> str:
    """Commit one canonical policy when another authority must bind it."""

    return canonical_json_sha256(policy.model_dump(mode="json"))


class EvaluationRegime(FrozenStrictModel):
    """One independently publishable semantic evaluation bundle."""

    regime_id: NonEmptyStr
    critics: tuple[Critic, ...] = Field(min_length=2)
    budget: EvaluationBudget
    acceptance_policy: AcceptancePolicy
    eligibility_policy: EligibilityPolicy
    denominator_policy: DenominatorPolicy
    evidence_policy: EvidencePolicy
    calibration_policy: CalibrationPolicy | None = None
    stopping_policy: StoppingPolicy | None = None
    monitoring_policy: MonitoringPolicy | None = None
    world_evaluation_policy: WorldEvaluationPolicy | None = None

    @field_validator("critics")
    @classmethod
    def canonicalize_critics(cls, value: tuple[Critic, ...]) -> tuple[Critic, ...]:
        roles = tuple(critic.role for critic in value)
        if len(roles) != len(set(roles)):
            raise ValueError("evaluation regime critic roles must be unique")
        required = {CriticRole.DEVELOPMENT, CriticRole.ACCEPTANCE}
        if not required.issubset(roles):
            raise ValueError("evaluation regime requires development and acceptance critics")
        critic_ids = tuple(critic.critic_id for critic in value)
        if len(critic_ids) != len(set(critic_ids)):
            raise ValueError("evaluation regime critic IDs must be unique")
        principals = tuple(critic.execution_principal_id for critic in value)
        if len(principals) != len(set(principals)):
            raise ValueError("evaluation regime critic execution principals must be distinct")
        order = {role: index for index, role in enumerate(CriticRole)}
        return tuple(sorted(value, key=lambda critic: order[critic.role]))

    def critic(self, role: CriticRole) -> Critic:
        """Return the critic for one required role."""

        for critic in self.critics:
            if critic.role is role:
                return critic
        raise LookupError(f"evaluation regime has no {role.value} critic")


class EvaluationRegimeEnvelope(FrozenStrictModel):
    """Only versioned persisted envelope for an evaluation regime."""

    schema_version: Literal[1] = 1
    regime: EvaluationRegime


class CandidateManifestScope(FrozenStrictModel):
    """Named assignment commitment over task-scoped candidate manifests."""

    scope_id: NonEmptyStr
    candidate_manifest_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator("candidate_manifest_sha256s")
    @classmethod
    def canonicalize_candidate_manifest_sha256s(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("candidate manifest scope identities must be unique")
        return tuple(sorted(value))


def candidate_manifest_scope_commitment(scope: CandidateManifestScope) -> str:
    """Return the named commitment for one candidate-manifest scope."""

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
    """Task-specific verifier-only file inventory used as an assignment commitment."""

    task_id: NonEmptyStr
    task_revision: str
    source_task_package_sha256: str
    sealed_task_package_sha256: str | None = None
    files: tuple[TaskVerifierFileInventoryEntry, ...] = Field(min_length=1)

    @field_validator("task_revision", "source_task_package_sha256", "sealed_task_package_sha256")
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
            raise ValueError("sealed verifier files and sealed task package identity must be present together")
        return self


class TaskVerifierSurfaceScope(FrozenStrictModel):
    """Named assignment commitment over task-specific verifier surfaces."""

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
        return tuple(sorted(value, key=lambda surface: (surface.task_id, surface.task_revision)))


def task_verifier_surface_commitment(surface: TaskVerifierSurface | TaskVerifierSurfaceScope) -> str:
    """Return the named commitment for a verifier surface."""

    return canonical_json_sha256(surface.model_dump(mode="json"))


class EvaluationAssignment(FrozenStrictModel):
    """Candidate- and split-specific bindings kept outside the public regime."""

    assignment_id: NonEmptyStr
    regime: EvaluationRegimeRef
    kernel_ref: KernelRef
    harness_policy_commitment: str
    candidate_manifest_commitment: str
    task_manifest_commitment: str
    split_manifest_commitment: str
    task_verifier_commitment: str

    @field_validator(
        "harness_policy_commitment",
        "candidate_manifest_commitment",
        "task_manifest_commitment",
        "split_manifest_commitment",
        "task_verifier_commitment",
    )
    @classmethod
    def validate_commitments(cls, value: str) -> str:
        return validate_sha256(value)


class CriticReleaseAuthorityRef(FrozenStrictModel):
    """Replayable host reference to one exact critic release authority event."""

    critic: CriticRef
    authority_event_id: NonEmptyStr
    authority_event_sha256: str

    @field_validator("authority_event_sha256")
    @classmethod
    def validate_authority_event_hash(cls, value: str) -> str:
        return validate_sha256(value)


class EvaluationRegimeAuthorityScope(FrozenStrictModel):
    """Critic release authority for one exact published regime."""

    scope_id: NonEmptyStr
    regime: EvaluationRegimeRef
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
        if not {CriticRole.DEVELOPMENT, CriticRole.ACCEPTANCE}.issubset(roles):
            raise ValueError("evaluation authority requires development and acceptance critic releases")
        critic_ids = tuple(item.critic.critic_id for item in value)
        if len(critic_ids) != len(set(critic_ids)):
            raise ValueError("critic identities must be unique")
        event_ids = tuple(item.authority_event_id for item in value)
        event_hashes = tuple(item.authority_event_sha256 for item in value)
        if len(event_ids) != len(set(event_ids)) or len(event_hashes) != len(set(event_hashes)):
            raise ValueError("critic release authority events must be unique")
        order = {role: index for index, role in enumerate(CriticRole)}
        return tuple(sorted(value, key=lambda item: order[item.critic.role]))

    @model_validator(mode="after")
    def validate_regime(self) -> Self:
        if any(item.critic.regime != self.regime for item in self.critic_releases):
            raise ValueError("critic release belongs to a different evaluation regime")
        return self


def assert_evaluation_regimes_compatible(left: EvaluationRegimeRef, right: EvaluationRegimeRef) -> None:
    """Fail closed unless two references identify the same exact regime bytes."""

    if left.artifact.sha256 != right.artifact.sha256:
        raise ValueError("evaluation regime artifacts do not match")


def _salted_manifest_sha256(*, case_manifest: JsonValue, scoring_policy: JsonValue, salt: str) -> str:
    return canonical_json_sha256(
        {
            "domain": "aecbench.acceptance-manifest-commitment.v1",
            "salt": salt,
            "case_manifest": case_manifest,
            "scoring_policy": scoring_policy,
        }
    )


def _hidden_acceptance_configuration_path(value: dict[str, JsonValue]) -> str | None:
    hidden_keys = {
        "acceptance_cases",
        "case_ids",
        "case_manifest",
        "cases",
        "hidden_cases",
        "rubric",
        "salt",
        "scoring",
        "scoring_policy",
    }
    for key in value:
        if key.casefold().replace("-", "_") in hidden_keys:
            return f"configuration.{key}"
    return None


def _prohibited_regime_metadata_path(value: JsonValue, path: str = "configuration") -> str | None:
    prohibited_keys = {
        "case_manifest_sha256",
        "comment",
        "comments",
        "compatibility_generation",
        "content_sha256",
        "created_at",
        "critic_version",
        "denominator_policy_sha256",
        "eligibility_policy_sha256",
        "evidence_inclusion_policy_sha256",
        "generated_at",
        "implementation_sha256",
        "local_path",
        "publication_label",
        "published_at",
        "rubric_policy_sha256",
        "runtime_environment_sha256",
        "schema_version",
        "threshold_policy_sha256",
        "timestamp",
        "updated_at",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key.casefold().replace("-", "_") in prohibited_keys:
                return child_path
            nested = _prohibited_regime_metadata_path(item, child_path)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for index, item in enumerate(value):
            nested = _prohibited_regime_metadata_path(item, f"{path}[{index}]")
            if nested is not None:
                return nested
    return None


__all__ = (
    "AcceptanceManifestCommitment",
    "AcceptanceManifestReveal",
    "AcceptanceManifestRevealRule",
    "AcceptancePolicy",
    "ArtifactCriticSource",
    "CalibrationPolicy",
    "CandidateManifestScope",
    "Critic",
    "CriticFeedbackVisibility",
    "CriticReleaseAuthorityRef",
    "DenominatorPolicy",
    "EligibilityPolicy",
    "EvaluationAssignment",
    "EvaluationBudget",
    "EvaluationBudgetPartition",
    "EvaluationRegime",
    "EvaluationRegimeAuthorityScope",
    "EvaluationRegimeEnvelope",
    "EvidencePolicy",
    "ExecutableAnchorCalibrationCadence",
    "ExecutableAnchorCalibrationEvidence",
    "ExecutableAnchorCalibrationPolicy",
    "MonitoringPolicy",
    "RepositoryCriticSource",
    "StoppingPolicy",
    "TaskVerifierFileInventoryEntry",
    "TaskVerifierSurface",
    "TaskVerifierSurfaceScope",
    "WorldEvaluationPolicy",
    "acceptance_manifest_reveal_commitment",
    "assert_evaluation_regimes_compatible",
    "candidate_manifest_scope_commitment",
    "evaluation_policy_commitment",
    "task_verifier_surface_commitment",
)
