# ABOUTME: Tests for evolution config YAML loading and task directory resolution.
# ABOUTME: Covers YAML parsing, field mapping, and task selector resolution.

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from aec_bench.contracts.evolution import EvolutionConfig, EvolverModelConfig, TaskGenerateConfig
from aec_bench.contracts.experiment_manifest import TaskSelector
from aec_bench.evolution.config_loader import (
    load_evolution_config,
    merge_harness_config,
    resolve_task_dirs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.dump(data))
    return path


def _create_task(root: Path, task_id: str) -> Path:
    task_dir = root / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "instruction.md").write_text(f"Task: {task_id}")
    return task_dir


# ---------------------------------------------------------------------------
# TestLoadEvolutionConfig
# ---------------------------------------------------------------------------


class TestLoadEvolutionConfig:
    def test_loads_minimal_yaml(self, tmp_path: Path) -> None:
        data = {
            "workspace_path": "workspaces/test",
            "models": {
                "classifier": "claude-haiku-4-5-20251001",
                "evolver": "claude-sonnet-4-20250514",
            },
            "tasks": {},
        }
        config_file = _write_yaml(tmp_path / "evolution.yaml", data)

        config = load_evolution_config(config_file)

        assert config.workspace_path == "workspaces/test"
        assert config.models.classifier == "claude-haiku-4-5-20251001"
        assert config.models.evolver == "claude-sonnet-4-20250514"
        assert config.task_selector.domains == []

    def test_loads_full_yaml(self, tmp_path: Path) -> None:
        data = {
            "workspace_path": "workspaces/electrical-agent",
            "models": {
                "classifier": "claude-haiku-4-5-20251001",
                "evolver": "claude-sonnet-4-20250514",
            },
            "solver": {
                "name": "evolution-solver",
                "adapter": "rlm",
                "model": "claude-sonnet-4-20250514",
                "client": {"kind": "anthropic"},
            },
            "tasks": {
                "domains": ["electrical"],
            },
            "backend": "local",
            "batch_size": 5,
            "max_cycles": 10,
            "timeout": 1800,
        }
        config_file = _write_yaml(tmp_path / "evolution.yaml", data)

        config = load_evolution_config(config_file)

        assert config.workspace_path == "workspaces/electrical-agent"
        assert config.solver is not None
        assert config.solver.name == "evolution-solver"
        assert config.solver.adapter == "rlm"
        assert config.solver.client is not None
        assert config.solver.client.kind == "anthropic"
        assert config.backend == "local"
        assert config.batch_size == 5
        assert config.max_cycles == 10
        assert config.timeout == 1800

    def test_tasks_key_maps_to_task_selector(self, tmp_path: Path) -> None:
        data = {
            "workspace_path": "workspaces/test",
            "models": {
                "classifier": "claude-haiku-4-5-20251001",
                "evolver": "claude-sonnet-4-20250514",
            },
            "tasks": {
                "domains": ["civil", "electrical"],
                "include_patterns": ["*/voltage-*"],
            },
        }
        config_file = _write_yaml(tmp_path / "evolution.yaml", data)

        config = load_evolution_config(config_file)

        assert config.task_selector.domains == ["civil", "electrical"]
        assert config.task_selector.include_patterns == ["*/voltage-*"]

    def test_missing_required_fields_raises(self, tmp_path: Path) -> None:
        # workspace_path is required
        data = {
            "models": {
                "classifier": "claude-haiku-4-5-20251001",
                "evolver": "claude-sonnet-4-20250514",
            },
            "tasks": {},
        }
        config_file = _write_yaml(tmp_path / "evolution.yaml", data)

        with pytest.raises(ValidationError):
            load_evolution_config(config_file)


# ---------------------------------------------------------------------------
# TestResolveTaskDirs
# ---------------------------------------------------------------------------


