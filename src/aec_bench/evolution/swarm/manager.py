# ABOUTME: Core swarm orchestrator — manages agent lifecycle, budget, archive, and events.
# ABOUTME: Runs N agents as concurrent async tasks in a single process.

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from aec_bench.contracts.evolution import (
    BehaviourDescriptor,
    ConsolidationReport,
    LineageNarrative,
    LineageRecord,
    SwarmAgentState,
    SwarmEvent,
    SwarmEventType,
    SwarmNote,
    SwarmResult,
    WorkspaceSnapshot,
)
from aec_bench.evolution.archive import QDArchive
from aec_bench.evolution.swarm.agent_task import AgentContext, run_agent_loop
from aec_bench.evolution.swarm.budget import BudgetLedger
from aec_bench.evolution.swarm.config import SwarmConfig
from aec_bench.evolution.swarm.context import build_archive_context
from aec_bench.evolution.swarm.events import SwarmEventWriter
from aec_bench.evolution.swarm.lineage import LineageTracker
from aec_bench.evolution.swarm.notes import NoteStore
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard

logger = logging.getLogger(__name__)


@runtime_checkable
class EvolverFactory(Protocol):
    """Protocol for creating evolver instances — one per agent."""

    def create(self, agent_id: str) -> Any: ...


def _now_iso() -> str:
    """UTC ISO-8601 timestamp string."""
    return datetime.now(tz=UTC).isoformat()


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
    ) -> None:
        self._config = config
        self._state_dir = state_dir
        self._factory = evolver_factory
        self._run_id = uuid.uuid4().hex[:12]

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

        # Accumulator for the global best score seen across all agents
        self._global_best_score: float = 0.0

        # Per-agent tracking for pivot detection
        self._agent_best_scores: dict[str, float] = {}
        self._agent_non_improving: dict[str, int] = {}
        self._agent_pivot_cooldown: dict[str, int] = {}
        self._pivot_after = config.heartbeat.pivot_after

        # Per-agent score history and BD focus tracking
        self._agent_recent_scores: dict[str, list[float]] = {}
        self._agent_recent_bds: dict[str, list[BehaviourDescriptor]] = {}
        _BD_FOCUS_WINDOW = 5
        self._bd_focus_window = _BD_FOCUS_WINDOW

        # Reflect heartbeat tracking
        self._reflect_every = config.heartbeat.reflect_every
        self._agent_eval_counts: dict[str, int] = {}

        # Per-agent nudge hints (resolved at spawn, stored for context injection)
        self._agent_nudges: dict[str, str | None] = {}

        # Restart with backoff tracking
        self._max_restarts = config.agents.max_restarts
        self._agent_consecutive_errors: dict[str, int] = {}

        # Consolidation heartbeat
        self._consolidate_every = config.heartbeat.consolidate_every
        self._last_consolidation_at: int = 0
        self._latest_report: ConsolidationReport | None = None

        # Live status tracking
        self._total_evals = 0
        self._start_time: float = 0.0
        self._global_best_version: str = ""

    def _print_event(self, message: str) -> None:
        """Print a key event line to stderr (above the status line)."""
        elapsed = time.monotonic() - self._start_time
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
            f"  evals: {self._total_evals} "
            f"| archive: {cov_pct}% ({occupied}/{total}) "
            f"| best: {self._global_best_score:.2f} "
            f"| budget: {bud_pct}% "
            f"| {agent_id} → {score:.2f}",
            file=sys.stderr,
            flush=True,
        )

    def _emit(
        self,
        event_type: SwarmEventType,
        agent_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit a SwarmEvent to the JSONL log."""
        event = SwarmEvent(
            event_type=event_type,
            timestamp=_now_iso(),
            agent_id=agent_id,
            payload=payload or {},
        )
        self._event_writer.emit(event)

    async def _on_eval_complete(self, agent_id: str, result: Any) -> bool:
        """Callback invoked after each successful eval step.

        Updates budget, archive, and emits events.
        Returns False to signal the agent should stop.
        """
        score = getattr(result, "score", 0.0)
        cost = getattr(result, "cost_usd", 0.0)
        version = getattr(result, "workspace_version", "")
        bd: BehaviourDescriptor | None = getattr(result, "bd", None)

        async with self._lock:
            # Record spend and eval count — successful eval resets error streak
            self._budget.record_agent_spend(agent_id, cost)
            self._total_evals += 1
            self._agent_consecutive_errors[agent_id] = 0

            # Track recent scores (for context injection)
            if agent_id not in self._agent_recent_scores:
                self._agent_recent_scores[agent_id] = []
            self._agent_recent_scores[agent_id].append(score)

            # Track recent BDs for dynamic focus derivation (rolling window)
            if bd is not None:
                if agent_id not in self._agent_recent_bds:
                    self._agent_recent_bds[agent_id] = []
                bds = self._agent_recent_bds[agent_id]
                bds.append(bd)
                if len(bds) > self._bd_focus_window:
                    self._agent_recent_bds[agent_id] = bds[-self._bd_focus_window :]

            # Update QD archive — requires a BehaviourDescriptor
            inserted = False
            if bd is not None:
                snapshot = WorkspaceSnapshot(
                    system_prompt="swarm-generated",
                    skills=[],
                    workspace_version=version,
                )
                inserted = self._archive.insert(
                    bd=bd,
                    snapshot=snapshot,
                    run_id=agent_id,
                )

            # Track global best
            if score > self._global_best_score:
                self._global_best_score = score
                self._global_best_version = version

            # Track per-agent improvement for pivot detection
            agent_best = self._agent_best_scores.get(agent_id, 0.0)
            if score > agent_best:
                self._agent_best_scores[agent_id] = score
                self._agent_non_improving[agent_id] = 0
            else:
                self._agent_non_improving[agent_id] = self._agent_non_improving.get(agent_id, 0) + 1

            # Pivot detection — fire when consecutive non-improving exceeds threshold
            cooldown = self._agent_pivot_cooldown.get(agent_id, 0)
            non_improving = self._agent_non_improving.get(agent_id, 0)
            if cooldown > 0:
                self._agent_pivot_cooldown[agent_id] = cooldown - 1
            elif non_improving >= self._pivot_after:
                self._emit(
                    SwarmEventType.AGENT_PIVOTING,
                    agent_id=agent_id,
                    payload={"consecutive_non_improving": non_improving},
                )
                # Cooldown: don't pivot again for 3 evals
                self._agent_pivot_cooldown[agent_id] = 3

            # Emit eval event with rich observability data
            eval_payload: dict[str, Any] = {
                "score": score,
                "cost_usd": cost,
                "version": version,
                "inserted": inserted,
                "agent_best": self._agent_best_scores.get(agent_id, 0.0),
                "non_improving": non_improving,
                "budget_phase": self._budget.phase,
                "budget_pct": round(self._budget.spend_percentage, 3),
            }
            if bd is not None:
                eval_payload["bd"] = {
                    "token_cost": bd.token_cost,
                    "verification_depth": bd.verification_depth,
                    "reward": bd.reward,
                }
            self._emit(
                SwarmEventType.EVAL_COMPLETED,
                agent_id=agent_id,
                payload=eval_payload,
            )

            if inserted:
                self._emit(
                    SwarmEventType.ARCHIVE_UPDATED,
                    agent_id=agent_id,
                    payload={"version": version, "score": score},
                )

                # Record lineage with parent provenance and surprise detection
                parent_version = getattr(result, "parent_version", "") or None
                is_surprise = False
                if parent_version and bd is not None:
                    parent_entry = self._archive.get_entry_by_version(parent_version)
                    if parent_entry is not None:
                        is_surprise = self._lineage.is_surprise(parent_entry.bd, bd)

                lineage_record = LineageRecord(
                    entry_version=version,
                    parent_version=parent_version,
                    source_agent_id=agent_id,
                    cross_agent=False,
                    cross_agent_source=None,
                    mutation_type="evolution_cycle",
                    bd_region_targeted=bd,
                    surprise=is_surprise,
                    timestamp=_now_iso(),
                )
                self._lineage.record(lineage_record)

                # Attach freeform narrative with structured reasoning context
                narrative = LineageNarrative(
                    entry_version=version,
                    agent_reasoning=(
                        f"Score {score:.2f} achieved via evolution_cycle. "
                        f"Agent {agent_id} eval #{self._agent_eval_counts.get(agent_id, 0) + 1}."
                    ),
                    investigation_context=(
                        f"Budget spent: ${self._budget.total_agent_spend:.2f}/"
                        f"${self._budget.max_cost_usd:.2f}. "
                        f"Archive coverage: {self._archive.coverage_report().get('coverage', 0):.0%}."
                    ),
                )
                self._lineage.attach_narrative(narrative)

                self._emit(
                    SwarmEventType.LINEAGE_RECORDED,
                    agent_id=agent_id,
                    payload={"version": version},
                )

            # Reflect heartbeat — create a structured note from eval data
            agent_evals = self._agent_eval_counts.get(agent_id, 0) + 1
            self._agent_eval_counts[agent_id] = agent_evals
            if self._reflect_every > 0 and agent_evals % self._reflect_every == 0:
                gate = "accepted" if inserted else "no change"
                note_content = f"Eval {agent_evals}: score {score:.2f} ({gate}). Cost ${cost:.2f}. Version {version}."
                if non_improving > 0:
                    note_content += f" Non-improving streak: {non_improving}."

                note = SwarmNote(
                    note_id=f"{agent_id}-reflect-{agent_evals}",
                    agent_id=agent_id,
                    timestamp=_now_iso(),
                    bd_region=bd,
                    title=f"Eval {agent_evals} reflection",
                    content=note_content,
                    tags=("reflect",),
                )
                self._notes.insert(note)
                self._emit(
                    SwarmEventType.NOTE_WRITTEN,
                    agent_id=agent_id,
                    payload={"note_id": note.note_id, "title": note.title},
                )

            # Consolidation heartbeat — run analyst every N global evals
            if (
                self._consolidate_every > 0
                and self._total_evals - self._last_consolidation_at >= self._consolidate_every
            ):
                from aec_bench.evolution.swarm.analyst import produce_consolidation_report

                self._latest_report = produce_consolidation_report(
                    archive=self._archive,
                    graveyard=self._graveyard,
                    lineage=self._lineage,
                    notes=self._notes,
                    total_evals=self._total_evals,
                )
                self._last_consolidation_at = self._total_evals
                self._emit(
                    SwarmEventType.CONSOLIDATION_PRODUCED,
                    payload={
                        "report_id": self._latest_report.report_id,
                        "coverage_pct": self._latest_report.archive_coverage_pct,
                        "patterns": len(self._latest_report.cross_agent_patterns),
                        "recommendations": len(self._latest_report.strategy_recommendations),
                    },
                )
                self._print_event(
                    f"Consolidation: {self._latest_report.archive_coverage_pct:.0f}% coverage, "
                    f"{len(self._latest_report.cross_agent_patterns)} patterns, "
                    f"{len(self._latest_report.strategy_recommendations)} recommendations"
                )

            # Print live status to terminal
            if inserted:
                self._print_event(f"{agent_id} new archive entry: {score:.2f} ({version})")
            if non_improving >= self._pivot_after and cooldown <= 0:
                self._print_event(f"{agent_id} PIVOTING — {non_improving} non-improving evals")
            self._print_status(agent_id, score)

            # Save shared state after every eval — cycles take minutes,
            # writing a few JSON files is negligible and prevents data loss.
            self._save_state()

            # Check budget — return False to stop the agent
            if self._budget.phase == "exhausted":
                logger.info("Budget exhausted — retiring agent %s", agent_id)
                self._emit(
                    SwarmEventType.AGENT_RETIRED,
                    agent_id=agent_id,
                    payload={"reason": "budget_exhausted"},
                )
                return False

            return True

    async def _on_error(self, agent_id: str, exc: Exception) -> bool:
        """Callback invoked when an agent step raises an exception.

        Implements restart with exponential backoff. After max_restarts
        consecutive failures, the agent is retired. A successful eval
        between errors resets the counter.
        """
        async with self._lock:
            consecutive = self._agent_consecutive_errors.get(agent_id, 0) + 1
            self._agent_consecutive_errors[agent_id] = consecutive

            if consecutive > self._max_restarts:
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
                f"{agent_id} error #{consecutive}/{self._max_restarts} — restarting in {backoff_seconds}s"
            )

        if backoff_seconds > 0:
            await asyncio.sleep(backoff_seconds)

        return True

    def _compute_bd_focus(self, agent_id: str) -> BehaviourDescriptor | None:
        """Compute the agent's current BD focus from its recent evaluations.

        Returns the centroid (mean) of the last N BDs, or None if no BDs tracked yet.
        """
        bds = self._agent_recent_bds.get(agent_id, [])
        if not bds:
            return None
        n = len(bds)
        return BehaviourDescriptor(
            token_cost=sum(b.token_cost for b in bds) / n,
            verification_depth=sum(b.verification_depth for b in bds) / n,
            tool_density=sum(b.tool_density for b in bds) / n,
            exploration_ratio=sum(b.exploration_ratio for b in bds) / n,
            deliberation_ratio=sum(b.deliberation_ratio for b in bds) / n,
            reward=sum(b.reward for b in bds) / n,
        )

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

    def _build_context_provider(self, agent_id: str):
        """Create a context provider callback for an agent.

        Returns a callable that builds the archive context string from
        current shared state. Called by the evolver before each engine step.
        """

        def _provide_context() -> str:
            nudge = self._agent_nudges.get(agent_id)
            non_improving = self._agent_non_improving.get(agent_id, 0)
            pivoting = non_improving >= self._pivot_after and self._agent_pivot_cooldown.get(agent_id, 0) <= 0
            best = self._agent_best_scores.get(agent_id, 0.0)
            evals = self._agent_eval_counts.get(agent_id, 0)

            bd_focus = self._compute_bd_focus(agent_id)
            recent_scores = self._agent_recent_scores.get(agent_id, [])

            context = build_archive_context(
                archive=self._archive,
                graveyard=self._graveyard,
                agent_id=agent_id,
                agent_bd_focus=bd_focus,
                generation=evals,
                agent_recent_scores=recent_scores,
                agent_best_score=best,
                pivoting=pivoting,
                consecutive_non_improving=non_improving,
                notes=self._notes,
                nudge=nudge,
                consolidation_report=self._latest_report,
            )

            # Wind-down notification (I4)
            phase = self._budget.phase
            if phase == "winding_down":
                remaining = self._budget.remaining
                context += (
                    f"\n### Budget Warning\n\n"
                    f"Budget is running low (${remaining:.2f} remaining). "
                    f"Make your remaining evaluations count — focus on the most "
                    f"promising approaches.\n"
                )
            elif phase == "final":
                context += (
                    "\n### Budget Critical\n\n"
                    "Almost no budget remaining. This may be your last evaluation. "
                    "Make it count.\n"
                )

            return context

        return _provide_context

    def _build_agent_context(self, agent_id: str, agent_index: int) -> AgentContext:
        """Build an AgentContext for a single agent."""
        model = self._resolve_agent_model(agent_index)
        nudge = self._resolve_agent_nudge(agent_index)
        self._agent_nudges[agent_id] = nudge
        # Create evolver with per-agent model override if configured
        model_override = model if model != self._config.agents.default_model else None
        evolver = self._factory.create(agent_id, model_override=model_override)
        # Inject shared swarm state via the proper setter
        if hasattr(evolver, "set_shared_state"):
            evolver.set_shared_state(
                graveyard=self._graveyard,
                context_provider=self._build_context_provider(agent_id),
            )
        return AgentContext(
            agent_id=agent_id,
            evolver=evolver,
            on_eval_complete=lambda result: self._on_eval_complete(agent_id, result),
            on_error=lambda exc: self._on_error(agent_id, exc),
            model=model,
            worktree_branch=f"coral/{agent_id}",
        )

    def _save_state(self) -> None:
        """Persist all shared state to state_dir after each eval."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._archive.save(self._state_dir / "archive.json")
        self._graveyard.save(self._state_dir / "graveyard.json")
        self._lineage.save(self._state_dir / "lineage.json")
        self._notes.save(self._state_dir / "notes.json")
        # Persist latest consolidation report if available
        if self._latest_report is not None:
            import json

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
                "best_version": result.best_workspace_version,
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
        self._start_time = time.monotonic()
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

        # Run all agents concurrently
        agent_states: list[SwarmAgentState] = await asyncio.gather(*(run_agent_loop(ctx) for ctx in contexts))

        elapsed = time.monotonic() - self._start_time
        total_evals = sum(s.eval_count for s in agent_states)

        # Persist shared state
        self._save_state()

        # Default best_workspace_version if no archive insertions occurred
        best_version = self._global_best_version or "none"

        # Emit completion event with rich summary
        archive_summary = self._archive.to_summary()
        self._emit(
            SwarmEventType.SWARM_COMPLETED,
            payload={
                "run_id": self._run_id,
                "total_evals": total_evals,
                "total_cost_usd": self._budget.total_agent_spend,
                "best_score": self._global_best_score,
                "best_version": best_version,
                "elapsed_seconds": elapsed,
                "archive_size": archive_summary.get("size", 0),
                "archive_coverage": archive_summary.get("coverage", 0.0),
                "lineage_records": len(self._lineage.all_records()),
                "notes": self._notes.size,
                "budget_phase": self._budget.phase,
            },
        )

        result = SwarmResult(
            run_id=self._run_id,
            workspace_name=self._config.task.workspace,
            agents=agent_states,
            archive_summary=archive_summary,
            total_evals=total_evals,
            total_cost_usd=self._budget.total_agent_spend,
            eval_cost_usd=self._budget.eval_spend,
            elapsed_seconds=elapsed,
            best_score=self._global_best_score,
            best_workspace_version=best_version,
            converged=False,
            lineage_record_count=len(self._lineage.all_records()),
            event_count=self._event_writer.next_sequence,
        )

        # Write human-readable run summary
        self._save_run_summary(result)

        return result
