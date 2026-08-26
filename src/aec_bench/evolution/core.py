# ABOUTME: Immutable functional values for candidate evaluation and evolution cycles.
# ABOUTME: Binds each workspace candidate to its exact evidence before search decisions use it.

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionConfig,
    EvolutionCycleRecord,
    EvolutionObservation,
    GateDecision,
    MutationStrategy,
    MutationSummary,
    ObservationEnrichment,
    SelectionRecord,
    WorkspaceSnapshot,
)
from aec_bench.contracts.trial_record import EvaluationStatus, ExecutionStatus, TrialRecord
from aec_bench.evolution.analysis import EvolutionAnalysis, GraduatedScope
from aec_bench.evolution.graveyard import GraveyardEntry
from aec_bench.tasks.instance import ResolvedTaskInstance
from aec_bench.trials import PlannedTrial


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _extension_candidate_ids(value: Any) -> tuple[str, ...]:
    """Read candidate IDs from an attached trial extension when one exposes it."""
    if isinstance(value, Mapping):
        candidate_id = value.get("candidate_id")
    else:
        candidate_id = getattr(value, "candidate_id", None)
    if candidate_id is None:
        return ()
    if not isinstance(candidate_id, str):
        raise ValueError("trial extension candidate_id must be a string")
    return (candidate_id,)


def _validate_observation_candidate(observation: EvolutionObservation, candidate_id: str) -> None:
    if observation.candidate_id != candidate_id:
        raise ValueError("observation candidate_id must match the snapshot candidate_id")
    for extension in observation.trial.pending_extensions.values():
        extension_ids = _extension_candidate_ids(extension)
        if extension_ids and extension_ids[0] != candidate_id:
            raise ValueError("trial extension candidate_id must match the snapshot candidate_id")


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
    enrichments: Sequence[ObservationEnrichment] | None = None,
    batch: CandidateEvaluationBatch | None = None,
) -> tuple[EvolutionObservation, ...]:
    """Build ordered observations from the exact records returned by evaluation."""
    _require_text(candidate_id, "candidate_id")
    records = tuple(trial_records)
    selected_enrichments = tuple(enrichments or ())
    if selected_enrichments and len(selected_enrichments) != len(records):
        raise ValueError("observation enrichment count must match trial record count")
    if batch is not None:
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
    _validate_observation_order(observations, candidate_id, batch)
    return observations


def _validate_observation_order(
    observations: Sequence[EvolutionObservation],
    candidate_id: str,
    batch: CandidateEvaluationBatch | None,
) -> None:
    observed_candidate_ids = tuple(observation.candidate_id for observation in observations)
    if any(observed != candidate_id for observed in observed_candidate_ids):
        raise ValueError("enriched observations must retain the evaluated candidate_id")
    trial_ids = tuple(observation.trial.trial_id for observation in observations)
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("enriched observation trial IDs must be unique")
    if batch is not None:
        validate_trial_records(tuple(observation.trial for observation in observations), batch)


