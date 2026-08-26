# ABOUTME: Immutable functional values for candidate evaluation and evolution cycles.
# ABOUTME: Binds each workspace candidate to its exact evidence before search decisions use it.

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionCycleRecord,
    EvolutionObservation,
    GateDecision,
    MutationStrategy,
    MutationSummary,
    SelectionRecord,
    WorkspaceSnapshot,
)
from aec_bench.evolution.analysis import EvolutionAnalysis, GraduatedScope
from aec_bench.evolution.graveyard import GraveyardEntry


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
    def from_baseline(cls, baseline: EvaluatedCandidate) -> EvolutionState:
        """Create state from the baseline's exact assessment, not a default score."""
        score = baseline.assessment.batch_score
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

    def __post_init__(self) -> None:
        _require_text(self.reason, "gate reason")


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
