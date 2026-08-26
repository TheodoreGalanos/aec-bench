# ABOUTME: Functional application entry points for evolution execution.
# ABOUTME: Coordinates exact candidate evaluation, scratch variation, decisions, and effects.

from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolutionCycleRecord,
    EvolutionObservation,
    EvolutionResult,
    GateDecision,
    MutationStrategy,
    WorkspaceSnapshot,
)
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.analysis import (
    EvolutionAnalysis,
    compute_discipline_scores,
    compute_graduated_scope,
    detect_behavioral_patterns,
)
from aec_bench.evolution.core import (
    CycleOutcome,
    EvaluatedCandidate,
    EvolutionState,
    SelectionPlan,
    VariationRequest,
    VariationResult,
    VariationStatus,
    assessment_score,
    decide_candidate,
    rebase_evolution_state_for_parent,
    reduce_evolution_state,
)
from aec_bench.evolution.enrichment import enrich_observations
from aec_bench.evolution.evaluation import (
    CandidateBatchPlanner,
    CandidateEvaluationBatch,
    CandidateEvaluator,
    bind_candidate_evaluation,
    bind_evaluated_candidate,
    build_candidate_assessment,
)
from aec_bench.evolution.graveyard import GraveyardEntry, MutationGraveyard
from aec_bench.evolution.strategy import HillClimbStrategy, SelectionStrategy
from aec_bench.evolution.variation import run_structured_variation
from aec_bench.evolution.workspace import Workspace
from aec_bench.generation.application import generate_template_instances, resolve_template

logger = logging.getLogger(__name__)

ReportWriter = Callable[[Path], Path]
CandidateIdFactory = Callable[[str, int], str]
VariationOperator = Callable[[VariationRequest, Workspace, str], VariationResult]
ObservationEnricher = Callable[[Sequence[EvolutionObservation]], Sequence[EvolutionObservation]]


@dataclass(frozen=True)
class EvolutionCycleExecution:
    """Result of one functional evolution cycle, including its next state."""

    outcome: CycleOutcome
    record: EvolutionCycleRecord
    state: EvolutionState
    score: float


