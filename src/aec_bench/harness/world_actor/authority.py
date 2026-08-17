# ABOUTME: Owns trial-wide world action identity, budget, ordering, terminal state, and evidence.
# ABOUTME: Delegates task meaning to the world host and keeps provider transports semantically thin.

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import Field, JsonValue

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
    WorldInterfaceError,
)

ACTOR_INVOCATION_SEMANTICS = "aec-bench/actor-invocation/1"
ACTOR_INVOCATION_EVIDENCE_SCHEMA = "aec-bench/actor-invocation-evidence/1"


class WorldActorHost(Protocol):
    """The actor-facing surface supplied by one concrete task world."""

    def capabilities(self) -> WorldActorCapabilityCatalogue: ...

    def observe(self) -> WorldActorObservation: ...

    def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult: ...


class ActorInvocationLifecycle(StrEnum):
    """Lifecycle of one trial actor authority."""

    CREATED = "created"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"


class ActorInvocationOutcomeClass(StrEnum):
    """State whether a world action was not dispatched, completed, or is unknown."""

    NOT_DISPATCHED = "not-dispatched"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class ActorTurnDisposition(StrEnum):
    """Tell a provider-neutral actor loop whether the current turn can continue."""

    CONTINUE = "continue"
    CONCLUDE_TURN = "conclude-turn"


class _RequestState(StrEnum):
    IN_FLIGHT = "in-flight"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class ActorCorrelation(FrozenStrictModel):
    """Token-free transport correlation that does not participate in request identity."""

    transport_request_id: NonEmptyStr | None = None
    provider_session_id: NonEmptyStr | None = None
    provider_tool_call_id: NonEmptyStr | None = None
    model_turn: int | None = Field(default=None, ge=1)


class ActorInvocationRequest(FrozenStrictModel):
    """One transport-neutral logical world action request."""

    request_id: NonEmptyStr
    decision_id: NonEmptyStr
    action_name: NonEmptyStr
    arguments: dict[str, JsonValue]
    transport: NonEmptyStr
    correlation: ActorCorrelation


@dataclass(frozen=True)
class ActorInvocationAuthorityConfig:
    """Fixed identity, limits, and evidence location for one trial actor."""

    actor_principal_id: str
    max_world_actions: int
    evidence_path: Path
    close_timeout_sec: float = 30.0
    max_result_bytes: int = 4_194_304
    authority_id: str | None = None

    def __post_init__(self) -> None:
        principal = self.actor_principal_id.strip()
        if not principal:
            raise ValueError("actor principal ID must not be blank")
        if isinstance(self.max_world_actions, bool) or self.max_world_actions < 1:
            raise ValueError("actor world action budget must be positive")
        if self.close_timeout_sec < 0:
            raise ValueError("actor authority close timeout must not be negative")
        if isinstance(self.max_result_bytes, bool) or self.max_result_bytes < 1:
            raise ValueError("actor authority maximum result bytes must be positive")
        authority_id = self.authority_id.strip() if self.authority_id is not None else None
        if self.authority_id is not None and not authority_id:
            raise ValueError("actor authority ID must not be blank")
        object.__setattr__(self, "actor_principal_id", principal)
        object.__setattr__(self, "evidence_path", Path(self.evidence_path).resolve())
        object.__setattr__(self, "authority_id", authority_id)


@dataclass(frozen=True)
class ActorInvocationOutcome:
    """One completed world action outcome returned by the shared authority."""

    result: WorldActorActionResult
    action_sequence: int
    duplicate: bool
    disposition: ActorTurnDisposition


@dataclass(frozen=True)
class AuthorityCloseReport:
    """State whether close is quiescent and suitable for complete trial evidence."""

    quiescent: bool
    complete: bool
    unsettled_request_ids: tuple[str, ...]
    unknown_outcome_request_ids: tuple[str, ...]
    closed_at: datetime
    lifecycle: ActorInvocationLifecycle


