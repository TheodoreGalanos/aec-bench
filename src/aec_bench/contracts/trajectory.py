# ABOUTME: Pydantic contract for structured agent trajectory entries.
# ABOUTME: Validates JSONL entries produced by the container-side TrajectoryWriter.

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import NonNegativeInt

from aec_bench.contracts.validators import StrictModel

logger = logging.getLogger(__name__)

TRAJECTORY_FORMAT = "aec-bench-trajectory"
TRAJECTORY_VERSION = 1


class TrajectoryEntry(StrictModel):
    """A single structured entry from an agent trajectory JSONL file."""

    step: NonNegativeInt
    role: str
    content: str | None = None
    tool_name: str | None = None
    command: str | None = None
    arguments: dict[str, Any] | None = None
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    media: list[str] | None = None
    metadata: dict[str, Any] | None = None  # RLM step metadata (structured)
    call_type: str | None = None  # warmup, main, or subagent
    output_summary: str | None = None  # truncated preview of stdout
    timestamp: str | None = None


def read_trajectory(path: Path) -> list[TrajectoryEntry]:
    """Read a trajectory JSONL file and return validated TrajectoryEntry objects.

    Skips the version header line. Returns an empty list if the file does not exist.
    Logs a warning if the version number in the header does not match TRAJECTORY_VERSION.
    """
    if not path.exists():
        return []

    entries: list[TrajectoryEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        if "version" in data and "format" in data:
            if data["version"] != TRAJECTORY_VERSION:
                logger.warning(
                    "Trajectory file %s has unknown version %s (expected %s)",
                    path,
                    data["version"],
                    TRAJECTORY_VERSION,
                )
            continue
        entries.append(TrajectoryEntry.model_validate(data))

    return entries
