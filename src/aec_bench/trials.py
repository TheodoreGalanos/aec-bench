# ABOUTME: Provides the one direct trial-planning API for all runnable task families.
# ABOUTME: Expands task IDs, agents, compute, and repetitions into deterministic PlannedTrial values.

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig


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


class PlannableTask(Protocol):
    """The task identity needed by deterministic trial planning."""

    @property
    def task_id(self) -> str: ...


def plan_trials(
    experiment_id: str,
    *,
    tasks: Sequence[PlannableTask],
    agents: Sequence[AgentConfig],
    compute: ComputeConfig | None = None,
    repetitions: int = 1,
) -> list[PlannedTrial]:
    """Expand tasks, agents, and repetitions into stable planned trials."""

    if not experiment_id.strip():
        raise ValueError("experiment_id must not be blank")
    if not agents:
        raise ValueError("trial planning requires at least one agent")
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
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


__all__ = ("PlannableTask", "PlannedTrial", "build_trial_id", "plan_trials")
