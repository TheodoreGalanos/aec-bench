# ABOUTME: Adapts lifecycle experiments to the runtime-independent meta-harness evaluator boundary.
# ABOUTME: Keeps lifecycle candidate construction and execution policy outside the generic meta-harness core.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.meta_harness import HarnessCandidate
from aec_bench.lifecycles.application import (
    LifecycleTrial,
    LifecycleTrialExecutor,
    LifecycleVerifier,
    run_lifecycle_experiment,
)


@dataclass(frozen=True, slots=True)
class LifecycleHarnessCandidate:
    """Hold the lifecycle trials and effects for one harness candidate."""

    trials: tuple[LifecycleTrial, ...]
    execute: LifecycleTrialExecutor
    verify: LifecycleVerifier

    def __post_init__(self) -> None:
        if not self.trials:
            raise ValueError("lifecycle harness candidate requires at least one trial")


def evaluate_lifecycle_candidate(
    candidate: HarnessCandidate[LifecycleHarnessCandidate],
) -> list[TrialRecord]:
    """Evaluate one lifecycle candidate through normal lifecycle experiment composition."""
    value = candidate.value
    return run_lifecycle_experiment(
        trials=value.trials,
        execute=value.execute,
        verify=value.verify,
    )


__all__ = ("LifecycleHarnessCandidate", "evaluate_lifecycle_candidate")