class ActorInvocationError(RuntimeError):
    """A stable actor-boundary failure that transports can render without interpretation."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        outcome: ActorInvocationOutcomeClass,
        request_id: str | None = None,
        action_sequence: int | None = None,
        duplicate: bool = False,
        disposition: ActorTurnDisposition = ActorTurnDisposition.CONTINUE,
    ) -> None:
        self.code = code
        self.detail = detail
        self.outcome = outcome
        self.request_id = request_id
        self.action_sequence = action_sequence
        self.duplicate = duplicate
        self.disposition = disposition
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class _Failure:
    code: str
    detail: str
    outcome: ActorInvocationOutcomeClass
    disposition: ActorTurnDisposition


@dataclass
class _RequestEntry:
    request: ActorInvocationRequest
    fingerprint: str
    action_sequence: int
    state: _RequestState
    admitted_at: datetime
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
    result: WorldActorActionResult | None = None
    failure: _Failure | None = None
    duplicate_waiters: int = 0


class ActorInvocationAuthority:
    """Own all semantic admission and completion state for one trial actor."""

    def __init__(self, *, host: WorldActorHost, config: ActorInvocationAuthorityConfig) -> None:
        self._host = host
        self.config = config
        self.authority_id = config.authority_id or f"actor-authority-{uuid.uuid4().hex}"
        self._condition = threading.Condition(threading.Lock())
        self._host_operation_lock = threading.Lock()
        self._admission_lock = threading.Lock()
        self._evidence_lock = threading.Lock()
        self._lifecycle = ActorInvocationLifecycle.CREATED
        self._catalogue: WorldActorCapabilityCatalogue | None = None
        self._catalogue_hash: str | None = None
        self._action_names: frozenset[str] = frozenset()
        self._requests: dict[str, _RequestEntry] = {}
        self._active_request_ids: set[str] = set()
        self._next_action_sequence = 1
        self._next_dispatch_sequence = 1
        self._budget_used = 0
        self._budget_reserved = 0
        self._terminal = False
        self._terminal_action_sequence: int | None = None
        self._evidence_sequence = 0
        self._successful_close_report: AuthorityCloseReport | None = None

    @property
    def lifecycle(self) -> ActorInvocationLifecycle:
        with self._condition:
            return self._lifecycle

    @property
    def catalogue_hash(self) -> str | None:
        with self._condition:
            return self._catalogue_hash

    @property
    def world_action_count(self) -> int:
        with self._condition:
            return self._budget_used

    @property
    def world_action_limit_reached(self) -> bool:
        with self._condition:
            return self._budget_used + self._budget_reserved >= self.config.max_world_actions

    @property
    def terminal(self) -> bool:
        with self._condition:
            return self._terminal

    @property
    def last_action_result(self) -> WorldActorActionResult | None:
        """Return the latest completed world result without adding transport state."""
        with self._condition:
            completed = (
                entry
                for entry in self._requests.values()
                if entry.result is not None and entry.state is _RequestState.COMPLETED
            )
            latest = max(completed, key=lambda entry: entry.action_sequence, default=None)
            return None if latest is None else latest.result

    def start(self) -> None:
        """Freeze the task-owned catalogue and create the versioned evidence stream."""
        with self._condition:
            if self._lifecycle is not ActorInvocationLifecycle.CREATED:
                raise RuntimeError("actor invocation authority can start only once")
        catalogue = self._host.capabilities()
        catalogue_hash = _json_sha256(catalogue.model_dump(mode="json"))
        evidence_path = self.config.evidence_path
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        if evidence_path.exists() or evidence_path.is_symlink():
            raise FileExistsError(f"actor invocation evidence already exists: {evidence_path}")
        started_at = datetime.now(UTC)
        with self._evidence_lock:
            self._evidence_sequence = 1
            header = {
                "sequence": self._evidence_sequence,
                "record_type": "header",
                "schema": ACTOR_INVOCATION_EVIDENCE_SCHEMA,
                "semantics": ACTOR_INVOCATION_SEMANTICS,
                "authority_id": self.authority_id,
                "actor_principal_id": self.config.actor_principal_id,
                "catalogue_sha256": catalogue_hash,
                "max_world_actions": self.config.max_world_actions,
                "max_result_bytes": self.config.max_result_bytes,
                "started_at": started_at.isoformat(),
            }
            with evidence_path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(header, sort_keys=True, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            evidence_path.chmod(0o600)
        with self._condition:
            self._catalogue = catalogue
            self._catalogue_hash = catalogue_hash
            self._action_names = frozenset(action.name for action in catalogue.actions)
            self._lifecycle = ActorInvocationLifecycle.RUNNING
            self._condition.notify_all()

    def capabilities(self, *, correlation: ActorCorrelation) -> WorldActorCapabilityCatalogue:
        """Return the frozen catalogue after proving that the host has not drifted."""
        self._require_readable()
        self._require_catalogue_stable()
        with self._condition:
            assert self._catalogue is not None
            catalogue = self._catalogue
        self._append_evidence(
            {
                "record_type": "capabilities",
                "correlation": correlation.model_dump(mode="json"),
                "catalogue_sha256": self.catalogue_hash,
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )
        return catalogue

    def observe(self, *, correlation: ActorCorrelation) -> WorldActorObservation:
        """Read an actor view after all actions admitted before this call have settled."""
        self._require_readable()
        self._require_catalogue_stable()
        with self._condition:
            barrier = self._next_action_sequence - 1
            while any(
                entry.action_sequence <= barrier and entry.state is _RequestState.IN_FLIGHT
                for entry in self._requests.values()
            ):
                self._condition.wait()
            if self._lifecycle is not ActorInvocationLifecycle.RUNNING:
                raise self._lifecycle_error()
        observed_at = datetime.now(UTC)
        try:
            with self._host_operation_lock:
                observation = self._host.observe()
        except WorldInterfaceError as exc:
            error = ActorInvocationError(
                exc.code,
                exc.detail,
                outcome=ActorInvocationOutcomeClass.COMPLETED,
            )
            self._append_read_error("observe", correlation, error, observed_at)
            raise error from exc
        except Exception as exc:
            error = ActorInvocationError(
                "actor-observation-failed",
                "World observation failed.",
                outcome=ActorInvocationOutcomeClass.UNKNOWN,
            )
            self._append_read_error("observe", correlation, error, observed_at)
            raise error from exc
        self._append_evidence(
            {
                "record_type": "observe",
                "correlation": correlation.model_dump(mode="json"),
                "observed_at": observed_at.isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "decision_id_sha256": _text_sha256(observation.decision_id),
                "observation_sha256": _json_sha256(observation.model_dump(mode="json")),
                "barrier_action_sequence": barrier,
            }
        )
        return observation

    def invoke(self, request: ActorInvocationRequest) -> ActorInvocationOutcome:
        """Admit, deduplicate, order, and dispatch one logical world action."""
        with self._admission_lock:
            admitted = self._admit(request)
        if isinstance(admitted, ActorInvocationOutcome):
            return admitted
        return self._dispatch(admitted)

    def invoke_current(
        self,
        *,
        request_id: str,
        action_name: str,
        arguments: dict[str, JsonValue],
        transport: str,
        correlation: ActorCorrelation,
    ) -> ActorInvocationOutcome:
        """Capture one hidden current decision and retain it for exact retries."""
        with self._admission_lock:
            with self._condition:
                existing = self._requests.get(request_id)
                decision_id = existing.request.decision_id if existing is not None else None
            if decision_id is None:
                decision_id = self.observe(correlation=correlation).decision_id
            admitted = self._admit(
                ActorInvocationRequest(
                    request_id=request_id,
                    decision_id=decision_id,
                    action_name=action_name,
                    arguments=arguments,
                    transport=transport,
                    correlation=correlation,
                )
            )
        if isinstance(admitted, ActorInvocationOutcome):
            return admitted
        return self._dispatch(admitted)

    def _admit(self, request: ActorInvocationRequest) -> _RequestEntry | ActorInvocationOutcome:
        fingerprint = _request_fingerprint(self.config.actor_principal_id, request)
        with self._condition:
            existing = self._requests.get(request.request_id)
            if existing is not None:
                return self._handle_existing_locked(existing, request, fingerprint)
            if self._lifecycle is not ActorInvocationLifecycle.RUNNING:
                error = self._lifecycle_error(request.request_id)
                self._append_rejection(request, fingerprint, error)
                raise error
            if self._terminal:
                error = ActorInvocationError(
                    "episode-closed",
                    "The world episode is closed.",
                    outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                    request_id=request.request_id,
                    disposition=ActorTurnDisposition.CONCLUDE_TURN,
                )
                self._append_rejection(request, fingerprint, error)
                raise error
            if request.action_name not in self._action_names:
                error = ActorInvocationError(
                    "world-action-not-available",
                    "The requested world action is not in the frozen catalogue.",
                    outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                    request_id=request.request_id,
                )
                self._append_rejection(request, fingerprint, error)
                raise error
            if self._budget_used + self._budget_reserved >= self.config.max_world_actions:
                error = ActorInvocationError(
                    "world-action-budget-exhausted",
                    "The world action budget is exhausted.",
                    outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                    request_id=request.request_id,
                    disposition=ActorTurnDisposition.CONCLUDE_TURN,
                )
                self._append_rejection(request, fingerprint, error)
                raise error

        self._require_catalogue_stable()
        with self._condition:
            existing = self._requests.get(request.request_id)
            if existing is not None:
                return self._handle_existing_locked(existing, request, fingerprint)
            if self._lifecycle is not ActorInvocationLifecycle.RUNNING:
                error = self._lifecycle_error(request.request_id)
                self._append_rejection(request, fingerprint, error)
                raise error
            if self._terminal:
                error = ActorInvocationError(
                    "episode-closed",
                    "The world episode is closed.",
                    outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                    request_id=request.request_id,
                    disposition=ActorTurnDisposition.CONCLUDE_TURN,
                )
                self._append_rejection(request, fingerprint, error)
                raise error
            if self._budget_used + self._budget_reserved >= self.config.max_world_actions:
                error = ActorInvocationError(
                    "world-action-budget-exhausted",
                    "The world action budget is exhausted.",
                    outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                    request_id=request.request_id,
                    disposition=ActorTurnDisposition.CONCLUDE_TURN,
                )
                self._append_rejection(request, fingerprint, error)
                raise error
            action_sequence = self._next_action_sequence
            self._next_action_sequence += 1
            self._budget_reserved += 1
            entry = _RequestEntry(
                request=request,
                fingerprint=fingerprint,
                action_sequence=action_sequence,
                state=_RequestState.IN_FLIGHT,
                admitted_at=datetime.now(UTC),
            )
            self._requests[request.request_id] = entry
            self._active_request_ids.add(request.request_id)
            self._append_evidence(
                {
                    "record_type": "request-admitted",
                    "request_id": request.request_id,
                    "request_fingerprint": fingerprint,
                    "action_sequence": action_sequence,
                    "action_name": request.action_name,
                    "transport": request.transport,
                    "correlation": request.correlation.model_dump(mode="json"),
                    "budget_used": self._budget_used,
                    "budget_reserved": self._budget_reserved,
                    "admitted_at": entry.admitted_at.isoformat(),
                }
            )
            self._condition.notify_all()
        return entry

    def close(self, *, timeout_sec: float | None = None) -> AuthorityCloseReport:
        """Reject new actions and report whether every admitted action is settled."""
        timeout = self.config.close_timeout_sec if timeout_sec is None else timeout_sec
        if timeout < 0:
            raise ValueError("actor authority close timeout must not be negative")
        with self._condition:
            if self._successful_close_report is not None:
                return self._successful_close_report
            if self._lifecycle is ActorInvocationLifecycle.CREATED:
                raise RuntimeError("actor invocation authority is not started")
            if self._lifecycle is ActorInvocationLifecycle.RUNNING:
                self._lifecycle = ActorInvocationLifecycle.CLOSING
                self._condition.notify_all()
            deadline = time.monotonic() + timeout
            while self._active_request_ids:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
            unsettled = tuple(sorted(self._active_request_ids))
            if unsettled:
                for request_id in unsettled:
                    entry = self._requests[request_id]
                    if entry.dispatched_at is not None and entry.state is _RequestState.IN_FLIGHT:
                        entry.state = _RequestState.UNKNOWN
                        entry.failure = _Failure(
                            code="actor-invocation-outcome-unknown",
                            detail="The world action did not settle before authority close.",
                            outcome=ActorInvocationOutcomeClass.UNKNOWN,
                            disposition=ActorTurnDisposition.CONCLUDE_TURN,
                        )
                self._condition.notify_all()
            unknown = self._unknown_request_ids_locked()
            if not unsettled:
                self._lifecycle = ActorInvocationLifecycle.CLOSED
            report = AuthorityCloseReport(
                quiescent=not unsettled,
                complete=not unsettled and not unknown,
                unsettled_request_ids=unsettled,
                unknown_outcome_request_ids=unknown,
                closed_at=datetime.now(UTC),
                lifecycle=self._lifecycle,
            )
            if report.quiescent:
                self._successful_close_report = report
            self._append_evidence(
                {
                    "record_type": "close",
                    "closed_at": report.closed_at.isoformat(),
                    "lifecycle": report.lifecycle.value,
                    "quiescent": report.quiescent,
                    "complete": report.complete,
                    "unsettled_request_ids": list(report.unsettled_request_ids),
                    "unknown_outcome_request_ids": list(report.unknown_outcome_request_ids),
                    "budget_used": self._budget_used,
                    "terminal": self._terminal,
                }
            )
            return report

    def _dispatch(self, entry: _RequestEntry) -> ActorInvocationOutcome:
        with self._condition:
            while entry.state is _RequestState.IN_FLIGHT and entry.action_sequence != self._next_dispatch_sequence:
                if self._lifecycle is not ActorInvocationLifecycle.RUNNING and entry.dispatched_at is None:
                    self._cancel_before_dispatch_locked(entry)
                    break
                self._condition.wait()
            if entry.state is not _RequestState.IN_FLIGHT:
                return self._replay_locked(entry, duplicate=False)
            if self._lifecycle is not ActorInvocationLifecycle.RUNNING:
                self._reject_before_dispatch_locked(
                    entry,
                    _Failure(
                        code="actor-authority-closing",
                        detail="The actor invocation authority is closing.",
                        outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                        disposition=ActorTurnDisposition.CONCLUDE_TURN,
                    ),
                )
                return self._replay_locked(entry, duplicate=False)
            if self._terminal:
                self._reject_before_dispatch_locked(
                    entry,
                    _Failure(
                        code="episode-closed",
                        detail="The world episode is closed.",
                        outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                        disposition=ActorTurnDisposition.CONCLUDE_TURN,
                    ),
                )
                return self._replay_locked(entry, duplicate=False)
            budget_before = self._budget_used
            self._budget_reserved -= 1
            self._budget_used += 1
            entry.dispatched_at = datetime.now(UTC)
            self._append_evidence(
                {
                    "record_type": "dispatch",
                    "request_id": entry.request.request_id,
                    "action_sequence": entry.action_sequence,
                    "dispatched_at": entry.dispatched_at.isoformat(),
                    "budget_before": budget_before,
                    "budget_after": self._budget_used,
                }
            )

        result: WorldActorActionResult | None = None
        failure: _Failure | None = None
        try:
            with self._host_operation_lock:
                result = self._host.invoke(
                    WorldActorActionRequest(
                        request_id=entry.request.request_id,
                        decision_id=entry.request.decision_id,
                        action_name=entry.request.action_name,
                        arguments=entry.request.arguments,
                    )
                )
            if not isinstance(result, WorldActorActionResult):
                raise TypeError("world host returned an invalid action result")
            if result.request_id != entry.request.request_id or result.action_name != entry.request.action_name:
                raise ValueError("world result identity does not match the admitted request")
            result_bytes = _json_bytes(result.model_dump(mode="json"))
            if len(result_bytes) > self.config.max_result_bytes:
                failure = _Failure(
                    code="world-action-result-too-large",
                    detail="The world action result exceeds the authority limit.",
                    outcome=ActorInvocationOutcomeClass.COMPLETED,
                    disposition=(
                        ActorTurnDisposition.CONCLUDE_TURN
                        if result.terminated or result.truncated
                        else ActorTurnDisposition.CONTINUE
                    ),
                )
        except WorldInterfaceError as exc:
            failure = _Failure(
                code=exc.code,
                detail=exc.detail,
                outcome=ActorInvocationOutcomeClass.COMPLETED,
                disposition=ActorTurnDisposition.CONTINUE,
            )
        except (TypeError, ValueError):
            result = None
            failure = _Failure(
                code="world-action-outcome-invalid",
                detail="The world action returned an invalid outcome.",
                outcome=ActorInvocationOutcomeClass.UNKNOWN,
                disposition=ActorTurnDisposition.CONCLUDE_TURN,
            )
        except Exception:
            failure = _Failure(
                code="actor-invocation-outcome-unknown",
                detail="The world action outcome is unknown.",
                outcome=ActorInvocationOutcomeClass.UNKNOWN,
                disposition=ActorTurnDisposition.CONCLUDE_TURN,
            )

        completed_at = datetime.now(UTC)
        with self._condition:
            late_ignored = self._is_unknown(entry)
            if not late_ignored:
                entry.completed_at = completed_at
                if failure is None:
                    assert result is not None
                    entry.result = result
                    entry.state = _RequestState.COMPLETED
                    if result.terminated or result.truncated:
                        self._terminal = True
                        self._terminal_action_sequence = entry.action_sequence
                else:
                    entry.failure = failure
                    entry.state = (
                        _RequestState.UNKNOWN
                        if failure.outcome is ActorInvocationOutcomeClass.UNKNOWN
                        else _RequestState.COMPLETED
                    )
                    if failure.code == "world-action-result-too-large" and result is not None:
                        if result.terminated or result.truncated:
                            self._terminal = True
                            self._terminal_action_sequence = entry.action_sequence
            self._active_request_ids.discard(entry.request.request_id)
            self._advance_dispatch_sequence_locked()
            self._condition.notify_all()
            effective_failure = entry.failure if late_ignored else failure
            self._append_completion_locked(
                entry,
                result=result,
                failure=effective_failure,
                late_ignored=late_ignored,
            )
            return self._replay_locked(entry, duplicate=False)

    def _handle_existing_locked(
        self,
        entry: _RequestEntry,
        request: ActorInvocationRequest,
        fingerprint: str,
    ) -> ActorInvocationOutcome:
        if entry.fingerprint != fingerprint:
            error = ActorInvocationError(
                "request-id-conflict",
                "The request ID was reused with different world action content.",
                outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                request_id=request.request_id,
                action_sequence=entry.action_sequence,
            )
            self._append_evidence(
                {
                    "record_type": "request-conflict",
                    "request_id": request.request_id,
                    "request_fingerprint": fingerprint,
                    "conflicts_with_fingerprint": entry.fingerprint,
                    "action_sequence": entry.action_sequence,
                    "occurred_at": datetime.now(UTC).isoformat(),
                }
            )
            raise error
        entry.duplicate_waiters += 1
        duplicate_state = entry.state
        self._append_evidence(
            {
                "record_type": "request-duplicate",
                "request_id": request.request_id,
                "request_fingerprint": fingerprint,
                "action_sequence": entry.action_sequence,
                "original_state": duplicate_state.value,
                "duplicate_waiter": duplicate_state is _RequestState.IN_FLIGHT,
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )
        while entry.state is _RequestState.IN_FLIGHT:
            self._condition.wait()
        return self._replay_locked(entry, duplicate=True)

    def _replay_locked(self, entry: _RequestEntry, *, duplicate: bool) -> ActorInvocationOutcome:
        if entry.result is not None:
            disposition = (
                ActorTurnDisposition.CONCLUDE_TURN
                if entry.result.terminated or entry.result.truncated
                else ActorTurnDisposition.CONTINUE
            )
            return ActorInvocationOutcome(
                result=entry.result,
                action_sequence=entry.action_sequence,
                duplicate=duplicate,
                disposition=disposition,
            )
        assert entry.failure is not None
        raise ActorInvocationError(
            entry.failure.code,
            entry.failure.detail,
            outcome=entry.failure.outcome,
            request_id=entry.request.request_id,
            action_sequence=entry.action_sequence,
            duplicate=duplicate,
            disposition=entry.failure.disposition,
        )

    def _cancel_before_dispatch_locked(self, entry: _RequestEntry) -> None:
        self._reject_before_dispatch_locked(
            entry,
            _Failure(
                code="actor-authority-closing",
                detail="The actor invocation authority is closing.",
                outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                disposition=ActorTurnDisposition.CONCLUDE_TURN,
            ),
        )

    def _reject_before_dispatch_locked(self, entry: _RequestEntry, failure: _Failure) -> None:
        if entry.state is not _RequestState.IN_FLIGHT or entry.dispatched_at is not None:
            return
        self._budget_reserved -= 1
        entry.state = _RequestState.COMPLETED
        entry.completed_at = datetime.now(UTC)
        entry.failure = failure
        self._active_request_ids.discard(entry.request.request_id)
        self._advance_dispatch_sequence_locked()
        self._append_completion_locked(entry, result=None, failure=entry.failure, late_ignored=False)
        self._condition.notify_all()

    def _advance_dispatch_sequence_locked(self) -> None:
        while self._next_dispatch_sequence < self._next_action_sequence:
            current = next(
                (entry for entry in self._requests.values() if entry.action_sequence == self._next_dispatch_sequence),
                None,
            )
            if current is not None and current.state is _RequestState.IN_FLIGHT:
                break
            self._next_dispatch_sequence += 1

    def _append_completion_locked(
        self,
        entry: _RequestEntry,
        *,
        result: WorldActorActionResult | None,
        failure: _Failure | None,
        late_ignored: bool,
    ) -> None:
        receipt = result.task_receipt if result is not None else None
        self._append_evidence(
            {
                "record_type": "completion",
                "request_id": entry.request.request_id,
                "action_sequence": entry.action_sequence,
                "completed_at": datetime.now(UTC).isoformat(),
                "request_state": entry.state.value,
                "result_sha256": _json_sha256(result.model_dump(mode="json")) if result is not None else None,
                "result_bytes": len(_json_bytes(result.model_dump(mode="json"))) if result is not None else None,
                "error_code": failure.code if failure is not None else None,
                "error_sha256": _failure_sha256(failure) if failure is not None else None,
                "task_receipt_sha256": _json_sha256(receipt) if receipt is not None else None,
                "task_receipt_identity": _task_receipt_identity(receipt),
                "terminal_latched": self._terminal and self._terminal_action_sequence == entry.action_sequence,
                "late_ignored": late_ignored,
            }
        )

    def _append_rejection(
        self,
        request: ActorInvocationRequest,
        fingerprint: str,
        error: ActorInvocationError,
    ) -> None:
        if self._lifecycle is ActorInvocationLifecycle.CREATED:
            return
        self._append_evidence(
            {
                "record_type": "request-rejected",
                "request_id": request.request_id,
                "request_fingerprint": fingerprint,
                "action_name": request.action_name,
                "transport": request.transport,
                "correlation": request.correlation.model_dump(mode="json"),
                "error_code": error.code,
                "outcome": error.outcome.value,
                "budget_used": self._budget_used,
                "budget_reserved": self._budget_reserved,
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )

    def _append_read_error(
        self,
        operation: str,
        correlation: ActorCorrelation,
        error: ActorInvocationError,
        occurred_at: datetime,
    ) -> None:
        self._append_evidence(
            {
                "record_type": operation,
                "correlation": correlation.model_dump(mode="json"),
                "occurred_at": occurred_at.isoformat(),
                "error_code": error.code,
                "error_sha256": _text_sha256(error.detail),
                "outcome": error.outcome.value,
            }
        )

    def _append_evidence(self, record: dict[str, Any]) -> None:
        with self._evidence_lock:
            self._evidence_sequence += 1
            payload = {
                "sequence": self._evidence_sequence,
                "schema": ACTOR_INVOCATION_EVIDENCE_SCHEMA,
                "authority_id": self.authority_id,
                "actor_principal_id": self.config.actor_principal_id,
                **record,
            }
            with self.config.evidence_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

    def _require_readable(self) -> None:
        with self._condition:
            if self._lifecycle is not ActorInvocationLifecycle.RUNNING:
                raise self._lifecycle_error()

    def _require_catalogue_stable(self) -> None:
        current = self._host.capabilities()
        current_hash = _json_sha256(current.model_dump(mode="json"))
        with self._condition:
            expected = self._catalogue_hash
        if current_hash != expected:
            raise ActorInvocationError(
                "actor-catalogue-drift",
                "The world actor capability catalogue changed during the trial.",
                outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                disposition=ActorTurnDisposition.CONCLUDE_TURN,
            )

    def _lifecycle_error(self, request_id: str | None = None) -> ActorInvocationError:
        if self._lifecycle is ActorInvocationLifecycle.CREATED:
            code = "actor-authority-not-started"
            detail = "The actor invocation authority is not started."
        else:
            code = "actor-authority-closing"
            detail = "The actor invocation authority is closing or closed."
        return ActorInvocationError(
            code,
            detail,
            outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
            request_id=request_id,
            disposition=ActorTurnDisposition.CONCLUDE_TURN,
        )

    def _unknown_request_ids_locked(self) -> tuple[str, ...]:
        return tuple(
            sorted(request_id for request_id, entry in self._requests.items() if entry.state is _RequestState.UNKNOWN)
        )

    @staticmethod
    def _is_unknown(entry: _RequestEntry) -> bool:
        """Read state after another thread could have changed it during dispatch."""
        return entry.state is _RequestState.UNKNOWN


def _request_fingerprint(actor_principal_id: str, request: ActorInvocationRequest) -> str:
    return _json_sha256(
        {
            "semantics": ACTOR_INVOCATION_SEMANTICS,
            "actor_principal_id": actor_principal_id,
            "decision_id": request.decision_id,
            "action_name": request.action_name,
            "arguments": request.arguments,
        }
    )


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _failure_sha256(failure: _Failure) -> str:
    return _json_sha256(
        {
            "code": failure.code,
            "detail": failure.detail,
            "outcome": failure.outcome.value,
            "disposition": failure.disposition.value,
        }
    )


def _task_receipt_identity(receipt: dict[str, JsonValue] | None) -> JsonValue | None:
    if receipt is None:
        return None
    for key in ("receipt_id", "transition_id", "content_id", "commit_id"):
        value = receipt.get(key)
        if isinstance(value, str | int) and not isinstance(value, bool):
            return value
    return None
