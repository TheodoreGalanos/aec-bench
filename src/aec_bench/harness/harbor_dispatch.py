# ABOUTME: Harbor dispatch boundary for manifest-driven experiment execution.
# ABOUTME: Builds precise Harbor configs and can execute the Harbor CLI via an injected executor.

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

import yaml
from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]

from aec_bench.contracts.execution_environment import HarborEnvironmentBinding
from aec_bench.contracts.experiment_manifest import AgentConfig, ExperimentManifest
from aec_bench.contracts.identity import EntityIdentity
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.harness.compilation.task_snapshot import TaskSnapshotError, assert_task_snapshot_matches_directory
from aec_bench.harness.execution_payload import ExecutionBundle, build_entrypoint_execution_bundle
from aec_bench.harness.harbor_reconciliation import HarborTrialTransport, build_harbor_trial_transport
from aec_bench.ledger.evidence_run_store import EvidenceRunStore
from aec_bench.tasks.instance import ResolvedTaskInstance
from aec_bench.tasks.selector import validate_execution_tasks
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
    planned_trial_ids: tuple[UUID, ...] = ()
    trial_transport: tuple[HarborTrialTransport, ...] = ()
    trial_transport_path: Path | None = None


@dataclass(frozen=True)
class HarborPlannedDispatchResult:
    """All one-trial Harbor jobs prepared for one persisted plan subset."""

    run_identity: EntityIdentity
    dispatches: tuple[HarborDispatchResult, ...]


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
    planned_trial_ids: Sequence[UUID] = (),
    trial_transport: Sequence[HarborTrialTransport] = (),
) -> HarborDispatchResult:
    """Write and optionally execute one validated Harbor configuration."""

    destination = Path(config_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    transport_items = tuple(trial_transport)
    transport_path = None
    if transport_items:
        transport_path = destination.with_suffix(destination.suffix + ".trial-transport.json")
        transport_path.write_text(
            json.dumps([item.model_dump(mode="json") for item in transport_items], indent=2) + "\n",
            encoding="utf-8",
        )
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
        planned_trial_ids=tuple(planned_trial_ids),
        trial_transport=transport_items,
        trial_transport_path=transport_path,
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
        planned_trials: Sequence[PlannedTrial] | None = None,
        trial_transport: Sequence[HarborTrialTransport] = (),
        job_name: str | None = None,
    ) -> HarborDispatchResult:
        if not tasks:
            raise HarborDispatchError("manifest did not select any tasks for Harbor dispatch")
        validate_execution_tasks(tasks, permitted_visibility=manifest.tasks.visibility_filter)
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
            job_name=job_name,
        )
        legacy_planned_trials = plan_trials(
            manifest.experiment_id,
            tasks=tasks,
            agents=manifest.agents,
            compute=manifest.compute,
            repetitions=manifest.repetitions,
            permitted_visibility=manifest.tasks.visibility_filter,
        )
        canonical_trials = tuple(planned_trials) if planned_trials is not None else ()
        planned_trial_ids = tuple(trial.trial_identity.id for trial in canonical_trials)
        if len(set(planned_trial_ids)) != len(planned_trial_ids):
            raise HarborDispatchError("canonical Harbor planned trial IDs must be unique")
        selected_task_ids = {task.task_id for task in tasks}
        if any(trial.task_release.task_id not in selected_task_ids for trial in canonical_trials):
            raise HarborDispatchError("canonical Harbor planned trials must use selected tasks")
        selected_transport = tuple(trial_transport)
        if canonical_trials and not selected_transport:
            raise HarborDispatchError("canonical Harbor dispatch requires an explicit trial transport mapping")
        if selected_transport and {item.planned_trial_id for item in selected_transport} != set(planned_trial_ids):
            raise HarborDispatchError("Harbor transport must cover the exact canonical planned trial subset")
        if len({item.harbor_job_name for item in selected_transport}) != len(selected_transport):
            raise HarborDispatchError("Harbor transport job names must be unique")
        return dispatch_harbor_config(
            config=job_config,
            config_path=config_path,
            project_root=self.project_root,
            selected_task_count=len(tasks),
            planned_trial_count=len(legacy_planned_trials),
            executor=executor,
            execute=execute,
            planned_trial_ids=planned_trial_ids,
            trial_transport=selected_transport,
        )

    def dispatch_persisted_plan(
        self,
        *,
        store: EvidenceRunStore,
        run_identity: EntityIdentity,
        manifest: ExperimentManifest,
        tasks: Sequence[ResolvedTaskInstance],
        config_dir: Path,
        started_at: datetime,
        planned_trial_ids: Sequence[UUID] | None = None,
        environment_binding: HarborEnvironmentBinding | None = None,
        executor: HarborCommandExecutor | None = None,
        execute: bool = True,
    ) -> HarborPlannedDispatchResult:
        """Prepare every exact one-trial job before starting a persisted run."""

        stored = store.read_run(run_identity)
        run_plan = stored.plan
        if run_plan is None or stored.state.state != "ready":
            raise HarborDispatchError("canonical Harbor dispatch requires a persisted ready run plan")
        requested_ids = None if planned_trial_ids is None else tuple(planned_trial_ids)
        if requested_ids is not None and len(requested_ids) != len(set(requested_ids)):
            raise HarborDispatchError("canonical Harbor planned trial IDs must be unique")
        artifact_trials = tuple(trial for trial in run_plan.trials if trial.execution_family == "artifact")
        selected_ids = {trial.trial_identity.id for trial in artifact_trials}
        if requested_ids is not None:
            unknown_ids = set(requested_ids) - selected_ids
            if unknown_ids:
                raise HarborDispatchError("canonical Harbor trial subset is outside the artifact run plan")
            requested_set = set(requested_ids)
            artifact_trials = tuple(trial for trial in artifact_trials if trial.trial_identity.id in requested_set)
        if not artifact_trials:
            raise HarborDispatchError("persisted run plan contains no selected artifact trials for Harbor")

        tasks_by_id = {item.task.task_id: item for item in tasks}
        if len(tasks_by_id) != len(tasks):
            raise HarborDispatchError("canonical Harbor tasks must have unique task IDs")
        missing_tasks = sorted({trial.task_release.task_id for trial in artifact_trials} - set(tasks_by_id))
        if missing_tasks:
            raise HarborDispatchError("canonical Harbor planned tasks are not supplied: " + ", ".join(missing_tasks))

        destination = Path(config_dir)
        destination.mkdir(parents=True, exist_ok=True)
        prepared: list[HarborDispatchResult] = []
        for trial in artifact_trials:
            prepared.append(
                self.dispatch_planned_trial(
                    run_spec=stored.spec,
                    run_plan=run_plan,
                    planned_trial=trial,
                    manifest=manifest,
                    task=tasks_by_id[trial.task_release.task_id],
                    config_path=destination / f"aec-planned-{trial.trial_identity.id.hex}.yaml",
                    environment_binding=environment_binding,
                    execute=False,
                )
            )

        if not execute:
            return HarborPlannedDispatchResult(run_identity=run_identity, dispatches=tuple(prepared))
        store.start_run(run_identity, started_at=started_at)
        completed: list[HarborDispatchResult] = []
        for dispatch in prepared:
            command, exit_code = execute_harbor_config(
                config_path=dispatch.config_path,
                project_root=self.project_root,
                executor=executor,
                execute=True,
            )
            completed.append(replace(dispatch, command=command, exit_code=exit_code))
            if exit_code != 0:
                raise HarborDispatchError(f"Harbor dispatch failed with exit code {exit_code}")
        return HarborPlannedDispatchResult(run_identity=run_identity, dispatches=tuple(completed))

    def dispatch_planned_trial(
        self,
        *,
        run_spec: ResolvedRunSpec,
        run_plan: RunPlan,
        planned_trial: PlannedTrial,
        manifest: ExperimentManifest,
        task: ResolvedTaskInstance,
        config_path: Path,
        environment_binding: HarborEnvironmentBinding | None = None,
        executor: HarborCommandExecutor | None = None,
        execute: bool = True,
    ) -> HarborDispatchResult:
        """Dispatch one ready planned trial with a durable pre-effect mapping."""

        if run_spec.run_identity != run_plan.run_identity:
            raise HarborDispatchError("canonical Harbor run spec does not match the run plan")
        if run_plan.schema_version != 2 or run_plan.state != "ready":
            raise HarborDispatchError("canonical Harbor dispatch requires a ready schema-2 run plan")
        planned_by_id = {trial.trial_identity.id: trial for trial in run_plan.trials}
        if planned_by_id.get(planned_trial.trial_identity.id) != planned_trial:
            raise HarborDispatchError("planned trial is not the exact trial from the run plan")
        if planned_trial.execution_family != "artifact":
            raise HarborDispatchError("canonical Harbor dispatch supports artifact planned trials only")
        if task.task.task_id != planned_trial.task_release.task_id:
            raise HarborDispatchError("canonical Harbor task does not match the planned task release")
        if task.task.identity != planned_trial.task_release.task_identity:
            raise HarborDispatchError("canonical Harbor task identity does not match the planned release")
        try:
            assert_task_snapshot_matches_directory(reference=planned_trial.task_release, task_dir=task.instance_dir)
        except TaskSnapshotError as error:
            raise HarborDispatchError("canonical Harbor task bytes do not match the planned release") from error
        if manifest.experiment_id != str(run_spec.experiment_identity.key):
            raise HarborDispatchError("canonical Harbor manifest does not match the resolved experiment")
        if manifest.compute != planned_trial.compute or manifest.compute != run_spec.compute:
            raise HarborDispatchError("canonical Harbor compute condition does not match the persisted plan")
        agent_name = str(planned_trial.agent_condition.identity.key)
        agent = next((candidate for candidate in manifest.agents if candidate.name == agent_name), None)
        if agent is None:
            raise HarborDispatchError("canonical Harbor planned agent is not present in the manifest")
        if (
            agent.adapter != planned_trial.agent_condition.adapter
            or agent.model != planned_trial.agent_condition.model
            or agent.client != planned_trial.agent_condition.client
            or agent.system_prompt != planned_trial.agent_condition.system_prompt
            or agent.parameters != planned_trial.agent_condition.parameters
        ):
            raise HarborDispatchError("canonical Harbor agent condition does not match the manifest")
        if planned_trial.agent_condition.tool_versions or planned_trial.agent_condition.limits:
            raise HarborDispatchError("canonical Harbor dispatch cannot represent planned agent tools or limits")
        canonical_manifest = manifest.model_copy(update={"agents": [agent], "repetitions": 1})
        transport = build_harbor_trial_transport((planned_trial,))
        return self.dispatch(
            manifest=canonical_manifest,
            tasks=[task.task],
            config_path=config_path,
            task_path_overrides={task.task.task_id: task.instance_dir},
            environment_binding=environment_binding,
            executor=executor,
            execute=execute,
            planned_trials=(planned_trial,),
            trial_transport=transport,
            job_name=transport[0].harbor_job_name,
        )


def build_harbor_job_config(
    *,
    manifest: ExperimentManifest,
    tasks: list[TaskDefinition],
    jobs_dir: Path | str = "jobs",
    task_path_overrides: Mapping[str, Path] | None = None,
    environment_binding: HarborEnvironmentBinding | None = None,
    job_name: str | None = None,
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
    if job_name is not None:
        config["job_name"] = job_name
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
