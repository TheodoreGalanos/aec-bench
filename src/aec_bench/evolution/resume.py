# ABOUTME: Validates AVO checkpoint compatibility and restores explicit variation results.
# ABOUTME: Keeps resume decisions independent from the model loop and diagnostic event logs.

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from aec_bench.contracts.evolution import WorkspaceSnapshot
from aec_bench.evolution.checkpoint import (
    AVOBudgetSnapshot,
    AVOCheckpoint,
    AVOCheckpointTerminalResult,
    AVOConfigurationIdentity,
    AVOIncompleteExternalEffectError,
    read_checkpoint,
)
from aec_bench.evolution.core import (
    AVOBudget,
    SelectionPlan,
    VariationRequest,
    VariationResult,
    VariationStatus,
)
from aec_bench.evolution.evaluation import CandidateEvaluationBatch
from aec_bench.trials import planned_trial_to_data


class AVOResumeMismatchError(ValueError):
    """Raised when a checkpoint cannot resume the requested variation call."""


def checkpoint_path(root: Path, *, run_id: str, variation_id: str) -> Path:
    """Return a deterministic checkpoint path without using IDs as path segments."""

    _require_text(run_id, "run_id")
    _require_text(variation_id, "variation_id")
    run_digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    variation_digest = hashlib.sha256(variation_id.encode("utf-8")).hexdigest()
    return Path(root) / "_avo_checkpoints" / run_digest / f"{variation_digest}.json"


def request_configuration_identity(
    base: AVOConfigurationIdentity,
    request: VariationRequest,
    *,
    development_evaluation_cost_usd: float | None = None,
    development_batch_identity: str | None = None,
) -> AVOConfigurationIdentity:
    """Add a stable digest of model-visible request context to composition identity."""

    context = {
        "run_id": request.run_id,
        "parent": _jsonable(request.parent),
        "selection": _jsonable(request.selection),
        "inspirations": _jsonable(request.inspirations),
        "analysis": _jsonable(request.analysis),
        "scope": request.scope.value,
        "history": _jsonable(request.history),
        "graveyard": _jsonable(request.graveyard),
        "memory": _jsonable(request.memory),
        "cycle": request.cycle,
        "development_evaluation_cost_usd": development_evaluation_cost_usd,
        "development_batch_identity": development_batch_identity,
    }
    context_bytes = json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    context_digest = hashlib.sha256(context_bytes).hexdigest()
    return base.model_copy(update={"configuration_identity": f"{base.configuration_identity}:request-{context_digest}"})


