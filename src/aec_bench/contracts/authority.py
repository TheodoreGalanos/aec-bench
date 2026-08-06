# ABOUTME: Defines immutable origin, basis, authority, taint, and operator-capability contracts.
# ABOUTME: Keeps trust-granting transitions closed, content-addressed, and separate from candidate output.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel, FrozenStrictModel, validate_sha256
from aec_bench.contracts.validators import NonEmptyStr


class AuthorityPrincipalKind(StrEnum):
    """Closed principal kinds that may appear in governance provenance."""

    HUMAN = "human"
    HOST_RUNTIME = "host_runtime"
    HOST_POLICY = "host_policy"
    TASK_AUTHORITY = "task_authority"
    CRITIC_AUTHORITY = "critic_authority"
    CANDIDATE = "candidate"
    MODEL = "model"
    OPTIMIZER = "optimizer"
    RED_TEAM = "red_team"
    MONITOR = "monitor"
    EXTERNAL = "external"


class AuthorityAction(StrEnum):
    """Consequential transitions governed by typed authority events."""

    PROPOSAL_FREEZE = "proposal_freeze"
    COMPILE = "compile"
    PROVIDER_DISPATCH = "provider_dispatch"
    SCORED_EVIDENCE_IMPORT = "scored_evidence_import"
    PAIRED_COMPARISON = "paired_comparison"
    REPAIR_ACCEPTANCE = "repair_acceptance"
    POLICY_PROMOTION = "policy_promotion"
    MOTIF_PROMOTION = "motif_promotion"
    MOTIF_STATE_CHANGE = "motif_state_change"
    RELEASE_CRITIC_GENERATION = "release_critic_generation"
    RETIRE_CRITIC_GENERATION = "retire_critic_generation"
    REVEAL_ACCEPTANCE_MANIFEST = "reveal_acceptance_manifest"
    RELEASE_EVALUATION_COHORT = "release_evaluation_cohort"
    RETIRE_EVALUATION_COHORT = "retire_evaluation_cohort"
    CHANGE_KERNEL_VERSION = "change_kernel_version"
    SUSPEND_SUBJECT = "suspend_subject"


class AuthorityDecision(StrEnum):
    """Whether one scoped transition was granted or denied."""

    GRANTED = "granted"
    DENIED = "denied"


class BasisKind(StrEnum):
    """Typed artifact roles that may support an authority decision."""

    ORIGIN = "origin"
    EVIDENCE = "evidence"
    CRITIC_SPEC = "critic_spec"
    EVALUATION_OUTCOME = "evaluation_outcome"
    CRITIC_EVALUATION_OUTCOME = "critic_evaluation_outcome"
    MONITOR_REPORT = "monitor_report"
    PROMOTION_MONITOR = "promotion_monitor"
    PROMOTION_LINEAGE = "promotion_lineage"
    MOTIF_ASSURANCE = "motif_assurance"
    MOTIF_QUALIFICATION = "motif_qualification"
    AUTHORITY_EVENT = "authority_event"
    HUMAN_APPROVAL = "human_approval"
    REGRESSION_EVIDENCE = "regression_evidence"


class TaintLabel(StrEnum):
    """Monotone provenance labels carried by consequential derived artifacts."""

    CANDIDATE_AUTHORED = "candidate_authored"
    MODEL_REPORTED = "model_reported"
    EXTERNAL_UNVERIFIED = "external_unverified"
    RUNTIME_OBSERVED = "runtime_observed"
    TASK_AUTHORITY = "task_authority"
    CRITIC_AUTHORITY = "critic_authority"
    HUMAN_AUTHORITY = "human_authority"
    INTEGRITY_INCIDENT = "integrity_incident"


class AuthorityPrincipal(FrozenStrictModel):
    """One named principal observed at a governance boundary."""

    principal_id: NonEmptyStr
    kind: AuthorityPrincipalKind