def _execute_evolution_cycle(
    *,
    workspace: Workspace,
    config: EvolutionConfig,
    evaluate: CandidateEvaluator,
    strategy: SelectionStrategy,
    batch_planner: CandidateBatchPlanner,
    variation: VariationOperator,
    enrich: ObservationEnricher,
    graveyard: MutationGraveyard,
    history: list[EvolutionCycleRecord],
    snapshots: dict[str, WorkspaceSnapshot],
    cycle: int,
    state: EvolutionState | None,
    selection: SelectionPlan,
    run_id: str,
    now: Callable[[], datetime],
    candidate_id_factory: CandidateIdFactory,
) -> EvolutionCycleExecution:
    """Execute one cycle through the same functional path as ``run_evolution``.

    This narrow boundary lets provider-free swarm callers share the canonical
    candidate/evidence lifecycle without reviving a stateful engine.
    """
    parent_snapshot = _resolve_snapshot(selection.parent_candidate_id, snapshots, strategy)
    batch = batch_planner(config.batch_size, cycle - 1)
    parent = bind_candidate_evaluation(parent_snapshot, batch, evaluate(parent_snapshot, batch))
    parent = _enrich_candidate(parent, batch, enrich)
    if state is None:
        state = EvolutionState.from_baseline(parent, structural_weight=config.structural_weight)
    state = rebase_evolution_state_for_parent(state, parent, structural_weight=config.structural_weight)

    analysis = _build_analysis(parent, state)
    inspirations = tuple(
        _resolve_snapshot(candidate_id, snapshots, strategy) for candidate_id in selection.inspiration_candidate_ids
    )
    request = VariationRequest(
        selection=selection,
        parent=parent,
        inspirations=inspirations,
        analysis=analysis,
        scope=analysis.scope,
        history=tuple(history),
        graveyard=tuple(graveyard.browse(limit=graveyard.size)),
    )
    child_candidate_id = candidate_id_factory(run_id, cycle)
    variation_result = variation(request, workspace, child_candidate_id)
    child: EvaluatedCandidate | None = None
    if variation_result.status is VariationStatus.SUBMITTED:
        if variation_result.child is None:
            raise ValueError("submitted variation did not provide a child snapshot")
        child = bind_candidate_evaluation(
            variation_result.child,
            batch,
            evaluate(variation_result.child, batch),
        )
        child = _enrich_candidate(child, batch, enrich)

    decision = decide_candidate(
        parent=parent,
        child=child,
        variation=variation_result,
        state=state,
        config=config,
    )
    next_state = reduce_evolution_state(state=state, parent=parent, child=child, decision=decision)
    outcome = CycleOutcome(
        cycle=cycle,
        selection=selection,
        parent=parent,
        variation=variation_result,
        child=child,
        decision=decision,
        active_candidate_id_after=next_state.active_candidate_id,
        best_candidate_id_after=next_state.best_candidate_id,
    )

    if decision.decision is GateDecision.ACCEPTED:
        assert child is not None
        workspace.apply_snapshot(child.snapshot)
        workspace.commit_candidate(
            candidate_id=child.snapshot.candidate_id,
            summary=_candidate_summary(cycle, child, selection),
            score=assessment_score(child.assessment, structural_weight=config.structural_weight),
            parent_candidate_id=parent.snapshot.candidate_id,
            label=f"evo-{run_id}-{cycle}",
        )
        snapshots[child.snapshot.candidate_id] = child.snapshot
    elif decision.decision is GateDecision.REJECTED and child is not None:
        graveyard.insert(_graveyard_entry(outcome, run_id, now()))

    from aec_bench.evolution.trial_persistence import persist_cycle_trials

    persisted_observations = list(parent.observations)
    if child is not None:
        persisted_observations.extend(child.observations)
    persist_cycle_trials(
        workspace_root=workspace.root,
        cycle=cycle,
        run_id=run_id,
        observations=persisted_observations,
    )
    record = outcome.to_record(now())
    score = assessment_score(
        (child if decision.decision is GateDecision.ACCEPTED and child is not None else parent).assessment,
        structural_weight=config.structural_weight,
    )
    _notify_strategy(
        strategy,
        outcome=outcome,
        cycle_record=record,
        snapshot=child.snapshot if decision.decision is GateDecision.ACCEPTED and child else parent.snapshot,
        score_history=_project_score_history((*history, record), config),
        graveyard=graveyard,
        run_id=run_id,
    )
    return EvolutionCycleExecution(outcome=outcome, record=record, state=next_state, score=score)


def run_evolution(
    *,
    workspace: Workspace,
    config: EvolutionConfig,
    evaluate: CandidateEvaluator,
    strategy: SelectionStrategy,
    batch_planner: CandidateBatchPlanner,
    variation: VariationOperator,
    enrich: ObservationEnricher,
    report_writer: ReportWriter | None = None,
    clock: Callable[[], datetime] | None = None,
    run_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
) -> EvolutionResult:
    """Run one functional evolution loop.

    Evaluation is planned once per cycle and both candidates use that exact
    plan. The canonical workspace is changed only after an accepted child.
    Observation enrichment and variation are explicit application dependencies.
    """
    workspace.init_versioning()
    now = clock or (lambda: datetime.now(tz=UTC))
    resolved_run_id = run_id or _timestamp_slug()
    make_candidate_id = candidate_id_factory or (lambda current_run, cycle: f"{current_run}:{cycle}")
    graveyard = MutationGraveyard.load(workspace.root / "graveyard.json")
    history: list[EvolutionCycleRecord] = []
    snapshots: dict[str, WorkspaceSnapshot] = {"baseline": workspace.export_snapshot("baseline")}
    state: EvolutionState | None = None
    pending_selection: SelectionPlan | None = None

    for cycle_index in range(config.max_cycles):
        cycle = cycle_index + 1
        selection = pending_selection or SelectionPlan(
            parent_candidate_id="baseline",
            inspiration_candidate_ids=(),
            strategy=MutationStrategy.CONSERVATIVE,
            goal="Improve the selected agent workspace against the configured evaluation batch.",
            reasoning="Start from the baseline candidate.",
        )
        execution = _execute_evolution_cycle(
            workspace=workspace,
            config=config,
            evaluate=evaluate,
            strategy=strategy,
            batch_planner=batch_planner,
            variation=variation,
            enrich=enrich,
            graveyard=graveyard,
            history=history,
            snapshots=snapshots,
            cycle=cycle,
            state=state,
            selection=selection,
            run_id=resolved_run_id,
            now=now,
            candidate_id_factory=make_candidate_id,
        )
        record = execution.record
        history.append(record)
        state = execution.state
        pending_selection = _next_selection(strategy, state, execution.score)
        logger.info(
            "Cycle %d/%d — score=%.3f, gate=%s, parent=%s, child=%s",
            cycle,
            config.max_cycles,
            execution.score,
            execution.outcome.decision.decision.value,
            execution.outcome.parent.snapshot.candidate_id,
            execution.outcome.child.snapshot.candidate_id if execution.outcome.child else "none",
        )
        if _is_converged(state, config):
            break

    assert state is not None
    _write_report(workspace, report_writer)
    strategy.save(workspace.root)
    graveyard.save(workspace.root / "graveyard.json")
    return EvolutionResult(
        run_id=resolved_run_id,
        workspace_name=workspace.manifest.name,
        cycles_completed=len(history),
        final_score=_project_score_history(history, config)[-1] if history else state.best_score,
        best_score=state.best_score,
        best_candidate_id=state.best_candidate_id,
        score_history=_project_score_history(history, config),
        converged=_is_converged(state, config),
        total_trials=sum(len(record.parent_assessment.trial_ids) for record in history)
        + sum(len(record.child_assessment.trial_ids) for record in history if record.child_assessment is not None),
        cycle_records=history,
        archive_summary=strategy.summary(),
    )


