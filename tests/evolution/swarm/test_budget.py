# ABOUTME: Tests for the shared budget pool with phase transitions.
# ABOUTME: Verifies spend tracking, phase detection, and wind-down logic.

from __future__ import annotations

import pytest

from aec_bench.evolution.swarm.budget import BudgetLedger


def test_fresh_ledger_is_exploring() -> None:
    ledger = BudgetLedger(max_cost_usd=50.0, eval_budget_usd=10.0)
    assert ledger.phase == "exploring"
    assert ledger.remaining == pytest.approx(50.0)
    assert ledger.total_agent_spend == pytest.approx(0.0)


def test_record_agent_spend() -> None:
    ledger = BudgetLedger(max_cost_usd=50.0, eval_budget_usd=10.0)
    ledger.record_agent_spend("agent-1", 5.0)
    ledger.record_agent_spend("agent-1", 3.0)
    ledger.record_agent_spend("agent-2", 2.0)
    assert ledger.total_agent_spend == pytest.approx(10.0)
    assert ledger.agent_spend["agent-1"] == pytest.approx(8.0)
    assert ledger.agent_spend["agent-2"] == pytest.approx(2.0)
    assert ledger.remaining == pytest.approx(40.0)


def test_record_eval_spend() -> None:
    ledger = BudgetLedger(max_cost_usd=50.0, eval_budget_usd=10.0)
    ledger.record_eval_spend(3.5)
    assert ledger.eval_spend == pytest.approx(3.5)
    assert ledger.eval_budget_remaining == pytest.approx(6.5)


def test_phase_winding_down_at_80_percent() -> None:
    ledger = BudgetLedger(max_cost_usd=100.0, eval_budget_usd=10.0)
    ledger.record_agent_spend("agent-1", 80.0)
    assert ledger.phase == "winding_down"


def test_phase_final_at_95_percent() -> None:
    ledger = BudgetLedger(max_cost_usd=100.0, eval_budget_usd=10.0)
    ledger.record_agent_spend("agent-1", 95.0)
    assert ledger.phase == "final"


def test_phase_exhausted_at_100_percent() -> None:
    ledger = BudgetLedger(max_cost_usd=100.0, eval_budget_usd=10.0)
    ledger.record_agent_spend("agent-1", 100.0)
    assert ledger.phase == "exhausted"


def test_phase_custom_thresholds() -> None:
    ledger = BudgetLedger(
        max_cost_usd=100.0,
        eval_budget_usd=10.0,
        wind_down_threshold=0.5,
        final_threshold=0.9,
    )
    ledger.record_agent_spend("agent-1", 50.0)
    assert ledger.phase == "winding_down"
    ledger.record_agent_spend("agent-1", 40.0)
    assert ledger.phase == "final"


def test_eval_budget_exhausted() -> None:
    ledger = BudgetLedger(max_cost_usd=100.0, eval_budget_usd=5.0)
    ledger.record_eval_spend(5.0)
    assert ledger.eval_budget_exhausted is True


def test_eval_budget_not_exhausted() -> None:
    ledger = BudgetLedger(max_cost_usd=100.0, eval_budget_usd=5.0)
    ledger.record_eval_spend(4.9)
    assert ledger.eval_budget_exhausted is False


def test_spend_percentage() -> None:
    ledger = BudgetLedger(max_cost_usd=200.0, eval_budget_usd=10.0)
    ledger.record_agent_spend("agent-1", 50.0)
    assert ledger.spend_percentage == pytest.approx(0.25)