def validate_enriched_observations(
    observations: Sequence[EvolutionObservation],
    *,
    candidate_id: str,
    batch: CandidateEvaluationBatch,
) -> None:
    """Validate that enrichment preserved candidate, trial, task, and order identity."""
    _require_text(candidate_id, "candidate_id")
    _validate_observation_order(observations, candidate_id, batch)


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
    _validate_observation_order(ordered_observations, candidate_id, batch)
    if not ordered_observations:
        raise ValueError("candidate assessment evidence must not be empty")
    rewards: list[float] = []
    invalid_reasons: list[str] = []
    discipline_rewards: dict[str, list[float]] = {}
    structural_scores: list[float] = []
    for observation in ordered_observations:
        record = observation.trial
        evaluation = record.evaluation
        if evaluation is None or record.evaluation_status is not EvaluationStatus.COMPLETED:
            invalid_reasons.append(f"trial {record.trial_id} has no completed evaluation")
            continue
        if record.execution_status is not ExecutionStatus.COMPLETED:
            invalid_reasons.append(f"trial {record.trial_id} execution status is {record.execution_status.value}")
        rewards.append(evaluation.reward)
        discipline_rewards.setdefault(observation.discipline, []).append(evaluation.reward)
        validity = evaluation.validity
        if not (validity.output_parseable and validity.schema_valid and validity.verifier_completed):
            invalid_reasons.extend(validity.errors or (f"trial {record.trial_id} failed evaluation validity",))
        if observation.enrichment.structural_score is not None:
            structural_scores.append(observation.enrichment.structural_score.cosine_similarity)

    if not rewards:
        batch_score = 0.0
    else:
        batch_score = sum(rewards) / len(rewards)
    discipline_scores = {
        discipline: sum(scores) / len(scores) for discipline, scores in sorted(discipline_rewards.items())
    }
    return CandidateAssessment(
        candidate_id=candidate_id,
        batch_score=batch_score,
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


def validate_comparable_candidates(parent: EvaluatedCandidate, child: EvaluatedCandidate) -> None:
    """Require parent and child to use the same ordered evaluation cases."""
    if parent.assessment.evaluation_case_ids != child.assessment.evaluation_case_ids:
        raise ValueError("parent and child must use identical evaluation_case_ids")


def _extract_discipline(task_id: str) -> str:
    """Return the task's leading discipline component."""
    return task_id.split("/", maxsplit=1)[0]


@dataclass(frozen=True)
class EvaluatedCandidate:
    """One workspace snapshot and the complete evidence produced by that snapshot."""

    snapshot: WorkspaceSnapshot
    observations: tuple[EvolutionObservation, ...]
    assessment: CandidateAssessment

    def __post_init__(self) -> None:
        if not self.observations:
            raise ValueError("evaluated candidate evidence must not be empty")
        object.__setattr__(self, "observations", tuple(self.observations))
        candidate_id = self.snapshot.candidate_id
        if self.assessment.candidate_id != candidate_id:
            raise ValueError("assessment candidate_id must match the snapshot candidate_id")
        observation_trial_ids: list[str] = []
        for observation in self.observations:
            _validate_observation_candidate(observation, candidate_id)
            observation_trial_ids.append(observation.trial.trial_id)
        if len(observation_trial_ids) != len(set(observation_trial_ids)):
            raise ValueError("evaluated candidate trial IDs must be unique")
        if tuple(observation_trial_ids) != self.assessment.trial_ids:
            raise ValueError("assessment trial_ids must match the evidence order exactly")


def bind_evaluated_candidate(
    snapshot: WorkspaceSnapshot,
    observations: tuple[EvolutionObservation, ...],
    assessment: CandidateAssessment,
) -> EvaluatedCandidate:
    """Validate and bind a candidate snapshot to its evaluation evidence."""
    return EvaluatedCandidate(snapshot=snapshot, observations=observations, assessment=assessment)


@dataclass(frozen=True)
class SelectionPlan:
    """The validated parent and inspiration request for one variation cycle."""

    parent_candidate_id: str
    inspiration_candidate_ids: tuple[str, ...]
    strategy: MutationStrategy
    goal: str
    reasoning: str

    def __post_init__(self) -> None:
        _require_text(self.parent_candidate_id, "parent_candidate_id")
        _require_text(self.goal, "goal")
        _require_text(self.reasoning, "reasoning")
        object.__setattr__(self, "inspiration_candidate_ids", tuple(self.inspiration_candidate_ids))
        try:
            strategy = MutationStrategy(self.strategy)
        except ValueError as exc:
            raise ValueError(f"unsupported mutation strategy: {self.strategy!r}") from exc
        object.__setattr__(self, "strategy", strategy)
        for candidate_id in self.inspiration_candidate_ids:
            _require_text(candidate_id, "inspiration_candidate_id")
        if len(self.inspiration_candidate_ids) != len(set(self.inspiration_candidate_ids)):
            raise ValueError("selection inspiration candidate IDs must be unique")
        if self.parent_candidate_id in self.inspiration_candidate_ids:
            raise ValueError("selection parent cannot also be an inspiration")

    def to_record(self) -> SelectionRecord:
        """Project this internal selection value to its persisted summary."""
        return SelectionRecord(
            parent_candidate_id=self.parent_candidate_id,
            inspiration_candidate_ids=self.inspiration_candidate_ids,
            strategy=self.strategy,
            goal=self.goal,
            reasoning=self.reasoning,
        )


@dataclass(frozen=True)
class VariationRequest:
    """Inputs supplied to a variation operator after parent evaluation."""

    selection: SelectionPlan
    parent: EvaluatedCandidate
    inspirations: tuple[WorkspaceSnapshot, ...]
    analysis: EvolutionAnalysis
    scope: GraduatedScope
    history: tuple[EvolutionCycleRecord, ...]
    graveyard: tuple[GraveyardEntry, ...]

    def __post_init__(self) -> None:
        if self.parent.snapshot.candidate_id != self.selection.parent_candidate_id:
            raise ValueError("variation parent must match the selection parent_candidate_id")
        object.__setattr__(self, "inspirations", tuple(self.inspirations))
        inspiration_ids = tuple(snapshot.candidate_id for snapshot in self.inspirations)
        if inspiration_ids != self.selection.inspiration_candidate_ids:
            raise ValueError("variation inspirations must match the selected candidate IDs exactly")
        object.__setattr__(self, "history", tuple(self.history))
        object.__setattr__(self, "graveyard", tuple(self.graveyard))


class VariationStatus(StrEnum):
    """Status values returned by a variation operator."""

    SUBMITTED = "submitted"
    ABSTAINED = "abstained"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True)
