# ABOUTME: Connects one Prime process to one Interactive World actor host.
# ABOUTME: Owns scoped transport, action limits, and safe evidence without interpreting world state.

from __future__ import annotations

import hmac
import json
import os
import secrets
import socketserver
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import JsonValue, ValidationError

from aec_bench.contracts.continual_world import ContinualWorldActorRequest
from aec_bench.contracts.validators import StrictModel
from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.prime_agent.skills import WORLD_ACTOR_CAPABILITY_ENV, WORLD_ACTOR_SOCKET_ENV

_MAX_MESSAGE_BYTES = 1024 * 1024


class _WorldActorHost(Protocol):
    """The existing actor surface supplied by one concrete world."""

    def capabilities(self) -> WorldActorCapabilityCatalogue: ...

    def observe(self) -> WorldActorObservation: ...

    def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult: ...


class PrimeActorEndpointError(RuntimeError):
    """Raised when the scoped Prime actor endpoint cannot operate safely."""


class _TransportRequest(StrictModel):
    capability: str
    request: ContinualWorldActorRequest


class _TransportError(StrictModel):
    code: str
    detail: str


class _TransportResponse(StrictModel):
    result: dict[str, JsonValue] | None = None
    error: _TransportError | None = None


class _ThreadedUnixServer(socketserver.ThreadingUnixStreamServer):
    # Closure must wait for every actor request. A late request must not change
    # world state after the Prime session has ended.
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = False


class _RequestHandler(socketserver.StreamRequestHandler):
    server: _EndpointServer

    def handle(self) -> None:
        received_at = datetime.now(UTC)
        line = self.rfile.readline(_MAX_MESSAGE_BYTES + 1)
        if len(line) > _MAX_MESSAGE_BYTES:
            self.server.owner._reject_transport(
                self.wfile,
                received_at=received_at,
                error=("request-too-large", "actor request is too large"),
            )
            return
        if not line or not line.endswith(b"\n"):
            self.server.owner._reject_transport(
                self.wfile,
                received_at=received_at,
                error=("transport-malformed", "actor request must be one line"),
            )
            return
        self.server.owner._handle_request(line, self.wfile, received_at=received_at)


class _EndpointServer(_ThreadedUnixServer):
    owner: PrimeActorEndpoint


