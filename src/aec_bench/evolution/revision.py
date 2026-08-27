# ABOUTME: Owns the bounded revision-check seam used by AVO candidate proposals.
# ABOUTME: Freezes public evaluation cases and binds each scratch revision to exact trial evidence.

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import NonNegativeInt

from aec_bench.contracts.evolution import MutationSummary, ProposalUsage, WorkspaceSnapshot
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.evolution.core import (
    EvaluatedCandidate,
    RevisionAttempt,
)
from aec_bench.evolution.evaluation import (
    CandidateEvaluationBatch,
    assess_candidate,
    validate_trial_records,
)


class EvaluationRole(StrEnum):
    """Evaluation role recorded on evidence produced by one evaluation plane."""

    DEVELOPMENT = "development"
    HOST = "host"


class RevisionEvaluationProvenance(StrictModel):
    """Role and identity binding for one revision-check TrialRecord.

    The protected schema keeps the historic ``development`` role value.
    """

    role: EvaluationRole = EvaluationRole.DEVELOPMENT
    experiment_id: NonEmptyStr
    trial_id: NonEmptyStr
    candidate_id: NonEmptyStr
    revision: NonNegativeInt
    evaluation_case_id: NonEmptyStr

    def model_post_init(self, __context: object) -> None:
        if self.role is not EvaluationRole.DEVELOPMENT:
            raise ValueError("revision provenance must use the persisted DEVELOPMENT role")


type RevisionBatchPlanner = Callable[[int, int], CandidateEvaluationBatch]
type RevisionEvaluator = Callable[[WorkspaceSnapshot, CandidateEvaluationBatch], tuple[TrialRecord, ...]]


@dataclass
class RevisionEvaluation:
    """Plan one public revision batch and bind exact revision evidence.

    The planner is called at most once. This boundary does not score candidates,
    accept children, update archives, or write a canonical workspace.
    """

    planner: RevisionBatchPlanner
    evaluator: RevisionEvaluator
    batch_size: int
    cycle: int = 0
    experiment_id: str | None = None
    selection_experiment_id: str | None = None
    selection_trial_ids: tuple[str, ...] = ()
    _batch: CandidateEvaluationBatch | None = field(default=None, init=False, repr=False)
    _planned_experiment_id: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.batch_size, bool) or not isinstance(self.batch_size, int) or self.batch_size < 1:
            raise ValueError("revision batch size must be a positive integer")
        if isinstance(self.cycle, bool) or not isinstance(self.cycle, int) or self.cycle < 0:
            raise ValueError("revision batch cycle must be a non-negative integer")
        if self.experiment_id is not None and not self.experiment_id.strip():
            raise ValueError("revision experiment_id must not be blank")
        if self.selection_experiment_id is not None and not self.selection_experiment_id.strip():
            raise ValueError("selection experiment_id must not be blank")
        if self.experiment_id is not None and self.experiment_id == self.selection_experiment_id:
            raise ValueError("revision and selection experiment identities must differ")
        selection_trial_ids = tuple(self.selection_trial_ids)
        if any(not trial_id.strip() for trial_id in selection_trial_ids):
            raise ValueError("selection trial IDs must not be blank")
        if len(selection_trial_ids) != len(set(selection_trial_ids)):
            raise ValueError("selection trial IDs must be unique")
        self.selection_trial_ids = selection_trial_ids

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
            raise TypeError("revision planner must return a CandidateEvaluationBatch")
        _validate_public_batch(batch)
        experiment_ids = {trial.experiment_id for trial in batch.trials}
        if any(not experiment_id.strip() for experiment_id in experiment_ids):
            raise ValueError("revision batch trial experiment IDs must not be blank")
        if len(experiment_ids) != 1:
            raise ValueError("revision batch must use one experiment identity")
        planned_experiment_id = next(iter(experiment_ids))
        if self.experiment_id is not None and planned_experiment_id != self.experiment_id:
            raise ValueError("revision batch trial experiment_id must match the revision experiment identity")
        if self.selection_experiment_id is not None and planned_experiment_id == self.selection_experiment_id:
            raise ValueError("revision batch must not use the selection experiment identity")
        self._batch = batch
        self._planned_experiment_id = planned_experiment_id
        return batch

    def evaluate(self, snapshot: WorkspaceSnapshot, *, revision: int = 0) -> EvaluatedCandidate:
        """Evaluate one exact snapshot on the fixed public batch."""
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ValueError("revision must be a non-negative integer")
        batch = self.plan()
        records = tuple(self.evaluator(snapshot, batch))
        validate_trial_records(records, batch)
        bound_records = _bind_revision_provenance(
            records,
            batch=batch,
            candidate_id=snapshot.candidate_id,
            revision=revision,
            selection_experiment_id=self.selection_experiment_id,
            selection_trial_ids=self.selection_trial_ids,
            planned_experiment_id=self._planned_experiment_id,
        )
        return assess_candidate(snapshot, batch, bound_records)

    def evaluate_revision(
        self,
        snapshot: WorkspaceSnapshot,
        *,
        attempt_id: str,
        revision: int,
        mutation: MutationSummary,
        hypothesis: str,
        usage_after: ProposalUsage,
    ) -> RevisionAttempt:
        """Check and bind one internal scratch revision as a `RevisionAttempt`."""
        evaluated = self.evaluate(snapshot, revision=revision)
        return RevisionAttempt(
            attempt_id=attempt_id,
            revision=revision,
            evaluated=evaluated,
            mutation=mutation,
            hypothesis=hypothesis,
            usage_after=usage_after,
        )


