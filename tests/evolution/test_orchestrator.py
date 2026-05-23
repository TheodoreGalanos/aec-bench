# ABOUTME: Tests for the evolution orchestrator outer loop.
# ABOUTME: Covers cycle counting, convergence detection, and result assembly.

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolutionObservation,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import TaskSelector
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.backends.local import make_stub_solve_fn
from aec_bench.evolution.engine import AECEvolutionEngine
from aec_bench.evolution.orchestrator import EvolutionOrchestrator
from aec_bench.evolution.workspace import Workspace
from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scaffold_workspace(root: Path) -> Path:
    """Create the minimal directory structure for a valid Workspace."""
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "test-workspace",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    prompts_dir = root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are an engineering agent.")
    return root


class StubClassifierLLM:
    """Return valid bond-type JSON based on keyword matching in the prompt."""

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        indices_match = re.search(r"Classify turns:\s*([\d,\s]+)$", prompt, re.MULTILINE)
        if indices_match is None:
            return '{"classifications": []}'
        indices = [int(x.strip()) for x in indices_match.group(1).split(",")]
        return json.dumps(
            {
                "classifications": [
                    {
                        "turn_index": i,
                        "bond_type": "execution",
                        "confidence": 0.9,
                        "rationale": "stub",
                    }
                    for i in indices
                ]
            }
        )


class StubEvolverLLM:
    """Return a simple string indicating no changes are needed."""

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        return "No changes needed."


def _make_config(
    *,
    max_cycles: int = 3,
    batch_size: int = 2,
    improvement_threshold: float = 0.02,
    stagnation_window: int = 2,
    workspace_path: str = "/tmp/test-ws",
) -> EvolutionConfig:
    return EvolutionConfig(
        workspace_path=workspace_path,
        models={
            "classifier": "claude-haiku-4",
            "evolver": "claude-sonnet-4-6",
        },
        task_selector=TaskSelector(),
        max_cycles=max_cycles,
        batch_size=batch_size,
        improvement_threshold=improvement_threshold,
        stagnation_window=stagnation_window,
    )


def _make_engine() -> AECEvolutionEngine:
    return AECEvolutionEngine(
        classifier_llm=StubClassifierLLM(),
        evolver_llm=StubEvolverLLM(),
    )


def _make_record(reward: float, task_id: str = "electrical/voltage-drop/test") -> TrialRecord:
    return make_trial_record(
        task={"task_id": task_id, "task_revision": "abc123"},
        evaluation={
            "reward": reward,
            "validity": {
                "output_parseable": True,
                "schema_valid": True,
                "verifier_completed": True,
            },
        },
    )


# ---------------------------------------------------------------------------
# TestEvolutionOrchestrator
# ---------------------------------------------------------------------------


