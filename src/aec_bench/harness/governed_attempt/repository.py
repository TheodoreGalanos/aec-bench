# ABOUTME: Persists and replays phase-neutral governed-attempt stage records and claims.
# ABOUTME: Owns repository confinement, immutable stage prefixes, and local process locking.

from __future__ import annotations

import fcntl
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import TypeAdapter

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.ledger.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
)

from .chain_validation import (
    budget_closure_error,
    complete_chain_error,
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
    GovernedAttemptConfinementError,
    GovernedAttemptDispatchIntent,
    GovernedAttemptImportReceipt,
    GovernedAttemptIncompleteError,
    GovernedAttemptIntegrityError,
    GovernedAttemptMonitorClosure,
    GovernedAttemptMonitorPermit,
    GovernedAttemptPreflight,
    GovernedAttemptReplay,
    GovernedAttemptStage,
    GovernedAttemptStageClaim,
    GovernedAttemptTerminal,
)


@dataclass(frozen=True, slots=True)
class AttemptState:
    """Optional durable records for one exact lifecycle prefix."""

    preflight: GovernedAttemptPreflight | None
    reservation: GovernedAttemptBudgetReservation | None
    permit: GovernedAttemptMonitorPermit | None
    intent: GovernedAttemptDispatchIntent | None
    receipt: GovernedAttemptBackendReceipt | None
    imported: GovernedAttemptImportReceipt | None
    budget_closure: GovernedAttemptBudgetClosure | None
    monitor_closure: GovernedAttemptMonitorClosure | None
    terminal: GovernedAttemptTerminal | None


RecordT = TypeVar("RecordT", bound=ContentAddressedModel)

PREFLIGHT_ADAPTER = TypeAdapter(GovernedAttemptPreflight)
RESERVATION_ADAPTER = TypeAdapter(GovernedAttemptBudgetReservation)
PERMIT_ADAPTER = TypeAdapter(GovernedAttemptMonitorPermit)
INTENT_ADAPTER = TypeAdapter(GovernedAttemptDispatchIntent)
RECEIPT_ADAPTER = TypeAdapter(GovernedAttemptBackendReceipt)
IMPORT_ADAPTER = TypeAdapter(GovernedAttemptImportReceipt)
BUDGET_CLOSURE_ADAPTER = TypeAdapter(GovernedAttemptBudgetClosure)
MONITOR_CLOSURE_ADAPTER = TypeAdapter(GovernedAttemptMonitorClosure)
TERMINAL_ADAPTER = TypeAdapter(GovernedAttemptTerminal)
_CLAIM_ADAPTER = TypeAdapter(GovernedAttemptStageClaim)


