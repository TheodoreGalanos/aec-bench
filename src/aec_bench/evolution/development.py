# ABOUTME: Owns the bounded development-evaluation seam used by agentic variation.
# ABOUTME: Freezes public evaluation cases and binds each scratch revision to exact trial evidence.

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import NonNegativeInt

from aec_bench.contracts.evolution import MutationSummary, VariationUsage, WorkspaceSnapshot
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.evolution.core import (
    DevelopmentAttempt,
    EvaluatedCandidate,
)
from aec_bench.evolution.evaluation import (
    CandidateEvaluationBatch,
    bind_candidate_evaluation,
    validate_trial_records,
)


class EvaluationRole(StrEnum):
    """Evaluation role recorded on evidence produced by one evaluation plane."""

    DEVELOPMENT = "development"
    HOST = "host"


class DevelopmentEvaluationProvenance(StrictModel):
    """Role and identity binding for one development TrialRecord."""

    role: EvaluationRole = EvaluationRole.DEVELOPMENT
    experiment_id: NonEmptyStr
    trial_id: NonEmptyStr
    candidate_id: NonEmptyStr
    revision: NonNegativeInt
    evaluation_case_id: NonEmptyStr

    def model_post_init(self, __context: object) -> None:
        if self.role is not EvaluationRole.DEVELOPMENT:
            raise ValueError("development evaluation provenance must use the DEVELOPMENT role")


type DevelopmentBatchPlanner = Callable[[int, int], CandidateEvaluationBatch]
type DevelopmentEvaluator = Callable[[WorkspaceSnapshot, CandidateEvaluationBatch], tuple[TrialRecord, ...]]


@dataclass
class DevelopmentEvaluationBoundary:
    """Plan one public development batch and bind exact revision evidence.

    The planner is called at most once. This boundary does not score candidates,
    accept children, update archives, or write a canonical workspace.
    """

    planner: DevelopmentBatchPlanner
    evaluator: DevelopmentEvaluator
    batch_size: int
    cycle: int = 0
    experiment_id: str | None = None
    host_experiment_id: str | None = None
    host_trial_ids: tuple[str, ...] = ()
    _batch: CandidateEvaluationBatch | None = field(default=None, init=False, repr=False)
    _planned_experiment_id: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.batch_size, bool) or not isinstance(self.batch_size, int) or self.batch_size < 1:
            raise ValueError("development batch size must be a positive integer")
        if isinstance(self.cycle, bool) or not isinstance(self.cycle, int) or self.cycle < 0:
            raise ValueError("development batch cycle must be a non-negative integer")
        if self.experiment_id is not None and not self.experiment_id.strip():
            raise ValueError("development experiment_id must not be blank")
        if self.host_experiment_id is not None and not self.host_experiment_id.strip():
            raise ValueError("host experiment_id must not be blank")
        if self.experiment_id is not None and self.experiment_id == self.host_experiment_id:
            raise ValueError("development and host experiment identities must differ")
        host_trial_ids = tuple(self.host_trial_ids)
        if any(not trial_id.strip() for trial_id in host_trial_ids):
            raise ValueError("host trial IDs must not be blank")
        if len(host_trial_ids) != len(set(host_trial_ids)):
            raise ValueError("host trial IDs must be unique")
        self.host_trial_ids = host_trial_ids

    @property
    def role(self) -> EvaluationRole:
        """Return the only role this boundary can produce."""
        return EvaluationRole.DEVELOPMENT

    @property
    def batch(self) -> CandidateEvaluationBatch:
        """Return the fixed batch, planning it on first access."""
        return self.plan()

    def plan(self) -> CandidateEvaluationBatch:
        """Plan and validate the public batch once per boundary instance."""
        if self._batch is not None:
            return self._batch
        batch = self.planner(self.batch_size, self.cycle)
        if not isinstance(batch, CandidateEvaluationBatch):
            raise TypeError("development planner must return a CandidateEvaluationBatch")
        _validate_public_batch(batch)
        experiment_ids = {trial.experiment_id for trial in batch.trials}
        if any(not experiment_id.strip() for experiment_id in experiment_ids):
            raise ValueError("development batch trial experiment IDs must not be blank")
        if len(experiment_ids) != 1:
            raise ValueError("development batch must use one experiment identity")
        planned_experiment_id = next(iter(experiment_ids))
        if self.experiment_id is not None and planned_experiment_id != self.experiment_id:
            raise ValueError("development batch trial experiment_id must match the development experiment identity")
        if self.host_experiment_id is not None and planned_experiment_id == self.host_experiment_id:
            raise ValueError("development batch must not use the host experiment identity")
        self._batch = batch
        self._planned_experiment_id = planned_experiment_id
        return batch

    def evaluate(self, snapshot: WorkspaceSnapshot, *, revision: int = 0) -> EvaluatedCandidate:
        """Evaluate one exact snapshot on the fixed public batch."""
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ValueError("development revision must be a non-negative integer")
        batch = self.plan()
        records = tuple(self.evaluator(snapshot, batch))
        validate_trial_records(records, batch)
        bound_records = _bind_development_provenance(
            records,
            batch=batch,
            candidate_id=snapshot.candidate_id,
            revision=revision,
            host_experiment_id=self.host_experiment_id,
            host_trial_ids=self.host_trial_ids,
            planned_experiment_id=self._planned_experiment_id,
        )
        return bind_candidate_evaluation(snapshot, batch, bound_records)

    def evaluate_revision(
        self,
        snapshot: WorkspaceSnapshot,
        *,
        attempt_id: str,
        revision: int,
        mutation: MutationSummary,
        hypothesis: str,
        usage_after: VariationUsage,
    ) -> DevelopmentAttempt:
        """Evaluate and bind one internal scratch revision as a development attempt."""
        evaluated = self.evaluate(snapshot, revision=revision)
        return DevelopmentAttempt(
            attempt_id=attempt_id,
            revision=revision,
            evaluated=evaluated,
            mutation=mutation,
            hypothesis=hypothesis,
            usage_after=usage_after,
        )


