# ABOUTME: Provides direct functional composition for finite lifecycle execution and trials.
# ABOUTME: Keeps checkpoint coordination, execution effects, verification, and record return explicit.

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from aec_bench.contracts.execution_release import LifecycleExecutionRelease
from aec_bench.contracts.identity import EntityIdentity
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import PlannedTrial
from aec_bench.contracts.trial_record import PlannedTrialBinding, TrialRecord
from aec_bench.harness.planned_trial_reconciliation import (
    planned_trial_binding,
    validate_planned_trial_record,
)
from aec_bench.ledger.evidence_run_store import EvidenceRunStore
from aec_bench.lifecycles.compiled import load_compiled_lifecycle
from aec_bench.lifecycles.finalization import (
    LifecycleFinalizationSource,
    finalize_lifecycle_trial,
    live_lifecycle_finalization_source,
)
from aec_bench.lifecycles.invocation import (
    LifecycleExperimentRecordingResult,
    LifecycleExperimentTrialContext,
    LifecycleInvocationRecorderCapture,
)
from aec_bench.lifecycles.recording import record_lifecycle_experiment
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
type LifecycleEvidenceRetention = Callable[
    [LifecycleTrial, LifecycleExperimentRecordingResult],
    LifecycleFinalizationSource,
]


def run_lifecycle_trial(
    *,
    trial: LifecycleTrial,
    execute: LifecycleTrialExecutor,
    verify: LifecycleVerifier,
    retain: LifecycleEvidenceRetention = live_lifecycle_finalization_source,
    persist: LifecycleRecordPersistence | None = None,
    planned_trial_binding: PlannedTrialBinding | None = None,
) -> TrialRecord:
    """Execute, record, retain, finalize, and optionally persist one lifecycle trial."""
    current_compiled = load_compiled_lifecycle(trial.package_dir)
    if current_compiled.envelope != trial.compiled.envelope:
        raise ValueError("compiled lifecycle identity does not match package bytes")
    if trial.planned.agent.adapter == "deepseek_harness":
        raise ValueError(
            "deepseek_harness cannot produce the required canonical lifecycle turn-limit evidence; refusing to execute"
        )
    planned_max_turns = trial.max_turns_per_session
    execution = execute(trial)
    executed_max_turns = execution.agent.get("max_turns_per_session")
    if type(executed_max_turns) is not int or executed_max_turns != planned_max_turns:
        raise ValueError("lifecycle executor turn limit does not match the planned trial")
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

    recording = record_lifecycle_experiment(
        package_dir=trial.package_dir,
        run_dir=trial.run_dir,
        agent=execution.agent,
        verifier=verify,
        verification=verification,
        tool_schema=list(execution.tool_schema),
        sweep_context=trial.sweep_context,
        trial_context=LifecycleExperimentTrialContext(
            trial_id=trial.planned.trial_id,
            planned_experiment_id=trial.planned.experiment_id,
            task_id=trial.planned.task_id,
            repetition=trial.planned.repetition,
            run_id=trial.planned.trial_id,
            compiled=trial.compiled.envelope,
        ),
    )
    recorder_capture = recording.get("finalization_authority")
    if not isinstance(recorder_capture, LifecycleInvocationRecorderCapture):
        raise ValueError("lifecycle recorder did not return a recorder capture")
    source = retain(trial, recording)
    retained_authority = source.recording.get("finalization_authority")
    if not isinstance(retained_authority, LifecycleInvocationRecorderCapture) or retained_authority != recorder_capture:
        raise ValueError("lifecycle evidence retention did not preserve the recorder capture")
    record = finalize_lifecycle_trial(
        trial=trial,
        source=source,
        planned_trial_binding=planned_trial_binding,
    )
    if persist is not None:
        persist(record)
    return record


