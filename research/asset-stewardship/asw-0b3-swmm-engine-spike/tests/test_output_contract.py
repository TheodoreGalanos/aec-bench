# ABOUTME: Tests the research-only semantic output contract and replay hash.
# ABOUTME: Keeps expected periods, units, and canonical hashing independent from SWMM-reported counts.

from __future__ import annotations

import pytest
from asw_b3_swmm.output import OutputContractError, canonical_semantic_hash, expected_period_count


def test_expected_period_count_is_computed_independently() -> None:
    assert expected_period_count(horizon_seconds=7200, report_step_seconds=60) == 120


def test_expected_period_count_rejects_partial_periods() -> None:
    with pytest.raises(OutputContractError, match="divide the horizon"):
        expected_period_count(horizon_seconds=7201, report_step_seconds=60)


def test_semantic_hash_is_key_order_independent_and_value_sensitive() -> None:
    left = {"periods": 2, "series": {"flow": [1.0, 2.0], "depth": [0.1, 0.2]}}
    reordered = {"series": {"depth": [0.1, 0.2], "flow": [1.0, 2.0]}, "periods": 2}
    changed = {"periods": 2, "series": {"flow": [1.0, 2.1], "depth": [0.1, 0.2]}}

    assert canonical_semantic_hash(left) == canonical_semantic_hash(reordered)
    assert canonical_semantic_hash(left) != canonical_semantic_hash(changed)
