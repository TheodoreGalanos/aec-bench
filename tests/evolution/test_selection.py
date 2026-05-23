# ABOUTME: Tests for UCB1 cell selection and D-MAB strategy bandit.
# ABOUTME: Verifies explore/exploit balance and reward updates.

from aec_bench.evolution.selection import CellSelector, StrategyBandit


class TestCellSelector:
    def test_select_from_empty_returns_empty(self) -> None:
        selector = CellSelector()
        result = selector.select(k=5)
        assert result == []

    def test_register_and_select(self) -> None:
        selector = CellSelector()
        selector.register_cell("a", reward=0.8)
        selector.register_cell("b", reward=0.6)
        selector.register_cell("c", reward=0.4)

        result = selector.select(k=2)
        assert len(result) == 2
        assert all(cell_id in ("a", "b", "c") for cell_id in result)
        # No duplicates
        assert len(set(result)) == 2

    def test_unexplored_cells_preferred(self) -> None:
        """Never-selected cells get infinite UCB score and are preferred over explored cells."""
        selector = CellSelector()
        selector.register_cell("explored", reward=0.9)
        selector.register_cell("unexplored", reward=0.1)

        # Select 'explored' 20 times so it has a high n_selected count
        for _ in range(20):
            selector.record_selection("explored")

        # Now the unexplored cell should win due to infinite UCB bonus
        result = selector.select(k=1)
        assert result == ["unexplored"]

    def test_record_improvement_updates_stats(self) -> None:
        selector = CellSelector()
        selector.register_cell("x", reward=0.7)

        selector.record_selection("x")
        selector.record_selection("x")
        selector.record_improvement("x")

        stats = selector.cell_stats("x")
        assert stats["n_selected"] == 2
        assert stats["n_improved"] == 1

    def test_select_k_larger_than_archive(self) -> None:
        selector = CellSelector()
        selector.register_cell("only_one", reward=0.5)

        result = selector.select(k=10)
        assert len(result) == 1
        assert result[0] == "only_one"

    def test_select_respects_discipline_filter(self) -> None:
        selector = CellSelector()
        selector.register_cell("elec_1", reward=0.8, discipline="electrical")
        selector.register_cell("elec_2", reward=0.7, discipline="electrical")
        selector.register_cell("civil_1", reward=0.9, discipline="civil")

        result = selector.select(k=5, discipline="electrical")
        assert len(result) == 2
        assert all(cell_id in ("elec_1", "elec_2") for cell_id in result)
        assert "civil_1" not in result

    def test_cell_stats_returns_initial_zeros(self) -> None:
        selector = CellSelector()
        selector.register_cell("z", reward=0.5)
        stats = selector.cell_stats("z")
        assert stats["n_selected"] == 0
        assert stats["n_improved"] == 0
        assert stats["reward"] == 0.5
        assert stats["discipline"] == ""

    def test_register_cell_updates_existing(self) -> None:
        """Re-registering a cell updates its reward and discipline."""
        selector = CellSelector()
        selector.register_cell("q", reward=0.3, discipline="structural")
        selector.register_cell("q", reward=0.9, discipline="mechanical")

        stats = selector.cell_stats("q")
        assert stats["reward"] == 0.9
        assert stats["discipline"] == "mechanical"
        # Selection counts are preserved on update
        assert stats["n_selected"] == 0

    def test_discipline_filter_no_match_returns_empty(self) -> None:
        selector = CellSelector()
        selector.register_cell("a", reward=0.5, discipline="electrical")

        result = selector.select(k=5, discipline="civil")
        assert result == []

    def test_ucb1_prefers_high_success_rate(self) -> None:
        """After many trials, the cell with a higher success rate should rank higher."""
        selector = CellSelector(exploration_constant=0.01)  # Minimal exploration bonus
        selector.register_cell("good", reward=0.8)
        selector.register_cell("bad", reward=0.2)

        # Give both cells selection history so no infinite UCB ties
        for _ in range(100):
            selector.record_selection("good")
        for _ in range(1):
            selector.record_improvement("good")

        for _ in range(100):
            selector.record_selection("bad")
        # No improvements for 'bad'

        result = selector.select(k=1)
        assert result == ["good"]


class TestStrategyBandit:
    def test_available_strategies(self) -> None:
        bandit = StrategyBandit()
        assert set(bandit.strategies) == {
            "conservative",
            "exploratory",
            "crossover",
            "graveyard_rescue",
        }

    def test_select_strategy_returns_valid(self) -> None:
        bandit = StrategyBandit()
        strategy = bandit.select()
        assert strategy in bandit.strategies

    def test_unexplored_strategies_preferred(self) -> None:
        bandit = StrategyBandit()
        for _ in range(20):
            bandit.record("conservative", success=False)
        strategy = bandit.select()
        assert strategy != "conservative"

    def test_successful_strategy_preferred_after_exploration(self) -> None:
        # Use minimal exploration constant so success rate dominates UCB score.
        bandit = StrategyBandit(exploration_constant=0.01)
        for s in bandit.strategies:
            bandit.record(s, success=False)
        for _ in range(10):
            bandit.record("conservative", success=True)
        strategy = bandit.select()
        assert strategy == "conservative"

    def test_record_updates_window(self) -> None:
        bandit = StrategyBandit(window_size=5)
        for _ in range(10):
            bandit.record("conservative", success=True)
        stats = bandit.strategy_stats("conservative")
        assert stats["window_trials"] == 5
        assert stats["window_successes"] == 5

    def test_graveyard_rescue_excluded_when_no_graveyard(self) -> None:
        bandit = StrategyBandit()
        strategy = bandit.select(graveyard_available=False)
        assert strategy != "graveyard_rescue"
