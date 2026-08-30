# ABOUTME: Provides the one direct trial-planning API for all runnable task families.
# ABOUTME: Expands task IDs, agents, compute, and repetitions into deterministic PlannedTrial values.

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.task_definition import Visibility
from aec_bench.tasks.selector import SelectableTask, validate_execution_tasks


@dataclass(frozen=True)
class PlannedTrial:
    trial_id: str
    experiment_id: str
    task_id: str
    agent: AgentConfig
    compute: ComputeConfig
    repetition: int
    extensions: Mapping[str, BaseModel] = field(default_factory=dict)


def build_trial_id(
    *,
    experiment_id: str,
    task_id: str,
    agent_name: str,
    repetition: int,
) -> str:
    """Build one deterministic trial identity."""

    normalized_task_id = task_id.replace("/", "-")
    return f"{experiment_id}--{normalized_task_id}--{agent_name}--rep{repetition:02d}"


class PlannableTask(SelectableTask, Protocol):
    """The task identity and execution policy needed by trial planning."""


def plan_trials(
    experiment_id: str,
    *,
    tasks: Sequence[PlannableTask],
    agents: Sequence[AgentConfig],
    compute: ComputeConfig | None = None,
    repetitions: int = 1,
    permitted_visibility: Sequence[Visibility] = (Visibility.PUBLIC,),
) -> list[PlannedTrial]:
    """Expand tasks, agents, and repetitions into stable planned trials."""

    if not experiment_id.strip():
        raise ValueError("experiment_id must not be blank")
    if not agents:
        raise ValueError("trial planning requires at least one agent")
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    validate_execution_tasks(tasks, permitted_visibility=permitted_visibility)
    selected_compute = compute or ComputeConfig(backend="local")
    plan: list[PlannedTrial] = []
    for task in sorted(tasks, key=lambda item: item.task_id):
        for agent in agents:
            for repetition in range(1, repetitions + 1):
                plan.append(
                    PlannedTrial(
                        trial_id=build_trial_id(
                            experiment_id=experiment_id,
                            task_id=task.task_id,
                            agent_name=agent.name,
                            repetition=repetition,
                        ),
                        experiment_id=experiment_id,
                        task_id=task.task_id,
                        agent=agent,
                        compute=selected_compute,
                        repetition=repetition,
                    )
                )
    return plan


def planned_trial_to_data(trial: PlannedTrial) -> dict[str, object]:
    """Return one exact JSON-compatible representation of a planned trial."""

    return {
        "trial_id": trial.trial_id,
        "experiment_id": trial.experiment_id,
        "task_id": trial.task_id,
        "agent": trial.agent.model_dump(mode="json", round_trip=True),
        "compute": trial.compute.model_dump(mode="json", round_trip=True),
        "repetition": trial.repetition,
        "extensions": {
            kind: value.model_dump(mode="json", round_trip=True) for kind, value in sorted(trial.extensions.items())
        },
    }


def planned_trial_from_data(
    data: Mapping[str, object],
    *,
    extension_types: Mapping[str, type[BaseModel]] | None = None,
) -> PlannedTrial:
    """Load a planned trial while requiring explicit types for extension values."""

    selected_extension_types = extension_types or {}
    expected_fields = {"trial_id", "experiment_id", "task_id", "agent", "compute", "repetition", "extensions"}
    if set(data) != expected_fields:
        raise ValueError("planned trial data fields do not match the current contract")
    raw_extensions = data["extensions"]
    if not isinstance(raw_extensions, Mapping):
        raise ValueError("planned trial extensions must be an object")
    unknown = set(raw_extensions) - set(selected_extension_types)
    if unknown:
        raise ValueError(f"planned trial extension types are required: {sorted(unknown)}")
    extensions: dict[str, BaseModel] = {}
    for kind, extension_value in raw_extensions.items():
        if not isinstance(kind, str):
            raise ValueError("planned trial extension keys must be strings")
        extensions[kind] = selected_extension_types[kind].model_validate(extension_value)
    repetition = data["repetition"]
    if not isinstance(repetition, int) or isinstance(repetition, bool) or repetition < 1:
        raise ValueError("planned trial repetition must be a positive integer")
    string_values: dict[str, str] = {}
    for field_name in ("trial_id", "experiment_id", "task_id"):
        field_value: Any = data[field_name]
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(f"planned trial {field_name} must be a non-empty string")
        string_values[field_name] = field_value
    return PlannedTrial(
        trial_id=string_values["trial_id"],
        experiment_id=string_values["experiment_id"],
        task_id=string_values["task_id"],
        agent=AgentConfig.model_validate(data["agent"]),
        compute=ComputeConfig.model_validate(data["compute"]),
        repetition=repetition,
        extensions=extensions,
    )


__all__ = (
    "PlannableTask",
    "PlannedTrial",
    "build_trial_id",
    "plan_trials",
    "planned_trial_from_data",
    "planned_trial_to_data",
)
