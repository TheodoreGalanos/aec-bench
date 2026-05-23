# ABOUTME: Tests for swarm state reconstruction from event log replay.
# ABOUTME: Verifies budget, eval count, and best score recovery from JSONL events.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.evolution import SwarmEvent, SwarmEventType
from aec_bench.evolution.swarm.events import SwarmEventWriter
from aec_bench.evolution.swarm.resume import rebuild_state


def _emit_events(path: Path, events: list[tuple[SwarmEventType, str | None, dict]]) -> None:
    writer = SwarmEventWriter(path)
    for event_type, agent_id, payload in events:
        writer.emit(
            SwarmEvent(
                event_type=event_type,
                timestamp="2026-04-07T10:00:00Z",
                agent_id=agent_id,
                payload=payload,
            )
        )


def test_rebuild_empty_log(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.touch()
    state = rebuild_state(path)
    assert state.total_evals == 0
    assert state.total_cost_usd == 0.0
    assert state.best_score == 0.0


def test_rebuild_from_eval_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    _emit_events(
        path,
        [
            (SwarmEventType.SWARM_STARTED, None, {"run_id": "sw-test"}),
            (SwarmEventType.AGENT_SPAWNED, "agent-0", {"model": "sonnet"}),
            (
                SwarmEventType.EVAL_COMPLETED,
                "agent-0",
                {"score": 0.5, "cost_usd": 1.0},
            ),
            (
                SwarmEventType.EVAL_COMPLETED,
                "agent-0",
                {"score": 0.7, "cost_usd": 1.5},
            ),
            (
                SwarmEventType.EVAL_COMPLETED,
                "agent-1",
                {"score": 0.6, "cost_usd": 1.0},
            ),
        ],
    )
    state = rebuild_state(path)
    assert state.run_id == "sw-test"
    assert state.total_evals == 3
    assert state.best_score == 0.7
    assert state.next_sequence == 5


def test_rebuild_budget_from_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    _emit_events(
        path,
        [
            (SwarmEventType.SWARM_STARTED, None, {"run_id": "sw-test"}),
            (SwarmEventType.BUDGET_SPENT, "agent-0", {"amount": 2.0, "total": 2.0}),
            (SwarmEventType.BUDGET_SPENT, "agent-0", {"amount": 1.5, "total": 3.5}),
            (SwarmEventType.BUDGET_SPENT, "agent-1", {"amount": 1.0, "total": 4.5}),
        ],
    )
    state = rebuild_state(path)
    assert state.total_cost_usd == 4.5
    assert state.agent_spend["agent-0"] == 3.5
    assert state.agent_spend["agent-1"] == 1.0


def test_rebuild_agents_from_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    _emit_events(
        path,
        [
            (SwarmEventType.SWARM_STARTED, None, {"run_id": "sw-test"}),
            (SwarmEventType.AGENT_SPAWNED, "agent-0", {"model": "sonnet"}),
            (SwarmEventType.AGENT_SPAWNED, "agent-1", {"model": "opus"}),
            (SwarmEventType.AGENT_RETIRED, "agent-1", {}),
        ],
    )
    state = rebuild_state(path)
    assert "agent-0" in state.agent_models
    assert "agent-1" in state.agent_models
    assert "agent-1" in state.retired_agents