def run_persisted_lifecycle_plan(
    *,
    store: EvidenceRunStore,
    run_identity: EntityIdentity,
    trials: Sequence[LifecycleTrial],
    execute: LifecycleTrialExecutor,
    verify: LifecycleVerifier,
    started_at: datetime,
    retain: LifecycleEvidenceRetention = live_lifecycle_finalization_source,
    persist: LifecycleRecordPersistence | None = None,
) -> list[TrialRecord]:
    """Execute only lifecycle trials from one persisted ready plan."""

    stored = store.read_run(run_identity)
    plan = stored.plan
    if plan is None or stored.state.state != "ready":
        raise ValueError("a persisted ready plan is required for lifecycle execution")
    by_id = {trial.planned.trial_id: trial for trial in trials}
    if len(by_id) != len(trials):
        raise ValueError("lifecycle trials must have distinct trial IDs")
    lifecycle_trials = tuple(trial for trial in plan.trials if trial.execution_family == "lifecycle")
    if not lifecycle_trials:
        raise ValueError("persisted plan contains no lifecycle-family trials")
    for planned in lifecycle_trials:
        lifecycle = by_id.get(str(planned.trial_identity.id))
        if lifecycle is None:
            raise ValueError(f"planned lifecycle trial has no supplied trial: {planned.trial_identity.id}")
        validate_lifecycle_release(planned, lifecycle, stored.spec)

    store.start_run(run_identity, started_at=started_at)
    records: list[TrialRecord] = []
    for planned in lifecycle_trials:
        lifecycle = by_id[str(planned.trial_identity.id)]
        validate_lifecycle_release(planned, lifecycle, stored.spec)
        binding = planned_trial_binding(planned, stored.spec)
        record = run_lifecycle_trial(
            trial=lifecycle,
            execute=execute,
            verify=verify,
            retain=retain,
            planned_trial_binding=binding,
        )
        validate_planned_trial_record(
            record,
            planned,
            stored.spec,
            task_revision=lifecycle.compiled.envelope.package_sha256,
        )
        if persist is not None:
            persist(record)
        records.append(record)
    return sorted(records, key=lambda record: _planned_ordinal(record, lifecycle_trials))


def validate_lifecycle_release(
    planned: PlannedTrial,
    trial: LifecycleTrial,
    spec: ResolvedRunSpec,
) -> None:
    release = planned.family_release
    if not isinstance(release, LifecycleExecutionRelease):
        raise ValueError("lifecycle trial does not contain a lifecycle release")
    envelope = trial.compiled.envelope
    if (
        release.template_id != envelope.template_id
        or release.lifecycle_id != envelope.lifecycle_id
        or release.variant_id != envelope.variant_id
        or release.visibility != envelope.visibility
        or release.lifecycle_spec_sha256 != envelope.lifecycle_spec_sha256
        or release.package_sha256 != envelope.package_sha256
        or release.executable_artifact_sha256 != envelope.executable_artifact_sha256
        or release.operation_protocol_sha256 != envelope.operation_protocol_sha256
    ):
        raise ValueError("lifecycle trial release does not match the compiled lifecycle")
    if trial.planned.task_id != planned.task_release.task_id:
        raise ValueError("lifecycle trial task release does not match the canonical plan")
    if trial.planned.trial_id != str(planned.trial_identity.id):
        raise ValueError("lifecycle trial UUID does not match the canonical plan")
    if trial.planned.experiment_id != str(spec.experiment_identity.id):
        raise ValueError("lifecycle trial experiment does not match the canonical plan")
    condition = planned.agent_condition
    agent = trial.planned.agent
    if (
        agent.name != str(condition.identity.key)
        or agent.adapter != condition.adapter
        or agent.model != condition.model
        or agent.client != condition.client
        or agent.parameters != condition.parameters
        or agent.system_prompt != condition.system_prompt
    ):
        raise ValueError("lifecycle trial agent condition does not match the canonical plan")
    if trial.planned.compute != planned.compute:
        raise ValueError("lifecycle trial compute condition does not match the canonical plan")
    if trial.planned.repetition != planned.repetition:
        raise ValueError("lifecycle trial repetition does not match the canonical plan")


def _planned_ordinal(record: TrialRecord, trials: Sequence[PlannedTrial]) -> int:
    for trial in trials:
        if record.trial_id == str(trial.trial_identity.id):
            return trial.ordinal
    raise ValueError("lifecycle record does not match a planned trial")


def run_lifecycle_experiment(
    *,
    trials: Sequence[LifecycleTrial],
    execute: LifecycleTrialExecutor,
    verify: LifecycleVerifier,
    retain: LifecycleEvidenceRetention = live_lifecycle_finalization_source,
    persist: LifecycleRecordPersistence | None = None,
) -> list[TrialRecord]:
    """Run lifecycle trials in declared order and return their records directly."""
    return [
        run_lifecycle_trial(trial=trial, execute=execute, verify=verify, retain=retain, persist=persist)
        for trial in trials
    ]


__all__ = (
    "LifecycleExecution",
    "LifecycleEvidenceRetention",
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
    "run_persisted_lifecycle_plan",
    "run_lifecycle_trial",
    "validate_lifecycle_release",
    "submit_checkpoint",
)
