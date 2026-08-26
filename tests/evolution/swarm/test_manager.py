# ABOUTME: Integration tests for SwarmManager — lifecycle, budget, archive coordination.
# ABOUTME: Uses FakeEvolver to test orchestration without LLM calls.

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    MutationSummary,
    ObservationEnrichment,
    SwarmAgentState,
    SwarmEventType,
    VariationUsage,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import CostRecord
from aec_bench.evolution.cancellation import AVOCancellationError, AVOCancellationReason, AVOCancellationSignal
from aec_bench.evolution.checkpoint import AVOIncompleteExternalEffectError
from aec_bench.evolution.core import DevelopmentAttempt, SelectionPlan, VariationResult, VariationStatus
from aec_bench.evolution.evaluation import CandidateEvaluationBatch, bind_evaluated_candidate
from aec_bench.evolution.swarm.config import (
    SwarmAgentConfig,
    SwarmBudgetConfig,
    SwarmConfig,
    SwarmTaskConfig,
)
from aec_bench.evolution.swarm.core import (
    AgentBudget,
    AgentPivotState,
    PivotState,
    SwarmAgentResult,
    SwarmAssignment,
    SwarmState,
)
from aec_bench.evolution.swarm.events import SwarmEventReader
from aec_bench.evolution.swarm.manager import SwarmManager
from aec_bench.evolution.swarm.resume import load_resumed_state
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import PlannedTrial
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record


def _make_config(agent_count: int = 2, max_cost: float = 10.0, eval_budget: float = 5.0) -> SwarmConfig:
    return SwarmConfig(
        task=SwarmTaskConfig(workspace="./ws", task_path="tasks/test"),
        agents=SwarmAgentConfig(count=agent_count, default_model="test-model"),
        budget=SwarmBudgetConfig(max_cost_usd=max_cost, eval_budget_usd=eval_budget),
    )


class FakeEvolverFactory:
    """Creates fake evolvers that return predetermined scores."""

    def __init__(
        self,
        scores_per_agent: dict[str, list[float]],
        state_dir: Path | None = None,
        evaluation_cost: float | None = 0.0,
    ) -> None:
        self._state_dir = state_dir or Path("/private/tmp/aec-bench-swarm-test")
        self._scores = scores_per_agent
        self._evaluation_cost = evaluation_cost
        self._scores_by_candidate: dict[str, float] = {}

    def create(self, agent_id: str, model_override: str | None = None):
        scores = self._scores.get(agent_id, [0.5])

        class _FakeEvolver:
            def __init__(self) -> None:
                self._i = 0

            async def step(self, assignment):
                s = scores[self._i % len(scores)]
                self._i += 1
                candidate_id = f"{agent_id}-child-{self._i}"
                self._factory._scores_by_candidate[candidate_id] = s
                usage = VariationUsage(
                    model_requests=1,
                    development_evaluations=1,
                    model_cost_usd=0.5,
                    development_evaluation_cost_usd=0.0,
                )
                development_trial = make_trial_record(trial_id=f"{candidate_id}-development-trial")
                development_observation = EvolutionObservation(
                    trial=development_trial,
                    enrichment=ObservationEnrichment(),
                    candidate_id=candidate_id,
                    discipline="structural",
                )
                development_assessment = CandidateAssessment(
                    candidate_id=candidate_id,
                    batch_score=s,
                    structural_score=None,
                    discipline_scores={"structural": s},
                    trial_ids=(development_trial.trial_id,),
                    evaluation_case_ids=("development-case",),
                    valid=True,
                )
                development_candidate = bind_evaluated_candidate(
                    WorkspaceSnapshot(system_prompt=f"{candidate_id} prompt", candidate_id=candidate_id),
                    (development_observation,),
                    development_assessment,
                )
                attempt = DevelopmentAttempt(
                    attempt_id=f"{assignment.assignment_id}:attempt-1",
                    revision=1,
                    evaluated=development_candidate,
                    mutation=MutationSummary(prompt_modified=True),
                    hypothesis="Apply exact host-evaluated mutation",
                    usage_after=usage,
                )
                return SwarmAgentResult(
                    agent_id=agent_id,
                    assignment_id=assignment.assignment_id,
                    variation=VariationResult(
                        VariationStatus.SUBMITTED,
                        development_candidate.snapshot,
                        MutationSummary(prompt_modified=True),
                        "Apply exact host-evaluated mutation",
                        usage,
                        attempt,
                    ),
                    agent_usage=usage,
                )

        evolver = _FakeEvolver()
        evolver._factory = self
        return evolver

    def plan_batch(self, batch_size: int, cycle: int) -> CandidateEvaluationBatch:
        task_dir = self._state_dir / "task"
        task_dir.mkdir(parents=True, exist_ok=True)
        task_id = "electrical/check/swarm"
        resolved = resolve_instance_paths(make_task_definition(task_id=task_id), task_dir)
        planned = PlannedTrial(
            trial_id=f"planned-{cycle}",
            experiment_id="swarm-test",
            task_id=task_id,
            agent=AgentConfig(name="agent", adapter="direct", model="test"),
            compute=ComputeConfig(backend="local"),
            repetition=1,
        )
        return CandidateEvaluationBatch((resolved,), (planned,), (f"case-{cycle}",), cycle=cycle)

    def evaluate(self, snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch):
        score = self._scores_by_candidate.get(snapshot.candidate_id, 0.5)
        return tuple(
            make_trial_record(
                trial_id=f"{snapshot.candidate_id}-trial",
                task_id=trial.task_id,
                evaluation=EvaluationResult(
                    reward=score,
                    validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
                ),
                cost=CostRecord(estimated_cost_usd=self._evaluation_cost),
            )
            for trial in batch.trials
        )

    def enrich(self, observations: Sequence[EvolutionObservation]) -> Sequence[EvolutionObservation]:
        return observations

    def baseline_snapshot(self) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(system_prompt="baseline prompt", candidate_id="baseline")

    def cleanup(self) -> None:
        return None


