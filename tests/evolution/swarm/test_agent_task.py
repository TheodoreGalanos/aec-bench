# ABOUTME: Tests for the async per-agent evolution task loop.
# ABOUTME: Uses a fake evolver to test coordination without LLM calls.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from aec_bench.contracts.evolution import AgentStatus
from aec_bench.evolution.swarm.agent_task import AgentContext, run_agent_loop


@dataclass
class FakeResult:
    score: float


class FakeEvolver:
    def __init__(self, scores: list[float]) -> None:
        self._scores = scores
        self._index = 0

    async def step(self) -> FakeResult:
        score = self._scores[self._index % len(self._scores)]
        self._index += 1
        return FakeResult(score=score)


@pytest.mark.asyncio
async def test_agent_loop_runs_n_evals() -> None:
    evolver = FakeEvolver(scores=[0.5, 0.6, 0.7])
    results: list[Any] = []

    async def on_eval(result: Any) -> bool:
        results.append(result)
        return len(results) < 3

    ctx = AgentContext(agent_id="agent-1", evolver=evolver, on_eval_complete=on_eval)
    state = await run_agent_loop(ctx)
    assert len(results) == 3
    assert state.eval_count == 3


@pytest.mark.asyncio
async def test_agent_loop_tracks_best_score() -> None:
    evolver = FakeEvolver(scores=[0.3, 0.8, 0.5])
    results: list[Any] = []

    async def on_eval(result: Any) -> bool:
        results.append(result)
        return len(results) < 3

    ctx = AgentContext(agent_id="agent-1", evolver=evolver, on_eval_complete=on_eval)
    state = await run_agent_loop(ctx)
    assert state.best_score == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_agent_loop_stops_on_false() -> None:
    evolver = FakeEvolver(scores=[0.5])

    async def on_eval(result: Any) -> bool:
        return False

    ctx = AgentContext(agent_id="agent-1", evolver=evolver, on_eval_complete=on_eval)
    state = await run_agent_loop(ctx)
    assert state.eval_count == 1
    assert state.status == AgentStatus.RETIRED


@pytest.mark.asyncio
async def test_agent_loop_handles_error() -> None:
    class FailingEvolver:
        async def step(self) -> FakeResult:
            raise RuntimeError("API error")

    error_count = 0

    async def on_eval(result: Any) -> bool:
        return True

    async def on_error(error: Exception) -> bool:
        nonlocal error_count
        error_count += 1
        return False

    ctx = AgentContext(
        agent_id="agent-1",
        evolver=FailingEvolver(),
        on_eval_complete=on_eval,
        on_error=on_error,
    )
    state = await run_agent_loop(ctx)
    assert error_count == 1
    assert state.status == AgentStatus.ERROR