class GovernedAttemptRepository:
    """Content-addressed objects and logical claims for governed attempts."""

    def __init__(
        self,
        *,
        root: Path,
        disjoint_roots: tuple[Path, ...],
    ) -> None:
        with _translate_repository_errors(label="governed attempt repository"):
            self._repository = EvidenceRepository(
                Path(root),
                disjoint_roots=disjoint_roots,
                host_private=True,
            )
        self._lock_path = self._repository.root / ".governed-attempt.lock"

    @property
    def root(self) -> Path:
        """Return the exact confined evidence repository root."""

        return self._repository.root

    def publish_record(
        self,
        *,
        stage: GovernedAttemptStage,
        attempt_id: str,
        record: RecordT,
        adapter: TypeAdapter[RecordT],
    ) -> RecordT:
        """Publish one content object and bind its immutable logical stage claim."""

        label = _stage_label(stage)
        with _translate_repository_errors(label=label):
            stored = self._repository.publish_content_addressed_model(
                collection=_object_collection(stage),
                filename="record.json",
                model=record,
                adapter=adapter,
            )
            claim = GovernedAttemptStageClaim(
                attempt_id=attempt_id,
                stage=stage,
                record_sha256=stored.model.content_sha256,
            )
            self._repository.publish_logical_model(
                collection=_claim_collection(stage),
                logical_identity=_logical_identity(
                    attempt_id=attempt_id,
                    stage=stage,
                ),
                filename="claim.json",
                model=claim,
                adapter=_CLAIM_ADAPTER,
            )
            selected = self._repository.load_content_addressed_model(
                collection=_object_collection(stage),
                content_sha256=claim.record_sha256,
                filename="record.json",
                adapter=adapter,
            ).model
        if selected != record:
            raise GovernedAttemptCollisionError(
                f"{label} selected different immutable content",
            )
        return selected

    def load_state(self, attempt_id: str) -> AttemptState:
        """Load every claimed lifecycle record for one logical attempt identity."""

        return AttemptState(
            preflight=self._load_record(
                stage=GovernedAttemptStage.PREFLIGHT,
                attempt_id=attempt_id,
                adapter=PREFLIGHT_ADAPTER,
            ),
            reservation=self._load_record(
                stage=GovernedAttemptStage.BUDGET_RESERVATION,
                attempt_id=attempt_id,
                adapter=RESERVATION_ADAPTER,
            ),
            permit=self._load_record(
                stage=GovernedAttemptStage.MONITOR_PERMIT,
                attempt_id=attempt_id,
                adapter=PERMIT_ADAPTER,
            ),
            intent=self._load_record(
                stage=GovernedAttemptStage.DISPATCH_INTENT,
                attempt_id=attempt_id,
                adapter=INTENT_ADAPTER,
            ),
            receipt=self._load_record(
                stage=GovernedAttemptStage.BACKEND_RECEIPT,
                attempt_id=attempt_id,
                adapter=RECEIPT_ADAPTER,
            ),
            imported=self._load_record(
                stage=GovernedAttemptStage.IMPORT_RECEIPT,
                attempt_id=attempt_id,
                adapter=IMPORT_ADAPTER,
            ),
            budget_closure=self._load_record(
                stage=GovernedAttemptStage.BUDGET_CLOSURE,
                attempt_id=attempt_id,
                adapter=BUDGET_CLOSURE_ADAPTER,
            ),
            monitor_closure=self._load_record(
                stage=GovernedAttemptStage.MONITOR_CLOSURE,
                attempt_id=attempt_id,
                adapter=MONITOR_CLOSURE_ADAPTER,
            ),
            terminal=self._load_record(
                stage=GovernedAttemptStage.TERMINAL,
                attempt_id=attempt_id,
                adapter=TERMINAL_ADAPTER,
            ),
        )

    def validate_partial_state(self, state: AttemptState) -> None:
        """Require one exact valid prefix before any extension is invoked."""

        _validate_stage_prefix(state)
        _validate_pre_effect_state(state)
        _validate_post_effect_state(state)

    def complete_replay(self, state: AttemptState) -> GovernedAttemptReplay:
        """Build the typed replay only when every exact terminal record exists."""

        if (
            state.preflight is None
            or state.reservation is None
            or state.permit is None
            or state.intent is None
            or state.receipt is None
            or state.imported is None
            or state.budget_closure is None
            or state.monitor_closure is None
            or state.terminal is None
        ):
            raise GovernedAttemptIncompleteError(
                "governed attempt terminal evidence is incomplete",
            )
        return GovernedAttemptReplay(
            preflight=state.preflight,
            reservation=state.reservation,
            monitor_permit=state.permit,
            dispatch_intent=state.intent,
            dispatch_receipt=state.receipt,
            import_receipt=state.imported,
            budget_closure=state.budget_closure,
            monitor_closure=state.monitor_closure,
            terminal=state.terminal,
        )

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serialize one repository's logical claims across local processes."""

        with _translate_repository_errors(label="governed attempt lock"):
            self._repository.relative_path(self._lock_path)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self._lock_path, flags, 0o600)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise GovernedAttemptConfinementError(
                    "governed attempt lock must be a regular file",
                )
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def _load_record(
        self,
        *,
        stage: GovernedAttemptStage,
        attempt_id: str,
        adapter: TypeAdapter[RecordT],
    ) -> RecordT | None:
        label = _stage_label(stage)
        with _translate_repository_errors(label=label):
            claim_path = self._repository.logical_model_path(
                collection=_claim_collection(stage),
                logical_identity=_logical_identity(
                    attempt_id=attempt_id,
                    stage=stage,
                ),
                filename="claim.json",
            )
            if not self._repository.exists(claim_path):
                return None
            claim = self._repository.load_logical_model(
                collection=_claim_collection(stage),
                logical_identity=_logical_identity(
                    attempt_id=attempt_id,
                    stage=stage,
                ),
                filename="claim.json",
                adapter=_CLAIM_ADAPTER,
            ).model
            if claim.attempt_id != attempt_id or claim.stage is not stage:
                raise GovernedAttemptIntegrityError(
                    f"{label} claim differs from its logical identity",
                )
            return self._repository.load_content_addressed_model(
                collection=_object_collection(stage),
                content_sha256=claim.record_sha256,
                filename="record.json",
                adapter=adapter,
            ).model
        raise AssertionError("unreachable")


