# ABOUTME: Contract models for evaluation output consumed by communication and feedback.
# ABOUTME: Defines validity, taxonomy, confidence, annotations, and the scored-result envelope.

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.validators import (
    NonEmptyStr,
    StrictModel,
    ensure_optional_non_empty_string,
)


class ErrorSource(StrEnum):
    MECHANICAL = "mechanical"
    HUMAN = "human"
    JUDGE = "judge"


class Judgment(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    DEFER = "defer"


class ValidityCheck(StrictModel):
    output_parseable: bool
    schema_valid: bool
    verifier_completed: bool
    errors: list[str] = Field(default_factory=list)


class ErrorTag(StrictModel):
    category: NonEmptyStr
    description: str | None = None
    source: ErrorSource


class ConfidenceMetadata(StrictModel):
    annotator_count: NonNegativeInt | None = None
    inter_rater_agreement: float | None = None
    confidence_interval: tuple[float, float] | None = None
    confidence_method: str | None = None

    @field_validator("inter_rater_agreement")
    @classmethod
    def validate_inter_rater_agreement(cls, value: float | None) -> float | None:
        if value is not None and not 0.0 <= value <= 1.0:
            msg = "inter_rater_agreement must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value

    @field_validator("confidence_interval")
    @classmethod
    def validate_confidence_interval(cls, value: tuple[float, float] | None) -> tuple[float, float] | None:
        if value is None:
            return None
        low, high = value
        if low > high:
            msg = "confidence_interval low bound must not exceed high bound"
            raise ValueError(msg)
        return value

    @field_validator("confidence_method")
    @classmethod
    def validate_confidence_method(cls, value: str | None) -> str | None:
        return ensure_optional_non_empty_string(value)


class Annotation(StrictModel):
    reviewer_id: NonEmptyStr
    reviewer_discipline: str | None = None
    timestamp: datetime
    judgment: Judgment
    categories: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("reviewer_discipline")
    @classmethod
    def validate_optional_discipline(cls, value: str | None) -> str | None:
        return ensure_optional_non_empty_string(value)


class StewardshipTerminalLiability(StrictModel):
    """Terminal liability vector for one bounded stewardship trajectory."""

    review_required_physical_state: bool
    active_restriction_count: NonNegativeInt
    overdue_calendar_seconds: NonNegativeInt
    overdue_affected_pump_runtime_seconds: NonNegativeInt
    breached_obligation_count: NonNegativeInt
    unresolved_verification_count: NonNegativeInt
    deferred_work_count: NonNegativeInt
    unavailable_pump_count: NonNegativeInt
    consumed_maintenance_resource_count: NonNegativeInt
    unresolved_evidence: bool


class StewardshipMetricVector(StrictModel):
    """Evaluation-owned diagnostic vector for one stewardship trajectory."""

    decision_time_invalid_count: NonNegativeInt
    physical_service_review_required: bool
    maintenance_intervention_count: NonNegativeInt
    obligation_breach_count: NonNegativeInt
    restriction_breach_count: NonNegativeInt
    evidence_integrity_gap_count: NonNegativeInt
    consumed_maintenance_resource_count: NonNegativeInt
    handover_count: NonNegativeInt
    handover_omission_count: NonNegativeInt
    terminal_liability: StewardshipTerminalLiability


class StewardshipIntegrityGates(StrictModel):
    """Fail-closed evaluation gates in the PRD-defined order."""

    artifact_and_replay_integrity: bool
    output_and_action_contract_validity: bool
    authority_and_execution_consistency: bool
    decision_time_validity: bool
    obligation_and_restriction_integrity: bool
    physical_and_service_outcomes_available: bool
    resource_stewardship_available: bool
    evidence_and_record_integrity: bool
    handover_continuity_integrity: bool
    terminal_stewardship_available: bool
    errors: tuple[NonEmptyStr, ...] = ()

    @property
    def passed(self) -> bool:
        """Return true only when every ordered gate passed."""

        return all(
            (
                self.artifact_and_replay_integrity,
                self.output_and_action_contract_validity,
                self.authority_and_execution_consistency,
                self.decision_time_validity,
                self.obligation_and_restriction_integrity,
                self.physical_and_service_outcomes_available,
                self.resource_stewardship_available,
                self.evidence_and_record_integrity,
                self.handover_continuity_integrity,
                self.terminal_stewardship_available,
            )
        )

    @model_validator(mode="after")
    def validate_errors(self) -> "StewardshipIntegrityGates":
        if self.passed and self.errors:
            raise ValueError("passing stewardship gates cannot contain errors")
        if not self.passed and not self.errors:
            raise ValueError("failed stewardship gates must contain errors")
        return self


class StewardshipEvaluationEvidence(StrictModel):
    """Exact durable identities used to compute one stewardship evaluation."""

    world_run_manifest_content_id: NonEmptyStr
    initial_state_id: NonEmptyStr
    terminal_state_id: NonEmptyStr
    replayed_transition_ids: tuple[NonEmptyStr, ...]
    imported_artifact_sha256: tuple[NonEmptyStr, ...] = ()

    @field_validator(
        "world_run_manifest_content_id",
        "initial_state_id",
        "terminal_state_id",
    )
    @classmethod
    def validate_content_id(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("stewardship content identity must be a SHA-256 value")
        return value

    @field_validator("replayed_transition_ids")
    @classmethod
    def validate_transition_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("replayed transition ids must be distinct")
        return value

    @field_validator("imported_artifact_sha256")
    @classmethod
    def validate_artifact_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("imported stewardship artifact hashes must be sorted and distinct")
        for item in value:
            if len(item) != 64 or any(character not in "0123456789abcdef" for character in item):
                raise ValueError("imported stewardship artifact hash must be a SHA-256 value")
        return value


class StewardshipEvaluation(StrictModel):
    """Authoritative stewardship evaluation attached to an EvaluationResult."""

    schema_version: NonEmptyStr
    valid: bool
    gates: StewardshipIntegrityGates
    metrics: StewardshipMetricVector
    evidence: StewardshipEvaluationEvidence

    @model_validator(mode="after")
    def validate_gate_result(self) -> "StewardshipEvaluation":
        if self.valid != self.gates.passed:
            raise ValueError("stewardship evaluation validity must match its integrity gates")
        return self


class EvaluationResult(StrictModel):
    reward: float
    validity: ValidityCheck
    breakdown: dict[str, Any] | None = None
    error_taxonomy: list[ErrorTag] | None = None
    confidence: ConfidenceMetadata | None = None
    annotations: list[Annotation] | None = None
    stewardship: StewardshipEvaluation | None = None

    @field_validator("reward")
    @classmethod
    def validate_reward(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "reward must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_output_validity_reward(self) -> "EvaluationResult":
        if (not self.validity.output_parseable or not self.validity.schema_valid) and self.reward > 0.0:
            msg = "invalid outputs must have reward 0.0"
            raise ValueError(msg)
        if self.stewardship is not None and not self.stewardship.valid and self.reward > 0.0:
            raise ValueError("stewardship integrity failures must have reward 0.0")
        return self
