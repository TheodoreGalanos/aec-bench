# ABOUTME: Defines run-level membership, outcome, and aggregate accounting contracts.
# ABOUTME: Keeps quarantined results out of accepted records while exposing completeness and validity.

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Self
from uuid import UUID

from pydantic import NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.identity import validate_uuidv7
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef, RepositoryTaskSnapshotRef
from aec_bench.contracts.trial_record import (
    EvaluationStatus,
    EvidenceStatus,
    ExecutionStatus,
    PlannedTrialBinding,
    TrialRecord,
)
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

RunAccountingStatus = Literal["complete", "complete_with_failures", "cancelled", "incomplete", "invalid"]
RunTrialOutcome = Literal["succeeded", "failed", "cancelled", "timed_out", "invalid", "missing"]
RunCompleteness = Literal["complete", "incomplete"]
RunValidity = Literal["valid", "invalid"]


class TrialAccountingObservation(FrozenStrictModel):
    """One typed outcome reported for one result or planned trial."""

    trial_id: NonEmptyStr
    outcome: RunTrialOutcome
    record: TrialRecord | None = None

    @model_validator(mode="after")
    def validate_record_requirement(self) -> Self:
        if self.outcome == "missing" and self.record is not None:
            raise ValueError("missing trial outcomes must not carry a TrialRecord")
        if self.outcome in {"succeeded", "failed", "cancelled", "timed_out"} and self.record is None:
            raise ValueError(f"{self.outcome} trial outcomes require a TrialRecord")
        if self.record is not None and self.record.trial_id != self.trial_id:
            raise ValueError("trial accounting observation ID must match its TrialRecord")
        return self


class RunAccountingCounts(FrozenStrictModel):
    """Mutually exclusive expected-trial outcome counts plus membership counts."""

    planned: NonNegativeInt
    succeeded: NonNegativeInt = 0
    failed: NonNegativeInt = 0
    cancelled: NonNegativeInt = 0
    timed_out: NonNegativeInt = 0
    invalid: NonNegativeInt = 0
    missing: NonNegativeInt = 0
    duplicate: NonNegativeInt = 0
    unexpected: NonNegativeInt = 0

    @model_validator(mode="after")
    def validate_outcome_partition(self) -> Self:
        terminal = self.succeeded + self.failed + self.cancelled + self.timed_out + self.invalid + self.missing
        if terminal != self.planned:
            raise ValueError("run accounting outcome counts must partition planned trials")
        return self


