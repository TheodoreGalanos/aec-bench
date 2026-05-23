# ABOUTME: Coordinates adaptation families into ordinary planned trials for the harness layer.
# ABOUTME: Resolves task-family candidates by metadata and attaches adaptation provenance per run.

from dataclasses import dataclass
from typing import Any

from aec_bench.contracts.adaptation import AdaptationSpec, expand_adaptation_spec
from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.trial_record import AdaptationProvenance, DerivationStepRecord
from aec_bench.harness.trial import PlannedTrial, build_trial_id


class AdaptationCoordinationError(Exception):
    pass


@dataclass(frozen=True)
class AdaptationPlannedTrial:
    planned_trial: PlannedTrial
    adaptation: AdaptationProvenance


def build_adaptation_trial_plan(
    *,
    experiment_id: str,
    spec: AdaptationSpec,
    tasks: list[TaskDefinition],
    agents: list[AgentConfig],
    compute_backend: str,
    repetitions: int = 1,
) -> list[AdaptationPlannedTrial]:
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")

    candidates = expand_adaptation_spec(spec)
    plan: list[AdaptationPlannedTrial] = []
    for candidate in candidates:
        task = _resolve_task_for_candidate(
            candidate_family_id=spec.family_id,
            candidate_variation=candidate.variation,
            tasks=tasks,
        )
        adaptation = AdaptationProvenance(
            family_id=candidate.family_id,
            seed_task_id=candidate.seed_task_id,
            variation_key=candidate.variation_key,
            variation=candidate.variation,
            derivation_lineage=[
                DerivationStepRecord(
                    axis=step.axis,
                    parent_value=step.parent_value,
                    value=step.value,
                )
                for step in candidate.derivation_lineage
            ],
        )
        for agent in agents:
            for repetition in range(1, repetitions + 1):
                plan.append(
                    AdaptationPlannedTrial(
                        planned_trial=PlannedTrial(
                            trial_id=build_trial_id(
                                experiment_id=experiment_id,
                                task_id=task.task_id,
                                agent_name=agent.name,
                                repetition=repetition,
                            ),
                            experiment_id=experiment_id,
                            task_id=task.task_id,
                            agent=agent,
                            compute_backend=compute_backend,
                            repetition=repetition,
                        ),
                        adaptation=adaptation,
                    )
                )
    return plan


def _resolve_task_for_candidate(
    *,
    candidate_family_id: str,
    candidate_variation: dict[str, str],
    tasks: list[TaskDefinition],
) -> TaskDefinition:
    matches = [
        task
        for task in tasks
        if _task_matches_candidate(
            task=task,
            candidate_family_id=candidate_family_id,
            candidate_variation=candidate_variation,
        )
    ]
    if not matches:
        msg = f"no task matches candidate: {candidate_variation}"
        raise AdaptationCoordinationError(msg)
    if len(matches) > 1:
        msg = f"multiple tasks match candidate: {candidate_variation}"
        raise AdaptationCoordinationError(msg)
    return matches[0]


def _task_matches_candidate(
    *,
    task: TaskDefinition,
    candidate_family_id: str,
    candidate_variation: dict[str, str],
) -> bool:
    metadata = task.metadata
    family_id = metadata.get("adaptation_family_id")
    variation = metadata.get("adaptation_variation")
    return (
        isinstance(family_id, str)
        and family_id == candidate_family_id
        and _normalize_variation(variation) == candidate_variation
    )


def _normalize_variation(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    normalized: dict[str, str] = {}
    for axis, axis_value in value.items():
        if not isinstance(axis, str) or not isinstance(axis_value, str):
            return None
        normalized[axis] = axis_value
    return normalized
