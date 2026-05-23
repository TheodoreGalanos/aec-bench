# ABOUTME: Triage annotation persistence for the append-only ledger.
# ABOUTME: Stores lightweight pass/fail/defer/note verdicts alongside trial records.

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class TriageAnnotation:
    """Lightweight triage verdict for a single trial."""

    verdict: Literal["pass", "fail", "defer", "note"]
    notes: str = ""
    timestamp: str = ""

    @staticmethod
    def create(verdict: Literal["pass", "fail", "defer", "note"], notes: str = "") -> TriageAnnotation:
        """Build a new annotation with the current UTC timestamp."""
        return TriageAnnotation(
            verdict=verdict,
            notes=notes,
            timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


def save_annotation(experiment_dir: Path, trial_id: str, annotation: TriageAnnotation) -> None:
    """Write a triage annotation to the _annotations/ subdirectory."""
    ann_dir = experiment_dir / "_annotations"
    ann_dir.mkdir(exist_ok=True)
    payload = {
        "verdict": annotation.verdict,
        "notes": annotation.notes,
        "timestamp": annotation.timestamp,
    }
    (ann_dir / f"{trial_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_annotations(experiment_dir: Path) -> dict[str, TriageAnnotation]:
    """Load all triage annotations from the _annotations/ subdirectory."""
    ann_dir = experiment_dir / "_annotations"
    if not ann_dir.is_dir():
        return {}
    result: dict[str, TriageAnnotation] = {}
    for path in sorted(ann_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result[path.stem] = TriageAnnotation(
            verdict=data["verdict"],
            notes=data.get("notes", ""),
            timestamp=data.get("timestamp", ""),
        )
    return result


def delete_annotation(experiment_dir: Path, trial_id: str) -> None:
    """Delete a triage annotation file if it exists."""
    path = experiment_dir / "_annotations" / f"{trial_id}.json"
    if path.exists():
        path.unlink()