class TestResolveTaskDirs:
    def test_finds_task_dirs_by_instruction(self, tmp_path: Path) -> None:
        _create_task(tmp_path, "electrical/voltage-drop")

        selector = TaskSelector()
        result = resolve_task_dirs(selector, tmp_path)

        assert len(result) == 1
        assert result[0] == tmp_path / "electrical" / "voltage-drop"

    def test_filters_by_domain(self, tmp_path: Path) -> None:
        _create_task(tmp_path, "electrical/voltage-drop")
        _create_task(tmp_path, "electrical/cable-sizing")
        _create_task(tmp_path, "civil/pavement-design")

        selector = TaskSelector(domains=["electrical"])
        result = resolve_task_dirs(selector, tmp_path)

        assert len(result) == 2
        for path in result:
            assert path.relative_to(tmp_path).parts[0] == "electrical"

    def test_include_patterns(self, tmp_path: Path) -> None:
        _create_task(tmp_path, "electrical/voltage-drop")
        _create_task(tmp_path, "electrical/cable-sizing")
        _create_task(tmp_path, "civil/pavement-design")

        selector = TaskSelector(include_patterns=["electrical/*"])
        result = resolve_task_dirs(selector, tmp_path)

        assert len(result) == 2
        for path in result:
            assert path.relative_to(tmp_path).parts[0] == "electrical"

    def test_empty_selector_returns_all(self, tmp_path: Path) -> None:
        _create_task(tmp_path, "electrical/voltage-drop")
        _create_task(tmp_path, "civil/pavement-design")
        _create_task(tmp_path, "ground/slope-stability")

        selector = TaskSelector()
        result = resolve_task_dirs(selector, tmp_path)

        assert len(result) == 3

    def test_no_tasks_returns_empty(self, tmp_path: Path) -> None:
        selector = TaskSelector()
        result = resolve_task_dirs(selector, tmp_path)

        assert result == []

    def test_exclude_patterns(self, tmp_path: Path) -> None:
        _create_task(tmp_path, "electrical/voltage-drop")
        _create_task(tmp_path, "electrical/cable-sizing")
        _create_task(tmp_path, "civil/pavement-design")

        selector = TaskSelector(exclude_patterns=["civil/*"])
        result = resolve_task_dirs(selector, tmp_path)

        assert len(result) == 2
        for path in result:
            assert path.relative_to(tmp_path).parts[0] == "electrical"

    def test_finds_task_dirs_by_task_toml(self, tmp_path: Path) -> None:
        task_dir = tmp_path / "electrical" / "fault-current"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text("[task]\nid = 'fault-current'")

        selector = TaskSelector()
        result = resolve_task_dirs(selector, tmp_path)

        assert len(result) == 1
        assert result[0] == task_dir

    def test_returns_sorted_paths(self, tmp_path: Path) -> None:
        _create_task(tmp_path, "electrical/z-task")
        _create_task(tmp_path, "electrical/a-task")
        _create_task(tmp_path, "civil/m-task")

        selector = TaskSelector()
        result = resolve_task_dirs(selector, tmp_path)

        assert result == sorted(result)


# ---------------------------------------------------------------------------
# TestMergeHarnessConfig
# ---------------------------------------------------------------------------


