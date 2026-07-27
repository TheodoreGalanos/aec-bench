# ABOUTME: Runs the credential-holding provider broker and records every effect transition.
# ABOUTME: Separates request admission, provider effects, transport, and terminal receipts.

from __future__ import annotations

import ctypes
import json
import os
import socket
import struct
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any, Literal, Protocol, cast

from aec_bench.adapters.rlm.client import (
    ReplayRlmClient,
    RlmClient,
    RlmCompletionResponse,
    RlmMessage,
    ToolCall,
    ToolCapableRlmClient,
)
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.provider_broker import (
    ProviderBrokerCallPlane,
    ProviderBrokerCallReceipt,
    ProviderBrokerEffectUnknownCallReceipt,
    ProviderBrokerPolicy,
    ProviderBrokerReceipt,
    ProviderBrokerStatus,
)

_SO_PEERCRED = 17
_MAX_REQUEST_BYTES = 16 * 1024 * 1024
_PR_SET_DUMPABLE = 4


class ProviderBrokerError(RuntimeError):
    """Provider-broker transport, policy, or evidence failure."""


class ProviderBrokerReady(Protocol):
    """Minimal readiness signal accepted by the blocking broker server."""

    def set(self) -> None: ...


type _ProviderOperation = Literal["generate", "generate_with_tools"]


@dataclass(frozen=True, slots=True)
class _GenerateArguments:
    """Typed provider arguments for one plain generation request."""

    temperature: float | None


@dataclass(frozen=True, slots=True)
class _ToolArguments:
    """Typed provider arguments for one tool-capable generation request."""

    tool_name: str
    tool_description: str
    tool_parameters_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _AdmittedCall:
    """Fully decoded provider request that has passed every pre-effect gate."""

    request: dict[str, Any]
    operation: _ProviderOperation
    call_plane: ProviderBrokerCallPlane
    messages: tuple[RlmMessage, ...]
    system_prompt: str | None
    arguments: _GenerateArguments | _ToolArguments


@dataclass(frozen=True, slots=True)
class _CallOutcome:
    """One denied, completed, or effect-unknown broker call transition."""

    response: dict[str, Any]
    call: ProviderBrokerCallReceipt | None = None
    effect_unknown_call: ProviderBrokerEffectUnknownCallReceipt | None = None
    denied_reason: str | None = None
    terminal_failure: str | None = None


@dataclass(slots=True)
class _BrokerSession:
    """Mutable server-owned state reduced to one terminal immutable receipt."""

    policy: ProviderBrokerPolicy
    started_at: datetime
    calls: list[ProviderBrokerCallReceipt] = field(default_factory=list)
    effect_unknown_calls: list[ProviderBrokerEffectUnknownCallReceipt] = field(
        default_factory=list,
    )
    denied_calls: int = 0
    terminal_failure: str | None = None

    @property
    def terminal(self) -> bool:
        return self.terminal_failure is not None

    def deny(self) -> None:
        self.denied_calls += 1

    def fail(self, reason: str) -> None:
        if self.terminal_failure is None:
            self.terminal_failure = reason

    def apply(self, outcome: _CallOutcome) -> None:
        if outcome.call is not None:
            self.calls.append(outcome.call)
        if outcome.effect_unknown_call is not None:
            self.effect_unknown_calls.append(outcome.effect_unknown_call)
        if outcome.denied_reason is not None:
            self.deny()
        if outcome.terminal_failure is not None:
            self.fail(outcome.terminal_failure)


def serve_provider_broker(
    *,
    socket_path: Path,
    expected_peer_pid: int,
    policy: ProviderBrokerPolicy,
    client: RlmClient,
    ready: ProviderBrokerReady | Event | None = None,
    receipt_path: Path | None = None,
) -> ProviderBrokerReceipt:
    """Serve one policy-bound broker until finalization or its time cap."""
    if not isinstance(client, ReplayRlmClient):
        disable_broker_process_dumpability()
    path = Path(socket_path)
    _prepare_socket_parent(path)
    session = _BrokerSession(
        policy=policy,
        started_at=datetime.now(UTC),
    )
    started_monotonic = time.monotonic()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        _start_broker_server(
            server=server,
            path=path,
            ready=ready,
        )
        return _serve_broker_session(
            server=server,
            expected_peer_pid=expected_peer_pid,
            client=client,
            session=session,
            started_monotonic=started_monotonic,
            receipt_path=receipt_path,
        )
    finally:
        server.close()
        path.unlink(missing_ok=True)


