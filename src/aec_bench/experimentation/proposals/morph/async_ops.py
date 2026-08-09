# ABOUTME: Shields provider and receipt-bearing transitions from partial cancellation.
# ABOUTME: Waits for background work and cleanup before propagating cancellation.

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar

_ResultT = TypeVar("_ResultT")


async def run_provisioning_call(
    operation: Callable[[], _ResultT],
    *,
    label: str,
    cancel_cleanup: Callable[[_ResultT | None], Awaitable[list[Exception]]],
) -> _ResultT:
    """Finish a provider thread and reclaim late resources after cancellation."""

    worker = asyncio.create_task(asyncio.to_thread(operation))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancellation:
        result: _ResultT | None = None
        failures: list[Exception] = []
        try:
            result = await worker
        except Exception as error:
            failures.append(error)
        try:
            failures.extend(await cancel_cleanup(result))
        except Exception as error:
            failures.append(error)
        if failures:
            raise BaseExceptionGroup(
                f"proposal Morph Harbor {label} was cancelled and cleanup failed",
                [cancellation, *failures],
            ) from cancellation
        raise


async def run_transition_call(operation: Callable[[], _ResultT]) -> _ResultT:
    """Do not leave a host transition thread running after cancellation."""

    worker = asyncio.create_task(asyncio.to_thread(operation))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancellation:
        try:
            await worker
        except Exception as error:
            raise BaseExceptionGroup(
                "proposal Morph host transition was cancelled and failed",
                [cancellation, error],
            ) from cancellation
        raise


async def run_boundary_transition(
    operation: Callable[[], Coroutine[Any, Any, _ResultT]],
) -> _ResultT:
    """Let a whole receipt-bearing transition finish before propagating cancellation."""

    worker = asyncio.create_task(operation())
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancellation:
        try:
            await worker
        except BaseException as error:
            raise BaseExceptionGroup(
                "proposal Morph boundary transition was cancelled and failed",
                [cancellation, error],
            ) from cancellation
        raise
