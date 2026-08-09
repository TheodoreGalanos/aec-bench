# ABOUTME: Tests for the evolution runner entry point.
# ABOUTME: Verifies the runner wires workspace, engine, and orchestrator correctly.

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolverModelConfig,
    TaskGenerateConfig,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, ClientConfig, TaskSelector
from aec_bench.evolution.runner import (
    _build_harbor_solve_fn,
    _resolve_template,
    build_evolution_runner,
    build_evolution_runner_from_config,
    generate_task_instances,
)
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
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


class TestBuildEvolutionRunner:
    def test_returns_orchestrator(self, tmp_path: Path) -> None:
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(
                classifier="claude-haiku-4-5-20251001",
                evolver="claude-sonnet-4-20250514",
            ),
            task_selector=TaskSelector(),
            max_cycles=2,
        )
        runner = build_evolution_runner(config=config, task_dirs=[], model="claude-haiku-4-5-20251001")
        assert hasattr(runner, "run")
        assert runner._workspace.manifest.name == "runner-test"
        assert runner._config.max_cycles == 2

    def test_with_task_dirs(self, tmp_path: Path) -> None:
        ws_root = _scaffold_workspace(tmp_path / "ws")
        task_dir = tmp_path / "tasks" / "electrical" / "voltage-drop"
        task_dir.mkdir(parents=True)
        (task_dir / "instruction.md").write_text("Calculate voltage drop.")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        runner = build_evolution_runner(config=config, task_dirs=[task_dir], model="haiku")
        assert hasattr(runner, "run")

    def test_workspace_has_versioning(self, tmp_path: Path) -> None:
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        runner = build_evolution_runner(config=config, task_dirs=[], model="haiku")
        versions = runner._workspace.list_versions()
        assert any(v.tag == "evo-0" for v in versions)


class TestBuildEvolutionRunnerFromConfig:
    def test_builds_from_config_with_solver(self, tmp_path: Path) -> None:
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
        runner = build_evolution_runner_from_config(
            config=config,
            tasks_root=tasks_root,
        )
        assert hasattr(runner, "run")
        assert runner._config.max_cycles == 3

    def test_builds_without_solver_uses_defaults(self, tmp_path: Path) -> None:
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        runner = build_evolution_runner_from_config(config=config)
        assert hasattr(runner, "run")

    def test_builds_with_no_tasks_root(self, tmp_path: Path) -> None:
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        runner = build_evolution_runner_from_config(config=config)
        assert runner._workspace.manifest.name == "runner-test"

    def test_accepts_report_writer_from_the_composition_root(self, tmp_path: Path) -> None:
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )

        def write_report(workspace_root: Path) -> Path:
            return workspace_root / "evolution-report.html"

        runner = build_evolution_runner_from_config(config=config, report_writer=write_report)

        assert runner._report_writer is write_report


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

    def test_modal_without_solver_warns_and_stubs(self, tmp_path: Path) -> None:
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            backend="modal",
            # No solver = stubs
        )
        runner = build_evolution_runner_from_config(config=config)
        assert hasattr(runner, "run")

    def test_morph_without_solver_warns_and_stubs(self, tmp_path: Path) -> None:
        ws_root = _scaffold_workspace(tmp_path / "ws")
        config = EvolutionConfig(
            workspace_path=str(ws_root),
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            backend="morph",
        )
        runner = build_evolution_runner_from_config(config=config)
        assert hasattr(runner, "run")

    def test_morph_with_solver_builds_remote_solve_fn_without_connecting(self, tmp_path: Path) -> None:
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
        runner = build_evolution_runner_from_config(config=config)
        assert callable(runner._solve_fn)

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
        ledger_path = tmp_path / "ledger-record.json"
        ledger_path.write_text(record.model_dump_json(), encoding="utf-8")
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
        solve = _build_harbor_solve_fn(
            config=config,
            task_dirs=[task_dir],
            experiment_id="evo-current-harbor",
        )

        records = solve(
            WorkspaceSnapshot(
                system_prompt="Use the evolved instructions.",
                workspace_version="evo-1",
            ),
            1,
        )

        assert records == [record]
        assert observed["manifest"].compute.backend == "morph"
        assert observed["resolved_tasks"][0].task_id == "electrical/voltage-drop/demo"
        assert observed["task_path_overrides"] == {
            "electrical/voltage-drop/demo": task_dir.resolve(),
        }
        assert "Use the evolved instructions." in (task_dir / "system_prompt.md").read_text(encoding="utf-8")


class TestResolveTemplate:
    def test_resolves_builtin_by_name(self) -> None:
        path = _resolve_template("voltage-drop")
        assert path.is_dir()
        assert (path / "params.toml").exists()
        assert (path / "engine.py").exists()

    def test_resolves_by_path(self, tmp_path: Path) -> None:
        template = tmp_path / "my-template"
        template.mkdir()
        (template / "params.toml").write_text("[meta]\nname = 'test'\n")
        path = _resolve_template(str(template))
        assert path == template

    def test_raises_for_unknown_name(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            _resolve_template("nonexistent-template-xyz")


class TestRunnerStrategyWiring:
    def test_runner_builds_qd_strategy_from_config(self, tmp_path: Path) -> None:
        """When config.strategy='qd', runner creates QDStrategy."""
        from aec_bench.evolution.strategy import QDStrategy

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

        runner = build_evolution_runner_from_config(config=config)
        assert isinstance(runner._strategy, QDStrategy)

    def test_runner_builds_hill_climb_by_default(self, tmp_path: Path) -> None:
        """Default config builds HillClimbStrategy."""
        from aec_bench.evolution.strategy import HillClimbStrategy

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

        runner = build_evolution_runner_from_config(config=config)
        assert isinstance(runner._strategy, HillClimbStrategy)


class TestGenerateTaskInstances:
    def test_generates_correct_count(self) -> None:
        gen_config = TaskGenerateConfig(
            template="voltage-drop",
            count=3,
            seed=42,
            difficulties=["easy"],
        )
        dirs = generate_task_instances(gen_config)
        assert len(dirs) == 3
        for d in dirs:
            assert d.is_dir()
            assert (d / "instruction.md").exists()
            assert (d / "tests" / "verify.py").exists()

    def test_cycles_through_difficulties(self) -> None:
        gen_config = TaskGenerateConfig(
            template="voltage-drop",
            count=4,
            seed=42,
            difficulties=["easy", "medium"],
        )
        dirs = generate_task_instances(gen_config)
        assert len(dirs) == 4

    def test_different_seeds_produce_different_instances(self) -> None:
        gen1 = TaskGenerateConfig(template="voltage-drop", count=1, seed=1, difficulties=["easy"])
        gen2 = TaskGenerateConfig(template="voltage-drop", count=1, seed=99, difficulties=["easy"])
        dirs1 = generate_task_instances(gen1)
        dirs2 = generate_task_instances(gen2)
        # Different seeds should produce different instance names (different parameters)
        content1 = (dirs1[0] / "instruction.md").read_text()
        content2 = (dirs2[0] / "instruction.md").read_text()
        assert content1 != content2
