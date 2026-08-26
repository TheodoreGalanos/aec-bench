# ABOUTME: Candidate-independent evaluation planning and exact evidence binding.
# ABOUTME: Keeps task resolution and TrialRecord projections outside the pure evolution core.

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    ObservationEnrichment,
    WorkspaceSnapshot,
)
from aec_bench.contracts.trial_record import EvaluationStatus, ExecutionStatus, TrialRecord
from aec_bench.evolution.core import EvaluatedCandidate
from aec_bench.tasks.instance import ResolvedTaskInstance
from aec_bench.trials import PlannedTrial


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


@dataclass(frozen=True)
class CandidateEvaluationBatch:
    """Candidate-independent task and trial cases evaluated in one cycle."""

    tasks: tuple[ResolvedTaskInstance, ...]
    trials: tuple[PlannedTrial, ...]
    evaluation_case_ids: tuple[str, ...]
    cycle: int = 0

    def __post_init__(self) -> None:
        tasks = tuple(self.tasks)
        trials = tuple(self.trials)
        case_ids = tuple(self.evaluation_case_ids)
        if self.cycle < 0:
            raise ValueError("evaluation batch cycle must be non-negative")
        if not tasks:
            raise ValueError("evaluation batch tasks must not be empty")
        if not trials:
            raise ValueError("evaluation batch trials must not be empty")
        task_ids = tuple(task.task.task_id for task in tasks)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("evaluation batch task IDs must be unique")
        trial_ids = tuple(trial.trial_id for trial in trials)
        if len(trial_ids) != len(set(trial_ids)):
            raise ValueError("evaluation batch trial IDs must be unique")
        if not case_ids:
            raise ValueError("evaluation batch case IDs must not be empty")
        if len(case_ids) != len(trials):
            raise ValueError("evaluation batch case IDs must match trial cardinality")
        if any(not case_id.strip() for case_id in case_ids):
            raise ValueError("evaluation batch case IDs must not be blank")
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation batch case IDs must be unique")
        unknown_task_ids = {trial.task_id for trial in trials} - set(task_ids)
        if unknown_task_ids:
            raise ValueError(f"evaluation batch trials reference unresolved tasks: {sorted(unknown_task_ids)}")
        object.__setattr__(self, "tasks", tasks)
        object.__setattr__(self, "trials", trials)
        object.__setattr__(self, "evaluation_case_ids", case_ids)


CandidateBatchPlanner = Callable[[int, int], CandidateEvaluationBatch]
CandidateEvaluator = Callable[[WorkspaceSnapshot, CandidateEvaluationBatch], tuple[TrialRecord, ...]]


def build_observations(
    trial_records: Sequence[TrialRecord],
    candidate_id: str,
    *,
    batch: CandidateEvaluationBatch,
    enrichments: Sequence[ObservationEnrichment] | None = None,
) -> tuple[EvolutionObservation, ...]:
    """Build ordered observations from the exact records returned by evaluation."""
    _require_text(candidate_id, "candidate_id")
    records = tuple(trial_records)
    selected_enrichments = tuple(enrichments or ())
    if selected_enrichments and len(selected_enrichments) != len(records):
        raise ValueError("observation enrichment count must match trial record count")
    validate_trial_records(records, batch)

    observations = tuple(
        EvolutionObservation(
            trial=record,
            enrichment=selected_enrichments[index] if selected_enrichments else ObservationEnrichment(),
            candidate_id=candidate_id,
            discipline=_extract_discipline(record.task_id),
        )
        for index, record in enumerate(records)
    )
    validate_enriched_observations(observations, candidate_id=candidate_id, batch=batch)
    return observations


def validate_enriched_observations(
    observations: Sequence[EvolutionObservation],
    *,
    candidate_id: str,
    batch: CandidateEvaluationBatch,
) -> None:
    """Validate that enrichment preserved candidate, trial, task, and order identity."""
    _require_text(candidate_id, "candidate_id")
    observed_candidate_ids = tuple(observation.candidate_id for observation in observations)
    if any(observed != candidate_id for observed in observed_candidate_ids):
        raise ValueError("enriched observations must retain the evaluated candidate_id")
    trial_ids = tuple(observation.trial.trial_id for observation in observations)
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("enriched observation trial IDs must be unique")
    validate_trial_records(tuple(observation.trial for observation in observations), batch)