def _start_broker_server(
    *,
    server: socket.socket,
    path: Path,
    ready: ProviderBrokerReady | Event | None,
) -> None:
    server.bind(str(path))
    path.chmod(0o600)
    server.listen()
    server.settimeout(0.25)
    if ready is not None:
        ready.set()


def _serve_broker_session(
    *,
    server: socket.socket,
    expected_peer_pid: int,
    client: RlmClient,
    session: _BrokerSession,
    started_monotonic: float,
    receipt_path: Path | None,
) -> ProviderBrokerReceipt:
    while not session.terminal:
        elapsed = time.monotonic() - started_monotonic
        terminal_reason = _broker_terminal_reason(
            elapsed_seconds=elapsed,
            timeout_seconds=session.policy.timeout_seconds,
            expected_peer_pid=expected_peer_pid,
        )
        if terminal_reason is not None:
            session.fail(terminal_reason)
            break
        try:
            connection, _ = server.accept()
        except TimeoutError:
            continue
        with connection:
            finalized = _serve_broker_connection(
                connection=connection,
                expected_peer_pid=expected_peer_pid,
                client=client,
                session=session,
                elapsed_seconds=elapsed,
                receipt_path=receipt_path,
            )
        if finalized is not None:
            return finalized
    receipt = _build_receipt(session=session)
    _persist_receipt(receipt, receipt_path)
    return receipt


def _broker_terminal_reason(
    *,
    elapsed_seconds: float,
    timeout_seconds: int,
    expected_peer_pid: int,
) -> str | None:
    if elapsed_seconds >= timeout_seconds:
        return "provider broker time budget exhausted"
    if not _process_is_alive(expected_peer_pid):
        return "provider broker peer exited without finalization"
    return None


def _serve_broker_connection(
    *,
    connection: socket.socket,
    expected_peer_pid: int,
    client: RlmClient,
    session: _BrokerSession,
    elapsed_seconds: float,
    receipt_path: Path | None,
) -> ProviderBrokerReceipt | None:
    request = _receive_authorized_request(
        connection=connection,
        expected_peer_pid=expected_peer_pid,
        client=client,
        session=session,
    )
    if request is None:
        return None
    if _is_authorized_finalization(request, session.policy):
        return _finalize_broker_connection(
            connection=connection,
            session=session,
            receipt_path=receipt_path,
        )
    outcome = _handle_call(
        request=request,
        policy=session.policy,
        client=client,
        calls=tuple(session.calls),
        elapsed_seconds=elapsed_seconds,
    )
    session.apply(outcome)
    if not _send_payload(connection, outcome.response) and outcome.call is not None:
        session.fail(
            "provider broker response transport failed after provider effect",
        )
    return None


def _receive_authorized_request(
    *,
    connection: socket.socket,
    expected_peer_pid: int,
    client: RlmClient,
    session: _BrokerSession,
) -> dict[str, Any] | None:
    try:
        _validate_peer_identity(
            connection,
            expected_peer_pid=expected_peer_pid,
            client=client,
        )
        raw_request = _receive_payload(connection)
        if not isinstance(raw_request, dict):
            raise ProviderBrokerError(
                "provider broker request must be an object",
            )
        return cast(dict[str, Any], raw_request)
    except (OSError, TypeError, ValueError, ProviderBrokerError) as error:
        session.deny()
        _send_payload(
            connection,
            _malformed_request_response(str(error)),
        )
        return None


def _is_authorized_finalization(
    request: dict[str, Any],
    policy: ProviderBrokerPolicy,
) -> bool:
    return request.get("operation") == "finalize" and request.get("policy_sha256") == policy.content_sha256


def _finalize_broker_connection(
    *,
    connection: socket.socket,
    session: _BrokerSession,
    receipt_path: Path | None,
) -> ProviderBrokerReceipt:
    receipt = _build_receipt(session=session)
    _persist_receipt(receipt, receipt_path)
    _send_payload(
        connection,
        {"receipt": receipt.model_dump(mode="json")},
    )
    return receipt


def _send_payload(
    connection: socket.socket,
    payload: dict[str, Any],
) -> bool:
    try:
        connection.sendall(_encode_payload(payload))
    except (OSError, TypeError, ValueError, ProviderBrokerError):
        return False
    return True


