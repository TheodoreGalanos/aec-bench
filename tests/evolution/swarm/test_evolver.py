# ABOUTME: Integration tests for SwarmAgentEvolver and SwarmEvolverFactory.
# ABOUTME: Tests the full evolution cycle with stub LLMs — no real API calls.

from __future__ import annotations

import json
from pathlib import Path

import yaml

from aec_bench.evolution.swarm.evolver import (
    SwarmAgentEvolver,
    SwarmEvolverFactory,
    SwarmStepResult,
)

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
    result = SwarmStepResult(score=0.7, bd=bd, cost_usd=0.5, workspace_version="v1")
    assert result.score == 0.7
    assert result.bd is not None
    assert result.cost_usd == 0.5
    assert result.workspace_version == "v1"


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
