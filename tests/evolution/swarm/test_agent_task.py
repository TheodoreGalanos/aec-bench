# ABOUTME: Tests for the async per-agent evolution task loop.
# ABOUTME: Uses a fake evolver to test coordination without LLM calls.

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aec_bench.contracts.evolution import AgentStatus, MutationStrategy, ProposalUsage, WorkspaceSnapshot
from aec_bench.evolution.checkpoint import AVOIncompleteExternalEffectError
from aec_bench.evolution.core import CandidateProposal, ProposalStatus, SelectionPlan
from aec_bench.evolution.swarm.agent_task import AgentContext, run_agent_loop
from aec_bench.evolution.swarm.core import AgentBudget, SwarmAgentResult, SwarmAssignment


def _assignment(cycle: int, issued_at: datetime | None = None) -> SwarmAssignment:
    selection = SelectionPlan("parent", (), MutationStrategy.CONSERVATIVE, "Improve", "Exact source")
    return SwarmAssignment(
        run_id="run-test",
        assignment_id=f"assignment-{cycle}",
        agent_id="agent-1",
        selection=selection,
        parent=WorkspaceSnapshot(system_prompt="Parent", candidate_id="parent"),
        inspirations=(),
        budget=AgentBudget(1.0),
        issued_at=issued_at or datetime(2026, 8, 26, tzinfo=UTC),
    )


class FakeEvolver:
    def __init__(self, scores: list[float] | None = None) -> None:
        self._scores = scores or [0.5]
        self._index = 0

    async def step(self, assignment: SwarmAssignment) -> SwarmAgentResult:
        self._index += 1
        cost = self._scores[(self._index - 1) % len(self._scores)]
        usage = ProposalUsage(model_requests=1, model_cost_usd=cost)
        variation = CandidateProposal(ProposalStatus.ABSTAINED, None, None, "No child", usage)
        return SwarmAgentResult("agent-1", assignment.assignment_id, variation, usage)


@pytest.mark.asyncio
async def test_agent_loop_runs_n_evals() -> None:
    evolver = FakeEvolver()
    assignments: list[SwarmAssignment] = []

    async def next_assignment() -> SwarmAssignment:
        assignment = _assignment(len(assignments) + 1)
        assignments.append(assignment)
        return assignment

    async def on_eval(assignment: SwarmAssignment, result: SwarmAgentResult) -> bool:
        assert assignment.assignment_id == result.assignment_id
        return len(assignments) < 3

    ctx = AgentContext(agent_id="agent-1", evolver=evolver, next_assignment=next_assignment, on_eval_complete=on_eval)
    state = await run_agent_loop(ctx)
    assert [assignment.assignment_id for assignment in assignments] == ["assignment-1", "assignment-2", "assignment-3"]
    assert state is AgentStatus.RETIRED


@pytest.mark.asyncio
async def test_agent_loop_forwards_exact_typed_result() -> None:
    evolver = FakeEvolver(scores=[0.3, 0.8, 0.5])
    assignments: list[SwarmAssignment] = []
    results: list[SwarmAgentResult] = []

    async def next_assignment() -> SwarmAssignment:
        assignment = _assignment(len(assignments) + 1)
        assignments.append(assignment)
        return assignment

    async def on_eval(assignment: SwarmAssignment, result: SwarmAgentResult) -> bool:
        results.append(result)
        return len(results) < 3

    ctx = AgentContext(agent_id="agent-1", evolver=evolver, next_assignment=next_assignment, on_eval_complete=on_eval)
    state = await run_agent_loop(ctx)
    assert len(results) == 3
    assert [result.assignment_id for result in results] == [
        "assignment-1",
        "assignment-2",
        "assignment-3",
    ]
    assert [result.agent_usage.total_cost_usd for result in results] == [0.3, 0.8, 0.5]
    assert state is AgentStatus.RETIRED


@pytest.mark.asyncio
async def test_agent_loop_stops_on_false() -> None:
    evolver = FakeEvolver(scores=[0.5])

    async def next_assignment() -> SwarmAssignment:
        return _assignment(1)

    async def on_eval(assignment: SwarmAssignment, result: SwarmAgentResult) -> bool:
        return False

    ctx = AgentContext(agent_id="agent-1", evolver=evolver, next_assignment=next_assignment, on_eval_complete=on_eval)
    state = await run_agent_loop(ctx)
    assert state is AgentStatus.RETIRED


@pytest.mark.asyncio
async def test_agent_loop_handles_error() -> None:
    class FailingEvolver:
        async def step(self, assignment: SwarmAssignment) -> SwarmAgentResult:
            raise RuntimeError("API error")

    error_count = 0

    async def next_assignment() -> SwarmAssignment:
        return _assignment(1)

    async def on_eval(assignment: SwarmAssignment, result: SwarmAgentResult) -> bool:
        return True

    async def on_error(error: Exception) -> bool:
        nonlocal error_count
        error_count += 1
        return False

    ctx = AgentContext(
        agent_id="agent-1",
        evolver=FailingEvolver(),
        next_assignment=next_assignment,
        on_eval_complete=on_eval,
        on_error=on_error,
    )
    state = await run_agent_loop(ctx)
    assert error_count == 1
    assert state is AgentStatus.ERROR


@pytest.mark.asyncio
async def test_agent_loop_propagates_incomplete_external_effect_without_retry() -> None:
    class IncompleteEvolver:
        async def step(self, assignment: SwarmAssignment) -> SwarmAgentResult:
            raise AVOIncompleteExternalEffectError()

    assignments: list[SwarmAssignment] = []
    error_count = 0

    async def next_assignment() -> SwarmAssignment:
        assignment = _assignment(len(assignments) + 1)
        assignments.append(assignment)
        return assignment

    async def on_eval(_assignment: SwarmAssignment, _result: SwarmAgentResult) -> bool:
        return True

    async def on_error(_error: Exception) -> bool:
        nonlocal error_count
        error_count += 1
        return True

    ctx = AgentContext(
        agent_id="agent-1",
        evolver=IncompleteEvolver(),
        next_assignment=next_assignment,
        on_eval_complete=on_eval,
        on_error=on_error,
    )

    with pytest.raises(AVOIncompleteExternalEffectError):
        await run_agent_loop(ctx)

    assert len(assignments) == 1
    assert error_count == 0
