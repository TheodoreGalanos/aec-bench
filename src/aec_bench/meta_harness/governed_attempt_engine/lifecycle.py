# ABOUTME: Coordinates one provider-neutral governed attempt across durable lifecycle stages.
# ABOUTME: Prevents ambiguous backend redispatch while delegating contracts and persistence.

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from aec_bench.contracts.harness_kernel import ContentAddressedModel

from .chain_validation import (
    budget_closure_error,
    build_dispatch_intent,
    import_error,
    intent_error,
    monitor_closure_error,
    permit_error,
    receipt_error,
    reservation_error,
)
from .contracts import (
    GovernedAttemptBackendReceipt,
    GovernedAttemptBudgetClosure,
    GovernedAttemptBudgetReservation,
    GovernedAttemptCollisionError,
    GovernedAttemptDispatchIntent,
    GovernedAttemptDispatchUncertainError,
    GovernedAttemptError,
    GovernedAttemptExtensionError,
    GovernedAttemptImportReceipt,
    GovernedAttemptIncompleteError,
    GovernedAttemptIntegrityError,
    GovernedAttemptMonitorClosure,
    GovernedAttemptMonitorPermit,
    GovernedAttemptPreflight,
    GovernedAttemptReconciliationRequiredError,
    GovernedAttemptReplay,
    GovernedAttemptStage,
    GovernedAttemptTerminal,
)
from .ports import (
    GovernedAttemptBackendPort,
    GovernedAttemptBudgetPort,
    GovernedAttemptImportExtension,
    GovernedAttemptMonitorPort,
)
from .repository import (
    BUDGET_CLOSURE_ADAPTER,
    IMPORT_ADAPTER,
    INTENT_ADAPTER,
    MONITOR_CLOSURE_ADAPTER,
    PERMIT_ADAPTER,
    PREFLIGHT_ADAPTER,
    RECEIPT_ADAPTER,
    RESERVATION_ADAPTER,
    TERMINAL_ADAPTER,
    GovernedAttemptRepository,
)


