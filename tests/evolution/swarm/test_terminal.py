# ABOUTME: Tests for the compact terminal status line renderer.
# ABOUTME: Verifies formatting of agent count, eval count, archive coverage, budget, and events.

from __future__ import annotations

from aec_bench.contracts.evolution import AgentStatus, SwarmAgentState
from aec_bench.evolution.swarm.terminal import (
    format_event_line,
    render_status_line,
)


def _make_agent(
    agent_id: str,
    status: AgentStatus = AgentStatus.ACTIVE,
) -> SwarmAgentState:
    return SwarmAgentState(
        agent_id=agent_id,
        model="sonnet",
        status=status,
        worktree_branch=f"coral/{agent_id}",
    )


def _render(
    agents: list[SwarmAgentState],
    *,
    total_evals: int = 10,
    archive_coverage: float = 0.25,
    archive_size: int = 50,
    archive_total: int = 200,
    best_score: float = 0.82,
    budget_pct: float = 0.61,
) -> str:
    return render_status_line(
        agents=agents,
        total_evals=total_evals,
        archive_coverage=archive_coverage,
        archive_size=archive_size,
        archive_total=archive_total,
        best_score=best_score,
        budget_pct=budget_pct,
    )


def test_status_line_contains_agent_count() -> None:
    agents = [_make_agent("a1"), _make_agent("a2"), _make_agent("a3")]
    line = _render(agents)
    assert "3/3" in line


def test_status_line_contains_evals() -> None:
    agents = [_make_agent("a1")]
    line = _render(
        agents,
        total_evals=47,
        archive_coverage=0.38,
        archive_size=196,
        archive_total=512,
    )
    assert "47" in line


def test_status_line_contains_coverage() -> None:
    agents = [_make_agent("a1")]
    line = _render(
        agents,
        archive_coverage=0.38,
        archive_size=196,
        archive_total=512,
    )
    assert "38%" in line


def test_status_line_contains_budget() -> None:
    agents = [_make_agent("a1")]
    line = _render(agents)
    assert "61%" in line


def test_status_line_retired_agents() -> None:
    agents = [
        _make_agent("a1", AgentStatus.ACTIVE),
        _make_agent("a2", AgentStatus.RETIRED),
    ]
    line = _render(agents)
    assert "1/2" in line


def test_format_event_new_best() -> None:
    line = format_event_line(
        timestamp="12:33:12",
        message="Agent-2 new best: 0.87",
    )
    assert "12:33:12" in line
    assert "0.87" in line
