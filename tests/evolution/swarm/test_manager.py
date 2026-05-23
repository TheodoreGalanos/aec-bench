# ABOUTME: Integration tests for SwarmManager — lifecycle, budget, archive coordination.
# ABOUTME: Uses FakeEvolver to test orchestration without LLM calls.

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.evolution import BehaviourDescriptor, SwarmEventType
from aec_bench.evolution.swarm.config import (
    SwarmAgentConfig,
    SwarmBudgetConfig,
    SwarmConfig,
    SwarmTaskConfig,
)
from aec_bench.evolution.swarm.events import SwarmEventReader
from aec_bench.evolution.swarm.manager import SwarmManager


def _make_config(agent_count: int = 2, max_cost: float = 10.0, eval_budget: float = 5.0) -> SwarmConfig:
    return SwarmConfig(
        task=SwarmTaskConfig(workspace="./ws", task_path="tasks/test"),
        agents=SwarmAgentConfig(count=agent_count, default_model="test-model"),
        budget=SwarmBudgetConfig(max_cost_usd=max_cost, eval_budget_usd=eval_budget),
    )


_call_counter = 0


class FakeResult:
    """Minimal result object returned by FakeEvolver.step()."""

    def __init__(self, score: float, cost: float = 0.5) -> None:
        global _call_counter
        _call_counter += 1
        self.score = score
        self.cost_usd = cost
        self.workspace_version = f"v-{_call_counter}"
        self.bd = BehaviourDescriptor(
            token_cost=float(_call_counter * 10_000),
            verification_depth=min(score, 1.0),
            tool_density=1.0,
            exploration_ratio=0.3,
            deliberation_ratio=0.2,
            reward=score,
        )
        self.parent_version = ""


class FakeEvolverFactory:
    """Creates fake evolvers that return predetermined scores."""

    def __init__(self, scores_per_agent: dict[str, list[float]]) -> None:
        self._scores = scores_per_agent

    def create(self, agent_id: str, model_override: str | None = None) -> Any:
        scores = self._scores.get(agent_id, [0.5])

        class _FakeEvolver:
            def __init__(self) -> None:
                self._i = 0

            async def step(self) -> FakeResult:
                s = scores[self._i % len(scores)]
                self._i += 1
                return FakeResult(score=s)

        return _FakeEvolver()


