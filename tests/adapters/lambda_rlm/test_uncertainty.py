# ABOUTME: Tests for lambda-rlm uncertainty helpers.
# ABOUTME: Validates running stats and joint uncertainty score computation.

import math

import pytest

from aec_bench.adapters.lambda_rlm.uncertainty import RunningStats, compute_joint_score


def test_running_stats_empty_defaults() -> None:
    stats = RunningStats()

    assert stats.n == 0
    assert stats.mean == 0.0
    assert stats.stdev == 0.0
    assert stats.z_score(42.0) == 0.0


def test_running_stats_single_value_has_zero_stdev() -> None:
    stats = RunningStats()
    stats.push(10.0)

    assert stats.n == 1
    assert stats.mean == 10.0
    assert stats.stdev == 0.0
    assert stats.z_score(10.0) == 0.0


def test_running_stats_known_sequence() -> None:
    stats = RunningStats()
    for value in (10.0, 12.0, 14.0):
        stats.push(value)

    assert stats.n == 3
    assert stats.mean == pytest.approx(12.0)
    assert stats.stdev == pytest.approx(math.sqrt(8.0 / 3.0))
    assert stats.z_score(14.0) == pytest.approx(1.22474487139)


def test_compute_joint_score_prefers_confident_shorter_case() -> None:
    good = compute_joint_score(0.9, -0.5, 0.5, 0.01)
    bad = compute_joint_score(0.3, 1.5, 0.5, 0.01)

    assert good < bad


def test_compute_joint_score_clamps_confidence_with_eps() -> None:
    score = compute_joint_score(0.0, 0.0, 0.5, 0.01)
    assert score == pytest.approx(-math.log(0.01))


def test_compute_joint_score_higher_confidence_lowers_score() -> None:
    high_conf = compute_joint_score(0.9, 0.0, 0.5, 0.01)
    low_conf = compute_joint_score(0.3, 0.0, 0.5, 0.01)

    assert high_conf < low_conf
