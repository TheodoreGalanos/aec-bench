# ABOUTME: Defines explicit terminal variants and retirement evidence for evaluation generations.
# ABOUTME: Replaces phase-specific nullable state bags with phase-neutral content-addressed joins.

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.evaluation_generation.cohort import (
    EvaluationCohortRetirement,
)
from aec_bench.contracts.evaluation_plane import CriticRole
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr


class EvaluationGenerationEvidenceRole(StrEnum):
    """Stable role of one exact artifact in the generation lifecycle."""

    SOURCE_TERMINAL = "source_terminal"
    BATCH_EXECUTION = "batch_execution"
    COHORT_RETIREMENT = "cohort_retirement"
    CRITIC_RETIREMENT = "critic_retirement"
    ACCEPTANCE_MANIFEST_REVEAL = "acceptance_manifest_reveal"


class EvaluationGenerationEvidenceRef(FrozenStrictModel):
    """Typed reference to one immutable lifecycle artifact."""

    artifact_id: NonEmptyStr
    role: EvaluationGenerationEvidenceRole
    schema_version: NonEmptyStr
    content_sha256: str

    @field_validator("content_sha256")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        return validate_sha256(value)


class _EvaluationGenerationClosureBase(ContentAddressedModel):
    """Fields shared by every explicit generation-terminal variant."""

    execution_id: NonEmptyStr
    prepared_generation_sha256: str
    source_terminal: EvaluationGenerationEvidenceRef
    completed_at: datetime

    @field_validator("prepared_generation_sha256")
    @classmethod
    def validate_prepared_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "evaluation-generation terminal timestamp must be timezone-aware",
            )
        return value

    @model_validator(mode="after")
    def validate_source_terminal_role(self) -> Self:
        if self.source_terminal.role is not EvaluationGenerationEvidenceRole.SOURCE_TERMINAL:
            raise ValueError(
                "evaluation-generation closure requires source-terminal evidence",
            )
        return self


class ProposalGenerationClosure(_EvaluationGenerationClosureBase):
    """Provider-free terminal before a complete candidate batch exists."""

    schema_version: Literal["aecbench.proposal-generation-closure.v2"] = "aecbench.proposal-generation-closure.v2"
    closure_kind: Literal["proposal_generation"] = "proposal_generation"
    status: Literal["failed", "incomplete"]
    proposal_result_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator("proposal_result_sha256s")
    @classmethod
    def validate_proposal_results(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_unique_hashes(
            value,
            label="proposal-generation results",
        )


class CandidateBatchRejectionClosure(_EvaluationGenerationClosureBase):
    """Provider-free terminal for a realized batch rejected before dispatch."""

    schema_version: Literal["aecbench.candidate-batch-rejection-closure.v2"] = (
        "aecbench.candidate-batch-rejection-closure.v2"
    )
    closure_kind: Literal["batch_rejection"] = "batch_rejection"
    batch_plan_sha256: str
    rejected_assignment_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator("batch_plan_sha256")
    @classmethod
    def validate_batch_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("rejected_assignment_sha256s")
    @classmethod
    def validate_rejected_assignments(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                _validate_unique_hashes(
                    value,
                    label="rejected assignments",
                ),
            )
        )


class GovernedBatchAssignmentEvidence(FrozenStrictModel):
    """Exact assignment-to-terminal join reported by one execution plane."""

    assignment_sha256: str
    terminal_sha256: str

    @field_validator(
        "assignment_sha256",
        "terminal_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class GovernedBatchTerminalEvidence(ContentAddressedModel):
    """Phase-neutral execution projection for one completed batch."""

    schema_version: Literal["aecbench.governed-batch-terminal-evidence.v2"] = (
        "aecbench.governed-batch-terminal-evidence.v2"
    )
    status: Literal["completed"] = "completed"
    execution_id: NonEmptyStr
    batch_plan_sha256: str
    source_terminal: EvaluationGenerationEvidenceRef
    execution_evidence: EvaluationGenerationEvidenceRef
    execution_assignments: tuple[GovernedBatchAssignmentEvidence, ...]

    @field_validator("batch_plan_sha256")
    @classmethod
    def validate_batch_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "execution_assignments",
    )
    @classmethod
    def validate_assignment_evidence(
        cls,
        value: tuple[GovernedBatchAssignmentEvidence, ...],
    ) -> tuple[GovernedBatchAssignmentEvidence, ...]:
        assignment_ids = tuple(item.assignment_sha256 for item in value)
        terminal_ids = tuple(item.terminal_sha256 for item in value)
        if len(assignment_ids) != len(set(assignment_ids)) or len(terminal_ids) != len(set(terminal_ids)):
            raise ValueError(
                "governed batch terminal assignment evidence must be unique",
            )
        return value

    @model_validator(mode="after")
    def validate_evidence_roles(self) -> Self:
        expected_roles = (
            (
                self.source_terminal.role,
                EvaluationGenerationEvidenceRole.SOURCE_TERMINAL,
            ),
            (
                self.execution_evidence.role,
                EvaluationGenerationEvidenceRole.BATCH_EXECUTION,
            ),
        )
        if any(observed is not expected for observed, expected in expected_roles):
            raise ValueError(
                "governed batch terminal evidence roles are invalid",
            )
        return self


