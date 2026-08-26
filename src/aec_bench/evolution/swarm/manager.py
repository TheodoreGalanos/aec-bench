# ABOUTME: Core swarm orchestrator — manages agent lifecycle, budget, archive, and events.
# ABOUTME: Runs N agents as concurrent async tasks in a single process.

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from aec_bench.contracts.evolution import (
    AgentStatus,
    ConsolidationReport,
    LineageNarrative,
    LineageRecord,
    MutationStrategy,
    SwarmAgentState,
    SwarmEvent,
    SwarmEventType,
    SwarmNote,
    SwarmResult,
    WorkspaceSnapshot,
)
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.archive import QDArchive
from aec_bench.evolution.behaviour import extract_behaviour_descriptor
from aec_bench.evolution.core import SelectionPlan, VariationStatus, assessment_score
from aec_bench.evolution.evaluation import CandidateBatchPlanner, CandidateEvaluator
from aec_bench.evolution.swarm.agent_task import AgentContext, Evolver, run_agent_loop
from aec_bench.evolution.swarm.budget import BudgetLedger
from aec_bench.evolution.swarm.config import SwarmConfig
from aec_bench.evolution.swarm.core import (
    AgentBudget,
    AgentPivotState,
    BudgetSnapshot,
    PivotState,
    SwarmAgentResult,
    SwarmAssignment,
    SwarmState,
    reduce_swarm_outcome,
)
from aec_bench.evolution.swarm.events import SwarmEventWriter
from aec_bench.evolution.swarm.evolver import SwarmEvolverFactory
from aec_bench.evolution.swarm.lineage import LineageTracker
from aec_bench.evolution.swarm.notes import NoteStore
from aec_bench.evolution.swarm.processing import (
    ObservationEnricher,
    SwarmEvaluation,
    evaluate_swarm_result,
    finalize_swarm_evaluation,
)
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard

logger = logging.getLogger(__name__)


@runtime_checkable
class EvolverFactory(Protocol):
    """Protocol for creating evolver instances — one per agent."""

    def create(
        self,
        agent_id: str,
        model_override: str | None = None,
    ) -> Evolver: ...


AssignmentIdFactory = Callable[[str, int], str]
RunIdFactory = Callable[[], str]
WallClock = Callable[[], datetime]
MonotonicClock = Callable[[], float]


def _default_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _default_assignment_id(agent_id: str, cycle: int) -> str:
    return f"{agent_id}:assignment:{cycle}"


def _trial_cost(record: object) -> float:
    """Read the explicit trial cost projection used for evaluation spend."""
    if not isinstance(record, TrialRecord) or record.cost is None:
        return 0.0
    if record.cost.estimated_cost_usd is not None:
        return float(record.cost.estimated_cost_usd)
    return 0.0


