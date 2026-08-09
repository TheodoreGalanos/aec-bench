# ABOUTME: Exposes one hydraulic-review lifecycle checkpoint through a capability-scoped Unix socket.
# ABOUTME: Keeps lifecycle paths, checkpoint control, hidden evidence, and verification outside Prime.

from __future__ import annotations

import copy
import hashlib
import hmac
import io
import json
import os
import secrets
import socketserver
import tempfile
import threading
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import Field, JsonValue, ValidationError

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeRequest, LifecycleVisibilityPolicy
from aec_bench.lifecycles.runtime.lifecycle import (
    EvidenceLifecycleError,
    execute_lifecycle_operation,
    load_evidence_lifecycle_spec,
    validate_evidence_checkpoint_submission,
)
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver

HYDRAULIC_REVIEW_SOCKET_ENV = "AEC_BENCH_HYDRAULIC_REVIEW_SOCKET"
HYDRAULIC_REVIEW_CAPABILITY_ENV = "AEC_BENCH_HYDRAULIC_REVIEW_CAPABILITY_TOKEN"
_MAX_MESSAGE_BYTES = 1024 * 1024


class HydraulicReviewPrimeLifecycleEndpointError(RuntimeError):
    """Raised when the scoped hydraulic-review endpoint cannot be used safely."""


class _CapabilitiesRequest(StrictModel):
    operation: Literal["capabilities"]


class _ObserveRequest(StrictModel):
    operation: Literal["observe"]


class _ListFilesRequest(StrictModel):
    operation: Literal["list_files"]
    path: str = "."


class _ReadFileRequest(StrictModel):
    operation: Literal["read_file"]
    path: NonEmptyStr


class _ExecuteOperationRequest(StrictModel):
    operation: Literal["execute_operation"]
    operation_id: NonEmptyStr
    visible_source_state_sha256: NonEmptyStr
    reason: NonEmptyStr


class _OfferSubmissionRequest(StrictModel):
    operation: Literal["offer_submission"]
    submission: dict[str, JsonValue]


type _LifecycleRequest = Annotated[
    _CapabilitiesRequest
    | _ObserveRequest
    | _ListFilesRequest
    | _ReadFileRequest
    | _ExecuteOperationRequest
    | _OfferSubmissionRequest,
    Field(discriminator="operation"),
]


class _TransportRequest(StrictModel):
    capability: NonEmptyStr
    request: _LifecycleRequest


class _TransportError(StrictModel):
    code: NonEmptyStr
    detail: NonEmptyStr


class _TransportResponse(StrictModel):
    result: dict[str, JsonValue] | None = None
    error: _TransportError | None = None


class _ThreadedUnixServer(socketserver.ThreadingUnixStreamServer):
    # Endpoint closure must wait for every actor request. Otherwise an operation
    # can change lifecycle state after the Prime process has ended.
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = False


class _EndpointRequestHandler(socketserver.StreamRequestHandler):
    server: _EndpointServer

    def handle(self) -> None:
        line = self.rfile.readline(_MAX_MESSAGE_BYTES + 1)
        if len(line) > _MAX_MESSAGE_BYTES:
            self.server.owner._reject_transport(self.wfile, ("request-too-large", "request is too large"))
            return
        if not line or not line.endswith(b"\n"):
            self.server.owner._reject_transport(
                self.wfile,
                ("transport-malformed", "request must be one complete line"),
            )
            return
        self.server.owner._handle_request(line, self.wfile)


class _EndpointServer(_ThreadedUnixServer):
    owner: HydraulicReviewPrimeLifecycleEndpoint