def validate_trial_records(records: Sequence[TrialRecord], batch: CandidateEvaluationBatch) -> None:
    """Check that returned records preserve every planned task and attempt case."""
    if len(records) != len(batch.trials):
        raise ValueError("trial record count must match the evaluation batch cardinality")
    for record, planned in zip(records, batch.trials, strict=True):
        if record.task_id != planned.task_id:
            raise ValueError("trial record task_id must match its planned evaluation case")
        if record.attempt != planned.repetition:
            raise ValueError("trial record attempt must match its planned evaluation case")


def build_candidate_assessment(
    candidate_id: str,
    batch: CandidateEvaluationBatch,
    observations: Sequence[EvolutionObservation],
) -> CandidateAssessment:
    """Project exact trial evaluation results into one candidate assessment."""
    _require_text(candidate_id, "candidate_id")
    ordered_observations = tuple(observations)
    validate_enriched_observations(ordered_observations, candidate_id=candidate_id, batch=batch)
    if not ordered_observations:
        raise ValueError("candidate assessment evidence must not be empty")
    rewards: list[float] = []
    invalid_reasons: list[str] = []
    discipline_rewards: dict[str, list[float]] = {}
    structural_scores: list[float] = []
    for observation in ordered_observations:
        record = observation.trial
        evaluation = record.evaluation
        if evaluation is None:
            raise ValueError(f"trial {record.trial_id} has no EvaluationResult evidence")
        rewards.append(evaluation.reward)
        discipline_rewards.setdefault(observation.discipline, []).append(evaluation.reward)
        if record.evaluation_status is not EvaluationStatus.COMPLETED:
            invalid_reasons.append(f"trial {record.trial_id}: evaluation status is {record.evaluation_status.value}")
        if record.execution_status is not ExecutionStatus.COMPLETED:
            invalid_reasons.append(f"trial {record.trial_id}: execution status is {record.execution_status.value}")
        validity = evaluation.validity
        if not (validity.output_parseable and validity.schema_valid and validity.verifier_completed):
            validity_reasons = validity.errors or ("evaluation validity checks failed",)
            invalid_reasons.extend(f"trial {record.trial_id}: {reason}" for reason in validity_reasons)
        if observation.enrichment.structural_score is not None:
            structural_scores.append(observation.enrichment.structural_score.cosine_similarity)

    discipline_scores = {
        discipline: sum(scores) / len(scores) for discipline, scores in sorted(discipline_rewards.items())
    }
    return CandidateAssessment(
        candidate_id=candidate_id,
        batch_score=sum(rewards) / len(rewards),
        structural_score=(sum(structural_scores) / len(structural_scores) if structural_scores else None),
        discipline_scores=discipline_scores,
        trial_ids=tuple(observation.trial.trial_id for observation in ordered_observations),
        evaluation_case_ids=batch.evaluation_case_ids,
        valid=not invalid_reasons,
        invalid_reasons=tuple(dict.fromkeys(invalid_reasons)),
    )


def bind_candidate_evaluation(
    snapshot: WorkspaceSnapshot,
    batch: CandidateEvaluationBatch,
    trial_records: Sequence[TrialRecord],
    *,
    enrichments: Sequence[ObservationEnrichment] | None = None,
) -> EvaluatedCandidate:
    """Build and bind one candidate to the exact batch records it produced."""
    observations = build_observations(
        trial_records,
        snapshot.candidate_id,
        enrichments=enrichments,
        batch=batch,
    )
    assessment = build_candidate_assessment(snapshot.candidate_id, batch, observations)
    return bind_evaluated_candidate(snapshot, observations, assessment)


def bind_evaluated_candidate(
    snapshot: WorkspaceSnapshot,
    observations: Sequence[EvolutionObservation],
    assessment: CandidateAssessment,
) -> EvaluatedCandidate:
    """Validate and bind a candidate snapshot to its evaluation evidence."""
    return EvaluatedCandidate(snapshot=snapshot, observations=tuple(observations), assessment=assessment)


def validate_comparable_candidates(parent: EvaluatedCandidate, child: EvaluatedCandidate) -> None:
    """Require parent and child to use the same ordered evaluation cases."""
    if parent.assessment.evaluation_case_ids != child.assessment.evaluation_case_ids:
        raise ValueError("parent and child must use identical evaluation_case_ids")


def _extract_discipline(task_id: str) -> str:
    """Return the task's leading discipline component."""
    return task_id.split("/", maxsplit=1)[0]


__all__ = (
    "CandidateBatchPlanner",
    "CandidateEvaluationBatch",
    "CandidateEvaluator",
    "bind_candidate_evaluation",
    "bind_evaluated_candidate",
    "build_candidate_assessment",
    "build_observations",
    "validate_comparable_candidates",
    "validate_enriched_observations",
    "validate_trial_records",
)