@pytest.mark.asyncio
async def test_unknown_agent_cost_has_no_host_effects(tmp_path: Path) -> None:
    """An unknown USD cost is rejected before any shared result effect."""
    factory = FakeEvolverFactory({"agent-0": [0.5]})
    host_evaluations = 0

    def evaluate(snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch):
        nonlocal host_evaluations
        host_evaluations += 1
        return factory.evaluate(snapshot, batch)

    manager = SwarmManager(
        config=_make_config(agent_count=1),
        state_dir=tmp_path,
        evolver_factory=factory,
        evaluator=evaluate,
    )
    parent = factory.baseline_snapshot()
    manager._candidate_snapshots[parent.candidate_id] = parent
    manager._initial_candidate_id = parent.candidate_id
    manager._agent_cycles["agent-0"] = 1
    initial_state = SwarmState(
        run_id=manager._run_id,
        total_evaluations=0,
        best_candidate_id=None,
        best_score=None,
        agent_states=(SwarmAgentState(agent_id="agent-0", model="test-model", status="active"),),
        recent_scores=(),
        recent_descriptors=(),
        pivot_state=PivotState((AgentPivotState("agent-0"),)),
        stopped=False,
        stop_reason=None,
    )
    manager._state = initial_state
    assignment = SwarmAssignment(
        run_id=manager._state.run_id,
        assignment_id="assignment-1",
        agent_id="agent-0",
        selection=SelectionPlan("baseline", (), "conservative", "Improve", "Use exact material"),
        parent=parent,
        inspirations=(),
        budget=AgentBudget(1.0),
        issued_at=datetime.now(UTC),
    )
    known_result = await factory.create("agent-0").step(assignment)
    unknown_usage = VariationUsage(
        model_requests=known_result.agent_usage.model_requests,
        development_evaluations=known_result.agent_usage.development_evaluations,
    )
    result = SwarmAgentResult(
        agent_id="agent-0",
        assignment_id="assignment-1",
        variation=known_result.variation,
        agent_usage=unknown_usage,
    )
    before_snapshots = dict(manager._candidate_snapshots)
    before_agent_spend = dict(manager._budget.agent_spend)

    with pytest.raises(ValueError, match="unknown cost"):
        await manager._on_result(assignment, result)

    assert manager._state == initial_state
    assert manager._candidate_snapshots == before_snapshots
    assert manager._archive.size == 0
    assert manager._graveyard.size == 0
    assert manager._budget.total_agent_spend == 0.0
    assert manager._budget.eval_spend == 0.0
    assert manager._budget.agent_spend == before_agent_spend
    assert host_evaluations == 0


