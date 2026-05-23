# ABOUTME: Ordered log of sub-call invocations for sibling sharing and debugging.
# ABOUTME: Auto-records type, args, result, tokens. Queryable by type, persistable to scratchpad.

from __future__ import annotations

import threading
import time
from typing import Any


class SubcallLog:
    """Records sub-call invocations so later calls can reference earlier results.

    Injected into the REPL as ``SUBCALL_LOG``.  The agent (or subsequent
    sub-calls via the scratchpad) can query what previous sub-calls
    returned without the parent having to relay context manually.

    Usage from REPL::

        SUBCALL_LOG.all()              # full ordered history
        SUBCALL_LOG.last(3)            # 3 most recent entries
        SUBCALL_LOG.by_type("extract") # all extract() results
        str(SUBCALL_LOG)               # readable summary
    """

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def record(
        self,
        *,
        subcall_type: str,
        args_summary: str,
        result_summary: Any,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record a sub-call invocation."""
        entry = {
            "type": subcall_type,
            "args": args_summary,
            "result": result_summary,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "timestamp": time.monotonic(),
        }
        with self._lock:
            self._entries.append(entry)

    def all(self) -> list[dict[str, Any]]:
        """Return the full ordered history of sub-call invocations."""
        return list(self._entries)

    def last(self, n: int = 1) -> list[dict[str, Any]]:
        """Return the *n* most recent entries."""
        return list(self._entries[-n:])

    def by_type(self, subcall_type: str) -> list[dict[str, Any]]:
        """Return all entries matching *subcall_type*."""
        return [e for e in self._entries if e["type"] == subcall_type]

    def to_scratchpad(self) -> list[dict[str, Any]]:
        """Return a JSON-serialisable snapshot for scratchpad persistence."""
        return [{k: v for k, v in e.items() if k != "timestamp"} for e in self._entries]

    def __len__(self) -> int:
        return len(self._entries)

    def __str__(self) -> str:
        if not self._entries:
            return "SubcallLog: 0 entries"
        type_counts: dict[str, int] = {}
        for e in self._entries:
            type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1
        summary = ", ".join(f"{t}: {c}" for t, c in sorted(type_counts.items()))
        return f"SubcallLog: {len(self._entries)} entries ({summary})"

    def __repr__(self) -> str:
        return str(self)
