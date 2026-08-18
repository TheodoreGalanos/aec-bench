# ABOUTME: Defines immutable phase-neutral records and errors for one governed attempt.
# ABOUTME: Keeps lifecycle identities, usage, evidence, and terminal joins schema-stable.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    field_validator,
    model_validator,
)

from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class GovernedAttemptError(RuntimeError):
    """Base error for a phase-neutral governed attempt."""


class GovernedAttemptConfinementError(GovernedAttemptError):
    """Raised when attempt evidence is not confined to its repository."""


class GovernedAttemptCollisionError(GovernedAttemptError):
    """Raised when one logical attempt stage is rebound to different content."""


class GovernedAttemptIntegrityError(GovernedAttemptError):
    """Raised when an adapter result or durable stage cannot replay exactly."""


class GovernedAttemptIncompleteError(GovernedAttemptError):
    """Raised when replay is requested before every terminal stage exists."""


class GovernedAttemptExtensionError(GovernedAttemptError):
    """Raised when a budget, monitor, or import extension fails."""


class GovernedAttemptDispatchUncertainError(GovernedAttemptError):
    """Raised after dispatch when no durable backend receipt was returned."""


class GovernedAttemptReconciliationRequiredError(GovernedAttemptError):
    """Raised when a durable dispatch intent has no reconcilable receipt."""


class GovernedAttemptUsage(FrozenStrictModel):
    """Exact provider-neutral usage retained across receipt and closure joins."""

    model_calls: NonNegativeInt = 0
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    cache_read_tokens: NonNegativeInt = 0
    cache_write_tokens: NonNegativeInt = 0
    estimated_cost_usd: NonNegativeFloat = 0.0
    wall_time_seconds: NonNegativeFloat = 0.0


class GovernedAttemptUsageLimits(FrozenStrictModel):
    """Pre-effect ceilings without pretending optional token or cost caps exist."""

    model_calls: NonNegativeInt
    total_tokens: NonNegativeInt | None = None
    estimated_cost_usd: NonNegativeFloat | None = None
    wall_time_seconds: NonNegativeFloat