@pytest.mark.asyncio
async def test_manager_runs_and_completes(tmp_path: Path) -> None:
    """SwarmManager spawns agents, runs evals, and returns a valid SwarmResult."""
    config = _make_config(agent_count=2, max_cost=5.0)
    factory = FakeEvolverFactory({"agent-0": [0.5, 0.6, 0.7], "agent-1": [0.4, 0.5, 0.6]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    result = await manager.run()
    assert result.run_id != ""
    assert result.total_evals > 0
    assert len(result.agents) == 2


@pytest.mark.asyncio
async def test_manager_enforces_budget(tmp_path: Path) -> None:
    """SwarmManager stops agents when budget is exhausted."""
    config = _make_config(agent_count=2, max_cost=1.0)
    factory = FakeEvolverFactory({"agent-0": [0.5], "agent-1": [0.5]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    result = await manager.run()
    # Small overshoot is acceptable since agents may complete a step before
    # budget exhaustion is detected, but it should be bounded.
    assert result.total_cost_usd <= 1.5


@pytest.mark.asyncio
async def test_manager_emits_events(tmp_path: Path) -> None:
    """SwarmManager emits lifecycle events: started, spawned, eval, completed."""
    config = _make_config(agent_count=1, max_cost=3.0)
    factory = FakeEvolverFactory({"agent-0": [0.5, 0.6]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    await manager.run()
    reader = SwarmEventReader(tmp_path / "events.jsonl")
    events = reader.read_all()
    types = [e.event_type for e in events]
    assert SwarmEventType.SWARM_STARTED in types
    assert SwarmEventType.AGENT_SPAWNED in types
    assert SwarmEventType.EVAL_COMPLETED in types
    assert SwarmEventType.SWARM_COMPLETED in types


@pytest.mark.asyncio
async def test_manager_tracks_best_score(tmp_path: Path) -> None:
    """SwarmManager reports the best score across all agents."""
    config = _make_config(agent_count=1, max_cost=3.0)
    factory = FakeEvolverFactory({"agent-0": [0.7, 0.8]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    result = await manager.run()
    assert result.best_score >= 0.7


@pytest.mark.asyncio
async def test_manager_populates_qd_archive(tmp_path: Path) -> None:
    """SwarmManager inserts eval results into the real QDArchive."""
    config = _make_config(agent_count=2, max_cost=5.0)
    factory = FakeEvolverFactory({"agent-0": [0.5, 0.6], "agent-1": [0.7, 0.8]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    result = await manager.run()

    # Archive should have entries from both agents
    assert result.archive_summary["size"] > 0
    # Archive JSON should be persisted
    assert (tmp_path / "archive.json").exists()


@pytest.mark.asyncio
async def test_manager_archive_has_coverage(tmp_path: Path) -> None:
    """QDArchive coverage increases as agents explore different BD regions."""
    config = _make_config(agent_count=2, max_cost=8.0)
    factory = FakeEvolverFactory({"agent-0": [0.3, 0.5, 0.7], "agent-1": [0.4, 0.6, 0.8]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    result = await manager.run()

    assert result.archive_summary.get("coverage", 0) > 0
    assert result.archive_summary.get("best_reward", 0) > 0


@pytest.mark.asyncio
async def test_manager_saves_state_every_eval(tmp_path: Path) -> None:
    """State files are written after each eval, not just at shutdown."""
    config = _make_config(agent_count=1, max_cost=3.0)
    factory = FakeEvolverFactory({"agent-0": [0.7]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    await manager.run()

    assert (tmp_path / "archive.json").exists()
    assert (tmp_path / "graveyard.json").exists()
    assert (tmp_path / "lineage.json").exists()


@pytest.mark.asyncio
async def test_manager_records_lineage(tmp_path: Path) -> None:
    """Lineage records are created when entries are inserted into the archive."""
    config = _make_config(agent_count=1, max_cost=3.0)
    factory = FakeEvolverFactory({"agent-0": [0.7, 0.8]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    result = await manager.run()

    assert result.lineage_record_count > 0

    # Check lineage file has content (new format: {record: ..., narrative: ...})
    import json

    lineage = json.loads((tmp_path / "lineage.json").read_text())
    assert len(lineage) > 0
    assert lineage[0]["record"]["source_agent_id"] == "agent-0"
    # Narrative should be attached
    assert "narrative" in lineage[0]
    assert "agent_reasoning" in lineage[0]["narrative"]


@pytest.mark.asyncio
async def test_manager_budget_tracks_cost(tmp_path: Path) -> None:
    """Budget is consumed when cost_usd > 0, eventually stopping agents."""
    config = _make_config(agent_count=1, max_cost=1.0)

    # FakeResult always has cost_usd=0.5, so $1 budget = 2 evals
    factory = FakeEvolverFactory({"agent-0": [0.5]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    result = await manager.run()

    assert result.total_cost_usd > 0
    assert result.total_evals <= 3  # budget should stop within a few evals


@pytest.mark.asyncio
async def test_manager_detects_pivot(tmp_path: Path) -> None:
    """Agent status changes to PIVOTING after consecutive non-improving evals."""
    # pivot_after=2 means pivot fires after 2 non-improving evals
    from aec_bench.evolution.swarm.config import SwarmHeartbeatConfig

    config = _make_config(agent_count=1, max_cost=5.0)
    config = config.model_copy(update={"heartbeat": SwarmHeartbeatConfig(pivot_after=2)})

    # All scores are 0.5 — no improvement ever
    factory = FakeEvolverFactory({"agent-0": [0.5]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    await manager.run()

    # Check events for a pivot event
    reader = SwarmEventReader(tmp_path / "events.jsonl")
    events = reader.read_all()
    pivot_events = [e for e in events if e.event_type == SwarmEventType.AGENT_PIVOTING]
    assert len(pivot_events) > 0


@pytest.mark.asyncio
async def test_manager_mixed_models(tmp_path: Path) -> None:
    """Agents can be assigned different models via config.agents.models."""
    from aec_bench.evolution.swarm.config import SwarmAgentConfig

    config = _make_config(agent_count=2, max_cost=3.0)
    config = config.model_copy(
        update={
            "agents": SwarmAgentConfig(
                count=2,
                default_model="model-default",
                models=["model-alpha", "model-beta"],
            ),
        }
    )

    factory = FakeEvolverFactory({"agent-0": [0.5], "agent-1": [0.6]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    await manager.run()

    # Check spawned events carry per-agent models
    reader = SwarmEventReader(tmp_path / "events.jsonl")
    events = reader.read_all()
    spawn_events = [e for e in events if e.event_type == SwarmEventType.AGENT_SPAWNED]
    models = [e.payload["model"] for e in spawn_events]
    assert models == ["model-alpha", "model-beta"]


@pytest.mark.asyncio
async def test_manager_creates_reflect_notes(tmp_path: Path) -> None:
    """Reflect heartbeat creates notes after each eval."""
    config = _make_config(agent_count=1, max_cost=3.0)
    factory = FakeEvolverFactory({"agent-0": [0.5, 0.6]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    await manager.run()

    # Notes should be persisted
    assert (tmp_path / "notes.json").exists()
    import json

    notes = json.loads((tmp_path / "notes.json").read_text())
    assert len(notes) > 0
    assert notes[0]["agent_id"] == "agent-0"
    assert "reflect" in notes[0]["tags"]

    # NOTE_WRITTEN events should be emitted
    reader = SwarmEventReader(tmp_path / "events.jsonl")
    events = reader.read_all()
    note_events = [e for e in events if e.event_type == SwarmEventType.NOTE_WRITTEN]
    assert len(note_events) > 0


@pytest.mark.asyncio
async def test_manager_nudged_specialisation(tmp_path: Path) -> None:
    """Nudges are resolved per agent from config.agents.nudges."""
    from aec_bench.evolution.swarm.config import SwarmAgentConfig

    config = _make_config(agent_count=2, max_cost=3.0)
    config = config.model_copy(
        update={
            "agents": SwarmAgentConfig(
                count=2,
                default_model="test-model",
                specialisation="nudged",
                nudges=["Focus on token efficiency", "Focus on verification depth"],
            ),
        }
    )

    factory = FakeEvolverFactory({"agent-0": [0.5], "agent-1": [0.6]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    await manager.run()

    # Agents should have spawned with nudges in their spawn events
    reader = SwarmEventReader(tmp_path / "events.jsonl")
    events = reader.read_all()
    spawn_events = [e for e in events if e.event_type == SwarmEventType.AGENT_SPAWNED]
    nudges = [e.payload.get("nudge", "") for e in spawn_events]
    assert nudges == ["Focus on token efficiency", "Focus on verification depth"]


@pytest.mark.asyncio
async def test_manager_consolidation_heartbeat(tmp_path: Path) -> None:
    """Consolidation report produced every consolidate_every global evals."""
    from aec_bench.evolution.swarm.config import SwarmHeartbeatConfig

    config = _make_config(agent_count=1, max_cost=5.0)
    config = config.model_copy(
        update={
            "heartbeat": SwarmHeartbeatConfig(consolidate_every=3),
        }
    )

    factory = FakeEvolverFactory({"agent-0": [0.5, 0.6, 0.7, 0.8]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    await manager.run()

    reader = SwarmEventReader(tmp_path / "events.jsonl")
    events = reader.read_all()
    consolidation_events = [e for e in events if e.event_type == SwarmEventType.CONSOLIDATION_PRODUCED]
    # With consolidate_every=3 and ~10 evals, should fire at least once
    assert len(consolidation_events) >= 1
    assert "report_id" in consolidation_events[0].payload


@pytest.mark.asyncio
async def test_manager_saves_run_summary(tmp_path: Path) -> None:
    """A human-readable summary.json is written after each run."""
    config = _make_config(agent_count=2, max_cost=5.0)
    factory = FakeEvolverFactory({"agent-0": [0.6, 0.7], "agent-1": [0.5, 0.8]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    await manager.run()

    summary_path = tmp_path / "summary.json"
    assert summary_path.exists()
    import json

    summary = json.loads(summary_path.read_text())
    assert "run_id" in summary
    assert "agents" in summary
    assert len(summary["agents"]) == 2
    assert "budget" in summary
    assert summary["budget"]["max_cost_usd"] == 5.0
    assert "totals" in summary
    assert summary["totals"]["evals"] > 0


@pytest.mark.asyncio
async def test_manager_eval_events_have_bd_data(tmp_path: Path) -> None:
    """Eval events include BD coordinates for post-run analysis."""
    config = _make_config(agent_count=1, max_cost=3.0)
    factory = FakeEvolverFactory({"agent-0": [0.7]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    await manager.run()

    reader = SwarmEventReader(tmp_path / "events.jsonl")
    events = reader.read_all()
    eval_events = [e for e in events if e.event_type == SwarmEventType.EVAL_COMPLETED]
    assert len(eval_events) > 0
    # BD data should be in the payload
    assert "bd" in eval_events[0].payload
    assert "budget_phase" in eval_events[0].payload
