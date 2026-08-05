# ABOUTME: Harbor dispatch boundary for manifest-driven experiment execution.
# ABOUTME: Builds precise Harbor configs and can execute the Harbor CLI via an injected executor.

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml
from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]

from aec_bench.contracts.experiment_manifest import AgentConfig, ExperimentManifest
from aec_bench.contracts.harness_instance import AgentBindingConfig
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.harness.execution_payload import ExecutionBundle, build_entrypoint_execution_bundle
from aec_bench.harness.proposal_session_config import (
    ProposalSessionHostConfig,
    ProposalSessionHostConfigError,
    load_proposal_session_host_inputs,
)
from aec_bench.harness.proposal_task_packaging.contracts import (
    ProposalTaskPackageFile,
    ProposalTaskPackageManifest,
)
from aec_bench.harness.scheduler import build_trial_plan
from aec_bench.providers.proposal_morph.constants import (
    PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
)
from aec_bench.tasks.loader import LoadError, load_task_definition

MORPH_BACKEND = "morph"
MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH = "aec_bench.providers.morph_harbor:MorphHarborEnvironment"
HARBOR_NATIVE_BACKENDS = ("modal", "e2b", "daytona", "docker")
HARBOR_RUN_BACKENDS = (*HARBOR_NATIVE_BACKENDS, MORPH_BACKEND)


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


@dataclass(frozen=True)
class ProposalHarborDispatchInput:
    """Exact host and derived-task inputs for one proposal candidate session."""

    host_config: ProposalSessionHostConfig
    derived_task_path: Path
    derived_task: TaskDefinition
    derived_task_manifest: ProposalTaskPackageManifest
    repetitions: int = 1


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
        executor: HarborCommandExecutor | None = None,
        execute: bool = True,
    ) -> HarborDispatchResult:
        if not tasks:
            raise HarborDispatchError("manifest did not select any tasks for Harbor dispatch")

        job_config = build_harbor_job_config(
            manifest=manifest,
            tasks=tasks,
            jobs_dir=self.jobs_dir,
            task_path_overrides=task_path_overrides,
        )
        planned_trials = build_trial_plan(manifest, tasks)
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
        "orchestrator": {
            "type": "local",
            "n_concurrent_trials": int(manifest.compute.resource_limits.get("n_concurrent_trials", 1)),
            "quiet": False,
        },
        "environment": harbor_environment_config(manifest.compute.backend),
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


def build_proposal_harbor_job_config(
    *,
    dispatch: ProposalHarborDispatchInput,
    jobs_dir: Path | str = "jobs",
) -> dict[str, Any]:
    """Build one validated proposal-only Harbor candidate job."""
    if type(dispatch.repetitions) is not int or dispatch.repetitions != 1:
        raise HarborDispatchError(
            "proposal Harbor dispatch requires exactly one repetition",
        )
    task_path = _exact_proposal_task_path(dispatch.derived_task_path)
    try:
        host_inputs = load_proposal_session_host_inputs(
            dispatch.host_config.model_dump(mode="json"),
            environment_dir=task_path / "environment",
        )
    except ProposalSessionHostConfigError as error:
        raise HarborDispatchError(
            f"proposal dispatch host inputs are invalid: {error}",
        ) from error
    if (
        host_inputs.config != dispatch.host_config
        or host_inputs.derived_task_manifest != dispatch.derived_task_manifest
    ):
        raise HarborDispatchError(
            "derived proposal task manifest differs from the exact host inputs",
        )
    _validate_exact_proposal_task_package(
        task_path=task_path,
        manifest=dispatch.derived_task_manifest,
    )
    _validate_exact_proposal_task(
        task_path=task_path,
        task=dispatch.derived_task,
        manifest=dispatch.derived_task_manifest,
        expected_task_id=host_inputs.bundle.task_snapshot.task_id,
    )
    agent_configurations = tuple(
        binding.configuration
        for binding in host_inputs.bundle.fixed_harness.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    )
    if len(agent_configurations) != 1:
        raise HarborDispatchError(
            "proposal fixed H0 requires exactly one agent binding",
        )
    fixed_agent = agent_configurations[0]
    host_payload = dispatch.host_config.model_dump(mode="json")
    runtime_binding = {
        "runtime_archive_path": dispatch.host_config.runtime_archive_path,
        "runtime_archive_sha256": (dispatch.host_config.runtime_archive_sha256),
        "runtime_archive_content_sha256": (dispatch.host_config.runtime_archive_content_sha256),
    }
    config: dict[str, Any] = {
        "job_name": (f"proposal-{host_inputs.bundle.compilation.candidate_ref.candidate_id}"),
        "jobs_dir": str(jobs_dir),
        "n_attempts": 1,
        "timeout_multiplier": 1.0,
        "metrics": [
            {"type": "mean"},
            {"type": "min"},
            {"type": "max"},
        ],
        "orchestrator": {
            "type": "local",
            "n_concurrent_trials": 1,
            "quiet": False,
        },
        "environment": {
            "import_path": PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
            "force_build": False,
            "delete": True,
            "kwargs": {
                "compute_backend": MORPH_BACKEND,
                **runtime_binding,
            },
        },
        "agents": [
            {
                "name": fixed_agent.agent_name,
                "import_path": ENTRYPOINT_AGENT_IMPORT_PATH,
                "model_name": fixed_agent.model,
                "kwargs": {
                    "adapter": "proposal_session",
                    "extra_env": {},
                    "proposal_session": host_payload,
                },
            }
        ],
        "datasets": [],
        "tasks": [{"path": str(task_path)}],
        "artifacts": [
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
        ],
    }
    try:
        validate_harbor_job_config(config)
    except ValueError as error:
        raise HarborDispatchError(
            f"proposal Harbor JobConfig is invalid: {error}",
        ) from error
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


