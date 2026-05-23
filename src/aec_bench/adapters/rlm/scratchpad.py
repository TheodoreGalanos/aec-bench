# ABOUTME: File-backed persistent key-value scratchpad for RLM working memory.
# ABOUTME: Provides NOTE/RECALL functions that survive context compaction via disk persistence.

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PREVIEW_LIMIT = 150


class Scratchpad:
    """Persistent key-value store backed by a JSON file.

    Designed for RLM agents — data written here survives context
    compaction because it lives on disk, not in conversation history.
    Injected into the REPL as ``NOTE`` and ``RECALL`` callables.
    """

    def __init__(self, path: str) -> None:
        self._path = Path(path)

    # ------------------------------------------------------------------
    # Public API (injected into REPL)
    # ------------------------------------------------------------------

    def note(self, key: str, value: Any) -> str:
        """Store *key*/*value* in the scratchpad and return a confirmation.

        Uses ``json.dump(default=str)`` so non-JSON-serialisable values
        are stored as their string representation.
        """
        data = self._read()
        data[key] = value
        self._write(data)
        return f"Noted: {key} ({type(value).__name__})"

    def recall(self, key: str | None = None) -> Any:
        """Retrieve a value by *key*, or list all keys with previews.

        * ``recall("x")`` → returns the stored value for *x*.
        * ``recall()`` (no args) → returns a formatted listing of all
          keys with truncated previews.
        * Missing key → returns an error message listing available keys.
        * Empty scratchpad → returns a helpful hint.
        """
        data = self._read()

        if key is None:
            return self._list_keys(data)

        if key in data:
            return data[key]

        available = ", ".join(sorted(data.keys())) if data else "none"
        return f"Key not found: '{key}'. Available keys: {available}"

    # ------------------------------------------------------------------
    # Metadata helpers (used by adapter for trajectory/compaction)
    # ------------------------------------------------------------------

    @property
    def keys(self) -> list[str]:
        """Sorted list of current scratchpad keys."""
        return sorted(self._read().keys())

    def snapshot(self) -> dict[str, Any]:
        """Full scratchpad contents for compaction input."""
        return self._read()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        """Read scratchpad from disk. Returns empty dict if file missing."""
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read scratchpad at %s, returning empty", self._path)
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        """Write scratchpad to disk with ``default=str`` for safety."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

    def _list_keys(self, data: dict[str, Any]) -> str:
        """Format all keys with truncated previews."""
        if not data:
            return "Scratchpad is empty. Use NOTE(key, value) to store data."

        lines: list[str] = [f"Scratchpad ({len(data)} keys):"]
        for key in sorted(data.keys()):
            preview = repr(data[key])
            if len(preview) > _PREVIEW_LIMIT:
                preview = preview[:_PREVIEW_LIMIT] + "..."
            lines.append(f"  {key}: {preview}")
        return "\n".join(lines)
