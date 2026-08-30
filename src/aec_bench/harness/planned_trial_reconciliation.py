# ABOUTME: Reconciles family runner output with one canonical planned trial.
# ABOUTME: Keeps shared identity checks explicit while leaving family release checks with each runner.

from __future__ import annotations

from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import PlannedTrial
from aec_bench.contracts.trial_record import PlannedTrialBinding, TrialRecord


def planned_trial_binding(trial: PlannedTrial, spec: ResolvedRunSpec) -> PlannedTrialBinding:
    """Build the backward-readable binding retained by a canonical trial record."""

    return PlannedTrialBinding(
        schema_version=2,
        run_identity=spec.run_identity,
        trial_identity=trial.trial_identity,
        task_release=trial.task_release,
        agent_condition_identity=trial.agent_condition.identity,
        ordinal=trial.ordinal,
        repetition=trial.repetition,
        compute=trial.compute,
        family_release=trial.family_release,
        execution_family=trial.execution_family,
        evaluation_profile=trial.evaluation_profile,
        expected_authorities=spec.expected_authorities,
    )


def validate_planned_trial_record(
    record: TrialRecord,
    trial: PlannedTrial,
    spec: ResolvedRunSpec,
    *,
    task_revision: str,
) -> None:
    """Reject a result that differs from its planned identity or execution condition."""

    binding = planned_trial_binding(trial, spec)
    if record.planned_trial_binding != binding:
        raise ValueError("trial record planned binding does not match the canonical plan")
    if record.trial_id != str(trial.trial_identity.id):
        raise ValueError("trial record UUID does not match the canonical plan")
    if record.run_id != str(spec.run_identity.id):
        raise ValueError("trial record run UUID does not match the canonical plan")
    if record.task_id != trial.task_release.task_id:
        raise ValueError("trial record task release does not match the canonical plan")
    if record.input.task_kind != trial.execution_family:
        raise ValueError("trial record execution family does not match the canonical plan")
    if record.input.task_revision != task_revision:
        raise ValueError("trial record task revision does not match the canonical release")
    if record.attempt != 1:
        raise ValueError("canonical trial records must contain one attempt receipt")
    if record.agent.adapter != trial.agent_condition.adapter or record.agent.model != trial.agent_condition.model:
        raise ValueError("trial record agent condition does not match the canonical plan")
    observed_parameters = record.agent.configuration.get("parameters", trial.agent_condition.parameters)
    if observed_parameters != trial.agent_condition.parameters:
        raise ValueError("trial record agent parameters do not match the canonical plan")
    if record.environment.compute_backend != trial.compute.backend:
        raise ValueError("trial record compute backend does not match the canonical plan")


__all__ = ("planned_trial_binding", "validate_planned_trial_record")
