# ABOUTME: Tests for the Harbor dispatch boundary in the Python harness.
# ABOUTME: Verifies config generation, agent resolution, and injected command execution.

import importlib
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
import yaml  # type: ignore[import-untyped]
from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]

from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    ReviewerConfig,
    ReviewerEndpointConfig,
    TaskSelector,
)
from aec_bench.contracts.harness_instance import AgentBindingConfig
from aec_bench.harness.harbor_dispatch import (
    MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
    HarborDispatchError,
    HarborExperimentDispatcher,
    ProposalHarborDispatchInput,
    SubprocessHarborExecutor,
    build_harbor_entrypoint_execution_bundle,
    build_harbor_job_config,
    build_proposal_harbor_job_config,
)
from aec_bench.harness.proposal_session_config import (
    ProposalSessionHostConfig,
)
from aec_bench.harness.proposal_task_package import (
    ProposalTaskPackageManifest,
)
from aec_bench.meta_harness.program_proposal_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.tasks.loader import load_task_definition
from tests.support.task_factories import make_task_definition

_PROPOSAL_MORPH_ENVIRONMENT_IMPORT_PATH = "aec_bench.providers.proposal_morph_harbor:ProposalMorphHarborEnvironment"


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


def test_build_harbor_job_config_uses_exact_external_task_path(
    tmp_path: Path,
) -> None:
    task = make_task_definition(task_id="civil/proposal-session/source-free")
    task_path = tmp_path / "derived-task"
    task_path.mkdir()
    manifest = ExperimentManifest(
        experiment_id="proposal-session-001",
        name="Proposal session",
        tasks=TaskSelector(include_patterns=[task.task_id]),
        agents=[AgentConfig(name="proposal", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )

    config = build_harbor_job_config(
        manifest=manifest,
        tasks=[task],
        task_path_overrides={task.task_id: task_path},
    )

    assert config["tasks"] == [{"path": str(task_path.resolve())}]


def test_build_harbor_job_config_rejects_unmatched_task_path_override(
    tmp_path: Path,
) -> None:
    task = make_task_definition(task_id="civil/proposal-session/source-free")
    task_path = tmp_path / "derived-task"
    task_path.mkdir()
    manifest = ExperimentManifest(
        experiment_id="proposal-session-001",
        name="Proposal session",
        tasks=TaskSelector(include_patterns=[task.task_id]),
        agents=[AgentConfig(name="proposal", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )

    with pytest.raises(HarborDispatchError, match="unknown task ids"):
        build_harbor_job_config(
            manifest=manifest,
            tasks=[task],
            task_path_overrides={"civil/proposal-session/other": task_path},
        )


@pytest.mark.parametrize(
    ("override_path", "message"),
    [
        (Path("relative-derived-task"), "must be absolute"),
        (Path("/definitely/missing/aec-bench-derived-task"), "must be an existing directory"),
    ],
)
def test_build_harbor_job_config_rejects_unsafe_task_path_override(
    override_path: Path,
    message: str,
) -> None:
    task = make_task_definition(task_id="civil/proposal-session/source-free")
    manifest = ExperimentManifest(
        experiment_id="proposal-session-001",
        name="Proposal session",
        tasks=TaskSelector(include_patterns=[task.task_id]),
        agents=[AgentConfig(name="proposal", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )

    with pytest.raises(HarborDispatchError, match=message):
        build_harbor_job_config(
            manifest=manifest,
            tasks=[task],
            task_path_overrides={task.task_id: override_path},
        )


def test_build_harbor_job_config_preserves_manifest_repetitions() -> None:
    manifest = ExperimentManifest(
        experiment_id="experiment-repeated",
        name="Repeated dispatch config",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[AgentConfig(name="direct", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
        repetitions=3,
    )

    config = build_harbor_job_config(
        manifest=manifest,
        tasks=[make_task_definition(task_id="mechanical/heat-load/alpha")],
    )

    assert config["n_attempts"] == 3


def test_build_proposal_harbor_job_config_binds_exact_host_runtime_and_fixed_h0(
    tmp_path: Path,
) -> None:
    dispatch, bundle = _proposal_dispatch_input(tmp_path)

    config = build_proposal_harbor_job_config(
        dispatch=dispatch,
        jobs_dir=tmp_path / "jobs",
    )

    parsed = JobConfig.model_validate(config)
    agent = config["agents"][0]
    environment = config["environment"]
    agent_host_config = agent["kwargs"]["proposal_session"]
    environment_runtime = environment["kwargs"]
    runtime_fields = (
        "runtime_archive_path",
        "runtime_archive_sha256",
        "runtime_archive_content_sha256",
    )
    assert parsed.n_attempts == 1
    assert len(parsed.tasks) == 1
    assert len(parsed.agents) == 1
    assert config["tasks"] == [{"path": str(dispatch.derived_task_path)}]
    assert agent["import_path"] == "agents.entrypoint_agent:EntrypointAgent"
    assert agent["model_name"] == _fixed_h0_model(bundle)
    assert agent["kwargs"] == {
        "adapter": "proposal_session",
        "extra_env": {},
        "proposal_session": dispatch.host_config.model_dump(mode="json"),
    }
    assert environment["import_path"] == (_PROPOSAL_MORPH_ENVIRONMENT_IMPORT_PATH)
    assert environment_runtime == {
        "compute_backend": "morph",
        "runtime_archive_path": dispatch.host_config.runtime_archive_path,
        "runtime_archive_sha256": (dispatch.host_config.runtime_archive_sha256),
        "runtime_archive_content_sha256": (dispatch.host_config.runtime_archive_content_sha256),
    }
    assert {field: agent_host_config[field] for field in runtime_fields} == {
        field: environment_runtime[field] for field in runtime_fields
    }
    assert config["artifacts"] == [
        {
            "source": "/workspace/proposal-session",
            "destination": "agent/proposal-session",
        },
        {
            "source": "/workspace/output.md",
            "destination": "agent/output.md",
        },
        {
            "source": "/workspace/agent_result.json",
            "destination": "agent/agent_result.json",
        },
    ]
    assert "client" not in agent["kwargs"]
    assert "tools" not in agent["kwargs"]
    assert "system_prompt" not in agent["kwargs"]
    assert "env" not in agent


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("relative_path", "absolute"),
        ("task_identity", "task identity"),
        ("manifest_identity", "task manifest"),
        ("repetitions", "exactly one repetition"),
    ),
)
def test_build_proposal_harbor_job_config_fails_closed_on_dispatch_drift(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    dispatch, _bundle = _proposal_dispatch_input(tmp_path)
    if mutation == "relative_path":
        dispatch = ProposalHarborDispatchInput(
            host_config=dispatch.host_config,
            derived_task_path=Path("derived-task"),
            derived_task=dispatch.derived_task,
            derived_task_manifest=dispatch.derived_task_manifest,
        )
    elif mutation == "task_identity":
        dispatch = ProposalHarborDispatchInput(
            host_config=dispatch.host_config,
            derived_task_path=dispatch.derived_task_path,
            derived_task=dispatch.derived_task.model_copy(
                update={"task_id": "civil/proposal-session/other"},
            ),
            derived_task_manifest=dispatch.derived_task_manifest,
        )
    elif mutation == "manifest_identity":
        dispatch = ProposalHarborDispatchInput(
            host_config=dispatch.host_config,
            derived_task_path=dispatch.derived_task_path,
            derived_task=dispatch.derived_task,
            derived_task_manifest=(
                dispatch.derived_task_manifest.model_copy(
                    update={"task_id": "civil/proposal-session/other"},
                )
            ),
        )
    else:
        dispatch = ProposalHarborDispatchInput(
            host_config=dispatch.host_config,
            derived_task_path=dispatch.derived_task_path,
            derived_task=dispatch.derived_task,
            derived_task_manifest=dispatch.derived_task_manifest,
            repetitions=2,
        )

    with pytest.raises(HarborDispatchError, match=message):
        build_proposal_harbor_job_config(dispatch=dispatch)


def test_build_proposal_harbor_job_config_rejects_tampered_manifest_member(
    tmp_path: Path,
) -> None:
    dispatch, _bundle = _proposal_dispatch_input(tmp_path)
    verifier = dispatch.derived_task_path / "tests" / "test.sh"
    verifier.write_bytes(verifier.read_bytes() + b"\n# tampered\n")

    with pytest.raises(HarborDispatchError, match="package member identity"):
        build_proposal_harbor_job_config(dispatch=dispatch)


def test_build_proposal_harbor_job_config_reports_first_sorted_unsafe_member(
    tmp_path: Path,
) -> None:
    dispatch, _bundle = _proposal_dispatch_input(tmp_path)
    (dispatch.derived_task_path / "aaa-symbolic-link").symlink_to("missing")
    (dispatch.derived_task_path / "bbb-undeclared").write_text(
        "undeclared",
        encoding="utf-8",
    )

    with pytest.raises(
        HarborDispatchError,
        match="contains a symbolic link: aaa-symbolic-link",
    ):
        build_proposal_harbor_job_config(dispatch=dispatch)


def test_entrypoint_request_prediction_includes_harbor_agent_environment_default() -> None:
    agent = AgentConfig(
        name="rlm",
        adapter="rlm",
        model="claude-test-model",
        parameters={"max_turns": 32, "prompt_cache": False},
    )

    bundle = build_harbor_entrypoint_execution_bundle(
        agent=agent,
        instruction="Review the drainage packet.",
    )

    assert bundle.request.configuration == {
        "adapter": "rlm",
        "extra_env": {},
        "max_turns": 32,
        "prompt_cache": False,
    }


def test_experiment_manifest_accepts_reviewer_config() -> None:
    manifest = ExperimentManifest(
        experiment_id="experiment-001",
        name="Reviewer config",
        tasks=TaskSelector(domains=["mechanical"]),
        agents=[AgentConfig(name="tool-loop", adapter="tool_loop", model="claude-sonnet-4-6")],
        compute=ComputeConfig(backend="modal"),
        reviewer=ReviewerConfig(
            enabled=True,
            models=[
                ReviewerEndpointConfig(
                    name="reviewer-main",
                    model="openai:gpt-5.2",
                )
            ],
        ),
    )

    assert manifest.reviewer is not None
    assert manifest.reviewer.enabled is True
    assert manifest.reviewer.models[0].name == "reviewer-main"


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


def test_dispatcher_forwards_external_task_path_to_harbor(tmp_path: Path) -> None:
    task = make_task_definition(task_id="civil/proposal-session/source-free")
    task_path = tmp_path / "derived-task"
    task_path.mkdir()
    manifest = ExperimentManifest(
        experiment_id="proposal-session-001",
        name="Proposal session",
        tasks=TaskSelector(include_patterns=[task.task_id]),
        agents=[AgentConfig(name="proposal", adapter="direct", model="test-model")],
        compute=ComputeConfig(backend="docker"),
    )
    executor = FakeExecutor()

    result = HarborExperimentDispatcher(project_root=tmp_path).dispatch(
        manifest=manifest,
        tasks=[task],
        config_path=tmp_path / "proposal-session.yaml",
        task_path_overrides={task.task_id: task_path},
        executor=executor,
    )

    written = yaml.safe_load(result.config_path.read_text(encoding="utf-8"))
    assert written["tasks"] == [{"path": str(task_path.resolve())}]


def test_subprocess_executor_adds_project_root_to_pythonpath(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Harbor subprocesses must be able to import project-local agents."""
    captured: dict[str, Any] = {}

    def fake_run(command: list[str], *, cwd: Path, check: bool, env: dict[str, str]) -> Any:
        captured["command"] = command
        captured["cwd"] = cwd
        captured["check"] = check
        captured["env"] = env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    exit_code = SubprocessHarborExecutor().execute(command=["uv", "run", "harbor"], cwd=tmp_path)

    assert exit_code == 0
    assert captured["cwd"] == tmp_path
    assert captured["env"]["PYTHONPATH"].split(":")[0] == str(tmp_path)


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


def test_harbor_agent_config_includes_serialized_client_in_kwargs() -> None:
    """_harbor_agent_config should preserve client settings for EntrypointAgent bundles."""
    from aec_bench.contracts.experiment_manifest import AgentConfig, ClientConfig
    from aec_bench.harness.harbor_dispatch import _harbor_agent_config

    agent = AgentConfig(
        name="direct-replay",
        adapter="direct",
        model="replay-direct",
        client=ClientConfig(
            kind="replay",
            settings={"output_text": "done"},
        ),
    )

    config = _harbor_agent_config(agent)

    assert config["kwargs"]["client"] == {
        "client_kind": "replay",
        "payload": {"output_text": "done"},
    }


def _proposal_dispatch_input(
    tmp_path: Path,
) -> tuple[ProposalHarborDispatchInput, ProposalRunSessionBundle]:
    fixture_module = importlib.import_module(
        "tests.harness.test_proposal_session_config",
    )
    host_fixture = cast(
        Callable[
            [Path],
            tuple[
                ProposalSessionHostConfig,
                ProposalRunSessionBundle,
                Path,
            ],
        ],
        fixture_module._host_fixture,
    )
    host_config, bundle, derived_task_path = host_fixture(tmp_path)
    manifest = ProposalTaskPackageManifest.model_validate_json(
        (derived_task_path / "proposal-task-package.json").read_bytes(),
    )
    observed_task = load_task_definition(
        derived_task_path,
        derived_task_path.parent.parent,
    )
    derived_task = observed_task.model_copy(
        update={"task_id": manifest.task_id},
    )
    return (
        ProposalHarborDispatchInput(
            host_config=host_config,
            derived_task_path=derived_task_path.resolve(),
            derived_task=derived_task,
            derived_task_manifest=manifest,
        ),
        bundle,
    )


def _fixed_h0_model(bundle: ProposalRunSessionBundle) -> str:
    bindings = tuple(
        binding.configuration
        for binding in bundle.fixed_harness.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    )
    assert len(bindings) == 1
    return bindings[0].model
