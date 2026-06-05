# ABOUTME: Tests for the Harbor dispatch boundary in the Python harness.
# ABOUTME: Verifies config generation, agent resolution, and injected command execution.

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.harness.harbor_dispatch import (
    MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
    HarborExperimentDispatcher,
    build_harbor_job_config,
)
from tests.support.task_factories import make_task_definition


class FakeExecutor:
    def __init__(self) -> None:
        self.command: list[str] | None = None
        self.cwd: Path | None = None

    def execute(self, *, command: list[str], cwd: Path) -> int:
        self.command = command
        self.cwd = cwd
        return 0


def test_build_harbor_job_config_uses_precise_task_paths() -> None:
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Dispatch config",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[
            AgentConfig(
                name="tool-loop-sonnet-46",
                adapter="tool_loop",
                model="claude-sonnet-4-6",
                parameters={"max_turns": 20, "command_timeout": 120},
            )
        ],
        compute=ComputeConfig(
            backend="modal",
            resource_limits={"n_concurrent_trials": 2},
        ),
    )
    tasks = [
        make_task_definition(task_id="mechanical/heat-load/alpha"),
        make_task_definition(task_id="mechanical/heat-load/beta"),
    ]

    config = build_harbor_job_config(manifest=manifest, tasks=tasks)

    assert config["jobs_dir"] == "jobs"
    assert config["orchestrator"]["n_concurrent_trials"] == 2
    assert config["environment"]["type"] == "modal"
    assert config["agents"][0]["import_path"] == "agents.entrypoint_agent:EntrypointAgent"
    assert config["tasks"] == [
        {"path": "tasks/mechanical/heat-load/alpha"},
        {"path": "tasks/mechanical/heat-load/beta"},
    ]


def test_build_harbor_job_config_maps_morph_to_import_path_environment() -> None:
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Morph dispatch config",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[AgentConfig(name="tool-loop", adapter="tool_loop", model="claude-sonnet-4-6")],
        compute=ComputeConfig(backend="morph"),
    )
    tasks = [make_task_definition(task_id="mechanical/heat-load/alpha")]

    config = build_harbor_job_config(manifest=manifest, tasks=tasks)

    assert "type" not in config["environment"]
    assert config["environment"]["import_path"] == MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH
    assert config["environment"]["kwargs"]["compute_backend"] == "morph"


def test_build_harbor_job_config_for_morph_validates_as_harbor_config() -> None:
    from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]

    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Morph dispatch config",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[AgentConfig(name="tool-loop", adapter="tool_loop", model="claude-sonnet-4-6")],
        compute=ComputeConfig(backend="morph"),
    )
    tasks = [make_task_definition(task_id="mechanical/heat-load/alpha")]

    config = build_harbor_job_config(manifest=manifest, tasks=tasks)

    parsed = JobConfig.model_validate(config)
    assert parsed.environment.import_path == MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH
    assert parsed.environment.type is None


def test_dispatcher_writes_yaml_and_executes_harbor_command(tmp_path: Path) -> None:
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Dispatch config",
        tasks=TaskSelector(include_patterns=["mechanical/heat-load/*"]),
        agents=[
            AgentConfig(
                name="tool-loop-sonnet-46",
                adapter="tool_loop",
                model="claude-sonnet-4-6",
                parameters={"max_turns": 20},
            )
        ],
        compute=ComputeConfig(backend="modal"),
    )
    executor = FakeExecutor()
    dispatcher = HarborExperimentDispatcher(project_root=tmp_path)
    tasks = [make_task_definition(task_id="mechanical/heat-load/alpha")]

    result = dispatcher.dispatch(
        manifest=manifest,
        tasks=tasks,
        config_path=tmp_path / "generated-job.yaml",
        executor=executor,
    )

    written = yaml.safe_load(result.config_path.read_text(encoding="utf-8"))

    assert result.selected_task_count == 1
    assert result.planned_trial_count == 1
    assert result.command == [
        "uv",
        "run",
        "harbor",
        "run",
        "-c",
        str(result.config_path),
    ]
    assert executor.command == result.command
    assert executor.cwd == tmp_path
    assert written["tasks"] == [{"path": "tasks/mechanical/heat-load/alpha"}]


def test_resolve_import_path_returns_entrypoint_agent_for_all_adapters() -> None:
    """All adapter kinds should resolve to EntrypointAgent."""
    from aec_bench.contracts.experiment_manifest import AgentConfig
    from aec_bench.harness.harbor_dispatch import _resolve_import_path

    for adapter in ("rlm", "direct", "tool_loop", "lambda-rlm", "lambda_rlm", "pydantic_ai"):
        agent = AgentConfig(name="test", adapter=adapter, model="claude-sonnet-4-20250514")
        path = _resolve_import_path(agent)
        assert path == "agents.entrypoint_agent:EntrypointAgent", f"Failed for adapter={adapter}"


def test_harbor_agent_config_includes_adapter_in_kwargs() -> None:
    """_harbor_agent_config must inject the adapter kind into kwargs so EntrypointAgent can route correctly."""
    from aec_bench.contracts.experiment_manifest import AgentConfig
    from aec_bench.harness.harbor_dispatch import _harbor_agent_config

    agent = AgentConfig(
        name="my-agent",
        adapter="rlm",
        model="claude-sonnet-4-20250514",
        parameters={"max_turns": 10},
    )
    config = _harbor_agent_config(agent)

    assert config["kwargs"]["adapter"] == "rlm"
    assert config["kwargs"]["max_turns"] == 10
    assert config["import_path"] == "agents.entrypoint_agent:EntrypointAgent"
