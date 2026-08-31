# ABOUTME: Functional application entry points for evolution execution.
# ABOUTME: Coordinates exact candidate evaluation, scratch variation, decisions, and effects.

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolutionCycleRecord,
    EvolutionResult,
    GateDecision,
    MutationStrategy,
    WorkspaceSnapshot,
)
from aec_bench.contracts.task_definition import Lifecycle, Visibility
from aec_bench.contracts.trial_record import CostRecord, TrialRecord
from aec_bench.evolution.analysis import (
    EvolutionAnalysis,
    compute_discipline_scores,
    compute_graduated_scope,
    detect_behavioral_patterns,
)
from aec_bench.evolution.archive import ArchiveBatchOutcome, ArchiveView, QDArchive
from aec_bench.evolution.archive_agent import run_archive_selection
from aec_bench.evolution.checkpoint import AVOConfigurationIdentity
from aec_bench.evolution.convergence import is_converged
from aec_bench.evolution.core import (
    CandidateProposal,
    CandidateProposalRequest,
    CycleOutcome,
    EvaluatedCandidate,
    EvolutionState,
    ProposalStatus,
    ResolvedSelection,
    SelectionPlan,
    assessment_score,
    gate_candidate,
    next_evolution_state,
)
from aec_bench.evolution.enrichment import enrich_observations
from aec_bench.evolution.evaluation import (
    CandidateChecks,
    CandidateEvaluationBatch,
)
from aec_bench.evolution.graveyard import GraveyardEntry, MutationGraveyard
from aec_bench.evolution.memory import AVOMemoryEntry
from aec_bench.evolution.model_provider import build_pydantic_model
from aec_bench.evolution.proposer import build_avo
from aec_bench.evolution.selection import (
    CellSelectionStat,
    CellSelectionState,
    QDState,
    StrategyBanditState,
    select_mutation_strategy,
    shortlist_cells,
    update_cell_selection_state,
    update_strategy_bandit_state,
)
from aec_bench.evolution.workspace import Workspace
from aec_bench.generation.application import generate_template_instances, resolve_template
from aec_bench.tasks.loader import load_task_definition

logger = logging.getLogger(__name__)

ReportWriter = Callable[[Path], Path]
CandidateIdFactory = Callable[[str, int], str]
CandidateProposer = Callable[[CandidateProposalRequest, Workspace, str], CandidateProposal]
ArchiveAgent = Callable[[str, ArchiveView, MutationGraveyard, list[str], float, MutationStrategy, int], SelectionPlan]


@dataclass(frozen=True)
class EvolutionCycleExecution:
    """Result of one functional evolution cycle, including its next state."""

    outcome: CycleOutcome
    record: EvolutionCycleRecord
    state: EvolutionState
    score: float
    archive_outcome: ArchiveBatchOutcome | None = None


