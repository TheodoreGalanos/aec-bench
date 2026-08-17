# ABOUTME: Exposes one actor invocation authority through a versioned local Unix-socket protocol.
# ABOUTME: Owns only authenticated framing, transport evidence, connection lifecycle, and safe close.

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socketserver
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, BinaryIO, cast

from pydantic import JsonValue, ValidationError

from aec_bench.contracts.world_interface import WorldActorActionResult
from aec_bench.harness.world_actor.authority import (
    ActorCorrelation,
    ActorInvocationAuthority,
    ActorInvocationError,
    ActorInvocationLifecycle,
    ActorInvocationOutcomeClass,
    ActorInvocationRequest,
    AuthorityCloseReport,
)
from aec_bench.harness.world_actor.protocol import (
    WORLD_ACTOR_CAPABILITY_ENV,
    WORLD_ACTOR_PROTOCOL,
    WORLD_ACTOR_PROTOCOL_ENV,
    WORLD_ACTOR_SOCKET_ENV,
    WORLD_ACTOR_TRANSPORT_EVIDENCE_SCHEMA,
    WorldActorInvokeRequest,
    WorldActorTransportError,
    WorldActorTransportFailure,
    WorldActorTransportRequest,
    WorldActorTransportSuccess,
)

_DEFAULT_MAX_REQUEST_BYTES = 1024 * 1024
_DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_DEFAULT_REQUEST_TIMEOUT_SEC = 5.0


class WorldActorEndpointLifecycle(StrEnum):
    """Lifecycle of one scoped local actor endpoint."""

    CREATED = "created"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"


class WorldActorEndpointError(RuntimeError):
    """Raised when the versioned actor endpoint cannot operate safely."""


@dataclass(frozen=True, slots=True)
class WorldActorEndpointCloseReport:
    """State whether transport and semantic authority closed completely."""

    complete: bool
    quiescent: bool
    lifecycle: WorldActorEndpointLifecycle
    authority: AuthorityCloseReport
    unsettled_transport_request_ids: tuple[str, ...]
    server_thread_stopped: bool
    closed_at: datetime


class _ThreadedUnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False


class _RequestHandler(socketserver.StreamRequestHandler):
    server: _EndpointServer

    def handle(self) -> None:
        owner = self.server.owner
        connection_id = owner._begin_transport()
        try:
            self._handle_connection(owner, connection_id=connection_id)
        finally:
            owner._end_transport(connection_id)

    def _handle_connection(self, owner: WorldActorEndpoint, *, connection_id: str) -> None:
        self.connection.settimeout(owner.request_timeout_sec)
        received_at = datetime.now(UTC)
        try:
            line = self.rfile.readline(owner.max_request_bytes + 2)
        except TimeoutError:
            owner._reject_transport(
                cast(BinaryIO, self.wfile),
                received_at=received_at,
                transport_request_id="unavailable",
                operation=None,
                code="transport-incomplete",
                detail="The world actor request line is incomplete.",
            )
            return
        transport_request_id, _ = _safe_request_labels(line)
        owner._label_transport(connection_id, transport_request_id)
        if len(line) > owner.max_request_bytes + 1:
            owner._reject_transport(
                cast(BinaryIO, self.wfile),
                received_at=received_at,
                transport_request_id="unavailable",
                operation=None,
                code="request-too-large",
                detail="The world actor request is too large.",
            )
            return
        if not line or not line.endswith(b"\n"):
            owner._reject_transport(
                cast(BinaryIO, self.wfile),
                received_at=received_at,
                transport_request_id="unavailable",
                operation=None,
                code="transport-incomplete",
                detail="The world actor request must end with one newline.",
            )
            return
        try:
            self.connection.settimeout(0.01)
            trailing = self.rfile.read1(owner.max_request_bytes + 1)
        except TimeoutError:
            trailing = b""
        finally:
            self.connection.settimeout(owner.request_timeout_sec)
        if len(trailing) > owner.max_request_bytes or trailing.strip():
            transport_request_id, operation = _safe_request_labels(line)
            owner._reject_transport(
                cast(BinaryIO, self.wfile),
                received_at=received_at,
                transport_request_id=transport_request_id,
                operation=operation,
                code="transport-trailing-data",
                detail="The world actor request contains trailing data.",
            )
            return
        owner._handle_request(line, cast(BinaryIO, self.wfile), received_at=received_at)


