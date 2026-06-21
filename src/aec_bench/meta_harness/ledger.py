# ABOUTME: Provides append-only JSONL ledger helpers for meta-harness process stages.
# ABOUTME: Records process evidence without owning execution or mutation decisions.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def append_ledger_entry(
    path: Path,
    *,
    process_id: str,
    stage: str,
    status: str,
    summary: dict[str, Any] | None = None,
    artifact_refs: list[str] | None = None,
) -> dict[str, Any]:
    entry = {
        "entry_id": f"{process_id}:{stage}:{_timestamp()}",
        "process_id": process_id,
        "stage": stage,
        "status": status,
        "summary": summary or {},
        "artifact_refs": artifact_refs or [],
        "created_at": _timestamp(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                entries.append(json.loads(line))
    return entries


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()
