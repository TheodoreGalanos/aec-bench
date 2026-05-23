# ABOUTME: End-to-end test for the evolution loop from orchestrator through engine.
# ABOUTME: Proves skills appear in workspace after evolution cycles with pattern detection.

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    GateDecision,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import TaskSelector
from aec_bench.contracts.trial_record import TrialRecord
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
        "name": "e2e-test",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    (root / "prompts").mkdir()
    (root / "prompts" / "system.md").write_text("You are an engineering agent.")
    return root


class _StubClassifier:
    """Return execution bond type for all turn indices found in the prompt."""

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


class _StubEvolver:
    """Return a skill creation action for every evolution call."""

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        return json.dumps(
            {
                "actions": [
                    {
                        "type": "write_skill",
                        "name": "evolved-engineering-reference",
                        "description": "Engineering formulas reference from evolution",
                        "discipline": "electrical",
                        "body": ("## Engineering Reference\n\nKey formulas for voltage drop calculations."),
                    }
                ],
                "reasoning": "Adding engineering reference based on analysis.",
            }
        )


def _make_solve_fn(reward: float = 0.5):
    """Create a solve function that returns trial records with the given reward."""

    def solve(snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
        records = []
        for i in range(batch_size):
            records.append(
                make_trial_record(
                    trial_id=f"trial-e2e-{i}",
                    evaluation={
                        "reward": reward,
                        "validity": {
                            "output_parseable": True,
                            "schema_valid": True,
                            "verifier_completed": True,
                        },
                        "breakdown": {"voltage_drop_v": 1.0, "compliance": 0.0},
                    },
                )
            )
        return records

    return solve


def _make_config(
    *,
    max_cycles: int = 3,
    batch_size: int = 2,
    improvement_threshold: float = 0.02,
    stagnation_window: int = 5,
    workspace_path: str = "/tmp/e2e-ws",
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
        classifier_llm=_StubClassifier(),
        evolver_llm=_StubEvolver(),
    )


# ---------------------------------------------------------------------------
# TestEndToEnd
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """End-to-end tests for the full evolution loop from orchestrator through engine."""

    def test_full_evolution_loop(self, tmp_path: Path) -> None:
        """Run orchestrator with 3 cycles; verify result structure, skills, and gate."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=_make_solve_fn(reward=0.5),
            config=_make_config(
                max_cycles=3,
                batch_size=2,
                stagnation_window=5,
                workspace_path=str(root),
            ),
        )

        result = orchestrator.run()

        assert result.cycles_completed == 3
        assert len(result.score_history) == 3
        assert result.workspace_name == "e2e-test"

        # Skills should appear in the workspace (from auto-seeding or evolver mutations)
        skills = ws.list_skills()
        assert len(skills) > 0, "Expected at least one skill after 3 evolution cycles"

        # At least one cycle should have been accepted
        accepted_cycles = [cr for cr in result.cycle_records if cr.gate_decision == GateDecision.ACCEPTED]
        assert len(accepted_cycles) >= 1

    def test_evolution_creates_git_tags(self, tmp_path: Path) -> None:
        """After running 3 cycles, workspace should have evo-* version tags."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=_make_solve_fn(reward=0.5),
            config=_make_config(
                max_cycles=3,
                batch_size=2,
                stagnation_window=5,
                workspace_path=str(root),
            ),
        )

        orchestrator.run()

        versions = ws.list_versions()
        version_tags = {v.tag for v in versions}

        # evo-0 is the initial tag, evo-1, evo-2, evo-3 are the cycle tags
        assert "evo-0" in version_tags
        assert len(versions) >= 2, f"Expected at least 2 version tags, got: {version_tags}"

    def test_hill_climb_evolution_loop(self, tmp_path: Path) -> None:
        """Run orchestrator with hill_climb strategy; verify score tracking."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        from aec_bench.evolution.strategy import HillClimbStrategy

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=_make_solve_fn(reward=0.5),
            config=_make_config(
                max_cycles=3,
                batch_size=2,
                stagnation_window=5,
                workspace_path=str(root),
            ),
            strategy=HillClimbStrategy(),
        )

        result = orchestrator.run()

        assert result.cycles_completed == 3
        assert len(result.score_history) == 3
        # Hill climb doesn't create archive.json
        assert not (root / "archive.json").exists()
        # But graveyard.json should be saved
        assert (root / "graveyard.json").exists()

    def test_evolution_converges_on_high_reward(self, tmp_path: Path) -> None:
        """High reward (0.95) with stagnation_window=2 causes early convergence."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        orchestrator = EvolutionOrchestrator(
            workspace=ws,
            engine=_make_engine(),
            solve_fn=_make_solve_fn(reward=0.95),
            config=_make_config(
                max_cycles=10,
                batch_size=2,
                improvement_threshold=0.02,
                stagnation_window=2,
                workspace_path=str(root),
            ),
        )

        result = orchestrator.run()

        assert result.converged is True
        assert result.cycles_completed < 10