def run_evolution_from_config(
    *,
    config: EvolutionConfig,
    tasks_root: Path | None = None,
    report_writer: ReportWriter | None = None,
    clock: Callable[[], datetime] | None = None,
    run_id: str | None = None,
) -> EvolutionResult:
    """Assemble and run evolution from repository configuration."""
    from aec_bench.evolution.backends.local import (
        make_local_candidate_batch_planner,
        make_local_candidate_evaluator,
        make_stub_candidate_evaluator,
    )
    from aec_bench.evolution.config_loader import resolve_task_dirs
    from aec_bench.evolution.llm import build_evolution_llm_clients
    from aec_bench.evolution.strategy import QDStrategy

    workspace = Workspace(Path(config.workspace_path))
    classifier_llm, evolver_llm = build_evolution_llm_clients(config.models)
    task_dirs: list[Path] = []
    if config.generate is not None:
        generation = config.generate
        generated = generate_template_instances(
            template=resolve_template(generation.template),
            output_root=Path(tempfile.mkdtemp(prefix="aec-bench-evo-tasks-")),
            count=generation.count,
            difficulties=tuple(generation.difficulties),
            seed=generation.seed,
            suite_id="evolution-generated-tasks",
        )
        task_dirs.extend(generated.task_paths)
    if tasks_root is not None:
        task_dirs.extend(resolve_task_dirs(config.task_selector, tasks_root))

    model = config.solver.model if config.solver is not None else config.models.evolver
    adapter = config.solver.adapter if config.solver is not None else "rlm"
    experiment_id = f"evo-{workspace.manifest.name}"
    if config.backend == "local" and task_dirs:
        batch_planner = make_local_candidate_batch_planner(
            task_dirs=task_dirs,
            model=model,
            experiment_id=experiment_id,
            adapter=adapter,
            timeout=config.timeout,
        )
        evaluate = make_local_candidate_evaluator(workspace_root=workspace.root)
    elif config.backend in ("modal", "morph") and config.solver is not None and task_dirs:
        batch_planner, evaluate = _build_harbor_candidate_runtime(
            config=config,
            task_dirs=task_dirs,
            experiment_id=experiment_id,
        )
    else:
        if config.backend in ("modal", "morph"):
            logger.warning("backend=%r requires solver and tasks; using provider-free stubs", config.backend)
        batch_planner = _empty_batch_planner
        evaluate = make_stub_candidate_evaluator(())

    strategy: SelectionStrategy = (
        QDStrategy(evolver_model=config.models.evolver) if config.strategy == "qd" else HillClimbStrategy()
    )

    def vary(request: VariationRequest, source: Workspace, child_id: str) -> VariationResult:
        return run_structured_variation(
            request,
            source,
            child_id,
            evolver_model_name=config.models.evolver,
            evolver_llm=evolver_llm,
            compaction_llm=classifier_llm,
        )

    return run_evolution(
        workspace=workspace,
        config=config,
        evaluate=evaluate,
        strategy=strategy,
        batch_planner=batch_planner,
        variation=vary,
        enrich=lambda observations: enrich_observations(observations, classifier_llm=classifier_llm),
        report_writer=report_writer,
        clock=clock,
        run_id=run_id,
    )