def _validate_stage_prefix(state: AttemptState) -> None:
    ordered = (
        state.preflight,
        state.reservation,
        state.permit,
        state.intent,
        state.receipt,
        state.imported,
        state.budget_closure,
        state.monitor_closure,
        state.terminal,
    )
    missing_seen = False
    for record in ordered:
        if record is None:
            missing_seen = True
        elif missing_seen:
            raise GovernedAttemptIntegrityError(
                "governed attempt durable stages do not form one exact prefix",
            )


def _validate_pre_effect_state(state: AttemptState) -> None:
    preflight = state.preflight
    if preflight is None:
        return
    reservation = state.reservation
    if reservation is None:
        return
    _raise_chain_error(reservation_error(preflight, reservation))
    permit = state.permit
    if permit is None:
        return
    _raise_chain_error(permit_error(preflight, reservation, permit))
    intent = state.intent
    if intent is None:
        return
    _raise_chain_error(intent_error(preflight, reservation, permit, intent))


def _validate_post_effect_state(state: AttemptState) -> None:
    if state.preflight is None or state.reservation is None or state.permit is None or state.intent is None:
        return
    receipt = state.receipt
    if receipt is None:
        return
    _raise_chain_error(receipt_error(state.preflight, state.intent, receipt))
    _validate_import_and_closures(state, receipt)


def _validate_import_and_closures(
    state: AttemptState,
    receipt: GovernedAttemptBackendReceipt,
) -> None:
    imported = state.imported
    if imported is None:
        return
    preflight = _required(state.preflight)
    reservation = _required(state.reservation)
    permit = _required(state.permit)
    _raise_chain_error(import_error(preflight, receipt, imported))
    budget_closure = state.budget_closure
    if budget_closure is None:
        return
    _raise_chain_error(
        budget_closure_error(
            reservation,
            receipt,
            imported,
            budget_closure,
        )
    )
    monitor_closure = state.monitor_closure
    if monitor_closure is None:
        return
    _raise_chain_error(
        monitor_closure_error(
            permit,
            receipt,
            imported,
            budget_closure,
            monitor_closure,
        )
    )
    if state.terminal is not None:
        _raise_chain_error(
            complete_chain_error(
                preflight=preflight,
                reservation=reservation,
                permit=permit,
                intent=_required(state.intent),
                receipt=receipt,
                imported=imported,
                budget_closure=budget_closure,
                monitor_closure=monitor_closure,
                terminal=state.terminal,
            )
        )


def _required[ValueT](value: ValueT | None) -> ValueT:
    if value is None:
        raise GovernedAttemptIntegrityError(
            "governed attempt stage prefix lost a required predecessor",
        )
    return value


def _raise_chain_error(error: str | None) -> None:
    if error is not None:
        raise GovernedAttemptIntegrityError(error)


def _object_collection(stage: GovernedAttemptStage) -> str:
    return f"governed-attempt/objects/{stage.value}"


def _claim_collection(stage: GovernedAttemptStage) -> str:
    return f"governed-attempt/claims/{stage.value}"


def _logical_identity(
    *,
    attempt_id: str,
    stage: GovernedAttemptStage,
) -> dict[str, str]:
    return {
        "attempt_id": attempt_id,
        "stage": stage.value,
    }


def _stage_label(stage: GovernedAttemptStage) -> str:
    return f"governed attempt {stage.value.replace('_', ' ')}"


@contextmanager
def _translate_repository_errors(
    *,
    label: str,
) -> Iterator[None]:
    try:
        yield
    except ImmutableArtifactCollisionError as error:
        raise GovernedAttemptCollisionError(
            f"{label} already contains different immutable content",
        ) from error
    except ImmutableArtifactConfinementError as error:
        raise GovernedAttemptConfinementError(
            f"{label}: {error}",
        ) from error
    except ImmutableArtifactIntegrityError as error:
        raise GovernedAttemptIntegrityError(
            f"{label} could not replay canonical evidence: {error}",
        ) from error
