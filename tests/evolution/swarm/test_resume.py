# ABOUTME: Tests explicit swarm-state loading and exact candidate-material validation.
# ABOUTME: Verifies that event logs remain diagnostic and are not the resume authority.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.contracts.evolution import SwarmEvent, SwarmEventType, WorkspaceSnapshot
from aec_bench.evolution.archive import QDArchive
from aec_bench.evolution.swarm.events import SwarmEventWriter
from aec_bench.evolution.swarm.lineage import LineageTracker
from aec_bench.evolution.swarm.notes import NoteStore
from aec_bench.evolution.swarm.resume import load_resumed_state
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard


def _emit_events(path: Path, events: list[tuple[SwarmEventType, str | None, dict]]) -> None:
    writer = SwarmEventWriter(path)
    for event_type, agent_id, payload in events:
        writer.emit(
            SwarmEvent(
                event_type=event_type,
                occurred_at="2026-04-07T10:00:00Z",
                agent_id=agent_id,
                payload=payload,
            )
        )


def _write_state(tmp_path: Path, *, candidate_ids: list[str] | None = None, best: str | None = None) -> Path:
    candidate_ids = candidate_ids or ["baseline"]
    (tmp_path / "swarm_state.json").write_text(
        json.dumps(
            {
                "run_id": "sw-test",
                "total_evaluations": 0,
                "best_candidate_id": best,
                "best_score": 0.5 if best else None,
                "agent_states": [],
                "recent_scores": [],
                "recent_descriptors": [],
                "pivot_state": {"agent_states": []},
                "stopped": False,
                "stop_reason": None,
            }
        )
    )
    (tmp_path / "candidates.json").write_text(
        json.dumps(
            {
                "initial_candidate_id": "baseline",
                "snapshots": [
                    WorkspaceSnapshot(system_prompt=f"{candidate_id} prompt", candidate_id=candidate_id).model_dump()
                    for candidate_id in candidate_ids
                ],
            }
        )
    )
    QDArchive(n_centroids=20).save(tmp_path / "archive.json")
    SharedGraveyard().save(tmp_path / "graveyard.json")
    LineageTracker().save(tmp_path / "lineage.json")
    NoteStore().save(tmp_path / "notes.json")
    (tmp_path / "budget.json").write_text(
        json.dumps({"max_cost_usd": 10.0, "eval_budget_usd": 10.0, "agent_spend": {}, "eval_spend": 0.0})
    )
    return tmp_path


def test_load_explicit_state_without_events(tmp_path: Path) -> None:
    _write_state(tmp_path)
    state = load_resumed_state(tmp_path)
    assert state.total_evals == 0
    assert state.total_cost_usd == 0.0
    assert state.best_score == 0.0
    assert state.initial_candidate_id == "baseline"
    assert state.candidates["baseline"].system_prompt == "baseline prompt"


def test_load_state_uses_events_only_for_diagnostic_sequence(tmp_path: Path) -> None:
    _write_state(tmp_path)
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
    state = load_resumed_state(tmp_path)
    assert state.run_id == "sw-test"
    assert state.total_evals == 0
    assert state.best_score == 0.0
    assert state.next_sequence == 5


def test_load_budget_from_explicit_state(tmp_path: Path) -> None:
    _write_state(tmp_path)
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
    (tmp_path / "budget.json").write_text(
        json.dumps(
            {
                "max_cost_usd": 10.0,
                "eval_budget_usd": 10.0,
                "agent_spend": {"agent-0": 3.5, "agent-1": 1.0},
                "eval_spend": 2.0,
            }
        )
    )
    state = load_resumed_state(tmp_path)
    assert state.total_cost_usd == 4.5
    assert state.budget.agent_spend["agent-0"] == 3.5
    assert state.budget.agent_spend["agent-1"] == 1.0
    assert state.budget.eval_spend == 2.0


def test_load_agents_from_explicit_state(tmp_path: Path) -> None:
    _write_state(tmp_path)
    payload = json.loads((tmp_path / "swarm_state.json").read_text())
    payload["agent_states"] = [
        {"agent_id": "agent-0", "model": "sonnet", "status": "active", "worktree_branch": "branch-0"},
        {"agent_id": "agent-1", "model": "opus", "status": "retired", "worktree_branch": "branch-1"},
    ]
    payload["pivot_state"]["agent_states"] = [{"agent_id": "agent-0"}, {"agent_id": "agent-1"}]
    (tmp_path / "swarm_state.json").write_text(json.dumps(payload))
    state = load_resumed_state(tmp_path)
    assert {agent.agent_id for agent in state.swarm.agent_states} == {"agent-0", "agent-1"}
    assert state.swarm.agent_states[0].model == "sonnet"
    assert state.swarm.agent_states[1].status.value == "retired"


def test_load_fails_when_required_state_is_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="swarm_state.json"):
        load_resumed_state(tmp_path)


def test_load_fails_when_candidate_material_is_missing(tmp_path: Path) -> None:
    _write_state(tmp_path, candidate_ids=["baseline", "child-1"], best="child-1")
    archive = QDArchive(n_centroids=20)
    from aec_bench.contracts.evolution import BehaviourDescriptor

    archive.insert(
        BehaviourDescriptor(
            token_cost=1.0,
            verification_depth=0.1,
            tool_density=0.1,
            exploration_ratio=0.1,
            deliberation_ratio=0.1,
            reward=0.5,
        ),
        WorkspaceSnapshot(system_prompt="Different material", candidate_id="child-1"),
    )
    archive.save(tmp_path / "archive.json")
    payload = json.loads((tmp_path / "candidates.json").read_text())
    payload["snapshots"] = [item for item in payload["snapshots"] if item["candidate_id"] != "child-1"]
    (tmp_path / "candidates.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="exact material"):
        load_resumed_state(tmp_path)
