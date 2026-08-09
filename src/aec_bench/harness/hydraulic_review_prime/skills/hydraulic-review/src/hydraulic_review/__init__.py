# ABOUTME: Gives Prime six async calls to one capability-scoped hydraulic-review lifecycle checkpoint.
# ABOUTME: Carries no package, run, checkpoint, profile, branch, verifier, evaluation, or host selector.

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from typing import Any

_SOCKET_ENV = "AEC_BENCH_HYDRAULIC_REVIEW_SOCKET"
_CAPABILITY_ENV = "AEC_BENCH_HYDRAULIC_REVIEW_CAPABILITY_TOKEN"
_MAX_MESSAGE_BYTES = 1024 * 1024


class LifecycleError(RuntimeError):
    """An explicit failure returned by the scoped lifecycle endpoint."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


async def capabilities() -> dict[str, Any]:
    """Return the exact operations exposed for the active checkpoint."""
    return await _call({"operation": "capabilities"})


async def observe() -> dict[str, Any]:
    """Return the current actor-visible checkpoint state."""
    return await _call({"operation": "observe"})


async def list_files(path: str = ".") -> dict[str, Any]:
    """List one actor-visible lifecycle directory."""
    return await _call({"operation": "list_files", "path": path})


async def read_file(path: str) -> dict[str, Any]:
    """Read one actor-visible lifecycle text file."""
    return await _call({"operation": "read_file", "path": path})


async def execute_operation(
    operation_id: str,
    visible_source_state_sha256: str,
    reason: str,
) -> dict[str, Any]:
    """Execute one declared operation for the active checkpoint and session."""
    return await _call(
        {
            "operation": "execute_operation",
            "operation_id": operation_id,
            "visible_source_state_sha256": visible_source_state_sha256,
            "reason": reason,
        }
    )


async def offer_submission(submission: dict[str, Any]) -> dict[str, Any]:
    """Offer one checkpoint submission without advancing the lifecycle."""
    return await _call({"operation": "offer_submission", "submission": submission})


async def _call(request: dict[str, Any]) -> dict[str, Any]:
    socket_path = os.environ.get(_SOCKET_ENV)
    capability = os.environ.get(_CAPABILITY_ENV)
    if not socket_path or not capability:
        raise LifecycleError("endpoint-unavailable", "scoped lifecycle endpoint is not configured")
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path, limit=_MAX_MESSAGE_BYTES + 1)
        payload = json.dumps(
            {"capability": capability, "request": request}, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        if len(payload) > _MAX_MESSAGE_BYTES:
            raise LifecycleError("request-too-large", "lifecycle request is too large")
        writer.write(payload + b"\n")
        await writer.drain()
        line = await reader.readline()
        if not line or len(line) > _MAX_MESSAGE_BYTES or not line.endswith(b"\n"):
            raise LifecycleError("transport-malformed", "lifecycle response is missing or malformed")
        response = json.loads(line)
        if not isinstance(response, dict):
            raise LifecycleError("transport-malformed", "lifecycle response must be an object")
        if "error" in response:
            error = response["error"]
            if (
                set(response) != {"error"}
                or not isinstance(error, dict)
                or not isinstance(error.get("code"), str)
                or not isinstance(error.get("detail"), str)
            ):
                raise LifecycleError("transport-malformed", "lifecycle error response is malformed")
            raise LifecycleError(error["code"], error["detail"])
        result = response.get("result")
        if not isinstance(result, dict) or set(response) != {"result"}:
            raise LifecycleError("transport-malformed", "lifecycle result response is malformed")
        return result
    except LifecycleError:
        raise
    except (OSError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise LifecycleError("endpoint-transport-failed", "scoped lifecycle transport failed") from exc
    finally:
        if "writer" in locals():
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


__all__ = [
    "LifecycleError",
    "capabilities",
    "execute_operation",
    "list_files",
    "observe",
    "offer_submission",
    "read_file",
]
