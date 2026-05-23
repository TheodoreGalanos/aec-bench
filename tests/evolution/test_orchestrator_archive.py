# ABOUTME: Tests that EvolutionResult includes archive_summary field.
# ABOUTME: Verifies the contract supports QD archive metadata.

from __future__ import annotations

from pathlib import Path

import yaml

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolutionResult,
)
from aec_bench.contracts.experiment_manifest import TaskSelector
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.backends.local import make_stub_solve_fn
from aec_bench.evolution.engine import AECEvolutionEngine
from aec_bench.evolution.orchestrator import EvolutionOrchestrator
from aec_bench.evolution.workspace import Workspace
from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Helpers (minimal stubs mirroring test_orchestrator.py patterns)
# ---------------------------------------------------------------------------


def _scaffold_workspace(root: Path) -> Path:
    """Create the minimal directory structure for a valid Workspace."""
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "archive-test-ws",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts"],
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    prompts_dir = root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are an engineering agent.")
    return root


class _StubClassifierLLM:
    """Return minimal valid bond-type JSON for any prompt."""

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:
        return '{"classifications": []}'


class _StubEvolverLLM:
    """Return a no-op evolver response."""

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:
        return "No changes needed."


def _make_config(
    *,
    max_cycles: int = 1,
    workspace_path: str = "/tmp/archive-test",
) -> EvolutionConfig:
    return EvolutionConfig(
        workspace_path=workspace_path,
        models={"classifier": "claude-haiku-4", "evolver": "claude-sonnet-4-6"},
        task_selector=TaskSelector(),
        max_cycles=max_cycles,
        batch_size=1,
        stagnation_window=5,
    )


def _make_engine() -> AECEvolutionEngine:
    return AECEvolutionEngine(
        classifier_llm=_StubClassifierLLM(),
        evolver_llm=_StubEvolverLLM(),
    )


def _make_record(reward: float = 0.7) -> TrialRecord:
    return make_trial_record(
        task={"task_id": "electrical/voltage-drop/test", "task_revision": "abc123"},
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
# Tests
# ---------------------------------------------------------------------------


class TestEvolutionResultArchiveSummary:
    """Verifies that EvolutionResult carries the QD archive_summary field."""

    def test_evolution_result_accepts_archive_summary(self) -> None:
        """EvolutionResult can be constructed with archive_summary as a dict."""
        result = EvolutionResult(
            run_id="test-run-001",
            workspace_name="test-ws",
            cycles_completed=1,
            final_score=0.7,
            best_score=0.7,
            best_workspace_version="evo-v1",
            score_history=[0.7],
            converged=False,
            total_trials=1,
            cycle_records=[],
            archive_summary={
                "size": 3,
                "n_centroids": 200,
                "coverage": 0.015,
                "best_reward": 0.9,
                "mean_reward": 0.7,
                "bd_dimensions": ["token_cost", "reward"],
            },
        )
        assert result.archive_summary is not None
        assert result.archive_summary["size"] == 3
        assert result.archive_summary["n_centroids"] == 200

    def test_evolution_result_archive_summary_defaults_to_none(self) -> None:
        """archive_summary is optional and defaults to None."""
        result = EvolutionResult(
            run_id="test-run-002",
            workspace_name="test-ws",
            cycles_completed=0,
            final_score=0.0,
            best_score=0.0,
            best_workspace_version="evo-v0",
            score_history=[],
            converged=False,
            total_trials=0,
            cycle_records=[],
        )
        assert result.archive_summary is None

    def test_orchestrator_populates_archive_summary(self, tmp_path: Path) -> None:
        """Orchestrator.run() returns an EvolutionResult with archive_summary populated."""
        from aec_bench.evolution.strategy import QDStrategy

        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        records = [_make_record(0.75)]
        solve_fn = make_stub_solve_fn(records)

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=solve_fn,
            config=_make_config(max_cycles=1),
            strategy=QDStrategy(evolver_model="claude-sonnet-4-6"),
        )

        result = orchestrator.run()

        assert result.archive_summary is not None
        assert "archive_summary" in result.archive_summary
        summary = result.archive_summary["archive_summary"]
        assert "size" in summary
        assert "n_centroids" in summary
        assert "coverage" in summary
        assert "best_reward" in summary
        assert "mean_reward" in summary
        assert summary["n_centroids"] == 200

    def test_archive_summary_size_grows_with_cycles(self, tmp_path: Path) -> None:
        """Archive accumulates entries across multiple cycles."""
        from aec_bench.evolution.strategy import QDStrategy

        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        # Vary rewards so each cycle's BD vector occupies a distinct cell.
        rewards = [0.3, 0.6, 0.9]
        call_idx = [0]

        from aec_bench.contracts.evolution import WorkspaceSnapshot

        def vary_solve(snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
            reward = rewards[min(call_idx[0], len(rewards) - 1)]
            call_idx[0] += 1
            return [_make_record(reward)]

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=vary_solve,
            config=_make_config(max_cycles=3),
            strategy=QDStrategy(evolver_model="claude-sonnet-4-6"),
        )

        result = orchestrator.run()

        assert result.archive_summary is not None
        # At least one entry must have been inserted across 3 cycles.
        summary = result.archive_summary["archive_summary"]
        assert summary["size"] >= 1
