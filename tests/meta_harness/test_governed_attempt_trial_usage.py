# ABOUTME: Tests exact TrialRecord usage aggregation for governed scored attempts.
# ABOUTME: Rejects incomplete or duplicate evidence instead of guessing provider effects.

from __future__ import annotations

import pytest

from aec_bench.contracts.trial_record import CostRecord, OutputRecord
from aec_bench.meta_harness.governed_attempt_engine.trial_usage import (
    GovernedTrialUsageError,
    aggregate_governed_trial_usage,
)
from tests.support.trial_record_factories import make_trial_record


def test_aggregate_governed_trial_usage_includes_advisor_effects() -> None:
    first = make_trial_record(
        trial_id="trial-alpha",
        outputs=OutputRecord(
            agent_result={
                "usage_model_calls": 2,
                "usage_advisor_calls": 1,
            },
        ),
        cost=CostRecord(
            tokens_in=100,
            tokens_out=20,
            cache_read_tokens=10,
            cache_write_tokens=5,
            estimated_cost_usd=0.2,
            advisor_calls=1,
            advisor_input_tokens=30,
            advisor_output_tokens=10,
        ),
    )
    second = make_trial_record(
        trial_id="trial-beta",
        outputs=OutputRecord(agent_result={"usage_model_calls": 1}),
        cost=CostRecord(
            tokens_in=40,
            tokens_out=8,
            cache_read_tokens=2,
            cache_write_tokens=1,
            estimated_cost_usd=0.05,
            advisor_calls=0,
            advisor_input_tokens=0,
            advisor_output_tokens=0,
        ),
    )

    usage = aggregate_governed_trial_usage(
        (first, second),
        wall_time_seconds=9.5,
    )

    assert usage.model_calls == 4
    assert usage.input_tokens == 170
    assert usage.output_tokens == 38
    assert usage.cache_read_tokens == 12
    assert usage.cache_write_tokens == 6
    assert usage.estimated_cost_usd == pytest.approx(0.25)
    assert usage.wall_time_seconds == 9.5


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (
            make_trial_record(
                cost=CostRecord(
                    tokens_in=1,
                    tokens_out=1,
                    cache_read_tokens=0,
                    cache_write_tokens=0,
                    estimated_cost_usd=0.01,
                ),
            ),
            "model-call evidence",
        ),
        (
            make_trial_record(
                outputs=OutputRecord(agent_result={"usage_model_calls": 1}),
            ),
            "cost evidence",
        ),
        (
            make_trial_record(
                outputs=OutputRecord(agent_result={"usage_model_calls": 1}),
                cost=CostRecord(
                    tokens_in=1,
                    tokens_out=1,
                    cache_read_tokens=None,
                    cache_write_tokens=0,
                    estimated_cost_usd=0.01,
                ),
            ),
            "complete token",
        ),
    ],
)
def test_aggregate_governed_trial_usage_rejects_incomplete_evidence(
    record,
    message: str,
) -> None:
    with pytest.raises(GovernedTrialUsageError, match=message):
        aggregate_governed_trial_usage((record,), wall_time_seconds=1.0)


def test_aggregate_governed_trial_usage_rejects_duplicate_trial_identity() -> None:
    record = make_trial_record(
        outputs=OutputRecord(agent_result={"usage_model_calls": 1}),
        cost=CostRecord(
            tokens_in=1,
            tokens_out=1,
            cache_read_tokens=0,
            cache_write_tokens=0,
            estimated_cost_usd=0.01,
            advisor_calls=0,
            advisor_input_tokens=0,
            advisor_output_tokens=0,
        ),
    )

    with pytest.raises(
        GovernedTrialUsageError,
        match="unique TrialRecord identities",
    ):
        aggregate_governed_trial_usage(
            (record, record),
            wall_time_seconds=1.0,
        )
