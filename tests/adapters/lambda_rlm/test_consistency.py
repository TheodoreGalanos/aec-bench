# ABOUTME: Tests for lambda-rlm self-consistency helpers.
# ABOUTME: Validates normalization, vote-merge, and deterministic consistency aggregation.

import pytest

from aec_bench.adapters.lambda_rlm.consistency import (
    aggregate_consistency,
    normalise_value,
    vote_merge,
)


def test_normalise_value_string_strips_lowercases_and_collapses_whitespace() -> None:
    assert normalise_value("  Four   Tanks ") == "four tanks"


def test_normalise_value_list_sorts_recursively() -> None:
    assert normalise_value([3, 1, 2]) == (1, 2, 3)


def test_normalise_value_numeric_identity() -> None:
    assert normalise_value(4) == 4


def test_vote_merge_exact_match() -> None:
    consensus, per_field = vote_merge(
        [{"tank_count": 4}, {"tank_count": 4}, {"tank_count": 4}],
    )

    assert consensus == {"tank_count": 4}
    assert per_field == {"tank_count": 1.0}


def test_vote_merge_disagreement() -> None:
    consensus, per_field = vote_merge(
        [{"tank_count": 4}, {"tank_count": 4}, {"tank_count": 3}],
    )

    assert consensus == {"tank_count": 4}
    assert per_field["tank_count"] == pytest.approx(2 / 3)


def test_vote_merge_filters_singleton_keys() -> None:
    consensus, per_field = vote_merge(
        [{"x": 1}, {"y": 2}, {"x": 1}],
    )

    assert consensus == {"x": 1}
    assert per_field == {"x": pytest.approx(2 / 3)}


def test_vote_merge_list_order_normalised() -> None:
    consensus, per_field = vote_merge(
        [
            {"items": [1, 2, 3]},
            {"items": [3, 2, 1]},
            {"items": [1, 2, 3]},
        ],
    )

    assert consensus == {"items": [1, 2, 3]}
    assert per_field == {"items": 1.0}


def test_vote_merge_tie_breaks_by_first_candidate() -> None:
    consensus, per_field = vote_merge(
        [{"status": "pass"}, {"status": "fail"}],
    )

    assert consensus == {"status": "pass"}
    assert per_field == {"status": 0.5}


def test_aggregate_consistency_is_mean() -> None:
    assert aggregate_consistency({"x": 1.0, "y": 0.5, "z": 0.75}) == pytest.approx(0.75)


def test_aggregate_consistency_empty_is_zero() -> None:
    assert aggregate_consistency({}) == 0.0
