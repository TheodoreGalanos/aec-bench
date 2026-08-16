# ABOUTME: Exposes the provider-neutral output commit authority on one authenticated Unix socket.
# ABOUTME: Binds a fixed trial output path and records secret-free append-only decision evidence.

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socketserver
import tempfile
import threading
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from aec_bench.adapters.output_commit import evaluate_output_commit_candidate
from aec_bench.contracts.output_completion import OutputCommitAttestation, OutputCompletionContract
from aec_bench.contracts.validators import NonEmptyStr, StrictModel

OUTPUT_COMMIT_PROTOCOL = "aec-bench/output-commit/1"
OUTPUT_COMMIT_SOCKET_ENV = "AEC_BENCH_COMMIT_SOCKET"
OUTPUT_COMMIT_TOKEN_ENV = "AEC_BENCH_COMMIT_TOKEN"
_MAX_REQUEST_BYTES = 16 * 1024
_MAX_RESPONSE_BYTES = 64 * 1024


class _CommitMetadata(StrictModel):
    deepseek_session_id: NonEmptyStr
    deepseek_tool_call_id: NonEmptyStr
    aec_model_turn: int = Field(ge=1)


class _CommitRequest(StrictModel):
    protocol: Literal["aec-bench/output-commit/1"]
    capability: NonEmptyStr
    request_id: NonEmptyStr
    operation: Literal["commit"]
    metadata: _CommitMetadata


class _ThreadingUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = False