def make_deterministic_development_batch_planner(
    batch: CandidateEvaluationBatch,
) -> DevelopmentBatchPlanner:
    """Return a provider-free planner that always returns one exact batch."""
    if not isinstance(batch, CandidateEvaluationBatch):
        raise TypeError("batch must be a CandidateEvaluationBatch")

    def plan(_batch_size: int, _cycle: int) -> CandidateEvaluationBatch:
        return batch

    return plan


def make_deterministic_development_evaluator(
    records: Sequence[TrialRecord],
) -> DevelopmentEvaluator:
    """Return a provider-free evaluator with fixed TrialRecord values."""
    fixed_records = tuple(records)

    def evaluate(_snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch) -> tuple[TrialRecord, ...]:
        validate_trial_records(fixed_records, batch)
        return fixed_records

    return evaluate


def _validate_public_batch(batch: CandidateEvaluationBatch) -> None:
    if any(task.task.visibility is not Visibility.PUBLIC for task in batch.tasks):
        raise ValueError("development evaluation permits only PUBLIC tasks")


def _bind_development_provenance(
    records: Sequence[TrialRecord],
    *,
    batch: CandidateEvaluationBatch,
    candidate_id: str,
    revision: int,
    host_experiment_id: str | None,
    host_trial_ids: Sequence[str],
    planned_experiment_id: str | None,
) -> tuple[TrialRecord, ...]:
    trial_ids = tuple(record.trial_id for record in records)
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("development TrialRecord trial IDs must be unique")
    bound: list[TrialRecord] = []
    for record, case_id in zip(records, batch.evaluation_case_ids, strict=True):
        if record.input.visibility is not Visibility.PUBLIC:
            raise ValueError("development TrialRecord visibility must be PUBLIC")
        try:
            experiment_id = record.experiment_id
        except RuntimeError as exc:
            raise ValueError("development TrialRecord must be bound to a RunManifest") from exc
        if host_experiment_id is not None and experiment_id == host_experiment_id:
            raise ValueError("development TrialRecord must not use the host experiment identity")
        if planned_experiment_id is None or experiment_id != planned_experiment_id:
            raise ValueError(
                "development TrialRecord experiment_id must match the planned development experiment identity"
            )
        if record.trial_id in host_trial_ids:
            raise ValueError("development TrialRecord trial_id must not collide with a host trial identity")
        provenance = DevelopmentEvaluationProvenance(
            experiment_id=experiment_id,
            trial_id=record.trial_id,
            candidate_id=candidate_id,
            revision=revision,
            evaluation_case_id=case_id,
        )
        copied = record.model_copy(deep=True)
        existing = copied.pending_extensions.get("development_evaluation")
        if existing is not None and existing != provenance:
            raise ValueError("development TrialRecord provenance identity conflicts with the evaluated record")
        if existing is None:
            copied.attach_extension("development_evaluation", provenance)
        bound.append(copied)
    return tuple(bound)


__all__ = (
    "DevelopmentBatchPlanner",
    "DevelopmentEvaluationBoundary",
    "DevelopmentEvaluationProvenance",
    "DevelopmentEvaluator",
    "EvaluationRole",
    "make_deterministic_development_batch_planner",
    "make_deterministic_development_evaluator",
)
