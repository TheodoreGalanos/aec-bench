# ABOUTME: Immutable functional values for candidate evaluation and evolution cycles.
# ABOUTME: Binds each workspace candidate to its exact evidence before search decisions use it.

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionConfig,
    EvolutionCycleRecord,
    EvolutionObservation,
    GateDecision,
    MutationStrategy,
    MutationSummary,
    SelectionRecord,
    VariationUsage,
    WorkspaceSnapshot,
)
from aec_bench.evolution.analysis import EvolutionAnalysis, GraduatedScope
from aec_bench.evolution.graveyard import GraveyardEntry
from aec_bench.evolution.memory import AVO_MEMORY_LIMIT, AVOMemoryEntry, validate_memory_entries

if TYPE_CHECKING:
    from aec_bench.evolution.supervision import AVOSupervisionRecord


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_non_negative_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_positive_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_finite_non_negative(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{field_name} must be a finite non-negative number")


def _require_finite_positive(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be a finite positive number")


def _same_workspace_material(left: WorkspaceSnapshot, right: WorkspaceSnapshot) -> bool:
    return left.system_prompt == right.system_prompt and left.skills == right.skills


@dataclass(frozen=True)
class AVOBudget:
    """Hard limits for one bounded agentic variation call."""

    max_model_requests: int = 12
    max_tool_calls: int = 40
    max_development_evaluations: int = 7
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_elapsed_seconds: float = 1800.0
    max_consecutive_evaluation_errors: int = 2
    max_stagnant_evaluations: int = 3
    max_supervisor_interventions: int = 1
    max_cost_usd: float | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "max_model_requests",
            "max_tool_calls",
            "max_development_evaluations",
            "max_consecutive_evaluation_errors",
            "max_stagnant_evaluations",
        ):
            _require_positive_integer(getattr(self, field_name), field_name)
        _require_finite_positive(self.max_elapsed_seconds, "max_elapsed_seconds")
        _require_non_negative_integer(self.max_supervisor_interventions, "max_supervisor_interventions")
        for field_name in ("max_input_tokens", "max_output_tokens"):
            limit = getattr(self, field_name)
            if limit is not None:
                _require_positive_integer(limit, field_name)
        if self.max_cost_usd is not None:
            _require_finite_positive(self.max_cost_usd, "max_cost_usd")


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


@dataclass(frozen=True)
class DevelopmentAttempt:
    """One exact scratch revision and its development evaluation evidence."""

    attempt_id: str
    revision: int
    evaluated: EvaluatedCandidate
    mutation: MutationSummary
    hypothesis: str
    usage_after: VariationUsage

    def __post_init__(self) -> None:
        _require_text(self.attempt_id, "attempt_id")
        _require_non_negative_integer(self.revision, "revision")
        if not isinstance(self.evaluated, EvaluatedCandidate):
            raise TypeError("evaluated must be an EvaluatedCandidate")
        if not isinstance(self.mutation, MutationSummary):
            raise TypeError("mutation must be a MutationSummary")
        _require_text(self.hypothesis, "hypothesis")
        if not isinstance(self.usage_after, VariationUsage):
            raise TypeError("usage_after must be a VariationUsage")
        if self.usage_after.development_evaluations < 1:
            raise ValueError("development attempt usage must include one development evaluation")


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
class ResolvedSelection:
    """A validated selection plan with the selected candidate material."""

    plan: SelectionPlan
    parent: WorkspaceSnapshot
    inspirations: tuple[WorkspaceSnapshot, ...]

    def __post_init__(self) -> None:
        if self.parent.candidate_id != self.plan.parent_candidate_id:
            raise ValueError("resolved parent must match the selection parent_candidate_id")
        inspirations = tuple(self.inspirations)
        inspiration_ids = tuple(snapshot.candidate_id for snapshot in inspirations)
        if inspiration_ids != self.plan.inspiration_candidate_ids:
            raise ValueError("resolved inspirations must match the selection candidate IDs exactly")
        object.__setattr__(self, "inspirations", inspirations)


@dataclass(frozen=True)
class VariationRequest:
    """Inputs supplied to a variation operator after parent evaluation."""

    run_id: str
    selection: SelectionPlan
    parent: EvaluatedCandidate
    inspirations: tuple[WorkspaceSnapshot, ...]
    analysis: EvolutionAnalysis
    scope: GraduatedScope
    history: tuple[EvolutionCycleRecord, ...]
    graveyard: tuple[GraveyardEntry, ...]
    cycle: int = 1
    memory: tuple[AVOMemoryEntry, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if self.parent.snapshot.candidate_id != self.selection.parent_candidate_id:
            raise ValueError("variation parent must match the selection parent_candidate_id")
        _require_positive_integer(self.cycle, "variation cycle")
        object.__setattr__(self, "inspirations", tuple(self.inspirations))
        inspiration_ids = tuple(snapshot.candidate_id for snapshot in self.inspirations)
        if inspiration_ids != self.selection.inspiration_candidate_ids:
            raise ValueError("variation inspirations must match the selected candidate IDs exactly")
        object.__setattr__(self, "history", tuple(self.history))
        object.__setattr__(self, "graveyard", tuple(self.graveyard))
        memory = validate_memory_entries(self.memory)
        if len(memory) > AVO_MEMORY_LIMIT:
            raise ValueError(f"variation memory must contain at most {AVO_MEMORY_LIMIT} entries")
        object.__setattr__(self, "memory", memory)


class VariationStatus(StrEnum):
    """Status values returned by a variation operator."""

    SUBMITTED = "submitted"
    ABSTAINED = "abstained"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class AVOState:
    """Explicit state for one bounded agentic variation call."""

    variation_id: str
    parent_candidate_id: str
    child_candidate_id: str
    current_revision: int
    attempts: tuple[DevelopmentAttempt, ...] = ()
    best_attempt_id: str | None = None
    consecutive_without_progress: int = 0
    consecutive_evaluation_errors: int = 0
    exhausted_direction_requested: bool = False
    supervision_records: tuple[AVOSupervisionRecord, ...] = ()
    memory: tuple[AVOMemoryEntry, ...] = ()
    usage: VariationUsage = VariationUsage()
    terminal_status: VariationStatus | None = None
    parent_snapshot: WorkspaceSnapshot | None = None

    def __post_init__(self) -> None:
        for field_name in ("variation_id", "parent_candidate_id", "child_candidate_id"):
            _require_text(getattr(self, field_name), field_name)
        _require_non_negative_integer(self.current_revision, "current_revision")
        _require_non_negative_integer(self.consecutive_without_progress, "consecutive_without_progress")
        _require_non_negative_integer(self.consecutive_evaluation_errors, "consecutive_evaluation_errors")
        if not isinstance(self.exhausted_direction_requested, bool):
            raise TypeError("exhausted_direction_requested must be a boolean")
        if not isinstance(self.usage, VariationUsage):
            raise TypeError("usage must be a VariationUsage")
        records = tuple(self.supervision_records)
        if any(record is None for record in records):
            raise TypeError("supervision_records must not contain None")
        if records:
            # Keep the foundational core independent from the supervision
            # adapter while still rejecting untyped state at this boundary.
            from aec_bench.evolution.supervision import AVOSupervisionRecord

            if any(not isinstance(record, AVOSupervisionRecord) for record in records):
                raise TypeError("supervision_records must contain AVOSupervisionRecord values")
        if len(records) > self.usage.supervisor_interventions:
            raise ValueError("supervision_records cannot exceed supervisor_interventions usage")
        if self.terminal_status is not None and self.exhausted_direction_requested:
            raise ValueError("terminal AVO state cannot retain a pending exhausted-direction request")
        object.__setattr__(self, "supervision_records", records)
        attempts = tuple(self.attempts)
        if any(not isinstance(attempt, DevelopmentAttempt) for attempt in attempts):
            raise TypeError("attempts must contain DevelopmentAttempt values")
        attempt_ids = tuple(attempt.attempt_id for attempt in attempts)
        if len(attempt_ids) != len(set(attempt_ids)):
            raise ValueError("attempt IDs must be unique")
        revisions = tuple(attempt.revision for attempt in attempts)
        if len(revisions) != len(set(revisions)):
            raise ValueError("attempt revisions must be unique")
        snapshot_ids = tuple(attempt.evaluated.snapshot.candidate_id for attempt in attempts)
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("development attempt snapshot IDs must be unique")
        trial_ids = tuple(
            observation.trial.trial_id for attempt in attempts for observation in attempt.evaluated.observations
        )
        if len(trial_ids) != len(set(trial_ids)):
            raise ValueError("development attempt trial IDs must be unique")
        if self.best_attempt_id is not None and self.best_attempt_id not in attempt_ids:
            raise ValueError("best_attempt_id must reference an attempt")
        memory = validate_memory_entries(self.memory)
        if len(memory) > AVO_MEMORY_LIMIT:
            raise ValueError(f"AVO state memory must contain at most {AVO_MEMORY_LIMIT} entries")
        object.__setattr__(self, "memory", memory)
        if self.parent_snapshot is not None:
            if not isinstance(self.parent_snapshot, WorkspaceSnapshot):
                raise TypeError("parent_snapshot must be a WorkspaceSnapshot")
            if self.parent_snapshot.candidate_id != self.parent_candidate_id:
                raise ValueError("parent_snapshot must match parent_candidate_id")
        object.__setattr__(self, "attempts", attempts)


def is_revision_valid(
    state: AVOState,
    revision: int,
    snapshot: WorkspaceSnapshot | None = None,
    *,
    parent_snapshot: WorkspaceSnapshot | None = None,
) -> bool:
    """Return whether an evaluated revision can be submitted now.

    A revision is eligible only when it is current, has exact development
    evidence, and is not the host-selected parent material.
    """
    if not isinstance(state, AVOState):
        raise TypeError("state must be an AVOState")
    if isinstance(revision, bool) or not isinstance(revision, int):
        raise TypeError("revision must be an integer")
    attempt = next((item for item in state.attempts if item.revision == revision), None)
    if attempt is None or revision != state.current_revision:
        return False
    evaluated_snapshot = attempt.evaluated.snapshot
    exact_parent = parent_snapshot or state.parent_snapshot
    if exact_parent is None:
        raise ValueError("exact parent_snapshot is required to validate revision material")
    if not isinstance(exact_parent, WorkspaceSnapshot):
        raise TypeError("parent_snapshot must be a WorkspaceSnapshot")
    if exact_parent.candidate_id != state.parent_candidate_id:
        raise ValueError("parent_snapshot must match parent_candidate_id")
    if _same_workspace_material(evaluated_snapshot, exact_parent):
        return False
    return snapshot is None or _same_workspace_material(evaluated_snapshot, snapshot)


def budget_exhaustion_reason(budget: AVOBudget, state: AVOState) -> str | None:
    """Return the first hard limit reached by usage, or ``None``."""
    if not isinstance(budget, AVOBudget):
        raise TypeError("budget must be an AVOBudget")
    if not isinstance(state, AVOState):
        raise TypeError("state must be an AVOState")
    usage = state.usage
    limits = (
        ("max_model_requests", usage.model_requests, budget.max_model_requests),
        ("max_tool_calls", usage.tool_calls, budget.max_tool_calls),
        ("max_development_evaluations", usage.development_evaluations, budget.max_development_evaluations),
        ("max_elapsed_seconds", usage.elapsed_seconds, budget.max_elapsed_seconds),
        (
            "max_consecutive_evaluation_errors",
            state.consecutive_evaluation_errors,
            budget.max_consecutive_evaluation_errors,
        ),
        (
            "max_stagnant_evaluations",
            state.consecutive_without_progress,
            budget.max_stagnant_evaluations,
        ),
        ("max_supervisor_interventions", usage.supervisor_interventions, budget.max_supervisor_interventions),
    )
    for name, observed, limit in limits:
        if limit > 0 and observed >= limit:
            return name
    token_limits: tuple[tuple[str, int | None, int | None], ...] = (
        ("max_input_tokens", usage.input_tokens, budget.max_input_tokens),
        ("max_output_tokens", usage.output_tokens, budget.max_output_tokens),
    )
    for token_name, token_observed, token_limit in token_limits:
        if token_limit is not None:
            if token_observed is None and usage.model_requests > 0:
                return f"{token_name}_unknown"
            if token_observed is not None and token_observed >= token_limit:
                return token_name
    if budget.max_cost_usd is not None:
        total_cost = usage.total_cost_usd
        if total_cost is None:
            return "max_cost_usd_unknown"
        if total_cost >= budget.max_cost_usd:
            return "max_cost_usd"
    return None


def budget_exhausted(budget: AVOBudget, state: AVOState) -> bool:
    """Return whether one of the configured hard limits has been reached."""
    return budget_exhaustion_reason(budget, state) is not None


@dataclass(frozen=True)
class VariationResult:
    """One submitted child or an explicit variation non-submission."""

    status: VariationStatus
    child: WorkspaceSnapshot | None
    mutation: MutationSummary | None
    reasoning: str
    usage: VariationUsage
    attempt: DevelopmentAttempt | None = None
    memory: tuple[AVOMemoryEntry, ...] = ()

    def __post_init__(self) -> None:
        status = VariationStatus(self.status)
        object.__setattr__(self, "status", status)
        _require_text(self.reasoning, "reasoning")
        if not isinstance(self.usage, VariationUsage):
            raise TypeError("usage must be a VariationUsage")
        memory = validate_memory_entries(self.memory)
        if len(memory) > AVO_MEMORY_LIMIT:
            raise ValueError(f"variation result memory must contain at most {AVO_MEMORY_LIMIT} entries")
        object.__setattr__(self, "memory", memory)
        if status is VariationStatus.SUBMITTED:
            if self.child is None or self.mutation is None or self.attempt is None:
                raise ValueError("submitted variation requires a child, mutation summary, and evaluated attempt")
            if not _same_workspace_material(self.attempt.evaluated.snapshot, self.child):
                raise ValueError("submitted child must match the exact evaluated attempt snapshot")
            return
        if self.child is not None or self.mutation is not None or self.attempt is not None:
            raise ValueError(f"{status.value} variation must not contain child, mutation, or attempt")


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
            evolver_usage=self.variation.usage,
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
            VariationStatus.CANCELLED: "variation cancelled",
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

    parent_score = assessment_score(parent.assessment, structural_weight=config.structural_weight)
    score = assessment_score(child.assessment, structural_weight=config.structural_weight)
    improved = score > parent_score + config.improvement_threshold
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


def rebase_evolution_state_for_parent(
    state: EvolutionState,
    parent: EvaluatedCandidate,
    *,
    structural_weight: float,
) -> EvolutionState:
    """Use the selected parent's fresh paired score for the next decision."""
    return EvolutionState(
        cycle=state.cycle,
        active_candidate_id=state.active_candidate_id,
        best_candidate_id=parent.snapshot.candidate_id,
        best_score=assessment_score(parent.assessment, structural_weight=structural_weight),
        cycles_without_improvement=state.cycles_without_improvement,
        best_score_history=state.best_score_history,
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
    if (
        child is not None
        and decision.decision is GateDecision.ACCEPTED
        and decision.improved
        and decision.effective_score is not None
    ):
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
