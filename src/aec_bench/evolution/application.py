# ABOUTME: Functional application entry points for evolution execution.
# ABOUTME: Composes candidate evaluation, evolution policy, persistence, and configuration assembly.

from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolutionCycleRecord,
    EvolutionObservation,
    EvolutionResult,
    GateDecision,
    MutationSummary,
    ObservationEnrichment,
    WorkspaceSnapshot,
)
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.archive_agent import SelectionResult
from aec_bench.evolution.engine import AECEvolutionEngine
from aec_bench.evolution.graveyard import GraveyardMutationAction
from aec_bench.evolution.strategy import HillClimbStrategy, SelectionStrategy
from aec_bench.evolution.workspace import Workspace
from aec_bench.generation.application import generate_template_instances, resolve_template

logger = logging.getLogger(__name__)

CandidateEvaluator = Callable[[WorkspaceSnapshot, int], list[TrialRecord]]
ReportWriter = Callable[[Path], Path]


def run_evolution(
    *,
    workspace: Workspace,
    config: EvolutionConfig,
    engine: AECEvolutionEngine,
    evaluate: CandidateEvaluator,
    strategy: SelectionStrategy,
    report_writer: ReportWriter | None = None,
) -> EvolutionResult:
    """Run evolution directly and return its result."""
    workspace.init_versioning()
    history: list[EvolutionCycleRecord] = []
    score_history: list[float] = []

    # The run ID gives candidate IDs a stable namespace.
    run_id = _timestamp_slug()
    engine.set_run_id(run_id)
    engine.set_strategy_name(strategy.summary().get("mode", ""))
    logger.info("Evolution run ID: %s", run_id)

    from aec_bench.evolution.graveyard import MutationGraveyard

    graveyard = MutationGraveyard.load(workspace.root / "graveyard.json")

    # Selection from the previous cycle — applied at the start of the next.
    # This ensures observations match the workspace state (solve happens
    # AFTER the parent is applied, not before).
    pending_selection: SelectionResult | None = None

    for cycle in range(config.max_cycles):
        candidates = workspace.list_candidates()
        current_candidate_id = (
            history[-1].candidate_id_after if history else candidates[-1].candidate_id if candidates else "baseline"
        )

        # 0. Apply selected parent from previous cycle (if any)
        if pending_selection is not None:
            parent_snapshot = strategy.get_snapshot(
                pending_selection.parent_candidate_id,
            )
            if parent_snapshot is not None:
                workspace.apply_snapshot(parent_snapshot)
                current_candidate_id = parent_snapshot.candidate_id
                logger.info(
                    "Applied parent: %s",
                    pending_selection.parent_candidate_id,
                )

        # 1. Export current workspace snapshot
        snapshot = workspace.export_snapshot(candidate_id=current_candidate_id)

        # 2. Solve: run a batch of tasks via the injected backend
        trial_records = evaluate(snapshot, config.batch_size)

        # 3. Enrich: wrap trial records as EvolutionObservations
        observations = _build_observations(trial_records, current_candidate_id)

        # Use the pending selection as the current cycle's selection context
        selection = pending_selection
        pending_selection = None

        # 4. Evolve: run one engine step
        step_result = engine.step(
            workspace,
            observations,
            history,
            selection=selection,
            graveyard=graveyard,
        )

        # 4b. Persist per-trial outcomes from retained trial artifacts.
        enriched_obs = step_result.enriched_observations or observations
        from aec_bench.evolution.trial_persistence import persist_cycle_trials

        persist_cycle_trials(
            workspace_root=workspace.root,
            cycle=step_result.cycle_record.cycle,
            run_id=run_id,
            observations=enriched_obs,
        )

        # 5. Record
        history.append(step_result.cycle_record)
        score_history.append(step_result.cycle_record.batch_score)

        # 5b. Export post-mutation snapshot for strategy
        current_snapshot = workspace.export_snapshot(
            candidate_id=step_result.cycle_record.candidate_id_after,
        )

        # 5c. Feed graveyard on rejection
        if (
            len(score_history) > 1
            and step_result.mutation is not None
            and step_result.gate_decision != GateDecision.ACCEPTED
        ):
            from aec_bench.evolution.graveyard import GraveyardEntry

            prev_score = score_history[-2]
            score_delta = step_result.cycle_record.batch_score - prev_score

            graveyard.insert(
                GraveyardEntry(
                    cycle=step_result.cycle_record.cycle,
                    strategy=selection.strategy if selection else "unknown",
                    mutation_description=step_result.mutation.evolver_reasoning or "",
                    score_before=prev_score,
                    score_after=step_result.cycle_record.batch_score,
                    candidate_id=step_result.cycle_record.candidate_id_after,
                    failure_reason=f"Score delta: {score_delta:+.3f}",
                    field_failures=_extract_field_failures(observations),
                    mutation_actions=_extract_mutation_actions(step_result.mutation),
                )
            )

        # 5d. Delegate to strategy
        strategy.on_cycle_end(
            cycle_record=step_result.cycle_record,
            snapshot=current_snapshot,
            step_result_gate=step_result.gate_decision,
            score_history=score_history,
            graveyard=graveyard,
            observations=observations,
            run_id=run_id,
        )

        # Log cycle summary — visible at INFO level (default when evolve CLI runs)
        gate = step_result.gate_decision.value
        mutation_desc = _describe_mutation(step_result.mutation)

        logger.info(
            "Cycle %d/%d — score=%.2f, gate=%s, mutations=[%s]",
            cycle + 1,
            config.max_cycles,
            score_history[-1],
            gate,
            mutation_desc,
        )

        # 6. Select parent for NEXT cycle
        pending_selection = strategy.select_parent(score_history[-1])
        if pending_selection is not None:
            logger.info(
                "Next-cycle selection: parent=%s, strategy=%s",
                pending_selection.parent_candidate_id,
                pending_selection.strategy,
            )

        # 7. Convergence check
        if _is_converged(score_history, config):
            break

    # Persist
    _write_report(workspace, report_writer)
    strategy.save(workspace.root)
    graveyard.save(workspace.root / "graveyard.json")
    logger.info("Graveyard saved: %d entries", graveyard.size)

    run_id_full = f"evo-{workspace.manifest.name}-{_timestamp_slug()}"

    return EvolutionResult(
        run_id=run_id_full,
        workspace_name=workspace.manifest.name,
        cycles_completed=len(history),
        final_score=score_history[-1] if score_history else 0.0,
        best_score=max(score_history) if score_history else 0.0,
        best_candidate_id=_find_best_candidate_id(history),
        score_history=score_history,
        converged=_is_converged(score_history, config),
        total_trials=sum(len(cr.trial_ids) for cr in history),
        cycle_records=history,
        archive_summary=strategy.summary(),
    )