def disable_broker_process_dumpability() -> None:
    """Block same-UID ptrace and `/proc/<pid>` credential inspection on Linux."""
    if not sys.platform.startswith("linux"):
        raise ProviderBrokerError(
            "provider broker dumpability control requires Linux",
        )
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0)
    if result != 0:
        error_number = ctypes.get_errno()
        raise ProviderBrokerError(
            f"provider broker could not disable process dumpability (errno={error_number})",
        )


def _handle_call(
    *,
    request: dict[str, Any],
    policy: ProviderBrokerPolicy,
    client: RlmClient,
    calls: tuple[ProviderBrokerCallReceipt, ...],
    elapsed_seconds: float,
) -> _CallOutcome:
    try:
        admitted = _admit_call(
            request=request,
            policy=policy,
            calls=calls,
            elapsed_seconds=elapsed_seconds,
        )
    except (TypeError, ValueError, ProviderBrokerError) as error:
        return _malformed_request_outcome(str(error))
    if isinstance(admitted, _CallOutcome):
        return admitted
    return _execute_admitted_call(
        admitted=admitted,
        policy=policy,
        client=client,
        calls=calls,
        elapsed_seconds=elapsed_seconds,
    )


def _admit_call(
    *,
    request: dict[str, Any],
    policy: ProviderBrokerPolicy,
    calls: tuple[ProviderBrokerCallReceipt, ...],
    elapsed_seconds: float,
) -> _AdmittedCall | _CallOutcome:
    operation = request.get("operation")
    if operation not in {"generate", "generate_with_tools"}:
        return _denied_outcome("provider broker operation is not authorized")
    if request.get("policy_sha256") != policy.content_sha256:
        return _denied_outcome("provider broker policy is not authorized")
    if request.get("model") != policy.model:
        return _denied_outcome("provider broker model is not authorized")
    call_plane = _authorized_call_plane(request.get("call_plane"))
    if call_plane is None:
        return _denied_outcome("provider broker call plane is not authorized")
    budget_reason = _call_budget_rejection(
        policy=policy,
        calls=calls,
        call_plane=call_plane,
        elapsed_seconds=elapsed_seconds,
    )
    if budget_reason is not None:
        terminal_failure = budget_reason if budget_reason == "provider broker time budget exhausted" else None
        return _denied_outcome(
            budget_reason,
            terminal_failure=terminal_failure,
        )
    return _decode_admitted_call(
        request=request,
        operation=cast(_ProviderOperation, operation),
        call_plane=call_plane,
    )


def _authorized_call_plane(value: object) -> ProviderBrokerCallPlane | None:
    if not isinstance(value, str):
        return None
    try:
        return ProviderBrokerCallPlane(value)
    except ValueError:
        return None


def _call_budget_rejection(
    *,
    policy: ProviderBrokerPolicy,
    calls: tuple[ProviderBrokerCallReceipt, ...],
    call_plane: ProviderBrokerCallPlane,
    elapsed_seconds: float,
) -> str | None:
    if elapsed_seconds >= policy.timeout_seconds:
        return "provider broker time budget exhausted"
    if len(calls) >= policy.max_calls:
        return "provider broker call budget exhausted"
    plane_call_count = sum(call.call_plane is call_plane for call in calls)
    plane_call_limit = (
        policy.max_main_calls if call_plane is ProviderBrokerCallPlane.MAIN else policy.max_auxiliary_calls
    )
    if plane_call_count >= plane_call_limit:
        return f"provider broker {call_plane.value} call budget exhausted"
    observed_tokens = sum(_call_tokens(call) for call in calls)
    if policy.max_total_tokens is not None and observed_tokens >= policy.max_total_tokens:
        return "provider broker token budget exhausted"
    observed_cost = sum(call.cost_usd for call in calls)
    if policy.max_cost_usd is not None and observed_cost >= policy.max_cost_usd:
        return "provider broker cost budget exhausted"
    return None


def _decode_admitted_call(
    *,
    request: dict[str, Any],
    operation: _ProviderOperation,
    call_plane: ProviderBrokerCallPlane,
) -> _AdmittedCall:
    messages = tuple(_messages_from_payload(request.get("messages")))
    system_prompt = _optional_string(
        request.get("system_prompt"),
        label="system_prompt",
    )
    if operation == "generate":
        raw_temperature = request.get("temperature")
        if raw_temperature is not None and not isinstance(
            raw_temperature,
            int | float,
        ):
            raise ProviderBrokerError("temperature must be numeric or null")
        arguments: _GenerateArguments | _ToolArguments = _GenerateArguments(
            temperature=(None if raw_temperature is None else float(raw_temperature)),
        )
    else:
        arguments = _tool_arguments_from_request(request)
    return _AdmittedCall(
        request=request,
        operation=operation,
        call_plane=call_plane,
        messages=messages,
        system_prompt=system_prompt,
        arguments=arguments,
    )