def _execute_evolution_cycle(
    *,
    workspace: Workspace,
    config: EvolutionConfig,
    checks: CandidateChecks,
    propose: CandidateProposer,
    graveyard: MutationGraveyard,
    history: list[EvolutionCycleRecord],
    snapshots: dict[str, WorkspaceSnapshot],
    cycle: int,
    state: EvolutionState | None,
    resolved_selection: ResolvedSelection,
    run_id: str,
    now: Callable[[], datetime],
    candidate_id_factory: CandidateIdFactory,
    archive: QDArchive | None = None,
    planned_batch: CandidateEvaluationBatch | None = None,
    evaluated_parent: EvaluatedCandidate | None = None,
    memory: tuple[AVOMemoryEntry, ...] = (),
) -> EvolutionCycleExecution:
    """Execute one cycle through the same functional path as ``run_evolution``.

    This narrow boundary lets provider-free swarm callers share the canonical
    candidate/evidence lifecycle without reviving a stateful engine.
    """
    selection = resolved_selection.plan
    parent_snapshot = resolved_selection.parent
    batch = planned_batch or checks.plan_batch(config.batch_size, cycle - 1)
    parent = evaluated_parent
    if parent is None or parent.snapshot.candidate_id != parent_snapshot.candidate_id:
        parent = checks.assess(parent_snapshot, batch)
    if state is None:
        state = EvolutionState.from_baseline(parent, structural_weight=config.structural_weight)

    analysis = _build_analysis(parent, state)
    inspirations = resolved_selection.inspirations
    request = CandidateProposalRequest(
        run_id=run_id,
        selection=selection,
        parent=parent,
        inspirations=inspirations,
        analysis=analysis,
        scope=analysis.scope,
        history=tuple(history),
        graveyard=tuple(graveyard.browse(limit=graveyard.size)),
        cycle=cycle,
        memory=memory,
    )
    child_candidate_id = candidate_id_factory(run_id, cycle)
    proposal = propose(request, workspace, child_candidate_id)
    child: EvaluatedCandidate | None = None
    if proposal.status is ProposalStatus.SUBMITTED:
        if proposal.child is None:
            raise ValueError("submitted proposal did not provide a child snapshot")
        child = checks.assess(proposal.child, batch)

    decision = gate_candidate(
        parent=parent,
        child=child,
        proposal=proposal,
        state=state,
        config=config,
    )
    archive_outcome: ArchiveBatchOutcome | None = None
    if archive is not None and child is not None and child.assessment.valid:
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        insertions = tuple(
            archive.insert(
                extract_behaviour_descriptor(observation),
                child.snapshot,
                task_ids=(observation.trial.task.task_id,),
                discipline=observation.discipline,
                run_id=run_id,
            )
            for observation in child.observations
        )
        archive_outcome = ArchiveBatchOutcome(candidate_id=child.snapshot.candidate_id, insertions=insertions)
        if archive_outcome.added:
            score = assessment_score(child.assessment, structural_weight=config.structural_weight)
            global_improved = score > state.best_score + config.improvement_threshold
            decision = replace(
                decision,
                decision=GateDecision.ACCEPTED,
                reason="candidate entered or improved a quality-diversity archive cell",
                effective_score=score,
                improved=global_improved,
                cycles_without_improvement=0 if global_improved else state.cycles_without_improvement + 1,
            )
        else:
            decision = replace(
                decision,
                decision=GateDecision.REJECTED,
                reason="candidate did not enter or improve a quality-diversity archive cell",
            )
    next_state = next_evolution_state(state=state, parent=parent, child=child, decision=decision)
    outcome = CycleOutcome(
        cycle=cycle,
        selection=selection,
        parent=parent,
        proposal=proposal,
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
    return EvolutionCycleExecution(
        outcome=outcome,
        record=record,
        state=next_state,
        score=score,
        archive_outcome=archive_outcome,
    )


def run_evolution(
    *,
    workspace: Workspace,
    config: EvolutionConfig,
    selection_checks: CandidateChecks,
    propose: CandidateProposer,
    report_writer: ReportWriter | None = None,
    clock: Callable[[], datetime] | None = None,
    run_id: str | None = None,
    candidate_id_factory: CandidateIdFactory | None = None,
    archive_agent: ArchiveAgent | None = None,
) -> EvolutionResult:
    """Run one functional evolution loop.

    Evaluation is planned once per cycle and both candidates use that exact
    plan. The canonical workspace is changed only after an accepted child.
    Candidate checks and proposal are explicit application dependencies.
    """
    workspace.init_versioning()
    now = clock or (lambda: datetime.now(tz=UTC))
    resolved_run_id = run_id or _timestamp_slug()
    make_candidate_id = candidate_id_factory or (lambda current_run, cycle: f"{current_run}:{cycle}")
    graveyard = MutationGraveyard.load(workspace.root / "graveyard.json")
    history: list[EvolutionCycleRecord] = []
    snapshots: dict[str, WorkspaceSnapshot] = {"baseline": workspace.export_snapshot("baseline")}
    state: EvolutionState | None = None
    proposal_memory: tuple[AVOMemoryEntry, ...] = ()

    baseline_batch = selection_checks.plan_batch(config.batch_size, 0)
    baseline = selection_checks.assess(snapshots["baseline"], baseline_batch)
    state = EvolutionState.from_baseline(baseline, structural_weight=config.structural_weight)

    archive: QDArchive | None = None
    qd_state: QDState | None = None
    if config.strategy == "qd":
        archive_path = workspace.root / "archive.json"
        archive = (
            QDArchive.load(archive_path)
            if archive_path.exists()
            else QDArchive(n_centroids=config.qd_n_centroids, seed=config.qd_seed)
        )
        _insert_candidate_descriptors(archive, baseline, run_id=resolved_run_id)
        qd_state = _load_qd_state(workspace.root / "qd_state.json")
        if qd_state is None:
            qd_state = _initial_qd_state(archive)
        _add_archive_snapshots(archive, snapshots)
        _add_graveyard_snapshots(graveyard, snapshots)
    starting_cycle = qd_state.cycle if qd_state is not None else 0

    for cycle_index in range(config.max_cycles):
        cycle = starting_cycle + cycle_index + 1
        if config.strategy == "qd":
            assert archive is not None and qd_state is not None
            _add_graveyard_snapshots(graveyard, snapshots)
            selection, parent_cell_index = _select_qd_plan(
                archive=archive,
                graveyard=graveyard,
                state=qd_state,
                current_score=state.best_score,
                config=config,
                archive_agent=archive_agent,
            )
            qd_state = replace(qd_state, last_selection=selection)
        else:
            selection = SelectionPlan(
                parent_candidate_id=state.best_candidate_id,
                inspiration_candidate_ids=(),
                strategy=MutationStrategy.CONSERVATIVE,
                goal="Improve the best evaluated candidate.",
                reasoning=f"Explicit state selected best candidate {state.best_candidate_id}.",
            )
        resolved_selection = _resolve_selection(selection, snapshots)
        execution = _execute_evolution_cycle(
            workspace=workspace,
            config=config,
            checks=selection_checks,
            propose=propose,
            graveyard=graveyard,
            history=history,
            snapshots=snapshots,
            cycle=cycle,
            state=state,
            resolved_selection=resolved_selection,
            run_id=resolved_run_id,
            now=now,
            candidate_id_factory=make_candidate_id,
            archive=archive,
            planned_batch=baseline_batch if cycle == 1 else None,
            evaluated_parent=baseline if cycle == 1 and selection.parent_candidate_id == "baseline" else None,
            memory=proposal_memory,
        )
        record = execution.record
        history.append(record)
        state = execution.state
        proposal_memory = execution.outcome.proposal.memory
        if config.strategy == "qd":
            assert archive is not None and qd_state is not None
            qd_state = replace(qd_state, cycle=cycle)
            if parent_cell_index is not None and execution.outcome.proposal.status is ProposalStatus.SUBMITTED:
                inserted = execution.archive_outcome.added if execution.archive_outcome is not None else False
                qd_state = replace(
                    qd_state,
                    cell_selection=update_cell_selection_state(
                        qd_state.cell_selection,
                        parent_cell_index,
                        cycle,
                        improved=inserted,
                    ),
                    strategy_bandit=update_strategy_bandit_state(
                        qd_state.strategy_bandit,
                        selection.strategy,
                        success=inserted,
                    ),
                )
        logger.info(
            "Cycle %d/%d — score=%.3f, gate=%s, parent=%s, child=%s",
            cycle,
            config.max_cycles,
            execution.score,
            execution.outcome.decision.decision.value,
            execution.outcome.parent.snapshot.candidate_id,
            execution.outcome.child.snapshot.candidate_id if execution.outcome.child else "none",
        )
        if is_converged(state, config):
            break

    assert state is not None
    _write_report(workspace, report_writer)
    graveyard.save(workspace.root / "graveyard.json")
    archive_summary: dict[str, object] | None = None
    if archive is not None:
        archive.save(workspace.root / "archive.json")
        assert qd_state is not None
        _save_qd_state(workspace.root / "qd_state.json", qd_state)
        archive_summary = {"mode": "qd", "archive_summary": archive.to_summary()}
    return EvolutionResult(
        run_id=resolved_run_id,
        workspace_name=workspace.manifest.name,
        cycles_completed=len(history),
        final_score=_project_score_history(history, config)[-1] if history else state.best_score,
        best_score=state.best_score,
        best_candidate_id=state.best_candidate_id,
        score_history=_project_score_history(history, config),
        converged=is_converged(state, config),
        total_trials=sum(len(record.parent_assessment.trial_ids) for record in history)
        + sum(len(record.child_assessment.trial_ids) for record in history if record.child_assessment is not None),
        total_evolver_cost=_project_total_evolver_cost(history),
        cycle_records=history,
        archive_summary=archive_summary,
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
    from aec_bench.evolution.backends.local import build_local_checks
    from aec_bench.evolution.config_loader import resolve_task_dirs
    from aec_bench.providers.behavioral_llm import build_behavioral_llm_client

    workspace = Workspace(Path(config.workspace_path))
    resolved_run_id = run_id or _timestamp_slug()
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
            task_lifecycle=Lifecycle.ACTIVE,
            task_visibility=Visibility.PUBLIC,
        )
        _validate_public_evolution_tasks(generated.task_paths, generated.output_root)
        task_dirs.extend(generated.task_paths)
    if tasks_root is not None:
        resolved_tasks_root = tasks_root.resolve()
        resolved_task_dirs = resolve_task_dirs(config.task_selector, resolved_tasks_root)
        _validate_public_evolution_tasks(resolved_task_dirs, resolved_tasks_root)
        task_dirs.extend(resolved_task_dirs)

    # Validate task visibility before composing any model client or entering
    # the host application. Holdout material belongs to a separate qualification
    # operation and must never reach adaptive evolution.
    classifier_llm = build_behavioral_llm_client(model=config.models.classifier)

    model = config.solver.model if config.solver is not None else config.models.evolver
    adapter = config.solver.adapter if config.solver is not None else "rlm"
    run_digest = hashlib.sha256(resolved_run_id.encode("utf-8")).hexdigest()
    experiment_id = f"evo-{workspace.manifest.name}-{run_digest}"
    development_experiment_id = f"{experiment_id}-development"
    configuration_digest = hashlib.sha256(
        json.dumps(config.model_dump(mode="json"), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    avo_configuration_identity = AVOConfigurationIdentity(
        model_identity=config.models.evolver,
        supervisor_model_identity=config.models.evolver,
        tool_identity="avo-tools:1",
        development_evaluator_identity=(
            f"{config.backend}:{development_experiment_id}:{adapter}:{model}:timeout-{config.timeout}"
        ),
        configuration_identity=f"evolution-config:{configuration_digest}",
    )
    if config.backend == "local" and task_dirs:
        selection_checks = build_local_checks(
            task_dirs=task_dirs,
            model=model,
            experiment_id=experiment_id,
            workspace_root=workspace.root,
            adapter=adapter,
            timeout=config.timeout,
        )
        revision_checks = build_local_checks(
            task_dirs=task_dirs,
            model=model,
            experiment_id=development_experiment_id,
            workspace_root=workspace.root,
            candidate_identity=False,
            adapter=adapter,
            timeout=config.timeout,
        )
    elif config.backend in ("modal", "morph") and config.solver is not None and task_dirs:
        selection_checks = _build_harbor_candidate_runtime(
            config=config,
            task_dirs=task_dirs,
            experiment_id=experiment_id,
        )
        revision_checks = _build_harbor_candidate_runtime(
            config=config,
            task_dirs=task_dirs,
            experiment_id=development_experiment_id,
        )
    else:
        if config.backend in ("modal", "morph"):
            logger.warning("backend=%r requires solver and tasks; using provider-free stubs", config.backend)
        selection_checks = CandidateChecks(plan=_empty_batch_planner, run=_empty_evaluator)
        revision_checks = CandidateChecks(plan=_empty_batch_planner, run=_empty_evaluator)

    evolver_model = build_pydantic_model(config.models.evolver)
    avo = build_avo(
        model=evolver_model,
        model_identity=avo_configuration_identity.model_identity,
        revision_checks=revision_checks,
        batch_size=config.batch_size,
        revision_experiment_prefix=development_experiment_id,
        compaction_llm=classifier_llm,
        checkpoint_root=workspace.root,
        configuration_identity=avo_configuration_identity,
    )

    return run_evolution(
        workspace=workspace,
        config=config,
        selection_checks=replace(
            selection_checks,
            enrich=lambda observations: enrich_observations(observations, classifier_llm=classifier_llm),
        ),
        propose=avo,
        report_writer=report_writer,
        clock=clock,
        run_id=resolved_run_id,
    )


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


def _resolve_selection(selection: SelectionPlan, snapshots: dict[str, WorkspaceSnapshot]) -> ResolvedSelection:
    """Resolve a validated plan to exact snapshot material before variation."""
    parent = snapshots.get(selection.parent_candidate_id)
    if parent is None:
        raise ValueError(f"selected candidate {selection.parent_candidate_id!r} has no available snapshot")
    inspirations = []
    for candidate_id in selection.inspiration_candidate_ids:
        snapshot = snapshots.get(candidate_id)
        if snapshot is None:
            raise ValueError(f"selected candidate {candidate_id!r} has no available snapshot")
        inspirations.append(snapshot)
    return ResolvedSelection(plan=selection, parent=parent, inspirations=tuple(inspirations))


def _initial_qd_state(archive: QDArchive) -> QDState:
    """Create selector state from the archive cells occupied at startup."""
    return QDState(
        cell_selection=CellSelectionState(
            stats=tuple(CellSelectionStat(entry.cell_index) for entry in archive.view().entries)
        ),
        strategy_bandit=StrategyBanditState(),
        last_selection=None,
        cycle=0,
    )


def _add_archive_snapshots(archive: QDArchive, snapshots: dict[str, WorkspaceSnapshot]) -> None:
    for entry in archive.view().entries:
        snapshots.setdefault(entry.snapshot.candidate_id, entry.snapshot)


def _add_graveyard_snapshots(graveyard: MutationGraveyard, snapshots: dict[str, WorkspaceSnapshot]) -> None:
    for entry in graveyard.browse(limit=graveyard.size):
        if entry.rejected_snapshot is not None and entry.rejected_snapshot.candidate_id == entry.candidate_id:
            snapshots.setdefault(entry.candidate_id, entry.rejected_snapshot)


def _insert_candidate_descriptors(
    archive: QDArchive,
    candidate: EvaluatedCandidate,
    *,
    run_id: str,
) -> ArchiveBatchOutcome:
    from aec_bench.evolution.behaviour import extract_behaviour_descriptor

    return ArchiveBatchOutcome(
        candidate_id=candidate.snapshot.candidate_id,
        insertions=tuple(
            archive.insert(
                extract_behaviour_descriptor(observation),
                candidate.snapshot,
                task_ids=(observation.trial.task.task_id,),
                discipline=observation.discipline,
                run_id=run_id,
            )
            for observation in candidate.observations
        ),
    )


def _select_qd_plan(
    *,
    archive: QDArchive,
    graveyard: MutationGraveyard,
    state: QDState,
    current_score: float,
    config: EvolutionConfig,
    archive_agent: ArchiveAgent | None,
) -> tuple[SelectionPlan, int]:
    """Select one bounded plan from explicit archive and selector values."""
    strategy = select_mutation_strategy(
        state.strategy_bandit,
        graveyard_available=_has_resolvable_graveyard(graveyard),
        seed=config.qd_seed + state.cycle,
    )
    cells = shortlist_cells(
        state.cell_selection,
        (entry.cell_index for entry in archive.view().entries),
        k=config.qd_shortlist_size,
        seed=config.qd_seed + state.cycle,
    )
    entries_by_cell = {entry.cell_index: entry for entry in archive.view().entries}
    shortlist = []
    candidate_cells: dict[str, int] = {}
    for cell in cells:
        candidate_id = entries_by_cell[cell].snapshot.candidate_id
        if candidate_id not in shortlist:
            shortlist.append(candidate_id)
            candidate_cells[candidate_id] = cell
    if not shortlist:
        raise ValueError("QD selection requires at least one occupied archive cell")
    select = archive_agent or run_archive_selection
    plan = select(
        config.models.evolver,
        archive.view(),
        graveyard,
        shortlist,
        current_score,
        strategy,
        config.qd_inspiration_limit,
    )
    if plan.strategy is not strategy:
        raise ValueError("archive agent changed the host-selected mutation strategy")
    if plan.parent_candidate_id not in shortlist:
        raise ValueError("archive agent selected parent outside the allowed candidate set")
    allowed_inspirations = set(shortlist)
    if strategy is MutationStrategy.GRAVEYARD_RESCUE:
        allowed_inspirations.update(
            entry.candidate_id
            for entry in graveyard.browse(limit=graveyard.size)
            if entry.rejected_snapshot is not None and entry.rejected_snapshot.candidate_id == entry.candidate_id
        )
    if len(plan.inspiration_candidate_ids) > config.qd_inspiration_limit:
        raise ValueError("archive agent returned too many inspirations")
    if any(candidate_id not in allowed_inspirations for candidate_id in plan.inspiration_candidate_ids):
        raise ValueError("archive agent returned an unknown inspiration ID")
    return plan, candidate_cells[plan.parent_candidate_id]


def _has_resolvable_graveyard(graveyard: MutationGraveyard) -> bool:
    return any(
        entry.rejected_snapshot is not None and entry.rejected_snapshot.candidate_id == entry.candidate_id
        for entry in graveyard.browse(limit=graveyard.size)
    )


def _save_qd_state(path: Path, state: QDState) -> None:
    payload = {
        "cycle": state.cycle,
        "last_selection": state.last_selection.to_record().model_dump(mode="json")
        if state.last_selection is not None
        else None,
        "cell_selection": [stat.__dict__ for stat in state.cell_selection.stats],
        "strategy_bandit": [
            {"strategy": stat.strategy.value, "attempts": stat.attempts, "successes": stat.successes}
            for stat in state.strategy_bandit.stats
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_qd_state(path: Path) -> QDState | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    from aec_bench.evolution.selection import StrategyBanditStat

    plan_data = data.get("last_selection")
    plan = SelectionPlan(**plan_data) if plan_data is not None else None
    return QDState(
        cell_selection=CellSelectionState(
            stats=tuple(CellSelectionStat(**item) for item in data.get("cell_selection", []))
        ),
        strategy_bandit=StrategyBanditState(
            stats=tuple(StrategyBanditStat(**item) for item in data.get("strategy_bandit", []))
        ),
        last_selection=plan,
        cycle=int(data.get("cycle", 0)),
    )


def _graveyard_entry(outcome: CycleOutcome, run_id: str, timestamp: datetime) -> GraveyardEntry:
    child = outcome.child
    assert child is not None
    return GraveyardEntry(
        cycle=outcome.cycle,
        strategy=outcome.selection.strategy.value,
        mutation_description=outcome.proposal.reasoning,
        score_before=outcome.parent.assessment.batch_score,
        score_after=child.assessment.batch_score,
        candidate_id=child.snapshot.candidate_id,
        failure_reason=outcome.decision.reason,
        parent_candidate_id=outcome.parent.snapshot.candidate_id,
        rejected_snapshot=child.snapshot,
        parent_assessment=outcome.parent.assessment,
        child_assessment=child.assessment,
        mutation=outcome.proposal.mutation,
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


def _project_total_evolver_cost(records: Sequence[EvolutionCycleRecord]) -> CostRecord | None:
    """Project exact model usage and known variation cost across completed cycles."""
    if not records:
        return None
    usage = tuple(record.evolver_usage for record in records)
    known_costs = tuple(item.total_cost_usd for item in usage)
    total_cost = sum(known_cost for known_cost in known_costs if known_cost is not None)
    return CostRecord(
        model_calls=sum(item.model_requests for item in usage),
        estimated_cost_usd=total_cost if all(cost is not None for cost in known_costs) else None,
    )


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


def _empty_evaluator(
    _snapshot: WorkspaceSnapshot,
    _batch: CandidateEvaluationBatch,
) -> tuple[TrialRecord, ...]:
    return ()


def _validate_public_evolution_tasks(task_dirs: Sequence[Path], tasks_root: Path) -> None:
    """Reject non-public task definitions before evolution composition starts."""
    for task_dir in task_dirs:
        task = load_task_definition(task_dir, tasks_root)
        if task.visibility is not Visibility.PUBLIC:
            raise ValueError(
                f"evolution task {task.task_id!r} has visibility {task.visibility.value!r}; "
                "only PUBLIC tasks are permitted"
            )


def _timestamp_slug() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")


def _build_harbor_candidate_runtime(
    *,
    config: EvolutionConfig,
    task_dirs: Sequence[Path],
    experiment_id: str,
) -> CandidateChecks:
    """Build one Harbor capability without candidate-specific planning."""
    from aec_bench.evolution.backends.local import build_local_checks

    planner = build_local_checks(
        task_dirs=task_dirs,
        model=config.solver.model if config.solver else config.models.evolver,
        experiment_id=experiment_id,
        adapter=config.solver.adapter if config.solver else "rlm",
        timeout=config.timeout,
        backend=config.backend,
        agent_config=config.solver,
    ).plan
    return CandidateChecks(
        plan=planner,
        run=_build_harbor_candidate_evaluator(config=config, experiment_id=experiment_id),
    )


def _build_harbor_candidate_evaluator(
    *, config: EvolutionConfig, experiment_id: str
) -> Callable[[WorkspaceSnapshot, CandidateEvaluationBatch], tuple[TrialRecord, ...]]:
    """Compose remote candidate evaluation from a preplanned batch."""
    from aec_bench.contracts.experiment_manifest import ComputeConfig, ExperimentManifest, TaskSelector
    from aec_bench.contracts.run_plan import SingleAttemptRecipe
    from aec_bench.evolution.snapshot import serialise_snapshot
    from aec_bench.harness.artifact_tasks import run_experiment
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
                recipe=SingleAttemptRecipe(),
            )
        )

    return evaluate


__all__ = (
    "ReportWriter",
    "run_evolution",
    "run_evolution_from_config",
)