def run_evolution_from_config(
    *,
    config: EvolutionConfig,
    tasks_root: Path | None = None,
    report_writer: ReportWriter | None = None,
) -> EvolutionResult:
    """Assemble and run evolution from repository configuration."""
    from aec_bench.evolution.backends.local import make_local_candidate_evaluator, make_stub_candidate_evaluator
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

    model = config.models.evolver
    adapter = "rlm"
    if config.solver is not None:
        model = config.solver.model
        adapter = config.solver.adapter

    experiment_id = f"evo-{workspace.manifest.name}"
    if config.backend in ("modal", "morph") and config.solver is not None:
        evaluate = _build_harbor_candidate_evaluator(
            config=config,
            task_dirs=task_dirs,
            experiment_id=experiment_id,
        )
    elif task_dirs and config.backend == "local":
        evaluate = make_local_candidate_evaluator(
            task_dirs=task_dirs,
            model=model,
            experiment_id=experiment_id,
            adapter=adapter,
            timeout=config.timeout,
            workspace_root=Path(config.workspace_path),
        )
    else:
        if config.backend in ("modal", "morph"):
            logger.warning(
                "backend=%r requires solver config (via harness_config or explicit solver). "
                "Falling back to stub candidate evaluator.",
                config.backend,
            )
        evaluate = make_stub_candidate_evaluator([])

    engine = AECEvolutionEngine(
        classifier_llm=classifier_llm,
        evolver_llm=evolver_llm,
        evolver_model_name=config.models.evolver,
        improvement_threshold=config.improvement_threshold,
        stagnation_window=config.stagnation_window,
        structural_weight=config.structural_weight,
    )
    strategy: SelectionStrategy
    if config.strategy == "qd":
        strategy = QDStrategy(evolver_model=config.models.evolver)
    else:
        strategy = HillClimbStrategy()

    return run_evolution(
        workspace=workspace,
        config=config,
        engine=engine,
        evaluate=evaluate,
        strategy=strategy,
        report_writer=report_writer,
    )


def _extract_field_failures(
    observations: list[EvolutionObservation],
) -> dict[str, str] | None:
    """Extract field failure directions from observations."""
    from aec_bench.evolution.prompts import _describe_error_direction

    failures: dict[str, str] = {}
    for obs in observations:
        for fs in obs.enrichment.field_scores:
            if fs.reward < 1.0 and fs.expected is not None and fs.actual is not None:
                failures[fs.field_name] = _describe_error_direction(
                    fs.expected,
                    fs.actual,
                )
    return failures if failures else None


def _extract_mutation_actions(
    mutation: MutationSummary | None,
) -> list[GraveyardMutationAction] | None:
    """Convert a MutationSummary to a list of action dicts for the graveyard."""
    if mutation is None:
        return None
    actions: list[GraveyardMutationAction] = []
    if mutation.prompt_modified:
        actions.append({"action_type": "modify_prompt"})
    for name in mutation.skills_added:
        actions.append({"action_type": "write_skill", "skill_name": name})
    for name in mutation.skills_modified:
        actions.append({"action_type": "modify_skill", "skill_name": name})
    for name in mutation.skills_removed:
        actions.append({"action_type": "remove_skill", "skill_name": name})
    return actions if actions else None