def _tool_arguments_from_request(
    request: dict[str, Any],
) -> _ToolArguments:
    tool_name = _required_string(request.get("tool_name"), label="tool_name")
    tool_description = _required_string(
        request.get("tool_description"),
        label="tool_description",
    )
    raw_schema = request.get("tool_parameters_schema")
    if not isinstance(raw_schema, dict):
        raise ProviderBrokerError("tool_parameters_schema must be an object")
    return _ToolArguments(
        tool_name=tool_name,
        tool_description=tool_description,
        tool_parameters_schema=cast(dict[str, Any], raw_schema),
    )


def _execute_admitted_call(
    *,
    admitted: _AdmittedCall,
    policy: ProviderBrokerPolicy,
    client: RlmClient,
    calls: tuple[ProviderBrokerCallReceipt, ...],
    elapsed_seconds: float,
) -> _CallOutcome:
    started_at = datetime.now(UTC)
    try:
        response = _invoke_provider(
            admitted=admitted,
            model=policy.model,
            client=client,
        )
        return _metered_call_outcome(
            admitted=admitted,
            policy=policy,
            client=client,
            calls=calls,
            response=response,
            started_at=started_at,
            elapsed_seconds=elapsed_seconds,
        )
    except Exception:
        return _effect_unknown_outcome(
            admitted=admitted,
            model=policy.model,
            call_index=len(calls) + 1,
            started_at=started_at,
        )


def _invoke_provider(
    *,
    admitted: _AdmittedCall,
    model: str,
    client: RlmClient,
) -> RlmCompletionResponse:
    messages = list(admitted.messages)
    if isinstance(admitted.arguments, _GenerateArguments):
        return client.generate(
            model=model,
            messages=messages,
            system_prompt=admitted.system_prompt,
            temperature=admitted.arguments.temperature,
        )
    if not isinstance(client, ToolCapableRlmClient):
        return client.generate(
            model=model,
            messages=messages,
            system_prompt=admitted.system_prompt,
        )
    return client.generate_with_tools(
        model=model,
        messages=messages,
        system_prompt=admitted.system_prompt,
        tool_name=admitted.arguments.tool_name,
        tool_description=admitted.arguments.tool_description,
        tool_parameters_schema=admitted.arguments.tool_parameters_schema,
    )


def _metered_call_outcome(
    *,
    admitted: _AdmittedCall,
    policy: ProviderBrokerPolicy,
    client: RlmClient,
    calls: tuple[ProviderBrokerCallReceipt, ...],
    response: RlmCompletionResponse,
    started_at: datetime,
    elapsed_seconds: float,
) -> _CallOutcome:
    finished_at = datetime.now(UTC)
    cost = _response_cost(
        model=policy.model,
        response=response,
        client=client,
    )
    response_payload = _response_payload(response)
    call = ProviderBrokerCallReceipt(
        call_index=len(calls) + 1,
        call_plane=admitted.call_plane,
        method=admitted.operation,
        model=policy.model,
        request_sha256=canonical_content_sha256(admitted.request),
        response_sha256=canonical_content_sha256(response_payload),
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cache_read_tokens=response.cache_read_tokens,
        cache_write_tokens=response.cache_write_tokens,
        cost_usd=cost,
        started_at=started_at,
        finished_at=finished_at,
    )
    fatal_reason = _response_budget_failure(
        policy=policy,
        calls=calls,
        call=call,
        elapsed_seconds=elapsed_seconds,
    )
    if fatal_reason is not None:
        return _CallOutcome(
            response={
                "response": _response_payload(
                    RlmCompletionResponse(error_message=fatal_reason),
                ),
            },
            call=call,
            denied_reason=fatal_reason,
            terminal_failure=fatal_reason,
        )
    return _CallOutcome(
        response={"response": response_payload},
        call=call,
    )


def _response_budget_failure(
    *,
    policy: ProviderBrokerPolicy,
    calls: tuple[ProviderBrokerCallReceipt, ...],
    call: ProviderBrokerCallReceipt,
    elapsed_seconds: float,
) -> str | None:
    next_tokens = sum(_call_tokens(observed) for observed in calls) + _call_tokens(
        call,
    )
    if policy.max_total_tokens is not None and next_tokens > policy.max_total_tokens:
        return "provider broker response exceeded token budget"
    next_cost = sum(observed.cost_usd for observed in calls) + call.cost_usd
    if policy.max_cost_usd is not None and next_cost > policy.max_cost_usd:
        return "provider broker response exceeded cost budget"
    call_seconds = (call.finished_at - call.started_at).total_seconds()
    if call_seconds + elapsed_seconds > policy.timeout_seconds:
        return "provider broker response exceeded time budget"
    return None


