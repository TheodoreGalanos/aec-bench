# ABOUTME: Integration tests for SwarmAgentEvolver and SwarmEvolverFactory.
# ABOUTME: Tests the full evolution cycle with stub LLMs — no real API calls.

from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    MutationSummary,
    VariationUsage,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig, TaskSelector
from aec_bench.contracts.trial_record import CostRecord
from aec_bench.evolution import variation_operator
from aec_bench.evolution.cancellation import AVOCancellationSignal
from aec_bench.evolution.core import DevelopmentAttempt, SelectionPlan, VariationResult, VariationStatus
from aec_bench.evolution.evaluation import CandidateEvaluationBatch, bind_evaluated_candidate
from aec_bench.evolution.memory import AVOMemoryEntry
from aec_bench.evolution.supervision import (
    AVORemainingBudget,
    AVOSupervisionAdvice,
    AVOSupervisionRequest,
    AVOSupervisionResult,
    AVOSupervisionTrigger,
)
from aec_bench.evolution.swarm import evolver as swarm_evolver_module
from aec_bench.evolution.swarm.core import AgentBudget, SwarmAgentResult, SwarmAssignment
from aec_bench.evolution.swarm.evolver import (
    SwarmAgentEvolver,
    SwarmEvolverFactory,
)
from aec_bench.evolution.workspace import Workspace
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import PlannedTrial
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record


def test_evolver_timeout_waits_for_cooperative_executor_worker() -> None:
    """A timeout signals the worker and does not abandon its executor future."""
    started = threading.Event()
    evolver = SwarmAgentEvolver(
        workspace=None,
        config=None,
        batch_planner=None,
        solve_fn=None,
        classifier_llm=None,
        variation_operator=lambda _request, _workspace, _child: None,
        cancellation_signal=AVOCancellationSignal(),
        timeout=0.01,
    )

    def worker(_assignment: object) -> object:
        started.set()
        while not evolver.cancellation_signal.is_set():
            time.sleep(0.001)
        return None

    evolver._sync_step = worker  # type: ignore[method-assign]

    async def run() -> None:
        task = asyncio.create_task(evolver.step(None))
        assert await asyncio.to_thread(started.wait, 1)
        with pytest.raises(TimeoutError):
            await task
        assert not evolver.worker_active

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Stub LLM clients that return canned responses
# ---------------------------------------------------------------------------


class StubClassifierLLM:
    """Returns a minimal classification response for any prompt."""

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:
        return json.dumps([{"turn_index": 0, "bond_type": "E", "confidence": 0.9, "rationale": "execution"}])


# ---------------------------------------------------------------------------
# Test workspace and task setup helpers
# ---------------------------------------------------------------------------