def _describe_mutation(mutation: MutationSummary | None) -> str:
    """Build a short mutation description for logging."""
    if mutation is None:
        return "no changes"
    parts: list[str] = []
    if mutation.skills_added:
        parts.append(f"+{len(mutation.skills_added)} skills")
    if mutation.skills_modified:
        parts.append(f"~{len(mutation.skills_modified)} skills")
    if mutation.skills_removed:
        parts.append(f"-{len(mutation.skills_removed)} skills")
    if mutation.prompt_modified:
        parts.append("prompt modified")
    return ", ".join(parts) if parts else "no changes"


def _write_report(workspace: Workspace, report_writer: ReportWriter | None) -> None:
    """Generate and write the evolution HTML report to the workspace."""
    if report_writer is None:
        return
    try:
        report_path = report_writer(workspace.root)
        logger.info("Evolution report written to %s", report_path)
    except Exception:
        logger.warning("Failed to generate evolution report", exc_info=True)


def _build_observations(
    trial_records: list[TrialRecord],
    candidate_id: str,
) -> list[EvolutionObservation]:
    """Wrap trial records as EvolutionObservations with empty enrichment.

    Discipline is extracted from the first component of task_id so the
    engine's classify phase can route observations correctly.
    """
    observations: list[EvolutionObservation] = []
    for record in trial_records:
        discipline = _extract_discipline(record.task.task_id)
        obs = EvolutionObservation(
            trial=record,
            enrichment=ObservationEnrichment(),
            candidate_id=candidate_id,
            discipline=discipline,
        )
        observations.append(obs)
    return observations


def _is_converged(score_history: list[float], config: EvolutionConfig) -> bool:
    """Return True when scores are flat within the stagnation window.

    Requires at least stagnation_window + 1 entries before evaluating.
    Convergence is declared when every score in the window is within
    improvement_threshold of every other score in the window.
    """
    window = config.stagnation_window
    if len(score_history) < window + 1:
        return False
    recent = score_history[-window:]
    return (max(recent) - min(recent)) <= config.improvement_threshold


def _find_best_candidate_id(history: list[EvolutionCycleRecord]) -> str:
    """Return the candidate ID from the cycle with the highest batch score."""
    if not history:
        return "baseline"
    best = max(history, key=lambda cr: cr.batch_score)
    return best.candidate_id_after


def _build_harbor_candidate_evaluator(
    *,
    config: EvolutionConfig,
    task_dirs: list[Path],
    experiment_id: str,
) -> CandidateEvaluator:
    """Compose remote candidate evaluation through the shared experiment runner."""
    from aec_bench.contracts.experiment_manifest import ComputeConfig, ExperimentManifest, TaskSelector
    from aec_bench.evolution.snapshot import serialise_snapshot
    from aec_bench.harness.artifact_tasks import SingleAttemptSpec, run_experiment
    from aec_bench.harness.harbor_runtime import HarborExperimentRuntime
    from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
    from aec_bench.harness.scheduler import build_trial_plan
    from aec_bench.tasks.instance import resolve_instance_paths
    from aec_bench.tasks.loader import load_task_definition

    solver = config.solver
    assert solver is not None
    project_root = Path(__file__).resolve().parents[3]
    artifact_root = Path(config.workspace_path) / "artifacts"
    resolved = []
    for task_dir in task_dirs:
        try:
            tasks_root = next((parent for parent in task_dir.parents if parent.name == "tasks"), task_dir.parent)
            task = load_task_definition(task_dir, tasks_root)
            resolved.append(resolve_instance_paths(task, task_dir))
        except (OSError, ValueError):
            logger.warning("Failed to resolve task: %s", task_dir, exc_info=True)

    call_count = 0

    def evaluate(snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
        nonlocal call_count
        selected = resolved[:batch_size]
        if not selected:
            return []
        agent = solver.model_copy(update={"system_prompt": serialise_snapshot(snapshot)})
        manifest = ExperimentManifest(
            experiment_id=f"{experiment_id}-cycle-{call_count}",
            name=f"Evolution evaluation {call_count}",
            tasks=TaskSelector(include_patterns=[task.task.task_id for task in selected]),
            agents=[agent],
            compute=ComputeConfig(
                backend=config.backend,
                timeout_override=config.timeout,
            ),
            repetitions=1,
        )
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
        trials = build_trial_plan(manifest, [task.task for task in selected])
        call_count += 1
        return run_experiment(
            runtime=runtime,
            tasks=selected,
            trials=trials,
            recipe=SingleAttemptSpec(),
        )

    return evaluate


# ---------------------------------------------------------------------------
# Private module-level helpers
# ---------------------------------------------------------------------------


def _extract_discipline(task_id: str) -> str:
    """Extract the discipline from a task_id path.

    For example "electrical/voltage-drop/au-office-fitout" → "electrical".
    Falls back to the full task_id when there is no slash separator.
    """
    return task_id.split("/")[0]


def _timestamp_slug() -> str:
    """Return a compact UTC timestamp string suitable for use in identifiers."""
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
