# ABOUTME: Exposes one exact AEC-owned native tool surface on an authenticated Unix socket.
# ABOUTME: Keeps tool state and effects in AEC while DeepSeek presents model-facing JSON schemas.

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import os
import secrets
import socketserver
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast, get_type_hints

from pydantic import BaseModel, Field, create_model

from aec_bench.contracts.validators import NonEmptyStr, StrictModel

TOOL_GATEWAY_PROTOCOL = "aec-bench/deepseek-tools/1"
TOOL_GATEWAY_SOCKET_ENV = "DSH_TOOLS_SOCKET"
TOOL_GATEWAY_TOKEN_ENV = "DSH_TOOLS_TOKEN"
TOOL_GATEWAY_MANIFEST_ENV = "DSH_TOOLS"
_MAX_REQUEST_BYTES = 1024 * 1024
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024

NativeTool = Callable[..., str]


@dataclass(frozen=True)
class _ToolBinding:
    function: NativeTool
    arguments_model: type[BaseModel]
    manifest: dict[str, Any]


class _ToolMetadata(StrictModel):
    deepseek_session_id: NonEmptyStr
    deepseek_tool_call_id: NonEmptyStr
    aec_model_turn: int = Field(ge=1)


class _ToolRequest(StrictModel):
    protocol: Literal["aec-bench/deepseek-tools/1"]
    capability: NonEmptyStr
    request_id: NonEmptyStr
    tool: NonEmptyStr
    arguments: dict[str, Any]
    metadata: _ToolMetadata


class _ThreadingUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = False
    block_on_close = True
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
        tools: Mapping[str, NativeTool],
        evidence_path: Path,
        capability_token: str | None = None,
        client_timeout_seconds: float = 120.0,
    ) -> None:
        if not tools:
            raise ValueError("tool gateway requires at least one tool")
        self._bindings = {name: _tool_binding(name, tool) for name, tool in tools.items()}
        self.tools = dict(tools)
        self.evidence_path = evidence_path
        self._capability_token = capability_token or secrets.token_urlsafe(32)
        self.client_timeout_seconds = client_timeout_seconds
        self._lock = threading.Lock()
        self._responses: dict[str, tuple[str, dict[str, Any]]] = {}
        self._server: _ToolServer | None = None
        self._thread: threading.Thread | None = None
        self._socket_directory: Path | None = None
        self._socket_path: Path | None = None
        self._closing = False

    def start(self) -> None:
        """Create the private socket and start accepting bounded requests."""
        with self._lock:
            if self._server is not None:
                raise RuntimeError("lifecycle tool endpoint is already started")
            if self._closing:
                raise RuntimeError("lifecycle tool endpoint is closed")
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

    def close(self) -> None:
        """Stop acceptance, wait for active handlers, and remove the owned socket."""
        with self._lock:
            if self._closing:
                return
            self._closing = True
            server = self._server
            thread = self._thread
            socket_path = self._socket_path
            socket_directory = self._socket_directory
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join()
        if socket_path is not None:
            socket_path.unlink(missing_ok=True)
        if socket_directory is not None:
            try:
                socket_directory.rmdir()
            except FileNotFoundError:
                pass

    def connection_environment(self) -> Mapping[str, str]:
        """Return private runtime connection values and the exact enabled tool names."""
        with self._lock:
            if self._socket_path is None or self._closing:
                raise RuntimeError("lifecycle tool endpoint is not active")
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
            request = _ToolRequest.model_validate_json(payload)
        except ValueError:
            return _error_response("invalid_request", "Tool request is invalid.")
        if not hmac.compare_digest(request.capability, self._capability_token):
            return _error_response("unauthorized", "Tool authorization failed.")

        fingerprint = _request_fingerprint(request)
        with self._lock:
            previous = self._responses.get(request.request_id)
            if previous is not None:
                previous_fingerprint, previous_response = previous
                if previous_fingerprint != fingerprint:
                    response = _error_response(
                        "request_id_conflict",
                        "Tool request_id was reused with a different call.",
                    )
                    self._append_evidence(request, response, idempotent_replay=False)
                    return response
                self._append_evidence(request, previous_response, idempotent_replay=True)
                return previous_response
            if self._closing:
                response = _error_response("endpoint_closing", "Lifecycle tool authority is closing.")
            else:
                response = self._execute(request)
            self._responses[request.request_id] = (fingerprint, response)
            self._append_evidence(request, response, idempotent_replay=False)
            return response

    def _execute(self, request: _ToolRequest) -> dict[str, Any]:
        binding = self._bindings.get(request.tool)
        if binding is None:
            return _error_response("tool_not_allowed", f"Tool is not enabled: {request.tool}")
        try:
            arguments = binding.arguments_model.model_validate_json(json.dumps(request.arguments))
            inspect.signature(binding.function).bind(**arguments.model_dump())
            raw_result = binding.function(**arguments.model_dump())
            result = json.loads(raw_result)
            if not isinstance(result, dict):
                raise ValueError("tool result must be a JSON object")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return _error_response("invalid_arguments", str(exc))
        except Exception:
            return _error_response("tool_failed", "Lifecycle tool execution failed.")
        return {"protocol": TOOL_GATEWAY_PROTOCOL, "status": "ok", "result": result}

    def _append_evidence(
        self,
        request: _ToolRequest,
        response: dict[str, Any],
        *,
        idempotent_replay: bool,
    ) -> None:
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "protocol": TOOL_GATEWAY_PROTOCOL,
            "occurred_at": datetime.now(UTC).isoformat(),
            "request_id": request.request_id,
            "tool": request.tool,
            "arguments_sha256": hashlib.sha256(
                json.dumps(request.arguments, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "metadata": request.metadata.model_dump(mode="json"),
            "response_status": response.get("status"),
            "response_error_code": (
                response.get("error", {}).get("code") if isinstance(response.get("error"), dict) else None
            ),
            "idempotent_replay": idempotent_replay,
        }
        with self.evidence_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def _tool_binding(name: str, tool: NativeTool) -> _ToolBinding:
    if not name or name != getattr(tool, "__name__", None):
        raise ValueError("tool gateway names must match stable callable names")
    fields: dict[str, tuple[Any, Any]] = {}
    type_hints = get_type_hints(tool)
    for parameter in inspect.signature(tool).parameters.values():
        if parameter.kind not in {parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY}:
            raise ValueError(f"tool gateway does not support parameter kind for {name}.{parameter.name}")
        annotation = type_hints.get(parameter.name)
        if annotation is None:
            raise ValueError(f"tool gateway requires an annotation for {name}.{parameter.name}")
        default = ... if parameter.default is inspect.Parameter.empty else parameter.default
        fields[parameter.name] = (annotation, default)
    model_factory = cast(Any, create_model)
    arguments_model = cast(
        type[BaseModel],
        model_factory(
            f"{''.join(part.title() for part in name.split('_'))}Arguments",
            __base__=StrictModel,
            **fields,
        ),
    )
    parameters = arguments_model.model_json_schema()
    parameters.pop("title", None)
    description = inspect.getdoc(tool) or name.replace("_", " ")
    return _ToolBinding(
        function=tool,
        arguments_model=arguments_model,
        manifest={"name": name, "description": description, "parameters": parameters},
    )


def _request_fingerprint(request: _ToolRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"capability"})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _error_response(code: str, message: str) -> dict[str, Any]:
    return {
        "protocol": TOOL_GATEWAY_PROTOCOL,
        "status": "error",
        "error": {"code": code, "message": message},
    }