def _setup_workspace(tmp_path: Path) -> Path:
    """Create a minimal evolution workspace."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "prompts").mkdir()
    (ws / "skills").mkdir()
    (ws / "manifest.yaml").write_text(
        yaml.dump(
            {
                "name": "test-swarm",
                "agent_adapter": "rlm",
                "evolvable_layers": ["prompts", "skills"],
            }
        )
    )
    (ws / "prompts" / "system.md").write_text("You are a helpful engineering agent. Solve the task.\n")
    return ws


def _setup_task(tmp_path: Path) -> Path:
    """Create a minimal task with instruction and a trivial verifier."""
    task_dir = tmp_path / "tasks" / "electrical" / "test-task" / "instance-1"
    task_dir.mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Compute 2 + 2.\n")
    (task_dir / "ground_truth.json").write_text(json.dumps({"answer": 4}))

    # Trivial verifier that always gives reward 0.5
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "verify.py").write_text(
        "import json\n"
        "from pathlib import Path\n"
        'reward = {"reward": 0.5}\n'
        'Path("logs/verifier").mkdir(parents=True, exist_ok=True)\n'
        'Path("logs/verifier/reward.json").write_text(json.dumps(reward))\n'
        'Path("logs/verifier/details.json").write_text(json.dumps({"answer": {"reward": 0.5}}))\n'
    )
    return task_dir


def _setup_evolution_inputs(tmp_path: Path) -> tuple[Workspace, CandidateEvaluationBatch]:
    """Build the provider-free inputs required by one functional swarm cycle."""
    root = _setup_workspace(tmp_path)
    workspace = Workspace(root)
    workspace.init_versioning()
    task_dir = tmp_path / "tasks" / "electrical" / "voltage-drop" / "case"
    task_dir.mkdir(parents=True)
    resolved = resolve_instance_paths(make_task_definition(task_id="electrical/voltage-drop/case"), task_dir)
    trial = PlannedTrial(
        trial_id="planned-trial",
        experiment_id="swarm-test",
        task_id=resolved.task.task_id,
        agent=AgentConfig(name="agent", adapter="direct", model="test"),
        compute=ComputeConfig(backend="local"),
        repetition=1,
    )
    return workspace, CandidateEvaluationBatch(
        tasks=(resolved,),
        trials=(trial,),
        evaluation_case_ids=("electrical/voltage-drop/case::attempt=1",),
    )


def _submitted_variation(
    request,
    child_id: str,
    prompt: str,
    cost: float,
    *,
    memory: tuple[AVOMemoryEntry, ...] = (),
) -> VariationResult:
    child = request.parent.snapshot.model_copy(update={"candidate_id": child_id, "system_prompt": prompt})
    usage = VariationUsage(
        model_requests=1,
        model_cost_usd=cost,
        development_evaluations=1,
        development_evaluation_cost_usd=0.0,
    )
    observations = tuple(item.model_copy(update={"candidate_id": child_id}) for item in request.parent.observations)
    assessment = request.parent.assessment.model_copy(update={"candidate_id": child_id})
    evaluated = bind_evaluated_candidate(child, observations, assessment)
    attempt = DevelopmentAttempt(
        attempt_id=f"{request.parent.snapshot.candidate_id}:attempt-1",
        revision=1,
        evaluated=evaluated,
        mutation=MutationSummary(prompt_modified=True),
        hypothesis="Submitted test child",
        usage_after=usage,
    )
    return VariationResult(
        status=VariationStatus.SUBMITTED,
        child=child,
        mutation=attempt.mutation,
        reasoning="submitted test child",
        usage=usage,
        attempt=attempt,
        memory=memory,
    )


# ---------------------------------------------------------------------------
# Swarm assignment/result contract
# ---------------------------------------------------------------------------


def test_evolver_returns_exact_assignment_result_without_host_evidence(tmp_path: Path) -> None:
    workspace, batch = _setup_evolution_inputs(tmp_path)
    config = EvolutionConfig(
        workspace_path=str(workspace.root),
        models={"classifier": "test", "evolver": "test"},
        task_selector=TaskSelector(),
        batch_size=1,
        max_cycles=1,
    )
    parent = workspace.export_snapshot("parent")
    assignment = SwarmAssignment(
        run_id="run-test",
        assignment_id="assignment-1",
        agent_id="agent-1",
        selection=SelectionPlan("parent", (), "conservative", "Improve", "Use exact material"),
        parent=parent,
        inspirations=(),
        budget=AgentBudget(2.0),
        issued_at=datetime.now(UTC),
    )

    def evaluate(snapshot, _batch):
        return (
            make_trial_record(
                trial_id=f"{snapshot.candidate_id}-trial",
                task_id="electrical/voltage-drop/case",
                evaluation={
                    "reward": 0.5,
                    "validity": {
                        "output_parseable": True,
                        "schema_valid": True,
                        "verifier_completed": True,
                    },
                },
                cost=CostRecord(estimated_cost_usd=0.0),
            ),
        )

    def submit(request, _source, child_id, **_kwargs):
        assert request.selection == assignment.selection
        assert request.parent.snapshot.candidate_id == assignment.parent.candidate_id
        return _submitted_variation(request, child_id, "child prompt", 0.25)

    evolver = SwarmAgentEvolver(
        workspace=workspace,
        config=config,
        batch_planner=lambda _size, _cycle: batch,
        solve_fn=evaluate,
        classifier_llm=StubClassifierLLM(),
        variation_operator=submit,
    )

    result = evolver._sync_step(assignment)

    assert isinstance(result, SwarmAgentResult)
    assert result.agent_id == assignment.agent_id
    assert result.assignment_id == assignment.assignment_id
    assert result.variation.status is VariationStatus.SUBMITTED
    assert result.variation.child is not None
    assert result.variation.child.candidate_id == assignment.assignment_id
    assert result.agent_usage.total_cost_usd == 0.25
    assert not hasattr(result, "score")
    assert not hasattr(result, "bd")
    assert workspace.read_prompt() == parent.system_prompt


def test_evolver_memory_is_private_to_each_agent_and_carries_between_cycles(tmp_path: Path) -> None:
    workspace, batch = _setup_evolution_inputs(tmp_path)
    config = EvolutionConfig(
        workspace_path=str(workspace.root),
        models={"classifier": "test", "evolver": "test"},
        task_selector=TaskSelector(),
        batch_size=1,
        max_cycles=1,
    )
    parent = workspace.export_snapshot("parent")
    assignment = SwarmAssignment(
        run_id="run-test",
        assignment_id="assignment-1",
        agent_id="agent-1",
        selection=SelectionPlan("parent", (), "conservative", "Improve", "Use exact material"),
        parent=parent,
        inspirations=(),
        budget=AgentBudget(2.0),
        issued_at=datetime.now(UTC),
    )
    other_assignment = SwarmAssignment(
        run_id="run-test",
        assignment_id="assignment-2",
        agent_id="agent-2",
        selection=SelectionPlan("parent", (), "conservative", "Improve", "Use exact material"),
        parent=parent,
        inspirations=(),
        budget=AgentBudget(2.0),
        issued_at=datetime.now(UTC),
    )
    seen: list[tuple[str, tuple[AVOMemoryEntry, ...]]] = []

    def submit(request, _source, child_id, **_kwargs):
        seen.append((request.selection.parent_candidate_id, request.memory))
        entry = AVOMemoryEntry(
            source_variation_id=request.run_id,
            source_attempt_id=f"{request.run_id}:{request.cycle}",
            hypothesis="Use the exact parent material.",
            change_summary="system prompt modified",
            evidence_summary="valid=True; batch_score=0.5; evaluation_cases=1; trials=1",
            outcome="improved",
            next_direction="Try one bounded follow-up.",
        )
        return _submitted_variation(request, child_id, "child prompt", 0.0, memory=(entry,))

    def evaluate(snapshot, _batch):
        return (
            make_trial_record(
                trial_id=f"{snapshot.candidate_id}-trial",
                task_id="electrical/voltage-drop/case",
                evaluation={
                    "reward": 0.5,
                    "validity": {"output_parseable": True, "schema_valid": True, "verifier_completed": True},
                },
            ),
        )

    first = SwarmAgentEvolver(
        workspace=workspace,
        config=config,
        batch_planner=lambda _size, _cycle: batch,
        solve_fn=evaluate,
        classifier_llm=StubClassifierLLM(),
        variation_operator=submit,
    )
    second = SwarmAgentEvolver(
        workspace=workspace,
        config=config,
        batch_planner=lambda _size, _cycle: batch,
        solve_fn=evaluate,
        classifier_llm=StubClassifierLLM(),
        variation_operator=submit,
    )

    first._sync_step(assignment)
    first._sync_step(assignment)
    second._sync_step(other_assignment)

    assert seen[0][1] == ()
    assert seen[1][1] != ()
    assert seen[2][1] == ()


# ---------------------------------------------------------------------------
# SwarmEvolverFactory
# ---------------------------------------------------------------------------


def test_factory_creates_evolver(tmp_path: Path) -> None:
    ws = _setup_workspace(tmp_path)
    task_dir = _setup_task(tmp_path)

    factory = SwarmEvolverFactory(
        workspace_source=ws,
        task_dirs=[task_dir],
        classifier_llm=StubClassifierLLM(),
        model="test-model",
    )

    evolver = factory.create("agent-0")
    assert isinstance(evolver, SwarmAgentEvolver)
    factory.cleanup()


def test_factory_creates_independent_workspaces(tmp_path: Path) -> None:
    ws = _setup_workspace(tmp_path)
    task_dir = _setup_task(tmp_path)

    factory = SwarmEvolverFactory(
        workspace_source=ws,
        task_dirs=[task_dir],
        classifier_llm=StubClassifierLLM(),
        model="test-model",
    )

    e1 = factory.create("agent-0")
    e2 = factory.create("agent-1")

    # Each agent should have a different workspace path
    assert e1._workspace._root != e2._workspace._root
    factory.cleanup()


def test_factory_isolates_supervisor_state_and_checkpoint_paths_per_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _setup_workspace(tmp_path)
    task_dir = _setup_task(tmp_path)
    inputs_root = tmp_path / "inputs"
    inputs_root.mkdir()
    _inputs_workspace, batch = _setup_evolution_inputs(inputs_root)
    models: list[object] = []
    supervisor_runners = []
    captures = []

    def build_model(_model_name: str) -> object:
        model = object()
        models.append(model)
        return model

    monkeypatch.setattr(swarm_evolver_module, "build_pydantic_model", build_model)

    def batch_planner(**_kwargs):
        return lambda _size, _cycle: batch

    def candidate_evaluator(**_kwargs):
        def evaluate(snapshot, current_batch):
            return tuple(
                make_trial_record(
                    trial_id=trial.trial_id,
                    task_id=trial.task_id,
                    evaluation={
                        "reward": 0.5,
                        "validity": {
                            "output_parseable": True,
                            "schema_valid": True,
                            "verifier_completed": True,
                        },
                    },
                )
                for trial in current_batch.trials
            )

        return evaluate

    monkeypatch.setattr(swarm_evolver_module, "make_local_candidate_batch_planner", batch_planner)
    monkeypatch.setattr(swarm_evolver_module, "make_local_candidate_evaluator", candidate_evaluator)

    class RecordingSupervisor:
        def __init__(self, label: str, model: object) -> None:
            self.label = label
            self.model = model
            self.requests: list[AVOSupervisionRequest] = []

        def __call__(self, request: AVOSupervisionRequest) -> AVOSupervisionResult:
            self.requests.append(request)
            return AVOSupervisionResult(
                output=AVOSupervisionAdvice(
                    directions=(f"Private direction for {self.label}.",),
                    reasoning="Advice must stay inside this agent's call.",
                ),
                usage=VariationUsage(model_requests=1, supervisor_interventions=1),
            )

    def build_supervisor(model: object, *, model_identity: str) -> SimpleNamespace:
        runner = RecordingSupervisor(f"agent-{len(supervisor_runners)}", model)
        supervisor_runners.append(runner)
        return SimpleNamespace(runner=runner)

    monkeypatch.setattr(variation_operator, "build_supervision_composition", build_supervisor)

    def capture_run(
        request,
        _source,
        child_candidate_id,
        *,
        agent_runner,
        supervisor_runner,
        checkpoint_path,
        cancellation_signal,
        **_kwargs,
    ) -> VariationResult:
        supervision_request = AVOSupervisionRequest(
            goal=request.selection.goal,
            selected_parent_id=request.selection.parent_candidate_id,
            strategy=request.selection.strategy,
            attempt_summaries=(),
            remaining_budget=AVORemainingBudget(
                remaining_model_requests=1,
                remaining_tool_calls=1,
                remaining_development_evaluations=1,
                remaining_elapsed_seconds=1.0,
                remaining_supervisor_interventions=1,
                cost_limit_usd=None,
                remaining_cost_usd=None,
            ),
            trigger_reason=AVOSupervisionTrigger.EXHAUSTED_DIRECTION_REQUEST,
        )
        advice = supervisor_runner(supervision_request).output
        captures.append(
            {
                "agent_runner": agent_runner,
                "supervisor_runner": supervisor_runner,
                "cancellation_signal": cancellation_signal,
                "checkpoint_path": checkpoint_path,
                "advice": advice,
                "child_candidate_id": child_candidate_id,
            }
        )
        return VariationResult(
            status=VariationStatus.ABSTAINED,
            child=None,
            mutation=None,
            reasoning=advice.directions[0],
            usage=VariationUsage(),
        )

    monkeypatch.setattr(variation_operator, "run_agentic_variation", capture_run)
    factory = SwarmEvolverFactory(
        workspace_source=source,
        task_dirs=[task_dir],
        classifier_llm=StubClassifierLLM(),
        model="test-model",
    )

    first = factory.create("agent-0")
    second = factory.create("agent-1")
    parent = Workspace(source).export_snapshot("parent")
    selection = SelectionPlan("parent", (), "conservative", "Improve checks", "Use the host direction.")
    first_assignment = SwarmAssignment(
        run_id="run-test",
        assignment_id="assignment-1",
        agent_id="agent-0",
        selection=selection,
        parent=parent,
        inspirations=(),
        budget=AgentBudget(2.0),
        issued_at=datetime.now(UTC),
    )
    second_assignment = SwarmAssignment(
        run_id="run-test",
        assignment_id="assignment-2",
        agent_id="agent-1",
        selection=selection,
        parent=parent,
        inspirations=(),
        budget=AgentBudget(2.0),
        issued_at=datetime.now(UTC),
    )
    first._sync_step(first_assignment)
    second._sync_step(second_assignment)
    factory.cleanup()

    assert len(models) == 2
    assert models[0] is not models[1]
    assert len(supervisor_runners) == 2
    assert supervisor_runners[0].model is models[0]
    assert supervisor_runners[1].model is models[1]
    assert supervisor_runners[0] is not supervisor_runners[1]
    assert first._variation_operator is not second._variation_operator
    assert first.cancellation_signal is not second.cancellation_signal
    assert len(captures) == 2
    assert captures[0]["agent_runner"] is not captures[1]["agent_runner"]
    assert captures[0]["supervisor_runner"] is supervisor_runners[0]
    assert captures[1]["supervisor_runner"] is supervisor_runners[1]
    assert captures[0]["cancellation_signal"] is first.cancellation_signal
    assert captures[1]["cancellation_signal"] is second.cancellation_signal
    assert captures[0]["checkpoint_path"] != captures[1]["checkpoint_path"]
    assert captures[0]["checkpoint_path"].parent.parent == source / "_avo_checkpoints"
    assert captures[1]["checkpoint_path"].parent.parent == source / "_avo_checkpoints"
    assert captures[0]["advice"].directions != captures[1]["advice"].directions
    assert len(supervisor_runners[0].requests) == 1
    assert len(supervisor_runners[1].requests) == 1
    assert supervisor_runners[0].requests[0] is not supervisor_runners[1].requests[0]


def test_evolver_returns_submitted_child_without_mutating_canonical_workspace(tmp_path: Path) -> None:
    workspace, batch = _setup_evolution_inputs(tmp_path)
    config = EvolutionConfig(
        workspace_path=str(workspace.root),
        models={"classifier": "test", "evolver": "test"},
        task_selector=TaskSelector(),
        batch_size=1,
        max_cycles=1,
        improvement_threshold=0.02,
    )

    def evaluate(snapshot, _batch):
        reward = 0.9 if snapshot.system_prompt == "accepted prompt" else 0.5
        return (
            make_trial_record(
                trial_id=f"{snapshot.candidate_id}-trial",
                task_id="electrical/voltage-drop/case",
                evaluation={
                    "reward": reward,
                    "validity": {"output_parseable": True, "schema_valid": True, "verifier_completed": True},
                },
            ),
        )

    def submit(request, _source, child_id, **_kwargs):
        result = _submitted_variation(request, child_id, "accepted prompt", 0.0)
        return result

    evolver = SwarmAgentEvolver(
        workspace=workspace,
        config=config,
        batch_planner=lambda _size, _cycle: batch,
        solve_fn=evaluate,
        classifier_llm=StubClassifierLLM(),
        variation_operator=submit,
    )

    assignment = SwarmAssignment(
        run_id="run-test",
        assignment_id="assignment-1",
        agent_id="agent-1",
        selection=SelectionPlan("parent", (), "conservative", "Improve", "Use exact material"),
        parent=workspace.export_snapshot("parent"),
        inspirations=(),
        budget=AgentBudget(2.0),
        issued_at=datetime.now(UTC),
    )
    result = evolver._sync_step(assignment)

    assert result.assignment_id == assignment.assignment_id
    assert result.variation.child is not None
    assert result.variation.child.system_prompt == "accepted prompt"
    assert workspace.read_prompt() == "You are a helpful engineering agent. Solve the task.\n"
