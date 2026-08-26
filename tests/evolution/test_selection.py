# ABOUTME: Tests pure UCB1 selection and immutable QD feedback updates.
# ABOUTME: Verifies explore/exploit balance without stateful selector objects.

import random

from aec_bench.contracts.evolution import MutationStrategy
from aec_bench.evolution.selection import (
    CellSelectionStat,
    CellSelectionState,
    StrategyBanditState,
    select_mutation_strategy,
    shortlist_cells,
    update_cell_selection_state,
    update_strategy_bandit_state,
)


def test_shortlist_cells_ranks_unselected_cells_first_and_breaks_ties_by_index() -> None:
    state = CellSelectionState((CellSelectionStat(2, selection_count=2, improvement_count=1),))

    assert shortlist_cells(state, [4, 2, 1], k=3) == (1, 4, 2)


def test_shortlist_cells_uses_seeded_tie_breaking_reproducibly() -> None:
    state = CellSelectionState()

    first = shortlist_cells(state, [1, 2, 3, 4], k=4, seed=17)
    second = shortlist_cells(state, [1, 2, 3, 4], k=4, seed=17)

    assert first == second
    assert set(first) == {1, 2, 3, 4}


def test_update_cell_selection_state_records_one_selection_and_one_improvement() -> None:
    state = CellSelectionState((CellSelectionStat(2, selection_count=3, improvement_count=1),))

    updated = update_cell_selection_state(state, cell_index=2, cycle=8, improved=True)

    assert updated.stats == (CellSelectionStat(2, selection_count=4, improvement_count=2, last_selected_cycle=8),)
    assert state.stats[0].selection_count == 3


def test_select_mutation_strategy_is_reproducible_and_does_not_mutate_rng() -> None:
    state = StrategyBanditState()
    rng = random.Random(23)
    before = rng.getstate()

    first = select_mutation_strategy(state, seed=23)
    second = select_mutation_strategy(state, seed=23)
    with_rng = select_mutation_strategy(state, rng=rng)

    assert first is second
    assert with_rng is first
    assert rng.getstate() == before


def test_select_mutation_strategy_excludes_unavailable_graveyard_rescue() -> None:
    state = StrategyBanditState()

    assert select_mutation_strategy(state, graveyard_available=False) is not MutationStrategy.GRAVEYARD_RESCUE


def test_update_strategy_bandit_state_records_one_attempt_and_one_success() -> None:
    state = StrategyBanditState()

    updated = update_strategy_bandit_state(state, MutationStrategy.EXPLORATORY, success=True)

    assert updated.stats[0].strategy is MutationStrategy.EXPLORATORY
    assert updated.stats[0].attempts == 1
    assert updated.stats[0].successes == 1
    assert state.stats == ()