@pytest.mark.asyncio
async def test_unknown_host_evaluation_cost_has_no_shared_effects(tmp_path: Path) -> None:
    """Unknown parent or child evaluation cost is rejected before finalisation."""
    factory = FakeEvolverFactory({"agent-0": [0.5]}, evaluation_cost=None)
    manager = SwarmManager(
        config=_make_config(agent_count=1),
        state_dir=tmp_path,
        evolver_factory=factory,
    )
    parent = factory.baseline_snapshot()
    manager._candidate_snapshots[parent.candidate_id] = parent
    manager._initial_candidate_id = parent.candidate_id
    manager._agent_cycles["agent-0"] = 1
    initial_state = SwarmState(
        run_id=manager._run_id,
        total_evaluations=0,
        best_candidate_id=None,
        best_score=None,
        agent_states=(SwarmAgentState(agent_id="agent-0", model="test-model", status="active"),),
        recent_scores=(),
        recent_descriptors=(),
        pivot_state=PivotState((AgentPivotState("agent-0"),)),
        stopped=False,
        stop_reason=None,
    )
    manager._state = initial_state
    assignment = SwarmAssignment(
        run_id=manager._state.run_id,
        assignment_id="assignment-1",
        agent_id="agent-0",
        selection=SelectionPlan("baseline", (), "conservative", "Improve", "Use exact material"),
        parent=parent,
        inspirations=(),
        budget=AgentBudget(1.0),
        issued_at=datetime.now(UTC),
    )
    result = await factory.create("agent-0").step(assignment)
    before_snapshots = dict(manager._candidate_snapshots)
    before_agent_spend = dict(manager._budget.agent_spend)

    with pytest.raises(ValueError, match="host evaluation has unknown cost"):
        await manager._on_result(assignment, result)

    assert manager._state == initial_state
    assert manager._candidate_snapshots == before_snapshots
    assert manager._archive.size == 0
    assert manager._graveyard.size == 0
    assert manager._budget.total_agent_spend == 0.0
    assert manager._budget.eval_spend == 0.0
    assert manager._budget.agent_spend == before_agent_spend
    assert not any(
        event.event_type == SwarmEventType.EVAL_COMPLETED
        for event in SwarmEventReader(tmp_path / "events.jsonl").read_all()
    )


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
    assert manager._budget.eval_spend == 0.0


@pytest.mark.asyncio
async def test_concurrent_completions_reduce_without_lost_state(tmp_path: Path) -> None:
    config = _make_config(agent_count=2, max_cost=1.0)
    factory = FakeEvolverFactory({"agent-0": [0.6], "agent-1": [0.7]})
    manager = SwarmManager(config=config, state_dir=tmp_path, evolver_factory=factory)
    result = await manager.run()

    assert result.total_evals >= 2
    assert result.total_cost_usd == pytest.approx(result.total_evals * 0.5)
    eval_events = [
        event
        for event in SwarmEventReader(tmp_path / "events.jsonl").read_all()
        if event.event_type == SwarmEventType.EVAL_COMPLETED
    ]
    assert len(eval_events) == result.total_evals
    persisted = json.loads((tmp_path / "swarm_state.json").read_text())
    assert persisted["total_evaluations"] == result.total_evals


@pytest.mark.asyncio
async def test_host_evaluation_does_not_hold_shared_state_lock(tmp_path: Path) -> None:
    evaluation_started = threading.Event()
    release_evaluation = threading.Event()

    class BlockingEvaluationFactory(FakeEvolverFactory):
        def evaluate(self, snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch):
            evaluation_started.set()
            if not release_evaluation.wait(timeout=5):
                raise TimeoutError("test did not release host evaluation")
            return super().evaluate(snapshot, batch)

    factory = BlockingEvaluationFactory({"agent-0": [0.6]})
    manager = SwarmManager(
        config=_make_config(agent_count=1, max_cost=0.5),
        state_dir=tmp_path,
        evolver_factory=factory,
    )
    run_task = asyncio.create_task(manager.run())
    try:
        started = await asyncio.wait_for(asyncio.to_thread(evaluation_started.wait, 5), timeout=6)
        assert started
        await asyncio.wait_for(manager._lock.acquire(), timeout=1)
        manager._lock.release()
    finally:
        release_evaluation.set()
    await run_task


