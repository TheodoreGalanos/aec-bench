# ABOUTME: Pydantic contracts for versioned training datasets built from agent traces.
# ABOUTME: Owns the canonical full trace and variant registration for SFT/RL compressed forms.

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from aec_bench.contracts.validators import StrictModel


class DatasetVariant(str, Enum):
    """Supported trace dataset variant types."""

    FULL = "full"
    SFT_MEMENTO = "sft_memento"
    RL_MEMENTO = "rl_memento"


class TraceDatasetVariant(StrictModel, frozen=True):
    """One view of a trace — full, compressed, or otherwise transformed."""

    name: str
    path: Path
    transform: str | None = None
    compression_ratio: float | None = None
    metadata: dict[str, Any] = {}


class TraceDatasetEntry(StrictModel, frozen=True):
    """A single trace with all its variants."""

    task_id: str
    model: str
    source_trace: Path
    variants: list[TraceDatasetVariant]


class TraceDatasetManifest(StrictModel, frozen=True):
    """A collection of traces packaged for training."""

    name: str
    version: str
    entries: list[TraceDatasetEntry]
    created_at: datetime
    content_hash: str


def compute_manifest_hash(entries: list[TraceDatasetEntry]) -> str:
    """Compute a deterministic SHA-256 hash over the entry content."""
    content = json.dumps(
        [e.model_dump(mode="json") for e in entries],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(content.encode()).hexdigest()
