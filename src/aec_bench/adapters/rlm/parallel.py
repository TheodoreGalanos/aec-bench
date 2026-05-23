# ABOUTME: General-purpose concurrent execution for sub-calls and LLM queries.
# ABOUTME: Runs callables via ThreadPoolExecutor, preserves order, wraps errors.

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParallelError:
    """Wraps an exception from a failed parallel callable.

    Returned in the results list at the same index as the failed
    callable.  The agent can check ``isinstance(result, ParallelError)``
    to detect failures without losing successful results.
    """

    index: int
    error: str


def parallel(
    callables: list[Callable[[], Any]],
    max_workers: int = 4,
) -> list[Any]:
    """Run callables concurrently and return results in input order.

    Each callable is submitted to a ``ThreadPoolExecutor``.  Results
    are collected and returned in the same order as the input list.

    If a callable raises an exception, its slot in the results list
    contains a :class:`ParallelError` instead of propagating the
    exception.  This lets the agent inspect partial results and retry
    failures selectively.

    Usage from REPL::

        results = parallel([
            lambda: extract(text=doc_a, fields=['speed']),
            lambda: extract(text=doc_b, fields=['speed']),
            lambda: llm_query("Write section 1..."),
        ])
        facts_a, facts_b, section1 = results
    """
    if not callables:
        return []

    results: list[Any] = [None] * len(callables)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {pool.submit(fn): i for i, fn in enumerate(callables)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = ParallelError(index=idx, error=str(exc))

    return results