def evaluation_batch_identity(batch: CandidateEvaluationBatch) -> str:
    """Return a deterministic identity for the complete development batch."""

    if not isinstance(batch, CandidateEvaluationBatch):
        raise TypeError("batch must be a CandidateEvaluationBatch")
    payload = {
        "cycle": batch.cycle,
        "evaluation_case_ids": list(batch.evaluation_case_ids),
        "tasks": [
            {
                "task": task.task.model_dump(mode="json", round_trip=True),
                "instance_dir": str(task.instance_dir),
                "environment_dockerfile": str(task.environment_dockerfile),
                "environment_compose_file": (
                    str(task.environment_compose_file) if task.environment_compose_file is not None else None
                ),
                "environment_manifest": (
                    str(task.environment_manifest) if task.environment_manifest is not None else None
                ),
                "verifier_script": str(task.verifier_script),
            }
            for task in batch.tasks
        ],
        "trials": [planned_trial_to_data(trial) for trial in batch.trials],
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_checkpoint_for_resume(
    checkpoint: AVOCheckpoint,
    *,
    run_id: str,
    variation_id: str,
    parent_snapshot: WorkspaceSnapshot,
    final_child_candidate_id: str,
    selection: SelectionPlan,
    development_case_ids: tuple[str, ...] | None,
    budget: AVOBudget,
    configuration_identity: AVOConfigurationIdentity,
    current_snapshot: WorkspaceSnapshot | None = None,
) -> None:
    """Reject every behavior-changing mismatch before any resumed effect."""

    if not isinstance(checkpoint, AVOCheckpoint):
        raise TypeError("checkpoint must be an AVOCheckpoint")
    checkpoint = AVOCheckpoint.model_validate(checkpoint.model_dump(mode="json"))
    if checkpoint.run_id != run_id:
        raise AVOResumeMismatchError("checkpoint run_id does not match the requested run_id")
    if checkpoint.variation_id != variation_id:
        raise AVOResumeMismatchError("checkpoint variation_id does not match the requested variation_id")
    if checkpoint.parent_candidate_id != parent_snapshot.candidate_id:
        raise AVOResumeMismatchError("checkpoint parent candidate ID does not match the requested parent")
    if not _same_material(checkpoint.parent_snapshot, parent_snapshot):
        raise AVOResumeMismatchError("checkpoint parent material does not match the requested parent")
    if checkpoint.final_child_candidate_id != final_child_candidate_id:
        raise AVOResumeMismatchError("checkpoint final child candidate ID does not match the request")
    if checkpoint.selection.model_dump(mode="json") != selection.to_record().model_dump(mode="json"):
        raise AVOResumeMismatchError("checkpoint selection does not match the requested selection")
    if development_case_ids is not None and checkpoint.development_case_ids != development_case_ids:
        raise AVOResumeMismatchError("checkpoint development case IDs or order do not match the request")
    if checkpoint.budget.model_dump(mode="json") != AVOBudgetSnapshot.from_budget(budget).model_dump(mode="json"):
        raise AVOResumeMismatchError("checkpoint budget does not match the requested budget")
    if checkpoint.configuration_identity.model_dump(mode="json") != configuration_identity.model_dump(mode="json"):
        raise AVOResumeMismatchError("checkpoint configuration identity does not match the request")
    if current_snapshot is not None and not _same_material(checkpoint.current_snapshot, current_snapshot):
        raise AVOResumeMismatchError("checkpoint current revision material does not match the request")


def load_checkpoint_for_resume(
    path: Path,
    **compatibility: Any,
) -> AVOCheckpoint:
    """Read one validated checkpoint, then apply explicit resume compatibility checks."""

    checkpoint = read_checkpoint(path)
    validate_checkpoint_for_resume(checkpoint, **compatibility)
    if checkpoint.incomplete_external_effects:
        # An event log cannot prove whether the provider or evaluator completed.
        # Never retry an effect until its owner reconciles this marker.
        raise AVOIncompleteExternalEffectError(checkpoint.incomplete_external_effects[0])
    return checkpoint


def terminal_result_from_checkpoint(checkpoint: AVOCheckpoint) -> VariationResult:
    """Restore a recorded terminal result without model or evaluator calls."""

    terminal = checkpoint.terminal_result
    if not isinstance(terminal, AVOCheckpointTerminalResult):
        raise ValueError("checkpoint has no terminal result")
    attempt = None
    if terminal.status is VariationStatus.SUBMITTED:
        assert terminal.attempt_id is not None
        selected = next(
            (item for item in checkpoint.evaluated_attempts if item.attempt_id == terminal.attempt_id),
            None,
        )
        if selected is None:
            raise AVOResumeMismatchError("checkpoint terminal attempt is missing")
        attempt = selected.to_attempt()
    return VariationResult(
        status=terminal.status,
        child=terminal.child,
        mutation=terminal.mutation,
        reasoning=terminal.reasoning,
        usage=terminal.usage.to_usage(),
        attempt=attempt,
        memory=checkpoint.structured_memory,
    )


def _same_material(left: WorkspaceSnapshot, right: WorkspaceSnapshot) -> bool:
    return left.system_prompt == right.system_prompt and left.skills == right.skills


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "snapshot") and hasattr(value, "observations") and hasattr(value, "assessment"):
        return {
            "snapshot": _jsonable(value.snapshot),
            "observations": [_jsonable(item) for item in value.observations],
            "assessment": _jsonable(value.assessment),
        }
    if hasattr(value, "trial") and hasattr(value, "enrichment") and hasattr(value, "candidate_id"):
        trial = _jsonable(value.trial)
        try:
            trial["run_manifest"] = _jsonable(value.trial.run_manifest)
        except RuntimeError:
            # Unbound trial records cannot be used as authoritative host
            # evidence. The checkpoint layer rejects them before persistence.
            pass
        if value.trial.output is not None:
            trial["raw_output_path"] = value.trial.output.raw_output_path
            trial["conversation_path"] = value.trial.output.conversation_path
            trial["trajectory_path"] = value.trial.output.trajectory_path
        return {
            "trial": trial,
            "pending_extensions": {key: _jsonable(item) for key, item in value.trial.pending_extensions.items()},
            "enrichment": _jsonable(value.enrichment),
            "candidate_id": value.candidate_id,
            "discipline": value.discipline,
        }
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


__all__ = (
    "AVOResumeMismatchError",
    "checkpoint_path",
    "evaluation_batch_identity",
    "load_checkpoint_for_resume",
    "request_configuration_identity",
    "terminal_result_from_checkpoint",
    "validate_checkpoint_for_resume",
)
