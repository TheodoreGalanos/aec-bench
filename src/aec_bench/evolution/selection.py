# ABOUTME: Bandit-based cell selection and mutation strategy allocation for QD evolution.
# ABOUTME: UCB1 selects parent cells; D-MAB allocates mutation strategies.

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _CellStats:
    """Per-cell selection statistics for the UCB1 bandit."""

    reward: float
    discipline: str
    n_selected: int = field(default=0)
    n_improved: int = field(default=0)


class CellSelector:
    """UCB1 bandit over archive cells for parent selection.

    Balances exploitation (cells with a good improvement rate) against
    exploration (cells rarely tried). Never-selected cells are given infinite
    UCB score so they are always preferred over cells with selection history.
    """

    def __init__(self, exploration_constant: float = 1.41) -> None:
        self._c = exploration_constant
        self._cells: dict[str, _CellStats] = {}

    def register_cell(self, cell_id: str, reward: float, discipline: str = "") -> None:
        """Register or update a cell in the selector.

        If the cell already exists its reward and discipline are updated while
        selection and improvement counts are preserved.
        """
        if cell_id in self._cells:
            existing = self._cells[cell_id]
            self._cells[cell_id] = _CellStats(
                reward=reward,
                discipline=discipline,
                n_selected=existing.n_selected,
                n_improved=existing.n_improved,
            )
        else:
            self._cells[cell_id] = _CellStats(reward=reward, discipline=discipline)

    def record_selection(self, cell_id: str) -> None:
        """Record that a cell was selected as a parent."""
        if cell_id in self._cells:
            self._cells[cell_id].n_selected += 1

    def record_improvement(self, cell_id: str) -> None:
        """Record that a mutation from this cell improved the archive."""
        if cell_id in self._cells:
            self._cells[cell_id].n_improved += 1

    def cell_stats(self, cell_id: str) -> dict[str, int | float]:
        """Return stats for a cell."""
        stats = self._cells[cell_id]
        return {
            "reward": stats.reward,
            "discipline": stats.discipline,
            "n_selected": stats.n_selected,
            "n_improved": stats.n_improved,
        }

    def select(self, k: int = 5, discipline: str | None = None) -> list[str]:
        """Return top-k cells by UCB1 score.

        UCB1 = success_rate + c * sqrt(ln(N) / n_i)

        where success_rate is n_improved / n_selected, N is the total number of
        selections across all cells, and n_i is the selection count for cell i.

        Never-selected cells get infinite UCB score (exploration priority).
        An optional discipline filter restricts the candidate pool.
        """
        candidates = {
            cell_id: stats
            for cell_id, stats in self._cells.items()
            if discipline is None or stats.discipline == discipline
        }
        if not candidates:
            return []

        total_selections = sum(s.n_selected for s in candidates.values())

        def _ucb1_score(stats: _CellStats) -> float:
            if stats.n_selected == 0:
                return math.inf
            success_rate = stats.n_improved / stats.n_selected
            if total_selections <= 0:
                return success_rate
            exploration = self._c * math.sqrt(math.log(total_selections) / stats.n_selected)
            return success_rate + exploration

        ranked = sorted(
            candidates.keys(),
            key=lambda cid: _ucb1_score(candidates[cid]),
            reverse=True,
        )
        return ranked[:k]


class StrategyBandit:
    """Dynamic Multi-Armed Bandit over mutation strategies.

    Uses a sliding window of recent outcomes per strategy. UCB1 over the
    windowed success rate balances trying all strategies against focusing
    on what works.
    """

    def __init__(
        self,
        strategies: tuple[str, ...] = (
            "conservative",
            "exploratory",
            "crossover",
            "graveyard_rescue",
        ),
        window_size: int = 20,
        exploration_constant: float = 1.41,
    ) -> None:
        self._strategies = strategies
        self._c = exploration_constant
        self._windows: dict[str, deque[int]] = {s: deque(maxlen=window_size) for s in strategies}

    @property
    def strategies(self) -> tuple[str, ...]:
        """The tuple of strategy names."""
        return self._strategies

    def select(self, graveyard_available: bool = True) -> str:
        """Return the strategy with the highest UCB1 score.

        UCB1 = success_rate + c * sqrt(ln(N) / n_i)

        where success_rate is windowed successes / windowed trials, N is total
        windowed trials across eligible strategies, and n_i is trials for
        strategy i. Never-tried strategies get infinite UCB score.

        Excludes graveyard_rescue when graveyard_available is False.
        """
        eligible = [s for s in self._strategies if graveyard_available or s != "graveyard_rescue"]

        total_trials = sum(len(self._windows[s]) for s in eligible)

        def _ucb1_score(strategy: str) -> float:
            window = self._windows[strategy]
            n_i = len(window)
            if n_i == 0:
                return math.inf
            success_rate = sum(window) / n_i
            if total_trials <= 0:
                return success_rate
            exploration = self._c * math.sqrt(math.log(total_trials) / n_i)
            return success_rate + exploration

        return max(eligible, key=_ucb1_score)

    def record(self, strategy: str, success: bool) -> None:
        """Append a success (1) or failure (0) outcome to the strategy's window."""
        self._windows[strategy].append(1 if success else 0)

    def strategy_stats(self, strategy: str) -> dict[str, int | float]:
        """Return windowed stats for a strategy."""
        window = self._windows[strategy]
        window_trials = len(window)
        window_successes = sum(window)
        success_rate = window_successes / window_trials if window_trials > 0 else 0.0
        return {
            "window_trials": window_trials,
            "window_successes": window_successes,
            "success_rate": success_rate,
        }