class _CommitRequestHandler(socketserver.StreamRequestHandler):
    server: _CommitServer

    def handle(self) -> None:
        self.request.settimeout(self.server.endpoint.client_timeout_seconds)
        try:
            payload = self.rfile.readline(_MAX_REQUEST_BYTES + 1)
        except TimeoutError:
            response = _error_response("request_timeout", "Output commit request timed out.")
        else:
            if len(payload) > _MAX_REQUEST_BYTES:
                response = _error_response("request_too_large", "Output commit request is too large.")
            elif not payload:
                response = _error_response("empty_request", "Output commit request is empty.")
            else:
                response = self.server.endpoint._handle_payload(payload)
        encoded = json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > _MAX_RESPONSE_BYTES:
            encoded = (
                json.dumps(
                    _error_response("response_too_large", "Output commit response is too large."),
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


class _CommitServer(_ThreadingUnixServer):
    endpoint: OutputCommitEndpoint

    def __init__(self, path: str, endpoint: OutputCommitEndpoint) -> None:
        self.endpoint = endpoint
        super().__init__(path, _CommitRequestHandler)


class OutputCommitEndpoint:
    """Own one trial's authenticated, fixed-path output commit authority."""

    def __init__(
        self,
        *,
        workspace: Path,
        contract: OutputCompletionContract,
        initial_content: str | None,
        evidence_path: Path,
        capability_token: str | None = None,
        client_timeout_seconds: float = 2.0,
    ) -> None:
        self.workspace = workspace.resolve()
        self.contract = contract
        self.initial_content = initial_content
        self.evidence_path = evidence_path
        self._capability_token = capability_token or secrets.token_urlsafe(32)
        self.client_timeout_seconds = client_timeout_seconds
        self.candidate_path = resolve_trial_output_path(self.workspace, contract.output_path)
        self._lock = threading.Lock()
        self._responses: dict[str, tuple[str, dict[str, Any]]] = {}
        self._accepted_attestation: OutputCommitAttestation | None = None
        self._accepted_metadata: dict[str, object] | None = None
        self._server: _CommitServer | None = None
        self._thread: threading.Thread | None = None
        self._socket_directory: Path | None = None
        self._socket_path: Path | None = None
        self._closing = False

    @property
    def accepted_attestation(self) -> OutputCommitAttestation | None:
        with self._lock:
            return self._accepted_attestation

    @property
    def accepted_metadata(self) -> Mapping[str, object] | None:
        with self._lock:
            return None if self._accepted_metadata is None else dict(self._accepted_metadata)

    def start(self) -> None:
        """Create the private socket and start accepting bounded requests."""
        with self._lock:
            if self._server is not None:
                raise RuntimeError("output commit endpoint is already started")
            if self._closing:
                raise RuntimeError("output commit endpoint is closed")
            socket_directory = Path(tempfile.mkdtemp(prefix="aec-dsh-commit-"))
            os.chmod(socket_directory, 0o700)
            socket_path = socket_directory / "commit.sock"
            try:
                server = _CommitServer(str(socket_path), self)
            except BaseException:
                socket_path.unlink(missing_ok=True)
                socket_directory.rmdir()
                raise
            os.chmod(socket_path, 0o600)
            thread = threading.Thread(target=server.serve_forever, name="aec-output-commit", daemon=False)
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
        """Return the two secret-bearing values for the owned runtime process only."""
        with self._lock:
            if self._socket_path is None or self._closing:
                raise RuntimeError("output commit endpoint is not active")
            return {
                OUTPUT_COMMIT_SOCKET_ENV: str(self._socket_path),
                OUTPUT_COMMIT_TOKEN_ENV: self._capability_token,
            }

    def _handle_payload(self, payload: bytes) -> dict[str, Any]:
        try:
            request = _CommitRequest.model_validate_json(payload)
        except ValueError:
            return _error_response("invalid_request", "Output commit request is invalid.")
        if not hmac.compare_digest(request.capability, self._capability_token):
            return _error_response("unauthorized", "Output commit authorization failed.")

        fingerprint = _request_fingerprint(request)
        with self._lock:
            previous = self._responses.get(request.request_id)
            if previous is not None:
                previous_fingerprint, previous_response = previous
                if previous_fingerprint != fingerprint:
                    response = _error_response(
                        "request_id_conflict",
                        "Output commit request_id was reused with different metadata.",
                    )
                    self._append_evidence(request, response, idempotent_replay=False)
                    return response
                response = previous_response
                self._append_evidence(request, response, idempotent_replay=True)
                return response
            if self._closing:
                response = _error_response("endpoint_closing", "Output commit authority is closing.")
            elif self._accepted_attestation is not None:
                response = _error_response("commit_already_accepted", "An output commit was already accepted.")
            else:
                response = self._evaluate(request)
            self._responses[request.request_id] = (fingerprint, response)
            self._append_evidence(request, response, idempotent_replay=False)
            return response

    def _evaluate(self, request: _CommitRequest) -> dict[str, Any]:
        decision = evaluate_output_commit_candidate(
            self.contract,
            initial_content=self.initial_content,
            commit_turn=request.metadata.aec_model_turn,
            candidate_path=self.candidate_path,
        )
        if decision.attestation is None:
            return {
                "protocol": OUTPUT_COMMIT_PROTOCOL,
                "status": "rejected",
                "completion_evaluation": decision.completion_evaluation.model_dump(mode="json"),
                "diagnostics": [
                    {
                        "code": decision.diagnostic_code or "output_commit_rejected",
                        "message": decision.diagnostic,
                    }
                ],
            }
        self._accepted_attestation = decision.attestation
        self._accepted_metadata = request.metadata.model_dump(mode="json")
        return {
            "protocol": OUTPUT_COMMIT_PROTOCOL,
            "status": "accepted",
            "attestation": decision.attestation.model_dump(mode="json"),
            "commit_receipt_id": f"commit-{uuid.uuid4().hex}",
        }

    def _append_evidence(
        self,
        request: _CommitRequest,
        response: dict[str, Any],
        *,
        idempotent_replay: bool,
    ) -> None:
        record = {
            "captured_at": datetime.now(UTC).isoformat(),
            "request_id": request.request_id,
            "operation": request.operation,
            "metadata": request.metadata.model_dump(mode="json"),
            "idempotent_replay": idempotent_replay,
            "response": response,
        }
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with self.evidence_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()


def resolve_trial_output_path(workspace: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute() and path.parts[:2] == ("/", "workspace"):
        candidate = workspace.joinpath(*path.parts[2:])
    elif path.is_absolute():
        candidate = path
    else:
        candidate = workspace / path
    normalized = Path(os.path.abspath(candidate))
    if not normalized.is_relative_to(workspace):
        raise ValueError("DeepSeek output completion path must resolve inside the trial workspace")
    return normalized


def _request_fingerprint(request: _CommitRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"capability"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _error_response(code: str, message: str) -> dict[str, Any]:
    return {
        "protocol": OUTPUT_COMMIT_PROTOCOL,
        "status": "error",
        "diagnostics": [{"code": code, "message": message}],
    }