def _call_tokens(call: ProviderBrokerCallReceipt) -> int:
    return call.input_tokens + call.output_tokens + call.cache_read_tokens + call.cache_write_tokens


def _effect_unknown_outcome(
    *,
    admitted: _AdmittedCall,
    model: str,
    call_index: int,
    started_at: datetime,
) -> _CallOutcome:
    reason = "provider broker effect outcome is unknown"
    unknown_call = ProviderBrokerEffectUnknownCallReceipt(
        call_index=call_index,
        call_plane=admitted.call_plane,
        method=admitted.operation,
        model=model,
        request_sha256=canonical_content_sha256(admitted.request),
        failure_code="provider_effect_outcome_unknown",
        started_at=started_at,
        recorded_at=datetime.now(UTC),
    )
    return _CallOutcome(
        response={
            "response": _response_payload(
                RlmCompletionResponse(error_message=reason),
            ),
        },
        effect_unknown_call=unknown_call,
        terminal_failure=reason,
    )


def _denied_outcome(
    reason: str,
    *,
    terminal_failure: str | None = None,
) -> _CallOutcome:
    return _CallOutcome(
        response={
            "response": _response_payload(
                RlmCompletionResponse(error_message=reason),
            ),
        },
        denied_reason=reason,
        terminal_failure=terminal_failure,
    )


def _malformed_request_response(reason: str) -> dict[str, Any]:
    return {
        "response": _response_payload(
            RlmCompletionResponse(
                error_message="provider broker denied malformed request",
            ),
        ),
        "broker_error": reason,
    }


def _malformed_request_outcome(reason: str) -> _CallOutcome:
    return _CallOutcome(
        response=_malformed_request_response(reason),
        denied_reason=reason,
    )


def _build_receipt(
    *,
    session: _BrokerSession,
) -> ProviderBrokerReceipt:
    status = ProviderBrokerStatus.COMPLETED
    if session.effect_unknown_calls:
        status = ProviderBrokerStatus.EFFECT_UNKNOWN
    elif session.terminal_failure is not None:
        status = ProviderBrokerStatus.FAILED
    return ProviderBrokerReceipt(
        broker_id=session.policy.broker_id,
        policy_sha256=session.policy.content_sha256,
        status=status,
        calls=tuple(session.calls),
        effect_unknown_calls=tuple(session.effect_unknown_calls),
        denied_calls=session.denied_calls,
        total_calls=len(session.calls) + len(session.effect_unknown_calls),
        total_input_tokens=sum(call.input_tokens for call in session.calls),
        total_output_tokens=sum(call.output_tokens for call in session.calls),
        total_cache_read_tokens=sum(call.cache_read_tokens for call in session.calls),
        total_cache_write_tokens=sum(call.cache_write_tokens for call in session.calls),
        total_cost_usd=sum(call.cost_usd for call in session.calls),
        started_at=session.started_at,
        finished_at=datetime.now(UTC),
        failure_reason=session.terminal_failure,
    )


