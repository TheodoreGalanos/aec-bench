# ABOUTME: Observes admitted Prime child spawns from an isolated IPython startup hook.
# ABOUTME: Keeps cell identity in async context and leaves upstream requests and responses intact.

from __future__ import annotations

import base64
import contextvars
import functools
import importlib
import json
import logging
import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol, cast

_MARKER = "# aec-bench-prime-call "


class _RlmRuntime(Protocol):
    host_request: Callable[[str, dict[str, Any] | None], Awaitable[dict[str, Any]]]


def load_ipython_extension(shell: Any) -> None:
    """Install once per kernel; this file runs in Prime's Python, not AEC-Bench's."""
    rlm = cast(_RlmRuntime, importlib.import_module("rlm"))

    if getattr(shell, "_aec_prime_spawn_hook", False):
        return
    root = Path(os.environ["AEC_BENCH_PRIME_SESSION_ROOT"]).resolve()
    context: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar("aec_prime_call", default=None)
    original_request = rlm.host_request

    def identify_cell(info: Any) -> None:
        # IPython runs this in the cell's execution context. Detached asyncio tasks
        # retain it when later cells execute, including before the spawn first runs.
        context.set(None)
        line = info.raw_cell.rstrip("\n").rsplit("\n", 1)[-1]
        if not line.startswith(_MARKER):
            return
        identity = json.loads(base64.b64decode(line[len(_MARKER) :], validate=True))
        if not isinstance(identity, dict) or set(identity) != {"parent_session_id", "parent_tool_call_id"}:
            raise ValueError("invalid AEC-Bench Prime call identity")
        if any(not isinstance(value, str) or not value for value in identity.values()):
            raise ValueError("invalid AEC-Bench Prime call identity")
        context.set(identity)

    def strip_identity(lines: list[str]) -> list[str]:
        return lines[:-1] if lines and lines[-1].startswith(_MARKER) else lines

    @functools.wraps(original_request)
    async def observe_request(request_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        identity = context.get()
        result = await original_request(request_type, payload)
        if request_type == "rlm.run" and identity is not None:
            try:
                _record_spawn(root, identity, result)
            except (OSError, ValueError, TypeError, KeyError):
                # Trace failure must not hide an admitted child from its parent.
                logging.getLogger(__name__).warning("AEC-Bench Prime spawn capture failed")
        return result

    shell.input_transformers_cleanup.append(strip_identity)
    shell.events.register("pre_run_cell", identify_cell)
    rlm.host_request = observe_request
    shell._aec_prime_spawn_hook = True


def _record_spawn(root: Path, identity: dict[str, str], result: dict[str, Any]) -> None:
    child_id = result["rlm_child_id"]
    directory = Path(result["session_dir"]).resolve()
    if (
        not isinstance(child_id, str)
        or not child_id
        or directory == root
        or not directory.is_relative_to(root)
        or directory.name != child_id
    ):
        raise ValueError("Prime child directory does not match its spawn handle")
    destination = directory / "aec-spawn.json"
    data = {**identity, "rlm_child_id": child_id}
    # One admission creates one child directory. Refuse to overwrite evidence.
    if destination.exists():
        raise ValueError("Prime child already has spawn evidence")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