def _enrich_candidate(
    candidate: EvaluatedCandidate,
    batch: CandidateEvaluationBatch,
    enrich: ObservationEnricher,
) -> EvaluatedCandidate:
    """Classify traces and bind resulting enrichments to the same evidence."""
    observations = tuple(enrich(candidate.observations))
    assessment = build_candidate_assessment(candidate.snapshot.candidate_id, batch, observations)
    return bind_evaluated_candidate(candidate.snapshot, observations, assessment)


def _build_analysis(candidate: EvaluatedCandidate, state: EvolutionState) -> EvolutionAnalysis:
    observations = candidate.observations
    raw_score = candidate.assessment.batch_score
    improving = raw_score > state.best_score
    discipline_scores = compute_discipline_scores(observations)
    patterns = detect_behavioral_patterns(observations)
    weakest = min(discipline_scores, key=lambda item: item.mean_reward).discipline if discipline_scores else None
    return EvolutionAnalysis(
        discipline_scores=discipline_scores,
        behavioral_patterns=patterns,
        scope=compute_graduated_scope(raw_score, improving),
        weakest_discipline=weakest,
        batch_score=raw_score,
    )


def _resolve_snapshot(
    candidate_id: str,
    snapshots: dict[str, WorkspaceSnapshot],
    strategy: SelectionStrategy,
) -> WorkspaceSnapshot:
    snapshot = snapshots.get(candidate_id) or strategy.get_snapshot(candidate_id)
    if snapshot is None:
        raise ValueError(f"selected candidate {candidate_id!r} has no available snapshot")
    snapshots[candidate_id] = snapshot
    return snapshot


def _next_selection(strategy: SelectionStrategy, state: EvolutionState, current_score: float) -> SelectionPlan | None:
    if isinstance(strategy, HillClimbStrategy):
        return SelectionPlan(
            parent_candidate_id=state.best_candidate_id,
            inspiration_candidate_ids=(),
            strategy=MutationStrategy.CONSERVATIVE,
            goal="Improve the best evaluated candidate.",
            reasoning=f"Explicit state selected best candidate {state.best_candidate_id}.",
        )
    selected = strategy.select_parent(current_score)
    if selected is None:
        return None
    return SelectionPlan(
        parent_candidate_id=selected.parent_candidate_id,
        inspiration_candidate_ids=tuple(selected.inspiration_candidate_ids),
        strategy=MutationStrategy(selected.strategy),
        goal="Explore a quality-diversity archive candidate.",
        reasoning=selected.reasoning,
    )


def _notify_strategy(
    strategy: SelectionStrategy,
    *,
    outcome: CycleOutcome,
    cycle_record: EvolutionCycleRecord,
    snapshot: WorkspaceSnapshot,
    score_history: list[float],
    graveyard: MutationGraveyard,
    run_id: str,
) -> None:
    strategy.on_cycle_end(
        cycle_record=cycle_record,
        snapshot=snapshot,
        step_result_gate=outcome.decision.decision,
        score_history=score_history,
        graveyard=graveyard,
        observations=list((outcome.child or outcome.parent).observations),
        run_id=run_id,
        outcome=outcome,
    )


def _graveyard_entry(outcome: CycleOutcome, run_id: str, timestamp: datetime) -> GraveyardEntry:
    child = outcome.child
    assert child is not None
    return GraveyardEntry(
        cycle=outcome.cycle,
        strategy=outcome.selection.strategy.value,
        mutation_description=outcome.variation.reasoning,
        score_before=outcome.parent.assessment.batch_score,
        score_after=child.assessment.batch_score,
        candidate_id=child.snapshot.candidate_id,
        failure_reason=outcome.decision.reason,
        parent_candidate_id=outcome.parent.snapshot.candidate_id,
        rejected_snapshot=child.snapshot,
        parent_assessment=outcome.parent.assessment,
        child_assessment=child.assessment,
        mutation=outcome.variation.mutation,
        run_id=run_id,
        timestamp=timestamp,
    )


