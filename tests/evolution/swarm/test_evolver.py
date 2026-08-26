# ABOUTME: Integration tests for SwarmAgentEvolver and SwarmEvolverFactory.
# ABOUTME: Tests the full evolution cycle with stub LLMs — no real API calls.

from __future__ import annotations

import json
from pathlib import Path

import yaml

from aec_bench.contracts.evolution import EvolutionConfig, MutationSummary
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig, TaskSelector
from aec_bench.evolution.core import VariationResult, VariationStatus
from aec_bench.evolution.evaluation import CandidateEvaluationBatch
from aec_bench.evolution.swarm.evolver import (
    SwarmAgentEvolver,
    SwarmEvolverFactory,
    SwarmStepResult,
)
from aec_bench.evolution.workspace import Workspace
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import PlannedTrial
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Stub LLM clients that return canned responses
# ---------------------------------------------------------------------------


class StubClassifierLLM:
    """Returns a minimal classification response for any prompt."""

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:
        return json.dumps([{"turn_index": 0, "bond_type": "E", "confidence": 0.9, "rationale": "execution"}])


class StubEvolverLLM:
    """Returns a no-op mutation response."""

    def complete(self, prompt: str, *, temperature: float = 0.7, max_tokens: int = 16384) -> str:
        return json.dumps(
            {
                "reasoning": "No changes needed at this time.",
                "actions": [],
            }
        )


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


# ---------------------------------------------------------------------------
# SwarmStepResult contract
# ---------------------------------------------------------------------------


def test_swarm_step_result_has_required_fields() -> None:
    from aec_bench.contracts.evolution import BehaviourDescriptor

    bd = BehaviourDescriptor(
        token_cost=5000.0,
        verification_depth=0.5,
        tool_density=1.0,
        exploration_ratio=0.3,
        deliberation_ratio=0.2,
        reward=0.7,
    )
    result = SwarmStepResult(score=0.7, bd=bd, cost_usd=0.5, candidate_id="v1")
    assert result.score == 0.7
    assert result.bd is not None
    assert result.cost_usd == 0.5
    assert result.candidate_id == "v1"


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
        evolver_llm=StubEvolverLLM(),
        evolver_model_name="test-model",
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
        evolver_llm=StubEvolverLLM(),
        evolver_model_name="test-model",
        model="test-model",
    )

    e1 = factory.create("agent-0")
    e2 = factory.create("agent-1")

    # Each agent should have a different workspace path
    assert e1._workspace._root != e2._workspace._root
    factory.cleanup()


def test_accepted_swarm_child_remains_in_canonical_workspace(tmp_path: Path, monkeypatch) -> None:
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
        return VariationResult(
            status=VariationStatus.SUBMITTED,
            child=request.parent.snapshot.model_copy(
                update={"candidate_id": child_id, "system_prompt": "accepted prompt"}
            ),
            mutation=MutationSummary(prompt_modified=True),
            reasoning="accepted test child",
            model_cost_usd=0.0,
        )

    monkeypatch.setattr("aec_bench.evolution.swarm.evolver.run_structured_variation", submit)
    evolver = SwarmAgentEvolver(
        workspace=workspace,
        config=config,
        batch_planner=lambda _size, _cycle: batch,
        solve_fn=evaluate,
        classifier_llm=StubClassifierLLM(),
        evolver_llm=StubEvolverLLM(),
        evolver_model_name="test",
        run_id="swarm-test",
    )

    result = evolver._sync_step()

    assert result.candidate_id == "swarm-test:1"
    assert workspace.read_prompt() == "accepted prompt"
