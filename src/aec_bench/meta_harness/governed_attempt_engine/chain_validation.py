# ABOUTME: Validates causal joins across phase-neutral governed-attempt lifecycle records.
# ABOUTME: Builds the deterministic dispatch intent and reports the first replay mismatch.

from __future__ import annotations

from aec_bench.contracts.harness_kernel import canonical_content_sha256

from .contracts import (
    GovernedAttemptBackendReceipt,
    GovernedAttemptBudgetClosure,
    GovernedAttemptBudgetReservation,
    GovernedAttemptDispatchIntent,
    GovernedAttemptImportReceipt,
    GovernedAttemptMonitorClosure,
    GovernedAttemptMonitorPermit,
    GovernedAttemptPreflight,
    GovernedAttemptTerminal,
    GovernedAttemptUsage,
    GovernedAttemptUsageLimits,
)


def build_dispatch_intent(
    preflight: GovernedAttemptPreflight,
    reservation: GovernedAttemptBudgetReservation,
    permit: GovernedAttemptMonitorPermit,
) -> GovernedAttemptDispatchIntent:
    """Build the only dispatch intent valid for a permitted reservation."""

    dispatch_key_sha256 = canonical_content_sha256(
        {
            "attempt_id": preflight.attempt_id,
            "preflight_sha256": preflight.content_sha256,
            "dispatch_payload_sha256": preflight.dispatch_payload_sha256,
        }
    )
    return GovernedAttemptDispatchIntent(
        attempt_id=preflight.attempt_id,
        preflight_sha256=preflight.content_sha256,
        reservation_sha256=reservation.content_sha256,
        monitor_permit_sha256=permit.content_sha256,
        dispatch_payload_sha256=preflight.dispatch_payload_sha256,
        dispatch_key_sha256=dispatch_key_sha256,
    )


def reservation_error(
    preflight: GovernedAttemptPreflight,
    reservation: GovernedAttemptBudgetReservation,
) -> str | None:
    """Return a mismatch when a reservation is not the preflight's exact budget."""

    if (
        reservation.attempt_id != preflight.attempt_id
        or reservation.preflight_sha256 != preflight.content_sha256
        or reservation.maximum_usage != preflight.maximum_usage
    ):
        return "governed attempt budget reservation differs from preflight"
    return None


def permit_error(
    preflight: GovernedAttemptPreflight,
    reservation: GovernedAttemptBudgetReservation,
    permit: GovernedAttemptMonitorPermit,
) -> str | None:
    """Return a mismatch when a monitor permit is not bound to its reservation."""

    if (
        permit.attempt_id != preflight.attempt_id
        or permit.preflight_sha256 != preflight.content_sha256
        or permit.reservation_sha256 != reservation.content_sha256
    ):
        return "governed attempt monitor permit differs from its reservation"
    return None


def intent_error(
    preflight: GovernedAttemptPreflight,
    reservation: GovernedAttemptBudgetReservation,
    permit: GovernedAttemptMonitorPermit,
    intent: GovernedAttemptDispatchIntent,
) -> str | None:
    """Return a mismatch when a dispatch intent is not the deterministic join."""

    if intent != build_dispatch_intent(preflight, reservation, permit):
        return "governed attempt dispatch intent differs from its permitted effect"
    return None


def receipt_error(
    preflight: GovernedAttemptPreflight,
    intent: GovernedAttemptDispatchIntent,
    receipt: GovernedAttemptBackendReceipt,
) -> str | None:
    """Return the first identity, usage, or evidence mismatch in a backend receipt."""

    if (
        receipt.attempt_id != preflight.attempt_id
        or receipt.dispatch_intent_sha256 != intent.content_sha256
        or receipt.dispatch_key_sha256 != intent.dispatch_key_sha256
    ):
        return "governed attempt backend receipt differs from dispatch intent"
    usage_breach = usage_breach_label(
        observed=receipt.observed_usage,
        maximum=preflight.maximum_usage,
    )
    if usage_breach is not None:
        return f"governed attempt backend usage exceeds reserved {usage_breach}"
    if not set(preflight.required_effect_evidence_sha256s).issubset(
        receipt.effect_evidence_sha256s,
    ):
        return "governed attempt backend effect evidence is incomplete"
    return None


def import_error(
    preflight: GovernedAttemptPreflight,
    receipt: GovernedAttemptBackendReceipt,
    imported: GovernedAttemptImportReceipt,
) -> str | None:
    """Return a mismatch when import changes source usage or effect evidence."""

    if (
        imported.attempt_id != preflight.attempt_id
        or imported.dispatch_receipt_sha256 != receipt.content_sha256
        or imported.observed_usage != receipt.observed_usage
        or imported.source_effect_evidence_sha256s != receipt.effect_evidence_sha256s
    ):
        return "governed attempt import usage or effect evidence differs from backend receipt"
    return None


