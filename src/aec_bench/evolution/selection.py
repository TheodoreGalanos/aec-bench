# ABOUTME: Bandit-based cell selection and mutation strategy allocation for QD evolution.
# ABOUTME: UCB1 selects parent cells; D-MAB allocates mutation strategies.

from __future__ import annotations

import math
import random
from collections.abc import Iterable
from dataclasses import dataclass

from aec_bench.contracts.evolution import MutationStrategy
from aec_bench.evolution.core import SelectionPlan


def _require_non_negative(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


@dataclass(frozen=True)
class CellSelectionStat:
    """Outcome-relevant selection statistics for one archive cell."""

    cell_index: int
    selection_count: int = 0
    improvement_count: int = 0
    last_selected_cycle: int | None = None

    def __post_init__(self) -> None:
        _require_non_negative(self.cell_index, "cell_index")
        _require_non_negative(self.selection_count, "selection_count")
        _require_non_negative(self.improvement_count, "improvement_count")
        if self.improvement_count > self.selection_count:
            raise ValueError("improvement_count cannot exceed selection_count")
        if self.last_selected_cycle is not None:
            _require_non_negative(self.last_selected_cycle, "last_selected_cycle")


@dataclass(frozen=True)
class CellSelectionState:
    """Immutable state for cell selection feedback."""

    stats: tuple[CellSelectionStat, ...] = ()

    def __post_init__(self) -> None:
        stats = tuple(self.stats)
        if len({stat.cell_index for stat in stats}) != len(stats):
            raise ValueError("cell selection stats must have unique cell indices")
        object.__setattr__(self, "stats", stats)


@dataclass(frozen=True)
class StrategyBanditStat:
    """Attempt and successful archive-outcome counts for one strategy."""

    strategy: MutationStrategy
    attempts: int = 0
    successes: int = 0

    def __post_init__(self) -> None:
        try:
            strategy = MutationStrategy(self.strategy)
        except ValueError as exc:
            raise ValueError(f"unsupported mutation strategy: {self.strategy!r}") from exc
        object.__setattr__(self, "strategy", strategy)
        _require_non_negative(self.attempts, "attempts")
        _require_non_negative(self.successes, "successes")
        if self.successes > self.attempts:
            raise ValueError("successes cannot exceed attempts")


@dataclass(frozen=True)
class StrategyBanditState:
    """Immutable state for mutation-strategy bandit feedback."""

    stats: tuple[StrategyBanditStat, ...] = ()

    def __post_init__(self) -> None:
        stats = tuple(self.stats)
        if len({stat.strategy for stat in stats}) != len(stats):
            raise ValueError("strategy bandit stats must have unique strategies")
        object.__setattr__(self, "stats", stats)


@dataclass(frozen=True)
class QDState:
    """Explicit quality-diversity search state for one evolution run."""

    cell_selection: CellSelectionState
    strategy_bandit: StrategyBanditState
    last_selection: SelectionPlan | None
    cycle: int

    def __post_init__(self) -> None:
        if isinstance(self.cycle, bool) or not isinstance(self.cycle, int) or self.cycle < 0:
            raise ValueError("QD cycle must be a non-negative integer")


def _validate_exploration_constant(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
        raise ValueError("exploration_constant must be a finite non-negative number")
    return float(value)


def _validate_randomness(seed: int | None, rng: random.Random | None) -> None:
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
        raise ValueError("seed must be a non-negative integer or None")
    if rng is not None and not isinstance(rng, random.Random):
        raise TypeError("rng must be an instance of random.Random or None")
    if seed is not None and rng is not None:
        raise ValueError("provide seed or rng, not both")


def _cell_index(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("cell_index must be a non-negative integer")
    return value


def _tie_break_order(
    values: Iterable[int | MutationStrategy],
    seed: int | None,
    rng: random.Random | None,
) -> dict[int | MutationStrategy, int]:
    """Return a stable rank for equal scores without mutating a caller's RNG."""
    ordered = list(values)
    if seed is None and rng is None:
        return {value: rank for rank, value in enumerate(ordered)}
    tie_rng = random.Random(seed)
    if rng is not None:
        tie_rng.setstate(rng.getstate())
    tie_rng.shuffle(ordered)
    return {value: rank for rank, value in enumerate(ordered)}


def _cell_stats_by_index(state: CellSelectionState) -> dict[int, CellSelectionStat]:
    return {stat.cell_index: stat for stat in state.stats}


def shortlist_cells(
    state: CellSelectionState,
    cell_indices: Iterable[int],
    k: int = 5,
    *,
    exploration_constant: float = 1.41,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> tuple[int, ...]:
    """Return up to ``k`` eligible cell indices ranked by deterministic UCB1.

    Cell occupancy is an input to this pure function. A cell not yet present in
    ``state`` has no selection history and receives exploration priority. The
    optional seed or random generator is explicit to keep callers from using
    global randomness. Without it, ties use ascending cell index. With it,
    ties use a reproducible local random order.
    """
    _validate_randomness(seed, rng)
    exploration_constant = _validate_exploration_constant(exploration_constant)
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        raise ValueError("k must be a non-negative integer")
    eligible = tuple(sorted({_cell_index(value) for value in cell_indices}))
    if not eligible or k == 0:
        return ()

    stats_by_index = _cell_stats_by_index(state)
    total_selections = sum(stats_by_index.get(index, CellSelectionStat(index)).selection_count for index in eligible)

    def score(index: int) -> float:
        stat = stats_by_index.get(index, CellSelectionStat(index))
        if stat.selection_count == 0:
            return math.inf
        success_rate = stat.improvement_count / stat.selection_count
        if total_selections == 0:
            return success_rate
        return success_rate + exploration_constant * math.sqrt(math.log(total_selections) / stat.selection_count)

    tie_order = _tie_break_order(eligible, seed, rng)
    ranked = sorted(eligible, key=lambda index: (-score(index), tie_order[index]))
    return tuple(ranked[:k])


def update_cell_selection_state(
    state: CellSelectionState,
    cell_index: int,
    cycle: int,
    improved: bool = False,
) -> CellSelectionState:
    """Record one accepted parent selection and at most one improvement.

    The update is pure: it returns a new state and does not mutate ``state``.
    ``improved`` is the already-derived archive outcome for this cycle; callers
    must not call this function once per descriptor when a child occupies more
    than one cell.
    """
    cell_index = _cell_index(cell_index)
    _require_non_negative(cycle, "cycle")
    if not isinstance(improved, bool):
        raise TypeError("improved must be a boolean")

    stats = list(state.stats)
    for position, stat in enumerate(stats):
        if stat.cell_index == cell_index:
            stats[position] = CellSelectionStat(
                cell_index=cell_index,
                selection_count=stat.selection_count + 1,
                improvement_count=stat.improvement_count + int(improved),
                last_selected_cycle=cycle,
            )
            return CellSelectionState(tuple(stats))

    stats.append(
        CellSelectionStat(
            cell_index=cell_index,
            selection_count=1,
            improvement_count=int(improved),
            last_selected_cycle=cycle,
        )
    )
    return CellSelectionState(tuple(stats))


def _strategy_stats_by_strategy(state: StrategyBanditState) -> dict[MutationStrategy, StrategyBanditStat]:
    return {stat.strategy: stat for stat in state.stats}


def select_mutation_strategy(
    state: StrategyBanditState,
    graveyard_available: bool = True,
    *,
    exploration_constant: float = 1.41,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> MutationStrategy:
    """Select one host-owned mutation intent from immutable bandit state.

    UCB1 balances the observed success rate and exploration of untried
    strategies. Without a seed or generator, ties use the declaration order of
    ``MutationStrategy``. With one, ties use a reproducible local random order.
    The model or archive agent cannot influence this result.
    """
    _validate_randomness(seed, rng)
    exploration_constant = _validate_exploration_constant(exploration_constant)
    if not isinstance(graveyard_available, bool):
        raise TypeError("graveyard_available must be a boolean")

    eligible = tuple(
        strategy
        for strategy in MutationStrategy
        if graveyard_available or strategy is not MutationStrategy.GRAVEYARD_RESCUE
    )
    stats_by_strategy = _strategy_stats_by_strategy(state)
    total_attempts = sum(
        stats_by_strategy.get(strategy, StrategyBanditStat(strategy)).attempts for strategy in eligible
    )

    def score(strategy: MutationStrategy) -> float:
        stat = stats_by_strategy.get(strategy, StrategyBanditStat(strategy))
        if stat.attempts == 0:
            return math.inf
        success_rate = stat.successes / stat.attempts
        if total_attempts == 0:
            return success_rate
        return success_rate + exploration_constant * math.sqrt(math.log(total_attempts) / stat.attempts)

    tie_order = _tie_break_order(eligible, seed, rng)
    return max(eligible, key=lambda strategy: (score(strategy), -tie_order[strategy]))


def update_strategy_bandit_state(
    state: StrategyBanditState,
    strategy: MutationStrategy,
    success: bool,
) -> StrategyBanditState:
    """Record one strategy attempt and, at most, one successful archive outcome."""
    try:
        strategy = MutationStrategy(strategy)
    except ValueError as exc:
        raise ValueError(f"unsupported mutation strategy: {strategy!r}") from exc
    if not isinstance(success, bool):
        raise TypeError("success must be a boolean")

    stats = list(state.stats)
    for position, stat in enumerate(stats):
        if stat.strategy is strategy:
            stats[position] = StrategyBanditStat(
                strategy=strategy,
                attempts=stat.attempts + 1,
                successes=stat.successes + int(success),
            )
            return StrategyBanditState(tuple(stats))

    stats.append(StrategyBanditStat(strategy=strategy, attempts=1, successes=int(success)))
    return StrategyBanditState(tuple(stats))
