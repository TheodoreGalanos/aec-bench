# ABOUTME: Defines cardinality-neutral governed batch identities and terminal evidence.
# ABOUTME: Validates deterministic assignment prefixes and exact effect-monitor joins.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr


class GovernedBatchExecutionError(RuntimeError):
    """Base error for one phase-neutral governed batch lifecycle."""


class GovernedBatchExecutionIntegrityError(GovernedBatchExecutionError):
    """Raised when authority, effect, or replay evidence is inconsistent."""


class GovernedBatchExecutionConfinementError(GovernedBatchExecutionError):
    """Raised when durable batch evidence escapes its declared root."""


class GovernedBatchExecutionCollisionError(GovernedBatchExecutionError):
    """Raised when one batch identity is rebound to different immutable content."""


class GovernedBatchStatus(StrEnum):
    """Terminal state of one governed execution batch."""

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"


class GovernedBatchRetryPolicy(StrEnum):
    """Effect retry policy selected before batch execution."""

    DISABLED = "disabled"


class GovernedBatchAssignment(ContentAddressedModel):
    """Ordered assignment identity required before any batch effect."""

    schema_version: Literal["aecbench.governed-batch-assignment.v1"] = "aecbench.governed-batch-assignment.v1"
    assignment_sha256: str
    dispatch_sha256: str
    authorization_chain_sha256: str

    @field_validator(
        "assignment_sha256",
        "dispatch_sha256",
        "authorization_chain_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class GovernedBatchDesign(ContentAddressedModel):
    """Input-supplied batch order and execution policy with no fixed cardinality."""

    schema_version: Literal["aecbench.governed-batch-design.v1"] = "aecbench.governed-batch-design.v1"
    batch_id: NonEmptyStr
    source_batch_sha256: str
    assignments: tuple[GovernedBatchAssignment, ...] = Field(min_length=1)
    max_concurrency: PositiveInt
    retry_policy: GovernedBatchRetryPolicy = GovernedBatchRetryPolicy.DISABLED

    @field_validator("source_batch_sha256")
    @classmethod
    def validate_source_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("assignments")
    @classmethod
    def validate_assignment_identities(
        cls,
        value: tuple[GovernedBatchAssignment, ...],
    ) -> tuple[GovernedBatchAssignment, ...]:
        identity_groups = (
            tuple(item.assignment_sha256 for item in value),
            tuple(item.dispatch_sha256 for item in value),
            tuple(item.authorization_chain_sha256 for item in value),
        )
        if any(len(identities) != len(set(identities)) for identities in identity_groups):
            raise ValueError(
                "governed batch assignment identities must be unique",
            )
        return value

    @property
    def assignment_count(self) -> int:
        """Return cardinality derived exclusively from the supplied assignments."""

        return len(self.assignments)

    @property
    def ordered_assignment_sha256s(self) -> tuple[str, ...]:
        """Return the immutable assignment order supplied by this design."""

        return tuple(assignment.assignment_sha256 for assignment in self.assignments)

    @model_validator(mode="after")
    def validate_execution_policy(self) -> Self:
        if self.max_concurrency > self.assignment_count:
            raise ValueError(
                "governed batch concurrency cannot exceed assignment count",
            )
        return self


class GovernedBatchAssignmentTerminal(ContentAddressedModel):
    """Normalized exact terminal claim for one governed assignment attempt."""

    schema_version: Literal["aecbench.governed-batch-assignment-terminal.v1"] = (
        "aecbench.governed-batch-assignment-terminal.v1"
    )
    design_sha256: str
    ordinal: PositiveInt
    assignment_sha256: str
    dispatch_sha256: str
    authorization_chain_sha256: str
    effect_authorization_sha256: str
    attempt_terminal_sha256: str
    terminal_variant: NonEmptyStr
    monitor_evidence_sha256s: tuple[str, ...] = Field(min_length=1)
    effect_evidence_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "design_sha256",
        "assignment_sha256",
        "dispatch_sha256",
        "authorization_chain_sha256",
        "effect_authorization_sha256",
        "attempt_terminal_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "monitor_evidence_sha256s",
        "effect_evidence_sha256s",
    )
    @classmethod
    def canonicalize_evidence_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError(
                "governed assignment evidence identities must be unique",
            )
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_effect_evidence_join(self) -> Self:
        effect_evidence = set(self.effect_evidence_sha256s)
        if self.attempt_terminal_sha256 not in effect_evidence or not set(self.monitor_evidence_sha256s).issubset(
            effect_evidence,
        ):
            raise ValueError(
                "governed assignment effect evidence omits its attempt or monitor closure",
            )
        return self


class GovernedBatchTerminal(ContentAddressedModel):
    """Normalized terminal prefix for a dynamically sized governed batch."""

    schema_version: Literal["aecbench.governed-batch-terminal.v1"] = "aecbench.governed-batch-terminal.v1"
    design_sha256: str
    status: GovernedBatchStatus
    assignment_terminals: tuple[GovernedBatchAssignmentTerminal, ...]
    incomplete_assignment_sha256s: tuple[str, ...]
    monitor_closure_sha256: str
    observed_peak_concurrency: NonNegativeInt
    incomplete_reason: NonEmptyStr | None = None

    @field_validator("design_sha256", "monitor_closure_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("incomplete_assignment_sha256s")
    @classmethod
    def validate_incomplete_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError(
                "governed batch incomplete assignments must be unique",
            )
        return value

    @model_validator(mode="after")
    def validate_terminal_variant(self) -> Self:
        expected_ordinals = tuple(
            range(1, len(self.assignment_terminals) + 1),
        )
        if tuple(terminal.ordinal for terminal in self.assignment_terminals) != expected_ordinals or any(
            terminal.design_sha256 != self.design_sha256 for terminal in self.assignment_terminals
        ):
            raise ValueError(
                "governed batch terminal does not contain one exact result prefix",
            )
        if self.status is GovernedBatchStatus.COMPLETED:
            if self.incomplete_assignment_sha256s or self.incomplete_reason is not None:
                raise ValueError(
                    "completed governed batch cannot retain incomplete state",
                )
        elif self.incomplete_reason is None:
            raise ValueError(
                "incomplete governed batch requires an explicit reason",
            )
        return self
