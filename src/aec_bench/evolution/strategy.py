# ABOUTME: Selection strategy protocol and hill-climb implementation for evolution.
# ABOUTME: Defines the interface that the evolution application uses for parent selection.

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from aec_bench.contracts.evolution import (
    EvolutionCycleRecord,
    GateDecision,
    WorkspaceSnapshot,
)
from aec_bench.evolution.archive_agent import SelectionResult
from aec_bench.evolution.core import CycleOutcome
from aec_bench.evolution.graveyard import MutationGraveyard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class SelectionStrategy(Protocol):
    """Interface for evolution parent-selection strategies.

    The evolution loop calls on_cycle_end after each cycle to feed results,
    then select_parent before the next mutation to choose the starting point.
    """

    def on_cycle_end(
        self,
        *,
        cycle_record: EvolutionCycleRecord,
        snapshot: WorkspaceSnapshot,
        step_result_gate: GateDecision,
        score_history: list[float],
        graveyard: MutationGraveyard,
        **kwargs: Any,
    ) -> None: ...

    def select_parent(self, current_score: float) -> SelectionResult | None: ...

    def get_snapshot(self, candidate_id: str) -> WorkspaceSnapshot | None: ...

    def save(self, workspace_root: Path) -> None: ...

    def summary(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Hill-climb strategy
# ---------------------------------------------------------------------------


class HillClimbStrategy:
    """Provide snapshot lookup for hill climb while state owns selection."""

    def __init__(self) -> None:
        self._snapshots: dict[str, WorkspaceSnapshot] = {}

    # -- lifecycle -----------------------------------------------------------

    def on_cycle_end(
        self,
        *,
        cycle_record: EvolutionCycleRecord,
        snapshot: WorkspaceSnapshot,
        step_result_gate: GateDecision,
        score_history: list[float],
        graveyard: MutationGraveyard,
        **kwargs: Any,
    ) -> None:
        """Update best-so-far if the cycle improved on the previous best."""
        outcome = kwargs.get("outcome")
        if isinstance(outcome, CycleOutcome):
            self._snapshots[outcome.parent.snapshot.candidate_id] = outcome.parent.snapshot
            if outcome.child is not None:
                self._snapshots[outcome.child.snapshot.candidate_id] = outcome.child.snapshot
        else:
            self._snapshots[snapshot.candidate_id] = snapshot

    # -- selection -----------------------------------------------------------

    def select_parent(self, current_score: float) -> SelectionResult | None:
        """Return no selection; the application state is the authority."""
        return None

    # -- snapshot access -----------------------------------------------------

    def get_snapshot(self, candidate_id: str) -> WorkspaceSnapshot | None:
        """Return the stored snapshot if its candidate ID matches."""
        return self._snapshots.get(candidate_id)

    # -- persistence ---------------------------------------------------------

    def save(self, workspace_root: Path) -> None:
        """No-op — hill-climb has no persistent state beyond the workspace."""

    # -- introspection -------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a summary dict describing current strategy state."""
        result: dict[str, Any] = {"mode": "hill_climb"}
        return result


# ---------------------------------------------------------------------------
# QD strategy (MAP-Elites archive + bandit selection)
# ---------------------------------------------------------------------------


class QDStrategy:
    """MAP-Elites archive with UCB1 selection and archive explorer agent.

    Wraps QDArchive (CVT-MAP-Elites), CellSelector (UCB1 bandit over cells),
    and StrategyBandit (D-MAB over mutation strategies). The evolution loop
    delegates parent selection to this strategy, which uses an archive-explorer
    agent to choose among UCB1-shortlisted candidates.
    """

    def __init__(
        self,
        *,
        evolver_model: str,
        n_centroids: int = 200,
        seed: int = 42,
    ) -> None:
        from aec_bench.evolution.archive import QDArchive
        from aec_bench.evolution.selection import CellSelector, StrategyBandit

        self._archive = QDArchive(n_centroids=n_centroids, seed=seed)
        self._cell_selector = CellSelector()
        self._strategy_bandit = StrategyBandit()
        self._evolver_model = evolver_model
        self._n_centroids = n_centroids

    # -- properties ----------------------------------------------------------

    @property
    def archive_size(self) -> int:
        """Number of occupied cells in the archive."""
        return self._archive.size

    @property
    def n_centroids(self) -> int:
        """Total number of Voronoi centroids in the archive."""
        return self._n_centroids

    # -- lifecycle -----------------------------------------------------------

    def on_cycle_end(
        self,
        *,
        cycle_record: EvolutionCycleRecord,
        snapshot: WorkspaceSnapshot,
        step_result_gate: GateDecision,
        score_history: list[float],
        graveyard: MutationGraveyard,
        **kwargs: Any,
    ) -> None:
        """Extract exact outcome observations and insert the active candidate."""
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        outcome = kwargs.get("outcome")
        observations = kwargs.get("observations", [])
        run_id = kwargs.get("run_id", "")

        if isinstance(outcome, CycleOutcome):
            evaluated = outcome.child if outcome.decision.decision is GateDecision.ACCEPTED else outcome.parent
            if evaluated is not None:
                observations = list(evaluated.observations)
                snapshot = evaluated.snapshot

        for obs in observations:
            bd = extract_behaviour_descriptor(obs)
            self._archive.insert(
                bd,
                snapshot,
                task_ids=(obs.trial.task.task_id,),
                discipline=obs.discipline,
                run_id=run_id,
            )

        logger.info(
            "QD archive: size=%d, coverage=%.1f%%",
            self._archive.size,
            self._archive.size / self._n_centroids * 100,
        )

    # -- selection -----------------------------------------------------------

    def select_parent(self, current_score: float) -> SelectionResult | None:
        """Select a parent via UCB1 shortlisting and archive-explorer agent.

        Returns None if the archive has fewer than 2 entries (not enough
        diversity for meaningful selection).
        """
        if self._archive.size < 2:
            return None

        for entry in self._archive.top_k(k=self._archive.size):
            self._cell_selector.register_cell(
                entry.snapshot.candidate_id,
                reward=entry.bd.reward,
                discipline=entry.discipline,
            )
        shortlist = self._cell_selector.select(k=5)

        from aec_bench.evolution.archive_agent import run_archive_selection

        result = run_archive_selection(
            model_name=self._evolver_model,
            archive=self._archive,
            graveyard=MutationGraveyard(),
            shortlist=shortlist,
            current_score=current_score,
        )
        self._cell_selector.record_selection(result.parent_candidate_id)
        return result

    # -- snapshot access -----------------------------------------------------

    def get_snapshot(self, candidate_id: str) -> WorkspaceSnapshot | None:
        """Return a stored snapshot by candidate ID from the archive."""
        entry = self._archive.get_entry_by_candidate_id(candidate_id)
        if entry is not None:
            return entry.snapshot
        return None

    # -- persistence ---------------------------------------------------------

    def save(self, workspace_root: Path) -> None:
        """Persist the archive as archive.json in the workspace root."""
        self._archive.save(workspace_root / "archive.json")

    # -- introspection -------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a summary dict describing current QD strategy state."""
        return {
            "mode": "qd",
            "archive_size": self._archive.size,
            "archive_summary": self._archive.to_summary(),
        }