class HumanAuthorityApproval(ContentAddressedModel):
    """Human decision bound to one exact consequential action and subject identity."""

    schema_version: Literal["aecbench.human-authority-approval.v1"] = "aecbench.human-authority-approval.v1"
    approval_id: NonEmptyStr
    principal: AuthorityPrincipal
    action: AuthorityAction
    subject_id: NonEmptyStr
    subject_sha256: str
    approved: bool
    reason: NonEmptyStr

    @field_validator("subject_sha256")
    @classmethod
    def validate_subject_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_human_principal(self) -> Self:
        if self.principal.kind is not AuthorityPrincipalKind.HUMAN:
            raise ValueError("human authority approval requires a human principal")
        return self


class BasisReference(FrozenStrictModel):
    """Exact typed artifact reference used as decision basis."""

    kind: BasisKind
    artifact_id: NonEmptyStr
    artifact_sha256: str

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_hash(cls, value: str) -> str:
        return validate_sha256(value)


class PromotionSubjectLineage(ContentAddressedModel):
    """Host-derived join from one evaluated candidate to one promotion subject."""

    schema_version: Literal["aecbench.promotion-subject-lineage.v1"] = "aecbench.promotion-subject-lineage.v1"
    action: AuthorityAction
    critic_evaluation_outcome_sha256: str
    candidate_sha256: str
    subject_id: NonEmptyStr
    subject_sha256: str
    derivation_evidence_sha256s: tuple[str, ...] = ()

    @field_validator(
        "critic_evaluation_outcome_sha256",
        "candidate_sha256",
        "subject_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("derivation_evidence_sha256s")
    @classmethod
    def canonicalize_derivation_evidence(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("promotion derivation evidence identities must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_promotion_lineage(self) -> Self:
        if self.action not in {
            AuthorityAction.POLICY_PROMOTION,
            AuthorityAction.MOTIF_PROMOTION,
            AuthorityAction.MOTIF_STATE_CHANGE,
        }:
            raise ValueError("promotion lineage requires a promotion action")
        if self.subject_sha256 != self.candidate_sha256 and not self.derivation_evidence_sha256s:
            raise ValueError("derived promotion subject requires causal derivation evidence")
        return self


class MotifPromotionAssurance(ContentAddressedModel):
    """Exact active motif-assurance state admitted as promotion basis."""

    schema_version: Literal["aecbench.motif-promotion-assurance.v1"] = "aecbench.motif-promotion-assurance.v1"
    motif_subject_sha256: str
    selected_motif_sha256: str
    assurance_snapshot_sha256: str
    assurance_head_event_sha256: str
    eligible: Literal[True] = True

    @field_validator(
        "motif_subject_sha256",
        "selected_motif_sha256",
        "assurance_snapshot_sha256",
        "assurance_head_event_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class MotifPromotionQualification(ContentAddressedModel):
    """Host-derived proof that one exact provisional motif passed the first promotion gate."""

    schema_version: Literal["aecbench.motif-promotion-qualification.v1"] = "aecbench.motif-promotion-qualification.v1"
    action: Literal[AuthorityAction.MOTIF_PROMOTION] = AuthorityAction.MOTIF_PROMOTION
    subject_id: NonEmptyStr
    provisional_motif_sha256: str
    motif_subject_sha256: str
    candidate_sha256: str
    critic_evaluation_outcome_sha256: str
    promotion_lineage_sha256: str
    promotion_monitor_attestation_sha256: str
    monitor_report_sha256: str
    evaluation_plan_sha256: str
    critic_release_authority_event_sha256: str
    critic_generation_sha256: str
    kernel_sha256: str
    qualified: Literal[True] = True

    @field_validator(
        "provisional_motif_sha256",
        "motif_subject_sha256",
        "candidate_sha256",
        "critic_evaluation_outcome_sha256",
        "promotion_lineage_sha256",
        "promotion_monitor_attestation_sha256",
        "monitor_report_sha256",
        "evaluation_plan_sha256",
        "critic_release_authority_event_sha256",
        "critic_generation_sha256",
        "kernel_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_exact_candidate(self) -> Self:
        if self.candidate_sha256 != self.provisional_motif_sha256:
            raise ValueError("motif qualification candidate must be the exact provisional motif")
        return self


class PromotionMonitorAttestation(ContentAddressedModel):
    """Host-policy attestation joining a passing monitor to one promotion regime."""

    schema_version: Literal["aecbench.promotion-monitor-attestation.v1"] = "aecbench.promotion-monitor-attestation.v1"
    monitor_basis_sha256: str
    monitor_report_sha256: str
    evaluation_plan_sha256: str
    assurance_snapshot_sha256: str
    cycle_id: NonEmptyStr
    cycle_index: int = Field(ge=0)
    passed: Literal[True] = True

    @field_validator(
        "monitor_basis_sha256",
        "monitor_report_sha256",
        "evaluation_plan_sha256",
        "assurance_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class OriginStamp(ContentAddressedModel):
    """Host-observed producer and taint lineage for one consequential artifact."""

    schema_version: Literal["aecbench.origin-stamp.v1"] = "aecbench.origin-stamp.v1"
    artifact_id: NonEmptyStr
    artifact_sha256: str
    producer: AuthorityPrincipal
    producer_process_id: NonEmptyStr
    observed_by: AuthorityPrincipal
    channel: NonEmptyStr
    operation_id: NonEmptyStr
    invocation_id: NonEmptyStr
    parent_origin_sha256s: tuple[str, ...] = ()
    taint_labels: tuple[TaintLabel, ...] = Field(min_length=1)

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("parent_origin_sha256s")
    @classmethod
    def canonicalize_parent_origins(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("parent origin references must be unique")
        return tuple(sorted(value))

    @field_validator("taint_labels")
    @classmethod
    def canonicalize_taint(cls, value: tuple[TaintLabel, ...]) -> tuple[TaintLabel, ...]:
        return tuple(sorted(set(value), key=lambda label: label.value))

    @model_validator(mode="after")
    def validate_observation_boundary(self) -> Self:
        if self.observed_by.kind not in {
            AuthorityPrincipalKind.HOST_RUNTIME,
            AuthorityPrincipalKind.HOST_POLICY,
        }:
            raise ValueError("origin stamps must be observed by a host principal")
        required_by_producer = {
            AuthorityPrincipalKind.CANDIDATE: TaintLabel.CANDIDATE_AUTHORED,
            AuthorityPrincipalKind.MODEL: TaintLabel.MODEL_REPORTED,
            AuthorityPrincipalKind.EXTERNAL: TaintLabel.EXTERNAL_UNVERIFIED,
        }
        required = required_by_producer.get(self.producer.kind)
        if required is not None and required not in self.taint_labels:
            raise ValueError(f"{self.producer.kind.value} origin requires {required.value} taint")
        return self


class AuthorityEvent(ContentAddressedModel):
    """Scoped trust decision whose grant authority is validated by principal kind."""

    schema_version: Literal["aecbench.authority-event.v1"] = "aecbench.authority-event.v1"
    event_id: NonEmptyStr
    principal: AuthorityPrincipal
    action: AuthorityAction
    decision: AuthorityDecision
    subject_id: NonEmptyStr
    subject_sha256: str
    basis: tuple[BasisReference, ...] = Field(min_length=1)
    kernel_sha256: str
    critic_generation_sha256: str | None = None
    reasons: tuple[NonEmptyStr, ...] = Field(min_length=1)
    revalidation_triggers: tuple[NonEmptyStr, ...] = ()

    @field_validator("subject_sha256", "kernel_sha256")
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("critic_generation_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_sha256(value)

    @field_validator("basis")
    @classmethod
    def canonicalize_basis(cls, value: tuple[BasisReference, ...]) -> tuple[BasisReference, ...]:
        identities = tuple((item.kind.value, item.artifact_id, item.artifact_sha256) for item in value)
        if len(identities) != len(set(identities)):
            raise ValueError("authority basis references must be unique")
        return tuple(sorted(value, key=lambda item: (item.kind.value, item.artifact_id, item.artifact_sha256)))

    @field_validator("reasons", "revalidation_triggers")
    @classmethod
    def canonicalize_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("authority event string values must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_grant_authority(self) -> Self:
        if self.decision is AuthorityDecision.DENIED:
            return self
        allowed = _GRANT_AUTHORITY[self.action]
        if self.principal.kind not in allowed:
            if self.action in _HUMAN_ONLY_ACTIONS:
                raise ValueError(f"{self.action.value} requires a human principal")
            raise ValueError(f"{self.principal.kind.value} principal cannot grant {self.action.value}")
        if self.action in _CRITIC_GENERATION_ACTIONS and self.critic_generation_sha256 is None:
            raise ValueError("critic generation transitions require an exact critic generation identity")
        return self


class OperatorRole(StrEnum):
    """Disjoint adaptive controller roles."""

    DIAGNOSTIC_REPAIR = "diagnostic_repair"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    ADAPTIVE_RED_TEAM = "adaptive_red_team"


class OperatorCapability(StrEnum):
    """Non-authoritative capabilities exposed to adaptive controllers."""

    READ_DIAGNOSTIC_EVIDENCE = "read_diagnostic_evidence"
    PROPOSE_TYPED_PATCH = "propose_typed_patch"
    READ_DEVELOPMENT_FEEDBACK = "read_development_feedback"
    PROPOSE_CANDIDATE = "propose_candidate"
    UPDATE_TRAINING_STATE = "update_training_state"
    PROPOSE_CHALLENGE = "propose_challenge"
    WRITE_CHALLENGE_CASE = "write_challenge_case"


class OperatorAuthority(ContentAddressedModel):
    """Closed capability set for one non-authoritative adaptive operator."""

    schema_version: Literal["aecbench.operator-authority.v1"] = "aecbench.operator-authority.v1"
    operator_id: NonEmptyStr
    role: OperatorRole
    capabilities: tuple[OperatorCapability, ...]

    @field_validator("capabilities")
    @classmethod
    def canonicalize_capabilities(
        cls,
        value: tuple[OperatorCapability, ...],
    ) -> tuple[OperatorCapability, ...]:
        if len(value) != len(set(value)):
            raise ValueError("operator capabilities must be unique")
        declaration_order = {capability: index for index, capability in enumerate(OperatorCapability)}
        return tuple(sorted(value, key=declaration_order.__getitem__))

    @model_validator(mode="after")
    def validate_closed_role(self) -> Self:
        expected = _OPERATOR_CAPABILITIES[self.role]
        if self.capabilities != expected:
            raise ValueError(f"{self.role.value} operator capabilities must match the closed role policy")
        return self


_CRITIC_GENERATION_ACTIONS = {
    AuthorityAction.RELEASE_CRITIC_GENERATION,
    AuthorityAction.RETIRE_CRITIC_GENERATION,
    AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST,
}
_EVALUATION_COHORT_ACTIONS = {
    AuthorityAction.RELEASE_EVALUATION_COHORT,
    AuthorityAction.RETIRE_EVALUATION_COHORT,
}
_HUMAN_ONLY_ACTIONS = {
    *_CRITIC_GENERATION_ACTIONS,
    *_EVALUATION_COHORT_ACTIONS,
    AuthorityAction.CHANGE_KERNEL_VERSION,
}
_GRANT_AUTHORITY: dict[AuthorityAction, frozenset[AuthorityPrincipalKind]] = {
    AuthorityAction.PROPOSAL_FREEZE: frozenset(
        {
            AuthorityPrincipalKind.HOST_RUNTIME,
            AuthorityPrincipalKind.HOST_POLICY,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
    AuthorityAction.COMPILE: frozenset(
        {
            AuthorityPrincipalKind.HOST_RUNTIME,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
    AuthorityAction.PROVIDER_DISPATCH: frozenset(
        {
            AuthorityPrincipalKind.HOST_RUNTIME,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
    AuthorityAction.SCORED_EVIDENCE_IMPORT: frozenset(
        {
            AuthorityPrincipalKind.HOST_RUNTIME,
            AuthorityPrincipalKind.TASK_AUTHORITY,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
    AuthorityAction.PAIRED_COMPARISON: frozenset(
        {
            AuthorityPrincipalKind.HOST_POLICY,
            AuthorityPrincipalKind.CRITIC_AUTHORITY,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
    AuthorityAction.REPAIR_ACCEPTANCE: frozenset(
        {
            AuthorityPrincipalKind.HOST_POLICY,
            AuthorityPrincipalKind.CRITIC_AUTHORITY,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
    AuthorityAction.POLICY_PROMOTION: frozenset(
        {
            AuthorityPrincipalKind.HOST_POLICY,
            AuthorityPrincipalKind.CRITIC_AUTHORITY,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
    AuthorityAction.MOTIF_PROMOTION: frozenset(
        {
            AuthorityPrincipalKind.HOST_POLICY,
            AuthorityPrincipalKind.CRITIC_AUTHORITY,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
    AuthorityAction.MOTIF_STATE_CHANGE: frozenset(
        {
            AuthorityPrincipalKind.HOST_POLICY,
            AuthorityPrincipalKind.CRITIC_AUTHORITY,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
    AuthorityAction.RELEASE_CRITIC_GENERATION: frozenset({AuthorityPrincipalKind.HUMAN}),
    AuthorityAction.RETIRE_CRITIC_GENERATION: frozenset({AuthorityPrincipalKind.HUMAN}),
    AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST: frozenset({AuthorityPrincipalKind.HUMAN}),
    AuthorityAction.RELEASE_EVALUATION_COHORT: frozenset({AuthorityPrincipalKind.HUMAN}),
    AuthorityAction.RETIRE_EVALUATION_COHORT: frozenset({AuthorityPrincipalKind.HUMAN}),
    AuthorityAction.CHANGE_KERNEL_VERSION: frozenset({AuthorityPrincipalKind.HUMAN}),
    AuthorityAction.SUSPEND_SUBJECT: frozenset(
        {
            AuthorityPrincipalKind.HOST_POLICY,
            AuthorityPrincipalKind.HUMAN,
        }
    ),
}
_OPERATOR_CAPABILITIES: dict[OperatorRole, tuple[OperatorCapability, ...]] = {
    OperatorRole.DIAGNOSTIC_REPAIR: (
        OperatorCapability.READ_DIAGNOSTIC_EVIDENCE,
        OperatorCapability.PROPOSE_TYPED_PATCH,
    ),
    OperatorRole.PERFORMANCE_OPTIMIZATION: (
        OperatorCapability.READ_DEVELOPMENT_FEEDBACK,
        OperatorCapability.PROPOSE_CANDIDATE,
        OperatorCapability.UPDATE_TRAINING_STATE,
    ),
    OperatorRole.ADAPTIVE_RED_TEAM: (
        OperatorCapability.READ_DEVELOPMENT_FEEDBACK,
        OperatorCapability.PROPOSE_CHALLENGE,
        OperatorCapability.WRITE_CHALLENGE_CASE,
    ),
}


def derive_origin_stamp(
    *,
    artifact_id: str,
    artifact_sha256: str,
    producer: AuthorityPrincipal,
    producer_process_id: str,
    observed_by: AuthorityPrincipal,
    channel: str,
    operation_id: str,
    invocation_id: str,
    parents: tuple[OriginStamp, ...],
    operation_taint: tuple[TaintLabel, ...],
) -> OriginStamp:
    """Create a derived origin whose taint is the union of every parent and operation label."""
    inherited = {label for parent in parents for label in parent.taint_labels}
    return OriginStamp(
        artifact_id=artifact_id,
        artifact_sha256=artifact_sha256,
        producer=producer,
        producer_process_id=producer_process_id,
        observed_by=observed_by,
        channel=channel,
        operation_id=operation_id,
        invocation_id=invocation_id,
        parent_origin_sha256s=tuple(parent.content_sha256 for parent in parents),
        taint_labels=tuple(inherited.union(operation_taint)),
    )


def operator_authority_for(operator_id: str, role: OperatorRole) -> OperatorAuthority:
    """Build the exact non-authoritative capability set for one adaptive controller role."""
    return OperatorAuthority(
        operator_id=operator_id,
        role=role,
        capabilities=_OPERATOR_CAPABILITIES[role],
    )
