# ABOUTME: Async per-agent evolution task loop for swarm execution.
# ABOUTME: Each agent runs as a coroutine, calling step() and reporting results via callbacks.

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from aec_bench.contracts.evolution import AgentStatus, SwarmAgentState

logger = logging.getLogger(__name__)


class Evolver(Protocol):
    """Protocol for an evolver that can perform a single evolution step."""

    async def step(self) -> Any: ...


@dataclass
class AgentContext:
    """Everything an agent task loop needs to run."""

    agent_id: str
    evolver: Evolver
    on_eval_complete: Callable[[Any], Awaitable[bool]]
    on_error: Callable[[Exception], Awaitable[bool]] | None = None
    model: str = ""
    worktree_branch: str = ""


async def run_agent_loop(ctx: AgentContext) -> SwarmAgentState:
    """Run the eval loop for a single agent until told to stop.

    Calls ``ctx.evolver.step()`` repeatedly.  After each successful step the
    ``on_eval_complete`` callback decides whether to continue (return True)
    or stop (return False).  On error, ``on_error`` is consulted if provided.
    """
    eval_count = 0
    best_score = 0.0
    status = AgentStatus.ACTIVE
    last_timestamp = ""

    while True:
        try:
            result = await ctx.evolver.step()
        except Exception as exc:
            logger.warning("Agent %s error: %s", ctx.agent_id, exc)
            status = AgentStatus.ERROR
            if ctx.on_error is not None:
                should_continue = await ctx.on_error(exc)
                if should_continue:
                    continue
            break

        eval_count += 1
        score = getattr(result, "score", 0.0)
        if score > best_score:
            best_score = score
        last_timestamp = getattr(result, "timestamp", "")

        should_continue = await ctx.on_eval_complete(result)
        if not should_continue:
            status = AgentStatus.RETIRED
            break

    return SwarmAgentState(
        agent_id=ctx.agent_id,
        model=ctx.model or "unknown",
        status=status,
        eval_count=eval_count,
        best_score=best_score,
        last_eval_timestamp=last_timestamp,
        worktree_branch=ctx.worktree_branch or f"coral/{ctx.agent_id}",
    )