class GovernedBatchExecutionClosure(_EvaluationGenerationClosureBase):
    """Terminal for a governed candidate batch with exact execution evidence."""

    schema_version: Literal["aecbench.governed-batch-execution-closure.v2"] = (
        "aecbench.governed-batch-execution-closure.v2"
    )
    closure_kind: Literal["batch_execution"] = "batch_execution"
    status: Literal["completed", "incomplete"]
    batch_plan_sha256: str
    ordered_assignment_terminal_sha256s: tuple[str, ...]
    execution_evidence: EvaluationGenerationEvidenceRef

    @field_validator("batch_plan_sha256")
    @classmethod
    def validate_batch_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("ordered_assignment_terminal_sha256s")
    @classmethod
    def validate_assignment_terminals(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_unique_hashes(
            value,
            label="assignment terminals",
        )

    @model_validator(mode="after")
    def validate_execution_role(self) -> Self:
        if self.execution_evidence.role is not EvaluationGenerationEvidenceRole.BATCH_EXECUTION:
            raise ValueError(
                "governed batch closure requires batch-execution evidence",
            )
        return self


EvaluationGenerationClosure = Annotated[
    ProposalGenerationClosure | CandidateBatchRejectionClosure | GovernedBatchExecutionClosure,
    Field(discriminator="closure_kind"),
]


class EvaluationCriticRetirementRef(FrozenStrictModel):
    """Exact retirement evidence for one critic generation."""

    role: CriticRole
    critic_generation_sha256: str
    retirement_authority_event_sha256: str
    evidence: EvaluationGenerationEvidenceRef

    @field_validator(
        "critic_generation_sha256",
        "retirement_authority_event_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_evidence_role(self) -> Self:
        if self.evidence.role is not EvaluationGenerationEvidenceRole.CRITIC_RETIREMENT:
            raise ValueError(
                "critic retirement requires critic-retirement evidence",
            )
        return self


class EvaluationGenerationRetirementClosure(ContentAddressedModel):
    """Final retirement and acceptance-reveal join for one generation closure."""

    schema_version: Literal["aecbench.evaluation-generation-retirement-closure.v2"] = (
        "aecbench.evaluation-generation-retirement-closure.v2"
    )
    retirement_id: NonEmptyStr
    generation_closure_sha256: str
    cohort_retirement: EvaluationCohortRetirement
    cohort_retirement_evidence: EvaluationGenerationEvidenceRef
    required_critic_roles: tuple[CriticRole, ...] = Field(min_length=1)
    critic_retirements: tuple[EvaluationCriticRetirementRef, ...] = Field(
        min_length=1,
    )
    acceptance_manifest_reveal: EvaluationGenerationEvidenceRef

    @field_validator("generation_closure_sha256")
    @classmethod
    def validate_closure_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("required_critic_roles")
    @classmethod
    def canonicalize_required_roles(
        cls,
        value: tuple[CriticRole, ...],
    ) -> tuple[CriticRole, ...]:
        if len(value) != len(set(value)):
            raise ValueError(
                "evaluation-generation required critic roles must be unique",
            )
        return tuple(sorted(value, key=_critic_role_order))

    @field_validator("critic_retirements")
    @classmethod
    def canonicalize_critic_retirements(
        cls,
        value: tuple[EvaluationCriticRetirementRef, ...],
    ) -> tuple[EvaluationCriticRetirementRef, ...]:
        roles = tuple(item.role for item in value)
        if len(roles) != len(set(roles)):
            raise ValueError(
                "evaluation-generation critic retirements must have unique roles",
            )
        return tuple(sorted(value, key=lambda item: _critic_role_order(item.role)))

    @model_validator(mode="after")
    def validate_retirement_join(self) -> Self:
        if self.cohort_retirement_evidence.role is not EvaluationGenerationEvidenceRole.COHORT_RETIREMENT:
            raise ValueError(
                "evaluation-generation retirement requires cohort-retirement evidence",
            )
        if self.acceptance_manifest_reveal.role is not (EvaluationGenerationEvidenceRole.ACCEPTANCE_MANIFEST_REVEAL):
            raise ValueError(
                "evaluation-generation retirement requires acceptance-manifest reveal evidence",
            )
        observed_roles = tuple(item.role for item in self.critic_retirements)
        if observed_roles != self.required_critic_roles:
            raise ValueError(
                "evaluation-generation retirement critic roles differ from the required critic roles",
            )
        if CriticRole.ACCEPTANCE not in observed_roles:
            raise ValueError(
                "evaluation-generation retirement requires an acceptance critic",
            )
        return self


def _validate_unique_hashes(
    value: tuple[str, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    for digest in value:
        validate_sha256(digest)
    if len(value) != len(set(value)):
        raise ValueError(f"evaluation-generation {label} must be unique")
    return value


def _critic_role_order(role: CriticRole) -> int:
    return {
        CriticRole.DEVELOPMENT: 0,
        CriticRole.ACCEPTANCE: 1,
        CriticRole.RED_TEAM: 2,
    }[role]
