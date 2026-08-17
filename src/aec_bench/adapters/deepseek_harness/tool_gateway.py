# ABOUTME: Exposes one exact AEC-owned native tool surface on an authenticated Unix socket.
# ABOUTME: Supplies trusted invocation identity, cancellation, dispositions, and bounded close evidence.

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import socketserver
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import Field, JsonValue

from aec_bench.contracts.validators import NonEmptyStr, StrictModel

TOOL_GATEWAY_PROTOCOL = "aec-bench/deepseek-tools/2"
TOOL_GATEWAY_SOCKET_ENV = "DSH_TOOLS_SOCKET"
TOOL_GATEWAY_TOKEN_ENV = "DSH_TOOLS_TOKEN"
TOOL_GATEWAY_MANIFEST_ENV = "DSH_TOOLS"
_MAX_REQUEST_BYTES = 1024 * 1024
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_TOOL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


class NativeToolDisposition(StrEnum):
    """Tell the provider loop whether the current model turn can continue."""

    CONTINUE = "continue"
    CONCLUDE_TURN = "conclude-turn"


class NativeToolRequestSemantics(StrEnum):
    """Select the one component that owns logical request admission and replay."""

    GATEWAY = "gateway"
    HANDLER_AUTHORITY = "handler-authority"


class NativeCancellation:
    """Expose cooperative cancellation to one synchronous AEC handler."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._requested_at: datetime | None = None

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def requested_at(self) -> datetime | None:
        with self._lock:
            return self._requested_at

    def wait(self, timeout: float | None = None) -> bool:
        """Wait until cancellation or the optional timeout."""
        return self._event.wait(timeout)

    def _cancel(self) -> datetime:
        with self._lock:
            if self._requested_at is None:
                self._requested_at = datetime.now(UTC)
            requested_at = self._requested_at
        self._event.set()
        return requested_at


@dataclass(frozen=True)
class NativeToolInvocation:
    """AEC-created identity and lifecycle state hidden from the model schema."""

    request_id: str
    deepseek_session_id: str
    deepseek_tool_call_id: str
    model_turn: int
    tool_name: str
    generation_id: str
    admitted_at: datetime
    cancellation: NativeCancellation


@dataclass(frozen=True)
class NativeToolResponse:
    """Return one JSON result and generic provider-loop disposition."""

    result: JsonValue
    disposition: NativeToolDisposition = NativeToolDisposition.CONTINUE


NativeToolHandler = Callable[[NativeToolInvocation, Mapping[str, JsonValue]], NativeToolResponse]


@dataclass(frozen=True)
class NativeToolDefinition:
    """Define the exact model-facing schema and its AEC-owned handler."""

    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: NativeToolHandler
    request_semantics: NativeToolRequestSemantics = NativeToolRequestSemantics.GATEWAY


def json_native_tool_definition(
    *,
    name: str,
    description: str,
    parameters_schema: dict[str, Any],
    function: Callable[..., str],
    trusted_request_argument: str | None = None,
    disposition: Callable[[JsonValue], NativeToolDisposition] | None = None,
) -> NativeToolDefinition:
    """Bind an existing JSON-returning AEC method to one explicit model schema."""

    def handle(invocation: NativeToolInvocation, arguments: Mapping[str, JsonValue]) -> NativeToolResponse:
        call_arguments = dict(arguments)
        if trusted_request_argument is not None:
            call_arguments[trusted_request_argument] = invocation.request_id
        result = json.loads(function(**call_arguments))
        resolved_disposition = disposition(result) if disposition is not None else NativeToolDisposition.CONTINUE
        return NativeToolResponse(result=result, disposition=resolved_disposition)

    return NativeToolDefinition(
        name=name,
        description=description,
        parameters_schema=parameters_schema,
        handler=handle,
    )


@dataclass(frozen=True)
class EndpointCloseReport:
    """State whether every admitted operation settled before the close deadline."""

    quiescent: bool
    unsettled_request_ids: tuple[str, ...]
    unknown_outcome_request_ids: tuple[str, ...]
    closed_at: datetime


@dataclass(frozen=True)
class _ToolBinding:
    definition: NativeToolDefinition
    validator: Draft202012Validator
    manifest: dict[str, Any]


class _ToolMetadata(StrictModel):
    deepseek_session_id: NonEmptyStr
    deepseek_tool_call_id: NonEmptyStr
    aec_model_turn: int = Field(ge=1)


class _ToolInvocationRequest(StrictModel):
    protocol: Literal["aec-bench/deepseek-tools/2"]
    capability: NonEmptyStr
    operation: Literal["invoke"]
    tool: NonEmptyStr
    arguments: dict[str, JsonValue]
    metadata: _ToolMetadata


class _ToolCancellationRequest(StrictModel):
    protocol: Literal["aec-bench/deepseek-tools/2"]
    capability: NonEmptyStr
    operation: Literal["cancel"]
    metadata: _ToolMetadata


@dataclass
class _AdmittedInvocation:
    fingerprint: str
    invocation: NativeToolInvocation
    arguments: dict[str, JsonValue]
    request_semantics: NativeToolRequestSemantics
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
    response: dict[str, Any] | None = None
    done: threading.Event = field(default_factory=threading.Event)


class _ThreadingUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False


class _ToolRequestHandler(socketserver.StreamRequestHandler):
    server: _ToolServer

    def handle(self) -> None:
        self.request.settimeout(self.server.endpoint.client_timeout_seconds)
        try:
            payload = self.rfile.readline(_MAX_REQUEST_BYTES + 1)
        except TimeoutError:
            response = _error_response("request_timeout", "Tool request timed out.")
        else:
            if len(payload) > _MAX_REQUEST_BYTES:
                response = _error_response("request_too_large", "Tool request is too large.")
            elif not payload:
                response = _error_response("empty_request", "Tool request is empty.")
            else:
                response = self.server.endpoint._handle_payload(payload)
        encoded = json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > _MAX_RESPONSE_BYTES:
            encoded = (
                json.dumps(
                    _error_response("response_too_large", "Tool response is too large."),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
        try:
            self.wfile.write(encoded)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return


class _ToolServer(_ThreadingUnixServer):
    endpoint: ToolGatewayEndpoint

    def __init__(self, path: str, endpoint: ToolGatewayEndpoint) -> None:
        self.endpoint = endpoint
        super().__init__(path, _ToolRequestHandler)


class ToolGatewayEndpoint:
    """Own one trial's exact authenticated native tool allowlist."""

    def __init__(
        self,
        *,
        tools: Sequence[NativeToolDefinition],
        evidence_path: Path,
        capability_token: str | None = None,
        client_timeout_seconds: float = 120.0,
        close_timeout_seconds: float = 5.0,
        generation_id: str | None = None,
    ) -> None:
        if not tools:
            raise ValueError("tool gateway requires at least one tool")
        if client_timeout_seconds <= 0:
            raise ValueError("tool gateway client timeout must be positive")
        if close_timeout_seconds < 0:
            raise ValueError("tool gateway close timeout must not be negative")
        self._bindings = _tool_bindings(tools)
        self.tools = tuple(binding.definition for binding in self._bindings.values())
        self.evidence_path = evidence_path
        self._capability_token = capability_token or secrets.token_urlsafe(32)
        self.client_timeout_seconds = client_timeout_seconds
        self.close_timeout_seconds = close_timeout_seconds
        self.generation_id = generation_id or f"tool-gateway-{uuid.uuid4().hex}"
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._evidence_lock = threading.Lock()
        self._evidence_finalized = False
        self._responses: dict[str, tuple[str, dict[str, Any]]] = {}
        self._active: dict[str, _AdmittedInvocation] = {}
        self._handler_authority_active: dict[str, list[_AdmittedInvocation]] = {}
        self._handler_authority_completed: set[str] = set()
        self._cancelled_before_dispatch: set[str] = set()
        self._server: _ToolServer | None = None
        self._thread: threading.Thread | None = None
        self._socket_directory: Path | None = None
        self._socket_path: Path | None = None
        self._closing = False
        self._generation_finalized = False
        self._close_report: EndpointCloseReport | None = None

    def start(self) -> None:
        """Create the private socket and start accepting bounded requests."""
        with self._lock:
            if self._server is not None:
                raise RuntimeError("native tool endpoint is already started")
            if self._closing:
                raise RuntimeError("native tool endpoint is closed")
            socket_directory = Path(tempfile.mkdtemp(prefix="aec-dsh-tools-"))
            os.chmod(socket_directory, 0o700)
            socket_path = socket_directory / "tools.sock"
            try:
                server = _ToolServer(str(socket_path), self)
            except BaseException:
                socket_path.unlink(missing_ok=True)
                socket_directory.rmdir()
                raise
            os.chmod(socket_path, 0o600)
            thread = threading.Thread(target=server.serve_forever, name="aec-dsh-tools", daemon=False)
            self._socket_directory = socket_directory
            self._socket_path = socket_path
            self._server = server
            self._thread = thread
            thread.start()

    def close(self, *, timeout_seconds: float | None = None) -> EndpointCloseReport:
        """Stop acceptance and report whether admitted handlers became quiescent."""
        deadline_seconds = self.close_timeout_seconds if timeout_seconds is None else timeout_seconds
        if deadline_seconds < 0:
            raise ValueError("tool gateway close timeout must not be negative")
        with self._condition:
            if self._close_report is not None:
                return self._close_report
            if self._closing:
                while self._close_report is None:
                    self._condition.wait()
                return self._close_report
            self._closing = True
            self._generation_finalized = True
            server = self._server
            thread = self._thread
            socket_path = self._socket_path
            socket_directory = self._socket_directory
            for active in self._all_active_locked():
                active.invocation.cancellation._cancel()

        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join()

        deadline = time.monotonic() + deadline_seconds
        with self._condition:
            while self._has_active_locked():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
            unsettled = tuple(sorted(self._active_request_ids_locked()))
            unknown = tuple(sorted(self._unknown_active_request_ids_locked()))

        if socket_path is not None:
            socket_path.unlink(missing_ok=True)
        if socket_directory is not None:
            try:
                socket_directory.rmdir()
            except FileNotFoundError:
                pass

        report = EndpointCloseReport(
            quiescent=not unsettled,
            unsettled_request_ids=unsettled,
            unknown_outcome_request_ids=unknown,
            closed_at=datetime.now(UTC),
        )
        self._append_evidence(
            {
                "record_type": "close",
                "protocol": TOOL_GATEWAY_PROTOCOL,
                "generation_id": self.generation_id,
                "closed_at": report.closed_at.isoformat(),
                "quiescent": report.quiescent,
                "unsettled_request_ids": list(report.unsettled_request_ids),
                "unknown_outcome_request_ids": list(report.unknown_outcome_request_ids),
                "late_results_after_close_are_ignored": True,
            },
            finalize=True,
        )
        with self._condition:
            self._close_report = report
            self._condition.notify_all()
        return report

    def connection_environment(self) -> Mapping[str, str]:
        """Return private runtime connection values and the exact enabled tool manifest."""
        with self._lock:
            if self._socket_path is None or self._closing:
                raise RuntimeError("native tool endpoint is not active")
            return {
                TOOL_GATEWAY_SOCKET_ENV: str(self._socket_path),
                TOOL_GATEWAY_TOKEN_ENV: self._capability_token,
                TOOL_GATEWAY_MANIFEST_ENV: json.dumps(
                    [self._bindings[name].manifest for name in sorted(self._bindings)],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }

    def _handle_payload(self, payload: bytes) -> dict[str, Any]:
        try:
            raw = json.loads(payload)
            if not isinstance(raw, dict):
                raise ValueError
            operation = raw.get("operation")
            if operation == "invoke":
                request: _ToolInvocationRequest | _ToolCancellationRequest = _ToolInvocationRequest.model_validate(raw)
            elif operation == "cancel":
                request = _ToolCancellationRequest.model_validate(raw)
            else:
                raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError):
            return _error_response("invalid_request", "Tool request is invalid.")
        if not hmac.compare_digest(request.capability, self._capability_token):
            return _error_response("unauthorized", "Tool authorization failed.")
        if isinstance(request, _ToolCancellationRequest):
            return self._cancel(request)
        return self._invoke(request)

    def _invoke(self, request: _ToolInvocationRequest) -> dict[str, Any]:
        request_id = _trusted_request_id(request.metadata)
        binding = self._bindings.get(request.tool)
        if binding is None:
            response = _error_response("tool_not_allowed", f"Tool is not enabled: {request.tool}")
            self._append_unadmitted_evidence(request, request_id=request_id, response=response)
            return response
        try:
            binding.validator.validate(request.arguments)
        except ValidationError as exc:
            response = _error_response("invalid_arguments", exc.message)
            self._append_unadmitted_evidence(request, request_id=request_id, response=response)
            return response

        fingerprint = _request_fingerprint(request)
        if binding.definition.request_semantics is NativeToolRequestSemantics.HANDLER_AUTHORITY:
            return self._invoke_handler_authority(binding, request, request_id=request_id, fingerprint=fingerprint)
        owner = False
        with self._lock:
            previous = self._responses.get(request_id)
            if previous is not None:
                previous_fingerprint, previous_response = previous
                if previous_fingerprint != fingerprint:
                    response = _error_response(
                        "request_id_conflict",
                        "Trusted tool request identity was reused with a different call.",
                    )
                    self._append_duplicate_evidence(request, request_id, response, duplicate_of=request_id)
                    return response
                self._append_duplicate_evidence(request, request_id, previous_response, duplicate_of=request_id)
                return previous_response

            active = self._active.get(request_id)
            if active is not None:
                if active.fingerprint != fingerprint:
                    response = _error_response(
                        "request_id_conflict",
                        "Trusted tool request identity was reused with a different call.",
                    )
                    self._append_duplicate_evidence(request, request_id, response, duplicate_of=request_id)
                    return response
            elif request_id in self._cancelled_before_dispatch:
                response = _error_response("request_cancelled", "Tool request was cancelled before dispatch.")
                self._append_unadmitted_evidence(request, request_id=request_id, response=response, cancelled=True)
                return response
            elif self._closing:
                response = _error_response("endpoint_closing", "Native tool authority is closing.")
                self._append_unadmitted_evidence(request, request_id=request_id, response=response)
                return response
            else:
                admitted_at = datetime.now(UTC)
                invocation = NativeToolInvocation(
                    request_id=request_id,
                    deepseek_session_id=request.metadata.deepseek_session_id,
                    deepseek_tool_call_id=request.metadata.deepseek_tool_call_id,
                    model_turn=request.metadata.aec_model_turn,
                    tool_name=request.tool,
                    generation_id=self.generation_id,
                    admitted_at=admitted_at,
                    cancellation=NativeCancellation(),
                )
                active = _AdmittedInvocation(
                    fingerprint=fingerprint,
                    invocation=invocation,
                    arguments=dict(request.arguments),
                    request_semantics=NativeToolRequestSemantics.GATEWAY,
                )
                self._active[request_id] = active
                owner = True

        if not owner:
            if not active.done.wait(self.client_timeout_seconds):
                response = _error_response("request_in_progress", "The identical tool request is still running.")
                self._append_duplicate_evidence(request, request_id, response, duplicate_of=request_id)
                return response
            response = active.response or _error_response("unknown_outcome", "The tool request outcome is unknown.")
            self._append_duplicate_evidence(request, request_id, response, duplicate_of=request_id)
            return response

        return self._execute(binding, request, active)

    def _invoke_handler_authority(
        self,
        binding: _ToolBinding,
        request: _ToolInvocationRequest,
        *,
        request_id: str,
        fingerprint: str,
    ) -> dict[str, Any]:
        with self._lock:
            if request_id in self._cancelled_before_dispatch:
                response = _error_response("request_cancelled", "Tool request was cancelled before dispatch.")
                self._append_unadmitted_evidence(request, request_id=request_id, response=response, cancelled=True)
                return response
            if self._closing:
                response = _error_response("endpoint_closing", "Native tool transport is closing.")
                self._append_unadmitted_evidence(request, request_id=request_id, response=response)
                return response
            invocation = NativeToolInvocation(
                request_id=request_id,
                deepseek_session_id=request.metadata.deepseek_session_id,
                deepseek_tool_call_id=request.metadata.deepseek_tool_call_id,
                model_turn=request.metadata.aec_model_turn,
                tool_name=request.tool,
                generation_id=self.generation_id,
                admitted_at=datetime.now(UTC),
                cancellation=NativeCancellation(),
            )
            active = _AdmittedInvocation(
                fingerprint=fingerprint,
                invocation=invocation,
                arguments=dict(request.arguments),
                request_semantics=NativeToolRequestSemantics.HANDLER_AUTHORITY,
            )
            self._handler_authority_active.setdefault(request_id, []).append(active)
        return self._execute(binding, request, active)

    def _execute(
        self,
        binding: _ToolBinding,
        request: _ToolInvocationRequest,
        active: _AdmittedInvocation,
    ) -> dict[str, Any]:
        request_id = active.invocation.request_id
        with self._lock:
            cancelled_before_dispatch = active.invocation.cancellation.cancelled
            if not cancelled_before_dispatch:
                active.dispatched_at = datetime.now(UTC)
        if cancelled_before_dispatch:
            response = _error_response("request_cancelled", "Tool request was cancelled before dispatch.")
            outcome = "not-dispatched"
            raw_result: JsonValue | None = None
            disposition: NativeToolDisposition | None = None
        else:
            try:
                tool_response = binding.definition.handler(active.invocation, active.arguments)
                if not isinstance(tool_response, NativeToolResponse):
                    raise TypeError("native tool handler must return NativeToolResponse")
                json.dumps(tool_response.result, allow_nan=False)
                response = {
                    "protocol": TOOL_GATEWAY_PROTOCOL,
                    "status": "ok",
                    "result": tool_response.result,
                    "disposition": tool_response.disposition.value,
                }
                raw_result = tool_response.result
                disposition = tool_response.disposition
                outcome = "completed"
            except (TypeError, ValueError) as exc:
                response = _error_response("invalid_result", str(exc))
                raw_result = None
                disposition = None
                outcome = "completed"
            except Exception:
                response = _error_response("tool_failed", "Native tool execution failed.")
                raw_result = None
                disposition = None
                outcome = "completed"

        completed_at = datetime.now(UTC)
        with self._condition:
            active.completed_at = completed_at
            stale = self._generation_finalized
            if stale:
                transport_response = _error_response(
                    "generation_finalized",
                    "Tool result arrived after endpoint finalization began.",
                )
                active.response = transport_response
            else:
                active.response = response
                if active.request_semantics is NativeToolRequestSemantics.GATEWAY:
                    self._responses[request_id] = (active.fingerprint, response)
                else:
                    self._handler_authority_completed.add(request_id)
                transport_response = response
            if active.request_semantics is NativeToolRequestSemantics.GATEWAY:
                self._active.pop(request_id, None)
            else:
                remaining = [item for item in self._handler_authority_active.get(request_id, ()) if item is not active]
                if remaining:
                    self._handler_authority_active[request_id] = remaining
                else:
                    self._handler_authority_active.pop(request_id, None)
            active.done.set()
            self._condition.notify_all()

        self._append_invocation_evidence(
            request,
            active,
            response=response,
            result=raw_result,
            disposition=disposition,
            outcome=outcome,
            stale=stale,
        )
        return transport_response

    def _cancel(self, request: _ToolCancellationRequest) -> dict[str, Any]:
        request_id = _trusted_request_id(request.metadata)
        occurred_at = datetime.now(UTC)
        with self._lock:
            completed = request_id in self._responses or request_id in self._handler_authority_completed
            active = self._active.get(request_id)
            handler_authority_active = self._handler_authority_active.get(request_id, ())
            active_items = (*handler_authority_active, active) if active is not None else handler_authority_active
            for item in active_items:
                item.invocation.cancellation._cancel()
            if completed:
                outcome = "completed"
            elif not active_items:
                self._cancelled_before_dispatch.add(request_id)
                outcome = "not-dispatched"
            else:
                outcome = (
                    "unknown" if any(item.dispatched_at is not None for item in active_items) else "not-dispatched"
                )
        response = {
            "protocol": TOOL_GATEWAY_PROTOCOL,
            "status": "ok",
            "result": {"outcome": outcome},
        }
        self._append_evidence(
            {
                "record_type": "cancellation",
                "protocol": TOOL_GATEWAY_PROTOCOL,
                "generation_id": self.generation_id,
                "request_id": request_id,
                "deepseek_session_id": request.metadata.deepseek_session_id,
                "deepseek_tool_call_id": request.metadata.deepseek_tool_call_id,
                "model_turn": request.metadata.aec_model_turn,
                "occurred_at": occurred_at.isoformat(),
                "outcome": outcome,
            }
        )
        return response

    def _append_invocation_evidence(
        self,
        request: _ToolInvocationRequest,
        active: _AdmittedInvocation,
        *,
        response: dict[str, Any],
        result: JsonValue | None,
        disposition: NativeToolDisposition | None,
        outcome: str,
        stale: bool,
    ) -> None:
        cancellation_requested_at = active.invocation.cancellation.requested_at
        self._append_evidence(
            {
                "record_type": "invocation",
                "protocol": TOOL_GATEWAY_PROTOCOL,
                "generation_id": self.generation_id,
                "request_id": active.invocation.request_id,
                "deepseek_session_id": request.metadata.deepseek_session_id,
                "deepseek_tool_call_id": request.metadata.deepseek_tool_call_id,
                "model_turn": request.metadata.aec_model_turn,
                "tool": request.tool,
                "request_semantics": active.request_semantics.value,
                "arguments_sha256": _json_sha256(request.arguments),
                "admitted_at": active.invocation.admitted_at.isoformat(),
                "dispatched_at": active.dispatched_at.isoformat() if active.dispatched_at is not None else None,
                "cancellation_requested_at": (
                    cancellation_requested_at.isoformat() if cancellation_requested_at is not None else None
                ),
                "completed_at": active.completed_at.isoformat() if active.completed_at is not None else None,
                "result_sha256": _json_sha256(result) if result is not None else None,
                "error_code": _response_error_code(response),
                "disposition": disposition.value if disposition is not None else None,
                "duplicate_of": None,
                "outcome": outcome,
                "stale_ignored": stale,
            }
        )

    def _all_active_locked(self) -> tuple[_AdmittedInvocation, ...]:
        return (
            *self._active.values(),
            *(item for items in self._handler_authority_active.values() for item in items),
        )

    def _has_active_locked(self) -> bool:
        return bool(self._active or self._handler_authority_active)

    def _active_request_ids_locked(self) -> set[str]:
        return {*self._active, *self._handler_authority_active}

    def _unknown_active_request_ids_locked(self) -> set[str]:
        unknown = {request_id for request_id, active in self._active.items() if active.dispatched_at is not None}
        unknown.update(
            request_id
            for request_id, active_items in self._handler_authority_active.items()
            if any(active.dispatched_at is not None for active in active_items)
        )
        return unknown

    def _append_unadmitted_evidence(
        self,
        request: _ToolInvocationRequest,
        *,
        request_id: str,
        response: dict[str, Any],
        cancelled: bool = False,
    ) -> None:
        occurred_at = datetime.now(UTC)
        self._append_evidence(
            {
                "record_type": "invocation",
                "protocol": TOOL_GATEWAY_PROTOCOL,
                "generation_id": self.generation_id,
                "request_id": request_id,
                "deepseek_session_id": request.metadata.deepseek_session_id,
                "deepseek_tool_call_id": request.metadata.deepseek_tool_call_id,
                "model_turn": request.metadata.aec_model_turn,
                "tool": request.tool,
                "arguments_sha256": _json_sha256(request.arguments),
                "admitted_at": None,
                "dispatched_at": None,
                "cancellation_requested_at": occurred_at.isoformat() if cancelled else None,
                "completed_at": occurred_at.isoformat(),
                "result_sha256": None,
                "error_code": _response_error_code(response),
                "disposition": None,
                "duplicate_of": None,
                "outcome": "not-dispatched",
                "stale_ignored": False,
            }
        )

    def _append_duplicate_evidence(
        self,
        request: _ToolInvocationRequest,
        request_id: str,
        response: dict[str, Any],
        *,
        duplicate_of: str,
    ) -> None:
        self._append_evidence(
            {
                "record_type": "duplicate",
                "protocol": TOOL_GATEWAY_PROTOCOL,
                "generation_id": self.generation_id,
                "request_id": request_id,
                "deepseek_session_id": request.metadata.deepseek_session_id,
                "deepseek_tool_call_id": request.metadata.deepseek_tool_call_id,
                "model_turn": request.metadata.aec_model_turn,
                "tool": request.tool,
                "arguments_sha256": _json_sha256(request.arguments),
                "occurred_at": datetime.now(UTC).isoformat(),
                "error_code": _response_error_code(response),
                "duplicate_of": duplicate_of,
            }
        )

    def _append_evidence(self, record: Mapping[str, Any], *, finalize: bool = False) -> None:
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with self._evidence_lock:
            if self._evidence_finalized:
                return
            with self.evidence_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            if finalize:
                self._evidence_finalized = True