class SwarmManager:
    """Orchestrates a multi-agent swarm run.

    Responsibilities:
    - Creates shared infrastructure (budget, archive, graveyard, lineage, events)
    - Spawns N agent coroutines via ``asyncio.gather``
    - Provides callbacks that update shared state under a lock
    - Emits lifecycle events to the JSONL log
    - Collects agent states into a ``SwarmResult``
    """

    def __init__(
        self,
        config: SwarmConfig,
        state_dir: Path,
        evolver_factory: EvolverFactory,
        *,
        batch_planner: CandidateBatchPlanner | None = None,
        evaluator: CandidateEvaluator | None = None,
        enricher: ObservationEnricher | None = None,
        run_id: str | None = None,
        run_id_factory: RunIdFactory | None = None,
        wall_clock: WallClock | None = None,
        monotonic_clock: MonotonicClock | None = None,
        assignment_id_factory: AssignmentIdFactory | None = None,
        initial_snapshot: WorkspaceSnapshot | None = None,
    ) -> None:
        self._config = config
        self._state_dir = state_dir
        self._factory = evolver_factory
        if run_id is not None and run_id_factory is not None:
            raise ValueError("provide run_id or run_id_factory, not both")
        self._run_id = run_id or (run_id_factory or _default_run_id)()
        self._wall_clock = wall_clock or (lambda: datetime.now(tz=UTC))
        self._monotonic_clock = monotonic_clock or time.monotonic
        self._assignment_id_factory = assignment_id_factory or _default_assignment_id
        self._initial_snapshot = initial_snapshot
        if isinstance(evolver_factory, SwarmEvolverFactory):
            batch_planner = batch_planner or evolver_factory.plan_batch
            evaluator = evaluator or evolver_factory.evaluate
            enricher = enricher or evolver_factory.enrich
        if batch_planner is None or evaluator is None or enricher is None:
            raise ValueError("host batch_planner, evaluator, and enricher are required")
        self._batch_planner = batch_planner
        self._evaluator = evaluator
        self._enricher = enricher

        # Shared infrastructure
        self._budget = BudgetLedger(
            max_cost_usd=config.budget.max_cost_usd,
            eval_budget_usd=config.budget.eval_budget_usd,
            wind_down_threshold=config.budget.wind_down_threshold,
            final_threshold=config.budget.final_threshold,
        )
        self._archive = QDArchive(n_centroids=config.archive.n_centroids)
        self._graveyard = SharedGraveyard()
        self._lineage = LineageTracker()
        self._notes = NoteStore()
        self._event_writer = SwarmEventWriter(state_dir / "events.jsonl")

        # Protects shared state mutations from concurrent agent tasks
        self._lock = asyncio.Lock()
        self._start_time: float = 0.0
        self._agent_cycles: dict[str, int] = {}
        self._agent_consecutive_errors: dict[str, int] = {}
        self._agent_nudges: dict[str, str | None] = {}
        self._candidate_snapshots: dict[str, WorkspaceSnapshot] = {}
        self._initial_candidate_id: str | None = None
        self._state = SwarmState(
            run_id=self._run_id,
            total_evaluations=0,
            best_candidate_id=None,
            best_score=None,
            agent_states=(),
            recent_scores=(),
            recent_descriptors=(),
            pivot_state=PivotState(),
            stopped=False,
            stop_reason=None,
        )
        self._latest_report: ConsolidationReport | None = None

    def _print_event(self, message: str) -> None:
        """Print a key event line to stderr (above the status line)."""
        elapsed = self._monotonic_clock() - self._start_time
        mins, secs = divmod(int(elapsed), 60)
        import sys

        print(f"  [{mins:02d}:{secs:02d}] {message}", file=sys.stderr, flush=True)

    def _print_status(self, agent_id: str, score: float) -> None:
        """Print a compact status line to stderr after each eval."""
        report = self._archive.coverage_report()
        cov_pct = int(report.get("coverage", 0) * 100)
        occupied = report.get("occupied", 0)
        total = report.get("total_centroids", 0)
        bud_pct = int(self._budget.spend_percentage * 100)
        import sys

        print(
            f"  evals: {self._state.total_evaluations} "
            f"| archive: {cov_pct}% ({occupied}/{total}) "
            f"| best: {self._state.best_score or 0.0:.2f} "
            f"| budget: {bud_pct}% "
            f"| {agent_id} → {score:.2f}",
            file=sys.stderr,
            flush=True,
        )

    def _emit(
        self,
        event_type: SwarmEventType,
        agent_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        """Emit a SwarmEvent to the JSONL log."""
        event = SwarmEvent(
            event_type=event_type,
            occurred_at=self._wall_clock().isoformat(),
            agent_id=agent_id,
            payload=payload or {},
        )
        self._event_writer.emit(event)

    async def _on_result(self, assignment: SwarmAssignment, result: SwarmAgentResult) -> bool:
        """Evaluate and reduce one typed result; model work stays outside the lock."""
        if result.variation.status is VariationStatus.SUBMITTED:
            batch = self._batch_planner(self._config.evolution.batch_size, self._agent_cycles[assignment.agent_id] - 1)
            evaluated = evaluate_swarm_result(
                assignment=assignment,
                agent_result=result,
                batch=batch,
                evaluate=self._evaluator,
                enrich=self._enricher,
                run_id=self._run_id,
                cycle=self._agent_cycles[assignment.agent_id],
                now=self._wall_clock(),
            )
        else:
            evaluated = SwarmEvaluation(assignment, result, parent=None, child=None)

        async with self._lock:
            current_parent = self._candidate_snapshots.get(assignment.parent.candidate_id)
            if current_parent != assignment.parent:
                raise ValueError(f"assignment parent {assignment.parent.candidate_id!r} is no longer available")
            outcome = finalize_swarm_evaluation(
                evaluated=evaluated,
                archive=self._archive,
                graveyard=self._graveyard,
                run_id=self._run_id,
                cycle=self._agent_cycles[assignment.agent_id],
                now=self._wall_clock(),
            )
            if outcome.evaluated_candidate is not None:
                child = outcome.evaluated_candidate
                self._candidate_snapshots[child.snapshot.candidate_id] = child.snapshot
                self._budget.record_eval_spend(sum(_trial_cost(obs.trial) for obs in child.observations))
            self._budget.record_agent_spend(assignment.agent_id, result.agent_cost_usd)
            self._agent_consecutive_errors[assignment.agent_id] = 0
            budget = BudgetSnapshot(
                self._budget.max_cost_usd,
                self._budget.total_agent_spend,
                self._budget.eval_budget_usd,
                self._budget.eval_spend,
            )
            self._state, decision = reduce_swarm_outcome(
                state=self._state, outcome=outcome, budget=budget, config=self._config, now=self._wall_clock()
            )
            score = (
                assessment_score(
                    outcome.evaluated_candidate.assessment,
                    structural_weight=self._config.evolution.structural_weight,
                )
                if outcome.evaluated_candidate is not None
                else None
            )
            inserted = outcome.archive_outcome.added if outcome.archive_outcome is not None else False
            candidate_id = outcome.evaluated_candidate.snapshot.candidate_id if outcome.evaluated_candidate else None
            self._emit(
                SwarmEventType.EVAL_COMPLETED,
                assignment.agent_id,
                {
                    "assignment_id": assignment.assignment_id,
                    "candidate_id": candidate_id,
                    "agent_cost_usd": result.agent_cost_usd,
                    "inserted": inserted,
                    "budget_phase": self._budget.phase,
                    "score": score,
                },
            )
            if decision.pivot is not None:
                self._emit(
                    SwarmEventType.AGENT_PIVOTING,
                    assignment.agent_id,
                    {"reason": decision.pivot.reason},
                )
            if inserted and outcome.evaluated_candidate is not None:
                child = outcome.evaluated_candidate
                descriptor = extract_behaviour_descriptor(child.observations[0])
                self._emit(
                    SwarmEventType.ARCHIVE_UPDATED,
                    assignment.agent_id,
                    {"candidate_id": candidate_id, "score": score or 0.0},
                )
                parent_entry = self._archive.get_entry_by_candidate_id(assignment.parent.candidate_id)
                self._lineage.record(
                    LineageRecord(
                        entry_candidate_id=child.snapshot.candidate_id,
                        parent_candidate_id=assignment.parent.candidate_id,
                        source_agent_id=assignment.agent_id,
                        mutation_type="evolution_cycle",
                        bd_region_targeted=descriptor,
                        surprise=parent_entry is not None and self._lineage.is_surprise(parent_entry.bd, descriptor),
                        recorded_at=self._wall_clock().isoformat(),
                    )
                )
                self._lineage.attach_narrative(
                    LineageNarrative(
                        entry_candidate_id=child.snapshot.candidate_id,
                        agent_reasoning=result.variation.reasoning,
                        investigation_context=f"Assignment {assignment.assignment_id}.",
                    )
                )
                self._emit(SwarmEventType.LINEAGE_RECORDED, assignment.agent_id, {"candidate_id": candidate_id})
            if (
                outcome.evaluated_candidate is not None
                and self._config.heartbeat.reflect_every > 0
                and self._state.total_evaluations % self._config.heartbeat.reflect_every == 0
            ):
                note = SwarmNote(
                    note_id=f"{assignment.agent_id}-reflect-{self._state.total_evaluations}",
                    agent_id=assignment.agent_id,
                    authored_at=self._wall_clock().isoformat(),
                    bd_region=extract_behaviour_descriptor(outcome.evaluated_candidate.observations[0]),
                    title=f"Eval {self._state.total_evaluations} reflection",
                    content=f"Host evaluation recorded for candidate {candidate_id}.",
                    tags=("reflect",),
                )
                self._notes.insert(note)
                self._emit(
                    SwarmEventType.NOTE_WRITTEN,
                    assignment.agent_id,
                    {"note_id": note.note_id, "title": note.title},
                )
            if decision.consolidate:
                from aec_bench.evolution.swarm.analyst import produce_consolidation_report

                self._latest_report = produce_consolidation_report(
                    archive=self._archive,
                    graveyard=self._graveyard,
                    lineage=self._lineage,
                    notes=self._notes,
                    total_evals=self._state.total_evaluations,
                )
                self._emit(
                    SwarmEventType.CONSOLIDATION_PRODUCED,
                    payload={"report_id": self._latest_report.report_id},
                )
            self._save_state()
            if decision.stop:
                self._emit(SwarmEventType.AGENT_RETIRED, assignment.agent_id, {"reason": decision.reason})
            return decision.continue_agent

    async def _on_error(self, agent_id: str, exc: Exception) -> bool:
        """Callback invoked when an agent step raises an exception.

        Implements restart with exponential backoff. After max_restarts
        consecutive failures, the agent is retired. A successful eval
        between errors resets the counter.
        """
        async with self._lock:
            consecutive = self._agent_consecutive_errors.get(agent_id, 0) + 1
            self._agent_consecutive_errors[agent_id] = consecutive

            if consecutive > self._config.agents.max_restarts:
                self._emit(
                    SwarmEventType.AGENT_RETIRED,
                    agent_id=agent_id,
                    payload={"reason": "max_restarts_exceeded", "error": str(exc), "consecutive_errors": consecutive},
                )
                self._print_event(f"{agent_id} RETIRED — {consecutive} consecutive errors")
                return False

            # Exponential backoff: 0s, 30s, 60s
            backoff_seconds = 0 if consecutive == 1 else 30 * (consecutive - 1)
            self._emit(
                SwarmEventType.AGENT_RESTARTED,
                agent_id=agent_id,
                payload={"error": str(exc), "consecutive_errors": consecutive, "backoff_seconds": backoff_seconds},
            )
            self._print_event(
                f"{agent_id} error #{consecutive}/{self._config.agents.max_restarts} — restarting in {backoff_seconds}s"
            )

        if backoff_seconds > 0:
            await asyncio.sleep(backoff_seconds)

        return True

    def _resolve_agent_nudge(self, agent_index: int) -> str | None:
        """Resolve the nudge hint for a specific agent.

        Returns nudge text when specialisation is 'nudged' and a nudge is
        configured for this agent index. Returns None otherwise.
        """
        if self._config.agents.specialisation != "nudged":
            return None
        nudges = self._config.agents.nudges
        if nudges and agent_index < len(nudges):
            return nudges[agent_index]
        return None

    def _resolve_agent_model(self, agent_index: int) -> str:
        """Resolve the model for a specific agent.

        Uses per-agent override from config.agents.models if available,
        otherwise falls back to config.agents.default_model.
        """
        models = self._config.agents.models
        if models and agent_index < len(models):
            return models[agent_index]
        return self._config.agents.default_model

    async def _next_assignment(self, agent_id: str) -> SwarmAssignment:
        """Create an assignment from exact candidate sources under the lock."""
        async with self._lock:
            cycle = self._agent_cycles.get(agent_id, 0) + 1
            self._agent_cycles[agent_id] = cycle
            parent_id = self._state.best_candidate_id or self._initial_candidate_id
            if parent_id is None:
                raise ValueError("an exact initial candidate has not been registered")
            parent = self._candidate_snapshots.get(parent_id)
            if parent is None:
                raise ValueError(f"selected candidate {parent_id!r} has no available snapshot")
            inspiration_ids = tuple(
                entry.snapshot.candidate_id
                for entry in self._archive.view().top_k(5)
                if entry.snapshot.candidate_id != parent_id
            )
            unresolved = [
                candidate_id for candidate_id in inspiration_ids if candidate_id not in self._candidate_snapshots
            ]
            if unresolved:
                raise ValueError(f"inspiration candidates have no available snapshots: {unresolved}")
            inspirations = tuple(self._candidate_snapshots[candidate_id] for candidate_id in inspiration_ids)
            selection = SelectionPlan(
                parent_candidate_id=parent_id,
                inspiration_candidate_ids=tuple(snapshot.candidate_id for snapshot in inspirations),
                strategy=MutationStrategy.CONSERVATIVE,
                goal="Improve the selected candidate against the configured evaluation batch.",
                reasoning=f"Manager selected exact candidate source {parent_id}.",
            )
            return SwarmAssignment(
                assignment_id=self._assignment_id_factory(agent_id, cycle),
                agent_id=agent_id,
                selection=selection,
                parent=parent,
                inspirations=inspirations,
                budget=AgentBudget(
                    max_cost_usd=max(0.0, min(self._budget.remaining, self._budget.eval_budget_remaining))
                ),
                issued_at=self._wall_clock(),
            )

    def _build_agent_context(self, agent_id: str, agent_index: int) -> AgentContext:
        """Build an agent context with explicit assignment and result callbacks."""
        model = self._resolve_agent_model(agent_index)
        nudge = self._resolve_agent_nudge(agent_index)
        self._agent_nudges[agent_id] = nudge
        # Create evolver with per-agent model override if configured
        model_override = model if model != self._config.agents.default_model else None
        evolver = self._factory.create(agent_id, model_override=model_override)
        return AgentContext(
            agent_id=agent_id,
            evolver=evolver,
            next_assignment=lambda: self._next_assignment(agent_id),
            on_eval_complete=self._on_result,
            on_error=lambda exc: self._on_error(agent_id, exc),
            model=model,
            worktree_branch=f"coral/{agent_id}",
        )

    def _set_initial_agent_states(self, contexts: Sequence[AgentContext]) -> None:
        """Install the immutable initial pool state before agents start."""
        self._state = SwarmState(
            run_id=self._state.run_id,
            total_evaluations=self._state.total_evaluations,
            best_candidate_id=self._state.best_candidate_id,
            best_score=self._state.best_score,
            agent_states=tuple(
                SwarmAgentState(
                    agent_id=context.agent_id,
                    model=context.model or "unknown",
                    status=AgentStatus.ACTIVE,
                    worktree_branch=context.worktree_branch,
                )
                for context in contexts
            ),
            recent_scores=self._state.recent_scores,
            recent_descriptors=self._state.recent_descriptors,
            pivot_state=PivotState(tuple(AgentPivotState(context.agent_id) for context in contexts)),
            stopped=self._state.stopped,
            stop_reason=self._state.stop_reason,
        )

    def _save_state(self) -> None:
        """Persist all shared state to state_dir after each eval."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._archive.save(self._state_dir / "archive.json")
        self._graveyard.save(self._state_dir / "graveyard.json")
        self._lineage.save(self._state_dir / "lineage.json")
        self._notes.save(self._state_dir / "notes.json")
        (self._state_dir / "budget.json").write_text(
            json.dumps(
                {"agent_spend": dict(self._budget.agent_spend), "eval_spend": self._budget.eval_spend},
                indent=2,
            ),
            encoding="utf-8",
        )
        state_payload = {
            "run_id": self._state.run_id,
            "total_evaluations": self._state.total_evaluations,
            "best_candidate_id": self._state.best_candidate_id,
            "best_score": self._state.best_score,
            "agent_states": [agent.model_dump(mode="json") for agent in self._state.agent_states],
            "recent_scores": self._state.recent_scores,
            "recent_descriptors": [descriptor.model_dump(mode="json") for descriptor in self._state.recent_descriptors],
            "pivot_state": {"agent_states": [pivot.__dict__ for pivot in self._state.pivot_state.agent_states]},
            "stopped": self._state.stopped,
            "stop_reason": self._state.stop_reason,
        }
        (self._state_dir / "swarm_state.json").write_text(json.dumps(state_payload, indent=2), encoding="utf-8")
        # Persist latest consolidation report if available
        if self._latest_report is not None:
            report_path = self._state_dir / "consolidation.json"
            report_path.write_text(
                json.dumps(self._latest_report.model_dump(), indent=2),
                encoding="utf-8",
            )

    def _save_run_summary(self, result: SwarmResult) -> None:
        """Write a human-readable JSON summary after run completion."""
        import json

        summary = {
            "run_id": result.run_id,
            "workspace": result.workspace_name,
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "model": a.model,
                    "status": a.status,
                    "eval_count": a.eval_count,
                    "best_score": a.best_score,
                    "budget_consumed_usd": self._budget.agent_spend.get(a.agent_id, 0.0),
                }
                for a in result.agents
            ],
            "archive": result.archive_summary,
            "budget": {
                "max_cost_usd": self._budget.max_cost_usd,
                "total_spent_usd": result.total_cost_usd,
                "eval_spent_usd": result.eval_cost_usd,
                "final_phase": self._budget.phase,
            },
            "totals": {
                "evals": result.total_evals,
                "best_score": result.best_score,
                "best_candidate_id": result.best_candidate_id,
                "elapsed_seconds": result.elapsed_seconds,
                "lineage_records": result.lineage_record_count,
                "events": result.event_count,
                "consolidation_reports": 1 if self._latest_report else 0,
                "notes": self._notes.size,
            },
        }
        path = self._state_dir / "summary.json"
        path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        logger.info("Run summary saved to %s", path)

    async def run(self) -> SwarmResult:
        """Execute the swarm run — spawn agents, wait for completion, collect results."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._start_time = self._monotonic_clock()
        agent_count = self._config.agents.count

        logger.info("Starting swarm run %s with %d agents", self._run_id, agent_count)
        self._emit(
            SwarmEventType.SWARM_STARTED,
            payload={
                "run_id": self._run_id,
                "agent_count": agent_count,
                "max_cost_usd": self._config.budget.max_cost_usd,
            },
        )

        # Register exact source material before issuing any assignment.
        baseline = self._initial_snapshot
        if baseline is None and isinstance(self._factory, SwarmEvolverFactory):
            baseline = self._factory.baseline_snapshot()
        if baseline is None:
            raise ValueError("an exact initial_snapshot is required for swarm assignments")
        self._candidate_snapshots[baseline.candidate_id] = baseline
        self._initial_candidate_id = baseline.candidate_id

        # Build agent contexts and emit spawn events
        contexts: list[AgentContext] = []
        for i in range(agent_count):
            agent_id = f"agent-{i}"
            ctx = self._build_agent_context(agent_id, agent_index=i)
            contexts.append(ctx)
            self._emit(
                SwarmEventType.AGENT_SPAWNED,
                agent_id=agent_id,
                payload={"model": ctx.model, "nudge": self._agent_nudges.get(agent_id, "")},
            )

        self._set_initial_agent_states(contexts)
        # Run all agents concurrently. The explicit SwarmState is authoritative.
        statuses: list[AgentStatus] = await asyncio.gather(*(run_agent_loop(ctx) for ctx in contexts))

        elapsed = self._monotonic_clock() - self._start_time
        self._state = SwarmState(
            run_id=self._state.run_id,
            total_evaluations=self._state.total_evaluations,
            best_candidate_id=self._state.best_candidate_id,
            best_score=self._state.best_score,
            agent_states=tuple(
                agent.model_copy(update={"status": statuses[index]})
                for index, agent in enumerate(self._state.agent_states)
            ),
            recent_scores=self._state.recent_scores,
            recent_descriptors=self._state.recent_descriptors,
            pivot_state=self._state.pivot_state,
            stopped=self._state.stopped,
            stop_reason=self._state.stop_reason,
        )

        # Persist shared state
        self._save_state()

        best_candidate_id = self._state.best_candidate_id or "none"

        # Emit completion event with rich summary
        archive_summary = self._archive.to_summary()
        self._emit(
            SwarmEventType.SWARM_COMPLETED,
            payload={
                "run_id": self._run_id,
                "total_evals": self._state.total_evaluations,
                "total_cost_usd": self._budget.total_agent_spend,
                "best_score": self._state.best_score or 0.0,
                "best_candidate_id": best_candidate_id,
                "elapsed_seconds": elapsed,
                "archive_size": archive_summary.get("size", 0),
                "archive_coverage": archive_summary.get("coverage", 0.0),
                "lineage_records": self._lineage.size,
                "notes": self._notes.size,
                "budget_phase": self._budget.phase,
            },
        )

        result = SwarmResult(
            run_id=self._run_id,
            workspace_name=self._config.task.workspace,
            agents=list(self._state.agent_states),
            archive_summary=archive_summary,
            total_evals=self._state.total_evaluations,
            total_cost_usd=self._budget.total_agent_spend,
            eval_cost_usd=self._budget.eval_spend,
            elapsed_seconds=elapsed,
            best_score=self._state.best_score or 0.0,
            best_candidate_id=best_candidate_id,
            converged=False,
            lineage_record_count=self._lineage.size,
            event_count=self._event_writer.next_sequence,
        )

        # Write human-readable run summary
        self._save_run_summary(result)

        return result