class _EndpointServer(_ThreadedUnixServer):
    owner: WorldActorEndpoint


class WorldActorEndpoint:
    """Expose one provider-neutral authority to one scoped process actor."""

    def __init__(
        self,
        *,
        authority: ActorInvocationAuthority,
        socket_directory: Path,
        evidence_file: Path,
        max_request_bytes: int = _DEFAULT_MAX_REQUEST_BYTES,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        request_timeout_sec: float = _DEFAULT_REQUEST_TIMEOUT_SEC,
        endpoint_id: str | None = None,
    ) -> None:
        if isinstance(max_request_bytes, bool) or max_request_bytes < 1024:
            raise ValueError("world actor maximum request bytes must be at least 1024")
        if isinstance(max_response_bytes, bool) or max_response_bytes < 1024:
            raise ValueError("world actor maximum response bytes must be at least 1024")
        if request_timeout_sec <= 0:
            raise ValueError("world actor request timeout must be positive")
        resolved_endpoint_id = endpoint_id.strip() if endpoint_id is not None else None
        if endpoint_id is not None and not resolved_endpoint_id:
            raise ValueError("world actor endpoint ID must not be blank")

        requested_directory = Path(socket_directory).absolute()
        requested_socket = requested_directory / "actor.sock"
        self._owns_fallback_directory = len(os.fsencode(requested_socket)) > 100
        short_root = Path("/private/tmp") if Path("/private/tmp").is_dir() else Path("/tmp")
        self._requested_socket_directory = requested_directory
        self._socket_directory = (
            short_root / f"aecbench-world-actor-{uuid.uuid4().hex}"
            if self._owns_fallback_directory
            else requested_directory
        )
        self._socket_path = self._socket_directory / "actor.sock"
        self._authority = authority
        self._evidence_file = Path(evidence_file).resolve()
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self.request_timeout_sec = request_timeout_sec
        self.endpoint_id = resolved_endpoint_id or f"world-actor-endpoint-{uuid.uuid4().hex}"
        self._capability = secrets.token_urlsafe(32)
        self._server: _EndpointServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Condition(threading.Lock())
        self._lifecycle = WorldActorEndpointLifecycle.CREATED
        self._evidence_sequence = 0
        self._active_transport_requests: dict[str, str] = {}
        self._successful_close_report: WorldActorEndpointCloseReport | None = None

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    @property
    def lifecycle(self) -> WorldActorEndpointLifecycle:
        with self._lock:
            return self._lifecycle

    @property
    def last_action_result(self) -> WorldActorActionResult | None:
        return self._authority.last_action_result

    @property
    def world_action_count(self) -> int:
        return self._authority.world_action_count

    @property
    def world_action_limit_reached(self) -> bool:
        return self._authority.world_action_limit_reached

    def start(self) -> None:
        """Start the semantic authority, bind the socket, and accept requests."""
        with self._lock:
            if self._lifecycle is not WorldActorEndpointLifecycle.CREATED:
                raise WorldActorEndpointError("world actor endpoint can start only once")
        if self._authority.lifecycle is not ActorInvocationLifecycle.CREATED:
            raise WorldActorEndpointError("world actor authority must be new when the endpoint starts")
        requested = self._requested_socket_directory
        if requested.exists() or requested.is_symlink():
            raise WorldActorEndpointError("world actor socket directory already exists")
        if self._socket_path.exists() or self._socket_path.is_symlink():
            raise WorldActorEndpointError("world actor socket path already exists")
        if self._socket_directory.exists() or self._socket_directory.is_symlink():
            raise WorldActorEndpointError("world actor socket directory already exists")
        server: _EndpointServer | None = None
        try:
            self._socket_directory.mkdir(mode=0o700, parents=False, exist_ok=False)
            self._socket_directory.chmod(0o700)
            self._start_evidence()
            server = _EndpointServer(str(self._socket_path), _RequestHandler)
            self._socket_path.chmod(0o600)
            server.owner = self
            self._authority.start()
            thread = threading.Thread(target=server.serve_forever, name="world-actor-endpoint", daemon=True)
            with self._lock:
                self._server = server
                self._thread = thread
                self._lifecycle = WorldActorEndpointLifecycle.RUNNING
            thread.start()
        except Exception:
            if server is not None:
                server.server_close()
            self._socket_path.unlink(missing_ok=True)
            self._remove_socket_directory()
            raise

    def close(self, *, timeout_sec: float | None = None) -> WorldActorEndpointCloseReport:
        """Stop new connections and close transport and authority with explicit status."""
        with self._lock:
            if self._successful_close_report is not None:
                return self._successful_close_report
            if self._lifecycle is WorldActorEndpointLifecycle.CREATED:
                raise WorldActorEndpointError("world actor endpoint is not started")
            self._lifecycle = WorldActorEndpointLifecycle.CLOSING
            server = self._server
            thread = self._thread
        if server is not None:
            server.shutdown()
        authority_report = self._authority.close(timeout_sec=timeout_sec)
        if server is not None:
            server.server_close()
        transport_timeout = self._authority.config.close_timeout_sec if timeout_sec is None else timeout_sec
        transport_deadline = time.monotonic() + transport_timeout
        with self._lock:
            while self._active_transport_requests:
                remaining = transport_deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._lock.wait(remaining)
        if thread is not None:
            thread.join(timeout=2.0)
        server_thread_stopped = thread is None or not thread.is_alive()
        self._socket_path.unlink(missing_ok=True)
        self._remove_socket_directory()
        with self._lock:
            unsettled_transport = tuple(sorted(self._active_transport_requests.values()))
            complete = authority_report.complete and not unsettled_transport and server_thread_stopped
            quiescent = authority_report.quiescent and not unsettled_transport and server_thread_stopped
            lifecycle = WorldActorEndpointLifecycle.CLOSED if quiescent else WorldActorEndpointLifecycle.CLOSING
            self._lifecycle = lifecycle
            self._server = None
            self._thread = None if server_thread_stopped else thread
            report = WorldActorEndpointCloseReport(
                complete=complete,
                quiescent=quiescent,
                lifecycle=lifecycle,
                authority=authority_report,
                unsettled_transport_request_ids=unsettled_transport,
                server_thread_stopped=server_thread_stopped,
                closed_at=datetime.now(UTC),
            )
            if report.complete:
                self._successful_close_report = report
        self._append_evidence(
            {
                "record_type": "close",
                "closed_at": report.closed_at.isoformat(),
                "lifecycle": report.lifecycle.value,
                "complete": report.complete,
                "quiescent": report.quiescent,
                "authority_lifecycle": report.authority.lifecycle.value,
                "authority_complete": report.authority.complete,
                "unsettled_transport_request_ids": list(report.unsettled_transport_request_ids),
                "unsettled_authority_request_ids": list(report.authority.unsettled_request_ids),
                "unknown_authority_request_ids": list(report.authority.unknown_outcome_request_ids),
                "server_thread_stopped": report.server_thread_stopped,
            }
        )
        return report

    def connection_environment(self) -> dict[str, str]:
        """Return the exact scoped descriptor for an actor process."""
        with self._lock:
            if self._lifecycle is not WorldActorEndpointLifecycle.RUNNING:
                raise WorldActorEndpointError("world actor endpoint is not running")
        return {
            WORLD_ACTOR_SOCKET_ENV: str(self._socket_path),
            WORLD_ACTOR_CAPABILITY_ENV: self._capability,
            WORLD_ACTOR_PROTOCOL_ENV: WORLD_ACTOR_PROTOCOL,
        }

    def __enter__(self) -> WorldActorEndpoint:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        report = self.close()
        if exc is None and not report.complete:
            raise WorldActorEndpointError("world actor endpoint did not close completely")

    def _handle_request(self, line: bytes, writer: BinaryIO, *, received_at: datetime) -> None:
        transport_request_id, operation = _safe_request_labels(line)
        request_id: str | None = None
        action_sequence: int | None = None
        response: WorldActorTransportSuccess | WorldActorTransportFailure
        try:
            raw = json.loads(line.decode("utf-8"))
            envelope = WorldActorTransportRequest.model_validate(raw)
            transport_request_id = envelope.transport_request_id
            operation = envelope.request.operation
            if not hmac.compare_digest(envelope.capability, self._capability):
                raise ActorInvocationError(
                    "actor-unauthorized",
                    "The actor capability is invalid.",
                    outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                )
            with self._lock:
                if self._lifecycle is not WorldActorEndpointLifecycle.RUNNING:
                    raise ActorInvocationError(
                        "actor-endpoint-closing",
                        "The world actor endpoint is closing.",
                        outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
                    )
            correlation = ActorCorrelation(transport_request_id=transport_request_id)
            result_payload: dict[str, JsonValue]
            if operation == "capabilities":
                result_payload = self._authority.capabilities(correlation=correlation).model_dump(mode="json")
            elif operation == "observe":
                result_payload = self._authority.observe(correlation=correlation).model_dump(mode="json")
            else:
                invoke = envelope.request
                assert isinstance(invoke, WorldActorInvokeRequest)
                request_id = invoke.request_id
                outcome = self._authority.invoke(
                    ActorInvocationRequest(
                        request_id=invoke.request_id,
                        decision_id=invoke.decision_id,
                        action_name=invoke.action_name,
                        arguments=invoke.arguments,
                        transport="world-actor-endpoint",
                        correlation=correlation,
                    )
                )
                action_sequence = outcome.action_sequence
                result_payload = outcome.result.model_dump(mode="json")
            response = WorldActorTransportSuccess(
                transport_request_id=transport_request_id,
                result=result_payload,
            )
        except UnicodeDecodeError:
            response = _failure(
                transport_request_id,
                code="transport-invalid-utf8",
                detail="The world actor request is not valid UTF-8.",
                outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
            )
        except json.JSONDecodeError:
            response = _failure(
                transport_request_id,
                code="transport-invalid-json",
                detail="The world actor request is not valid JSON.",
                outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
            )
        except ValidationError:
            code = "actor-protocol-unsupported" if _unsupported_protocol(line) else "actor-request-invalid"
            detail = (
                "The world actor protocol version is not supported."
                if code == "actor-protocol-unsupported"
                else "The world actor request does not match the protocol."
            )
            response = _failure(
                transport_request_id,
                code=code,
                detail=detail,
                outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
            )
        except ActorInvocationError as error:
            request_id = error.request_id or request_id
            action_sequence = error.action_sequence
            response = _failure(
                transport_request_id,
                code=error.code,
                detail=error.detail,
                outcome=error.outcome,
                request_id=request_id,
                retryable=error.code == "decision-stale",
            )
        except Exception:
            response = _failure(
                transport_request_id,
                code="actor-endpoint-failed",
                detail="The world actor endpoint failed.",
                outcome=(
                    ActorInvocationOutcomeClass.UNKNOWN
                    if operation == "invoke"
                    else ActorInvocationOutcomeClass.NOT_DISPATCHED
                ),
                request_id=request_id,
            )
        response = self._bounded_response(response, request_id=request_id)
        self._record_response(
            response=response,
            operation=operation,
            received_at=received_at,
            action_sequence=action_sequence,
        )
        self._write_response(writer, response)

    def _begin_transport(self) -> str:
        connection_id = f"connection-{uuid.uuid4().hex}"
        with self._lock:
            self._active_transport_requests[connection_id] = connection_id
        return connection_id

    def _label_transport(self, connection_id: str, transport_request_id: str) -> None:
        if transport_request_id == "unavailable":
            return
        with self._lock:
            if connection_id in self._active_transport_requests:
                self._active_transport_requests[connection_id] = transport_request_id

    def _end_transport(self, connection_id: str) -> None:
        with self._lock:
            self._active_transport_requests.pop(connection_id, None)
            self._lock.notify_all()

    def _reject_transport(
        self,
        writer: BinaryIO,
        *,
        received_at: datetime,
        transport_request_id: str,
        operation: str | None,
        code: str,
        detail: str,
    ) -> None:
        response = _failure(
            transport_request_id,
            code=code,
            detail=detail,
            outcome=ActorInvocationOutcomeClass.NOT_DISPATCHED,
        )
        self._write_response(writer, response)
        self._record_response(response=response, operation=operation, received_at=received_at, action_sequence=None)

    def _bounded_response(
        self,
        response: WorldActorTransportSuccess | WorldActorTransportFailure,
        *,
        request_id: str | None,
    ) -> WorldActorTransportSuccess | WorldActorTransportFailure:
        if len(_response_bytes(response)) <= self.max_response_bytes:
            return response
        return _failure(
            response.transport_request_id,
            code="response-too-large",
            detail="The world actor response is too large.",
            outcome=ActorInvocationOutcomeClass.COMPLETED,
            request_id=request_id,
        )

    @staticmethod
    def _write_response(writer: BinaryIO, response: WorldActorTransportSuccess | WorldActorTransportFailure) -> None:
        writer.write(_response_bytes(response) + b"\n")
        writer.flush()

    def _record_response(
        self,
        *,
        response: WorldActorTransportSuccess | WorldActorTransportFailure,
        operation: str | None,
        received_at: datetime,
        action_sequence: int | None,
    ) -> None:
        response_payload = response.model_dump(mode="json", exclude_none=True)
        self._append_evidence(
            {
                "record_type": "transport-response",
                "transport_request_id": response.transport_request_id,
                "operation": operation,
                "received_at": received_at.isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "ok": response.ok,
                "authority_action_sequence": action_sequence,
                "response_sha256": _json_sha256(response_payload),
                "error_code": response.error.code if isinstance(response, WorldActorTransportFailure) else None,
                "response_outcome": (
                    response.error.outcome.value if isinstance(response, WorldActorTransportFailure) else "completed"
                ),
            }
        )

    def _start_evidence(self) -> None:
        self._evidence_file.parent.mkdir(parents=True, exist_ok=True)
        if self._evidence_file.exists() or self._evidence_file.is_symlink():
            raise WorldActorEndpointError("world actor transport evidence already exists")
        header = {
            "sequence": 1,
            "record_type": "header",
            "schema": WORLD_ACTOR_TRANSPORT_EVIDENCE_SCHEMA,
            "protocol": WORLD_ACTOR_PROTOCOL,
            "endpoint_id": self.endpoint_id,
            "actor_principal_id": self._authority.config.actor_principal_id,
            "authority_id": self._authority.authority_id,
            "socket_identity_sha256": hashlib.sha256(str(self._socket_path).encode("utf-8")).hexdigest(),
            "max_request_bytes": self.max_request_bytes,
            "max_response_bytes": self.max_response_bytes,
            "started_at": datetime.now(UTC).isoformat(),
        }
        with self._evidence_file.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(header, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._evidence_file.chmod(0o600)
        self._evidence_sequence = 1

    def _append_evidence(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._evidence_sequence += 1
            payload = {
                "sequence": self._evidence_sequence,
                "schema": WORLD_ACTOR_TRANSPORT_EVIDENCE_SCHEMA,
                "protocol": WORLD_ACTOR_PROTOCOL,
                "endpoint_id": self.endpoint_id,
                "actor_principal_id": self._authority.config.actor_principal_id,
                "authority_id": self._authority.authority_id,
                **record,
            }
            with self._evidence_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

    def _remove_socket_directory(self) -> None:
        try:
            self._socket_directory.rmdir()
        except FileNotFoundError:
            pass
        except OSError as error:
            raise WorldActorEndpointError("world actor socket directory is not empty after close") from error


def _failure(
    transport_request_id: str,
    *,
    code: str,
    detail: str,
    outcome: ActorInvocationOutcomeClass,
    request_id: str | None = None,
    retryable: bool = False,
) -> WorldActorTransportFailure:
    return WorldActorTransportFailure(
        transport_request_id=transport_request_id,
        error=WorldActorTransportError(
            code=code,
            detail=detail,
            outcome=outcome,
            request_id=request_id,
            retryable=retryable,
        ),
    )


def _response_bytes(response: WorldActorTransportSuccess | WorldActorTransportFailure) -> bytes:
    return response.model_dump_json(exclude_none=True).encode("utf-8")


def _safe_request_labels(line: bytes) -> tuple[str, str | None]:
    try:
        raw = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "unavailable", None
    if not isinstance(raw, dict):
        return "unavailable", None
    transport_request_id = raw.get("transport_request_id")
    safe_transport_id = (
        transport_request_id if isinstance(transport_request_id, str) and transport_request_id else "unavailable"
    )
    request = raw.get("request")
    operation = request.get("operation") if isinstance(request, dict) else None
    safe_operation = operation if operation in {"capabilities", "observe", "invoke"} else None
    return safe_transport_id, safe_operation


def _unsupported_protocol(line: bytes) -> bool:
    try:
        raw = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(raw, dict) and raw.get("protocol") != WORLD_ACTOR_PROTOCOL


def _json_sha256(value: dict[str, JsonValue]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "WorldActorEndpoint",
    "WorldActorEndpointCloseReport",
    "WorldActorEndpointError",
    "WorldActorEndpointLifecycle",
]