def _tool_bindings(tools: Sequence[NativeToolDefinition]) -> dict[str, _ToolBinding]:
    bindings: dict[str, _ToolBinding] = {}
    for definition in tools:
        if not _TOOL_NAME.fullmatch(definition.name):
            raise ValueError(f"invalid native tool name: {definition.name!r}")
        if not definition.description.strip():
            raise ValueError(f"native tool description must not be blank: {definition.name}")
        if definition.name in bindings:
            raise ValueError(f"duplicate native tool: {definition.name}")
        try:
            Draft202012Validator.check_schema(definition.parameters_schema)
        except SchemaError as exc:
            raise ValueError(f"invalid parameter schema for native tool {definition.name}: {exc.message}") from exc
        schema = json.loads(json.dumps(definition.parameters_schema, sort_keys=True))
        bindings[definition.name] = _ToolBinding(
            definition=definition,
            validator=Draft202012Validator(schema),
            manifest={"name": definition.name, "description": definition.description, "parameters": schema},
        )
    return bindings


def native_tool_manifest(tools: Sequence[NativeToolDefinition]) -> tuple[dict[str, Any], ...]:
    """Validate tools and return the exact canonical model-facing manifest."""
    bindings = _tool_bindings(tools)
    return tuple(bindings[name].manifest for name in sorted(bindings))


def _trusted_request_id(metadata: _ToolMetadata) -> str:
    return f"dsh:{metadata.deepseek_session_id}:{metadata.deepseek_tool_call_id}"


def _request_fingerprint(request: _ToolInvocationRequest) -> str:
    return _json_sha256(request.model_dump(mode="json", exclude={"capability"}))


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _response_error_code(response: Mapping[str, Any]) -> str | None:
    error = response.get("error")
    return str(error.get("code")) if isinstance(error, dict) and error.get("code") is not None else None


def _error_response(code: str, message: str) -> dict[str, Any]:
    return {
        "protocol": TOOL_GATEWAY_PROTOCOL,
        "status": "error",
        "error": {"code": code, "message": message},
    }