class HydraulicReviewPrimeLifecycleEndpoint:
    """Expose only the active hydraulic-review checkpoint's actor operations.

    Prime's root process and descendants share one capability and form one
    composite actor principal for this checkpoint.
    """

    def __init__(
        self,
        *,
        package_dir: Path,
        run_dir: Path,
        request: LifecycleEpisodeRequest,
        operation_resolver: LifecycleOperationResolver,
        socket_directory: Path,
        evidence_file: Path,
    ) -> None:
        if request.memory_visibility_policy is not LifecycleVisibilityPolicy.ARTIFACT_MEMORY:
            raise ValueError("hydraulic-review Prime requires artifact_memory lifecycle visibility")
        self._package_dir = package_dir.resolve()
        self._run_dir = run_dir.resolve()
        self._request = request
        self._resolver = operation_resolver
        self._workspace = Path(request.workspace).resolve()
        if Path(request.run_dir).resolve() != self._run_dir:
            raise ValueError("hydraulic-review endpoint run does not match the episode request")
        if self._workspace != (self._run_dir / "workspace").resolve():
            raise ValueError("hydraulic-review endpoint workspace does not match the lifecycle run")
        spec = load_evidence_lifecycle_spec(self._package_dir)
        try:
            self._checkpoint = next(item for item in spec.checkpoints if item.checkpoint_id == request.checkpoint_id)
        except StopIteration as exc:
            raise ValueError("hydraulic-review endpoint checkpoint is absent from the lifecycle") from exc

        requested_socket_directory = socket_directory.resolve()
        requested_socket = requested_socket_directory / "lifecycle.sock"
        self._owns_socket_directory = len(os.fsencode(requested_socket)) > 100
        short_root = Path("/private/tmp") if Path("/private/tmp").is_dir() else Path("/tmp")
        self._socket_directory = (
            Path(tempfile.mkdtemp(prefix="aecbench-hydraulic-review-", dir=short_root)).resolve()
            if self._owns_socket_directory
            else requested_socket_directory
        )
        self._socket_path = self._socket_directory / "lifecycle.sock"
        self._evidence_file = evidence_file.resolve()
        self._capability = secrets.token_urlsafe(32)
        self._server: _EndpointServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._sequence = 0
        self._offered_bytes: bytes | None = None
        self._offered_submission: dict[str, JsonValue] | None = None

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    @property
    def offered_submission(self) -> dict[str, JsonValue] | None:
        with self._lock:
            return copy.deepcopy(self._offered_submission)

    def start(self) -> None:
        if self._server is not None:
            raise HydraulicReviewPrimeLifecycleEndpointError("hydraulic-review endpoint is already running")
        self._socket_directory.mkdir(parents=True, exist_ok=True)
        self._socket_directory.chmod(0o700)
        if self._socket_path.exists() or self._socket_path.is_symlink():
            raise HydraulicReviewPrimeLifecycleEndpointError("hydraulic-review endpoint socket already exists")
        self._evidence_file.parent.mkdir(parents=True, exist_ok=True)
        self._evidence_file.write_bytes(b"")
        server = _EndpointServer(str(self._socket_path), _EndpointRequestHandler)
        self._socket_path.chmod(0o600)
        server.owner = self
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever, name="hydraulic-review-prime-endpoint", daemon=True
        )
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
            raise HydraulicReviewPrimeLifecycleEndpointError("hydraulic-review endpoint is not running")
        return {
            HYDRAULIC_REVIEW_SOCKET_ENV: str(self._socket_path),
            HYDRAULIC_REVIEW_CAPABILITY_ENV: self._capability,
        }

    def __enter__(self) -> HydraulicReviewPrimeLifecycleEndpoint:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _handle_request(self, line: bytes, writer: io.BufferedIOBase) -> None:
        request: _LifecycleRequest | None = None
        operation: str | None = None
        try:
            raw = json.loads(line)
            operation = _safe_operation(raw)
            envelope = _TransportRequest.model_validate(raw)
            if not hmac.compare_digest(envelope.capability, self._capability):
                self._record(operation=operation, request=None, error="capability-invalid")
                self._write_response(writer, error=("endpoint-unauthorized", "endpoint capability is invalid"))
                return
            request = envelope.request
            operation = request.operation
            result = self._dispatch(request)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            self._record(operation=operation, request=None, error="request-invalid")
            self._write_response(writer, error=("request-invalid", "request does not match the endpoint contract"))
            return
        except EvidenceLifecycleError as exc:
            self._record(operation=operation, request=None, error="lifecycle-rejected")
            self._write_response(writer, error=("lifecycle-rejected", self._safe_detail(str(exc))))
            return
        except (OSError, UnicodeError):
            self._record(operation=operation, request=None, error="endpoint-failed")
            self._write_response(writer, error=("endpoint-failed", "endpoint operation failed"))
            return
        except Exception:
            self._record(operation=operation, request=None, error="endpoint-failed")
            self._write_response(writer, error=("endpoint-failed", "endpoint operation failed"))
            return
        self._record(operation=operation, request=request, result=result)
        self._write_response(writer, result=result)

    def _dispatch(self, request: _LifecycleRequest) -> dict[str, Any]:
        if isinstance(request, _CapabilitiesRequest):
            return {
                "schema_version": "1",
                "operations": [
                    "capabilities",
                    "observe",
                    "list_files",
                    "read_file",
                    "execute_operation",
                    "offer_submission",
                ],
            }
        if isinstance(request, _ObserveRequest):
            return self._observation()
        if isinstance(request, _ListFilesRequest):
            return self._list_files(request.path)
        if isinstance(request, _ReadFileRequest):
            return self._read_file(request.path)
        if isinstance(request, _ExecuteOperationRequest):
            result = execute_lifecycle_operation(
                self._package_dir,
                self._run_dir,
                operation_resolver=self._resolver,
                checkpoint_id=self._request.checkpoint_id,
                operation_id=request.operation_id,
                visible_source_state_sha256=request.visible_source_state_sha256,
                reason=request.reason,
                session_id=self._request.session_id,
            )
            return _operation_result(result)
        assert isinstance(request, _OfferSubmissionRequest)
        return self._offer(request.submission)

    def _observation(self) -> dict[str, Any]:
        released_files = [
            (PurePosixPath("inbox") / self._request.checkpoint_id / path).as_posix()
            for path in self._request.released_files
        ]
        return {
            "schema_version": "2",
            "lifecycle_id": self._request.lifecycle_id,
            "checkpoint_id": self._request.checkpoint_id,
            "title": self._request.title,
            "instruction": self._request.instruction,
            "completed_checkpoint_ids": list(self._request.completed_checkpoint_ids),
            "released_files": released_files,
            "required_submission_fields": list(self._checkpoint.required_submission_fields),
            "allow_additional_submission_fields": self._checkpoint.allow_additional_submission_fields,
            "operation_catalog": (
                None
                if self._request.operation_catalog is None
                else self._request.operation_catalog.model_dump(mode="json")
            ),
            "current_source": (
                None if self._request.current_source is None else self._request.current_source.model_dump(mode="json")
            ),
            "submission_offered": self.offered_submission is not None,
        }

    def _list_files(self, raw_path: str) -> dict[str, Any]:
        target, relative = self._read_path(raw_path)
        if not target.is_dir():
            raise EvidenceLifecycleError(f"visible directory not found: {relative}")
        entries = []
        for child in sorted(target.iterdir(), key=lambda value: value.name):
            child_relative = PurePosixPath(relative) / child.name
            if not child.name.startswith(".") and self._is_visible_path(child_relative):
                entries.append(child.name)
        return {"status": "ok", "path": relative, "entries": entries}

    def _read_file(self, raw_path: str) -> dict[str, Any]:
        target, relative = self._read_path(raw_path)
        if not target.is_file():
            raise EvidenceLifecycleError(f"visible file not found: {relative}")
        return {"status": "ok", "path": relative, "content": target.read_text(encoding="utf-8")}

    def _read_path(self, raw_path: str) -> tuple[Path, str]:
        if "\\" in raw_path:
            raise EvidenceLifecycleError("visible path must use POSIX separators")
        path = PurePosixPath(raw_path or ".")
        if path.is_absolute() or ".." in path.parts or any(part.startswith(".") for part in path.parts if part != "."):
            raise EvidenceLifecycleError("visible path must stay inside the lifecycle workspace")
        relative = path.as_posix()
        if not self._is_visible_path(path):
            raise EvidenceLifecycleError(f"path is not actor-visible: {relative}")
        target = self._workspace
        for part in (item for item in path.parts if item not in {"", "."}):
            target = target / part
            if target.is_symlink():
                raise EvidenceLifecycleError("actor-visible paths must not contain symbolic links")
        resolved = target.resolve()
        if resolved != self._workspace and self._workspace not in resolved.parents:
            raise EvidenceLifecycleError("visible path must stay inside the lifecycle workspace")
        return resolved, relative

    def _is_visible_path(self, path: PurePosixPath) -> bool:
        parts = tuple(part for part in path.parts if part not in {"", "."})
        if not parts:
            return True
        if any(part.startswith(".") for part in parts):
            return False
        root = parts[0]
        if root == "instruction.md":
            return len(parts) == 1
        if root == "hydraulics":
            return len(parts) == 1 or (len(parts) == 2 and parts[1] == "current-source.json")
        visible_checkpoints = {self._request.checkpoint_id, *self._request.completed_checkpoint_ids}
        if root == "inbox":
            return len(parts) == 1 or (len(parts) >= 2 and parts[1] in visible_checkpoints)
        if root == "checkpoints":
            return len(parts) == 1 or (len(parts) >= 2 and parts[1] in visible_checkpoints)
        if root == "submissions":
            allowed = {
                PurePosixPath(checkpoint.submission_path)
                for checkpoint in load_evidence_lifecycle_spec(self._package_dir).checkpoints
                if checkpoint.checkpoint_id in self._request.completed_checkpoint_ids
            }
            candidate = PurePosixPath(*parts)
            return len(parts) == 1 or any(candidate == item or candidate in item.parents for item in allowed)
        if root == "branch_origin":
            return (self._workspace / "branch_origin").is_dir()
        return False

    def _offer(self, submission: dict[str, JsonValue]) -> dict[str, Any]:
        validate_evidence_checkpoint_submission(self._checkpoint, submission)
        encoded = _canonical_json(submission)
        with self._lock:
            if self._offered_bytes is not None and self._offered_bytes != encoded:
                raise EvidenceLifecycleError("checkpoint already has a different offered submission")
            self._offered_bytes = encoded
            self._offered_submission = copy.deepcopy(submission)
        return {
            "status": "accepted",
            "checkpoint_id": self._request.checkpoint_id,
            "submission_sha256": hashlib.sha256(encoded).hexdigest(),
        }

    def _reject_transport(self, writer: io.BufferedIOBase, error: tuple[str, str]) -> None:
        self._record(operation=None, request=None, error=error[0])
        self._write_response(writer, error=error)

    def _record(
        self,
        *,
        operation: str | None,
        request: _LifecycleRequest | None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            self._sequence += 1
            event: dict[str, JsonValue] = {
                "sequence": self._sequence,
                "operation": operation,
                "request": None if request is None else self._request_evidence(request),
                "result": None if result is None else self._redact_json(result),
                "error": error,
            }
            with self._evidence_file.open("ab") as sink:
                sink.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n")

    def _request_evidence(self, request: _LifecycleRequest) -> dict[str, JsonValue]:
        if isinstance(request, _ExecuteOperationRequest):
            return {
                "operation": request.operation,
                "operation_id": request.operation_id,
                "visible_source_state_sha256": request.visible_source_state_sha256,
                "reason_sha256": hashlib.sha256(request.reason.encode("utf-8")).hexdigest(),
            }
        if isinstance(request, _OfferSubmissionRequest):
            return {
                "operation": request.operation,
                "submission_sha256": hashlib.sha256(_canonical_json(request.submission)).hexdigest(),
            }
        return self._redact_json(request.model_dump(mode="json"))

    def _redact_json(self, value: dict[str, Any]) -> dict[str, JsonValue]:
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        for private in (
            self._capability,
            str(self._package_dir),
            str(self._run_dir),
            str(self._workspace),
            str(self._socket_path),
            str(self._evidence_file),
        ):
            encoded = encoded.replace(private, "<private>")
        decoded = json.loads(encoded)
        assert isinstance(decoded, dict)
        return decoded

    def _safe_detail(self, detail: str) -> str:
        result = detail
        for private in (
            self._capability,
            str(self._package_dir),
            str(self._run_dir),
            str(self._workspace),
            str(self._socket_path),
            str(self._evidence_file),
        ):
            result = result.replace(private, "<private>")
        return result

    @staticmethod
    def _write_response(
        writer: io.BufferedIOBase,
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


def _operation_result(result: dict[str, Any]) -> dict[str, Any]:
    """Select the actor-visible operation result without storage or host identity."""
    artifacts = [
        {"path": artifact["workspace_path"], "sha256": artifact["sha256"]}
        for artifact in result["artifacts"]
        if artifact.get("workspace_path") is not None
    ]
    payload: dict[str, Any] = {
        "status": result["outcome"],
        "action_id": result["action_id"],
        "checkpoint_id": result["checkpoint_id"],
        "operation_id": result["operation_id"],
        "operation_kind": result["operation_kind"],
        "disposition": result["disposition"],
        "visible_source_state_sha256": result["visible_source_state_after_sha256"],
        "input_projection_sha256": result["input_projection_sha256"],
        "prerequisite_action_ids": result["prerequisite_action_ids"],
        "retained_from_action_id": result["retained_from_action_id"],
        "budget_consumed": result["budget_consumed"],
        "remaining_budget": result["budget_after"],
        "artifacts": artifacts,
    }
    if result["rejection"] is not None:
        payload["rejection"] = result["rejection"]
    return payload


def _safe_operation(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    request = value.get("request")
    if not isinstance(request, dict):
        return None
    operation = request.get("operation")
    allowed = {
        "capabilities",
        "observe",
        "list_files",
        "read_file",
        "execute_operation",
        "offer_submission",
    }
    return operation if isinstance(operation, str) and operation in allowed else None


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


__all__ = [
    "HYDRAULIC_REVIEW_CAPABILITY_ENV",
    "HYDRAULIC_REVIEW_SOCKET_ENV",
    "HydraulicReviewPrimeLifecycleEndpoint",
    "HydraulicReviewPrimeLifecycleEndpointError",
]
