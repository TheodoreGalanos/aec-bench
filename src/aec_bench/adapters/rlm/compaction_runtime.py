# ABOUTME: Applies one RLM compaction transition and records its observable effects.
# ABOUTME: Keeps text and structured-tool turns on the same accounting and trajectory path.

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.adapters.rlm.compaction import compact
from aec_bench.adapters.rlm.engine import ReplEnvironment
from aec_bench.adapters.rlm.scaffolding import ScaffoldingState
from aec_bench.adapters.rlm.scratchpad import Scratchpad
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.rlm.tokens import TokenTracker
from aec_bench.contracts.constitution import StatePersistenceParams
from aec_bench.contracts.pricing import estimate_cost_usd

logger = logging.getLogger(__name__)


class CompactionTrajectory(Protocol):
    """Trajectory surface required to record one compaction event."""

    def new_step(self, call_type: str | None = None) -> int: ...

    def tool_result(
        self,
        tool_name: str,
        stdout: str,
        stderr: str = "",
        exit_code: int = 0,
        duration_ms: int | None = None,
        media: list[str] | None = None,
        metadata: dict[str, object] | None = None,
        output_summary: str | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CompactionTransition:
    """Immutable result of applying one compaction to the live RLM state."""

    number: int
    summary: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    conversation: tuple[RlmMessage, ...]


def run_compaction_transition(
    *,
    client: RlmClient,
    model: str,
    repl: ReplEnvironment,
    scratchpad: Scratchpad | None,
    template: ReportTemplate | None,
    params: StatePersistenceParams,
    previous_count: int,
    pre_message_count: int,
    token_tracker: TokenTracker,
    scaffolding: ScaffoldingState,
    trajectory: CompactionTrajectory | None,
    emit: Callable[[str, str], None],
) -> CompactionTransition:
    """Compact once, then apply accounting, trajectory, and reset effects."""

    result = compact(
        client=client,
        model=model,
        repl=repl,
        scratchpad=scratchpad,
        template=template,
        params=params,
    )
    number = previous_count + 1
    emit(
        "compaction",
        f"#{number} — {len(result.summary):,} char summary, {result.input_tokens:,}in/{result.output_tokens:,}out",
    )

    cost_usd = (
        estimate_cost_usd(
            model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        or 0.0
    )
    token_tracker.record_compaction(
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=cost_usd,
    )

    if trajectory is not None:
        trajectory.new_step()
        trajectory.tool_result(
            "compaction",
            stdout=result.summary[:500],
            metadata={
                "compaction": {
                    "number": number,
                    "pre_messages": pre_message_count,
                    "summary_chars": len(result.summary),
                    "model": model,
                }
            },
        )

    conversation = (
        RlmMessage(
            role="user",
            content=f"[Progress Summary]\n{result.summary}",
        ),
        RlmMessage(
            role="user",
            content=("Continue working on the task. Use RECALL() to retrieve your extracted data."),
        ),
    )
    token_tracker.reset_for_compaction()
    scaffolding.mark_compacted()

    logger.info(
        "Compaction #%d: %d chars summary, model=%s",
        number,
        len(result.summary),
        model,
    )
    return CompactionTransition(
        number=number,
        summary=result.summary,
        model=model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=cost_usd,
        conversation=conversation,
    )
