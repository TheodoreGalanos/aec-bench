# ABOUTME: Tests for swarm-specific contracts added to evolution.py.
# ABOUTME: Validates enums, frozen models, and field constraints.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.evolution import (
    AgentStatus,
    BehaviourDescriptor,
    LineageRecord,
    SwarmAgentState,
    SwarmEvent,
    SwarmEventType,
    SwarmResult,
)

# ---------------------------------------------------------------------------
# AgentStatus enum
# ---------------------------------------------------------------------------


def test_agent_status_values() -> None:
    assert AgentStatus.ACTIVE == "active"
    assert AgentStatus.PIVOTING == "pivoting"
    assert AgentStatus.WINDING_DOWN == "winding_down"
    assert AgentStatus.RETIRED == "retired"
    assert AgentStatus.ERROR == "error"
    assert AgentStatus.RESTARTING == "restarting"


# ---------------------------------------------------------------------------
# SwarmEventType enum
# ---------------------------------------------------------------------------


def test_swarm_event_type_has_core_events() -> None:
    expected = {
        "swarm_started",
        "agent_spawned",
        "eval_completed",
        "archive_updated",
        "graveyard_updated",
        "lineage_recorded",
        "budget_spent",
        "agent_restarted",
        "agent_retired",
        "agent_pivoting",
        "wind_down_started",
        "swarm_completed",
        "note_written",
        "consolidation_produced",
        "heartbeat_fired",
    }
    actual = {e.value for e in SwarmEventType}
    assert expected.issubset(actual)


# ---------------------------------------------------------------------------
# SwarmAgentState
# ---------------------------------------------------------------------------


def _make_agent_state(**overrides) -> SwarmAgentState:
    defaults = dict(
        agent_id="agent-1",
        model="anthropic.claude-sonnet-4-20250514",
        status=AgentStatus.ACTIVE,
        current_bd_focus=None,
        eval_count=0,
        best_score=0.0,
        budget_consumed_usd=0.0,
        restart_count=0,
        last_eval_timestamp="2026-04-07T10:00:00Z",
        consecutive_non_improving=0,
        worktree_branch="coral/agent-1",
    )
    defaults.update(overrides)
    return SwarmAgentState(**defaults)


def test_agent_state_creation() -> None:
    state = _make_agent_state()
    assert state.agent_id == "agent-1"
    assert state.status == AgentStatus.ACTIVE
    assert state.current_bd_focus is None


def test_agent_state_with_bd_focus() -> None:
    bd = BehaviourDescriptor(
        token_cost=5000.0,
        verification_depth=0.8,
        tool_density=1.2,
        exploration_ratio=0.3,
        deliberation_ratio=0.4,
        reward=0.75,
    )
    state = _make_agent_state(current_bd_focus=bd)
    assert state.current_bd_focus is not None
    assert state.current_bd_focus.reward == pytest.approx(0.75)


def test_agent_state_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _make_agent_state(unknown_field="nope")


# ---------------------------------------------------------------------------
# SwarmEvent
# ---------------------------------------------------------------------------


def test_swarm_event_creation() -> None:
    event = SwarmEvent(
        event_type=SwarmEventType.EVAL_COMPLETED,
        timestamp="2026-04-07T10:01:30Z",
        agent_id="agent-1",
        payload={"score": 0.72, "cycle": 1},
        sequence_number=2,
    )
    assert event.event_type == SwarmEventType.EVAL_COMPLETED
    assert event.payload["score"] == 0.72


def test_swarm_event_null_agent_for_global_events() -> None:
    event = SwarmEvent(
        event_type=SwarmEventType.SWARM_STARTED,
        timestamp="2026-04-07T10:00:00Z",
        agent_id=None,
        payload={"run_id": "sw-abc"},
        sequence_number=0,
    )
    assert event.agent_id is None


# ---------------------------------------------------------------------------
# LineageRecord
# ---------------------------------------------------------------------------


def test_lineage_record_creation() -> None:
    record = LineageRecord(
        entry_version="evo-sw-1",
        parent_version="evo-sw-0",
        source_agent_id="agent-2",
        cross_agent=False,
        cross_agent_source=None,
        mutation_type="skill_add",
        bd_region_targeted=None,
        surprise=False,
        timestamp="2026-04-07T10:05:00Z",
    )
    assert record.entry_version == "evo-sw-1"
    assert record.cross_agent is False


def test_lineage_record_cross_agent() -> None:
    record = LineageRecord(
        entry_version="evo-sw-5",
        parent_version="evo-sw-3",
        source_agent_id="agent-3",
        cross_agent=True,
        cross_agent_source="agent-1",
        mutation_type="crossover",
        bd_region_targeted=None,
        surprise=True,
        timestamp="2026-04-07T10:15:00Z",
    )
    assert record.cross_agent is True
    assert record.cross_agent_source == "agent-1"
    assert record.surprise is True


# ---------------------------------------------------------------------------
# SwarmResult
# ---------------------------------------------------------------------------


def test_swarm_result_creation() -> None:
    result = SwarmResult(
        run_id="sw-abc123",
        workspace_name="test-ws",
        agents=[_make_agent_state()],
        archive_summary={"coverage": 0.38, "size": 196},
        total_evals=47,
        total_cost_usd=12.50,
        eval_cost_usd=3.20,
        elapsed_seconds=1800.0,
        best_score=0.87,
        best_workspace_version="evo-sw-31",
        converged=False,
        lineage_record_count=42,
        event_count=150,
    )
    assert result.run_id == "sw-abc123"
    assert result.total_evals == 47
    assert len(result.agents) == 1