class VariationResult:
    """One submitted child or an explicit variation abstention."""

    status: VariationStatus
    child: WorkspaceSnapshot | None
    mutation: MutationSummary | None
    reasoning: str
    model_cost_usd: float

    def __post_init__(self) -> None:
        status = VariationStatus(self.status)
        object.__setattr__(self, "status", status)
        if not math.isfinite(self.model_cost_usd) or self.model_cost_usd < 0:
            raise ValueError("model_cost_usd must be a finite non-negative number")
        if status == VariationStatus.SUBMITTED and (self.child is None or self.mutation is None):
            raise ValueError("submitted variation requires a child and mutation summary")
        if status == VariationStatus.ABSTAINED and self.child is not None:
            raise ValueError("abstained variation must not contain a child")


@dataclass(frozen=True)
class EvolutionState:
    """Explicit hill-climb state used by pure evolution transitions."""

    cycle: int
    active_candidate_id: str
    best_candidate_id: str
    best_score: float
    cycles_without_improvement: int
    best_score_history: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.cycle < 0 or self.cycles_without_improvement < 0:
            raise ValueError("evolution state counters must be non-negative")
        _require_text(self.active_candidate_id, "active_candidate_id")
        _require_text(self.best_candidate_id, "best_candidate_id")
        if not math.isfinite(self.best_score):
            raise ValueError("best_score must be finite")
        history = tuple(self.best_score_history)
        if any(not math.isfinite(score) for score in history):
            raise ValueError("best_score_history values must be finite")
        object.__setattr__(self, "best_score_history", history)

    @classmethod
    def from_baseline(
        cls,
        baseline: EvaluatedCandidate,
        *,
        structural_weight: float = 0.0,
    ) -> EvolutionState:
        """Create state from the exact evaluated baseline rather than a default score."""
        score = assessment_score(baseline.assessment, structural_weight=structural_weight)
        return cls(
            cycle=0,
            active_candidate_id=baseline.snapshot.candidate_id,
            best_candidate_id=baseline.snapshot.candidate_id,
            best_score=score,
            cycles_without_improvement=0,
            best_score_history=(score,),
        )


@dataclass(frozen=True)
class GateResult:
    """Decision and reason produced by the search-specific candidate gate."""

    decision: GateDecision
    reason: str
    effective_score: float | None = None
    improved: bool = False
    cycles_without_improvement: int | None = None

    def __post_init__(self) -> None:
        _require_text(self.reason, "gate reason")
        if self.effective_score is not None and not math.isfinite(self.effective_score):
            raise ValueError("gate effective_score must be finite")
        if self.cycles_without_improvement is not None and self.cycles_without_improvement < 0:
            raise ValueError("gate stagnation counter must be non-negative")


@dataclass(frozen=True)
class CycleOutcome:
    """Complete functional outcome from one parent-selection and variation cycle."""

    cycle: int
    selection: SelectionPlan
    parent: EvaluatedCandidate
    variation: VariationResult
    child: EvaluatedCandidate | None
    decision: GateResult
    active_candidate_id_after: str
    best_candidate_id_after: str

    def __post_init__(self) -> None:
        if self.cycle < 1:
            raise ValueError("cycle must be positive")
        if self.parent.snapshot.candidate_id != self.selection.parent_candidate_id:
            raise ValueError("cycle parent must match the selection parent_candidate_id")
        if self.variation.status is VariationStatus.SUBMITTED and self.child is None:
            raise ValueError("submitted variation requires a bound evaluated child")
        if self.child is not None and self.variation.child is not None:
            if self.child.snapshot.candidate_id == self.parent.snapshot.candidate_id:
                raise ValueError("submitted child candidate_id must differ from the parent")
            if self.child.snapshot.candidate_id != self.variation.child.candidate_id:
                raise ValueError("evaluated child must match the submitted variation child")
        _require_text(self.active_candidate_id_after, "active_candidate_id_after")
        _require_text(self.best_candidate_id_after, "best_candidate_id_after")

    def to_record(self, timestamp: datetime) -> EvolutionCycleRecord:
        """Project this exact outcome to the persisted cycle summary."""
        return EvolutionCycleRecord(
            cycle=self.cycle,
            selection=self.selection.to_record(),
            parent_assessment=self.parent.assessment,
            child_assessment=None if self.child is None else self.child.assessment,
            mutation=self.variation.mutation,
            gate_decision=self.decision.decision,
            gate_reason=self.decision.reason,
            active_candidate_id_after=self.active_candidate_id_after,
            best_candidate_id_after=self.best_candidate_id_after,
            timestamp=timestamp,
            evolver_cost_usd=self.variation.model_cost_usd,
        )


