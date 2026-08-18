# ABOUTME: Defines phase-neutral critic-stress evidence, findings, and report contracts.
# ABOUTME: Keeps critic-stress evidence and classification with their current workflow owner.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    OriginStamp,
    TaintLabel,
)
from aec_bench.contracts.evaluation_outcome import (
    CriticGapDecomposition,
    NonNegativeFiniteFloat,
)
from aec_bench.contracts.evaluation_refs import CriticRef
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr


class RecordReceiptBinding(FrozenStrictModel):
    """Claimed mapping from one physical TrialRecord to one physical Harbor receipt."""

    record_sha256: str
    receipt_sha256: str

    @field_validator("record_sha256", "receipt_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class SeedEvidenceClaim(LegacyContentAddressedModel):
    """Derived claim surface used to seed integrity attacks without changing source bytes."""

    schema_version: Literal["aecbench.seed-evidence-claim.v1"] = "aecbench.seed-evidence-claim.v1"
    planned_record_sha256s: tuple[str, ...]
    claimed_record_sha256s: tuple[str, ...]
    claimed_denominator: NonNegativeInt
    cost_evidence_record_sha256s: tuple[str, ...]
    receipt_bindings: tuple[RecordReceiptBinding, ...]

    @field_validator(
        "planned_record_sha256s",
        "claimed_record_sha256s",
        "cost_evidence_record_sha256s",
    )
    @classmethod
    def canonicalize_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("seed evidence claim hash sets must be unique")
        return tuple(sorted(value))

    @field_validator("receipt_bindings")
    @classmethod
    def canonicalize_bindings(
        cls,
        value: tuple[RecordReceiptBinding, ...],
    ) -> tuple[RecordReceiptBinding, ...]:
        records = tuple(binding.record_sha256 for binding in value)
        if len(records) != len(set(records)):
            raise ValueError("seed evidence claim receipt records must be unique")
        return tuple(sorted(value, key=lambda binding: binding.record_sha256))


class AcceptanceGroundingKind(StrEnum):
    """How independently the acceptance critic is grounded."""

    EXECUTABLE_TRUTH = "executable_truth"
    HUMAN_AUDIT = "human_audit"
    HIDDEN_RUBRIC = "hidden_rubric"


class CriticStressFindingKind(StrEnum):
    """Closed interpretation of a raw gap plus independently observed evidence."""

    SELECTION_NOISE = "selection_noise"
    DIFFERENTIAL_SEAM = "differential_seam"
    COMMON_MODE_SHARED_CRITIC_BREACH = "common_mode_shared_critic_breach"
    INTEGRITY_BREACH = "integrity_breach"
    INCONCLUSIVE = "inconclusive"


class CriticStressLimitation(StrEnum):
    """Structural limitations that must remain attached to the classification."""

    HIDDEN_RUBRIC_CONDITIONAL_GAP = "hidden_rubric_acceptance_makes_differential_gap_conditional"


class ReplayedBoundaryKind(StrEnum):
    """Host-replayed causal boundary failures that independently create regressions."""

    FORBIDDEN_FLOW = "forbidden_flow"
    INTEGRITY_CHECK = "integrity_check"


class AcceptanceGrounding(FrozenStrictModel):
    """Pinned acceptance basis without interpreting the observed critic gap."""

    kind: AcceptanceGroundingKind
    basis_sha256: str

    @field_validator("basis_sha256")
    @classmethod
    def validate_basis_hash(cls, value: str) -> str:
        return validate_sha256(value)


class CriticStressMeasurement(LegacyContentAddressedModel):
    """Raw critic gains and null decomposition before any exploit classification."""

    schema_version: Literal["aecbench.adaptive-critic-stress-measurement.v1"] = (
        "aecbench.adaptive-critic-stress-measurement.v1"
    )
    measurement_id: NonEmptyStr
    critic: CriticRef
    gap: CriticGapDecomposition
    acceptance_grounding: AcceptanceGrounding


class CriticStressClassificationPolicy(LegacyContentAddressedModel):
    """Preregistered residual threshold and exact regime transition."""

    schema_version: Literal["aecbench.critic-stress-classification-policy.v1"] = (
        "aecbench.critic-stress-classification-policy.v1"
    )
    policy_id: NonEmptyStr
    current_critic: CriticRef
    next_critic: CriticRef
    minimum_null_adjusted_residual: NonNegativeFiniteFloat

    @model_validator(mode="after")
    def validate_regime_transition(self) -> Self:
        if self.current_critic == self.next_critic:
            raise ValueError("critic-stress policy requires a distinct next regime critic")
        if (
            self.current_critic.critic_id != self.next_critic.critic_id
            or self.current_critic.role is not self.next_critic.role
        ):
            raise ValueError("critic-stress policy must keep the stable critic ID and role")
        return self


class VRedChallengeEvidence(LegacyContentAddressedModel):
    """Host-observed red-team challenge that can modify only the next critic."""

    schema_version: Literal["aecbench.vred-challenge-evidence.v1"] = "aecbench.vred-challenge-evidence.v1"
    challenge_id: NonEmptyStr
    artifact_sha256: str
    origin: OriginStamp
    source_critic: CriticRef
    eligible_critic: CriticRef
    effect_scope: Literal["next_critic_only"] = "next_critic_only"
    current_promotion_basis_permitted: Literal[False] = False

    @field_validator(
        "artifact_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_red_team_provenance(self) -> Self:
        if self.origin.artifact_id != self.challenge_id or self.origin.artifact_sha256 != self.artifact_sha256:
            raise ValueError("Vred challenge does not match its host-observed origin")
        if self.origin.producer.kind is not AuthorityPrincipalKind.RED_TEAM:
            raise ValueError("Vred challenge requires red-team producer provenance")
        if TaintLabel.RUNTIME_OBSERVED not in self.origin.taint_labels:
            raise ValueError("Vred challenge requires runtime-observed provenance")
        if self.source_critic == self.eligible_critic:
            raise ValueError("Vred challenge cannot affect its source regime critic")
        if (
            self.source_critic.critic_id != self.eligible_critic.critic_id
            or self.source_critic.role is not self.eligible_critic.role
        ):
            raise ValueError("Vred challenge must keep the stable critic ID and role")
        return self


class VerifiedCausalSeamEvidence(LegacyContentAddressedModel):
    """Host-verified replay linking one candidate action to one critic seam."""

    schema_version: Literal["aecbench.verified-causal-seam-evidence.v1"] = "aecbench.verified-causal-seam-evidence.v1"
    evidence_id: NonEmptyStr
    measurement_sha256: str
    challenge_artifact_sha256: str
    candidate_action_sha256: str
    causal_replay_sha256: str
    seam_kind: NonEmptyStr
    observed_by: AuthorityPrincipal

    @field_validator(
        "measurement_sha256",
        "challenge_artifact_sha256",
        "candidate_action_sha256",
        "causal_replay_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_host_observer(self) -> Self:
        _require_host_observer(self.observed_by)
        return self


class ReplayedBoundaryEvidence(LegacyContentAddressedModel):
    """Host-replayed forbidden flow or integrity failure bound to one measurement."""

    schema_version: Literal["aecbench.replayed-boundary-evidence.v1"] = "aecbench.replayed-boundary-evidence.v1"
    evidence_id: NonEmptyStr
    kind: ReplayedBoundaryKind
    measurement_sha256: str
    replay_evidence_sha256: str
    observed_by: AuthorityPrincipal

    @field_validator("measurement_sha256", "replay_evidence_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_host_observer(self) -> Self:
        _require_host_observer(self.observed_by)
        return self


class CriticStressFinding(LegacyContentAddressedModel):
    """Causal interpretation derived separately from the raw gap measurement."""

    schema_version: Literal["aecbench.critic-stress-finding.v1"] = "aecbench.critic-stress-finding.v1"
    kind: CriticStressFindingKind
    measurement_sha256: str
    evidence_sha256s: tuple[str, ...]
    regression_case_eligible: bool
    detail: NonEmptyStr

    @field_validator("measurement_sha256")
    @classmethod
    def validate_measurement_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("evidence_sha256s")
    @classmethod
    def canonicalize_evidence_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("critic-stress finding evidence references must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_regression_eligibility(self) -> Self:
        eligible_kinds = {
            CriticStressFindingKind.DIFFERENTIAL_SEAM,
            CriticStressFindingKind.COMMON_MODE_SHARED_CRITIC_BREACH,
            CriticStressFindingKind.INTEGRITY_BREACH,
        }
        if self.regression_case_eligible is not (self.kind in eligible_kinds):
            raise ValueError("critic-stress regression eligibility must follow grounded finding kind")
        if self.regression_case_eligible and not self.evidence_sha256s:
            raise ValueError("critic-stress regression finding requires causal evidence")
        return self


class CriticRegressionCase(LegacyContentAddressedModel):
    """Immutable grounded case available only to the next regime critic."""

    schema_version: Literal["aecbench.critic-regression-case.v1"] = "aecbench.critic-regression-case.v1"
    case_id: NonEmptyStr
    finding_sha256: str
    measurement_sha256: str
    source_critic: CriticRef
    target_critic: CriticRef
    evidence_sha256s: tuple[str, ...]
    effect_scope: Literal["next_critic_only"] = "next_critic_only"
    current_promotion_basis_permitted: Literal[False] = False

    @field_validator(
        "finding_sha256",
        "measurement_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("evidence_sha256s")
    @classmethod
    def canonicalize_evidence_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if not value:
            raise ValueError("critic regression case requires grounded evidence")
        if len(value) != len(set(value)):
            raise ValueError("critic regression evidence references must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_regime_scope(self) -> Self:
        if self.source_critic == self.target_critic:
            raise ValueError("critic regression case cannot affect its source regime critic")
        if (
            self.source_critic.critic_id != self.target_critic.critic_id
            or self.source_critic.role is not self.target_critic.role
        ):
            raise ValueError("critic regression case must keep the stable critic ID and role")
        return self


class CriticStressReport(LegacyContentAddressedModel):
    """Provider-free causal classification and next-regime regression output."""

    schema_version: Literal["aecbench.adaptive-critic-stress-report.v1"] = "aecbench.adaptive-critic-stress-report.v1"
    policy: CriticStressClassificationPolicy
    measurement: CriticStressMeasurement
    causal_seam_evidence: tuple[VerifiedCausalSeamEvidence, ...] = ()
    replayed_boundary_evidence: tuple[ReplayedBoundaryEvidence, ...] = ()
    vred_challenges: tuple[VRedChallengeEvidence, ...] = ()
    finding: CriticStressFinding
    regression_case: CriticRegressionCase | None = None
    limitations: tuple[CriticStressLimitation, ...] = ()
    current_promotion_basis_sha256s: tuple[str, ...] = ()
    provider_calls: Literal[0] = 0
    provider_cost_usd: NonNegativeFiniteFloat = 0.0

    @field_validator(
        "causal_seam_evidence",
        "replayed_boundary_evidence",
        "vred_challenges",
    )
    @classmethod
    def canonicalize_evidence_models(
        cls,
        value: tuple[
            VerifiedCausalSeamEvidence | ReplayedBoundaryEvidence | VRedChallengeEvidence,
            ...,
        ],
    ) -> tuple[
        VerifiedCausalSeamEvidence | ReplayedBoundaryEvidence | VRedChallengeEvidence,
        ...,
    ]:
        identities = tuple(item.content_sha256 for item in value)
        if len(identities) != len(set(identities)):
            raise ValueError("critic-stress evidence models must be unique")
        return tuple(sorted(value, key=lambda item: item.content_sha256))

    @field_validator(
        "current_promotion_basis_sha256s",
    )
    @classmethod
    def canonicalize_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("critic-stress artifact references must be unique")
        return tuple(sorted(value))

    @field_validator("limitations")
    @classmethod
    def canonicalize_limitations(
        cls,
        value: tuple[CriticStressLimitation, ...],
    ) -> tuple[CriticStressLimitation, ...]:
        if len(value) != len(set(value)):
            raise ValueError("critic-stress limitations must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @model_validator(mode="after")
    def validate_causal_report(self) -> Self:
        _validate_measurement_bindings(self)
        _validate_challenge_scope(self)
        _validate_limitations(self)
        _validate_classification(self)
        return self


def _validate_measurement_bindings(report: CriticStressReport) -> None:
    if report.measurement.critic != report.policy.current_critic:
        raise ValueError("critic-stress measurement does not bind the current regime critic")
    if any(item.measurement_sha256 != report.measurement.content_sha256 for item in report.causal_seam_evidence) or any(
        item.measurement_sha256 != report.measurement.content_sha256 for item in report.replayed_boundary_evidence
    ):
        raise ValueError("critic-stress evidence does not bind the raw measurement")
    if report.provider_cost_usd != 0.0:
        raise ValueError("critic-stress reduction is provider-free")


def _validate_challenge_scope(report: CriticStressReport) -> None:
    challenge_artifacts = {challenge.artifact_sha256 for challenge in report.vred_challenges}
    if any(evidence.challenge_artifact_sha256 not in challenge_artifacts for evidence in report.causal_seam_evidence):
        raise ValueError("causal seam evidence requires a provenance-bound Vred challenge")
    if any(
        challenge.source_critic != report.policy.current_critic
        or challenge.eligible_critic != report.policy.next_critic
        for challenge in report.vred_challenges
    ):
        raise ValueError("Vred challenges can affect only the next regime critic")
    forbidden_current_basis = {
        digest
        for challenge in report.vred_challenges
        for digest in (
            challenge.artifact_sha256,
            challenge.content_sha256,
            challenge.origin.content_sha256,
        )
    }
    if report.regression_case is not None:
        forbidden_current_basis.add(report.regression_case.content_sha256)
    if forbidden_current_basis.intersection(report.current_promotion_basis_sha256s):
        raise ValueError("Vred challenge evidence is forbidden as current promotion basis")


def _validate_limitations(report: CriticStressReport) -> None:
    expected_limitations = (
        (CriticStressLimitation.HIDDEN_RUBRIC_CONDITIONAL_GAP,)
        if report.measurement.acceptance_grounding.kind is AcceptanceGroundingKind.HIDDEN_RUBRIC
        else ()
    )
    if report.limitations != expected_limitations:
        raise ValueError("critic-stress limitations do not match acceptance grounding")


def _validate_classification(report: CriticStressReport) -> None:
    from .reducer import derive_classification

    expected_finding, expected_regression = derive_classification(
        policy=report.policy,
        measurement=report.measurement,
        causal_seam_evidence=report.causal_seam_evidence,
        replayed_boundary_evidence=report.replayed_boundary_evidence,
    )
    if report.finding != expected_finding:
        raise ValueError("critic-stress finding does not match causal classification")
    if report.regression_case != expected_regression:
        raise ValueError("critic-stress regression case does not match grounded finding")


def _require_host_observer(principal: AuthorityPrincipal) -> None:
    if principal.kind not in {
        AuthorityPrincipalKind.HOST_RUNTIME,
        AuthorityPrincipalKind.HOST_POLICY,
    }:
        raise ValueError("causal critic-stress evidence requires a host observer")
