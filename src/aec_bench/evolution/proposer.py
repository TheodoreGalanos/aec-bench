# ABOUTME: Composes AVO with the private checks used while revising one candidate.
# ABOUTME: Keeps provider wiring and revision identity setup outside the loop implementation.

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from aec_bench.contracts.evolution import WorkspaceSnapshot
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.advice import build_avo_advisor
from aec_bench.evolution.agent_loop import run_avo
from aec_bench.evolution.agent_protocol import PydanticAIAVORunner
from aec_bench.evolution.cancellation import AVOCancellationSignal
from aec_bench.evolution.checkpoint import AVOConfigurationIdentity
from aec_bench.evolution.core import AVOBudget, CandidateProposal, CandidateProposalRequest
from aec_bench.evolution.evaluation import CandidateChecks, CandidateEvaluationBatch
from aec_bench.evolution.resume import avo_checkpoint_path
from aec_bench.evolution.revision import RevisionEvaluation
from aec_bench.evolution.sanitiser import CompactionLLM
from aec_bench.evolution.workspace import Workspace
from aec_bench.trials import build_trial_id


def build_avo(
    *,
    model: Any,
    model_identity: str,
    revision_checks: CandidateChecks,
    batch_size: int,
    advisor_model: Any | None = None,
    advisor_model_identity: str | None = None,
    revision_experiment_prefix: str = "development",
    budget: AVOBudget | None = None,
    compaction_llm: CompactionLLM | None = None,
    checkpoint_root: Path | None = None,
    configuration_identity: AVOConfigurationIdentity | None = None,
    cancellation_signal: AVOCancellationSignal | None = None,
) -> Callable[[CandidateProposalRequest, Workspace, str], CandidateProposal]:
    """Build the AVO candidate proposer used by functional evolution.

    The returned callable creates one private revision boundary for each
    proposal. The boundary plans one fixed public batch and gives each exact
    scratch revision distinct trial IDs. Selection evidence is used only to
    reject identity collisions. Candidate selection remains in the application.
    """
    if not isinstance(revision_checks, CandidateChecks):
        raise TypeError("revision_checks must be CandidateChecks")
    if not isinstance(model_identity, str) or not model_identity.strip():
        raise ValueError("model_identity must not be blank")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int):
        raise TypeError("batch_size must be an integer")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if not isinstance(revision_experiment_prefix, str) or not revision_experiment_prefix.strip():
        raise ValueError("revision_experiment_prefix must not be blank")
    selected_budget = budget if budget is not None else AVOBudget(max_supervisor_interventions=1)
    if not isinstance(selected_budget, AVOBudget):
        raise TypeError("budget must be an AVOBudget")
    selected_advisor_model = model if advisor_model is None else advisor_model
    selected_advisor_identity = model_identity if advisor_model_identity is None else advisor_model_identity
    if not isinstance(selected_advisor_identity, str) or not selected_advisor_identity.strip():
        raise ValueError("advisor_model_identity must not be blank")
    if checkpoint_root is not None and not isinstance(checkpoint_root, Path):
        raise TypeError("checkpoint_root must be a Path")
    if checkpoint_root is not None and configuration_identity is None:
        raise ValueError("configuration_identity is required when checkpointing is enabled")
    if configuration_identity is not None and model_identity.strip() != configuration_identity.model_identity:
        raise ValueError("model_identity must match configuration_identity.model_identity")
    if (
        configuration_identity is not None
        and selected_advisor_identity.strip() != configuration_identity.supervisor_model_identity
    ):
        raise ValueError("advisor_model_identity must match configuration_identity.supervisor_model_identity")
    runner = PydanticAIAVORunner(model)
    advisor_runner = build_avo_advisor(
        selected_advisor_model,
        model_identity=selected_advisor_identity,
    ).runner

    def vary(request: CandidateProposalRequest, source: Workspace, child_candidate_id: str) -> CandidateProposal:
        if not isinstance(request, CandidateProposalRequest):
            raise TypeError("request must be a CandidateProposalRequest")
        if request.cycle < 1:
            raise ValueError("proposal request cycle must be 1-based")
        revision_cycle_index = request.cycle - 1
        selection_experiment_id, selection_trial_ids = _selection_evidence_identity(request)
        run_digest = hashlib.sha256(request.run_id.encode("utf-8")).hexdigest()[:16]
        development_experiment_id = (
            f"{revision_experiment_prefix}-cycle-{request.cycle}-run-{run_digest}-child-{child_candidate_id}"
        )
        if development_experiment_id == selection_experiment_id:
            development_experiment_id = f"{development_experiment_id}-development"
        planned_batch: CandidateEvaluationBatch | None = None

        def plan(_batch_size: int, _cycle_index: int) -> CandidateEvaluationBatch:
            nonlocal planned_batch
            if planned_batch is None:
                source_batch = revision_checks.plan_batch(batch_size, revision_cycle_index)
                if not isinstance(source_batch, CandidateEvaluationBatch):
                    raise TypeError("revision checks must plan a CandidateEvaluationBatch")
                planned_batch = _bind_revision_batch(source_batch, development_experiment_id)
            return planned_batch

        def evaluate(snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch) -> tuple[TrialRecord, ...]:
            attempt_batch = _bind_revision_batch(batch, batch.trials[0].experiment_id, snapshot.candidate_id)
            return revision_checks.run(snapshot, attempt_batch)

        boundary = RevisionEvaluation(
            planner=plan,
            evaluator=evaluate,
            batch_size=batch_size,
            cycle=revision_cycle_index,
            experiment_id=development_experiment_id,
            selection_experiment_id=selection_experiment_id,
            selection_trial_ids=selection_trial_ids,
        )
        variation_id = f"{request.run_id}:variation-{request.cycle}:child-{child_candidate_id}"
        selected_checkpoint_path = (
            None
            if checkpoint_root is None
            else avo_checkpoint_path(checkpoint_root, run_id=request.run_id, variation_id=variation_id)
        )
        return run_avo(
            request,
            source,
            child_candidate_id,
            revision_evaluation=boundary,
            agent_runner=runner,
            advisor_runner=advisor_runner,
            budget=selected_budget,
            knowledge_source=lambda: _workspace_program(source),
            compaction_llm=compaction_llm,
            variation_id=variation_id,
            avo_checkpoint_path=selected_checkpoint_path,
            configuration_identity=configuration_identity,
            cancellation_signal=cancellation_signal,
        )

    return vary


def _selection_evidence_identity(request: CandidateProposalRequest) -> tuple[str, tuple[str, ...]]:
    """Return the one selection experiment and its exact parent trial IDs."""
    experiment_ids = tuple(observation.trial.experiment_id for observation in request.parent.observations)
    if not experiment_ids or len(set(experiment_ids)) != 1:
        raise ValueError("proposal parent evidence must use one selection experiment identity")
    trial_ids = tuple(observation.trial.trial_id for observation in request.parent.observations)
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("proposal parent evidence must use unique selection trial identities")
    return experiment_ids[0], trial_ids


def _bind_revision_batch(
    batch: CandidateEvaluationBatch,
    experiment_id: str,
    candidate_id: str | None = None,
) -> CandidateEvaluationBatch:
    """Bind a planned batch to one private revision identity and optional candidate."""
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


__all__ = ("build_avo",)