@pytest.mark.asyncio
async def test_cancellation_persists_state_and_cleans_agent_resources(tmp_path: Path) -> None:
    class BlockingFactory(FakeEvolverFactory):
        def __init__(self) -> None:
            super().__init__({"agent-0": [0.5]})
            self.cleaned = False

        def create(self, agent_id: str, model_override: str | None = None):
            class BlockingEvolver:
                async def step(self, assignment):
                    await asyncio.Event().wait()

            return BlockingEvolver()

        def cleanup(self) -> None:
            self.cleaned = True

    factory = BlockingFactory()
    manager = SwarmManager(config=_make_config(agent_count=1), state_dir=tmp_path, evolver_factory=factory)
    run_task = asyncio.create_task(manager.run())
    await asyncio.sleep(0.05)
    run_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run_task

    assert factory.cleaned
    assert (tmp_path / "swarm_state.json").exists()
    assert load_resumed_state(tmp_path).run_id == manager._run_id


@pytest.mark.asyncio
async def test_manager_stops_peer_before_cleanup_after_agent_cancellation(tmp_path: Path) -> None:
    peer_started = asyncio.Event()
    peer_stopped = asyncio.Event()

    class PeerAwareFactory(FakeEvolverFactory):
        def __init__(self) -> None:
            super().__init__({"agent-0": [0.5], "agent-1": [0.5]})
            self.cleaned = False

        def create(self, agent_id: str, model_override: str | None = None):
            del model_override
            signal = AVOCancellationSignal()

            class PeerAwareEvolver:
                cancellation_signal = signal

                async def step(self, _assignment):
                    if agent_id == "agent-1":
                        peer_started.set()
                        try:
                            await asyncio.Event().wait()
                        except asyncio.CancelledError:
                            peer_stopped.set()
                            raise
                    await peer_started.wait()
                    raise AVOCancellationError(AVOCancellationReason(detail="agent-0 cancelled"))

            return PeerAwareEvolver()

        def cleanup(self) -> None:
            assert peer_stopped.is_set()
            self.cleaned = True

    factory = PeerAwareFactory()
    manager = SwarmManager(config=_make_config(agent_count=2), state_dir=tmp_path, evolver_factory=factory)
    with pytest.raises(AVOCancellationError, match="agent-0 cancelled"):
        await manager.run()

    assert factory.cleaned


@pytest.mark.asyncio
async def test_manager_does_not_retry_incomplete_external_effect(tmp_path: Path) -> None:
    class NonRetryableFactory(FakeEvolverFactory):
        def __init__(self) -> None:
            super().__init__({"agent-0": [0.5]})
            self.step_count = 0
            self.cleaned = False

        def create(self, agent_id: str, model_override: str | None = None):
            del agent_id, model_override
            factory = self

            class IncompleteEvolver:
                async def step(self, _assignment: SwarmAssignment) -> SwarmAgentResult:
                    factory.step_count += 1
                    raise AVOIncompleteExternalEffectError()

            return IncompleteEvolver()

        def cleanup(self) -> None:
            self.cleaned = True

    factory = NonRetryableFactory()
    manager = SwarmManager(config=_make_config(agent_count=1), state_dir=tmp_path, evolver_factory=factory)

    with pytest.raises(AVOIncompleteExternalEffectError):
        await manager.run()

    assert factory.step_count == 1
    assert factory.cleaned
    assert (tmp_path / "swarm_state.json").exists()


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
    result = await manager.run()

    assert (tmp_path / "archive.json").exists()
    assert (tmp_path / "graveyard.json").exists()
    assert (tmp_path / "lineage.json").exists()
    resumed = load_resumed_state(tmp_path)
    assert resumed.run_id == result.run_id
    assert resumed.initial_candidate_id == "baseline"
    assert resumed.candidates["baseline"].system_prompt == "baseline prompt"


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
