# ABOUTME: Trial planning and lifecycle primitives for the Python harness layer.
# ABOUTME: Defines deterministic planned-trial identities and valid lifecycle transitions.

from enum import StrEnum


class TrialLifecycleState(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


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
