# ABOUTME: Trial planning and lifecycle primitives for the Python harness layer.
# ABOUTME: Defines deterministic planned-trial identities and valid lifecycle transitions.

from dataclasses import dataclass
from enum import StrEnum

from aec_bench.contracts.experiment_manifest import AgentConfig


class TrialLifecycleState(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class PlannedTrial:
    trial_id: str
    experiment_id: str
    task_id: str
    agent: AgentConfig
    compute_backend: str
    repetition: int


def build_trial_id(
    *,
    experiment_id: str,
    task_id: str,
    agent_name: str,
    repetition: int,
) -> str:
    normalized_task_id = task_id.replace("/", "-")
    return f"{experiment_id}--{normalized_task_id}--{agent_name}--rep{repetition:02d}"


def transition_trial_state(
    current: TrialLifecycleState,
    target: TrialLifecycleState,
) -> TrialLifecycleState:
    allowed = {
        TrialLifecycleState.PLANNED: {
            TrialLifecycleState.RUNNING,
            TrialLifecycleState.DUPLICATE,
            TrialLifecycleState.FAILED,
        },
        TrialLifecycleState.RUNNING: {
            TrialLifecycleState.COMPLETED,
            TrialLifecycleState.FAILED,
        },
        TrialLifecycleState.COMPLETED: set(),
        TrialLifecycleState.FAILED: set(),
        TrialLifecycleState.DUPLICATE: set(),
    }
    if target not in allowed[current]:
        raise ValueError(f"invalid trial lifecycle transition: {current} -> {target}")
    return target