def _persist_receipt(
    receipt: ProviderBrokerReceipt,
    receipt_path: Path | None,
) -> None:
    if receipt_path is None:
        return
    target = Path(receipt_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(
        receipt.model_dump_json() + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(target)


def _prepare_socket_parent(path: Path) -> None:
    if len(os.fsencode(path)) >= 104:
        raise ProviderBrokerError("provider broker socket path is too long")
    parent_existed = path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not parent_existed:
        path.parent.chmod(0o700)
    if path.exists() or path.is_symlink():
        raise ProviderBrokerError("provider broker refuses a pre-existing socket path")


def _process_is_alive(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _validate_peer_identity(
    connection: socket.socket,
    *,
    expected_peer_pid: int,
    client: RlmClient,
) -> None:
    if sys.platform.startswith("linux"):
        credentials = connection.getsockopt(
            socket.SOL_SOCKET,
            _SO_PEERCRED,
            struct.calcsize("3i"),
        )
        peer_pid, _uid, _gid = struct.unpack("3i", credentials)
        if peer_pid != expected_peer_pid:
            raise ProviderBrokerError(
                "provider broker peer process is not authorized",
            )
        return
    if isinstance(client, ReplayRlmClient) and expected_peer_pid == os.getpid():
        return
    raise ProviderBrokerError(
        "provider broker requires Linux SO_PEERCRED for production execution",
    )


def _response_cost(
    *,
    model: str,
    response: RlmCompletionResponse,
    client: RlmClient,
) -> float:
    estimated = estimate_cost_usd(
        model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cache_read_tokens=response.cache_read_tokens,
        cache_write_tokens=response.cache_write_tokens,
    )
    if estimated is not None:
        return estimated
    if isinstance(client, ReplayRlmClient):
        return 0.0
    raise ProviderBrokerError(
        "provider broker cannot meter cost for the authorized model",
    )


def _message_payload(message: RlmMessage) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
        "tool_call_id": message.tool_call_id,
        "tool_name": message.tool_name,
    }


def _messages_from_payload(value: object) -> list[RlmMessage]:
    if not isinstance(value, list):
        raise ProviderBrokerError("messages must be a list")
    messages: list[RlmMessage] = []
    for item in value:
        if not isinstance(item, dict):
            raise ProviderBrokerError("each message must be an object")
        messages.append(
            RlmMessage(
                role=_required_string(item.get("role"), label="message role"),
                content=_required_string(
                    item.get("content"),
                    label="message content",
                    allow_empty=True,
                ),
                tool_call_id=_optional_string(
                    item.get("tool_call_id"),
                    label="tool_call_id",
                ),
                tool_name=_optional_string(
                    item.get("tool_name"),
                    label="tool_name",
                ),
            ),
        )
    return messages


def _response_payload(response: RlmCompletionResponse) -> dict[str, Any]:
    return {
        "output_text": response.output_text,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cache_read_tokens": response.cache_read_tokens,
        "cache_write_tokens": response.cache_write_tokens,
        "error_message": response.error_message,
        "done": response.done,
        "tool_call": (
            {
                "name": response.tool_call.name,
                "code": response.tool_call.code,
                "call_id": response.tool_call.call_id,
            }
            if response.tool_call is not None
            else None
        ),
    }


def _response_from_payload(payload: dict[str, Any]) -> RlmCompletionResponse:
    raw = payload.get("response")
    if not isinstance(raw, dict):
        raise ProviderBrokerError("provider broker response evidence is missing")
    tool_payload = raw.get("tool_call")
    tool_call: ToolCall | None = None
    if tool_payload is not None:
        if not isinstance(tool_payload, dict):
            raise ProviderBrokerError("provider broker tool call must be an object")
        tool_call = ToolCall(
            name=_required_string(tool_payload.get("name"), label="tool name"),
            code=_required_string(
                tool_payload.get("code"),
                label="tool code",
                allow_empty=True,
            ),
            call_id=_required_string(
                tool_payload.get("call_id"),
                label="tool call id",
            ),
        )
    try:
        return RlmCompletionResponse(
            output_text=str(raw.get("output_text", "")),
            input_tokens=int(raw.get("input_tokens", 0)),
            output_tokens=int(raw.get("output_tokens", 0)),
            cache_read_tokens=int(raw.get("cache_read_tokens", 0)),
            cache_write_tokens=int(raw.get("cache_write_tokens", 0)),
            error_message=cast(str | None, raw.get("error_message")),
            done=bool(raw.get("done", False)),
            tool_call=tool_call,
        )
    except (TypeError, ValueError) as error:
        raise ProviderBrokerError(
            f"provider broker response metrics are malformed: {error}",
        ) from error


def _encode_payload(payload: object) -> bytes:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > _MAX_REQUEST_BYTES:
        raise ProviderBrokerError("provider broker payload exceeds size limit")
    return encoded


def _receive_payload(connection: socket.socket) -> object:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = connection.recv(min(65_536, _MAX_REQUEST_BYTES + 1 - size))
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        if size > _MAX_REQUEST_BYTES:
            raise ProviderBrokerError("provider broker payload exceeds size limit")
    if not chunks:
        raise ProviderBrokerError("provider broker payload is empty")
    try:
        return json.loads(b"".join(chunks))
    except json.JSONDecodeError as error:
        raise ProviderBrokerError("provider broker payload is not valid JSON") from error


def _required_string(
    value: object,
    *,
    label: str,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ProviderBrokerError(f"{label} must be a string")
    return value


def _optional_string(value: object, *, label: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, label=label, allow_empty=True)
