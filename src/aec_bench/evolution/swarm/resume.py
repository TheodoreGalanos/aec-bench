# ABOUTME: State reconstruction from swarm event log for resume support.
# ABOUTME: Replays JSONL events to rebuild budget, agent states, and run metadata.

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from aec_bench.contracts.evolution import SwarmEventType
from aec_bench.evolution.swarm.events import SwarmEventReader


@dataclass
class ResumedState:
    """Reconstructed swarm state from event log replay."""

    run_id: str = ""
    total_evals: int = 0
    best_score: float = 0.0
    total_cost_usd: float = 0.0
    agent_spend: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    agent_models: dict[str, str] = field(default_factory=dict)
    retired_agents: set[str] = field(default_factory=set)
    next_sequence: int = 0


def rebuild_state(event_log_path: Path) -> ResumedState:
    """Replay event log to reconstruct swarm state for resume."""
    reader = SwarmEventReader(event_log_path)
    events = reader.read_all()
    state = ResumedState()

    for event in events:
        state.next_sequence = max(state.next_sequence, event.sequence_number + 1)

        if event.event_type == SwarmEventType.SWARM_STARTED:
            state.run_id = event.payload.get("run_id", "")
        elif event.event_type == SwarmEventType.AGENT_SPAWNED:
            if event.agent_id:
                state.agent_models[event.agent_id] = event.payload.get("model", "")
        elif event.event_type == SwarmEventType.EVAL_COMPLETED:
            state.total_evals += 1
            score = event.payload.get("score", 0.0)
            if score > state.best_score:
                state.best_score = score
        elif event.event_type == SwarmEventType.BUDGET_SPENT:
            amount = event.payload.get("amount", 0.0)
            total = event.payload.get("total", 0.0)
            if event.agent_id:
                state.agent_spend[event.agent_id] += amount
            state.total_cost_usd = total
        elif event.event_type == SwarmEventType.AGENT_RETIRED:
            if event.agent_id:
                state.retired_agents.add(event.agent_id)

    return state