class PrimeActorEndpoint:
    """Expose one world actor host to one composite Prime actor."""

    def __init__(
        self,
        *,
        host: _WorldActorHost,
        socket_directory: Path,
        max_world_actions: int,
        evidence_file: Path,
    ) -> None:
        if max_world_actions < 1:
            raise ValueError("Prime world max_world_actions must be positive")
        requested_socket_directory = socket_directory.resolve()
        requested_socket = requested_socket_directory / "actor.sock"
        self._owns_socket_directory = len(os.fsencode(requested_socket)) > 100
        short_root = Path("/private/tmp") if Path("/private/tmp").is_dir() else Path("/tmp")
        self._socket_directory = (
            Path(tempfile.mkdtemp(prefix="aecbench-prime-actor-", dir=short_root)).resolve()
            if self._owns_socket_directory
            else requested_socket_directory
        )
        self._socket_path = self._socket_directory / "actor.sock"
        self._host = host
        self._max_world_actions = max_world_actions
        self._evidence_file = evidence_file.resolve()
        self._capability = secrets.token_urlsafe(32)
        self._server: _EndpointServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._sequence = 0
        self._world_action_attempts = 0
        self._world_action_limit_reached = False
        self._world_action_requests: dict[str, str] = {}
        self._last_action_result: WorldActorActionResult | None = None

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    @property
    def last_action_result(self) -> WorldActorActionResult | None:
        return self._last_action_result

    @property
    def world_action_attempts(self) -> int:
        return self._world_action_attempts

    @property
    def world_action_limit_reached(self) -> bool:
        return self._world_action_limit_reached

    def start(self) -> None:
        if self._server is not None:
            raise PrimeActorEndpointError("Prime actor endpoint is already running")
        self._socket_directory.mkdir(parents=True, exist_ok=True)
        self._socket_directory.chmod(0o700)
        if self._socket_path.exists() or self._socket_path.is_symlink():
            raise PrimeActorEndpointError("Prime actor socket path already exists")
        self._evidence_file.parent.mkdir(parents=True, exist_ok=True)
        self._evidence_file.write_bytes(b"")
        server = _EndpointServer(str(self._socket_path), _RequestHandler)
        self._socket_path.chmod(0o600)
        server.owner = self
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, name="prime-actor-endpoint", daemon=True)
        self._thread.start()

    def close(self) -> None:
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        self._socket_path.unlink(missing_ok=True)
        if self._owns_socket_directory:
            self._socket_directory.rmdir()

    def connection_environment(self) -> dict[str, str]:
        if self._server is None:
            raise PrimeActorEndpointError("Prime actor endpoint is not running")
        return {
            WORLD_ACTOR_SOCKET_ENV: str(self._socket_path),
            WORLD_ACTOR_CAPABILITY_ENV: self._capability,
        }

    def __enter__(self) -> PrimeActorEndpoint:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _handle_request(self, line: bytes, writer: Any, *, received_at: datetime) -> None:
        request: ContinualWorldActorRequest | None = None
        operation: str | None = None
        try:
            raw = json.loads(line)
            operation = _safe_operation(raw)
            envelope = _TransportRequest.model_validate(raw)
            if not hmac.compare_digest(envelope.capability, self._capability):
                self._record(
                    request=None,
                    operation=operation,
                    received_at=received_at,
                    error={"code": "actor-unauthorized", "detail": "actor capability is invalid"},
                )
                self._write_response(writer, error=("actor-unauthorized", "actor capability is invalid"))
                return
            request = envelope.request
            operation = request.operation
            if request.operation == "invoke" and not self._authorize_world_action(request):
                error = ("world-action-budget-exhausted", "world action budget is exhausted")
                self._record(
                    request=request,
                    operation=operation,
                    received_at=received_at,
                    error={"code": error[0], "detail": error[1]},
                )
                self._write_response(writer, error=error)
                return
            result = self._dispatch(request)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            self._record(
                request=None,
                operation=operation,
                received_at=received_at,
                error={"code": "actor-request-invalid", "detail": "actor request does not match the contract"},
            )
            self._write_response(writer, error=("actor-request-invalid", "actor request does not match the contract"))
            return
        except WorldInterfaceError as error:
            self._record(
                request=request,
                operation=operation,
                received_at=received_at,
                error={"code": error.code, "detail": error.detail},
            )
            self._write_response(writer, error=(error.code, error.detail))
            return
        except Exception:
            self._record(
                request=request,
                operation=operation,
                received_at=received_at,
                error={"code": "actor-endpoint-failed", "detail": "host actor call failed"},
            )
            self._write_response(writer, error=("actor-endpoint-failed", "host actor call failed"))
            return
        payload = result.model_dump(mode="json")
        self._record(request=request, operation=operation, received_at=received_at, result=payload)
        self._write_response(writer, result=payload)

    def _authorize_world_action(self, request: ContinualWorldActorRequest) -> bool:
        assert request.request_id is not None
        fingerprint = request.model_dump_json()
        with self._lock:
            if self._world_action_requests.get(request.request_id) == fingerprint:
                return True
            self._world_action_attempts += 1
            if self._world_action_attempts > self._max_world_actions:
                self._world_action_limit_reached = True
                return False
            self._world_action_requests.setdefault(request.request_id, fingerprint)
            if self._world_action_attempts == self._max_world_actions:
                self._world_action_limit_reached = True
            return True

    def _dispatch(self, request: ContinualWorldActorRequest) -> StrictModel:
        if request.operation == "capabilities":
            return self._host.capabilities()
        if request.operation == "observe":
            return self._host.observe()
        assert request.request_id is not None
        assert request.decision_id is not None
        assert request.action_name is not None
        assert request.arguments is not None
        result = self._host.invoke(
            WorldActorActionRequest(
                request_id=request.request_id,
                decision_id=request.decision_id,
                action_name=request.action_name,
                arguments=request.arguments,
            )
        )
        with self._lock:
            self._last_action_result = result
        return result

    def _reject_transport(self, writer: Any, *, received_at: datetime, error: tuple[str, str]) -> None:
        self._record(
            request=None,
            operation=None,
            received_at=received_at,
            error={"code": error[0], "detail": error[1]},
        )
        self._write_response(writer, error=error)

    def _record(
        self,
        *,
        request: ContinualWorldActorRequest | None,
        operation: str | None,
        received_at: datetime,
        result: dict[str, JsonValue] | None = None,
        error: dict[str, JsonValue] | None = None,
    ) -> None:
        with self._lock:
            self._sequence += 1
            event: dict[str, JsonValue] = {
                "sequence": self._sequence,
                "received_at": received_at.isoformat(),
                "operation": operation,
                "request": request.model_dump(mode="json") if request is not None else None,
                "result": result,
                "error": error,
            }
            with self._evidence_file.open("ab") as sink:
                sink.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n")

    @staticmethod
    def _write_response(
        writer: Any,
        *,
        result: dict[str, JsonValue] | None = None,
        error: tuple[str, str] | None = None,
    ) -> None:
        response = _TransportResponse(
            result=result,
            error=None if error is None else _TransportError(code=error[0], detail=error[1]),
        )
        writer.write(response.model_dump_json(exclude_none=True).encode("utf-8") + b"\n")
        writer.flush()


def _safe_operation(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    request = value.get("request")
    if not isinstance(request, dict):
        return None
    operation = request.get("operation")
    return operation if operation in {"capabilities", "observe", "invoke"} else None


__all__ = ["PrimeActorEndpoint", "PrimeActorEndpointError"]
