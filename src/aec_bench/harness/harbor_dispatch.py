# ABOUTME: Harbor dispatch boundary for manifest-driven experiment execution.
# ABOUTME: Builds precise Harbor configs and can execute the Harbor CLI via an injected executor.

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml
from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]

from aec_bench.contracts.execution_environment import HarborEnvironmentBinding
from aec_bench.contracts.experiment_manifest import AgentConfig, ExperimentManifest
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.harness.execution_payload import ExecutionBundle, build_entrypoint_execution_bundle
from aec_bench.trials import plan_trials

HARBOR_NATIVE_BACKENDS = ("modal", "e2b", "daytona", "docker")


class HarborDispatchError(Exception):
    pass


def validate_harbor_job_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate one concrete config at the Harbor SDK boundary."""

    JobConfig.model_validate(config)
    return config


@dataclass(frozen=True)
class HarborDispatchResult:
    config_path: Path
    command: list[str]
    selected_task_count: int
    planned_trial_count: int
    exit_code: int | None = None


class HarborCommandExecutor(Protocol):
    def execute(self, *, command: list[str], cwd: Path) -> int: ...


class SubprocessHarborExecutor:
    def execute(self, *, command: list[str], cwd: Path) -> int:
        env = dict(os.environ)
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(cwd) if not existing_pythonpath else f"{cwd}{os.pathsep}{existing_pythonpath}"
        completed = subprocess.run(command, cwd=cwd, check=False, env=env)
        return int(completed.returncode)


def execute_harbor_config(
    *,
    config_path: Path,
    project_root: Path,
    executor: HarborCommandExecutor | None = None,
    execute: bool = True,
) -> tuple[list[str], int | None]:
    """Execute one already-written Harbor configuration through the current effect boundary."""

    command = ["uv", "run", "harbor", "run", "-c", str(config_path)]
    if not execute:
        return command, None
    exit_code = (executor or SubprocessHarborExecutor()).execute(
        command=command,
        cwd=Path(project_root),
    )
    return command, exit_code


def dispatch_harbor_config(
    *,
    config: dict[str, Any],
    config_path: Path,
    project_root: Path,
    selected_task_count: int,
    planned_trial_count: int,
    executor: HarborCommandExecutor | None = None,
    execute: bool = True,
) -> HarborDispatchResult:
    """Write and optionally execute one validated Harbor configuration."""

    destination = Path(config_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    command, exit_code = execute_harbor_config(
        config_path=destination,
        project_root=project_root,
        executor=executor,
        execute=execute,
    )
    return HarborDispatchResult(
        config_path=destination,
        command=command,
        selected_task_count=selected_task_count,
        planned_trial_count=planned_trial_count,
        exit_code=exit_code,
    )


@dataclass(frozen=True)
class HarborExperimentDispatcher:
    project_root: Path
    jobs_dir: Path | str = "jobs"

    def dispatch(
        self,
        *,
        manifest: ExperimentManifest,
        tasks: list[TaskDefinition],
        config_path: Path,
        task_path_overrides: Mapping[str, Path] | None = None,
        environment_binding: HarborEnvironmentBinding | None = None,
        executor: HarborCommandExecutor | None = None,
        execute: bool = True,
    ) -> HarborDispatchResult:
        if not tasks:
            raise HarborDispatchError("manifest did not select any tasks for Harbor dispatch")
        overrides = dict(task_path_overrides or {})
        feedback_tasks = tuple(
            task.task_id
            for task in tasks
            if (
                overrides.get(task.task_id, self.project_root / "tasks" / task.task_id) / "verifier_retry_prompt.md"
            ).is_file()
        )
        if feedback_tasks:
            raise HarborDispatchError(
                "verifier-feedback is not supported by Harbor dispatch: " + ", ".join(feedback_tasks)
            )

        job_config = build_harbor_job_config(
            manifest=manifest,
            tasks=tasks,
            jobs_dir=self.jobs_dir,
            task_path_overrides=task_path_overrides,
            environment_binding=environment_binding,
        )
        planned_trials = plan_trials(
            manifest.experiment_id,
            tasks=tasks,
            agents=manifest.agents,
            compute=manifest.compute,
            repetitions=manifest.repetitions,
        )
        return dispatch_harbor_config(
            config=job_config,
            config_path=config_path,
            project_root=self.project_root,
            selected_task_count=len(tasks),
            planned_trial_count=len(planned_trials),
            executor=executor,
            execute=execute,
        )


def build_harbor_job_config(
    *,
    manifest: ExperimentManifest,
    tasks: list[TaskDefinition],
    jobs_dir: Path | str = "jobs",
    task_path_overrides: Mapping[str, Path] | None = None,
    environment_binding: HarborEnvironmentBinding | None = None,
) -> dict[str, Any]:
    agents = [_harbor_agent_config(agent) for agent in manifest.agents]
    if manifest.compute.timeout_override is not None:
        for agent in agents:
            agent["override_timeout_sec"] = manifest.compute.timeout_override
    config: dict[str, Any] = {
        "jobs_dir": str(jobs_dir),
        "n_attempts": manifest.repetitions,
        "timeout_multiplier": 1.0,
        "metrics": [{"type": "mean"}, {"type": "min"}, {"type": "max"}],
        "n_concurrent_trials": int(manifest.compute.resource_limits.get("n_concurrent_trials", 1)),
        "quiet": False,
        "environment": harbor_environment_config(
            manifest.compute.backend,
            environment_binding=environment_binding,
        ),
        "agents": agents,
        "datasets": [],
        "tasks": _harbor_task_configs(
            tasks=tasks,
            task_path_overrides=task_path_overrides,
        ),
        "artifacts": [
            {"source": "/workspace/output.md", "destination": "agent/output.md"},
            {"source": "/workspace/agent_result.json", "destination": "agent/agent_result.json"},
            {"source": "/workspace/conversation.jsonl", "destination": "agent/conversation.jsonl"},
            {"source": "/workspace/trajectory.jsonl", "destination": "agent/trajectory.jsonl"},
            {"source": "/workspace/symbolic_state.json", "destination": "agent/symbolic_state.json"},
            {"source": "/workspace/model_reasoning.jsonl", "destination": "agent/model_reasoning.jsonl"},
            {"source": "/workspace/.scratchpad.json", "destination": "agent/scratchpad.json"},
        ],
    }
    if manifest.disable_verification:
        config["verifier"] = {"disable": True}
    return config


def _harbor_task_configs(
    *,
    tasks: list[TaskDefinition],
    task_path_overrides: Mapping[str, Path] | None,
) -> list[dict[str, str]]:
    overrides = dict(task_path_overrides or {})
    task_ids = {task.task_id for task in tasks}
    unknown_task_ids = sorted(set(overrides) - task_ids)
    if unknown_task_ids:
        raise HarborDispatchError("task path overrides reference unknown task ids: " + ", ".join(unknown_task_ids))

    configs: list[dict[str, str]] = []
    for task in tasks:
        override = overrides.get(task.task_id)
        if override is None:
            configs.append({"path": f"tasks/{task.task_id}"})
            continue
        path = Path(override)
        if not path.is_absolute():
            raise HarborDispatchError(f"task path override for {task.task_id!r} must be absolute")
        if not path.is_dir():
            raise HarborDispatchError(f"task path override for {task.task_id!r} must be an existing directory")
        configs.append({"path": str(path.resolve())})
    return configs


def harbor_environment_config(
    backend: str,
    *,
    environment_binding: HarborEnvironmentBinding | None = None,
) -> dict[str, Any]:
    if environment_binding is not None:
        if environment_binding.backend != backend:
            raise HarborDispatchError(
                f"environment binding backend {environment_binding.backend!r} does not match {backend!r}",
            )
        return {
            "import_path": environment_binding.import_path,
            "force_build": False,
            "delete": True,
            "kwargs": dict(environment_binding.kwargs),
        }
    if backend not in HARBOR_NATIVE_BACKENDS:
        raise HarborDispatchError(f"custom Harbor backend {backend!r} requires an environment binding")
    return {
        "type": backend,
        "force_build": False,
        "delete": True,
        "kwargs": {},
    }


ENTRYPOINT_AGENT_IMPORT_PATH = "agents.entrypoint_agent:EntrypointAgent"
ENTRYPOINT_AGENT_RUNTIME_NAME = "entrypoint"


def _harbor_agent_config(agent: AgentConfig) -> dict[str, Any]:
    kwargs = dict(agent.parameters)
    kwargs["adapter"] = agent.adapter
    if agent.system_prompt is not None:
        kwargs["system_prompt"] = agent.system_prompt
    if agent.client is not None:
        kwargs["client"] = {
            "client_kind": agent.client.kind,
            "payload": dict(agent.client.settings),
        }
    return {
        "name": agent.name,
        "import_path": _resolve_import_path(agent),
        "model_name": agent.model,
        "kwargs": kwargs,
    }


def build_harbor_entrypoint_execution_bundle(
    *,
    agent: AgentConfig,
    instruction: str,
) -> ExecutionBundle:
    """Build the exact request bundle implied by one concrete Harbor agent config."""
    harbor_agent = _harbor_agent_config(agent)
    kwargs = harbor_agent["kwargs"]
    if not isinstance(kwargs, dict):
        raise TypeError("Harbor entrypoint kwargs must be a mapping")
    # Harbor's agent factory always injects the parsed AgentConfig.env mapping as
    # ``extra_env``; this manifest surface currently leaves that mapping empty.
    kwargs.setdefault("extra_env", {})
    return build_entrypoint_execution_bundle(
        instruction=instruction,
        adapter_name=ENTRYPOINT_AGENT_RUNTIME_NAME,
        model_name=str(harbor_agent["model_name"]),
        harbor_kwargs=kwargs,
    )


def _resolve_import_path(agent: AgentConfig) -> str:
    return ENTRYPOINT_AGENT_IMPORT_PATH
