# ABOUTME: Evaluation artifact model and persistence for the _evaluations/ ledger directory.
# ABOUTME: Supports write, read, and list operations for persisted evaluation summaries.

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from aec_bench.contracts.validators import StrictModel


class EvaluationFilters(StrictModel):
    """Filters applied when producing the evaluation."""

    adapter: str | None = None
    model: str | None = None
    task_prefix: str | None = None


class EvaluationArtifact(StrictModel):
    """A persisted evaluation summary stored alongside trial records."""

    evaluation_id: str
    experiment_id: str
    timestamp: datetime
    filters: EvaluationFilters
    summary: dict[str, Any]
    behavioral: dict[str, Any] | None = None
    framework_version: str


def write_evaluation_artifact(ledger_root: Path, artifact: EvaluationArtifact) -> Path:
    """Write an evaluation artifact to _evaluations/ within the experiment directory."""
    eval_dir = ledger_root / artifact.experiment_id / "_evaluations"
    eval_dir.mkdir(parents=True, exist_ok=True)
    path = eval_dir / f"{artifact.evaluation_id}.json"
    path.write_text(artifact.model_dump_json(indent=2))
    return path


def read_evaluation_artifact(path: Path) -> EvaluationArtifact:
    """Read a single evaluation artifact from disk."""
    return EvaluationArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def list_evaluation_artifacts(ledger_root: Path, *, experiment_id: str) -> list[EvaluationArtifact]:
    """List all evaluation artifacts for an experiment, sorted by timestamp."""
    eval_dir = ledger_root / experiment_id / "_evaluations"
    if not eval_dir.exists():
        return []
    artifacts = [read_evaluation_artifact(p) for p in sorted(eval_dir.glob("*.json"))]
    return sorted(artifacts, key=lambda a: a.timestamp)
