# ABOUTME: Tests aggregate evidence accounting and fail-closed Hx runtime budget enforcement.
# ABOUTME: Covers token, cost, wall-clock, and missing-observation behavior independently of Harbor.

from __future__ import annotations

import pytest

from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.trial_record import CostRecord, TimingRecord
from aec_bench.harness.budget import HarnessBudgetError, HarnessBudgetLedger
from tests.support.trial_record_factories import make_trial_record


def test_budget_ledger_aggregates_cost_and_preserves_first_breach() -> None:
    ledger = HarnessBudgetLedger(HarnessBudget(max_tokens=None, max_cost_usd=0.1))
    record = make_trial_record(
        cost=CostRecord(tokens_in=10, tokens_out=2, estimated_cost_usd=0.06),
    )

    ledger.record_trial(record)
    with pytest.raises(HarnessBudgetError) as captured:
        ledger.record_trial(record.model_copy(update={"trial_id": "trial-002"}))

    assert captured.value.code == "harness_cost_budget_exceeded"
    observation = ledger.snapshot()
    assert observation.imported_trials == 2
    assert observation.observed_cost_usd == pytest.approx(0.12)
    assert observation.breach_code == "harness_cost_budget_exceeded"
    with pytest.raises(HarnessBudgetError, match="observed cost") as repeated:
        ledger.before_dispatch()
    assert repeated.value.code == captured.value.code


def test_budget_ledger_requires_token_evidence_only_when_cap_is_declared() -> None:
    unmetered = make_trial_record(cost=CostRecord(estimated_cost_usd=0.01))
    permissive = HarnessBudgetLedger(HarnessBudget(max_tokens=None, max_cost_usd=None))

    permissive.record_trial(unmetered)

    assert permissive.snapshot().token_evidence_complete is False
    metered = HarnessBudgetLedger(HarnessBudget(max_tokens=100, max_cost_usd=None))
    with pytest.raises(HarnessBudgetError) as captured:
        metered.record_trial(unmetered)
    assert captured.value.code == "harness_token_evidence_missing"


def test_budget_ledger_uses_trial_and_wall_clock_runtime_evidence() -> None:
    now = [10.0]
    ledger = HarnessBudgetLedger(
        HarnessBudget(max_runtime_seconds=5, max_tokens=None, max_cost_usd=None),
        clock=lambda: now[0],
    )
    assert ledger.before_dispatch() == 5

    ledger.record_trial(make_trial_record(timing=TimingRecord(total_seconds=4.0)))
    now[0] = 16.0
    with pytest.raises(HarnessBudgetError) as captured:
        ledger.after_dispatch()

    assert captured.value.code == "harness_runtime_budget_exceeded"
    assert ledger.snapshot().elapsed_wall_seconds == 6.0


def test_budget_ledger_accounts_intermediate_stage_usage_without_importing_a_trial() -> None:
    ledger = HarnessBudgetLedger(HarnessBudget(max_tokens=100, max_cost_usd=0.1))

    ledger.record_stage_execution(
        input_tokens=30,
        output_tokens=5,
        estimated_cost_usd=0.04,
        total_seconds=2.5,
    )

    observation = ledger.snapshot()
    assert observation.imported_trials == 0
    assert observation.recorded_stage_executions == 1
    assert observation.observed_tokens == 35
    assert observation.observed_cost_usd == pytest.approx(0.04)
    assert observation.observed_trial_seconds == pytest.approx(2.5)
    assert observation.token_evidence_complete
    assert observation.cost_evidence_complete


@pytest.mark.parametrize(
    ("budget", "second_reservation", "code"),
    [
        (
            HarnessBudget(max_agent_turns=3),
            {"agent_turns": 2, "tool_calls": 0, "context_tokens": 0},
            "harness_agent_turn_capacity_exceeded",
        ),
        (
            HarnessBudget(max_tool_calls=3),
            {"agent_turns": 0, "tool_calls": 2, "context_tokens": 0},
            "harness_tool_call_capacity_exceeded",
        ),
        (
            HarnessBudget(max_context_tokens=3),
            {"agent_turns": 0, "tool_calls": 0, "context_tokens": 2},
            "harness_context_capacity_exceeded",
        ),
    ],
)
def test_budget_ledger_reserves_aggregate_invocation_capacity_before_dispatch(
    budget: HarnessBudget,
    second_reservation: dict[str, int],
    code: str,
) -> None:
    ledger = HarnessBudgetLedger(budget)
    ledger.reserve_invocation_capacity(agent_turns=2, tool_calls=2, context_tokens=2)

    with pytest.raises(HarnessBudgetError) as captured:
        ledger.reserve_invocation_capacity(**second_reservation)

    assert captured.value.code == code
    observation = ledger.snapshot()
    assert observation.reserved_agent_turns == 2
    assert observation.reserved_tool_calls == 2
    assert observation.reserved_context_tokens == 2
