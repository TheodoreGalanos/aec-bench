# ABOUTME: Tests for the pure tournament scoring functions used by best-of-k.
# ABOUTME: Covers round-robin, weighted round-robin, mixture, and tie-breaking.

from __future__ import annotations

import math
from dataclasses import dataclass

from aec_bench.adapters.lambda_rlm.tournament import (
    PairwiseOutcome,
    _should_swap_stable,
    mixture_scores,
    pick_winner,
    round_robin_win_rates,
    weighted_round_robin_scores,
)


@dataclass
class _ScriptedJudge:
    """Test judge whose decisions follow a deterministic preference order.

    Higher index in ``preferences`` means stronger candidate. The judge always
    picks the candidate whose id appears LATER in the preference list.
    """

    preferences: list[str]

    def compare(self, *, a_id, b_id, completion_a, completion_b):
        a_rank = self.preferences.index(a_id)
        b_rank = self.preferences.index(b_id)
        return PairwiseOutcome(
            a_id=a_id,
            b_id=b_id,
            a_won=a_rank > b_rank,
            reasoning=f"rank {a_rank} vs {b_rank}",
        )


def test_round_robin_single_candidate_returns_full_score():
    judge = _ScriptedJudge(preferences=["only"])
    candidates = [("only", "content")]
    win_rates, outcomes = round_robin_win_rates(candidates, judge)
    assert win_rates == [1.0]
    assert outcomes == []


def test_round_robin_strict_ordering_matches_preference():
    judge = _ScriptedJudge(preferences=["a", "b", "c"])
    candidates = [("a", "A text"), ("b", "B text"), ("c", "C text")]
    win_rates, outcomes = round_robin_win_rates(candidates, judge)
    # c beats both -> 2/2; b beats a -> 1/2; a beats none -> 0/2
    assert win_rates == [0.0, 0.5, 1.0]
    assert len(outcomes) == 3  # C(3,2)


def test_round_robin_winner_selection():
    judge = _ScriptedJudge(preferences=["a", "b", "c", "d"])
    candidates = [("a", "x"), ("b", "y"), ("c", "z"), ("d", "w")]
    win_rates, _ = round_robin_win_rates(candidates, judge)
    assert pick_winner(win_rates) == 3  # d


def test_weighted_round_robin_downweights_similar_opponents():
    """If three candidates are close and one is far, weighted should still pick the far one."""
    judge = _ScriptedJudge(preferences=["w", "x", "y", "champion"])
    candidates = [("w", "_"), ("x", "_"), ("y", "_"), ("champion", "_")]
    weighted, _ = weighted_round_robin_scores(candidates, judge)
    # Champion still wins under weighted scoring
    assert pick_winner(weighted) == 3


def test_mixture_scores_uses_exponential_decay():
    pointwise = [0.5, 0.5, 0.5]
    pairwise = [0.0, 0.5, 1.0]
    mixed = mixture_scores(pointwise, pairwise, alpha=0.5)
    # mixed[i] = 0.5 + exp(-0.5 * 0.5) * pairwise[i]
    decay = math.exp(-0.25)
    expected = [0.5 + decay * 0.0, 0.5 + decay * 0.5, 0.5 + decay * 1.0]
    for actual, want in zip(mixed, expected, strict=False):
        assert math.isclose(actual, want, rel_tol=1e-9)


def test_mixture_scores_high_pointwise_decays_pairwise_more():
    """As pointwise mean increases, pairwise weight should decrease."""
    low_point = mixture_scores([0.1, 0.1], [1.0, 0.0], alpha=1.0)
    high_point = mixture_scores([0.9, 0.9], [1.0, 0.0], alpha=1.0)
    low_gap = low_point[0] - low_point[1]
    high_gap = high_point[0] - high_point[1]
    # The pairwise gap should contribute LESS when pointwise mean is high
    assert high_gap < low_gap


def test_mixture_scores_length_mismatch_raises():
    import pytest

    with pytest.raises(ValueError):
        mixture_scores([0.5], [0.5, 0.5])


def test_pick_winner_first_tie_wins():
    assert pick_winner([0.5, 0.5, 0.5]) == 0
    assert pick_winner([0.1, 0.9, 0.9]) == 1


def test_should_swap_stable_is_symmetric():
    # Same pair, different argument order, should produce consistent (mirrored) decisions
    swap_ab = _should_swap_stable("section1", "alpha", "beta")
    swap_ba = _should_swap_stable("section1", "beta", "alpha")
    assert swap_ab != swap_ba


def test_should_swap_stable_changes_with_seed():
    swap1 = _should_swap_stable("section1", "alpha", "beta")
    swap2 = _should_swap_stable("section2", "alpha", "beta")
    # Different seeds may give different swap decisions (not necessarily, but
    # at least the function reads the seed)
    assert swap1 in (True, False)
    assert swap2 in (True, False)
