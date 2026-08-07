# ABOUTME: Gives Prime three async calls to the capability-scoped AECBench world actor endpoint.
# ABOUTME: Carries no run selector, host control, hidden state, verifier, or evaluation access.

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import uuid
from typing import Any

_SOCKET_ENV = "AEC_BENCH_WORLD_ACTOR_SOCKET"
_CAPABILITY_ENV = "AEC_BENCH_WORLD_ACTOR_CAPABILITY_TOKEN"
_MAX_MESSAGE_BYTES = 1024 * 1024


class ActorError(RuntimeError):
    """An explicit failure returned by the scoped actor endpoint."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


async def capabilities() -> dict[str, Any]:
    """Return the current task-owned actor capability catalogue."""
    return await _call({"operation": "capabilities"})


async def observe() -> dict[str, Any]:
    """Return the current actor-visible observation and opaque decision ID."""
    return await _call({"operation": "observe"})


async def invoke(
    action_name: str,
    arguments: dict[str, Any],
    *,
    decision_id: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Invoke one task-owned action without selecting a run or host operation."""
    return await _call(
        {
            "operation": "invoke",
            "request_id": request_id or str(uuid.uuid4()),
            "decision_id": decision_id,
            "action_name": action_name,
            "arguments": arguments,
        }
    )


async def _call(request: dict[str, Any]) -> dict[str, Any]:
    socket_path = os.environ.get(_SOCKET_ENV)
    capability = os.environ.get(_CAPABILITY_ENV)
    if not socket_path or not capability:
        raise ActorError("actor-unavailable", "scoped actor endpoint is not configured")
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path, limit=_MAX_MESSAGE_BYTES + 1)
        payload = json.dumps(
            {"capability": capability, "request": request}, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        if len(payload) > _MAX_MESSAGE_BYTES:
            raise ActorError("request-too-large", "actor request is too large")
        writer.write(payload + b"\n")
        await writer.drain()
        line = await reader.readline()
        if not line or len(line) > _MAX_MESSAGE_BYTES or not line.endswith(b"\n"):
            raise ActorError("transport-malformed", "actor response is missing or malformed")
        response = json.loads(line)
        if not isinstance(response, dict):
            raise ActorError("transport-malformed", "actor response must be an object")
        if "error" in response:
            error = response["error"]
            if (
                set(response) != {"error"}
                or not isinstance(error, dict)
                or not isinstance(error.get("code"), str)
                or not isinstance(error.get("detail"), str)
            ):
                raise ActorError("transport-malformed", "actor error response is malformed")
            raise ActorError(error["code"], error["detail"])
        result = response.get("result")
        if not isinstance(result, dict) or set(response) != {"result"}:
            raise ActorError("transport-malformed", "actor result response is malformed")
        return result
    except ActorError:
        raise
    except (OSError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ActorError("actor-transport-failed", "scoped actor transport failed") from exc
    finally:
        if "writer" in locals():
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


__all__ = ["ActorError", "capabilities", "invoke", "observe"]