class GovernedAttemptPreflight(FrozenStrictModel):
    """Frozen input and effect ceilings validated before budget reservation."""

    schema_version: Literal["aecbench.governed-attempt-preflight.v1"] = "aecbench.governed-attempt-preflight.v1"
    attempt_id: NonEmptyStr
    workload_sha256: str
    dispatch_payload_sha256: str
    maximum_usage: GovernedAttemptUsageLimits
    required_effect_evidence_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator("workload_sha256", "dispatch_payload_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("required_effect_evidence_sha256s")
    @classmethod
    def validate_evidence_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_sorted_unique_hashes(
            value,
            label="required effect evidence",
        )


class GovernedAttemptBudgetReservation(FrozenStrictModel):
    """Budget-port evidence selected before any backend effect is permitted."""

    schema_version: Literal["aecbench.governed-attempt-budget-reservation.v1"] = (
        "aecbench.governed-attempt-budget-reservation.v1"
    )
    attempt_id: NonEmptyStr
    reservation_id: NonEmptyStr
    maximum_usage: GovernedAttemptUsageLimits


class GovernedAttemptMonitorPermit(FrozenStrictModel):
    """Standing-monitor permit bound to the exact preflight and reservation."""

    schema_version: Literal["aecbench.governed-attempt-monitor-permit.v1"] = (
        "aecbench.governed-attempt-monitor-permit.v1"
    )
    attempt_id: NonEmptyStr
    reservation_id: NonEmptyStr
    permit_id: NonEmptyStr


class GovernedAttemptDispatchIntent(FrozenStrictModel):
    """Host-owned durable intent that must exist before backend dispatch."""

    schema_version: Literal["aecbench.governed-attempt-dispatch-intent.v1"] = (
        "aecbench.governed-attempt-dispatch-intent.v1"
    )
    attempt_id: NonEmptyStr
    reservation_id: NonEmptyStr
    permit_id: NonEmptyStr
    dispatch_payload_sha256: str
    dispatch_key_sha256: str

    @field_validator(
        "dispatch_payload_sha256",
        "dispatch_key_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class GovernedAttemptBackendReceipt(FrozenStrictModel):
    """Typed backend receipt retained before import or terminal accounting."""

    schema_version: Literal["aecbench.governed-attempt-backend-receipt.v1"] = (
        "aecbench.governed-attempt-backend-receipt.v1"
    )
    attempt_id: NonEmptyStr
    dispatch_key_sha256: str
    backend_receipt_id: NonEmptyStr
    observed_usage: GovernedAttemptUsage
    effect_evidence_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator("dispatch_key_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("effect_evidence_sha256s")
    @classmethod
    def validate_evidence_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_sorted_unique_hashes(
            value,
            label="backend effect evidence",
        )


class GovernedAttemptImportReceipt(FrozenStrictModel):
    """Typed import extension output bound to source usage and effect evidence."""

    schema_version: Literal["aecbench.governed-attempt-import-receipt.v1"] = (
        "aecbench.governed-attempt-import-receipt.v1"
    )
    attempt_id: NonEmptyStr
    backend_receipt_id: NonEmptyStr
    import_id: NonEmptyStr
    observed_usage: GovernedAttemptUsage
    source_effect_evidence_sha256s: tuple[str, ...] = Field(min_length=1)
    imported_evidence_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "source_effect_evidence_sha256s",
        "imported_evidence_sha256s",
    )
    @classmethod
    def validate_evidence_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_sorted_unique_hashes(
            value,
            label="import evidence",
        )


class GovernedAttemptBudgetClosure(FrozenStrictModel):
    """Budget-port terminal accounting over the exact imported backend effect."""

    schema_version: Literal["aecbench.governed-attempt-budget-closure.v1"] = (
        "aecbench.governed-attempt-budget-closure.v1"
    )
    attempt_id: NonEmptyStr
    reservation_id: NonEmptyStr
    backend_receipt_id: NonEmptyStr
    import_id: NonEmptyStr
    observed_usage: GovernedAttemptUsage
    effect_evidence_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator("effect_evidence_sha256s")
    @classmethod
    def validate_evidence_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_sorted_unique_hashes(
            value,
            label="budget closure effect evidence",
        )


class GovernedAttemptMonitorClosure(FrozenStrictModel):
    """Standing-monitor terminal closure over imported and accounted evidence."""

    schema_version: Literal["aecbench.governed-attempt-monitor-closure.v1"] = (
        "aecbench.governed-attempt-monitor-closure.v1"
    )
    attempt_id: NonEmptyStr
    permit_id: NonEmptyStr
    backend_receipt_id: NonEmptyStr
    import_id: NonEmptyStr
    observed_usage: GovernedAttemptUsage
    effect_evidence_sha256s: tuple[str, ...] = Field(min_length=1)
    closure_permitted: Literal[True] = True

    @field_validator("effect_evidence_sha256s")
    @classmethod
    def validate_evidence_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_sorted_unique_hashes(
            value,
            label="monitor closure effect evidence",
        )


class GovernedAttemptTerminal(FrozenStrictModel):
    """Final immutable join over every stage in one governed attempt."""

    schema_version: Literal["aecbench.governed-attempt-terminal.v1"] = "aecbench.governed-attempt-terminal.v1"
    attempt_id: NonEmptyStr
    reservation_id: NonEmptyStr
    permit_id: NonEmptyStr
    backend_receipt_id: NonEmptyStr
    import_id: NonEmptyStr
    effect_evidence_sha256s: tuple[str, ...] = Field(min_length=1)
    imported_evidence_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "effect_evidence_sha256s",
        "imported_evidence_sha256s",
    )
    @classmethod
    def validate_evidence_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_sorted_unique_hashes(
            value,
            label="terminal evidence",
        )


class GovernedAttemptReplay(FrozenStrictModel):
    """Complete typed replay of one terminal governed attempt."""

    preflight: GovernedAttemptPreflight
    reservation: GovernedAttemptBudgetReservation
    monitor_permit: GovernedAttemptMonitorPermit
    dispatch_intent: GovernedAttemptDispatchIntent
    dispatch_receipt: GovernedAttemptBackendReceipt
    import_receipt: GovernedAttemptImportReceipt
    budget_closure: GovernedAttemptBudgetClosure
    monitor_closure: GovernedAttemptMonitorClosure
    terminal: GovernedAttemptTerminal

    @model_validator(mode="after")
    def validate_replay(self) -> Self:
        from .chain_validation import complete_chain_error

        error = complete_chain_error(
            preflight=self.preflight,
            reservation=self.reservation,
            permit=self.monitor_permit,
            intent=self.dispatch_intent,
            receipt=self.dispatch_receipt,
            imported=self.import_receipt,
            budget_closure=self.budget_closure,
            monitor_closure=self.monitor_closure,
            terminal=self.terminal,
        )
        if error is not None:
            raise ValueError(error)
        return self


class GovernedAttemptStage(StrEnum):
    """Closed persisted stages in lifecycle order."""

    PREFLIGHT = "preflight"
    BUDGET_RESERVATION = "budget_reservation"
    MONITOR_PERMIT = "monitor_permit"
    DISPATCH_INTENT = "dispatch_intent"
    BACKEND_RECEIPT = "backend_receipt"
    IMPORT_RECEIPT = "import_receipt"
    BUDGET_CLOSURE = "budget_closure"
    MONITOR_CLOSURE = "monitor_closure"
    TERMINAL = "terminal"


def _validate_sorted_unique_hashes(
    value: tuple[str, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    for digest in value:
        validate_sha256(digest)
    if value != tuple(sorted(set(value))):
        raise ValueError(f"{label} hashes must be sorted and unique")
    return value
