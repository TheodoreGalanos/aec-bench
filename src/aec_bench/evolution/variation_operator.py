# ABOUTME: Composes the bounded agentic variation loop with development evaluation.
# ABOUTME: Keeps provider wiring and development identity setup outside the loop implementation.

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from aec_bench.contracts.evolution import WorkspaceSnapshot
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.agent_loop import run_agentic_variation
from aec_bench.evolution.agent_protocol import PydanticAIStructuredRunner
from aec_bench.evolution.cancellation import AVOCancellationSignal
from aec_bench.evolution.checkpoint import AVOConfigurationIdentity
from aec_bench.evolution.core import AVOBudget, VariationRequest, VariationResult
from aec_bench.evolution.development import (
    DevelopmentBatchPlanner,
    DevelopmentEvaluationBoundary,
    DevelopmentEvaluator,
)
from aec_bench.evolution.evaluation import CandidateEvaluationBatch
from aec_bench.evolution.resume import checkpoint_path
from aec_bench.evolution.sanitiser import CompactionLLM
from aec_bench.evolution.workspace import Workspace
from aec_bench.trials import build_trial_id


def build_agentic_variation_operator(
    *,
    agent_model: Any,
    development_batch_planner: DevelopmentBatchPlanner,
    development_evaluator: DevelopmentEvaluator,
    development_batch_size: int,
    development_experiment_prefix: str = "development",
    budget: AVOBudget | None = None,
    compaction_llm: CompactionLLM | None = None,
    checkpoint_root: Path | None = None,
    configuration_identity: AVOConfigurationIdentity | None = None,
    cancellation_signal: AVOCancellationSignal | None = None,
) -> Callable[[VariationRequest, Workspace, str], VariationResult]:
    """Build the production variation operator used by functional evolution.

    The returned callable creates one development boundary for each variation
    call. The boundary plans one fixed public batch, while the evaluator gets
    distinct trial IDs for each exact scratch revision. Host evidence is used
    only to reject identity collisions; host selection and acceptance remain in
    the application layer.
    """
    if not callable(development_batch_planner):
        raise TypeError("development_batch_planner must be callable")
    if not callable(development_evaluator):
        raise TypeError("development_evaluator must be callable")
    if isinstance(development_batch_size, bool) or not isinstance(development_batch_size, int):
        raise TypeError("development_batch_size must be an integer")
    if development_batch_size < 1:
        raise ValueError("development_batch_size must be positive")
    if not isinstance(development_experiment_prefix, str) or not development_experiment_prefix.strip():
        raise ValueError("development_experiment_prefix must not be blank")
    selected_budget = budget if budget is not None else AVOBudget()
    if not isinstance(selected_budget, AVOBudget):
        raise TypeError("budget must be an AVOBudget")
    if checkpoint_root is not None and not isinstance(checkpoint_root, Path):
        raise TypeError("checkpoint_root must be a Path")
    if checkpoint_root is not None and configuration_identity is None:
        raise ValueError("configuration_identity is required when checkpointing is enabled")
    runner = PydanticAIStructuredRunner(agent_model)

    def vary(request: VariationRequest, source: Workspace, child_candidate_id: str) -> VariationResult:
        if not isinstance(request, VariationRequest):
            raise TypeError("request must be a VariationRequest")
        if request.cycle < 1:
            raise ValueError("variation request cycle must be 1-based")
        development_cycle_index = request.cycle - 1
        host_experiment_id, host_trial_ids = _host_evidence_identity(request)
        run_digest = hashlib.sha256(request.run_id.encode("utf-8")).hexdigest()[:16]
        development_experiment_id = (
            f"{development_experiment_prefix}-cycle-{request.cycle}-run-{run_digest}-child-{child_candidate_id}"
        )
        if development_experiment_id == host_experiment_id:
            development_experiment_id = f"{development_experiment_id}-development"
        planned_batch: CandidateEvaluationBatch | None = None

        def plan(_batch_size: int, _cycle_index: int) -> CandidateEvaluationBatch:
            nonlocal planned_batch
            if planned_batch is None:
                source_batch = development_batch_planner(development_batch_size, development_cycle_index)
                if not isinstance(source_batch, CandidateEvaluationBatch):
                    raise TypeError("development planner must return a CandidateEvaluationBatch")
                planned_batch = _rebind_development_batch(source_batch, development_experiment_id)
            return planned_batch

        def evaluate(snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch) -> tuple[TrialRecord, ...]:
            attempt_batch = _rebind_development_batch(batch, batch.trials[0].experiment_id, snapshot.candidate_id)
            return development_evaluator(snapshot, attempt_batch)

        boundary = DevelopmentEvaluationBoundary(
            planner=plan,
            evaluator=evaluate,
            batch_size=development_batch_size,
            cycle=development_cycle_index,
            experiment_id=development_experiment_id,
            host_experiment_id=host_experiment_id,
            host_trial_ids=host_trial_ids,
        )
        variation_id = f"{request.run_id}:variation-{request.cycle}:child-{child_candidate_id}"
        selected_checkpoint_path = (
            None
            if checkpoint_root is None
            else checkpoint_path(checkpoint_root, run_id=request.run_id, variation_id=variation_id)
        )
        return run_agentic_variation(
            request,
            source,
            child_candidate_id,
            development_boundary=boundary,
            agent_runner=runner,
            budget=selected_budget,
            knowledge_source=lambda: _workspace_program(source),
            compaction_llm=compaction_llm,
            variation_id=variation_id,
            checkpoint_path=selected_checkpoint_path,
            configuration_identity=configuration_identity,
            cancellation_signal=cancellation_signal,
        )

    return vary


def _host_evidence_identity(request: VariationRequest) -> tuple[str, tuple[str, ...]]:
    """Return the one host experiment and its exact parent trial IDs."""
    experiment_ids = tuple(observation.trial.experiment_id for observation in request.parent.observations)
    if not experiment_ids or len(set(experiment_ids)) != 1:
        raise ValueError("variation parent evidence must use one host experiment identity")
    trial_ids = tuple(observation.trial.trial_id for observation in request.parent.observations)
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("variation parent evidence must use unique host trial identities")
    return experiment_ids[0], trial_ids


def _rebind_development_batch(
    batch: CandidateEvaluationBatch,
    experiment_id: str,
    candidate_id: str | None = None,
) -> CandidateEvaluationBatch:
    """Rebind a planned batch to one development identity and optional revision."""
    namespace = experiment_id if candidate_id is None else f"{experiment_id}--candidate-{candidate_id}"
    trials = tuple(
        replace(
            trial,
            experiment_id=experiment_id,
            trial_id=build_trial_id(
                experiment_id=namespace,
                task_id=trial.task_id,
                agent_name=trial.agent.name,
                repetition=trial.repetition,
            ),
        )
        for trial in batch.trials
    )
    return CandidateEvaluationBatch(
        tasks=batch.tasks,
        trials=trials,
        evaluation_case_ids=batch.evaluation_case_ids,
        cycle=batch.cycle,
    )


def _workspace_program(source: Workspace) -> str:
    """Return only the approved workspace ``program.md`` knowledge."""
    path = source.root / "program.md"
    if not path.is_file():
        return "No approved workspace program.md knowledge is available."
    return path.read_text(encoding="utf-8")


__all__ = ("build_agentic_variation_operator",)
