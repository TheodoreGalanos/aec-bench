# ABOUTME: Outer-loop orchestrator for the evolution framework.
# ABOUTME: Coordinates solve → enrich → evolve → repeat until convergence or max cycles.

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

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
from aec_bench.evolution.strategy import HillClimbStrategy, SelectionStrategy
from aec_bench.evolution.workspace import Workspace

logger = logging.getLogger(__name__)

# Callable type: takes a workspace snapshot and a batch size, returns trial records.
SolveFn = Callable[[WorkspaceSnapshot, int], list[TrialRecord]]


class EvolutionOrchestrator:
    """Outer loop that coordinates solve → enrich → evolve → repeat.

    The orchestrator delegates the solve step to an injected callable so the
    execution backend (local, Modal, Harbor) is decoupled from the loop logic.
    Convergence is detected when scores stagnate across a rolling window.
    """

    def __init__(
        self,
        *,
        workspace: Workspace,
        engine: AECEvolutionEngine,
        solve_fn: SolveFn,
        config: EvolutionConfig,
        strategy: SelectionStrategy | None = None,
    ) -> None:
        self._workspace = workspace
        self._engine = engine
        self._solve_fn = solve_fn
        self._config = config
        self._strategy = strategy or HillClimbStrategy()

    def run(self) -> EvolutionResult:
        """Run the evolution loop and return the aggregated result."""
        history: list[EvolutionCycleRecord] = []
        score_history: list[float] = []

        # Generate a unique run ID so tags don't clobber across runs.
        # Format: YYYYMMDD-HHMM (compact, human-readable, sortable)
        run_id = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M")
        self._engine.set_run_id(run_id)
        self._engine.set_strategy_name(self._strategy.summary().get("mode", ""))
        logger.info("Evolution run ID: %s", run_id)

        from aec_bench.evolution.graveyard import MutationGraveyard

        graveyard = MutationGraveyard.load(self._workspace.root / "graveyard.json")

        # Selection from the previous cycle — applied at the start of the next.
        # This ensures observations match the workspace state (solve happens
        # AFTER the parent is applied, not before).
        pending_selection: SelectionResult | None = None

        for cycle in range(self._config.max_cycles):
            current_version = f"evo-{run_id}-{cycle}"

            # 0. Apply selected parent from previous cycle (if any)
            if pending_selection is not None:
                parent_snapshot = self._strategy.get_snapshot(
                    pending_selection.parent_version,
                )
                if parent_snapshot is not None:
                    self._workspace.apply_snapshot(parent_snapshot)
                    logger.info(
                        "Applied parent: %s",
                        pending_selection.parent_version,
                    )

            # 1. Export current workspace snapshot
            snapshot = self._workspace.export_snapshot(workspace_version=current_version)

            # 2. Solve: run a batch of tasks via the injected backend
            trial_records = self._solve_fn(snapshot, self._config.batch_size)

            # 3. Enrich: wrap trial records as EvolutionObservations
            observations = self._build_observations(trial_records, current_version)

            # Use the pending selection as the current cycle's selection context
            selection = pending_selection
            pending_selection = None

            # 4. Evolve: run one engine step
            step_result = self._engine.step(
                self._workspace,
                observations,
                history,
                selection=selection,
                graveyard=graveyard,
            )

            # 4b. Persist per-trial outcomes before cleanup wipes temp dirs.
            enriched_obs = step_result.enriched_observations or observations
            from aec_bench.evolution.trial_persistence import persist_cycle_trials

            persist_cycle_trials(
                workspace_root=self._workspace.root,
                cycle=step_result.cycle_record.cycle,
                run_id=run_id,
                observations=enriched_obs,
            )

            # 4c. Clean up temporary workspaces now that classification is done.
            # The solve_fn may hold temp dirs with artifacts that the engine
            # needed during the classify phase. Safe to remove now.
            if hasattr(self._solve_fn, "cleanup"):
                self._solve_fn.cleanup()

            # 5. Record
            history.append(step_result.cycle_record)
            score_history.append(step_result.cycle_record.batch_score)

            # 5b. Export post-mutation snapshot for strategy
            current_snapshot = self._workspace.export_snapshot(
                workspace_version=step_result.cycle_record.workspace_version_after,
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
                        workspace_version=step_result.cycle_record.workspace_version_after,
                        failure_reason=f"Score delta: {score_delta:+.3f}",
                        field_failures=self._extract_field_failures(observations),
                        mutation_actions=self._extract_mutation_actions(step_result.mutation),
                    )
                )

            # 5d. Delegate to strategy
            self._strategy.on_cycle_end(
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
            mutation_desc = self._describe_mutation(step_result.mutation)

            logger.info(
                "Cycle %d/%d — score=%.2f, gate=%s, mutations=[%s]",
                cycle + 1,
                self._config.max_cycles,
                score_history[-1],
                gate,
                mutation_desc,
            )

            # 6. Select parent for NEXT cycle
            pending_selection = self._strategy.select_parent(score_history[-1])
            if pending_selection is not None:
                logger.info(
                    "Next-cycle selection: parent=%s, strategy=%s",
                    pending_selection.parent_version,
                    pending_selection.strategy,
                )

            # 7. Convergence check
            if self._is_converged(score_history):
                break

        # Persist
        self._write_report()
        self._strategy.save(self._workspace.root)
        graveyard.save(self._workspace.root / "graveyard.json")
        logger.info("Graveyard saved: %d entries", graveyard.size)

        run_id_full = f"evo-{self._workspace.manifest.name}-{_timestamp_slug()}"

        return EvolutionResult(
            run_id=run_id_full,
            workspace_name=self._workspace.manifest.name,
            cycles_completed=len(history),
            final_score=score_history[-1] if score_history else 0.0,
            best_score=max(score_history) if score_history else 0.0,
            best_workspace_version=self._find_best_version(history),
            score_history=score_history,
            converged=self._is_converged(score_history),
            total_trials=sum(len(cr.trial_ids) for cr in history),
            cycle_records=history,
            archive_summary=self._strategy.summary(),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
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

    @staticmethod
    def _extract_mutation_actions(
        mutation: MutationSummary | None,
    ) -> list[dict] | None:
        """Convert a MutationSummary to a list of action dicts for the graveyard."""
        if mutation is None:
            return None
        actions: list[dict] = []
        if mutation.prompt_modified:
            actions.append({"action_type": "modify_prompt"})
        for name in mutation.skills_added:
            actions.append({"action_type": "write_skill", "skill_name": name})
        for name in mutation.skills_modified:
            actions.append({"action_type": "modify_skill", "skill_name": name})
        for name in mutation.skills_removed:
            actions.append({"action_type": "remove_skill", "skill_name": name})
        return actions if actions else None

    @staticmethod
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

    def _write_report(self) -> None:
        """Generate and write the evolution HTML report to the workspace."""
        try:
            from aec_bench.communication.evolution_report import (
                render_evolution_report_html,
            )
            from aec_bench.evolution.report_data import build_evolution_report_data

            data = build_evolution_report_data(self._workspace.root)
            html = render_evolution_report_html(data)
            report_path = self._workspace.root / "evolution-report.html"
            report_path.write_text(html, encoding="utf-8")
            logger.info("Evolution report written to %s", report_path)
        except Exception:
            logger.warning("Failed to generate evolution report", exc_info=True)

    def _build_observations(
        self,
        trial_records: list[TrialRecord],
        workspace_version: str,
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
                workspace_version=workspace_version,
                discipline=discipline,
            )
            observations.append(obs)
        return observations

    def _is_converged(self, score_history: list[float]) -> bool:
        """Return True when scores are flat within the stagnation window.

        Requires at least stagnation_window + 1 entries before evaluating.
        Convergence is declared when every score in the window is within
        improvement_threshold of every other score in the window.
        """
        window = self._config.stagnation_window
        if len(score_history) < window + 1:
            return False
        recent = score_history[-window:]
        return (max(recent) - min(recent)) <= self._config.improvement_threshold

    def _find_best_version(self, history: list[EvolutionCycleRecord]) -> str:
        """Return the workspace_version_after of the cycle with the highest batch_score."""
        if not history:
            return "evo-0"
        best = max(history, key=lambda cr: cr.batch_score)
        return best.workspace_version_after


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
