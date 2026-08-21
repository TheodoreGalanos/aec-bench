# ABOUTME: Provides direct functional composition for finite lifecycle execution and trials.
# ABOUTME: Keeps checkpoint coordination, execution effects, verification, and record return explicit.

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.lifecycles.runtime.lifecycle import (
    branch_lifecycle,
    read_lifecycle,
    release_checkpoint,
    request_checkpoint_evidence,
    revisit_checkpoint,
    run_lifecycle,
    submit_checkpoint,
    validate_lifecycle_verification,
)
from aec_bench.lifecycles.values import LifecycleExecution, LifecycleTrial

type LifecycleTrialExecutor = Callable[[LifecycleTrial], LifecycleExecution]
type LifecycleVerifier = Callable[[Path, Path], dict[str, object]]
type LifecycleRecordPersistence = Callable[[TrialRecord], None]


def run_lifecycle_trial(
    *,
    trial: LifecycleTrial,
    execute: LifecycleTrialExecutor,
    verify: LifecycleVerifier,
    persist: LifecycleRecordPersistence | None = None,
) -> TrialRecord:
    """Execute, verify, build, optionally persist, and return one lifecycle trial."""
    execution = execute(trial)
    from aec_bench.lifecycles.catalogue import lifecycle_operation_resolver

    state = read_lifecycle(
        trial.package_dir,
        trial.run_dir,
        operation_resolver=lifecycle_operation_resolver(trial.package_dir, trial.run_dir),
    )
    if state != execution.state:
        raise ValueError("lifecycle executor result does not match canonical run state")
    agent_status = execution.agent.get("status")
    if state.get("status") == "complete" and agent_status == "completed":
        try:
            verification = validate_lifecycle_verification(verify(trial.package_dir, trial.run_dir))
        except Exception as exc:
            lifecycle_id = state.get("lifecycle_id")
            if not isinstance(lifecycle_id, str) or not lifecycle_id:
                raise ValueError("lifecycle state identity is missing") from exc
            verification = validate_lifecycle_verification(
                {
                    "lifecycle_id": lifecycle_id,
                    "overall": "incomplete",
                    "passed": False,
                    "reward": 0.0,
                    "gates": {
                        "lifecycle_verifier": {
                            "passed": False,
                            "score": 0.0,
                            "failures": [f"verifier_exception:{type(exc).__name__}:{exc}"],
                        }
                    },
                }
            )
    else:
        lifecycle_id = state.get("lifecycle_id")
        if not isinstance(lifecycle_id, str) or not lifecycle_id:
            raise ValueError("lifecycle state identity is missing")
        verification = validate_lifecycle_verification(
            {
                "lifecycle_id": lifecycle_id,
                "overall": "incomplete",
                "passed": False,
                "reward": 0.0,
                "gates": {
                    "lifecycle_runtime": {
                        "passed": False,
                        "score": 0.0,
                        "failures": [f"stopped_at:{state.get('active_checkpoint_id') or state.get('status')}"],
                    }
                },
            }
        )

    from aec_bench.lifecycles.recording import LifecycleExperimentSweepContext, record_lifecycle_experiment
    from aec_bench.lifecycles.trial_record import build_lifecycle_trial_record

    sweep_context = cast(
        LifecycleExperimentSweepContext | None,
        trial.planned.extensions.get("lifecycle_sweep_context"),
    )
    recording = record_lifecycle_experiment(
        package_dir=trial.package_dir,
        run_dir=trial.run_dir,
        agent=execution.agent,
        verifier=verify,
        verification=verification,
        tool_schema=list(execution.tool_schema),
        sweep_context=sweep_context,
    )
    record = build_lifecycle_trial_record(
        trial=trial,
        recording=recording,
    )
    if persist is not None:
        persist(record)
    return record


def run_lifecycle_experiment(
    *,
    trials: Sequence[LifecycleTrial],
    execute: LifecycleTrialExecutor,
    verify: LifecycleVerifier,
    persist: LifecycleRecordPersistence | None = None,
) -> list[TrialRecord]:
    """Run lifecycle trials in declared order and return their records directly."""
    return [run_lifecycle_trial(trial=trial, execute=execute, verify=verify, persist=persist) for trial in trials]


__all__ = (
    "LifecycleExecution",
    "LifecycleRecordPersistence",
    "LifecycleTrial",
    "LifecycleTrialExecutor",
    "LifecycleVerifier",
    "branch_lifecycle",
    "read_lifecycle",
    "release_checkpoint",
    "request_checkpoint_evidence",
    "revisit_checkpoint",
    "run_lifecycle",
    "run_lifecycle_experiment",
    "run_lifecycle_trial",
    "submit_checkpoint",
)