def _candidate_summary(cycle: int, child: EvaluatedCandidate, selection: SelectionPlan) -> str:
    return f"cycle {cycle}: score {child.assessment.batch_score:.3f} [{selection.strategy.value}]"


def _project_score_history(
    records: Sequence[EvolutionCycleRecord],
    config: EvolutionConfig,
) -> list[float]:
    """Project active-candidate scores from exact completed cycle records."""
    return [
        assessment_score(
            record.child_assessment
            if record.gate_decision is GateDecision.ACCEPTED and record.child_assessment is not None
            else record.parent_assessment,
            structural_weight=config.structural_weight,
        )
        for record in records
    ]


def _is_converged(state: EvolutionState, config: EvolutionConfig) -> bool:
    from aec_bench.evolution.convergence import is_converged

    return is_converged(state, config)


def _write_report(workspace: Workspace, report_writer: ReportWriter | None) -> None:
    if report_writer is None:
        return
    try:
        report_path = report_writer(workspace.root)
        logger.info("Evolution report written to %s", report_path)
    except Exception:
        logger.warning("Failed to generate evolution report", exc_info=True)


def _empty_batch_planner(_batch_size: int, _cycle: int) -> CandidateEvaluationBatch:
    raise ValueError("evolution evaluation requires at least one resolved task")


def _timestamp_slug() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")


def _build_harbor_candidate_runtime(
    *,
    config: EvolutionConfig,
    task_dirs: Sequence[Path],
    experiment_id: str,
) -> tuple[CandidateBatchPlanner, CandidateEvaluator]:
    """Build planned-batch Harbor evaluation without candidate-specific planning."""
    from aec_bench.evolution.backends.local import make_local_candidate_batch_planner

    planner = make_local_candidate_batch_planner(
        task_dirs=task_dirs,
        model=config.solver.model if config.solver else config.models.evolver,
        experiment_id=experiment_id,
        adapter=config.solver.adapter if config.solver else "rlm",
        timeout=config.timeout,
        backend=config.backend,
        agent_config=config.solver,
    )
    return planner, _build_harbor_candidate_evaluator(config=config, experiment_id=experiment_id)


def _build_harbor_candidate_evaluator(*, config: EvolutionConfig, experiment_id: str) -> CandidateEvaluator:
    """Compose remote candidate evaluation from a preplanned batch."""
    from aec_bench.contracts.experiment_manifest import ComputeConfig, ExperimentManifest, TaskSelector
    from aec_bench.evolution.snapshot import serialise_snapshot
    from aec_bench.harness.artifact_tasks import SingleAttemptSpec, run_experiment
    from aec_bench.harness.harbor_runtime import HarborExperimentRuntime
    from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow

    solver = config.solver
    assert solver is not None
    project_root = Path(__file__).resolve().parents[3]
    artifact_root = Path(config.workspace_path) / "artifacts"
    call_count = 0

    def evaluate(snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch) -> tuple[TrialRecord, ...]:
        nonlocal call_count
        agent = solver.model_copy(update={"system_prompt": serialise_snapshot(snapshot)})
        if not batch.trials:
            raise ValueError("evaluation batch requires at least one planned trial")
        manifest = ExperimentManifest(
            experiment_id=batch.trials[0].experiment_id,
            name=f"Evolution evaluation {call_count}",
            tasks=TaskSelector(include_patterns=[task.task.task_id for task in batch.tasks]),
            agents=[agent],
            compute=ComputeConfig(backend=config.backend, timeout_override=config.timeout),
            repetitions=1,
        )
        trials = [replace(trial, agent=agent) for trial in batch.trials]
        runtime = HarborExperimentRuntime(
            workflow=SynchronousHarborWorkflow(
                project_root=project_root,
                repo_root=project_root,
                tasks_root=project_root / "tasks",
                ledger_root=artifact_root / "ledger",
                jobs_root=artifact_root / "jobs",
            ),
            manifest=manifest,
            config_path=artifact_root / f"harbor-{call_count}.yaml",
        )
        call_count += 1
        return tuple(
            run_experiment(
                runtime=runtime,
                tasks=list(batch.tasks),
                trials=trials,
                recipe=SingleAttemptSpec(),
            )
        )

    return evaluate


__all__ = (
    "CandidateEvaluator",
    "ObservationEnricher",
    "ReportWriter",
    "VariationOperator",
    "run_evolution",
    "run_evolution_from_config",
)
