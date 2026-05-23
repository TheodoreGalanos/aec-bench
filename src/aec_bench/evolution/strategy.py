# ABOUTME: Selection strategy protocol and hill-climb implementation for evolution.
# ABOUTME: Defines the interface that orchestrator delegates to for parent selection.

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
from aec_bench.evolution.graveyard import MutationGraveyard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class SelectionStrategy(Protocol):
    """Interface for evolution parent-selection strategies.

    The orchestrator calls on_cycle_end after each cycle to feed results,
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

    def get_snapshot(self, version: str) -> WorkspaceSnapshot | None: ...

    def save(self, workspace_root: Path) -> None: ...

    def summary(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Hill-climb strategy
# ---------------------------------------------------------------------------


class HillClimbStrategy:
    """Always mutate from the best-scoring workspace seen so far.

    Tracks a single best version/score/snapshot triple. The first cycle
    always becomes the initial best. Subsequent cycles replace best only
    when the batch score strictly improves.
    """

    def __init__(self) -> None:
        self._best_version: str | None = None
        self._best_score: float | None = None
        self._best_snapshot: WorkspaceSnapshot | None = None

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
        score = cycle_record.batch_score
        if self._best_score is None or score > self._best_score:
            self._best_version = cycle_record.workspace_version_after
            self._best_score = score
            self._best_snapshot = snapshot
            logger.debug(
                "hill-climb: new best %s (score=%.4f)",
                self._best_version,
                self._best_score,
            )

    # -- selection -----------------------------------------------------------

    def select_parent(self, current_score: float) -> SelectionResult | None:
        """Return the best workspace as the parent, or None if no cycle has run."""
        if self._best_version is None:
            return None
        return SelectionResult(
            parent_version=self._best_version,
            inspiration_versions=[],
            strategy="conservative",
            reasoning=f"Hill-climb: selecting best-so-far {self._best_version} (score={self._best_score:.4f})",
        )

    # -- snapshot access -----------------------------------------------------

    def get_snapshot(self, version: str) -> WorkspaceSnapshot | None:
        """Return stored snapshot if version matches, otherwise None."""
        if self._best_snapshot is not None and self._best_version == version:
            return self._best_snapshot
        return None

    # -- persistence ---------------------------------------------------------

    def save(self, workspace_root: Path) -> None:
        """No-op — hill-climb has no persistent state beyond the workspace."""

    # -- introspection -------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a summary dict describing current strategy state."""
        result: dict[str, Any] = {"mode": "hill_climb"}
        if self._best_version is not None:
            result["best_version"] = self._best_version
            result["best_score"] = self._best_score
        return result


# ---------------------------------------------------------------------------
# QD strategy (MAP-Elites archive + bandit selection)
# ---------------------------------------------------------------------------


class QDStrategy:
    """MAP-Elites archive with UCB1 selection and archive explorer agent.

    Wraps QDArchive (CVT-MAP-Elites), CellSelector (UCB1 bandit over cells),
    and StrategyBandit (D-MAB over mutation strategies). The orchestrator
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
        """Extract behaviour descriptors from observations and insert into archive."""
        from aec_bench.evolution.behaviour import extract_behaviour_descriptor

        observations = kwargs.get("observations", [])
        run_id = kwargs.get("run_id", "")

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
                entry.snapshot.workspace_version,
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
        self._cell_selector.record_selection(result.parent_version)
        return result

    # -- snapshot access -----------------------------------------------------

    def get_snapshot(self, version: str) -> WorkspaceSnapshot | None:
        """Return stored snapshot by version from the archive, or None."""
        entry = self._archive.get_entry_by_version(version)
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