class RunAccounting(FrozenStrictModel):
    """The accepted membership and status summary for one canonical run plan."""

    schema_version: Literal[1] = 1
    run_id: UUID
    plan_id: UUID
    status: RunAccountingStatus
    completeness: RunCompleteness
    validity: RunValidity
    counts: RunAccountingCounts
    cancellation_requested: bool = False
    accepted_trial_ids: tuple[UUID, ...] = ()
    missing_trial_ids: tuple[UUID, ...] = ()
    invalid_trial_ids: tuple[UUID, ...] = ()
    duplicate_trial_ids: tuple[UUID, ...] = ()
    conflicting_duplicate_trial_ids: tuple[UUID, ...] = ()
    unexpected_trial_ids: tuple[NonEmptyStr, ...] = ()
    unexpected_duplicate_trial_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("run_id", "plan_id")
    @classmethod
    def validate_entity_ids(cls, value: UUID) -> UUID:
        return validate_uuidv7(value)

    @field_validator(
        "accepted_trial_ids",
        "missing_trial_ids",
        "invalid_trial_ids",
        "duplicate_trial_ids",
        "conflicting_duplicate_trial_ids",
    )
    @classmethod
    def validate_unique_planned_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(value) != len(set(value)):
            raise ValueError("run accounting trial ID lists must be unique")
        for trial_id in value:
            validate_uuidv7(trial_id)
        return value

    @field_validator("unexpected_trial_ids", "unexpected_duplicate_trial_ids")
    @classmethod
    def validate_unique_unexpected_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("run accounting unexpected trial ID lists must be unique")
        return value

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        accepted = set(self.accepted_trial_ids)
        missing = set(self.missing_trial_ids)
        invalid = set(self.invalid_trial_ids)
        if accepted & missing or accepted & invalid or missing & invalid:
            raise ValueError("accepted, missing, and invalid planned trial IDs must be disjoint")
        if not set(self.conflicting_duplicate_trial_ids).issubset(set(self.duplicate_trial_ids) & invalid):
            raise ValueError("conflicting duplicate trial IDs must also be duplicate and invalid")
        if not set(self.unexpected_duplicate_trial_ids).issubset(self.unexpected_trial_ids):
            raise ValueError("unexpected duplicate trial IDs must also be unexpected")
        if (
            len(self.accepted_trial_ids)
            != self.counts.succeeded + self.counts.failed + self.counts.cancelled + self.counts.timed_out
        ):
            raise ValueError("accepted trial IDs must match accepted terminal outcome counts")
        if len(self.missing_trial_ids) != self.counts.missing:
            raise ValueError("missing trial IDs must match the missing count")
        if len(self.invalid_trial_ids) != self.counts.invalid:
            raise ValueError("invalid trial IDs must match the invalid count")
        if len(self.duplicate_trial_ids) + len(self.unexpected_duplicate_trial_ids) != self.counts.duplicate:
            raise ValueError("duplicate trial IDs must match the duplicate count")
        if len(self.unexpected_trial_ids) != self.counts.unexpected:
            raise ValueError("unexpected trial IDs must match the unexpected count")
        if self.completeness != ("incomplete" if self.counts.missing else "complete"):
            raise ValueError("run accounting completeness does not match missing results")
        invalid_evidence = bool(self.counts.invalid or self.counts.unexpected or self.conflicting_duplicate_trial_ids)
        if self.validity != ("invalid" if invalid_evidence else "valid"):
            raise ValueError("run accounting validity does not match evidence")
        expected_status: RunAccountingStatus
        if invalid_evidence:
            expected_status = "invalid"
        elif self.counts.missing:
            expected_status = "incomplete"
        elif self.cancellation_requested and self.counts.cancelled:
            expected_status = "cancelled"
        elif self.counts.failed or self.counts.cancelled or self.counts.timed_out:
            expected_status = "complete_with_failures"
        else:
            expected_status = "complete"
        if self.status != expected_status:
            raise ValueError("run accounting status does not match its counts")
        return self


@dataclass(frozen=True)
class RunAccountingResult:
    """Accounting summary and records eligible for downstream aggregation."""

    accounting: RunAccounting
    accepted_records: tuple[TrialRecord, ...]
    quarantined_records: tuple[TrialRecord, ...]


