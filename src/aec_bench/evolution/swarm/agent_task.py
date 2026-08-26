# ABOUTME: Async per-agent evolution task loop for swarm execution.
# ABOUTME: Each agent runs as a coroutine, calling step() and reporting results via callbacks.

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from aec_bench.contracts.evolution import AgentStatus
from aec_bench.evolution.swarm.core import SwarmAgentResult, SwarmAssignment

logger = logging.getLogger(__name__)


class Evolver(Protocol):
    """Protocol for an evolver that can perform a single evolution step."""

    async def step(self, assignment: SwarmAssignment) -> SwarmAgentResult: ...


@dataclass
class AgentContext:
    """Everything an agent task loop needs to run."""

    agent_id: str
    evolver: Evolver
    next_assignment: Callable[[], Awaitable[SwarmAssignment]]
    on_eval_complete: Callable[[SwarmAssignment, SwarmAgentResult], Awaitable[bool]]
    on_error: Callable[[Exception], Awaitable[bool]] | None = None
    model: str = ""
    worktree_branch: str = ""


async def run_agent_loop(ctx: AgentContext) -> AgentStatus:
    """Run the eval loop for a single agent until told to stop.

    Calls ``ctx.evolver.step()`` repeatedly.  After each successful step the
    ``on_eval_complete`` callback decides whether to continue (return True)
    or stop (return False).  On error, ``on_error`` is consulted if provided.
    """
    status = AgentStatus.ACTIVE

    while True:
        try:
            assignment = await ctx.next_assignment()
            result = await ctx.evolver.step(assignment)
        except Exception as exc:
            logger.warning("Agent %s error: %s", ctx.agent_id, exc)
            status = AgentStatus.ERROR
            if ctx.on_error is not None:
                should_continue = await ctx.on_error(exc)
                if should_continue:
                    continue
            break

        should_continue = await ctx.on_eval_complete(assignment, result)
        if not should_continue:
            status = AgentStatus.RETIRED
            break

    return status
