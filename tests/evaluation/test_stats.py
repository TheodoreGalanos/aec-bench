# ABOUTME: Tests reusable statistical primitives for the evaluation domain.
# ABOUTME: Covers deterministic fixtures and Hypothesis-backed invariants.

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from aec_bench.evaluation.stats import cohen_kappa, mean, wilson_confidence_interval


def test_mean_returns_zero_for_empty_or_all_none_inputs() -> None:
    assert mean([]) == pytest.approx(0.0)
    assert mean([None, None]) == pytest.approx(0.0)


def test_cohen_kappa_matches_expected_fixture_cases() -> None:
    assert cohen_kappa(["pass", "pass", "fail"], ["pass", "pass", "fail"]) == pytest.approx(1.0)
    assert cohen_kappa(
        ["pass", "pass", "fail", "fail"],
        ["fail", "fail", "pass", "pass"],
    ) == pytest.approx(-1.0)


def test_wilson_confidence_interval_handles_degenerate_counts() -> None:
    assert wilson_confidence_interval(successes=0, trials=0) == pytest.approx((0.0, 0.0))
    lower, upper = wilson_confidence_interval(successes=7, trials=10)
    assert 0.0 <= lower <= upper <= 1.0
    assert lower < 0.7 < upper


@given(
    st.lists(
        st.one_of(
            st.none(),
            st.floats(
                min_value=-1e6,
                max_value=1e6,
                allow_nan=False,
                allow_infinity=False,
            ),
        ),
        min_size=1,
        max_size=30,
    )
)
def test_mean_stays_within_observed_bounds(values: list[float | None]) -> None:
    observed = [value for value in values if value is not None]
    result = mean(values)

    if not observed:
        assert result == pytest.approx(0.0)
        return

    assert min(observed) - 1e-9 <= result <= max(observed) + 1e-9


@given(
    st.integers(min_value=0, max_value=500),
    st.integers(min_value=0, max_value=500),
)
def test_wilson_confidence_interval_is_bounded_and_contains_empirical_rate(
    successes: int,
    trials: int,
) -> None:
    actual_trials = max(successes, trials)
    lower, upper = wilson_confidence_interval(successes=successes, trials=actual_trials)

    assert 0.0 <= lower <= upper <= 1.0
    if actual_trials == 0:
        assert (lower, upper) == pytest.approx((0.0, 0.0))
        return

    empirical_rate = successes / actual_trials
    assert lower <= empirical_rate + 1e-12
    assert empirical_rate <= upper + 1e-12
