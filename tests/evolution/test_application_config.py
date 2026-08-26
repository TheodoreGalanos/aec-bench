# ABOUTME: Tests configuration-based functional evolution composition.
# ABOUTME: Verifies workspace, evaluator, engine, strategy, and remote runtime wiring.

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolutionResult,
    EvolverModelConfig,
    TaskGenerateConfig,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, ClientConfig, TaskSelector
from aec_bench.evolution import application
from aec_bench.evolution.application import (
    _build_harbor_candidate_runtime,
    run_evolution_from_config,
)
from aec_bench.generation.application import generate_template_instances, resolve_template
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.ledger.writer import write_trial_record
from tests.support.trial_record_factories import make_trial_record


def _scaffold_workspace(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "runner-test",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    (root / "prompts").mkdir()
    (root / "prompts" / "system.md").write_text("You are an engineering agent.")
    return root


def _capture_run(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], EvolutionResult]:
    observed: dict[str, Any] = {}
    expected = EvolutionResult(
        run_id="evo-test",
        workspace_name="runner-test",
        cycles_completed=0,
        final_score=0.0,
        best_score=0.0,
        best_candidate_id="baseline",
        score_history=[],
        converged=False,
        total_trials=0,
        cycle_records=[],
    )

    def fake_run_evolution(**kwargs: Any) -> EvolutionResult:
        observed.update(kwargs)
        return expected

    monkeypatch.setattr(application, "run_evolution", fake_run_evolution)
    return observed, expected


class TestRunEvolutionFromConfig:
    def test_composes_one_agentic_variation_operator_with_development_runtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observed, expected = _capture_run(monkeypatch)
        ws_root = _scaffold_workspace(tmp_path / "ws")
        builder: dict[str, Any] = {}

        def fake_builder(**kwargs: Any):
            builder.update(kwargs)
            return lambda _request, _source, _child_id: None

        monkeypatch.setattr(application, "build_agentic_variation_operator", fake_builder)
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )

        result = run_evolution_from_config(config=config, run_id="run/with unsafe spaces")

        assert result is expected
        assert builder["agent_model"] == "sonnet"
        assert builder["supervisor_model"] == builder["agent_model"]
        assert builder["supervisor_model_identity"] == "sonnet"
        assert builder["development_batch_size"] == config.batch_size
        assert callable(builder["development_batch_planner"])
        assert callable(builder["development_evaluator"])
        assert "budget" not in builder
        assert builder["checkpoint_root"] == ws_root
        identity = builder["configuration_identity"]
        assert identity.model_identity == "sonnet"
        assert identity.development_evaluator_identity.startswith("local:")
        assert "run/with unsafe spaces" not in identity.development_evaluator_identity
        assert observed["run_id"] == "run/with unsafe spaces"
        assert callable(observed["variation"])

    def test_runs_from_config_with_solver(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        observed, expected = _capture_run(monkeypatch)
        ws_root = _scaffold_workspace(tmp_path / "ws")
        # Create a task dir so resolution finds something
        tasks_root = tmp_path / "tasks"
        task_dir = tasks_root / "electrical" / "voltage-drop" / "test-instance"
        task_dir.mkdir(parents=True)
        (task_dir / "instruction.md").write_text("Calculate voltage drop.")

        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(domains=["electrical"]),
            solver=AgentConfig(
                name="evo-solver",
                adapter="rlm",
                model="claude-sonnet-4-20250514",
                client=ClientConfig(kind="anthropic"),
            ),
            backend="local",
            max_cycles=3,
        )
        result = run_evolution_from_config(
            config=config,
            tasks_root=tasks_root,
        )
        assert result is expected
        assert observed["config"].max_cycles == 3
        assert callable(observed["evaluate"])

    def test_without_solver_uses_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        observed, expected = _capture_run(monkeypatch)
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        result = run_evolution_from_config(config=config)
        assert result is expected
        assert callable(observed["evaluate"])

    def test_builds_workspace_with_no_tasks_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        observed, _expected = _capture_run(monkeypatch)
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        run_evolution_from_config(config=config)
        assert observed["workspace"].manifest.name == "runner-test"

    def test_accepts_report_writer_from_the_composition_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observed, _expected = _capture_run(monkeypatch)
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )

        def write_report(workspace_root: Path) -> Path:
            return workspace_root / "evolution-report.html"

        run_evolution_from_config(config=config, report_writer=write_report)

        assert observed["report_writer"] is write_report