def _validate_public_batch(batch: CandidateEvaluationBatch) -> None:
    if any(task.task.visibility is not Visibility.PUBLIC for task in batch.tasks):
        raise ValueError("revision checks permit only PUBLIC tasks")


def _bind_revision_provenance(
    records: Sequence[TrialRecord],
    *,
    batch: CandidateEvaluationBatch,
    candidate_id: str,
    revision: int,
    selection_experiment_id: str | None,
    selection_trial_ids: Sequence[str],
    planned_experiment_id: str | None,
) -> tuple[TrialRecord, ...]:
    trial_ids = tuple(record.trial_id for record in records)
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("revision TrialRecord trial IDs must be unique")
    bound: list[TrialRecord] = []
    for record, case_id in zip(records, batch.evaluation_case_ids, strict=True):
        if record.input.visibility is not Visibility.PUBLIC:
            raise ValueError("revision TrialRecord visibility must be PUBLIC")
        try:
            experiment_id = record.experiment_id
        except RuntimeError as exc:
            raise ValueError("revision TrialRecord must be bound to a RunManifest") from exc
        if selection_experiment_id is not None and experiment_id == selection_experiment_id:
            raise ValueError("revision TrialRecord must not use the selection experiment identity")
        if planned_experiment_id is None or experiment_id != planned_experiment_id:
            raise ValueError("revision TrialRecord experiment_id must match the planned revision experiment identity")
        if record.trial_id in selection_trial_ids:
            raise ValueError("revision TrialRecord trial_id must not collide with a selection trial identity")
        provenance = RevisionEvaluationProvenance(
            experiment_id=experiment_id,
            trial_id=record.trial_id,
            candidate_id=candidate_id,
            revision=revision,
            evaluation_case_id=case_id,
        )
        copied = record.model_copy(deep=True)
        existing = copied.pending_extensions.get("development_evaluation")
        if existing is not None and existing != provenance:
            raise ValueError("revision TrialRecord provenance identity conflicts with the evaluated record")
        if existing is None:
            copied.attach_extension("development_evaluation", provenance)
        bound.append(copied)
    return tuple(bound)


__all__ = (
    "RevisionEvaluation",
    "RevisionEvaluationProvenance",
    "EvaluationRole",
    "RevisionBatchPlanner",
    "RevisionEvaluator",
)
