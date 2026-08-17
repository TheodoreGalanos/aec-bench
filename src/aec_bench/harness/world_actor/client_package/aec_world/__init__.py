# ABOUTME: Gives process-based actors a standalone async client for the scoped world endpoint.
# ABOUTME: Preserves action request identity and surfaces explicit transport outcome classes.

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import uuid
from typing import Any, Literal

_PROTOCOL = "aec-bench/world-actor/1"
_SOCKET_ENV = "AEC_BENCH_WORLD_ACTOR_SOCKET"
_CAPABILITY_ENV = "AEC_BENCH_WORLD_ACTOR_CAPABILITY_TOKEN"
_PROTOCOL_ENV = "AEC_BENCH_WORLD_ACTOR_PROTOCOL"
_MAX_REQUEST_BYTES = 1024 * 1024
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024

ActorOutcome = Literal["not-dispatched", "completed", "unknown"]
_OUTCOMES = frozenset({"not-dispatched", "completed", "unknown"})


class ActorError(RuntimeError):
    """A safe structured failure from the local actor boundary."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        request_id: str | None,
        outcome: ActorOutcome,
        retryable: bool,
    ) -> None:
        self.code = code
        self.detail = detail
        self.request_id = request_id
        self.outcome = outcome
        self.retryable = retryable
        super().__init__(f"{code}: {detail}")


async def capabilities() -> dict[str, Any]:
    """Return the frozen task-owned actor capability catalogue."""
    return await _call({"operation": "capabilities"}, action_request_id=None)


async def observe() -> dict[str, Any]:
    """Return the current actor-visible observation and opaque decision ID."""
    return await _call({"operation": "observe"}, action_request_id=None)


async def invoke(
    action_name: str,
    arguments: dict[str, Any],
    *,
    decision_id: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Invoke one task-owned action without automatically retrying it."""
    action_request_id = request_id or str(uuid.uuid4())
    return await _call(
        {
            "operation": "invoke",
            "request_id": action_request_id,
            "decision_id": decision_id,
            "action_name": action_name,
            "arguments": arguments,
        },
        action_request_id=action_request_id,
    )


async def _call(request: dict[str, Any], *, action_request_id: str | None) -> dict[str, Any]:
    socket_path = os.environ.get(_SOCKET_ENV)
    capability = os.environ.get(_CAPABILITY_ENV)
    protocol = os.environ.get(_PROTOCOL_ENV)
    if not socket_path or not capability or protocol != _PROTOCOL:
        raise ActorError(
            "actor-unavailable",
            "The scoped world actor endpoint is not configured for the supported protocol.",
            request_id=action_request_id,
            outcome="not-dispatched",
            retryable=False,
        )

    transport_request_id = str(uuid.uuid4())
    try:
        payload = json.dumps(
            {
                "protocol": _PROTOCOL,
                "transport_request_id": transport_request_id,
                "capability": capability,
                "request": request,
            },
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ActorError(
            "actor-request-invalid",
            "The world actor request is not valid JSON.",
            request_id=action_request_id,
            outcome="not-dispatched",
            retryable=False,
        ) from exc
    if len(payload) > _MAX_REQUEST_BYTES:
        raise ActorError(
            "request-too-large",
            "The world actor request is too large.",
            request_id=action_request_id,
            outcome="not-dispatched",
            retryable=False,
        )

    writer: asyncio.StreamWriter | None = None
    request_sent = False
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path, limit=_MAX_RESPONSE_BYTES + 1)
        writer.write(payload + b"\n")
        await writer.drain()
        request_sent = True
        line = await reader.readline()
        if not line or len(line) > _MAX_RESPONSE_BYTES or not line.endswith(b"\n"):
            raise _malformed_response(action_request_id, request_sent=request_sent)
        trailing = await asyncio.wait_for(reader.read(_MAX_RESPONSE_BYTES + 1), timeout=1.0)
        if len(trailing) > _MAX_RESPONSE_BYTES or trailing.strip():
            raise _malformed_response(action_request_id, request_sent=request_sent)
        return _decode_response(
            line,
            transport_request_id=transport_request_id,
            action_request_id=action_request_id,
            request_sent=request_sent,
        )
    except ActorError:
        raise
    except (OSError, TimeoutError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ActorError(
            "actor-transport-failed",
            "The scoped world actor transport failed.",
            request_id=action_request_id,
            outcome="unknown" if action_request_id is not None and request_sent else "not-dispatched",
            retryable=True,
        ) from exc
    finally:
        if writer is not None:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


def _decode_response(
    line: bytes,
    *,
    transport_request_id: str,
    action_request_id: str | None,
    request_sent: bool,
) -> dict[str, Any]:
    try:
        response = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _malformed_response(action_request_id, request_sent=request_sent) from exc
    if not isinstance(response, dict):
        raise _malformed_response(action_request_id, request_sent=request_sent)
    if response.get("protocol") != _PROTOCOL or response.get("transport_request_id") != transport_request_id:
        raise _malformed_response(action_request_id, request_sent=request_sent)
    ok = response.get("ok")
    if ok is True:
        if set(response) != {"protocol", "transport_request_id", "ok", "result"}:
            raise _malformed_response(action_request_id, request_sent=request_sent)
        result = response.get("result")
        if not isinstance(result, dict):
            raise _malformed_response(action_request_id, request_sent=request_sent)
        return result
    if ok is not False or set(response) != {"protocol", "transport_request_id", "ok", "error"}:
        raise _malformed_response(action_request_id, request_sent=request_sent)
    error = response.get("error")
    if not isinstance(error, dict) or not set(error) <= {
        "code",
        "detail",
        "request_id",
        "outcome",
        "retryable",
    }:
        raise _malformed_response(action_request_id, request_sent=request_sent)
    required = {"code", "detail", "outcome", "retryable"}
    if not required <= set(error):
        raise _malformed_response(action_request_id, request_sent=request_sent)
    code = error.get("code")
    detail = error.get("detail")
    outcome = error.get("outcome")
    retryable = error.get("retryable")
    request_id = error.get("request_id")
    if (
        not isinstance(code, str)
        or not code
        or not isinstance(detail, str)
        or not detail
        or outcome not in _OUTCOMES
        or not isinstance(retryable, bool)
        or (request_id is not None and (not isinstance(request_id, str) or not request_id))
    ):
        raise _malformed_response(action_request_id, request_sent=request_sent)
    raise ActorError(
        code,
        detail,
        request_id=request_id if isinstance(request_id, str) else action_request_id,
        outcome=outcome,
        retryable=retryable,
    )


def _malformed_response(request_id: str | None, *, request_sent: bool) -> ActorError:
    return ActorError(
        "transport-malformed",
        "The world actor response is malformed.",
        request_id=request_id,
        outcome="unknown" if request_id is not None and request_sent else "not-dispatched",
        retryable=False,
    )


__all__ = ["ActorError", "capabilities", "invoke", "observe"]
