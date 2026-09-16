# ABOUTME: Tests configuration rejection before Harbor execution or dispatch files are created.
# ABOUTME: Exercises the installed Harbor agent and environment validation boundaries without providers.

from pathlib import Path
from typing import Any

import pytest
import yaml
from harbor.agents.factory import AgentFactory  # type: ignore[import-untyped]
from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]

from aec_bench.experimentation.proposals.harbor import build_proposal_harbor_job_config
from aec_bench.harness.harbor_dispatch import (
    ENTRYPOINT_AGENT_IMPORT_PATH,
    HarborDispatchError,
    dispatch_harbor_config,
    execute_harbor_config,
    validate_harbor_job_config,
)
from agents.entrypoint_agent import EntrypointAgent
from tests.harness.test_harbor_dispatch import FakeExecutor, _proposal_dispatch_input


def _config() -> dict[str, Any]:
    return {
        "environment": {"type": "docker"},
        "agents": [
            {
                "name": "experiment-condition",
                "import_path": ENTRYPOINT_AGENT_IMPORT_PATH,
                "model_name": "replay-model",
                "kwargs": {"adapter": "tool_loop", "max_turns": 3},
            }
        ],
        "tasks": [{"path": "tasks/public/example"}],
    }


@pytest.mark.parametrize("execute", [False, True])
@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"n_concurrent_trials": 0}, "n_concurrent_trials"),
        ({"agents": [{"import_path": "missing_harbor_agent:Agent"}]}, "missing_harbor_agent"),
        ({"agents": [{"import_path": "builtins:object"}]}, "BaseAgent subclass"),
        ({"agents": [{"name": "codex", "kwargs": {"unknown_option": True}}]}, "unknown_option"),
        ({"environment": {"type": "docker", "cpu_enforcement_policy": "request"}}, "resource requests"),
    ],
)
def test_invalid_job_is_rejected_before_dispatch_files_or_execution(
    tmp_path: Path,
    execute: bool,
    change: dict[str, Any],
    message: str,
) -> None:
    config = _config() | change
    destination = tmp_path / "dispatch" / "job.yaml"
    executor = FakeExecutor()

    with pytest.raises(HarborDispatchError, match=message):
        dispatch_harbor_config(
            config=config,
            config_path=destination,
            project_root=tmp_path,
            selected_task_count=1,
            planned_trial_count=1,
            executor=executor,
            execute=execute,
        )

    assert not destination.parent.exists()
    assert executor.command is None


@pytest.mark.parametrize("execute", [False, True])
@pytest.mark.parametrize("contents", ["n_concurrent_trials: 0\n", "[not, a, job]\n", "agents: [\n"])
def test_saved_job_is_validated_again_before_execution(tmp_path: Path, contents: str, execute: bool) -> None:
    destination = tmp_path / "job.yaml"
    destination.write_text(contents, encoding="utf-8")
    executor = FakeExecutor()

    with pytest.raises(HarborDispatchError):
        execute_harbor_config(config_path=destination, project_root=tmp_path, executor=executor, execute=execute)

    assert destination.read_text(encoding="utf-8") == contents
    assert executor.command is None


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({"max_turns": 0}, "max_turns"),
        ({"max_tokens": False}, "max_tokens"),
        ({"max_context_tokens": 100}, "cannot be enforced"),
        ({"adapter": "direct", "max_tool_calls": 2}, "task-tool controls"),
    ],
)
def test_entrypoint_preflight_checks_existing_runtime_limits(parameters: dict[str, Any], message: str) -> None:
    config = _config()
    config["agents"][0]["kwargs"].update(parameters)
    with pytest.raises(HarborDispatchError, match=message):
        validate_harbor_job_config(config)


def test_custom_import_cannot_silently_select_a_builtin_agent() -> None:
    config = _config()
    config["agents"][0]["name"] = "oracle"
    with pytest.raises(HarborDispatchError, match="name.*import_path"):
        validate_harbor_job_config(config)


def test_framework_constructor_arguments_cannot_be_duplicated_in_agent_kwargs() -> None:
    config = _config()
    config["agents"][0]["kwargs"]["extra_env"] = {}
    with pytest.raises(HarborDispatchError, match="extra_env"):
        validate_harbor_job_config(config)


def test_valid_preflight_does_not_construct_agents_or_change_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_constructor(*args: Any, **kwargs: Any) -> None:
        pytest.fail("preflight must not construct an agent")

    monkeypatch.setattr(EntrypointAgent, "__init__", forbidden_constructor)
    config = _config()
    before = yaml.safe_dump(config)
    executor = FakeExecutor()
    destination = tmp_path / "job.yaml"
    result = dispatch_harbor_config(
        config=config,
        config_path=destination,
        project_root=tmp_path,
        selected_task_count=1,
        planned_trial_count=1,
        executor=executor,
        execute=False,
    )
    assert yaml.safe_dump(config) == before
    assert yaml.safe_load(destination.read_text(encoding="utf-8")) == config
    assert result.exit_code is None
    assert executor.command is None


def test_proposal_config_constructs_the_real_harbor_agent(tmp_path: Path) -> None:
    dispatch, _ = _proposal_dispatch_input(tmp_path)
    config = JobConfig.model_validate(build_proposal_harbor_job_config(dispatch=dispatch))

    agent = AgentFactory.create_agent_from_config(config.agents[0], logs_dir=tmp_path / "logs")

    assert isinstance(agent, EntrypointAgent)
    assert agent.model_name == config.agents[0].model_name
    agent._validate_proposal_configuration()


def test_saved_relative_config_uses_the_executor_working_directory(tmp_path: Path) -> None:
    (tmp_path / "job.yaml").write_text(yaml.safe_dump(_config()), encoding="utf-8")
    executor = FakeExecutor()
    command, exit_code = execute_harbor_config(
        config_path=Path("job.yaml"),
        project_root=tmp_path,
        executor=executor,
    )
    assert command[-1] == "job.yaml"
    assert executor.cwd == tmp_path
    assert exit_code == 0


def test_preflight_does_not_mutate_deprecated_harbor_input_fields() -> None:
    config = _config()
    config["orchestrator"] = {"n_concurrent_trials": 2}
    before = yaml.safe_dump(config)
    with pytest.warns(DeprecationWarning):
        validate_harbor_job_config(config)
    assert yaml.safe_dump(config) == before