def budget_closure_error(
    reservation: GovernedAttemptBudgetReservation,
    receipt: GovernedAttemptBackendReceipt,
    imported: GovernedAttemptImportReceipt,
    closure: GovernedAttemptBudgetClosure,
) -> str | None:
    """Return a mismatch when terminal accounting changes effect evidence."""

    if (
        closure.attempt_id != reservation.attempt_id
        or closure.reservation_sha256 != reservation.content_sha256
        or closure.dispatch_receipt_sha256 != receipt.content_sha256
        or closure.import_receipt_sha256 != imported.content_sha256
        or closure.observed_usage != receipt.observed_usage
        or closure.effect_evidence_sha256s != receipt.effect_evidence_sha256s
    ):
        return "governed attempt budget closure differs from effect usage or evidence"
    return None


def monitor_closure_error(
    permit: GovernedAttemptMonitorPermit,
    receipt: GovernedAttemptBackendReceipt,
    imported: GovernedAttemptImportReceipt,
    budget_closure: GovernedAttemptBudgetClosure,
    closure: GovernedAttemptMonitorClosure,
) -> str | None:
    """Return a mismatch when monitor closure differs from the accounted effect."""

    if (
        closure.attempt_id != permit.attempt_id
        or closure.permit_sha256 != permit.content_sha256
        or closure.dispatch_receipt_sha256 != receipt.content_sha256
        or closure.import_receipt_sha256 != imported.content_sha256
        or closure.budget_closure_sha256 != budget_closure.content_sha256
        or closure.observed_usage != receipt.observed_usage
        or closure.effect_evidence_sha256s != receipt.effect_evidence_sha256s
        or not closure.closure_permitted
    ):
        return "governed attempt monitor closure differs from accounted effect evidence"
    return None


def complete_chain_error(
    *,
    preflight: GovernedAttemptPreflight,
    reservation: GovernedAttemptBudgetReservation,
    permit: GovernedAttemptMonitorPermit,
    intent: GovernedAttemptDispatchIntent,
    receipt: GovernedAttemptBackendReceipt,
    imported: GovernedAttemptImportReceipt,
    budget_closure: GovernedAttemptBudgetClosure,
    monitor_closure: GovernedAttemptMonitorClosure,
    terminal: GovernedAttemptTerminal,
) -> str | None:
    """Return the first mismatch in a complete terminal lifecycle chain."""

    for error in (
        reservation_error(preflight, reservation),
        permit_error(preflight, reservation, permit),
        intent_error(preflight, reservation, permit, intent),
        receipt_error(preflight, intent, receipt),
        import_error(preflight, receipt, imported),
        budget_closure_error(
            reservation,
            receipt,
            imported,
            budget_closure,
        ),
        monitor_closure_error(
            permit,
            receipt,
            imported,
            budget_closure,
            monitor_closure,
        ),
    ):
        if error is not None:
            return error
    if (
        terminal.attempt_id != preflight.attempt_id
        or terminal.preflight_sha256 != preflight.content_sha256
        or terminal.reservation_sha256 != reservation.content_sha256
        or terminal.monitor_permit_sha256 != permit.content_sha256
        or terminal.dispatch_intent_sha256 != intent.content_sha256
        or terminal.dispatch_receipt_sha256 != receipt.content_sha256
        or terminal.import_receipt_sha256 != imported.content_sha256
        or terminal.budget_closure_sha256 != budget_closure.content_sha256
        or terminal.monitor_closure_sha256 != monitor_closure.content_sha256
        or terminal.effect_evidence_sha256s != receipt.effect_evidence_sha256s
        or terminal.imported_evidence_sha256s != imported.imported_evidence_sha256s
    ):
        return "governed attempt terminal differs from its exact lifecycle chain"
    return None


def usage_breach_label(
    *,
    observed: GovernedAttemptUsage,
    maximum: GovernedAttemptUsageLimits,
) -> str | None:
    """Return the first generic usage dimension above its reservation."""

    comparisons: tuple[tuple[int | float, int | float | None, str], ...] = (
        (observed.model_calls, maximum.model_calls, "model calls"),
        (
            observed.input_tokens + observed.output_tokens + observed.cache_read_tokens + observed.cache_write_tokens,
            maximum.total_tokens,
            "total tokens",
        ),
        (
            observed.estimated_cost_usd,
            maximum.estimated_cost_usd,
            "estimated cost",
        ),
        (
            observed.wall_time_seconds,
            maximum.wall_time_seconds,
            "wall time",
        ),
    )
    return next(
        (label for actual, permitted, label in comparisons if permitted is not None and actual > permitted),
        None,
    )