def assessment_score(assessment: CandidateAssessment, *, structural_weight: float) -> float:
    """Return the configured gate score for one candidate assessment."""
    if not math.isfinite(structural_weight) or not 0.0 <= structural_weight <= 1.0:
        raise ValueError("structural_weight must be finite and between 0.0 and 1.0")
    if assessment.structural_score is None:
        return assessment.batch_score
    return assessment.batch_score * (1.0 - structural_weight) + assessment.structural_score * structural_weight


def decide_candidate(
    *,
    parent: EvaluatedCandidate,
    child: EvaluatedCandidate | None,
    variation: VariationResult,
    state: EvolutionState,
    config: EvolutionConfig,
) -> GateResult:
    """Apply configured acceptance and stagnation policy without side effects."""
    if variation.status is not VariationStatus.SUBMITTED:
        reason = {
            VariationStatus.ABSTAINED: "variation abstained",
            VariationStatus.BUDGET_EXHAUSTED: "variation budget exhausted",
        }[variation.status]
        return GateResult(
            decision=GateDecision.SKIPPED,
            reason=reason,
            cycles_without_improvement=state.cycles_without_improvement,
        )
    if child is None or variation.child is None:
        raise ValueError("submitted variation requires an evaluated child")
    if child.snapshot.candidate_id != variation.child.candidate_id:
        raise ValueError("evaluated child must match the submitted variation child")
    if child.snapshot.candidate_id == parent.snapshot.candidate_id:
        raise ValueError("submitted child candidate_id must differ from the parent")
    if parent.assessment.evaluation_case_ids != child.assessment.evaluation_case_ids:
        raise ValueError("parent and child must use the same evaluation cases")
    if not child.assessment.valid:
        reasons = "; ".join(child.assessment.invalid_reasons)
        count = state.cycles_without_improvement + 1
        return GateResult(
            decision=GateDecision.REJECTED,
            reason=f"child evaluation is invalid: {reasons}",
            effective_score=assessment_score(child.assessment, structural_weight=config.structural_weight),
            cycles_without_improvement=count,
        )

    score = assessment_score(child.assessment, structural_weight=config.structural_weight)
    improved = score > state.best_score + config.improvement_threshold
    stagnation_count = 0 if improved else state.cycles_without_improvement + 1
    if stagnation_count >= config.stagnation_window:
        return GateResult(
            decision=GateDecision.REJECTED,
            reason=f"stagnation for {stagnation_count} cycles without improvement",
            effective_score=score,
            improved=improved,
            cycles_without_improvement=stagnation_count,
        )
    return GateResult(
        decision=GateDecision.ACCEPTED,
        reason=f"candidate score {score:.3f} passed the configured gate",
        effective_score=score,
        improved=improved,
        cycles_without_improvement=stagnation_count,
    )


def reduce_evolution_state(
    *,
    state: EvolutionState,
    parent: EvaluatedCandidate,
    child: EvaluatedCandidate | None,
    decision: GateResult,
) -> EvolutionState:
    """Return the next explicit search state for one exact cycle outcome."""
    if decision.decision is GateDecision.SKIPPED:
        active_candidate_id = state.active_candidate_id
    elif child is not None and decision.decision is GateDecision.ACCEPTED:
        active_candidate_id = child.snapshot.candidate_id
    else:
        active_candidate_id = parent.snapshot.candidate_id

    best_candidate_id = state.best_candidate_id
    best_score = state.best_score
    if child is not None and decision.improved and decision.effective_score is not None:
        best_candidate_id = child.snapshot.candidate_id
        best_score = decision.effective_score

    if decision.cycles_without_improvement is None:
        stagnation_count = (
            state.cycles_without_improvement
            if decision.decision is GateDecision.SKIPPED
            else state.cycles_without_improvement + (0 if decision.improved else 1)
        )
    else:
        stagnation_count = decision.cycles_without_improvement

    score_history = (*state.best_score_history, best_score)
    return EvolutionState(
        cycle=state.cycle + 1,
        active_candidate_id=active_candidate_id,
        best_candidate_id=best_candidate_id,
        best_score=best_score,
        cycles_without_improvement=stagnation_count,
        best_score_history=score_history,
    )