class TestBuildEvolutionRunnerRemoteExecution:
    """Tests remote evolution wiring without contacting a provider."""

    def test_undocumented_harbor_backend_alias_is_rejected(self, tmp_path: Path) -> None:
        ws_root = _scaffold_workspace(tmp_path / "ws")
        with pytest.raises(ValueError, match="Input should be 'local', 'modal' or 'morph'"):
            EvolutionConfig(
                workspace_path=str(ws_root),
                models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
                task_selector=TaskSelector(),
                backend="harbor",  # type: ignore[arg-type]
            )

    def test_modal_without_solver_warns_and_stubs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        observed, _expected = _capture_run(monkeypatch)
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            backend="modal",
            # No solver = stubs
        )
        run_evolution_from_config(config=config)
        assert callable(observed["evaluate"])

    def test_morph_without_solver_warns_and_stubs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        observed, _expected = _capture_run(monkeypatch)
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            backend="morph",
        )
        run_evolution_from_config(config=config)
        assert callable(observed["evaluate"])

    def test_morph_with_solver_builds_remote_evaluator_without_connecting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observed, _expected = _capture_run(monkeypatch)
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            solver=AgentConfig(
                name="evo-solver",
                adapter="direct",
                model="replay-direct",
                client=ClientConfig(kind="replay", settings={"output_text": '{"findings": []}'}),
            ),
            backend="morph",
        )
        run_evolution_from_config(config=config)
        assert callable(observed["evaluate"])

    def test_remote_solve_consumes_the_current_harbor_workflow(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workspace = _scaffold_workspace(tmp_path / "ws")
        task_dir = tmp_path / "tasks" / "electrical" / "voltage-drop" / "demo"
        (task_dir / "environment").mkdir(parents=True)
        (task_dir / "tests").mkdir()
        (task_dir / "task.toml").write_text('[metadata]\ndifficulty = "easy"\n', encoding="utf-8")
        (task_dir / "instruction.md").write_text(
            "Calculate voltage drop and write /workspace/output.md.",
            encoding="utf-8",
        )
        (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
        (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        record = make_trial_record(experiment_id="evo-current-harbor")
        ledger_path = write_trial_record(ledger_root=workspace / "artifacts" / "ledger", record=record)
        observed: dict[str, Any] = {}

        def fake_run(_workflow: SynchronousHarborWorkflow, **kwargs: Any) -> SimpleNamespace:
            observed.update(kwargs)
            return SimpleNamespace(
                import_result=SimpleNamespace(ledger_paths=[ledger_path]),
            )

        monkeypatch.setattr(SynchronousHarborWorkflow, "run", fake_run)
        config = EvolutionConfig(
            workspace_path=str(workspace),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            solver=AgentConfig(
                name="evo-solver",
                adapter="direct",
                model="replay-direct",
                client=ClientConfig(kind="replay", settings={"output_text": "done"}),
            ),
            backend="morph",
        )
        planner, evaluate = _build_harbor_candidate_runtime(
            config=config,
            task_dirs=[task_dir],
            experiment_id="evo-current-harbor",
        )

        batch = planner(1, 0)
        records = evaluate(
            WorkspaceSnapshot(
                system_prompt="Use the evolved instructions.",
                candidate_id="run:1",
            ),
            batch,
        )

        assert [item.model_dump(mode="json") for item in records] == [record.model_dump(mode="json")]
        assert observed["manifest"].compute.backend == "morph"
        assert observed["resolved_tasks"][0].task_id == "electrical/voltage-drop/demo"
        assert observed["task_path_overrides"] == {
            "electrical/voltage-drop/demo": task_dir.resolve(),
        }
        assert "Use the evolved instructions." in observed["manifest"].agents[0].system_prompt
        assert not (task_dir / "system_prompt.md").exists()


class TestResolveTemplate:
    def test_resolves_builtin_by_name(self) -> None:
        template = resolve_template("voltage-drop")
        assert template.path.is_dir()
        assert (template.path / "params.toml").exists()
        assert (template.path / "engine.py").exists()

    def test_resolves_by_path(self, tmp_path: Path) -> None:
        template = tmp_path / "my-template"
        template.mkdir()
        (template / "params.toml").write_text(
            "[meta]\n"
            "name = 'test'\n"
            "description = 'Test template'\n"
            "discipline = 'electrical'\n"
            "category = 'reasoning'\n"
            "tool_mode = 'no-tool'\n"
        )
        (template / "instruction.md").write_text("Do the task.\n")
        (template / "engine.py").write_text("def compute(params):\n    return {}\n")
        loaded = resolve_template(str(template))
        assert loaded.path == template

    def test_raises_for_unknown_name(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            resolve_template("nonexistent-template-xyz")


class TestRunnerStrategyWiring:
    def test_config_passes_qd_mode_to_functional_application(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When config.strategy='qd', composition leaves selection to the application."""
        observed, _expected = _capture_run(monkeypatch)

        ws_path = tmp_path / "ws"
        ws_path.mkdir()
        (ws_path / "prompts").mkdir()
        (ws_path / "prompts" / "system.md").write_text("agent")
        (ws_path / "manifest.yaml").write_text(
            yaml.dump({"name": "test", "agent_adapter": "rlm", "evolvable_layers": ["prompts"]})
        )

        config = EvolutionConfig(
            workspace_path=str(ws_path),
            models=EvolverModelConfig(classifier="claude-haiku-4", evolver="claude-sonnet-4-6"),
            task_selector=TaskSelector(),
            strategy="qd",
        )

        run_evolution_from_config(config=config)
        assert observed["config"].strategy == "qd"
        assert "strategy" not in observed

    def test_config_passes_hill_climb_mode_to_functional_application(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default config leaves direct hill-climb selection to the application state."""
        observed, _expected = _capture_run(monkeypatch)

        ws_path = tmp_path / "ws"
        ws_path.mkdir()
        (ws_path / "prompts").mkdir()
        (ws_path / "prompts" / "system.md").write_text("agent")
        (ws_path / "manifest.yaml").write_text(
            yaml.dump({"name": "test", "agent_adapter": "rlm", "evolvable_layers": ["prompts"]})
        )

        config = EvolutionConfig(
            workspace_path=str(ws_path),
            models=EvolverModelConfig(classifier="claude-haiku-4", evolver="claude-sonnet-4-6"),
            task_selector=TaskSelector(),
        )

        run_evolution_from_config(config=config)
        assert observed["config"].strategy == "hill_climb"
        assert "strategy" not in observed


class TestGenerateTaskInstances:
    def test_generates_correct_count(self, tmp_path: Path) -> None:
        gen_config = TaskGenerateConfig(
            template="voltage-drop",
            count=3,
            seed=42,
            difficulties=["easy"],
        )
        generated = generate_template_instances(
            template=resolve_template(gen_config.template),
            output_root=tmp_path / "generated",
            count=gen_config.count,
            difficulties=tuple(gen_config.difficulties),
            seed=gen_config.seed,
        )
        dirs = generated.task_paths
        assert len(dirs) == 3
        for d in dirs:
            assert d.is_dir()
            assert (d / "instruction.md").exists()
            assert (d / "tests" / "verify.py").exists()

    def test_cycles_through_difficulties(self, tmp_path: Path) -> None:
        gen_config = TaskGenerateConfig(
            template="voltage-drop",
            count=4,
            seed=42,
            difficulties=["easy", "medium"],
        )
        dirs = generate_template_instances(
            template=resolve_template(gen_config.template),
            output_root=tmp_path / "generated",
            count=gen_config.count,
            difficulties=tuple(gen_config.difficulties),
            seed=gen_config.seed,
        ).task_paths
        assert len(dirs) == 4

    def test_different_seeds_produce_different_instances(self, tmp_path: Path) -> None:
        gen1 = TaskGenerateConfig(template="voltage-drop", count=1, seed=1, difficulties=["easy"])
        gen2 = TaskGenerateConfig(template="voltage-drop", count=1, seed=99, difficulties=["easy"])
        dirs1 = generate_template_instances(
            template=resolve_template(gen1.template),
            output_root=tmp_path / "seed-1",
            count=gen1.count,
            difficulties=tuple(gen1.difficulties),
            seed=gen1.seed,
        ).task_paths
        dirs2 = generate_template_instances(
            template=resolve_template(gen2.template),
            output_root=tmp_path / "seed-2",
            count=gen2.count,
            difficulties=tuple(gen2.difficulties),
            seed=gen2.seed,
        ).task_paths
        # Different seeds should produce different instance names (different parameters)
        content1 = (dirs1[0] / "instruction.md").read_text()
        content2 = (dirs2[0] / "instruction.md").read_text()
        assert content1 != content2
