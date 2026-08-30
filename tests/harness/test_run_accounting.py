# ABOUTME: Tests exact run-plan membership and typed terminal outcome accounting.
# ABOUTME: Proves duplicate and unexpected results cannot enter accepted aggregates.

import json
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_accounting import (
    RunAccounting,
    TrialAccountingObservation,
    account_run,
)
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan, plan_run
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    TrialRecord,
)
from aec_bench.harness.planned_trial_reconciliation import planned_trial_binding
from tests.contracts.test_run_plan import _PLAN_CREATED_AT, _accept_combination, _resolved_run, _task_profiles
from tests.support.trial_record_factories import make_trial_record


def _plan() -> tuple[ResolvedRunSpec, RunPlan]:
    spec = _resolved_run(repetitions=1)
    return spec, plan_run(
        spec,
        plan_identity=EntityIdentity(id=new_entity_id(EntityKind.PLAN), key="accounting-plan", version=1),
        created_at=_PLAN_CREATED_AT,
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
    )


def _record(
    spec: ResolvedRunSpec,
    plan_trial: PlannedTrial,
    *,
    status: ExecutionStatus = ExecutionStatus.COMPLETED,
    evaluation_status: EvaluationStatus = EvaluationStatus.COMPLETED,
    evidence_status: EvidenceStatus = EvidenceStatus.NOT_REQUIRED,
) -> TrialRecord:
    trial = plan_trial
    revision = (
        trial.task_release.artifact.sha256
        if hasattr(trial.task_release, "artifact")
        else trial.task_release.source_revision
    )
    return make_trial_record(
        trial_id=str(trial.trial_identity.id),
        run_id=str(trial.run_identity.id),
        task_id=trial.task_release.task_id,
        task={
            "task_id": trial.task_release.task_id,
            "task_revision": revision,
            "visibility": trial.task_metadata.visibility,
        },
        agent=AgentConfiguration(adapter=trial.agent_condition.adapter, model=trial.agent_condition.model),
        environment=ExecutionEnvironmentRef(
            runtime_image="test-image",
            compute_backend=trial.compute.backend,
            tool_versions={},
        ),
        inputs={
            "instruction": "Run the planned task.",
            "task_revision": revision,
            "task_kind": trial.execution_family,
            "visibility": trial.task_metadata.visibility,
        },
        execution_status=status,
        evaluation_status=evaluation_status,
        evidence_status=evidence_status,
        planned_trial_binding=planned_trial_binding(trial, spec),
    )


def _observation(
    spec: ResolvedRunSpec,
    plan_trial: PlannedTrial,
    outcome: Literal["succeeded", "failed", "cancelled", "timed_out", "invalid", "missing"],
    *,
    status: ExecutionStatus = ExecutionStatus.COMPLETED,
) -> TrialAccountingObservation:
    return TrialAccountingObservation(
        trial_id=str(plan_trial.trial_identity.id),
        outcome=outcome,
        record=None if outcome == "missing" else _record(spec, plan_trial, status=status),
    )


def test_account_run_accepts_terminal_records_in_plan_order() -> None:
    spec, plan = _plan()
    observations = [_observation(spec, trial, "succeeded") for trial in reversed(plan.trials)]

    result = account_run(spec, plan, observations)

    assert result.accounting.status == "complete"
    assert result.accounting.validity == "valid"
    assert result.accounting.counts.model_dump() == {
        "planned": 4,
        "succeeded": 4,
        "failed": 0,
        "cancelled": 0,
        "timed_out": 0,
        "invalid": 0,
        "missing": 0,
        "duplicate": 0,
        "unexpected": 0,
    }
    assert [record.trial_id for record in result.accepted_records] == [str(trial.trial_id) for trial in plan.trials]


def test_account_run_uses_explicit_timeout_outcome_and_failure_status() -> None:
    spec, plan = _plan()
    outcomes = ["failed", "timed_out", "cancelled", "succeeded"]
    observations = [
        _observation(
            spec,
            trial,
            outcome,
            status=ExecutionStatus.FAILED
            if outcome in {"failed", "timed_out"}
            else ExecutionStatus.CANCELLED
            if outcome == "cancelled"
            else ExecutionStatus.COMPLETED,
        )
        for trial, outcome in zip(plan.trials, outcomes, strict=True)
    ]

    result = account_run(spec, plan, observations)

    assert result.accounting.status == "complete_with_failures"
    assert result.accounting.counts.failed == 1
    assert result.accounting.counts.timed_out == 1
    assert result.accounting.counts.cancelled == 1


def test_evaluation_failure_is_an_accepted_failed_outcome() -> None:
    spec, plan = _plan()
    failed = TrialAccountingObservation(
        trial_id=str(plan.trials[0].trial_id),
        outcome="failed",
        record=_record(spec, plan.trials[0], evaluation_status=EvaluationStatus.FAILED),
    )
    observations = [failed] + [_observation(spec, trial, "succeeded") for trial in plan.trials[1:]]

    result = account_run(spec, plan, observations)

    assert result.accounting.status == "complete_with_failures"
    assert result.accounting.counts.failed == 1
    assert result.accepted_records[0].trial_id == str(plan.trials[0].trial_id)


def test_account_run_reports_cancelled_when_requested() -> None:
    spec, plan = _plan()
    observations = [_observation(spec, trial, "cancelled", status=ExecutionStatus.CANCELLED) for trial in plan.trials]

    result = account_run(spec, plan, observations, cancellation_requested=True)

    assert result.accounting.status == "cancelled"


