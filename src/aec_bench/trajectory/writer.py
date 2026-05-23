# ABOUTME: stdlib-only TrajectoryWriter for recording structured agent execution traces as JSONL.
# ABOUTME: Designed to be COPY'd into Docker containers; no external dependencies required.

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime


def _now_utc_iso() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class TrajectoryWriter:
    """Writes agent execution traces incrementally to a JSONL file.

    Each write is flushed immediately so the file is readable even if the
    agent process is killed before close() is called.
    """

    def __init__(self, path: str = "/workspace/trajectory.jsonl") -> None:
        self._path = path
        self._step: int = 0
        self._call_type: str | None = None
        self._seen_system_hash: str | None = None
        self._file = open(path, "w", encoding="utf-8")  # noqa: SIM115
        self._write({"version": 1, "format": "aec-bench-trajectory"})

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def new_step(self, call_type: str | None = None) -> int:
        """Increment the step counter and return the new value (1, 2, 3…).

        If *call_type* is provided (e.g. ``"warmup"``, ``"main"``,
        ``"subagent"``), all entries written during this step will carry
        that tag.  Pass ``None`` (the default) for ordinary steps.
        """
        self._step += 1
        self._call_type: str | None = call_type
        return self._step

    # ------------------------------------------------------------------
    # Entry writers
    # ------------------------------------------------------------------

    def system(self, content: str) -> None:
        """Write a system-role entry at step 0, skipping if identical to the last."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        if content_hash == self._seen_system_hash:
            return
        self._seen_system_hash = content_hash
        self._write({"role": "system", "step": 0, "content": content})

    def user(self, content: str) -> None:
        """Write a user-role entry at step 0."""
        self._write({"role": "user", "step": 0, "content": content})

    def thinking(self, content: str) -> None:
        """Write an assistant (thinking) entry at the current step."""
        self._write({"role": "assistant", "step": self._step, "content": content})

    def tool_call(
        self,
        tool_name: str,
        command: str,
        arguments: dict | None = None,
    ) -> None:
        """Write a tool_call entry at the current step."""
        entry: dict = {
            "role": "tool_call",
            "step": self._step,
            "tool_name": tool_name,
            "command": command,
        }
        if arguments is not None:
            entry["arguments"] = arguments
        self._write(entry)

    _SUMMARY_LIMIT: int = 200

    def tool_result(
        self,
        tool_name: str,
        stdout: str,
        stderr: str = "",
        exit_code: int = 0,
        duration_ms: int | None = None,
        media: list[str] | None = None,
        metadata: dict | None = None,
        output_summary: str | None = None,
    ) -> None:
        """Write a tool_result entry at the current step."""
        entry: dict = {
            "role": "tool_result",
            "step": self._step,
            "tool_name": tool_name,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        }
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        if media is not None:
            entry["media"] = media
        if metadata is not None:
            entry["metadata"] = metadata
        # Auto-generate summary for long output; explicit value takes priority
        if output_summary is not None:
            entry["output_summary"] = output_summary
        elif stdout and len(stdout) > self._SUMMARY_LIMIT:
            entry["output_summary"] = stdout[: self._SUMMARY_LIMIT] + "\u2026"
        self._write(entry)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Flush and close the underlying file handle."""
        self._file.flush()
        self._file.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write(self, entry: dict) -> None:
        """Add a timestamp, serialise to JSON, write a line, and flush."""
        if self._call_type is not None and entry.get("step", 0) > 0:
            entry["call_type"] = self._call_type
        entry["timestamp"] = _now_utc_iso()
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()