def _exact_proposal_task_path(path: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise HarborDispatchError(
            "derived proposal task path must be absolute",
        )
    if candidate.is_symlink():
        raise HarborDispatchError(
            "derived proposal task path must not be a symbolic link",
        )
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise HarborDispatchError(
            "derived proposal task path must be an existing directory",
        ) from error
    if resolved != candidate or not resolved.is_dir():
        raise HarborDispatchError(
            "derived proposal task path must be an exact existing directory",
        )
    return resolved


def _validate_exact_proposal_task(
    *,
    task_path: Path,
    task: TaskDefinition,
    manifest: ProposalTaskPackageManifest,
    expected_task_id: str,
) -> None:
    if (
        task.task_id != expected_task_id
        or manifest.task_id != expected_task_id
        or task.visibility is not manifest.visibility
    ):
        raise HarborDispatchError(
            "derived proposal task identity does not match the compiled session",
        )
    try:
        observed = load_task_definition(
            task_path,
            task_path.parent.parent,
        )
    except (LoadError, OSError, ValueError) as error:
        raise HarborDispatchError(
            f"derived proposal task cannot be loaded: {error}",
        ) from error
    observed_payload = observed.model_dump(
        mode="json",
        exclude={"domain", "task_id", "task_type"},
    )
    expected_payload = task.model_dump(
        mode="json",
        exclude={"domain", "task_id", "task_type"},
    )
    if observed_payload != expected_payload:
        raise HarborDispatchError(
            "derived proposal task bytes differ from the supplied task",
        )


def _validate_exact_proposal_task_package(
    *,
    task_path: Path,
    manifest: ProposalTaskPackageManifest,
) -> None:
    manifest_path = "proposal-task-package.json"
    expected = {item.path: item for item in manifest.files}
    observed: set[str] = set()
    for path in sorted(
        task_path.rglob("*"),
        key=lambda candidate: candidate.relative_to(task_path).as_posix(),
    ):
        relative = path.relative_to(task_path).as_posix()
        if _validate_exact_proposal_task_package_member(
            path=path,
            relative=relative,
            manifest_path=manifest_path,
            manifest_entry=expected.get(relative),
        ):
            observed.add(relative)
    if observed != set(expected):
        raise HarborDispatchError(
            "derived proposal task package does not match its exact manifest surface",
        )


def _validate_exact_proposal_task_package_member(
    *,
    path: Path,
    relative: str,
    manifest_path: str,
    manifest_entry: ProposalTaskPackageFile | None,
) -> bool:
    if path.is_symlink():
        raise HarborDispatchError(
            f"derived proposal task package contains a symbolic link: {relative}",
        )
    try:
        path_stat = path.stat(follow_symlinks=False)
    except OSError as error:
        raise HarborDispatchError(
            f"derived proposal task package member cannot be inspected: {relative}",
        ) from error
    if stat.S_ISDIR(path_stat.st_mode):
        return False
    if not stat.S_ISREG(path_stat.st_mode):
        raise HarborDispatchError(
            f"derived proposal task package member is not a regular file: {relative}",
        )
    if relative == manifest_path:
        return False
    if manifest_entry is None:
        raise HarborDispatchError(
            f"derived proposal task package contains an undeclared member: {relative}",
        )
    if path_stat.st_size != manifest_entry.byte_size:
        raise HarborDispatchError(
            f"derived proposal task package member identity mismatch: {relative}",
        )
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise HarborDispatchError(
            f"derived proposal task package member cannot be read: {relative}",
        ) from error
    if len(payload) != manifest_entry.byte_size or hashlib.sha256(payload).hexdigest() != manifest_entry.sha256:
        raise HarborDispatchError(
            f"derived proposal task package member identity mismatch: {relative}",
        )
    return True


def harbor_environment_config(backend: str) -> dict[str, Any]:
    if backend == MORPH_BACKEND:
        return {
            "import_path": MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
            "force_build": False,
            "delete": True,
            "kwargs": {"compute_backend": MORPH_BACKEND},
        }
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