def test_account_run_reports_missing_and_excludes_it_from_accepted_records() -> None:
    spec, plan = _plan()
    observations = [_observation(spec, trial, "succeeded") for trial in plan.trials[:-1]]

    result = account_run(spec, plan, observations)

    assert result.accounting.status == "incomplete"
    assert result.accounting.counts.missing == 1
    assert len(result.accepted_records) == 3


def test_account_run_accepts_idempotent_duplicate_once() -> None:
    spec, plan = _plan()
    first = _observation(spec, plan.trials[0], "succeeded")
    observations = [first, first] + [_observation(spec, trial, "succeeded") for trial in plan.trials[1:]]

    result = account_run(spec, plan, observations)

    assert result.accounting.status == "complete"
    assert result.accounting.counts.duplicate == 1
    assert len(result.accepted_records) == len(plan.trials)
    assert result.quarantined_records == ()


def test_account_run_rejects_conflicting_duplicate_as_invalid() -> None:
    spec, plan = _plan()
    first = _observation(spec, plan.trials[0], "succeeded")
    second = _observation(spec, plan.trials[0], "failed", status=ExecutionStatus.FAILED)
    observations = [first, second] + [_observation(spec, trial, "succeeded") for trial in plan.trials[1:]]

    result = account_run(spec, plan, observations)

    assert result.accounting.status == "invalid"
    assert result.accounting.counts.invalid == 1
    assert result.accounting.counts.duplicate == 1
    assert result.accounting.conflicting_duplicate_trial_ids == (plan.trials[0].trial_id,)
    assert all(record.trial_id != str(plan.trials[0].trial_id) for record in result.accepted_records)


def test_account_run_excludes_invalid_evidence_from_aggregates() -> None:
    spec, plan = _plan()
    invalid = TrialAccountingObservation(
        trial_id=str(plan.trials[0].trial_id),
        outcome="invalid",
        record=_record(spec, plan.trials[0], status=ExecutionStatus.INVALID),
    )
    observations = [invalid] + [_observation(spec, trial, "succeeded") for trial in plan.trials[1:]]

    result = account_run(spec, plan, observations)

    assert result.accounting.status == "invalid"
    assert result.accounting.counts.invalid == 1
    assert all(record.trial_id != str(plan.trials[0].trial_id) for record in result.accepted_records)
    assert len(result.quarantined_records) == 1


def test_account_run_requires_the_exact_planned_binding() -> None:
    spec, plan = _plan()
    unbound = _record(spec, plan.trials[0]).model_copy(update={"planned_trial_binding": None})
    observation = TrialAccountingObservation(
        trial_id=str(plan.trials[0].trial_id),
        outcome="succeeded",
        record=unbound,
    )

    result = account_run(
        spec,
        plan,
        [observation] + [_observation(spec, trial, "succeeded") for trial in plan.trials[1:]],
    )

    assert result.accounting.status == "invalid"
    assert result.accounting.invalid_trial_ids == (plan.trials[0].trial_id,)
    assert unbound in result.quarantined_records


def test_account_run_excludes_invalid_evidence_status() -> None:
    spec, plan = _plan()
    record = _record(spec, plan.trials[0], evidence_status=EvidenceStatus.INVALID)
    observation = TrialAccountingObservation(
        trial_id=str(plan.trials[0].trial_id),
        outcome="succeeded",
        record=record,
    )

    result = account_run(
        spec,
        plan,
        [observation] + [_observation(spec, trial, "succeeded") for trial in plan.trials[1:]],
    )

    assert result.accounting.status == "invalid"
    assert record not in result.accepted_records


def test_account_run_quarantines_unexpected_results() -> None:
    spec, plan = _plan()
    unexpected = _record(spec, plan.trials[0]).model_copy(
        update={"trial_id": "backend-unexpected", "planned_trial_binding": None}
    )
    observations = [_observation(spec, trial, "succeeded") for trial in plan.trials]
    observations.append(
        TrialAccountingObservation(trial_id="backend-unexpected", outcome="succeeded", record=unexpected)
    )

    result = account_run(spec, plan, observations)

    assert result.accounting.status == "invalid"
    assert result.accounting.counts.unexpected == 1
    assert result.accounting.counts.planned == len(result.accepted_records)
    assert [record.trial_id for record in result.quarantined_records] == ["backend-unexpected"]


def test_accounting_fixture_is_readable() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "run" / "run-accounting-complete.json"

    accounting = RunAccounting.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert accounting.status == "complete_with_failures"
    assert accounting.counts.timed_out == 1


def test_persisted_accounting_rejects_overlapping_membership_sets() -> None:
    spec, plan = _plan()
    result = account_run(spec, plan, [_observation(spec, trial, "succeeded") for trial in plan.trials])
    payload = result.accounting.model_dump(mode="json")
    payload["counts"]["succeeded"] = 3
    payload["counts"]["invalid"] = 1
    payload["accepted_trial_ids"] = payload["accepted_trial_ids"][:3]
    payload["invalid_trial_ids"] = [payload["accepted_trial_ids"][0]]
    payload["status"] = "invalid"
    payload["validity"] = "invalid"

    with pytest.raises(ValidationError, match="must be disjoint"):
        RunAccounting.model_validate(payload)


@pytest.mark.parametrize("outcome", ["timed_out", "succeeded", "failed", "cancelled"])
def test_terminal_outcomes_require_records(outcome: str) -> None:
    with pytest.raises(ValueError, match="require a TrialRecord"):
        TrialAccountingObservation(trial_id="trial", outcome=outcome)