class GovernedAttemptEngine:
    """Execute or replay one exact governed attempt without phase knowledge."""

    def __init__(
        self,
        *,
        root: Path,
        budget: GovernedAttemptBudgetPort,
        monitor: GovernedAttemptMonitorPort,
        backend: GovernedAttemptBackendPort,
        import_extension: GovernedAttemptImportExtension,
        disjoint_roots: tuple[Path, ...] = (),
    ) -> None:
        self._repository = GovernedAttemptRepository(
            root=Path(root),
            disjoint_roots=disjoint_roots,
        )
        self._budget = budget
        self._monitor = monitor
        self._backend = backend
        self._import_extension = import_extension

    @property
    def root(self) -> Path:
        """Return the exact confined evidence repository root."""

        return self._repository.root

    def execute(
        self,
        preflight: GovernedAttemptPreflight,
    ) -> GovernedAttemptReplay:
        """Execute missing stages or replay a complete terminal attempt."""

        selected_preflight = _validated_model(
            preflight,
            GovernedAttemptPreflight,
            label="governed attempt preflight",
        )
        with self._repository.locked():
            selected_preflight = self._select_preflight(selected_preflight)
            state = self._repository.load_state(
                selected_preflight.attempt_id,
            )
            self._repository.validate_partial_state(state)
            if state.terminal is not None:
                return self._repository.complete_replay(state)

            reservation = self._ensure_reservation(
                selected_preflight,
                state.reservation,
            )
            permit = self._ensure_permit(
                selected_preflight,
                reservation,
                state.permit,
            )
            intent, intent_was_durable = self._ensure_intent(
                selected_preflight,
                reservation,
                permit,
                state.intent,
            )
            receipt = self._ensure_receipt(
                selected_preflight,
                intent,
                state.receipt,
                intent_was_durable=intent_was_durable,
            )
            imported = self._ensure_import(
                selected_preflight,
                receipt,
                state.imported,
            )
            budget_closure = self._ensure_budget_closure(
                reservation,
                receipt,
                imported,
                state.budget_closure,
            )
            monitor_closure = self._ensure_monitor_closure(
                permit,
                receipt,
                imported,
                budget_closure,
                state.monitor_closure,
            )
            terminal = self._publish_terminal(
                preflight=selected_preflight,
                reservation=reservation,
                permit=permit,
                intent=intent,
                receipt=receipt,
                imported=imported,
                budget_closure=budget_closure,
                monitor_closure=monitor_closure,
            )
            return GovernedAttemptReplay(
                preflight=selected_preflight,
                reservation=reservation,
                monitor_permit=permit,
                dispatch_intent=intent,
                dispatch_receipt=receipt,
                import_receipt=imported,
                budget_closure=budget_closure,
                monitor_closure=monitor_closure,
                terminal=terminal,
            )

    def replay(self, attempt_id: str) -> GovernedAttemptReplay:
        """Replay one terminal attempt without invoking any extension port."""

        if not attempt_id.strip():
            raise GovernedAttemptIntegrityError(
                "governed attempt id must be non-empty",
            )
        with self._repository.locked():
            state = self._repository.load_state(attempt_id)
            self._repository.validate_partial_state(state)
            if state.terminal is None:
                raise GovernedAttemptIncompleteError(
                    "governed attempt has no terminal evidence",
                )
            return self._repository.complete_replay(state)

    def _select_preflight(
        self,
        preflight: GovernedAttemptPreflight,
    ) -> GovernedAttemptPreflight:
        selected = self._repository.publish_record(
            stage=GovernedAttemptStage.PREFLIGHT,
            attempt_id=preflight.attempt_id,
            record=preflight,
            adapter=PREFLIGHT_ADAPTER,
        )
        if selected != preflight:
            raise GovernedAttemptCollisionError(
                "governed attempt preflight selected different immutable content",
            )
        return selected

    def _ensure_reservation(
        self,
        preflight: GovernedAttemptPreflight,
        existing: GovernedAttemptBudgetReservation | None,
    ) -> GovernedAttemptBudgetReservation:
        if existing is not None:
            return existing
        reservation = _validated_model(
            self._call_extension(
                "budget reservation",
                lambda: self._budget.reserve(preflight),
            ),
            GovernedAttemptBudgetReservation,
            label="governed attempt budget reservation",
        )
        selected = self._repository.publish_record(
            stage=GovernedAttemptStage.BUDGET_RESERVATION,
            attempt_id=preflight.attempt_id,
            record=reservation,
            adapter=RESERVATION_ADAPTER,
        )
        _raise_chain_error(reservation_error(preflight, selected))
        return selected

    def _ensure_permit(
        self,
        preflight: GovernedAttemptPreflight,
        reservation: GovernedAttemptBudgetReservation,
        existing: GovernedAttemptMonitorPermit | None,
    ) -> GovernedAttemptMonitorPermit:
        if existing is not None:
            return existing
        permit = _validated_model(
            self._call_extension(
                "monitor authorization",
                lambda: self._monitor.authorize(
                    preflight=preflight,
                    reservation=reservation,
                ),
            ),
            GovernedAttemptMonitorPermit,
            label="governed attempt monitor permit",
        )
        selected = self._repository.publish_record(
            stage=GovernedAttemptStage.MONITOR_PERMIT,
            attempt_id=preflight.attempt_id,
            record=permit,
            adapter=PERMIT_ADAPTER,
        )
        _raise_chain_error(permit_error(preflight, reservation, selected))
        return selected

    def _ensure_intent(
        self,
        preflight: GovernedAttemptPreflight,
        reservation: GovernedAttemptBudgetReservation,
        permit: GovernedAttemptMonitorPermit,
        existing: GovernedAttemptDispatchIntent | None,
    ) -> tuple[GovernedAttemptDispatchIntent, bool]:
        if existing is not None:
            return existing, True
        intent = build_dispatch_intent(preflight, reservation, permit)
        selected = self._repository.publish_record(
            stage=GovernedAttemptStage.DISPATCH_INTENT,
            attempt_id=preflight.attempt_id,
            record=intent,
            adapter=INTENT_ADAPTER,
        )
        _raise_chain_error(intent_error(preflight, reservation, permit, selected))
        return selected, False

    def _ensure_receipt(
        self,
        preflight: GovernedAttemptPreflight,
        intent: GovernedAttemptDispatchIntent,
        existing: GovernedAttemptBackendReceipt | None,
        *,
        intent_was_durable: bool,
    ) -> GovernedAttemptBackendReceipt:
        if existing is not None:
            return existing
        receipt = self._obtain_backend_receipt(
            intent=intent,
            intent_was_durable=intent_was_durable,
        )
        selected = self._repository.publish_record(
            stage=GovernedAttemptStage.BACKEND_RECEIPT,
            attempt_id=preflight.attempt_id,
            record=receipt,
            adapter=RECEIPT_ADAPTER,
        )
        _raise_chain_error(receipt_error(preflight, intent, selected))
        return selected

    def _ensure_import(
        self,
        preflight: GovernedAttemptPreflight,
        receipt: GovernedAttemptBackendReceipt,
        existing: GovernedAttemptImportReceipt | None,
    ) -> GovernedAttemptImportReceipt:
        if existing is not None:
            return existing
        imported = _validated_model(
            self._call_extension(
                "import extension",
                lambda: self._import_extension.import_result(
                    preflight=preflight,
                    dispatch_receipt=receipt,
                ),
            ),
            GovernedAttemptImportReceipt,
            label="governed attempt import receipt",
        )
        selected = self._repository.publish_record(
            stage=GovernedAttemptStage.IMPORT_RECEIPT,
            attempt_id=preflight.attempt_id,
            record=imported,
            adapter=IMPORT_ADAPTER,
        )
        _raise_chain_error(import_error(preflight, receipt, selected))
        return selected

    def _ensure_budget_closure(
        self,
        reservation: GovernedAttemptBudgetReservation,
        receipt: GovernedAttemptBackendReceipt,
        imported: GovernedAttemptImportReceipt,
        existing: GovernedAttemptBudgetClosure | None,
    ) -> GovernedAttemptBudgetClosure:
        if existing is not None:
            return existing
        closure = _validated_model(
            self._call_extension(
                "budget closure",
                lambda: self._budget.close(
                    reservation=reservation,
                    dispatch_receipt=receipt,
                    import_receipt=imported,
                ),
            ),
            GovernedAttemptBudgetClosure,
            label="governed attempt budget closure",
        )
        selected = self._repository.publish_record(
            stage=GovernedAttemptStage.BUDGET_CLOSURE,
            attempt_id=reservation.attempt_id,
            record=closure,
            adapter=BUDGET_CLOSURE_ADAPTER,
        )
        _raise_chain_error(
            budget_closure_error(
                reservation,
                receipt,
                imported,
                selected,
            )
        )
        return selected

    def _ensure_monitor_closure(
        self,
        permit: GovernedAttemptMonitorPermit,
        receipt: GovernedAttemptBackendReceipt,
        imported: GovernedAttemptImportReceipt,
        budget_closure: GovernedAttemptBudgetClosure,
        existing: GovernedAttemptMonitorClosure | None,
    ) -> GovernedAttemptMonitorClosure:
        if existing is not None:
            return existing
        closure = _validated_model(
            self._call_extension(
                "monitor closure",
                lambda: self._monitor.close(
                    permit=permit,
                    dispatch_receipt=receipt,
                    import_receipt=imported,
                    budget_closure=budget_closure,
                ),
            ),
            GovernedAttemptMonitorClosure,
            label="governed attempt monitor closure",
        )
        selected = self._repository.publish_record(
            stage=GovernedAttemptStage.MONITOR_CLOSURE,
            attempt_id=permit.attempt_id,
            record=closure,
            adapter=MONITOR_CLOSURE_ADAPTER,
        )
        _raise_chain_error(
            monitor_closure_error(
                permit,
                receipt,
                imported,
                budget_closure,
                selected,
            )
        )
        return selected

    def _publish_terminal(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        reservation: GovernedAttemptBudgetReservation,
        permit: GovernedAttemptMonitorPermit,
        intent: GovernedAttemptDispatchIntent,
        receipt: GovernedAttemptBackendReceipt,
        imported: GovernedAttemptImportReceipt,
        budget_closure: GovernedAttemptBudgetClosure,
        monitor_closure: GovernedAttemptMonitorClosure,
    ) -> GovernedAttemptTerminal:
        terminal = GovernedAttemptTerminal(
            attempt_id=preflight.attempt_id,
            preflight_sha256=preflight.content_sha256,
            reservation_sha256=reservation.content_sha256,
            monitor_permit_sha256=permit.content_sha256,
            dispatch_intent_sha256=intent.content_sha256,
            dispatch_receipt_sha256=receipt.content_sha256,
            import_receipt_sha256=imported.content_sha256,
            budget_closure_sha256=budget_closure.content_sha256,
            monitor_closure_sha256=monitor_closure.content_sha256,
            effect_evidence_sha256s=receipt.effect_evidence_sha256s,
            imported_evidence_sha256s=imported.imported_evidence_sha256s,
        )
        return self._repository.publish_record(
            stage=GovernedAttemptStage.TERMINAL,
            attempt_id=preflight.attempt_id,
            record=terminal,
            adapter=TERMINAL_ADAPTER,
        )

    def _obtain_backend_receipt(
        self,
        *,
        intent: GovernedAttemptDispatchIntent,
        intent_was_durable: bool,
    ) -> GovernedAttemptBackendReceipt:
        if intent_was_durable:
            return self._reconcile_backend_receipt(intent)
        try:
            dispatched = self._backend.dispatch(intent)
            return _validated_model(
                dispatched,
                GovernedAttemptBackendReceipt,
                label="governed attempt backend receipt",
            )
        except Exception as error:
            raise GovernedAttemptDispatchUncertainError(
                "governed attempt backend receipt is uncertain after durable dispatch intent",
            ) from error

    def _reconcile_backend_receipt(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> GovernedAttemptBackendReceipt:
        try:
            reconciled = self._backend.reconcile(intent)
        except Exception as error:
            raise GovernedAttemptReconciliationRequiredError(
                "durable governed dispatch intent could not reconcile a backend receipt",
            ) from error
        if reconciled is None:
            raise GovernedAttemptReconciliationRequiredError(
                "durable governed dispatch intent could not reconcile a backend receipt",
            )
        try:
            return _validated_model(
                reconciled,
                GovernedAttemptBackendReceipt,
                label="reconciled governed attempt backend receipt",
            )
        except GovernedAttemptIntegrityError as error:
            raise GovernedAttemptReconciliationRequiredError(
                "durable governed dispatch intent reconciled an invalid backend receipt",
            ) from error

    def _call_extension[ResultT](
        self,
        label: str,
        operation: Callable[[], ResultT],
    ) -> ResultT:
        try:
            return operation()
        except GovernedAttemptError:
            raise
        except Exception as error:
            raise GovernedAttemptExtensionError(
                f"governed attempt {label} failed: {error}",
            ) from error


def _validated_model[ModelT: ContentAddressedModel](
    value: object,
    model_type: type[ModelT],
    *,
    label: str,
) -> ModelT:
    try:
        if not isinstance(value, model_type):
            raise TypeError(f"expected {model_type.__name__}")
        return model_type.model_validate(
            value.model_dump(mode="python"),
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise GovernedAttemptIntegrityError(
            f"{label} is invalid: {error}",
        ) from error


def _raise_chain_error(error: str | None) -> None:
    if error is not None:
        raise GovernedAttemptIntegrityError(error)