def account_run(
    run_spec: ResolvedRunSpec,
    run_plan: RunPlan,
    observations: Sequence[TrialAccountingObservation],
    *,
    cancellation_requested: bool = False,
) -> RunAccountingResult:
    """Reconcile typed trial outcomes with one plan and retain only accepted records."""

    if run_spec.run_identity != run_plan.run_identity:
        raise ValueError("run accounting specification does not match the run plan")
    spec_releases = {release.task_id: release for release in run_spec.task_releases}
    spec_conditions = {condition.identity.id: condition for condition in run_spec.agent_conditions}
    for trial in run_plan.trials:
        if spec_releases.get(trial.task_release.task_id) != trial.task_release:
            raise ValueError("run accounting plan task release does not match the specification")
        if spec_conditions.get(trial.agent_condition.identity.id) != trial.agent_condition:
            raise ValueError("run accounting plan agent condition does not match the specification")
        if trial.compute != run_spec.compute or trial.evaluation_profile != run_spec.evaluation_regime:
            raise ValueError("run accounting plan execution condition does not match the specification")
    planned_by_id = {str(trial.trial_identity.id): trial for trial in run_plan.trials}
    if len(planned_by_id) != len(run_plan.trials):
        raise ValueError("run accounting requires unique planned trial identities")
    grouped: dict[str, list[TrialAccountingObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.trial_id].append(observation)

    accepted: dict[str, TrialRecord] = {}
    quarantined: list[TrialRecord] = []
    missing_ids: list[UUID] = []
    invalid_ids: list[UUID] = []
    duplicate_ids: list[UUID] = []
    conflicting_duplicate_ids: list[UUID] = []
    accepted_outcomes: dict[str, RunTrialOutcome] = {}
    unexpected_ids = sorted(trial_id for trial_id in grouped if trial_id not in planned_by_id)
    unexpected_duplicate_ids = sorted(trial_id for trial_id in unexpected_ids if len(grouped[trial_id]) > 1)

    for trial_id in unexpected_ids:
        for observation in grouped[trial_id]:
            if observation.record is not None:
                quarantined.append(observation.record)

    for planned_id, trial in planned_by_id.items():
        current = grouped.get(planned_id, [])
        if not current:
            missing_ids.append(trial.trial_identity.id)
            continue
        if len(current) > 1:
            duplicate_ids.append(trial.trial_identity.id)
            if not _observations_equal(current):
                conflicting_duplicate_ids.append(trial.trial_identity.id)
                quarantined.extend(observation.record for observation in current if observation.record is not None)
                invalid_ids.append(trial.trial_identity.id)
                continue
        observation = current[0]
        if observation.outcome == "missing":
            missing_ids.append(trial.trial_identity.id)
            continue
        if observation.outcome == "invalid":
            invalid_ids.append(trial.trial_identity.id)
            if observation.record is not None:
                quarantined.append(observation.record)
            continue
        if observation.record is None or not _record_matches_plan(
            observation.record,
            trial,
            run_spec,
            observation.outcome,
        ):
            invalid_ids.append(trial.trial_identity.id)
            if observation.record is not None:
                quarantined.append(observation.record)
            continue
        assert observation.record is not None
        accepted[planned_id] = observation.record

        accepted_outcomes[planned_id] = observation.outcome
    succeeded = sum(outcome == "succeeded" for outcome in accepted_outcomes.values())
    failed = sum(outcome == "failed" for outcome in accepted_outcomes.values())
    cancelled = sum(outcome == "cancelled" for outcome in accepted_outcomes.values())
    timed_out = sum(outcome == "timed_out" for outcome in accepted_outcomes.values())
    counts = RunAccountingCounts(
        planned=len(planned_by_id),
        succeeded=succeeded,
        failed=failed,
        cancelled=cancelled,
        timed_out=timed_out,
        invalid=len(invalid_ids),
        missing=len(missing_ids),
        duplicate=len(duplicate_ids) + len(unexpected_duplicate_ids),
        unexpected=len(unexpected_ids),
    )
    accounting = RunAccounting(
        run_id=run_plan.run_identity.id,
        plan_id=run_plan.plan_identity.id,
        status=_status_for(counts, conflicting_duplicate_ids, cancellation_requested=cancellation_requested),
        cancellation_requested=cancellation_requested,
        completeness="incomplete" if counts.missing else "complete",
        validity="invalid" if counts.invalid or counts.unexpected or conflicting_duplicate_ids else "valid",
        counts=counts,
        accepted_trial_ids=tuple(UUID(trial_id) for trial_id in planned_by_id if trial_id in accepted),
        missing_trial_ids=tuple(missing_ids),
        invalid_trial_ids=tuple(invalid_ids),
        duplicate_trial_ids=tuple(duplicate_ids),
        conflicting_duplicate_trial_ids=tuple(conflicting_duplicate_ids),
        unexpected_trial_ids=tuple(unexpected_ids),
        unexpected_duplicate_trial_ids=tuple(unexpected_duplicate_ids),
    )
    return RunAccountingResult(
        accounting=accounting,
        accepted_records=tuple(accepted[trial_id] for trial_id in planned_by_id if trial_id in accepted),
        quarantined_records=tuple(quarantined),
    )


def _observations_equal(observations: Sequence[TrialAccountingObservation]) -> bool:
    first = observations[0]
    return all(
        observation.outcome == first.outcome
        and (observation.record is None) == (first.record is None)
        and (
            observation.record is None
            or first.record is None
            or observation.record.model_dump(mode="json") == first.record.model_dump(mode="json")
        )
        for observation in observations[1:]
    )


def _record_matches_plan(
    record: TrialRecord,
    trial: PlannedTrial,
    run_spec: ResolvedRunSpec,
    outcome: RunTrialOutcome,
) -> bool:
    if record.run_id != str(trial.run_identity.id):
        return False
    if record.task_id != trial.task_release.task_id or record.input.task_kind != trial.execution_family:
        return False
    if record.input.visibility != trial.task_metadata.visibility:
        return False
    if record.agent.adapter != trial.agent_condition.adapter or record.agent.model != trial.agent_condition.model:
        return False
    if record.environment.compute_backend != trial.compute.backend:
        return False
    if record.attempt != 1:
        return False
    expected_revision = (
        trial.task_release.artifact.sha256
        if isinstance(trial.task_release, ArtifactTaskSnapshotRef)
        else trial.task_release.source_revision
        if isinstance(trial.task_release, RepositoryTaskSnapshotRef)
        else None
    )
    if expected_revision is not None and record.input.task_revision != expected_revision:
        return False
    if record.evidence_status in {EvidenceStatus.PENDING, EvidenceStatus.INCOMPLETE, EvidenceStatus.INVALID}:
        return False
    if record.evaluation_status in {EvaluationStatus.PENDING, EvaluationStatus.INVALID}:
        return False
    if outcome == "succeeded":
        if record.execution_status is not ExecutionStatus.COMPLETED or record.evaluation_status not in {
            EvaluationStatus.COMPLETED,
            EvaluationStatus.NOT_REQUESTED,
        }:
            return False
    elif outcome == "failed":
        if not (
            record.execution_status is ExecutionStatus.FAILED
            or (
                record.execution_status is ExecutionStatus.COMPLETED
                and record.evaluation_status is EvaluationStatus.FAILED
            )
        ):
            return False
    elif outcome == "cancelled":
        if record.execution_status is not ExecutionStatus.CANCELLED:
            return False
    elif outcome == "timed_out" and record.execution_status is not ExecutionStatus.FAILED:
        return False
    expected_binding = PlannedTrialBinding(
        schema_version=2,
        run_identity=run_spec.run_identity,
        trial_identity=trial.trial_identity,
        task_release=trial.task_release,
        agent_condition_identity=trial.agent_condition.identity,
        ordinal=trial.ordinal,
        repetition=trial.repetition,
        compute=trial.compute,
        family_release=trial.family_release,
        execution_family=trial.execution_family,
        evaluation_profile=trial.evaluation_profile,
        expected_authorities=run_spec.expected_authorities,
    )
    return record.planned_trial_binding == expected_binding


def _status_for(
    counts: RunAccountingCounts, conflicting_duplicate_ids: Sequence[UUID], *, cancellation_requested: bool = False
) -> RunAccountingStatus:
    if counts.invalid or counts.unexpected or conflicting_duplicate_ids:
        return "invalid"
    if counts.missing:
        return "incomplete"
    if cancellation_requested and counts.cancelled:
        return "cancelled"
    if counts.failed or counts.cancelled or counts.timed_out:
        return "complete_with_failures"
    return "complete"


__all__ = (
    "RunAccounting",
    "RunAccountingCounts",
    "RunAccountingResult",
    "RunAccountingStatus",
    "RunCompleteness",
    "RunTrialOutcome",
    "RunValidity",
    "TrialAccountingObservation",
    "account_run",
)