class TestEvolutionOrchestrator:
    """Tests for the EvolutionOrchestrator outer loop."""

    def test_runs_configured_cycles(self, tmp_path: Path) -> None:
        """Orchestrator runs exactly max_cycles cycles when no convergence occurs."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        records = [_make_record(0.5), _make_record(0.6)]
        solve_fn = make_stub_solve_fn(records)

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=solve_fn,
            config=_make_config(max_cycles=3, batch_size=2, stagnation_window=5),
        )

        result = orchestrator.run()

        assert result.cycles_completed == 3
        assert len(result.score_history) == 3

    def test_converges_early(self, tmp_path: Path) -> None:
        """Orchestrator halts before max_cycles when scores stagnate."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        # Same reward every cycle → stagnation after stagnation_window
        records = [_make_record(0.8)]
        solve_fn = make_stub_solve_fn(records)

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=solve_fn,
            config=_make_config(
                max_cycles=10,
                batch_size=1,
                improvement_threshold=0.02,
                stagnation_window=2,
            ),
        )

        result = orchestrator.run()

        assert result.converged is True
        assert result.cycles_completed < 10

    def test_result_has_correct_best_score(self, tmp_path: Path) -> None:
        """best_score reflects the highest reward seen across all cycles."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        cycle_rewards = [0.5, 0.7, 0.9]
        call_count = [0]

        def vary_solve(snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
            reward = cycle_rewards[min(call_count[0], len(cycle_rewards) - 1)]
            call_count[0] += 1
            return [_make_record(reward)]

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=vary_solve,
            config=_make_config(max_cycles=3, batch_size=1, stagnation_window=5),
        )

        result = orchestrator.run()

        assert abs(result.best_score - 0.9) < 1e-9

    def test_discipline_extracted_from_task_id(self, tmp_path: Path) -> None:
        """Discipline is parsed from the first path component of task_id."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        captured_observations: list[list[EvolutionObservation]] = []

        # Monkey-patch the engine to capture observations passed to step
        engine = _make_engine()
        original_step_fn = engine.step

        def capturing_step(workspace, observations, history, selection=None, graveyard=None):
            captured_observations.append(list(observations))
            return original_step_fn(workspace, observations, history, selection=selection, graveyard=graveyard)

        engine.step = capturing_step  # type: ignore[method-assign]

        records = [_make_record(0.7, task_id="electrical/voltage-drop/test")]
        solve_fn = make_stub_solve_fn(records)

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=engine,
            solve_fn=solve_fn,
            config=_make_config(max_cycles=1, batch_size=1, stagnation_window=5),
        )

        orchestrator.run()

        assert len(captured_observations) == 1
        first_cycle_obs = captured_observations[0]
        assert len(first_cycle_obs) == 1
        assert first_cycle_obs[0].discipline == "electrical"


# ---------------------------------------------------------------------------
# TestSelectionPipeline
# ---------------------------------------------------------------------------


class TestSelectionPipeline:
    """Tests for the archive selection pipeline wired into the orchestrator."""

    def test_graveyard_file_saved_after_run(self, tmp_path: Path) -> None:
        """Orchestrator writes graveyard.json to workspace root after run."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        records = [_make_record(0.5)]
        solve_fn = make_stub_solve_fn(records)

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=solve_fn,
            config=_make_config(max_cycles=1, batch_size=1, stagnation_window=5),
        )
        orchestrator.run()

        assert (root / "graveyard.json").exists()

    def test_graveyard_loaded_from_existing_file(self, tmp_path: Path) -> None:
        """Orchestrator loads an existing graveyard.json rather than starting fresh."""
        import json

        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        # Write a pre-existing graveyard file with one entry
        existing_entry = {
            "cycle": 1,
            "strategy": "conservative",
            "mutation_description": "old failed mutation",
            "score_before": 0.4,
            "score_after": 0.3,
            "workspace_version": "evo-old-1",
            "failure_reason": "Score delta: -0.100",
        }
        (root / "graveyard.json").write_text(json.dumps([existing_entry]))

        records = [_make_record(0.5)]
        solve_fn = make_stub_solve_fn(records)

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=solve_fn,
            config=_make_config(max_cycles=1, batch_size=1, stagnation_window=5),
        )
        orchestrator.run()

        # Graveyard file must still exist after run
        saved = json.loads((root / "graveyard.json").read_text())
        # The pre-existing entry should be present (or evicted only if graveyard is full,
        # but with max_size=50 default there is plenty of room)
        assert len(saved) >= 1

    def test_engine_step_receives_selection_kwarg(self, tmp_path: Path) -> None:
        """Engine step is called with selection keyword argument (may be None)."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        captured_selections: list = []

        engine = _make_engine()
        original_step_fn = engine.step

        def capturing_step(workspace, observations, history, selection=None, graveyard=None):
            captured_selections.append(selection)
            return original_step_fn(workspace, observations, history, selection=selection, graveyard=graveyard)

        engine.step = capturing_step  # type: ignore[method-assign]

        records = [_make_record(0.5)]
        solve_fn = make_stub_solve_fn(records)

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=engine,
            solve_fn=solve_fn,
            config=_make_config(max_cycles=1, batch_size=1, stagnation_window=5),
        )
        orchestrator.run()

        # selection is None on cycle 1 (archive has 0 entries before first solve)
        assert len(captured_selections) == 1
        assert captured_selections[0] is None