class TestMergeHarnessConfig:
    def test_no_harness_config_returns_unchanged(self) -> None:
        config = EvolutionConfig(
            workspace_path="/tmp/ws",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        result = merge_harness_config(config, config_dir=Path("/tmp"))
        assert result.solver is None
        assert result.backend == "local"

    def test_merges_solver_from_manifest(self, tmp_path: Path) -> None:
        manifest_data = {
            "experiment_id": "exp-001",
            "name": "test experiment",
            "tasks": {},
            "agents": [
                {
                    "name": "test-agent",
                    "adapter": "rlm",
                    "model": "claude-sonnet-4-20250514",
                    "client": {"kind": "anthropic"},
                }
            ],
            "compute": {"backend": "modal"},
        }
        manifest_path = tmp_path / "experiment.yaml"
        manifest_path.write_text(yaml.dump(manifest_data))

        config = EvolutionConfig(
            workspace_path="/tmp/ws",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            harness_config="experiment.yaml",
        )
        result = merge_harness_config(config, config_dir=tmp_path)
        assert result.solver is not None
        assert result.solver.model == "claude-sonnet-4-20250514"
        assert result.backend == "modal"

    def test_explicit_solver_not_overridden(self, tmp_path: Path) -> None:
        manifest_data = {
            "experiment_id": "exp-001",
            "name": "test",
            "tasks": {},
            "agents": [{"name": "manifest-agent", "adapter": "rlm", "model": "opus", "client": {"kind": "anthropic"}}],
            "compute": {"backend": "modal"},
        }
        (tmp_path / "experiment.yaml").write_text(yaml.dump(manifest_data))

        from aec_bench.contracts.experiment_manifest import AgentConfig, ClientConfig

        config = EvolutionConfig(
            workspace_path="/tmp/ws",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            harness_config="experiment.yaml",
            solver=AgentConfig(
                name="my-solver",
                adapter="tool_loop",
                model="haiku",
                client=ClientConfig(kind="anthropic"),
            ),
        )
        result = merge_harness_config(config, config_dir=tmp_path)
        assert result.solver.model == "haiku"
        assert result.solver.adapter == "tool_loop"

    def test_merges_backend_from_manifest(self, tmp_path: Path) -> None:
        manifest_data = {
            "experiment_id": "exp-001",
            "name": "test",
            "tasks": {},
            "agents": [{"name": "a", "adapter": "rlm", "model": "m", "client": {"kind": "anthropic"}}],
            "compute": {"backend": "modal"},
        }
        (tmp_path / "experiment.yaml").write_text(yaml.dump(manifest_data))

        config = EvolutionConfig(
            workspace_path="/tmp/ws",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            harness_config="experiment.yaml",
        )
        result = merge_harness_config(config, config_dir=tmp_path)
        assert result.backend == "modal"

    def test_merges_timeout_from_manifest(self, tmp_path: Path) -> None:
        manifest_data = {
            "experiment_id": "exp-001",
            "name": "test",
            "tasks": {},
            "agents": [{"name": "a", "adapter": "rlm", "model": "m", "client": {"kind": "anthropic"}}],
            "compute": {"backend": "modal", "timeout_override": 3600},
        }
        (tmp_path / "experiment.yaml").write_text(yaml.dump(manifest_data))

        config = EvolutionConfig(
            workspace_path="/tmp/ws",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            harness_config="experiment.yaml",
        )
        result = merge_harness_config(config, config_dir=tmp_path)
        assert result.timeout == 3600

    def test_explicit_timeout_not_overridden(self, tmp_path: Path) -> None:
        manifest_data = {
            "experiment_id": "exp-001",
            "name": "test",
            "tasks": {},
            "agents": [{"name": "a", "adapter": "rlm", "model": "m", "client": {"kind": "anthropic"}}],
            "compute": {"backend": "modal", "timeout_override": 3600},
        }
        (tmp_path / "experiment.yaml").write_text(yaml.dump(manifest_data))

        config = EvolutionConfig(
            workspace_path="/tmp/ws",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            harness_config="experiment.yaml",
            timeout=900,
        )
        result = merge_harness_config(config, config_dir=tmp_path)
        # 900 is not the default (1800), so it should be preserved
        assert result.timeout == 900


# ---------------------------------------------------------------------------
# TestTaskGenerateConfig
# ---------------------------------------------------------------------------


class TestTaskGenerateConfig:
    def test_minimal_config(self) -> None:
        gen = TaskGenerateConfig(template="voltage-drop")
        assert gen.template == "voltage-drop"
        assert gen.count == 5
        assert gen.seed == 42
        assert gen.difficulties == ["easy", "medium"]

    def test_custom_values(self) -> None:
        gen = TaskGenerateConfig(
            template="cable-sizing",
            count=10,
            seed=99,
            difficulties=["easy", "medium", "hard"],
        )
        assert gen.count == 10
        assert gen.seed == 99
        assert len(gen.difficulties) == 3

    def test_empty_template_raises(self) -> None:
        with pytest.raises(ValidationError):
            TaskGenerateConfig(template="")


def test_config_accepts_strategy_field() -> None:
    """EvolutionConfig accepts strategy='hill_climb' and strategy='qd'."""
    from aec_bench.contracts.evolution import EvolutionConfig

    config_hc = EvolutionConfig(
        workspace_path="/tmp/ws",
        models={"classifier": "claude-haiku-4", "evolver": "claude-sonnet-4-6"},
        task_selector={},
        strategy="hill_climb",
    )
    assert config_hc.strategy == "hill_climb"

    config_qd = EvolutionConfig(
        workspace_path="/tmp/ws",
        models={"classifier": "claude-haiku-4", "evolver": "claude-sonnet-4-6"},
        task_selector={},
        strategy="qd",
    )
    assert config_qd.strategy == "qd"


def test_config_defaults_to_hill_climb() -> None:
    """EvolutionConfig defaults strategy to 'hill_climb'."""
    from aec_bench.contracts.evolution import EvolutionConfig

    config = EvolutionConfig(
        workspace_path="/tmp/ws",
        models={"classifier": "claude-haiku-4", "evolver": "claude-sonnet-4-6"},
        task_selector={},
    )
    assert config.strategy == "hill_climb"


class TestEvolutionConfigWithGenerate:
    def test_generate_field_defaults_to_none(self) -> None:
        config = EvolutionConfig(
            workspace_path="/tmp/ws",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        assert config.generate is None

    def test_generate_field_from_dict(self) -> None:
        config = EvolutionConfig(
            workspace_path="/tmp/ws",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            generate={"template": "voltage-drop", "count": 3},
        )
        assert config.generate is not None
        assert config.generate.template == "voltage-drop"
        assert config.generate.count == 3

    def test_loads_generate_from_yaml(self, tmp_path: Path) -> None:
        data = {
            "workspace_path": "workspaces/test",
            "models": {
                "classifier": "claude-haiku-4-5-20251001",
                "evolver": "claude-sonnet-4-20250514",
            },
            "tasks": {"domains": ["electrical"]},
            "generate": {
                "template": "voltage-drop",
                "count": 5,
                "seed": 123,
                "difficulties": ["easy"],
            },
        }
        config_file = _write_yaml(tmp_path / "evolution.yaml", data)
        config = load_evolution_config(config_file)

        assert config.generate is not None
        assert config.generate.template == "voltage-drop"
        assert config.generate.count == 5
        assert config.generate.seed == 123
        assert config.generate.difficulties == ["easy"]
        # task_selector still parsed correctly
        assert config.task_selector.domains == ["electrical"]
