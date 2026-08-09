# ABOUTME: Declares narrow injected ports used by the phase-neutral governed-attempt engine.
# ABOUTME: Separates durable budget, monitor, backend, and import behavior from orchestration.

from __future__ import annotations

from typing import Protocol

from .contracts import (
    GovernedAttemptBackendReceipt,
    GovernedAttemptBudgetClosure,
    GovernedAttemptBudgetReservation,
    GovernedAttemptDispatchIntent,
    GovernedAttemptImportReceipt,
    GovernedAttemptMonitorClosure,
    GovernedAttemptMonitorPermit,
    GovernedAttemptPreflight,
)


class GovernedAttemptBudgetPort(Protocol):
    """Reserve capacity before effects and close exact terminal usage."""

    def reserve(
        self,
        preflight: GovernedAttemptPreflight,
    ) -> GovernedAttemptBudgetReservation: ...

    def close(
        self,
        *,
        reservation: GovernedAttemptBudgetReservation,
        dispatch_receipt: GovernedAttemptBackendReceipt,
        import_receipt: GovernedAttemptImportReceipt,
    ) -> GovernedAttemptBudgetClosure: ...


class GovernedAttemptMonitorPort(Protocol):
    """Issue a standing permit and close monitor evidence after import."""

    def authorize(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        reservation: GovernedAttemptBudgetReservation,
    ) -> GovernedAttemptMonitorPermit: ...

    def close(
        self,
        *,
        permit: GovernedAttemptMonitorPermit,
        dispatch_receipt: GovernedAttemptBackendReceipt,
        import_receipt: GovernedAttemptImportReceipt,
        budget_closure: GovernedAttemptBudgetClosure,
    ) -> GovernedAttemptMonitorClosure: ...


class GovernedAttemptBackendPort(Protocol):
    """Dispatch exactly once or reconcile an already durable dispatch intent."""

    def dispatch(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> GovernedAttemptBackendReceipt: ...

    def reconcile(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> GovernedAttemptBackendReceipt | None: ...


class GovernedAttemptImportExtension(Protocol):
    """Produce typed import evidence without owning backend dispatch."""

    def import_result(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        dispatch_receipt: GovernedAttemptBackendReceipt,
    ) -> GovernedAttemptImportReceipt: ...
